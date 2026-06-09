"""
Users App — Tests Habilitation Views (Story 1.5 + 1.7)

Vérifie les vues d'habilitation : accès, filtrage, édition, toggle admin.

Note : force_login() est utilisé au lieu de login() car django-axes
exige un objet request dans authenticate() (incompatible avec les tests).
"""
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.users.models import Department, OrgUnitType, User


class HabilitationAccessTest(TestCase):
    """Tests de contrôle d'accès aux vues d'habilitation (ADR-10)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_lambda", password="testpass123",
            role=User.Role.DM,
        )
        self.shell_user = User.objects.create_user(
            username="coquille", password="testpass123",
        )

    def test_list_accessible_by_audit_admin(self):
        """Un audit_admin peut accéder à la liste d'habilitation."""
        self.client.force_login(self.audit_admin)
        response = self.client.get(reverse("workflow:habilitation-list"))
        self.assertEqual(response.status_code, 200)

    def test_list_forbidden_for_dm(self):
        """Un DM reçoit 403 sur la liste d'habilitation."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("workflow:habilitation-list"))
        self.assertEqual(response.status_code, 403)

    def test_list_accessible_by_superuser(self):
        """Un superuser peut accéder pour le bootstrapping."""
        superuser = User.objects.create_superuser(
            username="super", password="testpass123",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("workflow:habilitation-list"))
        self.assertEqual(response.status_code, 200)

    def test_edit_forbidden_for_dm(self):
        """Un DM reçoit 403 sur le formulaire d'édition."""
        self.client.force_login(self.dm_user)
        url = reverse("workflow:habilitation-edit", args=[self.shell_user.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class HabilitationListFilterTest(TestCase):
    """Tests des filtres de la liste d'habilitation."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.shell_user = User.objects.create_user(
            username="coquille", password="testpass123",
        )
        self.dm_user = User.objects.create_user(
            username="dm_actif", password="testpass123",
            role=User.Role.DM,
        )
        self.client.force_login(self.audit_admin)

    def test_filter_shell_only_shows_shells(self):
        """Le filtre 'shell' ne montre que les coquilles vides."""
        response = self.client.get(
            reverse("workflow:habilitation-list") + "?filtre=shell"
        )
        users = response.context["users"]
        self.assertIn(self.shell_user, users)
        self.assertNotIn(self.dm_user, users)

    def test_filter_actif_excludes_shells(self):
        """Le filtre 'actif' exclut les coquilles vides."""
        response = self.client.get(
            reverse("workflow:habilitation-list") + "?filtre=actif"
        )
        users = response.context["users"]
        self.assertNotIn(self.shell_user, users)
        self.assertIn(self.dm_user, users)


class HabilitationEditTest(TestCase):
    """Tests du formulaire d'édition de rôle (FR3)."""

    def setUp(self):
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        self.dept = Department.objects.create(
            name="Direction RH", code="DRH",
            type=self.type_direction,
        )
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.shell_user = User.objects.create_user(
            username="coquille", password="testpass123",
        )
        self.client.force_login(self.audit_admin)

    def test_edit_assigns_role(self):
        """POST attribue le rôle et le département."""
        url = reverse("workflow:habilitation-edit", args=[self.shell_user.pk])
        self.client.post(url, {
            "role": User.Role.DM,
            "department": str(self.dept.pk),
        })
        self.shell_user.refresh_from_db()
        self.assertEqual(self.shell_user.role, User.Role.DM)
        self.assertEqual(self.shell_user.department, self.dept)

    def test_edit_redirects_after_save(self):
        """Après sauvegarde, redirection vers la liste."""
        url = reverse("workflow:habilitation-edit", args=[self.shell_user.pk])
        response = self.client.post(url, {
            "role": User.Role.ETP,
            "department": str(self.dept.pk),
        })
        self.assertRedirects(response, reverse("workflow:habilitation-list"))

    def test_edit_creates_audit_log(self):
        """L'édition crée une entrée dans l'Audit Log."""
        url = reverse("workflow:habilitation-edit", args=[self.shell_user.pk])
        self.client.post(url, {
            "role": User.Role.DM,
            "department": str(self.dept.pk),
        })
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="User",
                object_id=self.shell_user.pk,
            ).exists()
        )


class HabilitationToggleAdminTest(TestCase):
    """Tests du toggle is_audit_admin inline (Story 1.7 / FR36)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.auditor = User.objects.create_user(
            username="auditeur_std", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=False,
        )
        self.client.force_login(self.audit_admin)

    def test_toggle_grants_admin(self):
        """POST active le flag is_audit_admin."""
        url = reverse("workflow:habilitation-toggle-admin", args=[self.auditor.pk])
        self.client.post(url)
        self.auditor.refresh_from_db()
        self.assertTrue(self.auditor.is_audit_admin)

    def test_toggle_revokes_admin(self):
        """POST désactive le flag is_audit_admin."""
        self.auditor.is_audit_admin = True
        self.auditor.save(update_fields=["is_audit_admin"])
        url = reverse("workflow:habilitation-toggle-admin", args=[self.auditor.pk])
        self.client.post(url)
        self.auditor.refresh_from_db()
        self.assertFalse(self.auditor.is_audit_admin)

    def test_toggle_non_audit_shows_error(self):
        """Toggle sur un non-AUDIT redirige avec un message d'erreur."""
        dm = User.objects.create_user(
            username="dm_test", password="testpass123",
            role=User.Role.DM,
        )
        url = reverse("workflow:habilitation-toggle-admin", args=[dm.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("workflow:habilitation-list"))
        dm.refresh_from_db()
        self.assertFalse(dm.is_audit_admin)

