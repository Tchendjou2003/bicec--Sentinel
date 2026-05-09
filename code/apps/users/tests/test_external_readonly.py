"""
Users App — Tests du Middleware Read-Only Externe (Story 1.3, AC1 + AC3)

Vérifie que :
    - AC1 : Les utilisateurs is_external=True ne peuvent effectuer aucune
      action d'écriture (POST, PUT, DELETE).
    - AC3 : Les utilisateurs externes ne peuvent PAS accéder aux vues internes
      (admin, gestion, etc.) → 403 Forbidden.
    - La déconnexion (POST /auth/logout/) reste autorisée pour les EXT.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class ExternalReadOnlyMiddlewareTest(TestCase):
    """Tests du middleware bloquant les écritures pour les comptes externes (AC1)."""

    def setUp(self):
        self.client = Client()
        self.ext_user = User.objects.create_user(
            username="ext_readonly",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_writer",
            password="testpass123",
            role=User.Role.DM,
        )

    def test_ext_user_get_request_allowed(self):
        """Les requêtes GET sont autorisées pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_ext_user_post_request_blocked(self):
        """Les requêtes POST sont bloquées (403) pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.post(reverse("home"))
        self.assertEqual(response.status_code, 403)

    def test_ext_user_put_request_blocked(self):
        """Les requêtes PUT sont bloquées (403) pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.put(reverse("home"))
        self.assertEqual(response.status_code, 403)

    def test_ext_user_delete_request_blocked(self):
        """Les requêtes DELETE sont bloquées (403) pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.delete(reverse("home"))
        self.assertEqual(response.status_code, 403)

    def test_ext_user_logout_post_allowed(self):
        """La déconnexion (POST /auth/logout/) est autorisée pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.post(reverse("auth:logout"))
        # LogoutView effectue une redirection (302) après déconnexion
        self.assertIn(response.status_code, [200, 302])

    def test_internal_user_post_not_blocked(self):
        """Les requêtes POST d'un utilisateur interne ne sont PAS bloquées."""
        self.client.force_login(self.dm_user)
        # Un DM peut faire un POST vers la home (même si la view peut ne pas le supporter,
        # ce qui compte c'est que le middleware ne bloque pas)
        response = self.client.post(reverse("home"))
        # Ne doit PAS renvoyer 403 depuis le middleware (peut être 405, 200 ou redirect,
        # mais le middleware ne doit pas le bloquer).
        self.assertNotEqual(response.status_code, 403)


class ExternalAccessInternalBlockTest(TestCase):
    """Tests du blocage d'accès aux URLs internes pour les EXT (AC3)."""

    def setUp(self):
        self.client = Client()
        self.ext_user = User.objects.create_user(
            username="ext_blocked",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )

    def test_ext_user_cannot_access_admin(self):
        """Un utilisateur externe ne peut pas accéder à /admin/."""
        self.client.force_login(self.ext_user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 403)

    def test_ext_user_cannot_access_habilitation(self):
        """Un utilisateur externe ne peut pas accéder à la page d'habilitation."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:habilitation-list"))
        self.assertEqual(response.status_code, 403)

    def test_ext_user_cannot_access_home(self):
        """Un utilisateur externe ne peut pas accéder à la page d'accueil interne."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 403)

    def test_ext_user_can_access_external_dashboard(self):
        """Un utilisateur externe PEUT accéder à son tableau de bord."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_ext_user_can_access_login_page(self):
        """Le middleware n'empêche pas un utilisateur externe d'accéder à /auth/login/."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:login"))
        self.assertIn(response.status_code, [200, 302])

    def test_ext_user_can_logout(self):
        """Un utilisateur externe peut se déconnecter."""
        self.client.force_login(self.ext_user)
        response = self.client.post(reverse("auth:logout"))
        self.assertIn(response.status_code, [200, 302])


class ExternalPatchMethodTest(TestCase):
    """Test PATCH bloqué pour les EXT (L1 — Code Review)."""

    def setUp(self):
        self.client = Client()
        self.ext_user = User.objects.create_user(
            username="ext_patch",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )

    def test_ext_user_patch_request_blocked(self):
        """Les requêtes PATCH sont bloquées (403) pour un utilisateur externe."""
        self.client.force_login(self.ext_user)
        response = self.client.patch(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 403)


class ExternalRoleInconsistencyTest(TestCase):
    """Test edge case : role=EXT avec is_external=False (M5 — Code Review)."""

    def setUp(self):
        self.client = Client()
        self.inconsistent_user = User.objects.create_user(
            username="ext_inconsistent",
            password="testpass123",
            role=User.Role.EXT,
            is_external=False,  # Incohérence volontaire
        )

    def test_inconsistent_ext_user_blocked_from_external_dashboard(self):
        """Un user role=EXT avec is_external=False ne peut pas accéder au dashboard externe."""
        self.client.force_login(self.inconsistent_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 403)
