"""
Workflow App — Tests Vues Admin Sources (Story 3.7.b Phase A)

Vérifie les vues d'administration des sources de recommandation :
    - Contrôle d'accès (AuditAdminRequiredMixin)
    - List, Create, Edit, Toggle (HTMX : 204 + HX-Refresh)
    - Traçabilité AuditLog (NFR-SEC-05)

Note : RecommendationSource est seedée par la migration 0011 —
utiliser get_or_create pour les codes existants (INTERNE, EXTERNE…).
"""
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.users.models import User
from apps.workflow.models import RecommendationSource


class RecommendationSourceAccessTest(TestCase):
    """Contrôle d'accès aux vues sources (AuditAdminRequiredMixin)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_src",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_src",
            password="testpass123",
            role=User.Role.DM,
        )
        self.source, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def test_list_accessible_by_audit_admin(self):
        """Un Audit Admin peut accéder à la liste des sources."""
        self.client.force_login(self.audit_admin)
        response = self.client.get(reverse("workflow:source-list"))
        self.assertEqual(response.status_code, 200)

    def test_list_forbidden_for_dm(self):
        """Un DM reçoit 403 sur la liste des sources."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("workflow:source-list"))
        self.assertEqual(response.status_code, 403)

    def test_create_get_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le GET de création."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("workflow:source-create"))
        self.assertEqual(response.status_code, 403)

    def test_edit_get_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le GET d'édition."""
        self.client.force_login(self.dm_user)
        response = self.client.get(
            reverse("workflow:source-edit", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_toggle_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le toggle."""
        self.client.force_login(self.dm_user)
        response = self.client.post(
            reverse("workflow:source-toggle", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_list_accessible_by_superuser(self):
        """Un superuser peut accéder à la liste (bootstrapping)."""
        superuser = User.objects.create_superuser(
            username="super_src", password="testpass123",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("workflow:source-list"))
        self.assertEqual(response.status_code, 200)


class RecommendationSourceListTest(TestCase):
    """Tests de la vue liste des sources."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_list",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        # La migration 0011 a déjà seedé INTERNE / EXTERNE
        self.source_interne, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def test_list_renders_correct_template(self):
        """La liste utilise le bon template."""
        response = self.client.get(reverse("workflow:source-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workflow/admin/sources/list.html")

    def test_list_context_contains_sources(self):
        """Le contexte contient la clé 'sources'."""
        response = self.client.get(reverse("workflow:source-list"))
        self.assertIn("sources", response.context)
        self.assertIn(self.source_interne, response.context["sources"])

    def test_list_shows_inactive_sources_too(self):
        """La liste affiche aussi les sources inactives."""
        self.source_interne.is_active = False
        self.source_interne.save(update_fields=["is_active"])
        response = self.client.get(reverse("workflow:source-list"))
        self.assertIn(self.source_interne, response.context["sources"])
        # Remise à True pour ne pas polluer d'autres tests
        self.source_interne.is_active = True
        self.source_interne.save(update_fields=["is_active"])


class RecommendationSourceCreateTest(TestCase):
    """Tests de la vue de création (HTMX)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_create",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)

    def test_get_renders_form_partial(self):
        """GET retourne le formulaire partiel (template modal)."""
        response = self.client.get(reverse("workflow:source-create"))
        self.assertEqual(response.status_code, 200)

    def test_post_valid_returns_204_with_hx_refresh(self):
        """POST valide retourne 204 + entête HX-Refresh."""
        response = self.client.post(reverse("workflow:source-create"), {
            "code": "NEW_SRC",
            "label": "Source Test",
            "is_external": False,
        })
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.assertTrue(RecommendationSource.objects.filter(code="NEW_SRC").exists())

    def test_post_invalid_returns_422(self):
        """POST avec données invalides retourne 422."""
        response = self.client.post(reverse("workflow:source-create"), {
            "code": "",       # code requis
            "label": "",      # label requis
            "is_external": False,
        })
        self.assertEqual(response.status_code, 422)

    def test_post_creates_audit_log(self):
        """La création est tracée dans l'AuditLog (NFR-SEC-05)."""
        self.client.post(reverse("workflow:source-create"), {
            "code": "AUDIT_LOG_SRC",
            "label": "Source Tracée",
            "is_external": False,
        })
        source = RecommendationSource.objects.get(code="AUDIT_LOG_SRC")
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="RecommendationSource",
                object_id=source.pk,
                action=AuditLog.Action.CREATE,
            ).exists()
        )

    def test_post_duplicate_code_returns_422(self):
        """Un code déjà existant retourne 422 (contrainte unicité)."""
        RecommendationSource.objects.get_or_create(
            code="DUP_CODE",
            defaults={"label": "Original", "is_external": False},
        )
        response = self.client.post(reverse("workflow:source-create"), {
            "code": "DUP_CODE",
            "label": "Doublon",
            "is_external": False,
        })
        self.assertEqual(response.status_code, 422)


class RecommendationSourceEditTest(TestCase):
    """Tests de la vue d'édition (HTMX)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_edit",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        self.source, _ = RecommendationSource.objects.get_or_create(
            code="EDIT_SRC",
            defaults={"label": "À Éditer", "is_external": False},
        )

    def test_get_renders_form_with_existing_data(self):
        """GET retourne le formulaire prérempli (status 200)."""
        response = self.client.get(
            reverse("workflow:source-edit", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_post_valid_updates_source(self):
        """POST valide met à jour le libellé de la source."""
        response = self.client.post(
            reverse("workflow:source-edit", kwargs={"pk": self.source.pk}),
            {
                "code": "EDIT_SRC",   # code immuable (disabled) — envoyé quand même
                "label": "Libellé Modifié",
                "is_external": True,
            },
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.source.refresh_from_db()
        self.assertEqual(self.source.label, "Libellé Modifié")
        self.assertTrue(self.source.is_external)

    def test_post_invalid_returns_422(self):
        """POST avec label vide retourne 422."""
        response = self.client.post(
            reverse("workflow:source-edit", kwargs={"pk": self.source.pk}),
            {"code": "EDIT_SRC", "label": ""},
        )
        self.assertEqual(response.status_code, 422)

    def test_post_creates_audit_log(self):
        """La modification est tracée dans l'AuditLog."""
        self.client.post(
            reverse("workflow:source-edit", kwargs={"pk": self.source.pk}),
            {"code": "EDIT_SRC", "label": "Tracée", "is_external": False},
        )
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="RecommendationSource",
                object_id=self.source.pk,
                action=AuditLog.Action.UPDATE,
            ).exists()
        )

    def test_edit_404_for_unknown_pk(self):
        """Un pk inexistant retourne 404."""
        import uuid
        response = self.client.get(
            reverse("workflow:source-edit", kwargs={"pk": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)


class RecommendationSourceToggleTest(TestCase):
    """Tests du toggle is_active (HTMX POST)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_toggle",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        self.source, _ = RecommendationSource.objects.get_or_create(
            code="TOGGLE_SRC",
            defaults={"label": "Source Toggle", "is_external": False, "is_active": True},
        )
        # S'assurer que la source est active au départ
        self.source.is_active = True
        self.source.save(update_fields=["is_active"])

    def test_toggle_deactivates_active_source(self):
        """POST désactive une source active."""
        response = self.client.post(
            reverse("workflow:source-toggle", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.source.refresh_from_db()
        self.assertFalse(self.source.is_active)

    def test_toggle_activates_inactive_source(self):
        """POST active une source inactive."""
        self.source.is_active = False
        self.source.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("workflow:source-toggle", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.source.refresh_from_db()
        self.assertTrue(self.source.is_active)

    def test_toggle_creates_audit_log(self):
        """Le toggle est tracé dans l'AuditLog."""
        self.client.post(
            reverse("workflow:source-toggle", kwargs={"pk": self.source.pk})
        )
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="RecommendationSource",
                object_id=self.source.pk,
            ).exists()
        )

    def test_toggle_404_for_unknown_pk(self):
        """Un pk inexistant retourne 404."""
        import uuid
        response = self.client.post(
            reverse("workflow:source-toggle", kwargs={"pk": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)
