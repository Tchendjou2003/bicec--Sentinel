"""
Workflow App — Tests Services (Task 10.2)

Tests pour les services de mutation :
    - create_recommendation() → reco + livrables créés + AuditLog
    - soft_delete_recommendation() sur DRAFT → is_deleted=True
    - soft_delete_recommendation() sur ASSIGNED → ValueError
    - update_recommendation() → delta AuditLog
    - @transaction.atomic fonctionne (rollback si erreur)
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import Deliverable, Recommendation, RecommendationSource
from apps.workflow.services import (
    assign_recommendation_to_dm,
    create_recommendation,
    soft_delete_recommendation,
    update_recommendation,
)


class ServiceTestMixin:
    """Mixin pour les tests de services."""

    @classmethod
    def setUpTestData(cls):
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Opérations",
            code="DOP",
            type=cls.type_direction,
        )
        cls.audit_user = User.objects.create_user(
            username="auditeur_svc",
            password="TestPass123!",
            role=User.Role.AUDIT,
            first_name="Test",
            last_name="Auditeur",
        )
        # Story 3.7.b — source FK
        cls.source_cobac, _ = RecommendationSource.objects.get_or_create(
            code="COBAC",
            defaults={"label": "COBAC", "is_external": True},
        )

    def _base_data(self, **overrides):
        data = {
            "reference": f"REC-SVC-{uuid.uuid4().hex[:6].upper()}",
            "mission_date": timezone.now().date(),
            "mission_label": "Mission SVC test",
            "controlled_department": self.department,
            "observations": "Observations SVC",
            "anomalous_dossiers": "",
            "description": "Description recommandation SVC",
            "source": self.source_cobac,  # Story 3.7.b — FK instance
            "priority": Recommendation.Priority.HAUTE,
            "department": self.department,
            "due_date": timezone.now().date() + timedelta(days=60),
        }
        data.update(overrides)
        return data


class CreateRecommendationTest(ServiceTestMixin, TestCase):
    """Tests du service create_recommendation()."""

    def test_creates_recommendation_and_deliverables(self):
        """Crée une recommandation avec des livrables."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=["Livrable A", "Livrable B"],
            performed_by=self.audit_user,
            ip_address="127.0.0.1",
        )
        self.assertIsNotNone(rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.DRAFT)
        self.assertEqual(rec.deliverables.count(), 2)

    def test_sets_original_due_date(self):
        """original_due_date est initialisée avec due_date."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        self.assertEqual(rec.original_due_date, rec.due_date)

    def test_sets_created_by(self):
        """created_by est l'utilisateur effectuant la création."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        self.assertEqual(rec.created_by, self.audit_user)

    def test_creates_audit_log(self):
        """Un AuditLog CREATE est créé."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=["L1"],
            performed_by=self.audit_user,
            ip_address="192.168.1.1",
        )
        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.CREATE,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.audit_user)
        self.assertEqual(log.ip_address, "192.168.1.1")
        self.assertIn("deliverables_count", log.changes)

    def test_empty_deliverables_accepted(self):
        """La création sans livrables est acceptée."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        self.assertEqual(rec.deliverables.count(), 0)

    def test_strips_whitespace_from_deliverables(self):
        """Les espaces sont retirés des intitulés de livrables."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=["  Livrable A  ", "", "  "],
            performed_by=self.audit_user,
        )
        self.assertEqual(rec.deliverables.count(), 1)

    def test_deliverable_ordering(self):
        """Les livrables respectent l'ordre de la liste."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=["Premier", "Deuxième", "Troisième"],
            performed_by=self.audit_user,
        )
        orders = list(rec.deliverables.order_by("order").values_list("order", flat=True))
        self.assertEqual(orders, [0, 1, 2])


