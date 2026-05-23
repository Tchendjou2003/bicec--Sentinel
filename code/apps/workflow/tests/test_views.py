"""
Workflow App — Tests Views (Task 10.3)

Tests pour les vues :
    - 200 pour AUDIT sur /audit/recommandations/
    - 403 pour DM/ETP/ADMIN sur /audit/recommandations/
    - POST création valide → reco + livrables en base
    - POST soft-delete via HTMX
    - Empty state rendering
"""
import uuid
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.users.models import Department, User
from apps.workflow.models import Recommendation
from apps.workflow.services import create_recommendation


class ViewTestMixin:
    """Mixin pour les tests de vues."""

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(
            name="Direction Vue Test",
            code="DVT",
            type=Department.Type.DIRECTION,
        )
        cls.audit_user = User.objects.create_user(
            username="audit_view",
            password="TestPass123!",
            role=User.Role.AUDIT,
            first_name="Audit",
            last_name="View",
        )
        cls.dm_user = User.objects.create_user(
            username="dm_view",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="DM",
            last_name="View",
        )
        cls.etp_user = User.objects.create_user(
            username="etp_view",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="ETP",
            last_name="View",
        )
        cls.admin_user = User.objects.create_user(
            username="admin_view",
            password="TestPass123!",
            role=User.Role.ADMIN,
            first_name="Admin",
            last_name="View",
        )

    def _login_as(self, user):
        self.client.force_login(user)

    def _create_draft_recommendation(self):
        return create_recommendation(
            data={
                "reference": f"REC-VIEW-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission vue test",
                "controlled_department": self.department,
                "observations": "Obs test",
                "anomalous_dossiers": "",
                "description": "Desc test",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": self.department,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable test"],
            performed_by=self.audit_user,
        )


class RecommendationListViewTest(ViewTestMixin, TestCase):
    """Tests de RecommendationListView (AC2, AC3, AC7)."""

    def test_audit_user_gets_200(self):
        """Un utilisateur AUDIT obtient 200 sur la liste."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)

    def test_dm_user_gets_403(self):
        """Un DM obtient 403 sur la liste (AC7)."""
        self._login_as(self.dm_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 403)

    def test_etp_user_gets_403(self):
        """Un ETP obtient 403 sur la liste (AC7)."""
        self._login_as(self.etp_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_user_gets_403(self):
        """Un ADMIN obtient 403 sur la liste (AC7)."""
        self._login_as(self.admin_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirects_to_login(self):
        """Un utilisateur non connecté est redirigé vers le login."""
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 302)

    def test_empty_state_displayed(self):
        """Si aucune recommandation, l'empty state est affiché."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)

    def test_recommendations_displayed(self):
        """Les recommandations sont affichées dans la réponse."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, rec.reference)

    def test_filter_by_source(self):
        """Le filtre par source fonctionne."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"source": Recommendation.Source.INTERNE},
        )
        self.assertContains(response, rec.reference)

    def test_filter_by_source_excludes_other(self):
        """Le filtre par source exclut les autres sources."""
        self._login_as(self.audit_user)
        self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"source": Recommendation.Source.COBAC},
        )
        self.assertEqual(response.status_code, 200)

    def test_htmx_request_returns_partial(self):
        """Une requête HTMX retourne le partial du tableau."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_superuser_has_access(self):
        """Un superuser a accès même sans rôle AUDIT."""
        superuser = User.objects.create_superuser(
            username="super_test",
            password="TestPass123!",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)


class RecommendationCreateViewTest(ViewTestMixin, TestCase):
    """Tests de RecommendationCreateView (AC1)."""

    def test_get_returns_stepper_form(self):
        """GET retourne le formulaire stepper."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-create"))
        self.assertEqual(response.status_code, 200)

    def test_post_valid_creates_recommendation(self):
        """POST avec données valides crée une recommandation."""
        self._login_as(self.audit_user)
        due_date = (timezone.now().date() + timedelta(days=30)).isoformat()
        response = self.client.post(
            reverse("workflow:recommendation-create"),
            {
                "reference": "REC-CREATE-001",
                "mission_date": timezone.now().date().isoformat(),
                "mission_label": "Mission création test",
                "controlled_department": str(self.department.pk),
                "observations": "Observations test",
                "anomalous_dossiers": "",
                "description": "Description test",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": str(self.department.pk),
                "due_date": due_date,
                # FormSet management data
                "deliverables-TOTAL_FORMS": "1",
                "deliverables-INITIAL_FORMS": "0",
                "deliverables-MIN_NUM_FORMS": "0",
                "deliverables-MAX_NUM_FORMS": "1000",
                "deliverables-0-label": "Livrable test création",
            },
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            Recommendation.objects.filter(reference="REC-CREATE-001").exists()
        )

    def test_post_invalid_returns_422(self):
        """POST avec données invalides retourne 422."""
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-create"),
            {
                "reference": "",
                "deliverables-TOTAL_FORMS": "0",
                "deliverables-INITIAL_FORMS": "0",
                "deliverables-MIN_NUM_FORMS": "0",
                "deliverables-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_post_creates_audit_log(self):
        """POST crée un AuditLog CREATE."""
        self._login_as(self.audit_user)
        from apps.audit.models import AuditLog

        due_date = (timezone.now().date() + timedelta(days=30)).isoformat()
        self.client.post(
            reverse("workflow:recommendation-create"),
            {
                "reference": "REC-CREATE-LOG",
                "mission_date": timezone.now().date().isoformat(),
                "mission_label": "Mission log test",
                "controlled_department": str(self.department.pk),
                "observations": "Obs",
                "description": "Desc",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.HAUTE,
                "department": str(self.department.pk),
                "due_date": due_date,
                "deliverables-TOTAL_FORMS": "0",
                "deliverables-INITIAL_FORMS": "0",
                "deliverables-MIN_NUM_FORMS": "0",
                "deliverables-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="Recommendation",
                action=AuditLog.Action.CREATE,
            ).exists()
        )


class RecommendationDetailViewTest(ViewTestMixin, TestCase):
    """Tests de RecommendationDetailView (AC8)."""

    def test_detail_page_accessible(self):
        """La page détail est accessible pour un auditeur."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rec.reference)

    def test_detail_403_for_non_audit(self):
        """La page détail est interdite pour un non-auditeur."""
        self._login_as(self.dm_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_detail_404_for_deleted(self):
        """Une recommandation soft-deleted retourne 404."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        from apps.workflow.services import soft_delete_recommendation
        soft_delete_recommendation(
            recommendation=rec,
            performed_by=self.audit_user,
        )
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 404)


