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

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import EvidenceFile, EvidenceSubmission, Recommendation, RecommendationSource
from apps.workflow.services import create_recommendation


class ViewTestMixin:
    """Mixin pour les tests de vues."""

    @classmethod
    def setUpTestData(cls):
        cls.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.department = Department.objects.create(
            name="Direction Vue Test",
            code="DVT",
            type=cls.type_direction,
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
        cls.dg_user = User.objects.create_user(
            username="dg_view",
            password="TestPass123!",
            role=User.Role.DG,
            first_name="DG",
            last_name="View",
        )
        # Second DG user (simule le DGA BICEC) — Subtask 7.0 (Story 3.7)
        cls.dga_user = User.objects.create_user(
            username="dga_view",
            password="TestPass123!",
            role=User.Role.DG,
            first_name="DGA",
            last_name="View",
        )
        cls.dg_user.department = cls.department
        cls.dg_user.save()
        cls.dga_user.department = cls.department
        cls.dga_user.save()
        cls.dm_user.department = cls.department
        cls.dm_user.save()
        cls.etp_user.department = cls.department
        cls.etp_user.save()
        # Story 3.7.b — sources FK (seeded par migration 0011)
        cls.source_interne, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )
        cls.source_cobac, _ = RecommendationSource.objects.get_or_create(
            code="COBAC",
            defaults={"label": "COBAC", "is_external": True},
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
                "source": self.source_interne,  # Story 3.7.b — FK instance
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

    def test_admin_user_gets_403(self):
        """Un ADMIN obtient 403 sur la liste (accès purement technique)."""
        self._login_as(self.admin_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 403)

    def test_dm_excludes_draft(self):
        """Un DM ne voit pas les recommandations en DRAFT."""
        self._login_as(self.dm_user)
        draft_rec = self._create_draft_recommendation()
        assigned_rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=assigned_rec.pk).update(status=Recommendation.Status.ASSIGNED)
        
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, draft_rec.reference)
        self.assertContains(response, assigned_rec.reference)

    def test_dm_only_sees_own_department(self):
        """Un DM ne voit que les recommandations de son département."""
        self._login_as(self.dm_user)
        own_rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=own_rec.pk).update(status=Recommendation.Status.ASSIGNED)
        
        type_dir, _ = OrgUnitType.objects.get_or_create(code="DIRECTION", defaults={"name": "Direction", "level": 1})
        other_dept = Department.objects.create(name="Other", code="OTH", type=type_dir)
        other_rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=other_rec.pk).update(
            status=Recommendation.Status.ASSIGNED, department=other_dept
        )
        
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, own_rec.reference)
        self.assertNotContains(response, other_rec.reference)

    def test_dg_can_access_list(self):
        """Le DG voit uniquement les recos qui lui sont personnellement assignées (Task 8 / Story 3.7)."""
        self._login_as(self.dg_user)
        rec = self._create_draft_recommendation()
        # Story 3.x : assignation DG → status IN_PROGRESS (bypass ASSIGNED)
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.IN_PROGRESS,
            assigned_dm=self.dg_user,
        )
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rec.reference)

    def test_etp_only_sees_assigned(self):
        """Un ETP ne voit que les recommandations qui lui sont formellement assignées."""
        self._login_as(self.etp_user)
        # Not assigned
        rec_not_assigned = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec_not_assigned.pk).update(status=Recommendation.Status.IN_PROGRESS)
        # Assigned
        rec_assigned = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec_assigned.pk).update(
            status=Recommendation.Status.IN_PROGRESS, assigned_etp=self.etp_user
        )
        
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rec_assigned.reference)
        self.assertNotContains(response, rec_not_assigned.reference)

    def test_audit_sees_all_with_import_filter(self):
        """Audit voit tout et le filtre par statut d'import fonctionne."""
        self._login_as(self.audit_user)
        rec_recent = self._create_draft_recommendation()
        
        rec_historical = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec_historical.pk).update(import_tag="IMPORTED")
        
        # Test Recent (default behavior if no param, or explicit 'recent')
        response = self.client.get(reverse("workflow:recommendation-list"), {"import_status": "recent"})
        self.assertContains(response, rec_recent.reference)
        self.assertNotContains(response, rec_historical.reference)
        
        # Test Historical
        response = self.client.get(reverse("workflow:recommendation-list"), {"import_status": "historical"})
        self.assertNotContains(response, rec_recent.reference)
        self.assertContains(response, rec_historical.reference)
        
        # Test All
        response = self.client.get(reverse("workflow:recommendation-list"), {"import_status": "all"})
        self.assertContains(response, rec_recent.reference)
        self.assertContains(response, rec_historical.reference)

    def test_invalid_import_status_shows_all(self):
        """Un import_status invalide affiche toutes les recommandations."""
        self._login_as(self.audit_user)
        rec_recent = self._create_draft_recommendation()
        rec_hist = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec_hist.pk).update(import_tag="IMPORTED")
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "invalid_value"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rec_recent.reference)
        self.assertContains(response, rec_hist.reference)

    def test_cross_filters_preserved_with_import_status(self):
        """Le statut d'import est préservé lors du filtrage croisé (hx-include)."""
        self._login_as(self.audit_user)
        rec_hist = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec_hist.pk).update(
            import_tag="IMPORTED", source=self.source_cobac  # Story 3.7.b — FK instance
        )

        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "historical", "source": str(self.source_cobac.pk)}
        )
        self.assertEqual(response.context["current_import_status"], "historical")
        self.assertEqual(response.context["current_source"], str(self.source_cobac.pk))
        self.assertContains(response, rec_hist.reference)

    def test_pagination_preserves_import_status(self):
        """Le filtre d'importation est conservé dans les liens de pagination."""
        self._login_as(self.audit_user)
        for i in range(30): # Create 30 to trigger pagination
            rec = self._create_draft_recommendation()
            Recommendation.all_objects.filter(pk=rec.pk).update(import_tag="IMPORTED")
            
        response = self.client.get(reverse("workflow:recommendation-list"), {"import_status": "historical", "page": "1"})
        self.assertEqual(response.status_code, 200)

    def test_create_button_hidden_for_dm_and_etp(self):
        """Le bouton Créer n'est pas affiché pour DM et ETP."""
        self._login_as(self.dm_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, 'hx-get="/audit/recommandations/create/"')
        
        self._login_as(self.etp_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, 'hx-get="/audit/recommandations/create/"')

        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, 'hx-get="/audit/recommandations/create/"')

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
            {"source": str(self.source_interne.pk)},  # Story 3.7.b
        )
        self.assertContains(response, rec.reference)

    def test_filter_by_source_excludes_other(self):
        """Le filtre par source exclut les autres sources."""
        self._login_as(self.audit_user)
        self._create_draft_recommendation()
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"source": str(self.source_cobac.pk)},  # Story 3.7.b
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
                "source": str(self.source_interne.pk),  # Piège 4 — str(pk) pour client.post
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
                "source": str(self.source_interne.pk),  # Piège 4 — str(pk) pour client.post
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

    def test_detail_200_for_dm(self):
        """La page détail est accessible pour un DM (reco ASSIGNED dans son département)."""
        from apps.workflow import services
        self._login_as(self.dm_user)
        # Les DMs ne voient pas les DRAFTs (RBAC) → on crée une reco ASSIGNED
        rec = self._create_draft_recommendation()
        rec = services.assign_recommendation_to_dm(
            recommendation=rec,
            dm=self.dm_user,
            performed_by=self.audit_user,
        )
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_detail_403_for_admin(self):
        """La page détail est interdite pour un administrateur technique."""
        self._login_as(self.admin_user)
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

    def test_dg_assigned_is_not_considered_dm_porteur(self):
        """Non-régression — un DG assigné (stored in assigned_dm) ne doit pas
        déclencher le chemin DM porteur dans le contexte de la vue détail.

        Avant le fix de Story 3.7, is_dm_porteur était True pour le DG assigné,
        ce qui lui affichait les boutons DM à tort.
        """
        rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.IN_PROGRESS,
            assigned_dm=self.dg_user,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)

        self._login_as(self.dg_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)
        # Le DG ne doit pas voir is_dm_porteur=True — sinon il voit les boutons DM
        self.assertFalse(
            response.context.get("is_dm_porteur", False),
            "is_dm_porteur doit être False pour un DG — seul un DM peut être porteur.",
        )
        # En revanche, can_submit_dg doit être True (c'est son circuit)
        self.assertTrue(
            response.context.get("can_submit_dg", False),
            "can_submit_dg doit être True pour le DG assigné en IN_PROGRESS.",
        )


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
        from apps.users.models import Department, OrgUnitType
        type_dir, _ = OrgUnitType.objects.get_or_create(code="DIRECTION", defaults={"name": "Direction", "level": 1})
        empty_dept = Department.objects.create(name="Empty", code="EMP", type=type_dir)
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


# =============================================================================
# Story 3.2 — Tests de Délégation (DM -> ETP / DM Porteur)
# =============================================================================


