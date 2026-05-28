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
