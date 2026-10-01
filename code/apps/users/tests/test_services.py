"""
Users App — Tests Services (Convention HackSoft)

Vérifie la couche service d'habilitation : assign_role, toggle_audit_admin,
et la délégation horodatée du flag is_audit_admin (FR36).

Note Story 6.2.0 : assign_role utilise désormais user_is_provisioning_approver
(appartenance au groupe « Administrateurs Sentinel ») comme garde d'autorisation.
Les tests sont adaptés en conséquence.
"""
from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.users.models import AuditAdminDelegation, Department, OrgUnitType, User
from apps.users.services import (
    assign_role,
    delegate_audit_admin_timed,
    revoke_audit_admin_delegation,
    run_nightly_delegation_expiry_check,
    toggle_audit_admin,
)


def _get_or_create_approvers_group():
    group, _ = Group.objects.get_or_create(name="Administrateurs Sentinel")
    return group


class AssignRoleServiceTest(TestCase):
    """
    Tests du service assign_role (FR3, ADR-10 / Story 6.2.0).

    Depuis Story 6.2.0 : le garde d'autorisation est user_is_provisioning_approver
    (groupe « Administrateurs Sentinel »), pas can_manage_users.
    """

    def setUp(self):
        self.group = _get_or_create_approvers_group()
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        self.dept = Department.objects.create(
            name="Direction Financière", code="DFIN",
            type=self.type_direction,
        )
        # Checker = membre du groupe (peut effectuer assign_role)
        self.checker = User.objects.create_user(
            username="checker_it", password="testpass123",
            role=User.Role.ADMIN,
        )
        self.checker.groups.add(self.group)
        self.shell_user = User.objects.create_user(
            username="coquille", password="testpass123",
        )

    def test_assign_role_success(self):
        """Un membre du groupe peut attribuer un rôle (Story 6.2.0)."""
        result = assign_role(
            target_user=self.shell_user,
            role=User.Role.DM,
            department=self.dept,
            performed_by=self.checker,
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
            performed_by=self.checker,
        )
        log = AuditLog.objects.filter(
            content_type="User", object_id=self.shell_user.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, AuditLog.Action.UPDATE)
        self.assertEqual(log.user, self.checker)
        self.assertIn("role", log.changes)

    def test_assign_role_permission_denied_for_non_group_member(self):
        """Un utilisateur hors du groupe reçoit PermissionDenied (Story 6.2.0)."""
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

    def test_assign_role_audit_admin_without_group_is_denied(self):
        """Un Audit Admin NON membre du groupe reçoit PermissionDenied (Story 6.2.0)."""
        audit_admin_no_group = User.objects.create_user(
            username="audit_no_group", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        with self.assertRaises(PermissionDenied):
            assign_role(
                target_user=self.shell_user,
                role=User.Role.ETP,
                department=self.dept,
                performed_by=audit_admin_no_group,
            )

    def test_assign_role_invalid_role_raises_value_error(self):
        """Un rôle invalide lève ValueError."""
        with self.assertRaises(ValueError):
            assign_role(
                target_user=self.shell_user,
                role="INEXISTANT",
                department=self.dept,
                performed_by=self.checker,
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


class TimedDelegationTest(TestCase):
    """Tests de la délégation horodatée du flag is_audit_admin (FR36)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="dir_audit_timed", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.auditor = User.objects.create_user(
            username="auditeur_delegue", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=False,
        )
        self.tomorrow = date.today() + timedelta(days=1)

    # ── Création de délégation ────────────────────────────────────────────────

    def test_delegate_creates_delegation_record(self):
        """La délégation est persistée en base."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        self.assertEqual(AuditAdminDelegation.objects.filter(delegated_to=self.auditor).count(), 1)

    def test_delegate_logs_privilege_grant(self):
        """Un AuditLog PRIVILEGE_GRANT est créé."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        log = AuditLog.objects.filter(
            action=AuditLog.Action.PRIVILEGE_GRANT,
            object_id=self.auditor.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)

    def test_delegate_notifies_delegatee(self):
        """Le bénéficiaire reçoit une notification PRIVILEGE_ALERT."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        notif = Notification.objects.filter(
            recipient=self.auditor,
            notification_type=Notification.Type.PRIVILEGE_ALERT,
        ).first()
        self.assertIsNotNone(notif)

    def test_delegate_grants_can_manage_users(self):
        """Après délégation, can_manage_users retourne True pour le bénéficiaire."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        fresh = User.objects.get(pk=self.auditor.pk)
        self.assertTrue(fresh.can_manage_users)

    # ── Guards de validation ──────────────────────────────────────────────────

    def test_delegate_self_raises(self):
        """Un admin ne peut pas se déléguer le flag à lui-même."""
        with self.assertRaises(ValueError):
            delegate_audit_admin_timed(
                delegated_to=self.admin,
                valid_until=self.tomorrow,
                performed_by=self.admin,
            )

    def test_delegate_non_audit_raises(self):
        """La délégation est refusée pour un utilisateur non-AUDIT."""
        dm = User.objects.create_user(
            username="dm_delegate", password="testpass123",
            role=User.Role.DM,
        )
        with self.assertRaises(ValueError):
            delegate_audit_admin_timed(
                delegated_to=dm,
                valid_until=self.tomorrow,
                performed_by=self.admin,
            )

    def test_delegate_past_date_raises(self):
        """Une date de fin dans le passé est refusée."""
        yesterday = date.today() - timedelta(days=1)
        with self.assertRaises(ValueError):
            delegate_audit_admin_timed(
                delegated_to=self.auditor,
                valid_until=yesterday,
                performed_by=self.admin,
            )

    def test_delegate_duplicate_active_raises(self):
        """Créer une seconde délégation active pour le même auditeur est refusé."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        with self.assertRaises(ValueError):
            delegate_audit_admin_timed(
                delegated_to=self.auditor,
                valid_until=self.tomorrow + timedelta(days=5),
                performed_by=self.admin,
            )

    def test_delegate_par_un_delegue_est_refuse(self):
        """Un admin délégué (non permanent) ne peut pas créer de sous-délégation :
        il ne pourrait pas la révoquer lui-même (revoke exige is_audit_admin),
        et rien ne bornerait sa durée à sa propre échéance."""
        delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        fresh_auditor = User.objects.get(pk=self.auditor.pk)
        self.assertTrue(fresh_auditor.can_manage_users)
        self.assertFalse(fresh_auditor.is_audit_admin)

        other_auditor = User.objects.create_user(
            username="autre_auditeur", password="testpass123",
            role=User.Role.AUDIT, is_audit_admin=False,
        )
        with self.assertRaises(PermissionDenied):
            delegate_audit_admin_timed(
                delegated_to=other_auditor,
                valid_until=self.tomorrow,
                performed_by=fresh_auditor,
            )

    # ── Révocation manuelle ───────────────────────────────────────────────────

    def test_revoke_logs_privilege_revoke(self):
        """La révocation crée un AuditLog PRIVILEGE_REVOKE."""
        delegation = delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        revoke_audit_admin_delegation(delegation=delegation, revoked_by=self.admin)
        log = AuditLog.objects.filter(
            action=AuditLog.Action.PRIVILEGE_REVOKE,
            object_id=self.auditor.pk,
            changes__revoked_early=True,
        ).first()
        self.assertIsNotNone(log)

    def test_revoke_removes_can_manage_users(self):
        """Après révocation, can_manage_users retourne False."""
        delegation = delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        revoke_audit_admin_delegation(delegation=delegation, revoked_by=self.admin)
        fresh = User.objects.get(pk=self.auditor.pk)
        self.assertFalse(fresh.can_manage_users)

    def test_revoke_already_revoked_raises(self):
        """Révoquer une délégation déjà révoquée lève ValueError."""
        delegation = delegate_audit_admin_timed(
            delegated_to=self.auditor,
            valid_until=self.tomorrow,
            performed_by=self.admin,
        )
        revoke_audit_admin_delegation(delegation=delegation, revoked_by=self.admin)
        with self.assertRaises(ValueError):
            revoke_audit_admin_delegation(delegation=delegation, revoked_by=self.admin)

    # ── Expiration automatique ────────────────────────────────────────────────

    def test_expired_delegation_no_can_manage_users(self):
        """Une délégation expirée (valid_until < today) ne donne plus can_manage_users."""
        yesterday = date.today() - timedelta(days=1)
        AuditAdminDelegation.objects.create(
            delegated_to=self.auditor,
            delegated_by=self.admin,
            valid_until=yesterday,
        )
        fresh = User.objects.get(pk=self.auditor.pk)
        self.assertFalse(fresh.can_manage_users)

    def test_nightly_expiry_logs_and_notifies(self):
        """Le CRON trace l'expiration et notifie le bénéficiaire."""
        yesterday = date.today() - timedelta(days=1)
        AuditAdminDelegation.objects.create(
            delegated_to=self.auditor,
            delegated_by=self.admin,
            valid_until=yesterday,
        )
        result = run_nightly_delegation_expiry_check()
        self.assertEqual(result["expired"], 1)
        log = AuditLog.objects.filter(
            action=AuditLog.Action.PRIVILEGE_REVOKE,
            object_id=self.auditor.pk,
            changes__expired=True,
        ).first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.user)
        notif = Notification.objects.filter(
            recipient=self.auditor,
            notification_type=Notification.Type.PRIVILEGE_ALERT,
        ).first()
        self.assertIsNotNone(notif)