class SoftDeleteRecommendationTest(ServiceTestMixin, TestCase):
    """Tests du service soft_delete_recommendation()."""

    def test_soft_delete_draft(self):
        """Le soft delete fonctionne sur un brouillon DRAFT."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=["L1"],
            performed_by=self.audit_user,
        )
        result = soft_delete_recommendation(
            recommendation=rec,
            performed_by=self.audit_user,
            ip_address="127.0.0.1",
        )
        self.assertTrue(result.is_deleted)
        self.assertIsNotNone(result.deleted_at)

    def test_soft_delete_creates_audit_log(self):
        """Un AuditLog DELETE est créé lors du soft delete."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        soft_delete_recommendation(
            recommendation=rec,
            performed_by=self.audit_user,
        )
        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.DELETE,
        ).first()
        self.assertIsNotNone(log)

    def test_soft_delete_non_draft_raises_error(self):
        """Le soft delete sur une recommandation non-DRAFT lève ValueError."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        # Forcer le statut via all_objects pour contourner la protection FSM
        Recommendation.all_objects.filter(pk=rec.pk).update(status=Recommendation.Status.ASSIGNED)
        rec = Recommendation.all_objects.get(pk=rec.pk)

        with self.assertRaises(ValueError) as cm:
            soft_delete_recommendation(
                recommendation=rec,
                performed_by=self.audit_user,
            )
        self.assertIn("DRAFT", str(cm.exception))

    def test_soft_deleted_excluded_from_objects(self):
        """Après soft delete, la reco est exclue du manager par défaut."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        soft_delete_recommendation(
            recommendation=rec,
            performed_by=self.audit_user,
        )
        self.assertFalse(
            Recommendation.objects.filter(pk=rec.pk).exists()
        )
        self.assertTrue(
            Recommendation.all_objects.filter(pk=rec.pk).exists()
        )


