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
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditLog, HmacSeal
from apps.audit.services import (
    _build_seal_payload,
    diff_seal,
    generate_recommendation_seal,
    run_tamper_detection_task,
    log_tamper_detected,
    run_nightly_seal_verification,
    verify_recommendation_seal,
)
from apps.notifications.models import Notification
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

    # ── F3 — Scellement sans preuves fichier → ValueError (garde COBAC) ────
    def test_seal_without_accepted_submissions_raises(self):
        """F3 — generate_recommendation_seal() refuse de sceller un dossier sans fichier probatoire.
        Un sceau vide n'aurait aucune valeur réglementaire (COBAC / NFR-SEC-04)."""
        rec = self._make_reco(
            status=Recommendation.Status.CLOSED_RESOLVED, with_accepted_evidence=False
        )
        with self.assertRaises(ValueError) as cm:
            generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_user)
        self.assertIn("aucun fichier probatoire", str(cm.exception))

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
        # Reproduire le préchargement en masse fait par backfill_seals()
        accepted_subs = list(
            EvidenceSubmission.objects
            .filter(recommendation=rec, status="ACCEPTED")
            .order_by("created_at")
        )
        files_by_submission = {}
        for ef in EvidenceFile.objects.filter(submission__in=accepted_subs):
            files_by_submission.setdefault(ef.submission_id, []).append(ef)

        _, _, backfill_hash = mig._compute_payload(
            rec, accepted_subs, files_by_submission
        )
        self.assertEqual(service_hash, backfill_hash)


