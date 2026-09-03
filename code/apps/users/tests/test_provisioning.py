"""
Users App — Tests Provisioning Maker/Checker (Story 6.2.0)

Vérifie le flux complet : création de demande, approbation, rejet, annulation,
contrôles d'accès, et cas EXT.

Note : force_login() est utilisé car django-axes est incompatible avec login()
dans les tests.
"""
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.users.models import Department, ExternalMission, OrgUnitType, User, UserProvisioningRequest
from apps.users import services


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_org_type(code="DG", name="Direction Générale", level=1):
    # get_or_create car la migration 0006 seed déjà "DG", "DIRECTION", etc.
    org_type, _ = OrgUnitType.objects.get_or_create(
        code=code,
        defaults={"name": name, "level": level},
    )
    return org_type


def _make_dept(type_obj, code="DAF", name="Direction Admin & Financière"):
    return Department.objects.create(code=code, name=name, type=type_obj)


def _make_approvers_group():
    group, _ = Group.objects.get_or_create(name="Administrateurs Sentinel")
    return group


def _make_admin(username="admin_it", **kwargs):
    # Extraire email si fourni, sinon utiliser le défaut basé sur le username
    email = kwargs.pop("email", f"{username}@bicec.cm")
    return User.objects.create_user(
        username=username,
        password="Admin#12345",
        email=email,
        role=User.Role.ADMIN,
        **kwargs,
    )


def _make_checker(username="checker", group=None, **kwargs):
    user = User.objects.create_user(
        username=username,
        password="Checker#12345",
        email=f"{username}@bicec.cm",
        role=User.Role.AUDIT,
        **kwargs,
    )
    if group:
        user.groups.add(group)
    return user


def _base_data(role=User.Role.DM, dept=None):
    return {
        "requested_username": "jean.dupont",
        "requested_first_name": "Jean",
        "requested_last_name": "Dupont",
        "requested_email": "jean.dupont@bicec.cm",
        "password": "Secure#1234",
        "requested_role": role,
        "requested_department": dept,
        "mission_organization": "",
        "mission_scope": "",
        "mission_start_date": None,
        "mission_end_date": None,
    }


# ─── Service tests ─────────────────────────────────────────────────────────────


class CreateProvisioningRequestServiceTest(TestCase):
    """Tests du service create_provisioning_request."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.org_type = _make_org_type()
        self.dept = _make_dept(self.org_type)
        self.maker = _make_admin()
        self.checker = _make_checker(group=self.group)

    def test_create_pending_no_user(self):
        """Une requête PENDING est créée — aucun User réel n'existe."""
        data = _base_data(dept=self.dept)
        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        self.assertEqual(req.status, UserProvisioningRequest.Status.PENDING)
        # L'utilisateur n'existe pas encore
        self.assertFalse(User.objects.filter(username="jean.dupont").exists())

    def test_password_stored_hashed(self):
        """Le mot de passe en clair est haché avant stockage."""
        data = _base_data(dept=self.dept)
        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        # La valeur stockée ne doit pas être le clair
        self.assertNotEqual(req.hashed_initial_password, "Secure#1234")
        # Mais le check doit réussir
        self.assertTrue(check_password("Secure#1234", req.hashed_initial_password))

    def test_auditlog_created(self):
        """Un AuditLog CREATE est émis pour la requête."""
        data = _base_data(dept=self.dept)
        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        log = AuditLog.objects.filter(
            content_type="UserProvisioningRequest",
            object_id=req.pk,
            action=AuditLog.Action.CREATE,
        )
        self.assertTrue(log.exists())

    def test_notifies_group_members(self):
        """Chaque membre du groupe reçoit une notification PROVISIONING_REQUESTED."""
        checker2 = _make_checker(username="checker2", group=self.group)
        data = _base_data(dept=self.dept)
        services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        # Le checker et checker2 doivent être notifiés
        for member in [self.checker, checker2]:
            notif = Notification.objects.filter(
                recipient=member,
                notification_type=Notification.Type.PROVISIONING_REQUESTED,
            )
            self.assertTrue(notif.exists(), f"{member.username} non notifié")


