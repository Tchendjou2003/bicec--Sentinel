"""
Audit App — Tests Services Crypto (Story 3.10)

Couvre la génération, la vérification et le backfill du sceau HMAC-SHA256
(FR24 / NFR-SEC-03) : AC1-AC7 de la story 3.10.
"""
import hashlib
import hmac
import importlib
import json
import uuid
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit.models import HmacSeal
from apps.audit.services import (
    _build_seal_payload,
    generate_recommendation_seal,
    verify_recommendation_seal,
)
from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import (
    EvidenceFile,
    EvidenceSubmission,
    Recommendation,
    RecommendationSource,
)
from apps.workflow.services import (
    close_recommendation_by_audit,
    create_recommendation,
)


class HmacSealServiceTest(TestCase):
    """Tests de generate/verify/backfill du sceau HMAC (Story 3.10)."""

    @classmethod
    def setUpTestData(cls):
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Opérations", code="DOP", type=cls.type_direction,
        )
        cls.audit_user = User.objects.create_user(
            username="audit_seal", password="TestPass123!", role=User.Role.AUDIT,
            first_name="Alice", last_name="Audit",
        )
        cls.dm_user = User.objects.create_user(
            username="dm_seal", password="TestPass123!", role=User.Role.DM,
            department=cls.department, first_name="Marc", last_name="Métier",
        )
        cls.source, _ = RecommendationSource.objects.get_or_create(
            code="COBAC", defaults={"label": "COBAC", "is_external": True},
        )

    # ── Helpers ──────────────────────────────────────────────────────────
    def _make_reco(self, *, status, with_accepted_evidence=True, comment="Actions correctives menées."):
        rec = create_recommendation(
            data={
                "reference": f"REC-SEAL-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission scellement",
                "controlled_department": self.department,
                "observations": "obs",
                "anomalous_dossiers": "",
                "description": "Texte prescriptif de la recommandation.",
                "source": self.source,
                "priority": Recommendation.Priority.HAUTE,
                "department": self.department,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=status,
            assigned_dm=self.dm_user,
            closed_at=timezone.now() if status == Recommendation.Status.CLOSED_RESOLVED else None,
            closed_by=self.audit_user if status == Recommendation.Status.CLOSED_RESOLVED else None,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)

        if with_accepted_evidence:
            sub = EvidenceSubmission.objects.create(
                recommendation=rec,
                submitted_by=self.dm_user,
                status=EvidenceSubmission.SubmissionStatus.ACCEPTED,
                comment=comment,
            )
            EvidenceFile.objects.create(
                submission=sub,
                file="evidence/dummy.pdf",
                original_filename="preuve.pdf",
                file_size=1024,
                mime_type="application/pdf",
                sha256_hash="a" * 64,
                uploaded_by=self.dm_user,
            )
        return rec

    # ── AC1/AC2/AC3 — Génération ─────────────────────────────────────────
    def test_generate_seal_creates_record(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        seal = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertEqual(len(seal.hmac_hash), 64)
        int(seal.hmac_hash, 16)  # hex valide
        self.assertEqual(seal.sealed_by, self.audit_user)
        self.assertEqual(seal.sealed_metadata["reference"], rec.reference)
        self.assertEqual(seal.sealed_metadata["source"], "COBAC")
        self.assertEqual(seal.sealed_metadata["controlled_department"], "DOP")
        self.assertEqual(seal.sealed_metadata["department"], "DOP")

    def test_sealed_metadata_contains_submitter_and_comment(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED,
                              comment="Mesures KYC appliquées.")
        seal = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        subs = seal.sealed_metadata["submissions"]
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["submitted_by"], str(self.dm_user.pk))
        self.assertEqual(subs[0]["comment"], "Mesures KYC appliquées.")

    def test_file_hashes_match_evidence_sha256(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        seal = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertEqual(list(seal.file_hashes.values()), ["a" * 64])

    # ── AC4 — Vérification ───────────────────────────────────────────────
    def test_verify_returns_true_for_intact_seal(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertTrue(verify_recommendation_seal(Recommendation.all_objects.get(pk=rec.pk)))

    def test_verify_returns_false_after_tampering(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        # Altération d'un champ scellé (la description)
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        self.assertFalse(verify_recommendation_seal(Recommendation.all_objects.get(pk=rec.pk)))

    def test_verify_returns_false_when_no_seal(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        self.assertFalse(verify_recommendation_seal(rec))

    def test_verify_stable_after_user_rename(self):
        """E2 — renommer l'auteur ne casse pas le sceau (payload = UUID, pas nom)."""
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.dm_user.first_name = "Marc-Antoine"
        self.dm_user.last_name = "Renommé"
        self.dm_user.save(update_fields=["first_name", "last_name"])
        self.assertTrue(verify_recommendation_seal(Recommendation.all_objects.get(pk=rec.pk)))

    # ── M2 — Sans soumission acceptée ────────────────────────────────────
    def test_seal_without_accepted_submissions(self):
        rec = self._make_reco(
            status=Recommendation.Status.CLOSED_RESOLVED, with_accepted_evidence=False
        )
        seal = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertEqual(seal.sealed_metadata["submissions"], [])
        self.assertEqual(seal.file_hashes, {})
        self.assertEqual(len(seal.hmac_hash), 64)

    # ── AC7 — Idempotence ────────────────────────────────────────────────
    def test_seal_idempotent(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        s1 = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        s2 = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(HmacSeal.objects.filter(recommendation=rec).count(), 1)

    # ── AC3 — Clé dédiée (A3 version robuste) ────────────────────────────
    @override_settings(HMAC_SECRET_KEY="cle-test-connue-3.10")
    def test_hmac_uses_dedicated_key(self):
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        sealed_metadata, file_hashes, _ = _build_seal_payload(rec)
        canonical = json.dumps(
            {"metadata": sealed_metadata, "files": file_hashes},
            sort_keys=True, separators=(",", ":"),
        )
        expected = hmac.new(
            b"cle-test-connue-3.10", canonical.encode(), hashlib.sha256
        ).hexdigest()
        seal = generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertEqual(seal.hmac_hash, expected)

    # ── AC1 — Intégration avec la clôture ────────────────────────────────
    def test_close_recommendation_generates_seal(self):
        rec = self._make_reco(status=Recommendation.Status.PENDING_AUDIT_REVIEW)
        close_recommendation_by_audit(recommendation=rec, performed_by=self.audit_user)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertTrue(hasattr(rec, "hmac_seal"))
        self.assertTrue(verify_recommendation_seal(rec))

    # ── M4 — Synchronisation backfill ↔ service ──────────────────────────
    def test_backfill_logic_matches_service(self):
        """Le calcul HMAC répliqué dans la migration de backfill est identique
        à celui du service (sinon verify échouerait sur les recos backfillées)."""
        rec = self._make_reco(status=Recommendation.Status.CLOSED_RESOLVED)
        _, _, service_hash = _build_seal_payload(rec)

        mig = importlib.import_module(
            "apps.audit.migrations.0006_backfill_hmac_seals"
        )
        _, _, backfill_hash = mig._compute_payload(
            rec, EvidenceSubmission, EvidenceFile
        )
        self.assertEqual(service_hash, backfill_hash)
