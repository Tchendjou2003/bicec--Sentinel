"""
Workflow App — Tests Modèles (Task 10.1)

Tests pour les modèles Recommendation et Deliverable :
    - Champs et valeurs par défaut
    - Custom Manager (soft-deleted exclues de objects, présentes dans all_objects)
    - progress_percentage (0/0=0%, 2/4=50%, 3/3=100%)
    - Validation clean() (date passée, reference unique)
"""
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import (
    ActiveRecommendationManager,
    Deliverable,
    Recommendation,
    RecommendationSource,
)


class RecommendationModelTestMixin:
    """Mixin pour créer des données de test réutilisables."""

    @classmethod
    def setUpTestData(cls):
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Test",
            code="DT",
            type=cls.type_direction,
        )
        cls.audit_user = User.objects.create_user(
            username="auditeur_test",
            password="TestPass123!",
            role=User.Role.AUDIT,
            first_name="Test",
            last_name="Auditeur",
        )
        # Story 3.7.b — source FK (seeded par migration 0011)
        cls.source_interne, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def _make_recommendation(self, **overrides):
        """Helper : crée une recommandation avec des valeurs par défaut."""
        defaults = {
            "reference": f"REC-TEST-{uuid.uuid4().hex[:6].upper()}",
            "mission_date": timezone.now().date(),
            "mission_label": "Mission de test",
            "controlled_department": self.department,
            "observations": "Observations de test",
            "description": "Description de la recommandation test",
            "source": self.source_interne,
            "priority": Recommendation.Priority.MOYENNE,
            "department": self.department,
            "due_date": timezone.now().date() + timedelta(days=30),
            "original_due_date": timezone.now().date() + timedelta(days=30),
            "created_by": self.audit_user,
        }
        defaults.update(overrides)
        return Recommendation.all_objects.create(**defaults)


class RecommendationFieldsTest(RecommendationModelTestMixin, TestCase):
    """Tests des champs et valeurs par défaut du modèle Recommendation."""

    def test_default_status_is_draft(self):
        """Le statut par défaut est DRAFT."""
        rec = self._make_recommendation()
        self.assertEqual(rec.status, Recommendation.Status.DRAFT)

    def test_default_is_deleted_false(self):
        """is_deleted par défaut est False."""
        rec = self._make_recommendation()
        self.assertFalse(rec.is_deleted)

    def test_default_is_overdue_false(self):
        """is_overdue par défaut est False."""
        rec = self._make_recommendation()
        self.assertFalse(rec.is_overdue)

    def test_deleted_at_null_by_default(self):
        """deleted_at est null par défaut."""
        rec = self._make_recommendation()
        self.assertIsNone(rec.deleted_at)

    def test_uuid_primary_key(self):
        """La clé primaire est un UUID."""
        rec = self._make_recommendation()
        self.assertIsInstance(rec.pk, uuid.UUID)

    def test_str_representation(self):
        """__str__ contient la référence et la priorité."""
        rec = self._make_recommendation(reference="REC-2026-001")
        self.assertIn("REC-2026-001", str(rec))

    def test_reference_unique_constraint(self):
        """La référence doit être unique en base."""
        self._make_recommendation(reference="REC-UNIQUE-001")
        with self.assertRaises(Exception):
            self._make_recommendation(reference="REC-UNIQUE-001")

    def test_source_is_fk_to_recommendation_source(self):
        """Vérifie que le champ source est un FK vers RecommendationSource (Story 3.7.b)."""
        rec = self._make_recommendation()
        self.assertIsInstance(rec.source, RecommendationSource)
        self.assertEqual(rec.source.code, "INTERNE")

    def test_priority_choices(self):
        """Vérifie les 4 choix de criticité."""
        self.assertEqual(len(Recommendation.Priority.choices), 4)

    def test_status_choices(self):
        """Vérifie les 6 choix de statut."""
        self.assertEqual(len(Recommendation.Status.choices), 6)

    def test_ordering_by_created_at_desc(self):
        """L'ordering par défaut est -created_at."""
        self.assertEqual(Recommendation._meta.ordering, ["-created_at"])


class CustomManagerTest(RecommendationModelTestMixin, TestCase):
    """Tests du Custom Manager (soft-deleted exclues de objects)."""

    def test_objects_excludes_soft_deleted(self):
        """Le manager par défaut exclut les recommandations soft-deleted."""
        rec = self._make_recommendation()
        rec.is_deleted = True
        rec.deleted_at = timezone.now()
        rec.save(update_fields=["is_deleted", "deleted_at"])

        self.assertNotIn(rec, Recommendation.objects.all())

    def test_all_objects_includes_soft_deleted(self):
        """all_objects inclut les recommandations soft-deleted."""
        rec = self._make_recommendation()
        rec.is_deleted = True
        rec.deleted_at = timezone.now()
        rec.save(update_fields=["is_deleted", "deleted_at"])

        self.assertIn(rec, Recommendation.all_objects.all())

    def test_objects_includes_active(self):
        """Le manager par défaut inclut les recommandations actives."""
        rec = self._make_recommendation()
        self.assertIn(rec, Recommendation.objects.all())

    def test_default_manager_is_active(self):
        """Le manager par défaut est ActiveRecommendationManager."""
        self.assertIsInstance(Recommendation.objects, ActiveRecommendationManager)


