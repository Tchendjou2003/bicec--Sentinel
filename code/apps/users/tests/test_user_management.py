"""
Users App — Tests Story 8.x : Page unifiée Gestion des Utilisateurs + Mon Profil

Couvre :
    - UserManagementView (2 onglets, filtres)
    - Services reset_user_password, deactivate_user, reactivate_user, change_own_password
    - Flux MODIFY : création et approbation d'une demande de modification de profil
    - Page Mon Profil (tous rôles)
"""
import json

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.users import services
from apps.users.models import Department, OrgUnitType, User, UserProvisioningRequest


def _admin(**kw):
    defaults = {"role": User.Role.ADMIN, "is_staff": True}
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def _regular_user(username, role=User.Role.DM, **kw):
    return User.objects.create_user(username=username, password="pass1234", role=role, **kw)


def _approvers_group():
    group, _ = Group.objects.get_or_create(name="Administrateurs Sentinel")
    return group


# ──────────────────────────────────────────────────────────────────────────────
# Vue UserManagementView
# ──────────────────────────────────────────────────────────────────────────────

class UserManagementViewTest(TestCase):
    """Page unifiée rendue correctement avec les 2 onglets."""

    def setUp(self):
        self.client = Client()
        self.admin = _admin(username="admin_mgmt", password="pass1234")
        self.client.force_login(self.admin)
        self.url = reverse("auth:user-management")

    def test_page_renders_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/user_management.html")

    def test_context_contains_counts(self):
        _regular_user("dm1", role=User.Role.DM)
        _regular_user("dm2", role=User.Role.DM, is_active=False)
        response = self.client.get(self.url)
        self.assertIn("active_count", response.context)
        self.assertIn("inactive_count", response.context)
        self.assertIn("pending_count", response.context)

    def test_filter_by_role(self):
        _regular_user("dm_ok", role=User.Role.DM)
        _regular_user("etp_ok", role=User.Role.ETP)
        response = self.client.get(f"{self.url}?role=DM")
        users = list(response.context["users"])
        for u in users:
            self.assertEqual(u.role, User.Role.DM)

    def test_filter_by_status_inactive(self):
        _regular_user("active_u", role=User.Role.DM, is_active=True)
        _regular_user("inactive_u", role=User.Role.DM, is_active=False)
        response = self.client.get(f"{self.url}?status=inactive")
        users = list(response.context["users"])
        for u in users:
            self.assertFalse(u.is_active)

    def test_requires_admin_role(self):
        dm = _regular_user("dm_noaccess", role=User.Role.DM)
        self.client.force_login(dm)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────────────────
# Service reset_user_password
# ──────────────────────────────────────────────────────────────────────────────

class ResetUserPasswordServiceTest(TestCase):

    def setUp(self):
        self.admin = _admin(username="adm_reset", password="pass1234")
        self.target = _regular_user("target_reset", role=User.Role.DM)

    def test_password_is_changed(self):
        services.reset_user_password(
            target_user=self.target,
            new_password="NouveauMdp2024!",
            performed_by=self.admin,
        )
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("NouveauMdp2024!"))

    def test_empty_password_raises(self):
        with self.assertRaises((ValueError, ValidationError)):
            services.reset_user_password(
                target_user=self.target,
                new_password="",
                performed_by=self.admin,
            )


# ──────────────────────────────────────────────────────────────────────────────
# Service deactivate_user
# ──────────────────────────────────────────────────────────────────────────────

class DeactivateUserServiceTest(TestCase):

    def setUp(self):
        self.admin = _admin(username="adm_deact", password="pass1234")
        self.target = _regular_user("target_deact", role=User.Role.DM, is_active=True)

    def test_deactivate_sets_is_active_false(self):
        services.deactivate_user(target_user=self.target, performed_by=self.admin)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_cannot_deactivate_self(self):
        with self.assertRaises(PermissionDenied):
            services.deactivate_user(
                target_user=self.admin,
                performed_by=self.admin,
            )


# ──────────────────────────────────────────────────────────────────────────────
# Service reactivate_user
# ──────────────────────────────────────────────────────────────────────────────

class ReactivateUserServiceTest(TestCase):

    def setUp(self):
        self.admin = _admin(username="adm_react", password="pass1234")
        self.target = _regular_user("target_react", role=User.Role.DM, is_active=False)

    def test_reactivate_sets_is_active_true(self):
        services.reactivate_user(target_user=self.target, performed_by=self.admin)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)


# ──────────────────────────────────────────────────────────────────────────────
# Service change_own_password
# ──────────────────────────────────────────────────────────────────────────────

