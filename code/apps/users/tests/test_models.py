"""
Users App — Tests Unitaires des Modèles

Vérifie la conformité des modèles Department, OrgUnitType et User avec les
spécifications : FR28, FR35, FR36, FR37, ADR-10.

Convention : 1 test par comportement métier, nommage explicite.
"""
from django.db import IntegrityError
from django.test import TestCase

from apps.users.models import Department, OrgUnitType, User


class OrgUnitTypeModelTest(TestCase):
    """Tests du modèle OrgUnitType (Story 3.7.b Phase B)."""

    def setUp(self):
        # Migration 0006 seeds these — use get_or_create
        self.type_dg, _ = OrgUnitType.objects.get_or_create(
            code="DG", defaults={"name": "Direction Générale", "level": 0},
        )
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )

    def test_org_unit_type_str(self):
        """__str__ retourne le libellé."""
        self.assertEqual(str(self.type_dg), "Direction Générale")

    def test_org_unit_type_code_unique(self):
        """Le code est unique — la contrainte est respectée."""
        with self.assertRaises(IntegrityError):
            OrgUnitType.objects.create(name="Doublon DG", code="DG", level=0)

    def test_org_unit_type_active_by_default(self):
        """Un type est actif par défaut."""
        self.assertTrue(self.type_dg.is_active)

    def test_org_unit_type_level_advisory(self):
        """Le niveau indicatif est bien enregistré."""
        self.assertEqual(self.type_direction.level, 1)


class DepartmentModelTest(TestCase):
    """Tests du modèle Department (organigramme — FR35)."""

    def setUp(self):
        """Crée une hiérarchie de test : Direction → Agence."""
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        self.type_agence, _ = OrgUnitType.objects.get_or_create(
            code="AGENCE", defaults={"name": "Agence", "level": 6},
        )
        self.direction = Department.objects.create(
            name="Direction des Opérations",
            code="DOP",
            type=self.type_direction,
        )
        self.agence = Department.objects.create(
            name="Agence Douala Bonanjo",
            code="DLA-BON",
            type=self.type_agence,
            parent=self.direction,
        )

    def test_department_creation(self):
        """Un département est créé avec tous ses champs."""
        self.assertEqual(self.direction.name, "Direction des Opérations")
        self.assertEqual(self.direction.code, "DOP")
        self.assertEqual(self.direction.type, self.type_direction)
        self.assertTrue(self.direction.is_active)
        self.assertIsNone(self.direction.parent)

    def test_department_type_is_fk(self):
        """Le type est une FK vers OrgUnitType (plus un enum)."""
        self.assertIsInstance(self.direction.type, OrgUnitType)
        self.assertEqual(self.direction.type.code, "DIRECTION")
        self.assertEqual(self.direction.type.name, "Direction")

    def test_department_hierarchy(self):
        """Un département enfant référence correctement son parent."""
        self.assertEqual(self.agence.parent, self.direction)
        children = self.direction.get_children()
        self.assertIn(self.agence, children)

    def test_department_code_unique(self):
        """Le code département est unique (contrainte DB)."""
        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name="Doublon",
                code="DOP",  # Même code que self.direction
                type=self.type_direction,
            )

    def test_department_str_without_parent(self):
        """__str__ d'un département racine affiche son nom seul."""
        self.assertEqual(str(self.direction), "Direction des Opérations")

    def test_department_str_with_parent(self):
        """__str__ d'un département enfant affiche la hiérarchie."""
        self.assertEqual(
            str(self.agence),
            "Direction des Opérations → Agence Douala Bonanjo",
        )

    def test_get_children_excludes_inactive(self):
        """get_children() ne retourne que les départements actifs."""
        inactive = Department.objects.create(
            name="Agence Fermée",
            code="FERM",
            type=self.type_agence,
            parent=self.direction,
            is_active=False,
        )
        children = self.direction.get_children()
        self.assertNotIn(inactive, children)
        self.assertIn(self.agence, children)

    def test_department_protect_on_delete(self):
        """Supprimer un parent avec des enfants lève ProtectedError."""
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.direction.delete()


