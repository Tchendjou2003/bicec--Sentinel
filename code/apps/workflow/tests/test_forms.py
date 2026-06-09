"""
Workflow App — Tests Forms (Task 10.4)

Tests pour les formulaires :
    - Champs requis validés
    - clean_due_date() rejette dates passées
    - DeliverableFormSet accepte 0..N livrables
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import Department, OrgUnitType
from apps.workflow.forms import DeliverableFormSet, RecommendationForm
from apps.workflow.models import Recommendation, RecommendationSource


class RecommendationFormTest(TestCase):
    """Tests du formulaire RecommendationForm."""

    @classmethod
    def setUpTestData(cls):
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Form Test",
            code="DFT",
            type=cls.type_direction,
            is_active=True,
        )
        cls.inactive_dept = Department.objects.create(
            name="Direction Inactive",
            code="DIN",
            type=cls.type_direction,
            is_active=False,
        )
        # Story 3.7.b — source FK
        cls.source_interne, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def _valid_data(self, **overrides):
        data = {
            "reference": "REC-FORM-001",
            "mission_date": timezone.now().date(),
            "mission_label": "Mission Form",
            "controlled_department": self.department.pk,
            "observations": "Obs Form",
            "anomalous_dossiers": "",
            "description": "Desc Form",
            "source": str(self.source_interne.pk),  # Piège 4 — ModelChoiceField attend str(pk)
            "priority": Recommendation.Priority.HAUTE,
            "department": self.department.pk,
            "due_date": timezone.now().date() + timedelta(days=30),
        }
        data.update(overrides)
        return data

    def test_form_is_valid(self):
        """Le formulaire est valide avec des données correctes."""
        form = RecommendationForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_required_fields_invalid(self):
        """Les champs obligatoires sont vérifiés."""
        form = RecommendationForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("reference", form.errors)
        self.assertIn("description", form.errors)
        self.assertIn("due_date", form.errors)

    def test_clean_due_date_past_is_invalid(self):
        """La date de mise en œuvre dans le passé est rejetée (AC10)."""
        past_date = timezone.now().date() - timedelta(days=1)
        form = RecommendationForm(data=self._valid_data(due_date=past_date))
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)
        self.assertIn("passé", str(form.errors["due_date"]))

    def test_clean_due_date_today_is_valid(self):
        """La date du jour est acceptée."""
        today = timezone.now().date()
        form = RecommendationForm(data=self._valid_data(due_date=today))
        self.assertTrue(form.is_valid())

    def test_department_queryset_excludes_inactive(self):
        """Le formulaire ne propose que les départements actifs."""
        form = RecommendationForm()
        qs_controlled = form.fields["controlled_department"].queryset
        qs_dept = form.fields["department"].queryset

        self.assertIn(self.department, qs_controlled)
        self.assertNotIn(self.inactive_dept, qs_controlled)
        
        self.assertIn(self.department, qs_dept)
        self.assertNotIn(self.inactive_dept, qs_dept)


class DeliverableFormSetTest(TestCase):
    """Tests pour le DeliverableFormSet."""

    def test_formset_is_valid_with_zero_deliverables(self):
        """Le formset est valide avec 0 livrables."""
        formset = DeliverableFormSet(data={
            "deliverables-TOTAL_FORMS": "0",
            "deliverables-INITIAL_FORMS": "0",
            "deliverables-MIN_NUM_FORMS": "0",
            "deliverables-MAX_NUM_FORMS": "1000",
        })
        self.assertTrue(formset.is_valid())

    def test_formset_is_valid_with_multiple_deliverables(self):
        """Le formset est valide avec N livrables."""
        formset = DeliverableFormSet(data={
            "deliverables-TOTAL_FORMS": "2",
            "deliverables-INITIAL_FORMS": "0",
            "deliverables-MIN_NUM_FORMS": "0",
            "deliverables-MAX_NUM_FORMS": "1000",
            "deliverables-0-label": "Livrable A",
            "deliverables-1-label": "Livrable B",
        })
        self.assertTrue(formset.is_valid())
        
    def test_formset_ignores_deleted_forms(self):
        """Le formset gère correctement les formulaires marqués pour suppression."""
        formset = DeliverableFormSet(data={
            "deliverables-TOTAL_FORMS": "2",
            "deliverables-INITIAL_FORMS": "0",
            "deliverables-MIN_NUM_FORMS": "0",
            "deliverables-MAX_NUM_FORMS": "1000",
            "deliverables-0-label": "Livrable A",
            "deliverables-1-label": "Livrable B",
            "deliverables-1-DELETE": "on",
        })
        self.assertTrue(formset.is_valid())


class AssignDMFormTest(TestCase):
    """Tests du formulaire AssignDMForm (Story 2.5)."""

    @classmethod
    def setUpTestData(cls):
        from apps.users.models import User
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION_FDM", defaults={"name": "Direction FDM", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Form DM",
            code="DFD",
            type=cls.type_direction,
        )
        cls.other_department = Department.objects.create(
            name="Autre Direction",
            code="AUD",
            type=cls.type_direction,
        )
        
        cls.dm_user = User.objects.create_user(
            username="dm_valid",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
        )
        cls.dm_other = User.objects.create_user(
            username="dm_other",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.other_department,
        )

    def test_queryset_filtered_by_department(self):
        """Le queryset ne contient que les DMs du département."""
        from apps.workflow.forms import AssignDMForm
        form = AssignDMForm(department=self.department)
        qs = form.fields["dm"].queryset
        self.assertIn(self.dm_user, qs)
        self.assertNotIn(self.dm_other, qs)

    def test_queryset_empty_if_no_department(self):
        """Le queryset est vide si aucun département n'est fourni."""
        from apps.workflow.forms import AssignDMForm
        form = AssignDMForm()
        qs = form.fields["dm"].queryset
        self.assertEqual(qs.count(), 0)

    def test_form_is_valid_with_valid_dm(self):
        """Le formulaire est valide si on sélectionne un DM du département."""
        from apps.workflow.forms import AssignDMForm
        form = AssignDMForm(data={"dm": self.dm_user.pk}, department=self.department)
        self.assertTrue(form.is_valid())

    def test_form_is_invalid_if_dm_empty(self):
        """Le formulaire est invalide si aucun DM n'est sélectionné."""
        from apps.workflow.forms import AssignDMForm
        form = AssignDMForm(data={"dm": ""}, department=self.department)
        self.assertFalse(form.is_valid())
        self.assertIn("dm", form.errors)