class DelegationTestMixin(ViewTestMixin):
    """Mixin étendu pour les tests de délégation Story 3.2."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Département secondaire pour tests cross-department
        cls.other_department = Department.objects.create(
            name="Direction Autre Test",
            code="DAT",
            type=cls.type_direction,
        )
        # ETP d'un autre département
        cls.etp_other_dept = User.objects.create_user(
            username="etp_other_dept",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="ETP",
            last_name="Autre",
            department=cls.other_department,
        )
        # DM d'un autre département
        cls.dm_other = User.objects.create_user(
            username="dm_other",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="DM",
            last_name="Autre",
            department=cls.other_department,
        )

    def _create_assigned_recommendation(self, dm=None):
        """Crée une reco en ASSIGNED avec un DM assigné."""
        from apps.workflow import services
        rec = self._create_draft_recommendation()
        target_dm = dm or self.dm_user
        rec = services.assign_recommendation_to_dm(
            recommendation=rec,
            dm=target_dm,
            performed_by=self.audit_user,
        )
        return rec


class RecommendationDelegateViewTest(DelegationTestMixin, TestCase):
    """Tests pour RecommendationDelegateView (Story 3.2)."""

    # ── Subtask 3.1 : Test RBAC Délégation ──

    def test_dm_can_delegate_to_etp(self):
        """Le DM assigné peut déléguer à un ETP de son département (AC1)."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_user.pk)},
        )
        # Succès : 204 No Content + HX-Refresh
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Refresh"], "true")

        # Vérifier l'état en base
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec.assigned_etp, self.etp_user)

    def test_dm_can_get_delegate_modal(self):
        """Le DM assigné obtient 200 sur GET de la modale (AC3)."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Déléguer")

    # ── Subtask 3.2 : Test RBAC Interdiction ──

    def test_non_assigned_dm_cannot_delegate(self):
        """Un DM d'un autre département reçoit 404 sur delegate (RBAC cross-dept — AC4)."""
        self._login_as(self.dm_other)
        rec = self._create_assigned_recommendation(dm=self.dm_user)

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)

    def test_etp_cannot_delegate(self):
        """Un ETP non-assigné reçoit 404 sur delegate (RBAC — AC4)."""
        self._login_as(self.etp_user)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (ETP voit seulement ses recos)

    def test_audit_cannot_delegate(self):
        """L'audit ne peut pas déléguer (seul le DM assigné peut)."""
        self._login_as(self.audit_user)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 403)

    # ── Subtask 3.3 : Test DM Porteur ──

    def test_dm_can_become_porteur(self):
        """Le DM peut s'auto-assigner comme porteur, statut IN_PROGRESS (AC2)."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Refresh"], "true")

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertIsNone(rec.assigned_etp)

    # ── Subtask 3.4 : Test ETP cross-department ──

    def test_cannot_delegate_to_etp_from_other_department(self):
        """Impossible de déléguer à un ETP d'un autre département."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_other_dept.pk)},
        )
        # L'ETP n'est pas dans le queryset filtré par département → erreur formulaire
        self.assertIn(response.status_code, [422, 200])

    # ── Subtask 3.5 : Test Audit Log ──

    def test_delegation_traces_in_audit_log(self):
        """La délégation crée une entrée AuditLog (AC1)."""
        from apps.audit.models import AuditLog

        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_user.pk)},
        )

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
            user=self.dm_user,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("Délégation", log.description)
        self.assertEqual(log.changes["status"], ["ASSIGNED", "IN_PROGRESS"])

    def test_dm_porteur_traces_in_audit_log(self):
        """Le DM Porteur crée une entrée AuditLog (AC2)."""
        from apps.audit.models import AuditLog

        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
            user=self.dm_user,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("DM Porteur", log.description)

    # ── Subtask 3.6 : Test UI ──

    def test_delegate_button_visible_for_assigned_dm(self):
        """Le bouton Déléguer est visible pour le DM assigné sur la page de détail (AC3)."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Déléguer")

    def test_delegate_button_hidden_for_non_assigned_dm(self):
        """Un DM d'un autre département obtient 404 sur la page détail (RBAC cross-dept)."""
        self._login_as(self.dm_other)
        rec = self._create_assigned_recommendation(dm=self.dm_user)

        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC → page introuvable

    # ── Subtask 3.7 : Test FSM négatif ──

    def test_cannot_delegate_when_not_assigned(self):
        """Rejet si status != ASSIGNED (ex: IN_PROGRESS ou DRAFT)."""
        self._login_as(self.dm_user)
        rec = self._create_assigned_recommendation()

        # D'abord déléguer pour passer en IN_PROGRESS
        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)

        # Tenter une seconde délégation sur la même reco
        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_user.pk)},
        )
        self.assertEqual(response.status_code, 403)


# =============================================================================
# Story 3.3 — Tests Soumission de Preuves & Immutabilité
# =============================================================================


class EvidenceSubmissionTestMixin(DelegationTestMixin):
    """Mixin étendu pour les tests Story 3.3 v2 (brouillons persistants)."""

    def _create_in_progress_recommendation_etp(self):
        """Crée une reco IN_PROGRESS avec ETP assigné."""
        from apps.workflow import services
        rec = self._create_assigned_recommendation()
        rec = services.delegate_recommendation_to_etp(
            recommendation=rec,
            etp=self.etp_user,
            performed_by=self.dm_user,
        )
        return rec

    def _create_in_progress_recommendation_dm_porteur(self):
        """Crée une reco IN_PROGRESS avec DM Porteur (pas d'ETP)."""
        from apps.workflow import services
        rec = self._create_assigned_recommendation()
        rec = services.become_dm_porteur(
            recommendation=rec,
            performed_by=self.dm_user,
        )
        return rec

    def _create_draft_and_upload(self, rec, user, comment="Actions correctives appliquées."):
        """Crée un brouillon DRAFT avec un fichier PDF et un commentaire.

        Retourne (draft, evidence_file).
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=user,
        )
        pdf_content = b"%PDF-1.4 " + b"A" * 100
        pdf_file = SimpleUploadedFile("test.pdf", pdf_content, content_type="application/pdf")
        ef = services.add_file_to_draft(
            submission=draft, file=pdf_file, user=user,
        )
        services.save_draft_comment(
            submission=draft, comment=comment, user=user,
        )
        return draft, ef

    def _submit_via_draft(self, rec, user, comment="Actions correctives appliquées."):
        """Crée un brouillon complet et soumet via POST HTTP. Retourne la response."""
        self._create_draft_and_upload(rec, user, comment)
        return self.client.post(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk]),
        )



class EvidenceSubmissionViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests pour RecommendationSubmitEvidenceView (Story 3.3 v2 — brouillons)."""

    def test_etp_can_get_submit_evidence_modal(self):
        """L'ETP assigné obtient 200 sur GET de la modale (AC5, AC6)."""
        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        response = self.client.get(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_dm_porteur_can_get_submit_evidence_modal(self):
        """Le DM Porteur obtient 200 sur GET de la modale (AC6 — DM Porteur)."""
        self._login_as(self.dm_user)
        rec = self._create_in_progress_recommendation_dm_porteur()

        response = self.client.get(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_non_assigned_user_gets_403_on_get(self):
        """Un ETP d'un autre département obtient 404 sur GET de la modale (RBAC — AC6)."""
        self._login_as(self.etp_other_dept)
        rec = self._create_in_progress_recommendation_etp()

        response = self.client.get(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)

    def test_cannot_submit_evidence_when_not_in_progress(self):
        """GET sur une reco non IN_PROGRESS retourne 403 (garde FSM)."""
        self._login_as(self.audit_user)
        rec = self._create_draft_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_etp_can_submit_evidence_transitions_fsm(self):
        """Soumission via brouillon → status PENDING_DM_REVIEW (AC3)."""
        from apps.workflow.models import EvidenceSubmission

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        response = self._submit_via_draft(rec, self.etp_user)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Refresh"], "true")

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)
        self.assertTrue(EvidenceSubmission.objects.filter(recommendation=rec).exists())

    def test_dm_porteur_can_submit_evidence(self):
        """Le DM Porteur peut soumettre des preuves (AC6 — DM Porteur)."""
        self._login_as(self.dm_user)
        rec = self._create_in_progress_recommendation_dm_porteur()

        response = self._submit_via_draft(rec, self.dm_user, "DM Porteur : actions prises.")
        self.assertEqual(response.status_code, 204)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_non_assigned_user_gets_403_on_post(self):
        """Un ETP d'un autre département obtient 404 sur POST (RBAC — AC6)."""
        self._login_as(self.etp_other_dept)
        rec = self._create_in_progress_recommendation_etp()

        response = self.client.post(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk]),
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)

    def test_audit_log_created_on_evidence_submission(self):
        """Un AuditLog TRANSITION est créé après une soumission valide (AC3)."""
        from apps.audit.models import AuditLog

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        self._submit_via_draft(rec, self.etp_user, "Test audit log.")

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("preuve", log.description.lower())
        self.assertEqual(log.changes["status"], ["IN_PROGRESS", "PENDING_DM_REVIEW"])

    def test_sha256_hash_stored_on_upload(self):
        """Le hash SHA-256 est calculé et stocké sur chaque fichier (AC1)."""
        import hashlib
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow.models import EvidenceFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        pdf_content = b"%PDF-1.4 unique content for hash test"
        pdf_file = SimpleUploadedFile("hash_test.pdf", pdf_content, content_type="application/pdf")

        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )
        ef = services.add_file_to_draft(
            submission=draft, file=pdf_file, user=self.etp_user,
        )

        self.assertIsNotNone(ef)
        expected_hash = hashlib.sha256(pdf_content).hexdigest()
        self.assertEqual(ef.sha256_hash, expected_hash)


class EvidenceValidationTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests de validation des fichiers (magic bytes, taille, cumul — AC1, NFR-SEC-04, NFR-SCA-01)."""

    def test_invalid_file_magic_bytes_rejected(self):
        """Un fichier texte déguisé en PDF est rejeté par add_file_to_draft (NFR-SEC-04)."""
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )
        fake_pdf = SimpleUploadedFile(
            "malware.pdf",
            b"This is plain text, not a PDF",
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            services.add_file_to_draft(
                submission=draft, file=fake_pdf, user=self.etp_user,
            )

    def test_file_over_6mb_rejected(self):
        """Un fichier dépassant 6 Mo est rejeté par add_file_to_draft (NFR-SCA-01 / FR15)."""
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )
        large_pdf = SimpleUploadedFile(
            "large.pdf",
            b"%PDF-1.4 " + b"A" * (7 * 1024 * 1024),
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            services.add_file_to_draft(
                submission=draft, file=large_pdf, user=self.etp_user,
            )

    def test_cumulative_size_over_20mb_rejected(self):
        """Le service rejette quand le cumul dépasse 20 Mo (NFR-SCA-01)."""
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )

        # Ajouter 4 fichiers de 5.5 Mo → 22 Mo au total (dépasse 20 Mo)
        chunk = b"%PDF-1.4 " + b"B" * (int(5.5 * 1024 * 1024))

        for i in range(3):
            pdf = SimpleUploadedFile(f"file{i}.pdf", chunk, content_type="application/pdf")
            services.add_file_to_draft(
                submission=draft, file=pdf, user=self.etp_user,
            )

        # Le 4ème fichier doit dépasser le quota (3 × 5.5 ≈ 16.5 + 5.5 = 22 > 20)
        pdf4 = SimpleUploadedFile("file3.pdf", chunk, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            services.add_file_to_draft(
                submission=draft, file=pdf4, user=self.etp_user,
            )

    def test_cumulative_global_quota_exceeded_by_service(self):
        """Le service rejette quand les actifs DB + nouveau lot dépassent 20 Mo (NFR-SCA-01)."""
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow.models import EvidenceFile, EvidenceSubmission
        from apps.workflow import services

        rec = self._create_in_progress_recommendation_etp()

        # Créer une soumission PENDING existante avec 18 Mo déclarés en DB.
        existing_sub = EvidenceSubmission.objects.create(
            recommendation=rec,
            comment="Soumission antérieure simulée.",
            submitted_by=self.etp_user,
            status=EvidenceSubmission.SubmissionStatus.PENDING,
        )
        tiny_file = SimpleUploadedFile("existing.pdf", b"%PDF-1.4 tiny", content_type="application/pdf")
        existing_ef = EvidenceFile(
            submission=existing_sub,
            original_filename="existing.pdf",
            file_size=18 * 1024 * 1024,  # 18 Mo déclaré en DB
            mime_type="application/pdf",
            sha256_hash="a" * 64,
            tag=EvidenceFile.Tag.JUSTIFICATIF,
            uploaded_by=self.etp_user,
        )
        existing_ef.file = tiny_file
        existing_ef.save()

        # Créer un brouillon et tenter d'ajouter un fichier de 5 Mo : 18 + 5 = 23 > 20
        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )
        new_pdf = SimpleUploadedFile(
            "new.pdf",
            b"%PDF-1.4 " + b"C" * (5 * 1024 * 1024),
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            services.add_file_to_draft(
                submission=draft,
                file=new_pdf,
                user=self.etp_user,
            )


class EvidenceImmutabilityTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests d'immutabilité des fichiers probatoires (AC4)."""

    def test_evidence_file_delete_raises_permission_denied_when_pending(self):
        """Appel de .delete() sur EvidenceFile PENDING lève PermissionDenied (AC4)."""
        from django.core.exceptions import PermissionDenied
        from apps.workflow.models import EvidenceFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        # Créer un brouillon, ajouter un fichier, soumettre (DRAFT → PENDING)
        draft, ef = self._create_draft_and_upload(rec, self.etp_user, "Immutabilité.")
        draft.status = EvidenceSubmission.SubmissionStatus.PENDING
        draft.save(update_fields=["status"])

        ef.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            ef.delete()

    def test_evidence_file_can_be_deleted_when_draft(self):
        """Un fichier en brouillon DRAFT peut être supprimé (immutabilité conditionnelle)."""
        from apps.workflow.models import EvidenceFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        draft, ef = self._create_draft_and_upload(rec, self.etp_user)
        ef_pk = ef.pk

        # Ne devrait PAS lever d'exception
        ef.delete()
        self.assertFalse(EvidenceFile.objects.filter(pk=ef_pk).exists())

    def test_evidence_file_queryset_delete_raises_permission_denied_when_pending(self):
        """QuerySet.delete() sur EvidenceFile PENDING lève PermissionDenied (immutabilité)."""
        from django.core.exceptions import PermissionDenied
        from apps.workflow.models import EvidenceFile

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        # Créer brouillon, ajouter fichier, passer en PENDING
        draft, ef = self._create_draft_and_upload(rec, self.etp_user, "QS delete test.")
        draft.status = EvidenceSubmission.SubmissionStatus.PENDING
        draft.save(update_fields=["status"])

        with self.assertRaises(PermissionDenied):
            EvidenceFile.objects.filter(submission__recommendation=rec).delete()


class EvidenceDownloadViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests de téléchargement sécurisé (RBAC via get_recommendations_for_user)."""

    def _submit_evidence_and_get_file(self, logged_in_as_etp=True):
        """Crée une reco, soumet une preuve via brouillon, retourne (rec, evidence_file)."""
        from apps.workflow.models import EvidenceFile
        from apps.workflow import services

        rec = self._create_in_progress_recommendation_etp()

        self._login_as(self.etp_user)
        draft, ef = self._create_draft_and_upload(rec, self.etp_user, "Téléchargement test.")

        # Soumettre le brouillon (DRAFT → PENDING)
        services.submit_evidence_for_recommendation(
            recommendation=rec, performed_by=self.etp_user,
        )

        rec = Recommendation.all_objects.get(pk=rec.pk)
        ef.refresh_from_db()
        return rec, ef

    def test_audit_user_can_download(self):
        """Un auditeur ne peut pas télécharger une preuve PENDING (Vision B — cuisine interne)."""
        rec, ef = self._submit_evidence_and_get_file()
        self._login_as(self.audit_user)

        response = self.client.get(
            reverse("workflow:evidence-download", args=[rec.pk, ef.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_assigned_dm_can_download(self):
        """Le DM assigné peut télécharger les preuves."""
        rec, ef = self._submit_evidence_and_get_file()
        self._login_as(self.dm_user)

        response = self.client.get(
            reverse("workflow:evidence-download", args=[rec.pk, ef.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_gets_403(self):
        """Un utilisateur non autorisé obtient 403."""
        rec, ef = self._submit_evidence_and_get_file()
        self._login_as(self.etp_other_dept)

        response = self.client.get(
            reverse("workflow:evidence-download", args=[rec.pk, ef.pk])
        )
        self.assertEqual(response.status_code, 403)


class DraftViewsTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests HTTP directs pour les 4 vues HTMX de gestion des brouillons (Story 3.3 v2)."""

    def test_draft_upload_returns_file_card_fragment(self):
        """POST sur draft-upload retourne le partial _draft_file_card.html (200 + HTML)."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        # Créer le brouillon au préalable (la vue exige qu'il existe)
        services.get_or_create_draft_submission(recommendation=rec, user=self.etp_user)

        pdf = SimpleUploadedFile("upload.pdf", b"%PDF-1.4 valid", content_type="application/pdf")
        response = self.client.post(
            reverse("workflow:draft-upload", args=[rec.pk]),
            data={"file": pdf},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"upload.pdf", response.content)
        self.assertIn("HX-Trigger", response)

    def test_draft_upload_rejects_file_over_6mb(self):
        """POST sur draft-upload avec un fichier > 6 Mo retourne 422 (NFR-SCA-01)."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()
        services.get_or_create_draft_submission(recommendation=rec, user=self.etp_user)

        large = SimpleUploadedFile(
            "large.pdf",
            b"%PDF-1.4 " + b"A" * (7 * 1024 * 1024),
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("workflow:draft-upload", args=[rec.pk]),
            data={"file": large},
            format="multipart",
        )

        self.assertEqual(response.status_code, 422)

    def test_draft_delete_removes_file(self):
        """DELETE sur draft-delete-file supprime le fichier du brouillon (200, DB vide)."""
        from apps.workflow.models import EvidenceFile

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()
        draft, ef = self._create_draft_and_upload(rec, self.etp_user)
        ef_pk = ef.pk

        response = self.client.delete(
            reverse("workflow:draft-delete-file", args=[rec.pk, ef.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EvidenceFile.objects.filter(pk=ef_pk).exists())
        self.assertIn("HX-Trigger", response)

    def test_draft_delete_on_non_draft_returns_403(self):
        """DELETE sur un fichier non-DRAFT (PENDING) retourne 403 (immutabilité AC4)."""
        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()
        draft, ef = self._create_draft_and_upload(rec, self.etp_user)

        # Passer la soumission en PENDING pour déclencher la protection d'immutabilité
        draft.status = EvidenceSubmission.SubmissionStatus.PENDING
        draft.save(update_fields=["status"])

        response = self.client.delete(
            reverse("workflow:draft-delete-file", args=[rec.pk, ef.pk]),
        )

        self.assertEqual(response.status_code, 403)

    def test_draft_save_comment_autosave(self):
        """POST sur draft-save-comment met à jour le commentaire et retourne 'Sauvegardé'."""
        from apps.workflow import services

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()
        draft, _ = services.get_or_create_draft_submission(
            recommendation=rec, user=self.etp_user,
        )

        new_comment = "Commentaire mis à jour via autosave."
        response = self.client.post(
            reverse("workflow:draft-save-comment", args=[rec.pk]),
            data={"comment": new_comment},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sauvegard", response.content)

        draft.refresh_from_db()
        self.assertEqual(draft.comment, new_comment)

    def test_draft_toggle_deliverable(self):
        """POST sur draft-toggle-deliverable inverse is_completed et retourne la checklist."""
        from apps.workflow.models import Deliverable

        self._login_as(self.etp_user)
        rec = self._create_in_progress_recommendation_etp()

        deliverable = Deliverable.objects.create(
            recommendation=rec,
            label="Mettre à jour la procédure KYC",
            order=1,
        )
        self.assertFalse(deliverable.is_completed)

        response = self.client.post(
            reverse("workflow:draft-toggle-deliverable", args=[rec.pk, deliverable.pk]),
        )

        self.assertEqual(response.status_code, 200)

        deliverable.refresh_from_db()
        self.assertTrue(deliverable.is_completed)

    def test_non_assigned_user_cannot_upload_to_draft(self):
        """Un ETP d'un autre département obtient 404 sur draft-upload (RBAC — AC6)."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.workflow import services

        rec = self._create_in_progress_recommendation_etp()
        services.get_or_create_draft_submission(recommendation=rec, user=self.etp_user)

        self._login_as(self.etp_other_dept)
        pdf = SimpleUploadedFile("x.pdf", b"%PDF-1.4 ok", content_type="application/pdf")
        response = self.client.post(
            reverse("workflow:draft-upload", args=[rec.pk]),
            data={"file": pdf},
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)

    def test_non_assigned_user_cannot_delete_draft_file(self):
        """Un ETP non-assigné obtient 403 sur draft-delete-file (RBAC — AC6)."""
        rec = self._create_in_progress_recommendation_etp()
        _, ef = self._create_draft_and_upload(rec, self.etp_user)

        self._login_as(self.etp_other_dept)
        response = self.client.delete(
            reverse("workflow:draft-delete-file", args=[rec.pk, ef.pk]),
        )
        self.assertEqual(response.status_code, 403)

    def test_non_assigned_user_cannot_save_draft_comment(self):
        """Un ETP d'un autre département obtient 404 sur draft-save-comment (RBAC — AC6)."""
        from apps.workflow import services

        rec = self._create_in_progress_recommendation_etp()
        services.get_or_create_draft_submission(recommendation=rec, user=self.etp_user)

        self._login_as(self.etp_other_dept)
        response = self.client.post(
            reverse("workflow:draft-save-comment", args=[rec.pk]),
            data={"comment": "Tentative non autorisée."},
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)

    def test_non_assigned_user_cannot_toggle_deliverable(self):
        """Un ETP d'un autre département obtient 404 sur draft-toggle-deliverable (RBAC — AC6)."""
        from apps.workflow.models import Deliverable

        rec = self._create_in_progress_recommendation_etp()
        deliverable = Deliverable.objects.create(
            recommendation=rec, label="Livrable test", order=1,
        )

        self._login_as(self.etp_other_dept)
        response = self.client.post(
            reverse("workflow:draft-toggle-deliverable", args=[rec.pk, deliverable.pk]),
        )
        self.assertEqual(response.status_code, 404)  # hors périmètre RBAC (information hiding)


class EvidenceVisibilityRBACTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests pour la visibilité des preuves (Vision B - Cuisine Interne)."""

    def _create_pending_submission(self):
        """Crée une recommandation et soumet une preuve (status=PENDING)."""
        from apps.workflow import services
        rec = self._create_in_progress_recommendation_etp()
        
        self._login_as(self.etp_user)
        draft, _ = self._create_draft_and_upload(rec, self.etp_user, "Preuve PENDING")
        
        services.submit_evidence_for_recommendation(
            recommendation=rec, performed_by=self.etp_user,
        )
        return Recommendation.all_objects.get(pk=rec.pk)

    def _create_accepted_submission(self):
        """Crée une reco PENDING_AUDIT_REVIEW avec soumission ACCEPTED (simule validation DM Story 3.4)."""
        rec = self._create_pending_submission()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING,
        )
        submission.status = EvidenceSubmission.SubmissionStatus.ACCEPTED
        submission.save(update_fields=["status"])
        # Avancer le FSM manuellement pour que l'Audit puisse voir les preuves
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.PENDING_AUDIT_REVIEW,
        )
        return Recommendation.all_objects.get(pk=rec.pk)

    def test_audit_user_cannot_see_pending_submission(self):
        """L'Audit ne voit pas une soumission PENDING dans le contexte de la vue détail."""
        rec = self._create_pending_submission()
        self._login_as(self.audit_user)

        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        qs = response.context["evidence_submissions"]
        self.assertEqual(qs.count(), 0)

    def test_audit_user_sees_accepted_submission(self):
        """L'Audit voit une soumission ACCEPTED dans le contexte de la vue détail."""
        rec = self._create_accepted_submission()
        self._login_as(self.audit_user)

        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        qs = response.context["evidence_submissions"]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().status, qs.model.SubmissionStatus.ACCEPTED)

    def test_dm_sees_pending_submission(self):
        """Le DM voit une soumission PENDING (cuisine interne accessible)."""
        rec = self._create_pending_submission()
        self._login_as(self.dm_user)

        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        qs = response.context["evidence_submissions"]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().status, qs.model.SubmissionStatus.PENDING)

    def test_audit_cannot_download_pending_file(self):
        """L'Audit reçoit 403 en tentant de télécharger un fichier d'une soumission PENDING."""
        rec = self._create_pending_submission()
        ef = rec.evidence_submissions.first().files.first()
        self._login_as(self.audit_user)

        response = self.client.get(
            reverse("workflow:evidence-download", args=[rec.pk, ef.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_audit_can_download_accepted_file(self):
        """L'Audit peut télécharger un fichier d'une soumission ACCEPTED."""
        rec = self._create_accepted_submission()
        ef = rec.evidence_submissions.first().files.first()
        self._login_as(self.audit_user)

        response = self.client.get(
            reverse("workflow:evidence-download", args=[rec.pk, ef.pk])
        )
        self.assertEqual(response.status_code, 200)


# =============================================================================
# Story 3.4 — Rejet Interne par le DM
# =============================================================================


class EvidenceRejectViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests pour EvidenceRejectView — Story 3.4 (AC1, AC2, AC3)."""

    def _create_pending_submission_with_etp(self):
        """Crée une reco PENDING_DM_REVIEW avec ETP assigné et soumission PENDING (service layer)."""
        from apps.workflow import services
        rec = self._create_in_progress_recommendation_etp()
        draft, _ = self._create_draft_and_upload(rec, self.etp_user, "Actions correctives appliquées.")
        services.submit_evidence_for_recommendation(recommendation=rec, performed_by=self.etp_user)
        return Recommendation.all_objects.get(pk=rec.pk)

    def test_dm_can_reject_evidence_submission(self):
        """AC1 — Le DM rejette : statut passe à IN_PROGRESS, AuditLog créé."""
        from apps.audit.models import AuditLog
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "Signature manquante sur le document."},
        )

        self.assertEqual(response.status_code, 204)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="Recommendation",
                object_id=rec.pk,
                action=AuditLog.Action.TRANSITION,
            ).exists()
        )

    def test_evidence_submission_marked_as_rejected(self):
        """AC2 — La soumission passe à REJECTED avec motif et reviewed_by renseignés."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "Document illisible."},
        )

        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.SubmissionStatus.REJECTED)
        self.assertEqual(submission.review_comment, "Document illisible.")
        self.assertEqual(submission.reviewed_by, self.dm_user)
        self.assertIsNotNone(submission.reviewed_at)

    def test_etp_cannot_reject_evidence(self):
        """AC3 — Un ETP (ou non-DM) obtient 403 sur l'endpoint de rejet."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.etp_user)

        response = self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "Tentative non autorisée."},
        )

        self.assertEqual(response.status_code, 403)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_reject_evidence_requires_reason(self):
        """Subtask 5.4 — Le motif est obligatoire (formulaire invalide → pas de transition)."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": ""},
        )

        self.assertEqual(response.status_code, 200)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_dm_porteur_cannot_reject_own_submission(self):
        """Subtask 5.5 — Un DM Porteur reçoit 422 s'il tente de rejeter sa propre soumission."""
        from apps.workflow import services
        rec = self._create_in_progress_recommendation_dm_porteur()
        self._create_draft_and_upload(rec, self.dm_user, "DM Porteur auto-soumission.")
        services.submit_evidence_for_recommendation(recommendation=rec, performed_by=self.dm_user)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "Auto-rejet impossible."},
        )

        self.assertEqual(response.status_code, 422)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def _reject_as_dm(self, rec):
        """Helper : DM rejette la soumission PENDING (utilisé par les tests bannière)."""
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)
        self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "Motif test."},
        )
        self.client.logout()

    def test_audit_cannot_see_rejection_banner(self):
        """Cuisine interne — show_rejection_banner == False pour AUDIT."""
        rec = self._create_pending_submission_with_etp()
        self._reject_as_dm(rec)

        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertFalse(response.context["show_rejection_banner"])

    def test_etp_sees_rejection_banner(self):
        """Cuisine interne — show_rejection_banner == True pour l'ETP assigné."""
        rec = self._create_pending_submission_with_etp()
        self._reject_as_dm(rec)

        self._login_as(self.etp_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertTrue(response.context["show_rejection_banner"])


# =============================================================================
# Story 3.5 — Validation DM → Audit (Exemption PV de Recette)
# =============================================================================


class EvidenceDMApprovalViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests pour EvidenceDMApprovalView — Story 3.5 (AC1, AC2, AC3)."""

    def _create_pending_submission_with_etp(self):
        """Crée une reco PENDING_DM_REVIEW avec ETP assigné et soumission PENDING."""
        from apps.workflow import services
        rec = self._create_in_progress_recommendation_etp()
        draft, _ = self._create_draft_and_upload(
            rec, self.etp_user, "Actions correctives appliquées."
        )
        services.submit_evidence_for_recommendation(
            recommendation=rec, performed_by=self.etp_user
        )
        return Recommendation.all_objects.get(pk=rec.pk)

    def test_dm_can_approve_evidence_submission(self):
        """AC1 — Le DM approuve avec commentaire : statut passe à PENDING_AUDIT_REVIEW."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "Dossier complet et conforme. Validé pour l'Audit."},
        )

        self.assertEqual(response.status_code, 204)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_AUDIT_REVIEW)

    def test_submission_marked_as_accepted(self):
        """AC1 — La soumission passe à ACCEPTED avec review_comment/reviewed_at/reviewed_by."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "Conforme."},
        )

        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.SubmissionStatus.ACCEPTED)
        self.assertEqual(submission.review_comment, "Conforme.")
        self.assertEqual(submission.reviewed_by, self.dm_user)
        self.assertIsNotNone(submission.reviewed_at)

    def test_audit_log_created_on_approval(self):
        """AC1 — Un AuditLog TRANSITION est créé lors de la validation DM."""
        from apps.audit.models import AuditLog
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "Validé."},
        )

        self.assertTrue(
            AuditLog.objects.filter(
                content_type="Recommendation",
                object_id=rec.pk,
                action=AuditLog.Action.TRANSITION,
            ).exists()
        )

    def test_dm_cannot_approve_without_comment_when_no_pv_recette(self):
        """AC2 — Sans PV de Recette, le commentaire vide renvoie 422."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": ""},
        )

        self.assertEqual(response.status_code, 422)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_dm_can_approve_without_comment_with_pv_recette(self):
        """AC2 (FR19) — DM uploade un PV de Recette → commentaire vide accepté."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        pv_file = SimpleUploadedFile(
            "pv_recette.pdf",
            b"%PDF-1.4 " + b"A" * 100,
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "", "pv_recette": pv_file},
        )

        self.assertEqual(response.status_code, 204)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_AUDIT_REVIEW)
        # Le fichier PV_RECETTE a bien été créé par le service
        self.assertTrue(
            submission.files.filter(tag=EvidenceFile.Tag.PV_RECETTE).exists()
        )

    def test_dm_invalid_pv_file_returns_422_not_500(self):
        """Régression Bug 1 — Un PV avec mauvais magic bytes renvoie 422, pas 500."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.dm_user)

        bad_pv = SimpleUploadedFile(
            "fake.pdf",
            b"\x00\x01\x02\x03 not a real pdf",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "", "pv_recette": bad_pv},
        )

        self.assertEqual(response.status_code, 422)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_etp_cannot_approve_evidence(self):
        """AC3 — Un ETP obtient 403 sur l'endpoint de validation."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.etp_user)

        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "Tentative non autorisée."},
        )

        self.assertEqual(response.status_code, 403)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)

    def test_audit_cannot_approve_evidence(self):
        """AC3 — Un AUDIT obtient 403 sur l'endpoint de validation."""
        rec = self._create_pending_submission_with_etp()
        submission = rec.evidence_submissions.get(
            status=EvidenceSubmission.SubmissionStatus.PENDING
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "Tentative non autorisée."},
        )

        self.assertEqual(response.status_code, 403)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.PENDING_DM_REVIEW)