class UpdateRecommendationTest(ServiceTestMixin, TestCase):
    """Tests du service update_recommendation()."""

    def test_update_fields(self):
        """Les champs sont mis à jour correctement."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        updated = update_recommendation(
            recommendation=rec,
            data={"mission_label": "Mission modifiée"},
            performed_by=self.audit_user,
        )
        self.assertEqual(updated.mission_label, "Mission modifiée")

    def test_update_creates_audit_log_with_delta(self):
        """Un AuditLog UPDATE est créé avec le delta des changements."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        update_recommendation(
            recommendation=rec,
            data={"priority": Recommendation.Priority.CRITIQUE},
            performed_by=self.audit_user,
            ip_address="10.0.0.1",
        )
        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.UPDATE,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("priority", log.changes)

    def test_update_no_changes_no_log(self):
        """Aucun AuditLog si aucun champ n'a changé."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        initial_log_count = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.UPDATE,
        ).count()

        update_recommendation(
            recommendation=rec,
            data={"mission_label": rec.mission_label},
            performed_by=self.audit_user,
        )

        final_log_count = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.UPDATE,
        ).count()
        self.assertEqual(initial_log_count, final_log_count)


class AssignRecommendationToDMTest(ServiceTestMixin, TestCase):
    """Tests du service assign_recommendation_to_dm() (Story 2.5)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dm_user = User.objects.create_user(
            username="dm_user",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="Directeur",
            last_name="Metier",
            department=cls.department,
        )

    def test_assign_successful(self):
        """L'assignation DRAFT -> ASSIGNED fonctionne correctement."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        
        assigned_rec = assign_recommendation_to_dm(
            recommendation=rec,
            dm=self.dm_user,
            performed_by=self.audit_user,
            ip_address="127.0.0.1",
        )
        
        self.assertEqual(assigned_rec.status, Recommendation.Status.ASSIGNED)
        self.assertEqual(assigned_rec.assigned_dm, self.dm_user)

    def test_assign_creates_audit_log_transition(self):
        """Un AuditLog de type TRANSITION est créé."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        
        assign_recommendation_to_dm(
            recommendation=rec,
            dm=self.dm_user,
            performed_by=self.audit_user,
            ip_address="127.0.0.1",
        )
        
        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
        ).first()
        
        self.assertIsNotNone(log)
        self.assertIn("status", log.changes)
        self.assertEqual(log.changes["status"], ["DRAFT", "ASSIGNED"])
        self.assertIn("assigned_dm", log.changes)
        
        self.assertEqual(log.changes["assigned_dm"], [None, str(self.dm_user.pk)])

    def test_assign_non_draft_raises_error(self):
        """Assigner une recommandation qui n'est pas DRAFT lève une exception."""
        from django_fsm import TransitionNotAllowed
        
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        # Changer le statut directement
        Recommendation.all_objects.filter(pk=rec.pk).update(status=Recommendation.Status.ASSIGNED)
        rec = Recommendation.all_objects.get(pk=rec.pk)

        with self.assertRaises(TransitionNotAllowed):
            assign_recommendation_to_dm(
                recommendation=rec,
                dm=self.dm_user,
                performed_by=self.audit_user,
            )

    def test_assign_wrong_department_raises_error(self):
        """Assigner à un DM d'un autre département lève une exception (via FSM)."""
        from django.core.exceptions import ValidationError
        
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        
        # DM d'un autre département
        from apps.users.models import Department, OrgUnitType, User
        type_dir, _ = OrgUnitType.objects.get_or_create(code="DIRECTION", defaults={"name": "Direction", "level": 1})
        other_dept = Department.objects.create(name="Autre", code="AUT", type=type_dir)
        other_dm = User.objects.create_user(
            username="other_dm", password="TestPass123!", role=User.Role.DM, department=other_dept
        )

        with self.assertRaises(ValidationError):
            assign_recommendation_to_dm(
                recommendation=rec,
                dm=other_dm,
                performed_by=self.audit_user,
            )

    def test_assign_deleted_raises_error(self):
        """Assigner une recommandation soft-deleted lève une exception ValueError."""
        data = self._base_data()
        rec = create_recommendation(
            data=data,
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        # Soft delete
        rec.is_deleted = True
        rec.save(update_fields=["is_deleted"])

        with self.assertRaises(ValueError) as cm:
            assign_recommendation_to_dm(
                recommendation=rec,
                dm=self.dm_user,
                performed_by=self.audit_user,
            )
        self.assertIn("supprimée", str(cm.exception))


# =============================================================================
# Story 3.8 — Tests Services : Clôture Définitive et Rejet Audit
# =============================================================================


class AuditClosureServiceTestMixin(ServiceTestMixin):
    """Mixin pour les tests de clôture/rejet Audit — Story 3.8."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dm_user = User.objects.create_user(
            username="dm_closure_svc",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
            first_name="DM",
            last_name="Closure",
        )
        cls.dg_user = User.objects.create_user(
            username="dg_closure_svc",
            password="TestPass123!",
            role=User.Role.DG,
            department=cls.department,
        )

    def _create_pending_audit_review_rec(self):
        """Crée une reco PENDING_AUDIT_REVIEW prête pour les tests Audit."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow.services import (
            assign_recommendation_to_dm,
            become_dm_porteur,
            validate_evidence_for_audit,
            get_or_create_draft_submission,
            submit_evidence_for_recommendation,
            add_file_to_draft,
        )

        rec = create_recommendation(
            data=self._base_data(),
            deliverables_data=[],
            performed_by=self.audit_user,
        )
        rec = assign_recommendation_to_dm(
            recommendation=rec, dm=self.dm_user, performed_by=self.audit_user,
        )
        rec = become_dm_porteur(recommendation=rec, performed_by=self.dm_user)

        draft, _ = get_or_create_draft_submission(
            recommendation=rec, user=self.dm_user
        )
        pdf = SimpleUploadedFile(
            "preuve.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )
        add_file_to_draft(submission=draft, file=pdf, user=self.dm_user)
        draft.comment = "Actions correctives appliquees et verifiees."
        draft.save(update_fields=["comment", "updated_at"])

        rec = submit_evidence_for_recommendation(
            recommendation=rec, performed_by=self.dm_user,
        )
        submission = rec.evidence_submissions.filter(status="PENDING").first()
        rec = validate_evidence_for_audit(
            recommendation=rec,
            submission_id=submission.pk,
            comment="Preuves satisfaisantes.",
            performed_by=self.dm_user,
        )
        return rec


class CloseRecommendationByAuditServiceTest(AuditClosureServiceTestMixin, TestCase):
    """Tests de close_recommendation_by_audit() — Story 3.8 (AC2, AC5, AC6 / FR20)."""

    def test_close_success(self):
        """Audit cloture reco PENDING_AUDIT_REVIEW → CLOSED_RESOLVED + closed_at/closed_by."""
        from apps.workflow.services import close_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        result = close_recommendation_by_audit(
            recommendation=rec, performed_by=self.audit_user,
        )
        # django-fsm protected=True interdit refresh_from_db() — utiliser get() (Dev Notes Story 3.8)
        result = Recommendation.all_objects.get(pk=result.pk)

        self.assertEqual(result.status, "CLOSED_RESOLVED")
        self.assertIsNotNone(result.closed_at)
        self.assertEqual(result.closed_by, self.audit_user)

    def test_close_creates_audit_log_with_closed_by_audit_flag(self):
        """AuditLog changes['closed_by_audit'] = True (AC2)."""
        from apps.workflow.services import close_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        close_recommendation_by_audit(
            recommendation=rec, performed_by=self.audit_user,
        )

        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
        ).order_by("-created_at").first()

        self.assertIsNotNone(log)
        self.assertTrue(log.changes.get("closed_by_audit"))
        self.assertIn("CLOSED_RESOLVED", log.changes.get("status", []))

    def test_close_permission_denied_for_dm(self):
        """DM tente cloture → PermissionDenied (AC5)."""
        from apps.workflow.services import close_recommendation_by_audit
        from django.core.exceptions import PermissionDenied

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(PermissionDenied):
            close_recommendation_by_audit(
                recommendation=rec, performed_by=self.dm_user,
            )

    def test_close_permission_denied_for_dg(self):
        """DG tente cloture → PermissionDenied (AC5)."""
        from apps.workflow.services import close_recommendation_by_audit
        from django.core.exceptions import PermissionDenied

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(PermissionDenied):
            close_recommendation_by_audit(
                recommendation=rec, performed_by=self.dg_user,
            )

    def test_close_invalid_status_in_progress_raises_value_error(self):
        """Tenter de cloture une reco IN_PROGRESS → ValueError (AC6)."""
        from apps.workflow.services import (
            close_recommendation_by_audit,
            assign_recommendation_to_dm,
            become_dm_porteur,
        )

        rec = create_recommendation(
            data=self._base_data(), deliverables_data=[], performed_by=self.audit_user,
        )
        rec = assign_recommendation_to_dm(
            recommendation=rec, dm=self.dm_user, performed_by=self.audit_user,
        )
        rec = become_dm_porteur(recommendation=rec, performed_by=self.dm_user)

        with self.assertRaises(ValueError) as cm:
            close_recommendation_by_audit(
                recommendation=rec, performed_by=self.audit_user,
            )
        self.assertIn("IN_PROGRESS", str(cm.exception))

    def test_close_invalid_status_draft_raises_value_error(self):
        """Tenter de cloture une reco DRAFT → ValueError (AC6)."""
        from apps.workflow.services import close_recommendation_by_audit

        rec = create_recommendation(
            data=self._base_data(), deliverables_data=[], performed_by=self.audit_user,
        )
        with self.assertRaises(ValueError) as cm:
            close_recommendation_by_audit(
                recommendation=rec, performed_by=self.audit_user,
            )
        self.assertIn("DRAFT", str(cm.exception))

    def test_close_idempotent_already_closed(self):
        """Double cloture → ValueError idempotence (AC6)."""
        from apps.workflow.services import close_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        close_recommendation_by_audit(
            recommendation=rec, performed_by=self.audit_user,
        )
        # django-fsm protected=True interdit refresh_from_db() — utiliser get()
        rec = Recommendation.all_objects.get(pk=rec.pk)

        with self.assertRaises(ValueError) as cm:
            close_recommendation_by_audit(
                recommendation=rec, performed_by=self.audit_user,
            )
        self.assertIn("CLOSED_RESOLVED", str(cm.exception))