class ApproveProvisioningRequestServiceTest(TestCase):
    """Tests du service approve_provisioning_request."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.org_type = _make_org_type()
        self.dept = _make_dept(self.org_type)
        self.maker = _make_admin()
        self.checker = _make_checker(group=self.group)

    def _pending_req(self, **overrides):
        data = _base_data(dept=self.dept)
        data.update(overrides)
        return services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )

    def test_approve_creates_user_atomically(self):
        """L'approbation crée le User et passe le statut à APPROVED atomiquement."""
        req = self._pending_req()
        user = services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )
        self.assertIsNotNone(user.pk)
        req.refresh_from_db()
        self.assertEqual(req.status, UserProvisioningRequest.Status.APPROVED)
        self.assertEqual(req.reviewed_by, self.checker)

    def test_approve_password_is_usable(self):
        """Le mot de passe du User créé est fonctionnel (pas de double-hachage)."""
        req = self._pending_req()
        user = services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )
        user.refresh_from_db()
        self.assertTrue(
            check_password("Secure#1234", user.password),
            "Le mot de passe initial n'est pas valide — double-hachage probable."
        )

    def test_approve_emits_two_auditlogs(self):
        """Deux AuditLog sont émis : un pour le User et un pour la requête."""
        req = self._pending_req()
        services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )
        user_log = AuditLog.objects.filter(content_type="User", action=AuditLog.Action.CREATE)
        req_log = AuditLog.objects.filter(
            content_type="UserProvisioningRequest",
            action=AuditLog.Action.UPDATE,
            object_id=req.pk,
        )
        self.assertTrue(user_log.exists(), "AuditLog User CREATE manquant")
        self.assertTrue(req_log.exists(), "AuditLog UserProvisioningRequest UPDATE manquant")

    def test_approve_notifies_maker(self):
        """Le maker est notifié PROVISIONING_APPROVED."""
        req = self._pending_req()
        services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )
        notif = Notification.objects.filter(
            recipient=self.maker,
            notification_type=Notification.Type.PROVISIONING_APPROVED,
        )
        self.assertTrue(notif.exists())

    def test_approve_duplicate_username_fails(self):
        """Si le username existe déjà au moment de l'approbation, une ValidationError est levée."""
        from django.core.exceptions import ValidationError
        req = self._pending_req()
        # On crée un compte avec le même username entre-temps
        User.objects.create_user(username="jean.dupont", password="test")
        with self.assertRaises(ValidationError):
            services.approve_provisioning_request(
                request=req, checker=self.checker, ip_address="127.0.0.1"
            )
        # Aucun User créé pendant l'approbation (transaction rollback)
        self.assertEqual(User.objects.filter(username="jean.dupont").count(), 1)


class RejectProvisioningRequestServiceTest(TestCase):
    """Tests du service reject_provisioning_request."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.org_type = _make_org_type()
        self.dept = _make_dept(self.org_type)
        self.maker = _make_admin()
        self.checker = _make_checker(group=self.group)

    def _pending_req(self):
        data = _base_data(dept=self.dept)
        return services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )

    def test_reject_requires_reason(self):
        """Le rejet sans motif lève une ValidationError."""
        from django.core.exceptions import ValidationError
        req = self._pending_req()
        with self.assertRaises(ValidationError):
            services.reject_provisioning_request(
                request=req, checker=self.checker, reason="", ip_address="127.0.0.1"
            )

    def test_reject_with_reason_sets_status(self):
        """Un rejet avec motif passe la demande à REJECTED et aucun User n'est créé."""
        req = self._pending_req()
        services.reject_provisioning_request(
            request=req, checker=self.checker,
            reason="Demande incomplète — département manquant.",
            ip_address="127.0.0.1",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, UserProvisioningRequest.Status.REJECTED)
        self.assertFalse(User.objects.filter(username="jean.dupont").exists())

    def test_reject_notifies_maker(self):
        """Le maker reçoit une notification PROVISIONING_REJECTED."""
        req = self._pending_req()
        services.reject_provisioning_request(
            request=req, checker=self.checker,
            reason="Identifiant déjà utilisé par un autre compte.",
            ip_address="127.0.0.1",
        )
        notif = Notification.objects.filter(
            recipient=self.maker,
            notification_type=Notification.Type.PROVISIONING_REJECTED,
        )
        self.assertTrue(notif.exists())


