"""
Users App — Tests Vues Admin Types d'Unités Organisationnelles (Story 3.7.b Phase B)

Vérifie les vues CRUD des types d'unités organisationnelles :
    - Contrôle d'accès (AuditAdminRequiredMixin)
    - List, Create, Edit, Toggle (HTMX : 204 + HX-Refresh)
    - Champ code immuable à l'édition
    - Traçabilité AuditLog (NFR-SEC-05)

Note : OrgUnitType est seedé par la migration 0006 —
utiliser get_or_create pour les codes existants (DG, DIRECTION…).
"""
import uuid

from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.users.models import OrgUnitType, User


class OrgUnitTypeAccessTest(TestCase):
    """Contrôle d'accès aux vues OrgUnitType (AuditAdminRequiredMixin)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_out",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_out",
            password="testpass123",
            role=User.Role.DM,
        )
        self.org_type, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION",
            defaults={"name": "Direction", "level": 1},
        )

    def test_list_accessible_by_audit_admin(self):
        """Un Audit Admin peut accéder à la liste des types."""
        self.client.force_login(self.audit_admin)
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertEqual(response.status_code, 200)

    def test_list_forbidden_for_dm(self):
        """Un DM reçoit 403 sur la liste des types."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertEqual(response.status_code, 403)

    def test_create_get_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le GET de création."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("auth:org-unit-type-create"))
        self.assertEqual(response.status_code, 403)

    def test_edit_get_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le GET d'édition."""
        self.client.force_login(self.dm_user)
        response = self.client.get(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_toggle_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le toggle."""
        self.client.force_login(self.dm_user)
        response = self.client.post(
            reverse("auth:org-unit-type-toggle", kwargs={"pk": self.org_type.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_list_accessible_by_superuser(self):
        """Un superuser peut accéder à la liste (bootstrapping)."""
        superuser = User.objects.create_superuser(
            username="super_out", password="testpass123",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertEqual(response.status_code, 200)

    def test_list_forbidden_for_admin_it(self):
        """Un Admin IT (role=ADMIN) reçoit 403 — vues réservées aux Audit Admins."""
        admin_it = User.objects.create_user(
            username="admin_it_out",
            password="testpass123",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.force_login(admin_it)
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertEqual(response.status_code, 403)


class OrgUnitTypeListTest(TestCase):
    """Tests de la vue liste des types d'unités."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_list_out",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        # Seeded by migration 0006 — use get_or_create
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )

    def test_list_renders_correct_template(self):
        """La liste utilise le bon template."""
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/org_unit_types/list.html")

    def test_list_context_contains_org_unit_types(self):
        """Le contexte contient la clé 'org_unit_types'."""
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertIn("org_unit_types", response.context)
        self.assertIn(self.type_direction, response.context["org_unit_types"])

    def test_list_shows_inactive_types_too(self):
        """La liste affiche aussi les types inactifs (get_all_org_unit_types)."""
        inactive_type = OrgUnitType.objects.create(
            name="Type Inactif Test", code="INACT_T", level=9, is_active=False,
        )
        response = self.client.get(reverse("auth:org-unit-type-list"))
        self.assertIn(inactive_type, response.context["org_unit_types"])


class OrgUnitTypeCreateTest(TestCase):
    """Tests de la vue de création (HTMX)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_create_out",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)

    def test_get_renders_form_partial(self):
        """GET retourne le formulaire partiel."""
        response = self.client.get(reverse("auth:org-unit-type-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "admin_it/org_unit_types/_form_modal.html"
        )

    def test_post_valid_returns_204_with_hx_refresh(self):
        """POST valide retourne 204 + HX-Refresh, l'objet est créé."""
        response = self.client.post(reverse("auth:org-unit-type-create"), {
            "code": "NEW_TYPE",
            "name": "Nouveau Type",
            "level": 7,
        })
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.assertTrue(OrgUnitType.objects.filter(code="NEW_TYPE").exists())

    def test_post_invalid_missing_required_fields(self):
        """POST avec champs manquants re-rend le formulaire."""
        response = self.client.post(reverse("auth:org-unit-type-create"), {
            "code": "",
            "name": "",
        })
        # Pas 204, pas de redirection — formulaire re-rendu
        self.assertNotEqual(response.status_code, 204)

    def test_post_creates_audit_log(self):
        """La création est tracée dans l'AuditLog (NFR-SEC-05)."""
        self.client.post(reverse("auth:org-unit-type-create"), {
            "code": "LOG_TYPE",
            "name": "Type Tracé",
            "level": 8,
        })
        created = OrgUnitType.objects.get(code="LOG_TYPE")
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="OrgUnitType",
                object_id=created.pk,
                action=AuditLog.Action.CREATE,
            ).exists()
        )

    def test_post_duplicate_code_fails(self):
        """Un code déjà existant ne crée pas de doublon (contrainte unicité)."""
        OrgUnitType.objects.get_or_create(
            code="DUP_TYPE", defaults={"name": "Existant", "level": 0},
        )
        initial_count = OrgUnitType.objects.filter(code="DUP_TYPE").count()
        self.client.post(reverse("auth:org-unit-type-create"), {
            "code": "DUP_TYPE",
            "name": "Doublon",
            "level": 0,
        })
        self.assertEqual(
            OrgUnitType.objects.filter(code="DUP_TYPE").count(), initial_count
        )