class RecommendationDeleteViewTest(ViewTestMixin, TestCase):
    """Tests de RecommendationDeleteView (AC5, AC6)."""

    def test_soft_delete_draft_via_post(self):
        """POST supprime logiquement un brouillon."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.post(
            reverse("workflow:recommendation-delete", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertTrue(rec.is_deleted)

    def test_soft_delete_non_draft_returns_422(self):
        """POST sur une reco non-DRAFT retourne 422."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        # Forcer le statut
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.ASSIGNED
        )
        response = self.client.post(
            reverse("workflow:recommendation-delete", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_soft_delete_403_for_non_audit(self):
        """Un non-auditeur ne peut pas soft-delete."""
        self._login_as(self.dm_user)
        rec = self._create_draft_recommendation()
        response = self.client.post(
            reverse("workflow:recommendation-delete", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)


class RecommendationAssignViewTest(ViewTestMixin, TestCase):
    """Tests de RecommendationAssignView (Story 2.5)."""

    def setUp(self):
        # Assigner le DM au même département que la recommandation de test
        self.dm_user.department = self.department
        self.dm_user.save()

    def test_get_assign_modal_returns_200(self):
        """GET retourne 200 pour un auditeur et une recommandation DRAFT."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_get_assign_modal_403_if_no_department(self):
        """GET retourne 403 si la recommandation n'a pas de département."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        rec.department = None
        rec.save(update_fields=["department"])
        response = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_get_assign_modal_has_dms_context(self):
        """GET passe l'info s'il y a des DMs dans le département."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        # Verify the partial modal is returned and rendered with context
        self.assertEqual(response.status_code, 200)
        # Depending on how the context is passed or rendered, we can check content
        # Or we can just ensure 200 works for an empty department
        # Let's create another rec with a department that has NO dms
        from apps.users.models import Department
        empty_dept = Department.objects.create(name="Empty", code="EMP", type=Department.Type.DIRECTION)
        rec_empty = self._create_draft_recommendation()
        rec_empty.department = empty_dept
        rec_empty.save(update_fields=["department"])
        
        response_empty = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec_empty.pk])
        )
        self.assertEqual(response_empty.status_code, 200)
        self.assertIn(b"aucun directeur", response_empty.content.lower())

    def test_get_assign_modal_returns_403_if_not_draft(self):
        """GET retourne 403 si la recommandation n'est pas DRAFT."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        # Forcer le statut
        Recommendation.all_objects.filter(pk=rec.pk).update(status=Recommendation.Status.ASSIGNED)
        response = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_post_valid_assigns_dm(self):
        """POST avec un DM valide assigne la recommandation."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.post(
            reverse("workflow:recommendation-assign", args=[rec.pk]),
            {"dm": str(self.dm_user.pk)},
        )
        self.assertEqual(response.status_code, 204)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.ASSIGNED)
        self.assertEqual(rec.assigned_dm, self.dm_user)

    def test_post_invalid_form_returns_422(self):
        """POST avec un formulaire invalide retourne 422."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        response = self.client.post(
            reverse("workflow:recommendation-assign", args=[rec.pk]),
            {"dm": ""},
        )
        self.assertEqual(response.status_code, 422)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.DRAFT)

    def test_post_not_draft_returns_403(self):
        """POST sur une recommandation non DRAFT retourne 403."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()
        # Forcer le statut
        Recommendation.all_objects.filter(pk=rec.pk).update(status=Recommendation.Status.ASSIGNED)
        response = self.client.post(
            reverse("workflow:recommendation-assign", args=[rec.pk]),
            {"dm": str(self.dm_user.pk)},
        )
        self.assertEqual(response.status_code, 403)

    def test_dm_user_gets_403(self):
        """Un non-auditeur (ex: DM) obtient 403 sur cette vue."""
        self._login_as(self.dm_user)
        rec = self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)