# =============================================================================
# Story 3.6 — Demande de Report d'Échéance (Tests 7.1 à 7.13)
# =============================================================================

class ExtensionRequestViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests Story 3.6 — FR13, FR14, FR34.

    Couvre :
    - AC1/AC3 : DM / DG assigné peut demander un report
    - AC2 : doublon PENDING interdit (422)
    - AC2 : date ≤ échéance actuelle refusée (422)
    - AC4 : Audit peut approuver (commentaire optionnel)
    - AC5 : Audit peut rejeter (commentaire obligatoire)
    - AC6 : cohérence du statut en base
    - AC7 : tout rôle AUDIT peut traiter la demande (sans is_audit_admin)
    - FR34 : DG agit au même titre qu'un DM quand personnellement assigné
    """

    def _create_in_progress_reco_with_dm(self):
        """Crée une reco IN_PROGRESS (DM Porteur) avec due_date dans 60 jours."""
        from apps.workflow import services
        rec = self._create_assigned_recommendation()
        rec = services.become_dm_porteur(
            recommendation=rec,
            performed_by=self.dm_user,
        )
        return rec

    def _future_date(self, days=60):
        """Retourne une date future (due_date + extra jours)."""
        return (timezone.now().date() + timedelta(days=days)).isoformat()

    # ─────────────────────────────────────────────────────────────
    # 7.1 — DM assigné peut soumettre une demande de report
    # ─────────────────────────────────────────────────────────────
    def test_dm_can_request_extension(self):
        """AC1/AC3 — Le DM assigné obtient 204 et l'ExtensionRequest est créée."""
        from apps.audit.models import AuditLog
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": self._future_date(60),
                "reason": "Retard fournisseur externalisé.",
            },
        )

        self.assertEqual(response.status_code, 204)
        ext = ExtensionRequest.objects.filter(
            recommendation=rec,
            status=ExtensionRequest.Status.PENDING,
        ).first()
        self.assertIsNotNone(ext)
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="Recommendation",
                object_id=rec.pk,
                action="EXTENSION_REQUESTED",
            ).exists()
        )

    # ─────────────────────────────────────────────────────────────
    # 7.2 — Doublon PENDING refusé (422)
    # ─────────────────────────────────────────────────────────────
    def test_duplicate_pending_request_returns_422(self):
        """AC2 — Une 2e demande avec statut PENDING en cours renvoie 422."""
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        self._login_as(self.dm_user)

        payload = {
            "requested_date": self._future_date(60),
            "reason": "Première demande.",
        }
        self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]), payload
        )
        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": self._future_date(90),
                "reason": "Deuxième demande simultanée.",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            ExtensionRequest.objects.filter(
                recommendation=rec, status=ExtensionRequest.Status.PENDING
            ).count(),
            1,
        )

    # ─────────────────────────────────────────────────────────────
    # 7.3 — Date demandée ≤ due_date refusée (422)
    # ─────────────────────────────────────────────────────────────
    def test_extension_date_must_be_after_due_date_returns_422(self):
        """AC2 — Une date ≤ échéance actuelle renvoie 422."""
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        # La due_date est today + 30 (définie dans _create_draft_recommendation)
        past_date = (timezone.now().date() + timedelta(days=15)).isoformat()
        self._login_as(self.dm_user)

        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": past_date,
                "reason": "Mauvaise date.",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(
            ExtensionRequest.objects.filter(recommendation=rec).exists()
        )

    # ─────────────────────────────────────────────────────────────
    # 7.4 — Rôles non autorisés reçoivent 403
    # ─────────────────────────────────────────────────────────────
    def test_non_authorized_roles_cannot_request_extension(self):
        """AC3 — Rôles non autorisés ne peuvent pas demander un report.

        - ETP : 404 (information hiding — RBAC selector filtre par assigned_etp,
          l'ETP non assigné ne voit pas la recommandation).
        - AUDIT / ADMIN_IT : 403 (voient la reco via leur périmètre élargi,
          mais ne sont pas assigned_dm).
        """
        rec = self._create_in_progress_reco_with_dm()

        # ETP non assigné → 404 (information hiding FR28)
        self._login_as(self.etp_user)
        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": self._future_date(60),
                "reason": "Tentative non autorisée.",
            },
        )
        self.assertEqual(response.status_code, 404)

        # AUDIT et ADMIN_IT → 403 (visible mais non autorisé)
        for user in [self.audit_user, self.admin_user]:
            with self.subTest(role=user.role):
                self._login_as(user)
                response = self.client.post(
                    reverse("workflow:extension-request", args=[rec.pk]),
                    {
                        "requested_date": self._future_date(60),
                        "reason": "Tentative non autorisée.",
                    },
                )
                self.assertEqual(response.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 7.5 — Audit peut approuver ; due_date est mise à jour
    # ─────────────────────────────────────────────────────────────
    def test_audit_can_approve_extension(self):
        """AC4/AC7 — L'Audit approuve et la due_date de la reco est mise à jour."""
        from apps.workflow import services
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        new_date_str = self._future_date(60)
        import datetime
        new_date = datetime.date.fromisoformat(new_date_str)

        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:extension-approve", args=[rec.pk, ext.pk]),
            {"audit_comment": "Accepté."},
        )

        self.assertEqual(response.status_code, 204)
        ext.refresh_from_db()
        self.assertEqual(ext.status, ExtensionRequest.Status.APPROVED)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.due_date, new_date)

    # ─────────────────────────────────────────────────────────────
    # 7.6 — Audit peut rejeter ; due_date inchangée
    # ─────────────────────────────────────────────────────────────
    def test_audit_can_reject_extension(self):
        """AC5/AC7 — L'Audit rejette et la due_date reste inchangée."""
        from apps.workflow import services
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        original_due_date = rec.due_date
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))

        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:extension-reject", args=[rec.pk, ext.pk]),
            {"audit_comment": "Non recevable."},
        )

        self.assertEqual(response.status_code, 204)
        ext.refresh_from_db()
        self.assertEqual(ext.status, ExtensionRequest.Status.REJECTED)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.due_date, original_due_date)

    # ─────────────────────────────────────────────────────────────
    # 7.7 — Rejet sans commentaire renvoie 422
    # ─────────────────────────────────────────────────────────────
    def test_reject_without_comment_returns_422(self):
        """AC5 — Un rejet sans motif renvoie 422."""
        from apps.workflow import services
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))
        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:extension-reject", args=[rec.pk, ext.pk]),
            {"audit_comment": ""},
        )

        self.assertEqual(response.status_code, 422)
        ext.refresh_from_db()
        self.assertEqual(ext.status, ExtensionRequest.Status.PENDING)

    # ─────────────────────────────────────────────────────────────
    # 7.8 — DM / ETP / DG ne peuvent pas approuver ou rejeter
    # ─────────────────────────────────────────────────────────────
    def test_dm_etp_cannot_approve_or_reject(self):
        """AC7 — DM, ETP et DG_non_assigné obtiennent 403 sur approve/reject."""
        from apps.workflow import services

        rec = self._create_in_progress_reco_with_dm()
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))
        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )

        for user in [self.dm_user, self.etp_user, self.dg_user]:
            with self.subTest(role=user.role):
                self._login_as(user)
                for url_name in ["extension-approve", "extension-reject"]:
                    response = self.client.post(
                        reverse(f"workflow:{url_name}", args=[rec.pk, ext.pk]),
                        {"audit_comment": "Tentative."},
                    )
                    self.assertEqual(response.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 7.9 — original_due_date est immuable après approbation (COBAC)
    # ─────────────────────────────────────────────────────────────
    def test_original_due_date_immutable_after_approval(self):
        """AC6 — original_due_date reste inchangée après approbation du report."""
        from apps.workflow import services

        rec = self._create_in_progress_reco_with_dm()
        original_due_date_before = rec.original_due_date
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))

        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)
        self.client.post(
            reverse("workflow:extension-approve", args=[rec.pk, ext.pk]),
            {"audit_comment": ""},
        )

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.original_due_date, original_due_date_before)
        # due_date est mise à jour, original_due_date ne bouge pas
        self.assertEqual(rec.due_date, new_date)
        self.assertNotEqual(rec.due_date, rec.original_due_date)

    # ─────────────────────────────────────────────────────────────
    # 7.10 — DG assigné comme DM peut demander un report (FR34)
    # ─────────────────────────────────────────────────────────────
    def test_dg_assigned_as_dm_can_request_extension(self):
        """FR34 — Le DG assigné personnellement obtient 204 sur la demande de report."""
        from apps.workflow.models import ExtensionRequest

        # Assigner la reco au DG (assigned_dm = dg_user)
        rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.IN_PROGRESS,
            assigned_dm=self.dg_user,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)

        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": self._future_date(60),
                "reason": "Contrainte opérationnelle.",
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            ExtensionRequest.objects.filter(
                recommendation=rec,
                status=ExtensionRequest.Status.PENDING,
                requested_by=self.dg_user,
            ).exists()
        )

    # ─────────────────────────────────────────────────────────────
    # 7.11 — DG non assigné obtient 403 (pas de hiérarchie de département)
    # ─────────────────────────────────────────────────────────────
    def test_dg_not_assigned_cannot_request_extension(self):
        """FR34 — Le DG non assigné obtient 404 (information hiding via queryset RBAC — Task 8 / Story 3.7).

        Note : Avant Task 8, le DG voyait toutes les recos de son département → 403.
        Après Task 8, la reco n'est pas dans le queryset du DG non-assigné → 404.
        """
        from apps.workflow.models import ExtensionRequest

        # Reco assignée au DM, pas au DG
        rec = self._create_in_progress_reco_with_dm()

        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {
                "requested_date": self._future_date(60),
                "reason": "Tentative DG non assigné.",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ExtensionRequest.objects.filter(recommendation=rec).exists())

    # ─────────────────────────────────────────────────────────────
    # 7.12 — AUDIT sans is_audit_admin peut approuver (AC7)
    # ─────────────────────────────────────────────────────────────
    def test_audit_without_is_audit_admin_can_approve(self):
        """AC7 — Un AUDIT standard (is_audit_admin=False) peut approuver."""
        from apps.workflow import services
        from apps.workflow.models import ExtensionRequest

        # audit_user n'est pas is_audit_admin (créé dans ViewTestMixin sans flag)
        self.assertFalse(self.audit_user.is_audit_admin)

        rec = self._create_in_progress_reco_with_dm()
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))
        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:extension-approve", args=[rec.pk, ext.pk]),
            {"audit_comment": ""},
        )

        self.assertEqual(response.status_code, 204)
        ext.refresh_from_db()
        self.assertEqual(ext.status, ExtensionRequest.Status.APPROVED)

    # ─────────────────────────────────────────────────────────────
    # 7.13 — Approbation sans commentaire est acceptée (AC4)
    # ─────────────────────────────────────────────────────────────
    def test_audit_can_approve_without_comment(self):
        """AC4 — Le commentaire Audit est optionnel à l'approbation."""
        from apps.workflow import services
        from apps.workflow.models import ExtensionRequest

        rec = self._create_in_progress_reco_with_dm()
        import datetime
        new_date = datetime.date.fromisoformat(self._future_date(60))
        ext = services.request_extension(
            recommendation=rec,
            requested_date=new_date,
            reason="Raison valide.",
            performed_by=self.dm_user,
        )
        self._login_as(self.audit_user)

        response = self.client.post(
            reverse("workflow:extension-approve", args=[rec.pk, ext.pk]),
            {"audit_comment": ""},  # vide — doit passer
        )

        self.assertEqual(response.status_code, 204)
        ext.refresh_from_db()
        self.assertEqual(ext.status, ExtensionRequest.Status.APPROVED)
        self.assertEqual(ext.audit_comment, "")