class OrgUnitTypeEditTest(TestCase):
    """Tests de la vue d'édition (HTMX)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_edit_out",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        # Type dédié aux tests d'édition (code non-seedé)
        self.org_type = OrgUnitType.objects.create(
            code="EDIT_TYPE", name="À Éditer", level=5,
        )

    def test_get_renders_form_partial(self):
        """GET retourne le formulaire prérempli."""
        response = self.client.get(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "admin_it/org_unit_types/_form_modal.html"
        )

    def test_post_valid_updates_name_and_level(self):
        """POST valide met à jour le nom et le niveau."""
        response = self.client.post(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk}),
            {"code": "EDIT_TYPE", "name": "Nom Modifié", "level": 3},
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.org_type.refresh_from_db()
        self.assertEqual(self.org_type.name, "Nom Modifié")
        self.assertEqual(self.org_type.level, 3)

    def test_post_invalid_returns_non_204(self):
        """POST avec nom vide ne retourne pas 204."""
        response = self.client.post(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk}),
            {"code": "EDIT_TYPE", "name": "", "level": 5},
        )
        self.assertNotEqual(response.status_code, 204)
        # Le nom n'a pas changé
        self.org_type.refresh_from_db()
        self.assertEqual(self.org_type.name, "À Éditer")

    def test_post_creates_audit_log(self):
        """La modification est tracée dans l'AuditLog."""
        self.client.post(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk}),
            {"code": "EDIT_TYPE", "name": "Tracé", "level": 2},
        )
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="OrgUnitType",
                object_id=self.org_type.pk,
                action=AuditLog.Action.UPDATE,
            ).exists()
        )

    def test_edit_404_for_unknown_pk(self):
        """Un pk inexistant retourne 404."""
        response = self.client.get(
            reverse("auth:org-unit-type-edit", kwargs={"pk": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)

    def test_code_field_is_disabled_in_edit_mode(self):
        """Le champ code est disabled en édition (immuable — ADR similaire à source)."""
        response = self.client.get(
            reverse("auth:org-unit-type-edit", kwargs={"pk": self.org_type.pk})
        )
        form = response.context.get("form")
        self.assertIsNotNone(form, "Le contexte doit contenir un 'form'")
        code_field = form.fields.get("code")
        self.assertIsNotNone(code_field)
        self.assertTrue(
            code_field.disabled,
            "Le champ 'code' doit être disabled en mode édition",
        )


class OrgUnitTypeToggleTest(TestCase):
    """Tests du toggle is_active (HTMX POST)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="audit_admin_toggle_out",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.client.force_login(self.audit_admin)
        self.org_type = OrgUnitType.objects.create(
            code="TOGGLE_TYPE", name="Type Toggle", level=6, is_active=True,
        )

    def test_toggle_deactivates_active_type(self):
        """POST désactive un type actif."""
        response = self.client.post(
            reverse("auth:org-unit-type-toggle", kwargs={"pk": self.org_type.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Refresh", response)
        self.org_type.refresh_from_db()
        self.assertFalse(self.org_type.is_active)

    def test_toggle_activates_inactive_type(self):
        """POST active un type inactif."""
        self.org_type.is_active = False
        self.org_type.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("auth:org-unit-type-toggle", kwargs={"pk": self.org_type.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.org_type.refresh_from_db()
        self.assertTrue(self.org_type.is_active)

    def test_toggle_creates_audit_log(self):
        """Le toggle est tracé dans l'AuditLog."""
        self.client.post(
            reverse("auth:org-unit-type-toggle", kwargs={"pk": self.org_type.pk})
        )
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="OrgUnitType",
                object_id=self.org_type.pk,
            ).exists()
        )

    def test_toggle_404_for_unknown_pk(self):
        """Un pk inexistant retourne 404."""
        response = self.client.post(
            reverse("auth:org-unit-type-toggle", kwargs={"pk": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)