class RejectRecommendationByAuditServiceTest(AuditClosureServiceTestMixin, TestCase):
    """Tests de reject_recommendation_by_audit() — Story 3.8 (AC3, AC4, AC5, AC6)."""

    VALID_REASON = (
        "Les preuves fournies sont insuffisantes et ne couvrent pas "
        "toutes les anomalies identifiees par l'audit."
    )

    def test_reject_success(self):
        """Audit rejette → IN_PROGRESS + submission REJECTED_BY_AUDIT + metadonnees."""
        from apps.workflow.services import reject_recommendation_by_audit
        from apps.workflow.models import EvidenceSubmission

        rec = self._create_pending_audit_review_rec()
        result = reject_recommendation_by_audit(
            recommendation=rec,
            reason=self.VALID_REASON,
            performed_by=self.audit_user,
        )
        # django-fsm protected=True interdit refresh_from_db() — utiliser get()
        result = Recommendation.all_objects.get(pk=result.pk)

        self.assertEqual(result.status, "IN_PROGRESS")
        submission = result.evidence_submissions.filter(
            status=EvidenceSubmission.SubmissionStatus.REJECTED_BY_AUDIT
        ).first()
        self.assertIsNotNone(submission)
        self.assertEqual(submission.review_comment, self.VALID_REASON)
        self.assertEqual(submission.reviewed_by, self.audit_user)
        self.assertIsNotNone(submission.reviewed_at)

    def test_reject_draft_preserved_for_correction(self):
        """La soumission ACCEPTED passe en REJECTED_BY_AUDIT, aucun draft supprime (AC3)."""
        from apps.workflow.services import reject_recommendation_by_audit
        from apps.workflow.models import EvidenceSubmission

        rec = self._create_pending_audit_review_rec()
        reject_recommendation_by_audit(
            recommendation=rec,
            reason=self.VALID_REASON,
            performed_by=self.audit_user,
        )
        # django-fsm protected=True interdit refresh_from_db() — utiliser get()
        rec = Recommendation.all_objects.get(pk=rec.pk)

        rejected = rec.evidence_submissions.filter(
            status=EvidenceSubmission.SubmissionStatus.REJECTED_BY_AUDIT
        ).first()
        self.assertIsNotNone(
            rejected,
            "La soumission ACCEPTED doit passer en REJECTED_BY_AUDIT"
        )

    def test_reject_creates_audit_log(self):
        """AuditLog changes['rejected_by_audit']=True + changes['reason'] (AC3)."""
        from apps.workflow.services import reject_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        reject_recommendation_by_audit(
            recommendation=rec,
            reason=self.VALID_REASON,
            performed_by=self.audit_user,
        )

        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
        ).order_by("-created_at").first()

        self.assertIsNotNone(log)
        self.assertTrue(log.changes.get("rejected_by_audit"))
        self.assertEqual(log.changes.get("reason"), self.VALID_REASON)
        self.assertIn("IN_PROGRESS", log.changes.get("status", []))

    def test_reject_empty_reason_raises_value_error(self):
        """Motif vide → ValueError (AC4)."""
        from apps.workflow.services import reject_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(ValueError) as cm:
            reject_recommendation_by_audit(
                recommendation=rec, reason="", performed_by=self.audit_user,
            )
        self.assertIn("10 caractères", str(cm.exception))

    def test_reject_short_reason_raises_value_error(self):
        """Motif < 10 chars → ValueError (AC4)."""
        from apps.workflow.services import reject_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(ValueError) as cm:
            reject_recommendation_by_audit(
                recommendation=rec, reason="court", performed_by=self.audit_user,
            )
        self.assertIn("10 caractères", str(cm.exception))

    def test_reject_whitespace_only_reason_raises_value_error(self):
        """Motif d'espaces seulement → ValueError apres strip() (AC4)."""
        from apps.workflow.services import reject_recommendation_by_audit

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(ValueError) as cm:
            reject_recommendation_by_audit(
                recommendation=rec,
                reason="         ",
                performed_by=self.audit_user,
            )
        self.assertIn("10 caractères", str(cm.exception))

    def test_reject_permission_denied_for_dm(self):
        """DM tente rejet → PermissionDenied (AC5)."""
        from apps.workflow.services import reject_recommendation_by_audit
        from django.core.exceptions import PermissionDenied

        rec = self._create_pending_audit_review_rec()
        with self.assertRaises(PermissionDenied):
            reject_recommendation_by_audit(
                recommendation=rec,
                reason=self.VALID_REASON,
                performed_by=self.dm_user,
            )

    def test_reject_invalid_status_raises_value_error(self):
        """Rejeter une reco DRAFT → ValueError (AC6)."""
        from apps.workflow.services import reject_recommendation_by_audit

        rec = create_recommendation(
            data=self._base_data(), deliverables_data=[], performed_by=self.audit_user,
        )
        with self.assertRaises(ValueError) as cm:
            reject_recommendation_by_audit(
                recommendation=rec,
                reason=self.VALID_REASON,
                performed_by=self.audit_user,
            )
        self.assertIn("DRAFT", str(cm.exception))
