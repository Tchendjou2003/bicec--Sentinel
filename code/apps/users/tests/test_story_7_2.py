"""
Users App — Tests Story 7.2 : Onboarding GRC, bootstrap & profils de comptes

Couvre :
    - AC1/AC2 : entité système seedée, protégée (clean + services), renommable
    - AC3/AC4 : bootstrap gouverné (Checker / Maker / verrou)
    - AC5/AC6 : profils de comptes, création du DAI par formulaire, validation croisée
    - AC7     : rattachement auto ADMIN + exclusion du dept système du sélecteur
"""
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.users import services
from apps.users.account_templates import get_template, resolve_system_department
from apps.users.forms import UserProvisioningRequestForm
from apps.users.models import Department, OrgUnitType, User


def _approvers_group():
    group, _ = Group.objects.get_or_create(name="Administrateurs Sentinel")
    return group


class SystemEntitySeedTest(TestCase):
    """AC1/AC2 — Entité système seedée et protégée."""

    def test_system_department_is_seeded(self):
        dept = resolve_system_department()
        self.assertIsNotNone(dept)
        self.assertTrue(dept.is_system)
        self.assertEqual(dept.code, "SUPPORT")
        self.assertIsNone(dept.parent)

    def test_cannot_deactivate_system_department_via_clean(self):
        """La garde modèle couvre l'édition (DepartmentForm/update)."""
        dept = resolve_system_department()
        dept.is_active = False
        with self.assertRaises(ValidationError):
            dept.full_clean()

    def test_cannot_soft_delete_system_department(self):
        dept = resolve_system_department()
        admin = User.objects.create_user(
            username="adm", password="x", role=User.Role.ADMIN
        )
        with self.assertRaises(ValueError):
            services.soft_delete_department_with_audit(
                department=dept, performed_by=admin
            )

    def test_system_department_is_renamable(self):
        """Le renommage reste autorisé (seul is_active=False est interdit)."""
        dept = resolve_system_department()
        dept.name = "Direction des Systèmes d'Information"
        dept.full_clean()  # ne lève pas
        dept.save()
        self.assertEqual(resolve_system_department().name,
                         "Direction des Systèmes d'Information")

    def test_cannot_deactivate_support_org_unit_type(self):
        support_type = OrgUnitType.objects.get(code="SUPPORT")
        admin = User.objects.create_user(
            username="adm2", password="x", role=User.Role.ADMIN
        )
        with self.assertRaises(ValueError):
            services.toggle_org_unit_type(
                instance=support_type, performed_by=admin
            )


class BootstrapAdminTest(TestCase):
    """AC3/AC4 — Bootstrap gouverné : Checker, Maker, verrou."""

    def test_first_admin_is_checker_in_group(self):
        user = services.bootstrap_create_admin(
            username="sentinel1", email="s1@bicec.cm", password="motdepasse1"
        )
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.department.is_system)
        self.assertFalse(user.is_staff)
        self.assertTrue(
            user.groups.filter(name="Administrateurs Sentinel").exists()
        )

    def test_second_admin_is_maker_outside_group(self):
        services.bootstrap_create_admin(
            username="sentinel1", email="s1@bicec.cm", password="motdepasse1"
        )
        maker = services.bootstrap_create_admin(
            username="sentinel2", email="s2@bicec.cm", password="motdepasse2"
        )
        self.assertFalse(
            maker.groups.filter(name="Administrateurs Sentinel").exists()
        )

    def test_third_admin_is_locked(self):
        services.bootstrap_create_admin(
            username="sentinel1", email="s1@bicec.cm", password="motdepasse1"
        )
        services.bootstrap_create_admin(
            username="sentinel2", email="s2@bicec.cm", password="motdepasse2"
        )
        with self.assertRaises(PermissionDenied):
            services.bootstrap_create_admin(
                username="sentinel3", email="s3@bicec.cm", password="motdepasse3"
            )


class ProvisioningDAITest(TestCase):
    """AC6/AC7 — Création du DAI et rattachement ADMIN via le flux Maker/Checker."""

    def setUp(self):
        _approvers_group()
        self.maker = User.objects.create_user(
            username="maker", password="x", email="maker@bicec.cm",
            role=User.Role.ADMIN, is_staff=True,
        )
        self.checker = User.objects.create_user(
            username="checker", password="x", email="checker@bicec.cm",
            role=User.Role.ADMIN, is_staff=True,
        )

    def _base_data(self, **overrides):
        data = {
            "requested_username": "j.kamga",
            "requested_first_name": "Jean",
            "requested_last_name": "Kamga",
            "requested_email": "j.kamga@bicec.cm",
            "password": "motdepasse1",
            "requested_role": User.Role.AUDIT,
            "requested_department": None,
            "requested_is_audit_admin": True,
            "requested_job_title": "Directeur de l'Audit Interne",
            "requested_profile": "DIRECTEUR_AUDIT",
            "mission_organization": "",
            "mission_scope": "",
            "mission_start_date": None,
            "mission_end_date": None,
        }
        data.update(overrides)
        return data

    def test_create_directeur_audit_via_provisioning(self):
        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=self._base_data()
        )
        self.assertTrue(req.requested_is_audit_admin)
        user = services.approve_provisioning_request(
            request=req, checker=self.checker
        )
        self.assertEqual(user.role, User.Role.AUDIT)
        self.assertTrue(user.is_audit_admin)
        self.assertEqual(user.job_title, "Directeur de l'Audit Interne")

    def test_admin_profile_auto_assigns_system_department(self):
        data = self._base_data(
            requested_username="it.admin",
            requested_email="it.admin@bicec.cm",
            requested_role=User.Role.ADMIN,
            requested_is_audit_admin=False,
            requested_profile="ADMIN_SENTINEL",
            requested_job_title="Administrateur Sentinel",
        )
        req = services.create_provisioning_request(
            maker=self.maker, cleaned_data=data
        )
        self.assertIsNotNone(req.requested_department)
        self.assertTrue(req.requested_department.is_system)


class FormValidationTest(TestCase):
    """AC5/AC7 — Validation croisée et exclusion du département système."""

    def test_is_audit_admin_requires_audit_role(self):
        form = UserProvisioningRequestForm(data={
            "requested_username": "x.user",
            "requested_email": "x.user@bicec.cm",
            "password": "motdepasse1",
            "requested_role": User.Role.DM,
            "requested_is_audit_admin": "on",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("requested_is_audit_admin", form.errors)

    def test_system_department_excluded_from_selector(self):
        form = UserProvisioningRequestForm()
        qs = form.fields["requested_department"].queryset
        self.assertFalse(qs.filter(is_system=True).exists())

    def test_account_template_directeur_audit_consistency(self):
        t = get_template("DIRECTEUR_AUDIT")
        self.assertEqual(t["role"], User.Role.AUDIT)
        self.assertTrue(t["is_audit_admin"])
