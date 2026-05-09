"""
Users App — Tests Unitaires des Modèles

Vérifie la conformité des modèles Department et User avec les
spécifications : FR28, FR35, FR36, FR37, ADR-10.

Convention : 1 test par comportement métier, nommage explicite.
"""
from django.db import IntegrityError
from django.test import TestCase

from apps.users.models import Department, User


class DepartmentModelTest(TestCase):
    """Tests du modèle Department (organigramme — FR35)."""

    def setUp(self):
        """Crée une hiérarchie de test : Direction → Agence."""
        self.direction = Department.objects.create(
            name="Direction des Opérations",
            code="DOP",
            type=Department.Type.DIRECTION,
        )
        self.agence = Department.objects.create(
            name="Agence Douala Bonanjo",
            code="DLA-BON",
            type=Department.Type.AGENCE,
            parent=self.direction,
        )

    def test_department_creation(self):
        """Un département est créé avec tous ses champs."""
        self.assertEqual(self.direction.name, "Direction des Opérations")
        self.assertEqual(self.direction.code, "DOP")
        self.assertEqual(self.direction.type, Department.Type.DIRECTION)
        self.assertTrue(self.direction.is_active)
        self.assertIsNone(self.direction.parent)

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
                type=Department.Type.DIRECTION,
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
            type=Department.Type.AGENCE,
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
        self.dept = Department.objects.create(
            name="Direction Financière",
            code="DFIN",
            type=Department.Type.DIRECTION,
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
        self.rssi = User.objects.create_user(
            username="rssi",
            password="testpass123",
            role=User.Role.RSSI,
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

    def test_rssi_cannot_manage_users(self):
        """Le RSSI ne peut pas gérer les habilitations (ADR-10)."""
        self.assertFalse(self.rssi.can_manage_users)