class GetAvailableDMsForDepartmentTest(TestCase):
    """Tests pour le selector get_available_dms_for_department (Story 2.5)."""

    @classmethod
    def setUpTestData(cls):
        from apps.users.models import User
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION_SDM", defaults={"name": "Direction SDM", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Selector DM",
            code="DSD",
            type=cls.type_direction,
        )
        cls.other_department = Department.objects.create(
            name="Autre Direction Selector",
            code="ADS",
            type=cls.type_direction,
        )
        
        cls.dm_active = User.objects.create_user(
            username="dm_active",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
            is_active=True,
        )
        cls.dm_inactive = User.objects.create_user(
            username="dm_inactive",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.department,
            is_active=False,
        )
        cls.dm_other = User.objects.create_user(
            username="dm_other_dept",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.other_department,
            is_active=True,
        )
        cls.etp_user = User.objects.create_user(
            username="etp_dept",
            password="TestPass123!",
            role=User.Role.ETP,
            department=cls.department,
            is_active=True,
        )

    def test_returns_active_dms_of_department(self):
        """Retourne les DMs actifs du département."""
        from apps.workflow.selectors import get_available_dms_for_department
        dms = get_available_dms_for_department(department=self.department)
        self.assertIn(self.dm_active, dms)

    def test_excludes_inactive_dms(self):
        """Exclut les DMs inactifs."""
        from apps.workflow.selectors import get_available_dms_for_department
        dms = get_available_dms_for_department(department=self.department)
        self.assertNotIn(self.dm_inactive, dms)

    def test_excludes_dms_from_other_departments(self):
        """Exclut les DMs des autres départements."""
        from apps.workflow.selectors import get_available_dms_for_department
        dms = get_available_dms_for_department(department=self.department)
        self.assertNotIn(self.dm_other, dms)

    def test_excludes_non_dm_roles(self):
        """Exclut les utilisateurs avec un autre rôle (ex: ETP)."""
        from apps.workflow.selectors import get_available_dms_for_department
        dms = get_available_dms_for_department(department=self.department)
        self.assertNotIn(self.etp_user, dms)