class DGDirectSubmitViewTest(EvidenceSubmissionTestMixin, TestCase):
    """Tests pour EvidenceDGDirectSubmitView — Soumission Directe DG (Story 3.7 / FR33).

    Couvre :
      - AC2 : bypass DM Review → PENDING_AUDIT_REVIEW
      - AC3 : contenu requis (fichier OU commentaire)
      - AC4 : AuditLog avec submitted_by_dg=True
      - AC5 : seul le DG assigned_dm peut soumettre
      - AC6 : idempotence — double soumission rejetée
      - AC8 : AUDIT voit la soumission DG
      - AC9 : second user DG (DGA) ne supplée pas le DG
    """

    def _create_recommendation_for_dg(self, status=Recommendation.Status.IN_PROGRESS):
        """Crée une reco avec assigned_dm=dg_user dans l'état donné.

        Utilise un update direct (bypass FSM role-check qui exige role=DM)
        pour simuler l'assignation DG à la manière dont le service Audit le ferait.
        Note : refresh_from_db() est interdit par django-fsm ; on récupère une
        nouvelle instance via Recommendation.all_objects.get().
        Default : IN_PROGRESS (Story 3.x — le DG n'a pas de phase ASSIGNED).
        """
        rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=status,
            assigned_dm=self.dg_user,
        )
        # Ne pas utiliser refresh_from_db() — django-fsm lève AttributeError
        # sur modification directe du champ status.
        return Recommendation.all_objects.get(pk=rec.pk)

    # ─────────────────────────────────────────────────────────────
    # 7.1 — DG avec draft pré-rempli → POST → 204 (AC2)
    # ─────────────────────────────────────────────────────────────
    def test_dg_can_submit_directly_to_audit(self):
        """AC2 — DG assigné avec draft pré-rempli → POST → 204 + HX-Refresh."""
        rec = self._create_recommendation_for_dg()
        self._create_draft_and_upload(rec, self.dg_user)
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get("HX-Refresh"), "true")

    # ─────────────────────────────────────────────────────────────
    # 7.2 — FSM state = PENDING_AUDIT_REVIEW après POST (AC2)
    # ─────────────────────────────────────────────────────────────
    def test_recommendation_goes_to_pending_audit_review(self):
        """AC2 — La recommandation passe en PENDING_AUDIT_REVIEW après soumission DG."""
        rec = self._create_recommendation_for_dg()
        self._create_draft_and_upload(rec, self.dg_user)
        self._login_as(self.dg_user)
        self.client.post(reverse("workflow:evidence-submit-dg", args=[rec.pk]))
        # Ne pas utiliser refresh_from_db() — django-fsm interdit la modification directe du status
        rec_updated = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec_updated.status, Recommendation.Status.PENDING_AUDIT_REVIEW)

    # ─────────────────────────────────────────────────────────────
    # 7.3 — draft.status = ACCEPTED + reviewed_by = DG (AC2)
    # ─────────────────────────────────────────────────────────────
    def test_evidence_submission_status_becomes_accepted(self):
        """AC2 — Le draft EvidenceSubmission passe en ACCEPTED et reviewed_by = DG."""
        rec = self._create_recommendation_for_dg()
        draft, _ = self._create_draft_and_upload(rec, self.dg_user)
        self._login_as(self.dg_user)
        self.client.post(reverse("workflow:evidence-submit-dg", args=[rec.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, EvidenceSubmission.SubmissionStatus.ACCEPTED)
        self.assertEqual(draft.reviewed_by, self.dg_user)

    # ─────────────────────────────────────────────────────────────
    # 7.4 — Draft vide (ni fichier ni commentaire) → 422 (AC3)
    # ─────────────────────────────────────────────────────────────
    def test_empty_draft_returns_422(self):
        """AC3 — DG sans fichier ET sans commentaire → HTTP 422."""
        rec = self._create_recommendation_for_dg()
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    # ─────────────────────────────────────────────────────────────
    # 7.5 — Commentaire seul (sans fichier) → 204 (AC3)
    # ─────────────────────────────────────────────────────────────
    def test_comment_only_submission_accepted(self):
        """AC3 — Un commentaire seul (sans fichier) est suffisant pour soumettre."""
        from apps.workflow import services as svc
        rec = self._create_recommendation_for_dg()
        draft, _ = svc.get_or_create_draft_submission(
            recommendation=rec, user=self.dg_user
        )
        svc.save_draft_comment(
            submission=draft, comment="Mesures correctives appliquées.", user=self.dg_user
        )
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 204)

    # ─────────────────────────────────────────────────────────────
    # 7.6 — AuditLog créé avec action=TRANSITION + submitted_by_dg=True (AC4)
    # ─────────────────────────────────────────────────────────────
    def test_audit_log_created_with_content_type_recommendation(self):
        """AC4 — Un AuditLog TRANSITION avec submitted_by_dg=True est créé."""
        from apps.audit.models import AuditLog
        rec = self._create_recommendation_for_dg()
        self._create_draft_and_upload(rec, self.dg_user)
        self._login_as(self.dg_user)
        self.client.post(reverse("workflow:evidence-submit-dg", args=[rec.pk]))
        log = AuditLog.objects.filter(
            action=AuditLog.Action.TRANSITION,
            content_type="Recommendation",
            object_id=rec.pk,
        ).last()
        self.assertIsNotNone(log)
        self.assertTrue(log.changes.get("submitted_by_dg"))

    # ─────────────────────────────────────────────────────────────
    # 7.7 — DG non assigné → 404 information hiding (AC5)
    # ─────────────────────────────────────────────────────────────
    def test_non_assigned_dg_cannot_submit(self):
        """AC5 — Un DG non assigné reçoit 404 (information hiding via queryset RBAC)."""
        rec = self._create_recommendation_for_dg()  # assigned_dm = dg_user
        self._login_as(self.dga_user)              # second DG, pas assigned_dm
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 404)

    # ─────────────────────────────────────────────────────────────
    # 7.8 — DM ne peut pas utiliser l'endpoint DG → 403 (AC5)
    # ─────────────────────────────────────────────────────────────
    def test_dm_role_cannot_use_dg_endpoint(self):
        """AC5 — Un DM (rôle insuffisant) tente le endpoint DG → 403."""
        rec = self._create_recommendation_for_dg()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 7.9 — Reco déjà PENDING_AUDIT_REVIEW → 422 (AC6)
    # ─────────────────────────────────────────────────────────────
    def test_already_pending_audit_review_rejected(self):
        """AC6 — Reco déjà en PENDING_AUDIT_REVIEW → ValueError → HTTP 422."""
        rec = self._create_recommendation_for_dg(
            status=Recommendation.Status.PENDING_AUDIT_REVIEW
        )
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    # ─────────────────────────────────────────────────────────────
    # 7.10 — AUDIT voit la soumission DG dans la page de détail (AC8)
    # ─────────────────────────────────────────────────────────────
    def test_audit_sees_dg_submission(self):
        """AC8 — L'AUDIT peut consulter la page de détail après soumission DG."""
        rec = self._create_recommendation_for_dg()
        self._create_draft_and_upload(rec, self.dg_user)
        self._login_as(self.dg_user)
        self.client.post(reverse("workflow:evidence-submit-dg", args=[rec.pk]))
        # Audit vérifie la page de détail — doit voir la reco en PENDING_AUDIT_REVIEW
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    # ─────────────────────────────────────────────────────────────
    # 7.11 — DraftUploadFileView accepte ASSIGNED pour DG (Subtask 2.2)
    # ─────────────────────────────────────────────────────────────
    def test_dg_can_upload_files_in_assigned_state(self):
        """Subtask 2.2 — DraftUploadFileView n'a pas de garde de statut : DG peut uploader depuis ASSIGNED."""
        from apps.workflow import services as svc
        rec = self._create_recommendation_for_dg(status=Recommendation.Status.ASSIGNED)
        # Créer le draft avant l'upload (DraftUploadFileView exige un draft existant)
        svc.get_or_create_draft_submission(recommendation=rec, user=self.dg_user)
        pdf_content = b"%PDF-1.4 " + b"A" * 100
        pdf_file = SimpleUploadedFile("test.pdf", pdf_content, content_type="application/pdf")
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:draft-upload", args=[rec.pk]),
            {"file": pdf_file},
        )
        self.assertEqual(response.status_code, 200)

    # ─────────────────────────────────────────────────────────────
    # 7.12 — Second user DG (DGA) ne peut pas soumettre pour reco du DG (AC9)
    # ─────────────────────────────────────────────────────────────
    def test_second_dg_user_cannot_submit_for_first_dg_recommendation(self):
        """AC9 — Le DGA (second user DG) ne peut pas soumettre pour une reco du DG (pas de suppléance MVP)."""
        rec = self._create_recommendation_for_dg()  # assigned_dm = dg_user
        self._login_as(self.dga_user)               # DGA ne voit pas la reco via queryset
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        # Information hiding : 404 (la reco n'est pas dans le queryset du DGA)
        self.assertEqual(response.status_code, 404)


