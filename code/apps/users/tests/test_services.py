"""
Users App — Tests Services (Convention HackSoft)

Vérifie la couche service d'habilitation : assign_role et toggle_audit_admin.
Chaque test valide un comportement métier unique (ADR-10, FR3, FR36).
"""
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.users.models import Department, User
from apps.users.services import assign_role, toggle_audit_admin


class AssignRoleServiceTest(TestCase):
    """Tests du service assign_role (FR3, ADR-10)."""

    def setUp(self):
        self.dept = Department.objects.create(
            name="Direction Financière", code="DFIN",
            type=Department.Type.DIRECTION,
        )
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.shell_user = User.objects.create_user(
            username="coquille", password="testpass123",
        )

    def test_assign_role_success(self):
        """Un audit_admin peut attribuer un rôle à une coquille vide."""
        result = assign_role(
            target_user=self.shell_user,
            role=User.Role.DM,
            department=self.dept,
            performed_by=self.audit_admin,
        )
        self.shell_user.refresh_from_db()
        self.assertEqual(result.role, User.Role.DM)
        self.assertEqual(self.shell_user.department, self.dept)

    def test_assign_role_creates_audit_log(self):
        """L'attribution est tracée dans l'Audit Log (NFR-SEC-05)."""
        assign_role(
            target_user=self.shell_user,
            role=User.Role.ETP,
            department=self.dept,
            performed_by=self.audit_admin,
        )
        log = AuditLog.objects.filter(
            content_type="User", object_id=self.shell_user.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, AuditLog.Action.UPDATE)
        self.assertEqual(log.user, self.audit_admin)
        self.assertIn("role", log.changes)

    def test_assign_role_permission_denied_for_non_admin(self):
        """Un utilisateur sans can_manage_users est rejeté."""
        dm_user = User.objects.create_user(
            username="dm_lambda", password="testpass123",
            role=User.Role.DM,
        )
        with self.assertRaises(PermissionDenied):
            assign_role(
                target_user=self.shell_user,
                role=User.Role.ETP,
                department=self.dept,
                performed_by=dm_user,
            )

    def test_assign_role_invalid_role_raises_value_error(self):
        """Un rôle invalide lève ValueError."""
        with self.assertRaises(ValueError):
            assign_role(
                target_user=self.shell_user,
                role="INEXISTANT",
                department=self.dept,
                performed_by=self.audit_admin,
            )

    def test_assign_role_superuser_can_bootstrap(self):
        """Un superuser peut attribuer un rôle (bootstrapping)."""
        superuser = User.objects.create_superuser(
            username="super", password="testpass123",
        )
        assign_role(
            target_user=self.shell_user,
            role=User.Role.AUDIT,
            department=None,
            performed_by=superuser,
        )
        self.shell_user.refresh_from_db()
        self.assertEqual(self.shell_user.role, User.Role.AUDIT)


class ToggleAuditAdminServiceTest(TestCase):
    """Tests du service toggle_audit_admin (FR36, ADR-10)."""

    def setUp(self):
        self.audit_admin = User.objects.create_user(
            username="dir_audit", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.auditor = User.objects.create_user(
            username="auditeur_std", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=False,
        )

    def test_toggle_grant(self):
        """Accorder la délégation is_audit_admin (FR36)."""
        toggle_audit_admin(
            target_user=self.auditor,
            grant=True,
            performed_by=self.audit_admin,
        )
        self.auditor.refresh_from_db()
        self.assertTrue(self.auditor.is_audit_admin)

    def test_toggle_revoke(self):
        """Révoquer la délégation is_audit_admin."""
        self.auditor.is_audit_admin = True
        self.auditor.save(update_fields=["is_audit_admin"])
        toggle_audit_admin(
            target_user=self.auditor,
            grant=False,
            performed_by=self.audit_admin,
        )
        self.auditor.refresh_from_db()
        self.assertFalse(self.auditor.is_audit_admin)

    def test_toggle_creates_audit_log(self):
        """La délégation est tracée dans l'Audit Log."""
        toggle_audit_admin(
            target_user=self.auditor,
            grant=True,
            performed_by=self.audit_admin,
        )
        log = AuditLog.objects.filter(
            content_type="User", object_id=self.auditor.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("is_audit_admin", log.changes)

    def test_toggle_non_audit_role_raises_value_error(self):
        """Le flag ne peut être attribué qu'aux Auditeurs Internes."""
        dm_user = User.objects.create_user(
            username="dm_test", password="testpass123",
            role=User.Role.DM,
        )
        with self.assertRaises(ValueError):
            toggle_audit_admin(
                target_user=dm_user,
                grant=True,
                performed_by=self.audit_admin,
            )