class ChangeOwnPasswordServiceTest(TestCase):

    def setUp(self):
        self.user = _regular_user("self_changer", role=User.Role.DM)
        self.user.set_password("OldPass2024!")
        self.user.save()

    def test_wrong_old_password_raises(self):
        with self.assertRaises(ValidationError):
            services.change_own_password(
                user=self.user,
                old_password="WrongOld!",
                new_password="NewPass2024!",
            )

    def test_correct_old_password_changes_it(self):
        services.change_own_password(
            user=self.user,
            old_password="OldPass2024!",
            new_password="NewPass2024!",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass2024!"))


# ──────────────────────────────────────────────────────────────────────────────
# Flux MODIFY via Maker/Checker
# ──────────────────────────────────────────────────────────────────────────────

class ModifyProvisioningFlowTest(TestCase):

    def setUp(self):
        self.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIR", defaults={"name": "Direction", "level": 1}
        )
        self.dept_a, _ = Department.objects.get_or_create(
            code="DA", defaults={"name": "Direction A", "type": self.type_dir}
        )
        self.dept_b, _ = Department.objects.get_or_create(
            code="DB", defaults={"name": "Direction B", "type": self.type_dir}
        )
        self.maker = _admin(username="maker_modify", password="pass1234")
        self.checker = _admin(username="checker_modify", password="pass1234")
        group = _approvers_group()
        self.checker.groups.add(group)

        self.target = User.objects.create_user(
            username="target_modify",
            password="pass1234",
            role=User.Role.DM,
        )
        self.target.department = self.dept_a
        self.target.save()

    def _create_modify_request(self):
        return services.create_provisioning_request(
            maker=self.maker,
            cleaned_data={
                "request_type": "MODIFY",
                "target_user": self.target,
                "requested_role": User.Role.ETP,
                "requested_department": self.dept_b,
                "requested_is_audit_admin": False,
                "requested_job_title": "Chef de projet",
                "requested_first_name": "",
                "requested_last_name": "",
                "requested_username": self.target.username,
                "requested_email": self.target.email,
                "password": "",
            },
        )

    def test_modify_request_cannot_target_self(self):
        with self.assertRaises(PermissionDenied):
            services.create_provisioning_request(
                maker=self.maker,
                cleaned_data={
                    "request_type": "MODIFY",
                    "target_user": self.maker,
                    "requested_role": User.Role.DM,
                    "requested_department": self.dept_a,
                    "requested_is_audit_admin": False,
                    "requested_job_title": "",
                    "requested_first_name": "",
                    "requested_last_name": "",
                    "requested_username": self.maker.username,
                    "requested_email": self.maker.email,
                    "password": "",
                },
            )

    def test_modify_request_is_created_as_pending(self):
        req = self._create_modify_request()
        self.assertEqual(req.request_type, UserProvisioningRequest.RequestType.MODIFY)
        self.assertEqual(req.status, UserProvisioningRequest.Status.PENDING)
        self.assertEqual(req.target_user, self.target)
        self.assertEqual(req.hashed_initial_password, "")

    def test_modify_approve_updates_existing_user(self):
        req = self._create_modify_request()
        user_count_before = User.objects.count()
        services.approve_provisioning_request(
            request=req, checker=self.checker
        )
        # Aucun nouveau User créé
        self.assertEqual(User.objects.count(), user_count_before)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ETP)
        self.assertEqual(self.target.department, self.dept_b)
        self.assertEqual(self.target.job_title, "Chef de projet")
        self.assertEqual(req.pk, req.pk)  # toujours le même

    def test_approve_sets_status_approved(self):
        req = self._create_modify_request()
        services.approve_provisioning_request(
            request=req, checker=self.checker
        )
        req.refresh_from_db()
        self.assertEqual(req.status, UserProvisioningRequest.Status.APPROVED)

    def test_modify_via_view_post_resolves_target_user(self):
        """Chemin réel form→vue→service : le champ caché target_user (UUID) doit
        être résolu en User par clean_target_user (régression code review #1)."""
        client = Client()
        client.force_login(self.maker)
        resp = client.post(
            reverse("auth:provisioning-create"),
            data={
                "request_type": "MODIFY",
                "target_user": str(self.target.pk),
                "requested_role": User.Role.ETP,
                "requested_department": str(self.dept_b.pk),
                "requested_job_title": "Chef de projet",
                "requested_username": self.target.username,
                "requested_email": self.target.email,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 204)
        req = UserProvisioningRequest.objects.get(target_user=self.target)
        self.assertEqual(req.request_type, UserProvisioningRequest.RequestType.MODIFY)
        self.assertEqual(req.requested_role, User.Role.ETP)

    def test_modify_view_post_unknown_target_returns_404(self):
        """Un target_user inexistant ne doit pas retomber silencieusement en CREATE."""
        import uuid as _uuid
        client = Client()
        client.force_login(self.maker)
        resp = client.post(
            reverse("auth:provisioning-create"),
            data={
                "request_type": "MODIFY",
                "target_user": str(_uuid.uuid4()),
                "requested_role": User.Role.ETP,
                "requested_department": str(self.dept_b.pk),
                "requested_username": "ghost",
                "requested_email": "ghost@bicec.cm",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 404)


# ──────────────────────────────────────────────────────────────────────────────
# Page Mon Profil
# ──────────────────────────────────────────────────────────────────────────────

class UserProfileViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("auth:user-profile")

    def _login_as(self, role):
        user = User.objects.create_user(
            username=f"user_{role}", password="pass1234", role=role
        )
        self.client.force_login(user)
        return user

    def test_profile_accessible_to_admin(self):
        self._login_as(User.Role.ADMIN)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile/profile.html")

    def test_profile_accessible_to_audit(self):
        self._login_as(User.Role.AUDIT)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_profile_accessible_to_dm(self):
        self._login_as(User.Role.DM)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_profile_redirects_anonymous(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_change_own_password_via_profile_view(self):
        user = self._login_as(User.Role.DM)
        user.set_password("OldPass2024!")
        user.save()
        self.client.force_login(user)

        response = self.client.post(self.url, {
            "old_password": "OldPass2024!",
            "new_password": "NewPass2024!",
            "confirm_password": "NewPass2024!",
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass2024!"))

    def test_wrong_old_password_shows_error(self):
        user = self._login_as(User.Role.DM)
        user.set_password("OldPass2024!")
        user.save()
        self.client.force_login(user)

        response = self.client.post(self.url, {
            "old_password": "WrongPassword!",
            "new_password": "NewPass2024!",
            "confirm_password": "NewPass2024!",
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("OldPass2024!"))