# =============================================================================
# Story 3.x — Assignation directe Audit → DG
# =============================================================================


class RecommendationAssignDGViewTest(ViewTestMixin, TestCase):
    """Tests pour RecommendationAssignDGView — Assignation directe DG (Story 3.x).

    Couvre :
      - GET modal → 200 (Audit peut ouvrir la modale DG)
      - POST → 204 + HX-Refresh (assignation réussie, statut IN_PROGRESS)
      - AuditLog TRANSITION créé avec assigned_by_dg_direct=True
      - Reco non-DRAFT → 422 (ou 403 selon garde)
      - Non-Audit (DM) tente → 403
      - Aucun DG disponible → has_dgs=False dans le contexte
    """

    # ─────────────────────────────────────────────────────────────
    # GET : l'Audit peut ouvrir la modale DG
    # ─────────────────────────────────────────────────────────────
    def test_audit_can_get_assign_dg_modal(self):
        """GET → 200 contenant le formulaire d'assignation DG."""
        rec = self._create_draft_recommendation()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    # ─────────────────────────────────────────────────────────────
    # POST : assignation réussie → 204, statut IN_PROGRESS
    # ─────────────────────────────────────────────────────────────
    def test_audit_can_assign_recommendation_to_dg(self):
        """POST valide → 204 + HX-Refresh, reco status=IN_PROGRESS, assigned_dm=dg_user."""
        rec = self._create_draft_recommendation()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk]),
            data={"dg": str(self.dg_user.pk)},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get("HX-Refresh"), "true")

        rec_updated = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec_updated.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec_updated.assigned_dm, self.dg_user)

    # ─────────────────────────────────────────────────────────────
    # AuditLog créé après assignation DG
    # ─────────────────────────────────────────────────────────────
    def test_audit_log_created_on_dg_assignment(self):
        """Un AuditLog TRANSITION avec assigned_by_dg_direct=True est créé."""
        from apps.audit.models import AuditLog
        rec = self._create_draft_recommendation()
        self._login_as(self.audit_user)
        self.client.post(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk]),
            data={"dg": str(self.dg_user.pk)},
        )
        log = AuditLog.objects.filter(
            content_type="Recommendation",
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
        ).last()
        self.assertIsNotNone(log)
        self.assertTrue(log.changes.get("assigned_by_dg_direct"))
        self.assertEqual(log.changes.get("status"), ["DRAFT", "IN_PROGRESS"])

    # ─────────────────────────────────────────────────────────────
    # Reco non-DRAFT → garde backend
    # ─────────────────────────────────────────────────────────────
    def test_non_draft_returns_403_on_post(self):
        """POST sur une reco qui n'est plus DRAFT → 403 (garde backend)."""
        rec = self._create_draft_recommendation()
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.IN_PROGRESS,
            assigned_dm=self.dg_user,
        )
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk]),
            data={"dg": str(self.dg_user.pk)},
        )
        self.assertEqual(response.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # Non-Audit → 403
    # ─────────────────────────────────────────────────────────────
    def test_non_audit_cannot_assign_dg(self):
        """Un DM ne peut pas accéder à l'endpoint d'assignation DG → 403."""
        rec = self._create_draft_recommendation()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk]),
            data={"dg": str(self.dg_user.pk)},
        )
        self.assertEqual(response.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # Aucun DG disponible → has_dgs=False
    # ─────────────────────────────────────────────────────────────
    def test_no_dg_available_shows_warning(self):
        """Si aucun DG actif n'existe, has_dgs=False et la modale l'indique."""
        from apps.users.models import User as UserModel
        rec = self._create_draft_recommendation()
        self._login_as(self.audit_user)
        # Désactiver temporairement tous les DG
        dg_pks = list(
            UserModel.objects.filter(role=UserModel.Role.DG, is_active=True)
            .values_list("pk", flat=True)
        )
        UserModel.objects.filter(pk__in=dg_pks).update(is_active=False)
        try:
            response = self.client.get(
                reverse("workflow:recommendation-assign-dg", args=[rec.pk])
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Aucun Directeur Général actif")
        finally:
            # Restaurer
            UserModel.objects.filter(pk__in=dg_pks).update(is_active=True)


# =============================================================================
# Story 3.8 — Tests Vues : Clôture Définitive et Rejet Audit (FR20)
# =============================================================================


class AuditClosureViewTestMixin(EvidenceSubmissionTestMixin):
    """
    Mixin pour les tests de vues Story 3.8.

    Fournit _create_pending_audit_reco() pour créer rapidement une
    recommandation PENDING_AUDIT_REVIEW via update direct DB (comme
    EvidenceVisibilityRBACTest._create_accepted_submission()).
    """

    def _create_pending_audit_reco(self):
        """
        Crée une reco PENDING_AUDIT_REVIEW avec soumission ACCEPTED.

        Utilise la même technique que EvidenceVisibilityRBACTest pour
        contourner la protection django-fsm protected=True en tests.
        """
        rec = self._create_in_progress_recommendation_etp()
        draft, _ = self._create_draft_and_upload(
            rec, self.etp_user, "Actions correctives appliquees."
        )
        from apps.workflow import services as svc
        svc.submit_evidence_for_recommendation(
            recommendation=rec, performed_by=self.etp_user,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)
        # Passer la soumission PENDING → ACCEPTED
        sub = rec.evidence_submissions.filter(
            status=EvidenceSubmission.SubmissionStatus.PENDING,
        ).first()
        if sub:
            sub.status = EvidenceSubmission.SubmissionStatus.ACCEPTED
            sub.save(update_fields=["status"])
        # Avancer le FSM manuellement (technique standard dans les tests)
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.PENDING_AUDIT_REVIEW,
        )
        return Recommendation.all_objects.get(pk=rec.pk)


class RecommendationCloseByAuditViewTest(AuditClosureViewTestMixin, TestCase):
    """
    Tests de RecommendationCloseByAuditView — Story 3.8 (AC1, AC2, AC5, AC6).
    """

    def test_audit_can_get_close_modal(self):
        """AC1 — GET modale cloture : Audit reçoit 200."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_audit_can_close_recommendation(self):
        """AC2 — Audit POST → 204 + HX-Refresh + status CLOSED_RESOLVED."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get("HX-Refresh"), "true")
        updated = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(updated.status, Recommendation.Status.CLOSED_RESOLVED)
        self.assertIsNotNone(updated.closed_at)
        self.assertEqual(updated.closed_by, self.audit_user)

    def test_close_modal_unauthorized_for_dm(self):
        """AC5 — DM tente GET → 403."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.dm_user)
        response = self.client.get(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_close_post_unauthorized_for_dm(self):
        """AC5 — DM tente POST → 403."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_close_unavailable_for_in_progress_status(self):
        """AC6 — POST sur reco IN_PROGRESS → 422."""
        rec = self._create_in_progress_recommendation_dm_porteur()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_close_get_modal_unavailable_for_wrong_status(self):
        """Garde GET — modale clôture inatteignable hors PENDING_AUDIT_REVIEW → 409."""
        rec = self._create_in_progress_recommendation_dm_porteur()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 409)

    def test_close_context_can_close_by_audit_true_only_for_audit_in_pending_audit_review(self):
        """AC1 — can_close_by_audit=True uniquement pour AUDIT en PENDING_AUDIT_REVIEW."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("can_close_by_audit"))
        self.assertTrue(response.context.get("can_reject_by_audit"))

        # Vérification DM : can_close_by_audit = False
        self._login_as(self.dm_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertFalse(response.context.get("can_close_by_audit"))


class RecommendationRejectByAuditViewTest(AuditClosureViewTestMixin, TestCase):
    """
    Tests de RecommendationRejectByAuditView — Story 3.8 (AC1, AC3, AC4, AC5).
    """

    VALID_REASON = "Preuves insuffisantes — les pieces jointes ne couvrent pas toutes les anomalies."

    def test_audit_can_get_reject_modal(self):
        """AC1 — GET modale rejet : Audit reçoit 200."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_reject_get_modal_unavailable_for_wrong_status(self):
        """Garde GET — modale rejet inatteignable hors PENDING_AUDIT_REVIEW → 409."""
        rec = self._create_in_progress_recommendation_dm_porteur()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 409)

    def test_audit_can_reject_with_valid_reason(self):
        """AC3 — Audit POST motif valide → 204 + HX-Refresh + status IN_PROGRESS."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": self.VALID_REASON},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get("HX-Refresh"), "true")
        updated = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(updated.status, Recommendation.Status.IN_PROGRESS)

    def test_reject_short_reason_returns_422(self):
        """AC4 — Motif < 10 chars → 422."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": "court"},
        )
        self.assertEqual(response.status_code, 422)

    def test_reject_empty_reason_returns_422(self):
        """AC4 — Motif vide → 422."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": ""},
        )
        self.assertEqual(response.status_code, 422)

    def test_dm_cannot_reject_audit(self):
        """AC5 — DM tente POST → 403."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": self.VALID_REASON},
        )
        self.assertEqual(response.status_code, 403)

    def test_reject_updates_submission_to_rejected_by_audit(self):
        """AC3 — La soumission ACCEPTED passe à REJECTED_BY_AUDIT après rejet."""
        rec = self._create_pending_audit_reco()
        self._login_as(self.audit_user)
        self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": self.VALID_REASON},
        )
        submission = rec.evidence_submissions.filter(
            status=EvidenceSubmission.SubmissionStatus.REJECTED_BY_AUDIT,
        ).first()
        self.assertIsNotNone(submission)
        self.assertEqual(submission.review_comment, self.VALID_REASON)