class CancelProvisioningRequestServiceTest(TestCase):
    """Tests du service cancel_provisioning_request."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.org_type = _make_org_type()
        self.dept = _make_dept(self.org_type)
        self.maker = _make_admin()
        self.other_admin = _make_admin(username="other_admin", email="other@bicec.cm")

    def _pending_req(self):
        data = _base_data(dept=self.dept)
        return services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )

    def test_cancel_only_by_maker(self):
        """Seul le maker peut annuler sa propre demande."""
        from django.core.exceptions import PermissionDenied
        req = self._pending_req()
        with self.assertRaises(PermissionDenied):
            services.cancel_provisioning_request(
                request=req, maker=self.other_admin, ip_address="127.0.0.1"
            )

    def test_cancel_by_maker_sets_cancelled(self):
        """Le maker peut annuler sa propre demande PENDING."""
        req = self._pending_req()
        services.cancel_provisioning_request(
            request=req, maker=self.maker, ip_address="127.0.0.1"
        )
        req.refresh_from_db()
        self.assertEqual(req.status, UserProvisioningRequest.Status.CANCELLED)

    def test_cancel_non_pending_fails(self):
        """Annuler une demande non-PENDING lève ValueError."""
        req = self._pending_req()
        req.status = UserProvisioningRequest.Status.APPROVED
        req.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            services.cancel_provisioning_request(
                request=req, maker=self.maker, ip_address="127.0.0.1"
            )


class EXTProvisioningServiceTest(TestCase):
    """Tests du provisioning EXT (auditeur externe avec ExternalMission)."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.maker = _make_admin()
        self.checker = _make_checker(group=self.group)

    def _ext_data(self):
        return {
            "requested_username": "cobac.auditeur",
            "requested_first_name": "Paul",
            "requested_last_name": "Auditorius",
            "requested_email": "p.auditorius@cobac.org",
            "password": "Cobac#12345",
            "requested_role": User.Role.EXT,
            "requested_department": None,
            "mission_organization": "COBAC",
            "mission_scope": "Audit des procédures de crédit",
            "mission_start_date": "2026-07-01",
            "mission_end_date": "2026-09-30",
        }

    def test_ext_requires_mission_fields(self):
        """Un compte EXT sans mission_organization lève ValidationError."""
        from django.core.exceptions import ValidationError
        data = self._ext_data()
        data["mission_organization"] = ""
        with self.assertRaises(ValidationError):
            services.create_provisioning_request(
                maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
            )

    def test_ext_requires_start_date(self):
        """Un compte EXT sans mission_start_date lève ValidationError."""
        from django.core.exceptions import ValidationError
        data = self._ext_data()
        data["mission_start_date"] = None
        with self.assertRaises(ValidationError):
            services.create_provisioning_request(
                maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
            )

    def test_ext_provisioning_creates_user_and_mission(self):
        """L'approbation EXT crée le User (is_external=True) ET une ExternalMission atomiquement."""
        import datetime
        data = self._ext_data()
        data["mission_start_date"] = datetime.date(2026, 7, 1)
        data["mission_end_date"] = datetime.date(2026, 9, 30)

        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        user = services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )

        self.assertTrue(user.is_external)
        self.assertEqual(user.role, User.Role.EXT)

        mission = ExternalMission.objects.get(auditor=user)
        self.assertEqual(mission.organization, "COBAC")

    def test_ext_three_auditlogs_on_approve(self):
        """L'approbation EXT émet 3 AuditLogs : User CREATE, Request UPDATE, Mission CREATE."""
        import datetime
        data = self._ext_data()
        data["mission_start_date"] = datetime.date(2026, 7, 1)
        data["mission_end_date"] = datetime.date(2026, 9, 30)

        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        services.approve_provisioning_request(
            request=req, checker=self.checker, ip_address="127.0.0.1"
        )

        self.assertTrue(AuditLog.objects.filter(
            content_type="User", action=AuditLog.Action.CREATE
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            content_type="UserProvisioningRequest", action=AuditLog.Action.UPDATE
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            content_type="ExternalMission", action=AuditLog.Action.CREATE
        ).exists())

    def test_ext_mission_dates_coherence(self):
        """start_date > end_date lève une ValidationError."""
        from django.core.exceptions import ValidationError
        import datetime
        data = self._ext_data()
        data["mission_start_date"] = datetime.date(2026, 9, 30)
        data["mission_end_date"] = datetime.date(2026, 7, 1)
        with self.assertRaises(ValidationError):
            services.create_provisioning_request(
                maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
            )


# ─── View / access tests ───────────────────────────────────────────────────────