class DepartmentFullHierarchyTest(TestCase):
    """Tests de la hiérarchie multi-niveaux réelle BICEC."""

    def setUp(self):
        # Migration 0006 seeds these — use get_or_create
        self.type_dg, _ = OrgUnitType.objects.get_or_create(code="DG", defaults={"name": "Direction Générale", "level": 0})
        self.type_direction, _ = OrgUnitType.objects.get_or_create(code="DIRECTION", defaults={"name": "Direction", "level": 1})
        self.type_sous_dir, _ = OrgUnitType.objects.get_or_create(code="SOUS_DIRECTION", defaults={"name": "Sous-Direction", "level": 2})
        self.type_dept, _ = OrgUnitType.objects.get_or_create(code="DEPARTEMENT", defaults={"name": "Département", "level": 3})
        self.type_service, _ = OrgUnitType.objects.get_or_create(code="SERVICE", defaults={"name": "Service", "level": 4})
        self.type_region, _ = OrgUnitType.objects.get_or_create(code="REGION", defaults={"name": "Direction Régionale", "level": 5})
        self.type_agence, _ = OrgUnitType.objects.get_or_create(code="AGENCE", defaults={"name": "Agence", "level": 6})

    def test_full_hierarchy_dg_to_service(self):
        """DG → DIRECTION → SOUS_DIRECTION → DEPARTEMENT → SERVICE."""
        dg = Department.objects.create(name="DG BICEC", code="DG", type=self.type_dg)
        direction = Department.objects.create(
            name="DOGSI", code="DOGSI",
            type=self.type_direction, parent=dg,
        )
        sous_dir = Department.objects.create(
            name="Sous-Direction SI", code="SDSI",
            type=self.type_sous_dir, parent=direction,
        )
        dept = Department.objects.create(
            name="Études et Développement", code="DEV",
            type=self.type_dept, parent=sous_dir,
        )
        service = Department.objects.create(
            name="Service Support", code="SUP",
            type=self.type_service, parent=dept,
        )
        self.assertEqual(service.parent.parent.parent.parent, dg)

    def test_region_contains_agences(self):
        """REGION → AGENCE."""
        region = Department.objects.create(
            name="Direction Régionale Littoral", code="DRLIT",
            type=self.type_region,
        )
        agence = Department.objects.create(
            name="Agence Douala Bonanjo", code="DLBON",
            type=self.type_agence, parent=region,
        )
        self.assertIn(agence, region.get_children())

    def test_all_org_unit_types_are_creatable(self):
        """Vérifie que tous les types peuvent être assignés à des départements."""
        types = [
            self.type_dg, self.type_direction, self.type_sous_dir,
            self.type_dept, self.type_service, self.type_region, self.type_agence,
        ]
        for i, t in enumerate(types):
            Department.objects.create(
                name=f"Test {t.name}", code=f"T{i}", type=t,
            )
        self.assertEqual(
            Department.objects.count(), len(types),
        )


class UserShellAccountTest(TestCase):
    """Tests du concept « coquille vide » (ADR-10, FR37)."""

    def setUp(self):
        """Crée un compte coquille vide (pas de rôle)."""
        self.shell_user = User.objects.create_user(
            username="coquille_vide",
            password="testpass123",
            email="shell@bicec.cm",
        )

    def test_user_without_role_is_shell(self):
        """Un User avec role='' est une coquille vide."""
        self.assertFalse(self.shell_user.has_role)
        self.assertTrue(self.shell_user.is_shell_account)

    def test_user_without_role_has_empty_string(self):
        """Le rôle par défaut est une chaîne vide (pas NULL)."""
        self.assertEqual(self.shell_user.role, "")


class UserWithRoleTest(TestCase):
    """Tests des comptes avec rôle métier attribué."""

    def setUp(self):
        """Crée un département et un utilisateur DM."""
        self.type_direction, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        self.dept = Department.objects.create(
            name="Direction Financière",
            code="DFIN",
            type=self.type_direction,
        )
        self.dm_user = User.objects.create_user(
            username="directeur_metier",
            password="testpass123",
            email="dm@bicec.cm",
            role=User.Role.DM,
            department=self.dept,
        )

    def test_user_with_role_is_active(self):
        """Un User avec un rôle métier n'est pas une coquille vide."""
        self.assertTrue(self.dm_user.has_role)
        self.assertFalse(self.dm_user.is_shell_account)

    def test_user_department_assignment(self):
        """Un User est correctement rattaché à un département (FR28)."""
        self.assertEqual(self.dm_user.department, self.dept)


class UserAuditAdminTest(TestCase):
    """Tests du flag is_audit_admin (ADR-10, FR36)."""

    def setUp(self):
        """Crée les différents profils pour tester can_manage_users."""
        self.audit_director = User.objects.create_user(
            username="directeur_audit",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=True,
        )
        self.regular_audit = User.objects.create_user(
            username="auditeur_standard",
            password="testpass123",
            role=User.Role.AUDIT,
            is_audit_admin=False,
        )
        self.dm_with_flag = User.objects.create_user(
            username="dm_avec_flag",
            password="testpass123",
            role=User.Role.DM,
            is_audit_admin=True,  # Flag activé mais rôle non-AUDIT
        )
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="testpass123",
            role=User.Role.ADMIN,
        )

    def test_audit_director_can_manage_users(self):
        """Le Directeur Audit (AUDIT + is_audit_admin) peut gérer les comptes."""
        self.assertTrue(self.audit_director.can_manage_users)

    def test_regular_audit_cannot_manage_users(self):
        """Un auditeur standard (AUDIT sans is_audit_admin) ne peut pas gérer les comptes."""
        self.assertFalse(self.regular_audit.can_manage_users)

    def test_non_audit_role_cannot_manage_users(self):
        """Un DM même avec is_audit_admin=True ne peut pas gérer les comptes."""
        self.assertFalse(self.dm_with_flag.can_manage_users)

    def test_admin_cannot_manage_users(self):
        """L'Admin ne peut pas gérer les habilitations (ADR-10)."""
        self.assertFalse(self.admin_user.can_manage_users)