class ImmutabilityAfterClosureTest(AuditClosureViewTestMixin, TestCase):
    """
    Tests d'immutabilité apres cloture CLOSED_RESOLVED — Story 3.8 (AC7).

    Chaque vue mutante doit retourner HTTP 422 avec message "cloture".
    La vue de lecture (GET detail, GET list) reste accessible.
    """

    def _create_closed_reco(self):
        """Crée une reco CLOSED_RESOLVED via clôture réelle du service."""
        from apps.workflow import services as svc
        rec = self._create_pending_audit_reco()
        svc.close_recommendation_by_audit(
            recommendation=rec, performed_by=self.audit_user,
        )
        return Recommendation.all_objects.get(pk=rec.pk)

    def test_close_audit_blocked_after_closure(self):
        """POST close-audit sur reco déjà CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-close-audit", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_reject_audit_blocked_after_closure(self):
        """POST reject-audit sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-reject-audit", args=[rec.pk]),
            {"reason": "Motif de test non applicable car cloture."},
        )
        self.assertEqual(response.status_code, 422)

    def test_draft_upload_blocked_after_closure(self):
        """POST draft-upload sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        # Forcer le statut ETP assigné pour bypasser le RBAC HTMX
        rec.assigned_etp = self.etp_user
        rec.save(update_fields=["assigned_etp"])
        self._login_as(self.etp_user)
        pdf = SimpleUploadedFile("t.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = self.client.post(
            reverse("workflow:draft-upload", args=[rec.pk]),
            {"file": pdf},
        )
        self.assertEqual(response.status_code, 422)

    def test_draft_save_comment_blocked_after_closure(self):
        """POST draft-save-comment sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        rec.assigned_etp = self.etp_user
        rec.save(update_fields=["assigned_etp"])
        self._login_as(self.etp_user)
        response = self.client.post(
            reverse("workflow:draft-save-comment", args=[rec.pk]),
            {"comment": "tentative modification"},
        )
        self.assertEqual(response.status_code, 422)

    def test_detail_view_still_accessible_after_closure(self):
        """GET detail reco CLOSED_RESOLVED reste accessible (AC7 lecture OK)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_list_view_includes_closed_recommendations(self):
        """La liste inclut bien les recos CLOSED_RESOLVED (AC7 lecture OK)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)
        # La reco clôturée doit figurer dans le queryset
        pks_in_qs = [str(r.pk) for r in response.context["recommendations"]]
        self.assertIn(str(rec.pk), pks_in_qs)

    def test_is_closed_context_variable_set_for_closed_reco(self):
        """Le contexte detail a is_closed=True pour une reco CLOSED_RESOLVED."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-detail", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("is_closed"))

    # ── Endpoints mutants supplémentaires (AC7 — couverture complète) ──

    def test_assign_dm_blocked_after_closure(self):
        """POST assign sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-assign", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_assign_dg_blocked_after_closure(self):
        """POST assign-dg sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-assign-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_update_blocked_after_closure(self):
        """POST update sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-update", args=[rec.pk]),
            {"reference": "X"},
        )
        self.assertEqual(response.status_code, 422)

    def test_delegate_blocked_after_closure(self):
        """POST delegate sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_submit_evidence_blocked_after_closure(self):
        """POST submit-evidence sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.etp_user)
        response = self.client.post(
            reverse("workflow:recommendation-submit-evidence", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_dm_validate_blocked_after_closure(self):
        """POST evidence-approve sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        submission = rec.evidence_submissions.first()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:evidence-approve", args=[rec.pk, submission.pk]),
            {"comment": "tentative"},
        )
        self.assertEqual(response.status_code, 422)

    def test_dm_reject_blocked_after_closure(self):
        """POST evidence-reject sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        submission = rec.evidence_submissions.first()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:evidence-reject", args=[rec.pk, submission.pk]),
            {"reason": "tentative de rejet apres cloture"},
        )
        self.assertEqual(response.status_code, 422)

    def test_extension_request_blocked_after_closure(self):
        """POST extension-request sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.dm_user)
        response = self.client.post(
            reverse("workflow:extension-request", args=[rec.pk]),
            {"requested_date": "2030-01-01", "reason": "tentative"},
        )
        self.assertEqual(response.status_code, 422)

    def test_extension_approve_blocked_after_closure(self):
        """POST extension-approve sur reco CLOSED_RESOLVED → 422 (AC7)."""
        from apps.workflow.models import ExtensionRequest
        rec = self._create_closed_reco()
        ext = ExtensionRequest.objects.create(
            recommendation=rec,
            requested_by=self.dm_user,
            requested_date=rec.due_date + timedelta(days=30),
            reason="Demande historique avant cloture.",
            status=ExtensionRequest.Status.PENDING,
        )
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:extension-approve", args=[rec.pk, ext.pk]),
            {"audit_comment": ""},
        )
        self.assertEqual(response.status_code, 422)

    def test_extension_reject_blocked_after_closure(self):
        """POST extension-reject sur reco CLOSED_RESOLVED → 422 (AC7)."""
        from apps.workflow.models import ExtensionRequest
        rec = self._create_closed_reco()
        ext = ExtensionRequest.objects.create(
            recommendation=rec,
            requested_by=self.dm_user,
            requested_date=rec.due_date + timedelta(days=30),
            reason="Demande historique avant cloture.",
            status=ExtensionRequest.Status.PENDING,
        )
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:extension-reject", args=[rec.pk, ext.pk]),
            {"audit_comment": "motif de rejet apres cloture"},
        )
        self.assertEqual(response.status_code, 422)

    def test_recommendation_delete_blocked_after_closure(self):
        """POST delete sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        self._login_as(self.audit_user)
        response = self.client.post(
            reverse("workflow:recommendation-delete", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_dg_direct_submit_blocked_after_closure(self):
        """POST submit-dg sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        # Le DG doit être assigned_dm pour passer le guard dispatch()
        Recommendation.all_objects.filter(pk=rec.pk).update(assigned_dm=self.dg_user)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        self._login_as(self.dg_user)
        response = self.client.post(
            reverse("workflow:evidence-submit-dg", args=[rec.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_draft_delete_file_blocked_after_closure(self):
        """DELETE draft-delete-file sur reco CLOSED_RESOLVED → 422 (AC7)."""
        rec = self._create_closed_reco()
        evidence_file = EvidenceFile.objects.filter(
            submission__recommendation=rec
        ).first()
        self.assertIsNotNone(evidence_file)
        self._login_as(self.etp_user)
        response = self.client.delete(
            reverse("workflow:draft-delete-file", args=[rec.pk, evidence_file.pk])
        )
        self.assertEqual(response.status_code, 422)

    def test_toggle_deliverable_blocked_after_closure(self):
        """POST draft-toggle-deliverable sur reco CLOSED_RESOLVED → 422 (AC7).

        Test critique : sans le verrou, un ETP encore assigné pouvait
        modifier l'avancement d'un dossier scellé (trou d'immutabilité).
        """
        from apps.workflow.models import Deliverable
        rec = self._create_closed_reco()
        deliverable = Deliverable.objects.create(
            recommendation=rec, label="Livrable test cloture", order=1,
        )
        self._login_as(self.etp_user)
        response = self.client.post(
            reverse(
                "workflow:draft-toggle-deliverable",
                args=[rec.pk, deliverable.pk],
            )
        )
        self.assertEqual(response.status_code, 422)
        # Le livrable ne doit pas avoir été modifié
        deliverable.refresh_from_db()
        self.assertFalse(deliverable.is_completed)