class ProvisioningViewAccessTest(TestCase):
    """Tests de contrôle d'accès aux vues provisioning (AC4)."""

    def setUp(self):
        self.group = _make_approvers_group()
        self.org_type = _make_org_type()
        self.dept = _make_dept(self.org_type)
        self.maker = _make_admin()
        self.checker = _make_checker(group=self.group)
        self.dm = User.objects.create_user(
            username="dm_test", password="DM#12345", role=User.Role.DM
        )
        self.list_url = reverse("auth:provisioning-list")
        self.create_url = reverse("auth:provisioning-create")

    def test_list_forbidden_for_non_admin(self):
        """Un DM (non-Admin IT) reçoit 403 sur la liste (AdminRequiredMixin)."""
        self.client.force_login(self.dm)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_list_accessible_by_maker_admin_it(self):
        """Un Admin IT (maker, hors groupe) peut voir ses propres demandes."""
        self.client.force_login(self.maker)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_accessible_by_checker(self):
        """Un membre du groupe (checker) peut voir toutes les demandes."""
        self.client.force_login(self.checker)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_accessible_by_superuser(self):
        """Un superuser peut accéder à la liste (bootstrapping)."""
        superuser = User.objects.create_superuser(username="root", password="root123")
        self.client.force_login(superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_maker_sees_only_own_requests(self):
        """Un maker hors groupe ne voit que ses propres demandes, pas celles des autres."""
        # Créer une demande du maker
        data = _base_data(role=User.Role.DM, dept=self.dept)
        services.create_provisioning_request(
            maker=self.maker, cleaned_data=data, ip_address="127.0.0.1"
        )
        # Créer une demande d'un autre admin
        other_maker = _make_admin(username="other_maker2", email="om2@bicec.cm")
        data2 = {**data, "requested_username": "autre.user2", "requested_email": "autre2@bicec.cm"}
        services.create_provisioning_request(
            maker=other_maker, cleaned_data=data2, ip_address="127.0.0.1"
        )
        self.client.force_login(self.maker)
        response = self.client.get(self.list_url)
        requests_in_context = list(response.context["requests"])
        # Le maker ne voit que sa propre demande
        for req in requests_in_context:
            self.assertEqual(req.requested_by, self.maker)

    def test_create_accessible_by_admin_it(self):
        """Un Admin IT peut soumettre une demande (modale GET)."""
        self.client.force_login(self.maker)
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)

    def test_create_forbidden_for_dm(self):
        """Un DM ne peut pas soumettre de demande (403)."""
        self.client.force_login(self.dm)
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

    def test_habilitation_toggle_still_requires_audit_admin(self):
        """
        HabilitationToggleAdminView reste sous AuditAdminRequiredMixin (AC5).
        Un checker non-auditeur reçoit 403.
        """
        # Le checker est AUDIT role et membre du groupe
        # On crée un checker non-auditeur (ADMIN dans le groupe)
        non_audit_checker = _make_admin(username="non_audit_checker", email="nac@bicec.cm")
        non_audit_checker.groups.add(self.group)

        target_audit = User.objects.create_user(
            username="audit_target", password="test", role=User.Role.AUDIT
        )
        toggle_url = reverse("workflow:habilitation-toggle-admin", kwargs={"pk": target_audit.pk})
        self.client.force_login(non_audit_checker)
        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 403)

    def test_audit_admin_can_still_toggle(self):
        """Un Audit Admin (is_audit_admin=True) peut toujours toggler le flag."""
        audit_admin = User.objects.create_user(
            username="dir_audit", password="test",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        target = User.objects.create_user(
            username="audit_normal", password="test", role=User.Role.AUDIT
        )
        toggle_url = reverse("workflow:habilitation-toggle-admin", kwargs={"pk": target.pk})
        self.client.force_login(audit_admin)
        response = self.client.post(toggle_url)
        # Doit réussir (200 ou redirect, pas 403)
        self.assertNotEqual(response.status_code, 403)

    def test_organigramme_requires_approver_group(self):
        """L'organigramme est maintenant réservé au groupe IT — Audit reçoit 403."""
        audit_admin = User.objects.create_user(
            username="dir_audit2", password="test",
            role=User.Role.AUDIT, is_audit_admin=True,
        )
        self.client.force_login(audit_admin)
        response = self.client.get(reverse("auth:organigramme-list"))
        self.assertEqual(response.status_code, 403)