class TamperDetectionTest(TestCase):
    """Tests pour diff_seal, log_tamper_detected et run_nightly_seal_verification."""

    @classmethod
    def setUpTestData(cls):
        cls.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Dept Tamper Tests", code="TMP", type=cls.type_dir,
        )
        # audit_admin recevra les notifications TAMPER_ALERT
        cls.audit_admin = User.objects.create_user(
            username="tamper_audit_admin",
            password="TestPass123!",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        cls.dm_user = User.objects.create_user(
            username="tamper_dm",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
        )
        cls.source, _ = RecommendationSource.objects.get_or_create(
            code="COBAC", defaults={"label": "COBAC", "is_external": True},
        )

    def _make_sealed_reco(self, description="Description originale."):
        """Crée une recommandation clôturée avec une preuve acceptée et son sceau HMAC."""
        rec = create_recommendation(
            data={
                "reference": f"REC-T-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission tamper",
                "controlled_department": self.department,
                "observations": "obs",
                "anomalous_dossiers": "",
                "description": description,
                "source": self.source,
                "priority": Recommendation.Priority.HAUTE,
                "department": self.department,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=[],
            performed_by=self.audit_admin,
        )
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.CLOSED_RESOLVED,
            assigned_dm=self.dm_user,
            closed_at=timezone.now(),
            closed_by=self.audit_admin,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)
        sub = EvidenceSubmission.objects.create(
            recommendation=rec,
            submitted_by=self.dm_user,
            status=EvidenceSubmission.SubmissionStatus.ACCEPTED,
            comment="Preuves fournies.",
        )
        EvidenceFile.objects.create(
            submission=sub,
            file="evidence/tamper_test.pdf",
            original_filename="tamper_test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            sha256_hash="a" * 64,
            uploaded_by=self.dm_user,
        )
        generate_recommendation_seal(recommendation=rec, sealed_by=self.audit_admin)
        return Recommendation.all_objects.select_related(
            "source", "controlled_department", "department", "hmac_seal",
        ).get(pk=rec.pk)

    def _reload(self, rec):
        return Recommendation.all_objects.select_related(
            "source", "controlled_department", "department", "hmac_seal",
        ).get(pk=rec.pk)

    # ── diff_seal ─────────────────────────────────────────────────────────

    def test_diff_seal_returns_empty_dict_when_no_seal(self):
        rec = self._make_sealed_reco()
        HmacSeal.objects.filter(recommendation=rec).delete()
        self.assertEqual(diff_seal(self._reload(rec)), {})

    def test_diff_seal_no_changes_when_intact(self):
        rec = self._make_sealed_reco()
        result = diff_seal(rec)
        self.assertEqual(result["metadata_changes"], {})
        self.assertEqual(result["file_changes"], {})

    def test_diff_seal_detects_metadata_change(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        result = diff_seal(self._reload(rec))
        self.assertIn("description", result["metadata_changes"])
        sealed_val, current_val = result["metadata_changes"]["description"]
        self.assertEqual(sealed_val, "Description originale.")
        self.assertEqual(current_val, "ALTÉRÉ")

    def test_diff_seal_detects_file_hash_change(self):
        rec = self._make_sealed_reco()
        EvidenceFile.objects.filter(submission__recommendation=rec).update(sha256_hash="b" * 64)
        result = diff_seal(self._reload(rec))
        self.assertEqual(len(result["file_changes"]), 1)
        self.assertIn("modifié", result["file_changes"].values())

    # ── log_tamper_detected ───────────────────────────────────────────────

    def test_log_creates_audit_log_entry(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        log_tamper_detected(rec, detected_by=self.audit_admin, diff=diff_seal(rec))
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.TAMPER_DETECTED,
                content_type="Recommendation",
                object_id=rec.pk,
            ).exists()
        )

    def test_log_user_is_none_not_detector(self):
        """Le champ user doit être None : le détecteur n'est pas l'auteur de l'altération."""
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        log_tamper_detected(rec, detected_by=self.audit_admin, diff=diff_seal(rec))
        entry = AuditLog.objects.get(
            action=AuditLog.Action.TAMPER_DETECTED,
            object_id=rec.pk,
        )
        self.assertIsNone(entry.user)

    def test_log_stores_diff_and_detector_in_changes(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        diff = diff_seal(rec)
        log_tamper_detected(
            rec, detected_by=self.audit_admin, diff=diff, ip_address="10.0.0.1"
        )
        entry = AuditLog.objects.get(
            action=AuditLog.Action.TAMPER_DETECTED,
            object_id=rec.pk,
        )
        self.assertIn("description", entry.changes["metadata_changes"])
        self.assertIsNotNone(entry.changes["detected_by"])
        self.assertEqual(entry.changes["detector_ip"], "10.0.0.1")

    def test_log_notifies_admin_it_with_audit_trail_link(self):
        """Un Admin IT n'a pas accès aux vues workflow (403) : son lien pointe
        vers le journal d'audit global (Story 5.1) plutôt que le détail de
        la recommandation, contrairement à l'Audit Admin."""
        admin_it = User.objects.create_user(
            username="tamper_admin_url", password="TestPass123!", role=User.Role.ADMIN,
        )
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        log_tamper_detected(rec, detected_by=None, diff=diff_seal(rec))

        admin_notif = Notification.objects.get(
            recipient=admin_it, notification_type=Notification.Type.TAMPER_ALERT,
        )
        self.assertEqual(admin_notif.url, "/auth/admin/audit-trail/?action=TAMPER_DETECTED")

        audit_notif = Notification.objects.get(
            recipient=self.audit_admin, notification_type=Notification.Type.TAMPER_ALERT,
        )
        self.assertEqual(audit_notif.url, f"/audit/recommandations/{rec.pk}/")

    def test_log_notifies_audit_admin(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        log_tamper_detected(rec, detected_by=None, diff=diff_seal(rec))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.audit_admin,
                notification_type=Notification.Type.TAMPER_ALERT,
                is_urgent=True,
            ).exists()
        )

    def test_log_notifies_admin_it(self):
        """Les admins IT doivent aussi recevoir l'alerte (incident de sécurité)."""
        admin_it = User.objects.create_user(
            username="tamper_admin_it",
            password="TestPass123!",
            role=User.Role.ADMIN,
        )
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        log_tamper_detected(rec, detected_by=None, diff=diff_seal(rec))
        self.assertTrue(
            Notification.objects.filter(
                recipient=admin_it,
                notification_type=Notification.Type.TAMPER_ALERT,
                is_urgent=True,
            ).exists()
        )

    def test_log_idempotent_within_24h(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        rec = self._reload(rec)
        diff = diff_seal(rec)
        log_tamper_detected(rec, detected_by=self.audit_admin, diff=diff)
        log_tamper_detected(rec, detected_by=self.audit_admin, diff=diff)
        count = AuditLog.objects.filter(
            action=AuditLog.Action.TAMPER_DETECTED,
            object_id=rec.pk,
        ).count()
        self.assertEqual(count, 1)

    # ── run_nightly_seal_verification ─────────────────────────────────────

    def test_nightly_counts_checked_and_tampered(self):
        self._make_sealed_reco()
        rec_tampered = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec_tampered.pk).update(description="FALSIFIÉ")
        result = run_nightly_seal_verification()
        self.assertGreaterEqual(result["checked"], 2)
        self.assertGreaterEqual(result["tampered"], 1)

    def test_nightly_creates_audit_log_for_tampered_reco(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="FALSIFIÉ")
        run_nightly_seal_verification()
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.TAMPER_DETECTED,
                content_type="Recommendation",
                object_id=rec.pk,
            ).exists()
        )

    def test_nightly_does_not_log_intact_recos(self):
        rec = self._make_sealed_reco()
        run_nightly_seal_verification()
        self.assertFalse(
            AuditLog.objects.filter(
                action=AuditLog.Action.TAMPER_DETECTED,
                object_id=rec.pk,
            ).exists()
        )

    def test_nightly_isole_les_erreurs_par_sceau(self):
        """Une exception sur un sceau ne doit pas empêcher la vérification des
        autres (sinon toute la vérification nocturne s'arrête au premier
        sceau corrompu — NFR-SEC-03)."""
        rec_broken = self._make_sealed_reco()
        rec_tampered = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec_tampered.pk).update(description="FALSIFIÉ")

        real_verify = verify_recommendation_seal

        def _raise_for_broken(rec):
            if rec.pk == rec_broken.pk:
                raise RuntimeError("payload corrompu")
            return real_verify(rec)

        with mock.patch(
            "apps.audit.services.verify_recommendation_seal", side_effect=_raise_for_broken,
        ):
            result = run_nightly_seal_verification()

        self.assertEqual(result["errors"], 1)
        self.assertGreaterEqual(result["tampered"], 1)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.TAMPER_DETECTED,
                object_id=rec_tampered.pk,
            ).exists()
        )

    # ── run_tamper_detection_task (déport async depuis la vue GET) ────────

    def test_task_ignore_un_sceau_intact(self):
        rec = self._make_sealed_reco()
        result = run_tamper_detection_task(
            recommendation_id=str(rec.pk), detected_by_id=self.audit_admin.pk,
        )
        self.assertEqual(result, "intact: no action")
        self.assertFalse(
            AuditLog.objects.filter(
                action=AuditLog.Action.TAMPER_DETECTED, object_id=rec.pk,
            ).exists()
        )

    def test_task_journalise_un_sceau_altere(self):
        rec = self._make_sealed_reco()
        Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ")
        result = run_tamper_detection_task(
            recommendation_id=str(rec.pk), detected_by_id=self.audit_admin.pk,
        )
        self.assertEqual(result, "tamper logged")
        log = AuditLog.objects.filter(
            action=AuditLog.Action.TAMPER_DETECTED, object_id=rec.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, None)  # le détecteur n'est pas l'auteur — voir log_tamper_detected
        self.assertIn(self.audit_admin.get_full_name() or self.audit_admin.username, str(log.changes))