class ProgressPercentageTest(RecommendationModelTestMixin, TestCase):
    """Tests de la propriété calculée progress_percentage."""

    def test_no_deliverables_returns_zero(self):
        """0 livrables → 0%."""
        rec = self._make_recommendation()
        self.assertEqual(rec.progress_percentage, 0)

    def test_half_completed(self):
        """2/4 livrables complétés → 50%."""
        rec = self._make_recommendation()
        for i in range(4):
            Deliverable.objects.create(
                recommendation=rec,
                label=f"Livrable {i}",
                order=i,
                is_completed=(i < 2),
            )
        self.assertEqual(rec.progress_percentage, 50)

    def test_all_completed(self):
        """3/3 livrables complétés → 100%."""
        rec = self._make_recommendation()
        for i in range(3):
            Deliverable.objects.create(
                recommendation=rec,
                label=f"Livrable {i}",
                order=i,
                is_completed=True,
            )
        self.assertEqual(rec.progress_percentage, 100)

    def test_none_completed(self):
        """0/3 livrables complétés → 0%."""
        rec = self._make_recommendation()
        for i in range(3):
            Deliverable.objects.create(
                recommendation=rec,
                label=f"Livrable {i}",
                order=i,
                is_completed=False,
            )
        self.assertEqual(rec.progress_percentage, 0)


class ValidationCleanTest(RecommendationModelTestMixin, TestCase):
    """Tests de la validation clean() du modèle."""

    def test_due_date_in_past_raises_error(self):
        """Une date de mise en œuvre passée lève une ValidationError."""
        rec = self._make_recommendation(
            due_date=timezone.now().date() - timedelta(days=1),
            original_due_date=timezone.now().date() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as cm:
            rec.full_clean(exclude=['status'])
        self.assertIn("due_date", cm.exception.message_dict)

    def test_due_date_today_is_valid(self):
        """La date d'aujourd'hui est acceptée."""
        rec = self._make_recommendation(
            due_date=timezone.now().date(),
            original_due_date=timezone.now().date(),
        )
        # Ne devrait pas lever d'exception
        rec.full_clean(exclude=['status'])

    def test_due_date_future_is_valid(self):
        """Une date future est acceptée."""
        rec = self._make_recommendation(
            due_date=timezone.now().date() + timedelta(days=90),
            original_due_date=timezone.now().date() + timedelta(days=90),
        )
        rec.full_clean(exclude=['status'])

    def test_imported_allows_past_date(self):
        """Les imports historiques (import_tag) peuvent avoir une date passée."""
        rec = self._make_recommendation(
            due_date=timezone.now().date() - timedelta(days=365),
            original_due_date=timezone.now().date() - timedelta(days=365),
            import_tag="IMPORTED",
        )
        # Ne devrait pas lever d'exception
        rec.full_clean(exclude=['status'])


class DeliverableModelTest(RecommendationModelTestMixin, TestCase):
    """Tests du modèle Deliverable."""

    def test_deliverable_creation(self):
        """Un livrable peut être créé et rattaché à une recommandation."""
        rec = self._make_recommendation()
        deliverable = Deliverable.objects.create(
            recommendation=rec,
            label="Procédure mise à jour",
            order=0,
        )
        self.assertEqual(deliverable.recommendation, rec)
        self.assertFalse(deliverable.is_completed)
        self.assertIsNone(deliverable.completed_at)

    def test_deliverable_str_uncompleted(self):
        """__str__ affiche ○ pour un livrable non complété."""
        rec = self._make_recommendation()
        deliverable = Deliverable.objects.create(
            recommendation=rec, label="Test", order=0
        )
        self.assertIn("○", str(deliverable))

    def test_deliverable_str_completed(self):
        """__str__ affiche ✓ pour un livrable complété."""
        rec = self._make_recommendation()
        deliverable = Deliverable.objects.create(
            recommendation=rec, label="Test", order=0,
            is_completed=True, completed_at=timezone.now(),
        )
        self.assertIn("✓", str(deliverable))

    def test_deliverable_cascade_delete(self):
        """Les livrables sont supprimés en cascade avec la recommandation."""
        rec = self._make_recommendation()
        Deliverable.objects.create(recommendation=rec, label="L1", order=0)
        Deliverable.objects.create(recommendation=rec, label="L2", order=1)

        rec_pk = rec.pk
        Recommendation.all_objects.filter(pk=rec_pk).delete()
        self.assertEqual(Deliverable.objects.filter(recommendation_id=rec_pk).count(), 0)

    def test_deliverable_ordering(self):
        """Les livrables sont ordonnés par (order, created_at)."""
        self.assertEqual(Deliverable._meta.ordering, ["order", "created_at"])


class AssignToDMTest(RecommendationModelTestMixin, TestCase):
    """Tests pour la méthode FSM assign_to_dm() (Story 2.5)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dm_user = User.objects.create_user(
            username="dm_model",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
        )

    def test_assign_to_dm_successful(self):
        """Transition DRAFT -> ASSIGNED réussie."""
        rec = self._make_recommendation()
        
        # Test transition
        rec.assign_to_dm(self.dm_user)
        
        self.assertEqual(rec.status, Recommendation.Status.ASSIGNED)
        self.assertEqual(rec.assigned_dm, self.dm_user)

    def test_assign_to_dm_invalid_status_raises_error(self):
        """Transition impossible depuis un autre statut que DRAFT."""
        from django_fsm import TransitionNotAllowed
        
        rec = self._make_recommendation(status=Recommendation.Status.ASSIGNED)
        
        with self.assertRaises(TransitionNotAllowed):
            rec.assign_to_dm(self.dm_user)

    def test_assign_to_dm_null_user_raises_error(self):
        """Impossible d'assigner à null."""
        from django.core.exceptions import ValidationError
        
        rec = self._make_recommendation()
        
        # Le FSM attend un User, si c'est null il lève au minimum un AttributeError ou TypeError
        # ou potentiellement un ValidationError si on le valide.
        # En fonction de l'implémentation exacte (accès à dm.role par ex), on attrape AttributeError.
        with self.assertRaises(ValidationError):
            rec.assign_to_dm(None)

