"""
Smoke tests — Story 1.2 (Authentification)
"""
from django.test import TestCase, Client
from apps.users.models import User


class AuthSmokeTest(TestCase):
    """Tests du flux d'authentification."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123!",
            role=User.Role.ETP,
        )

    def test_anonymous_home_redirects_to_login(self):
        """Un utilisateur anonyme est redirigé vers /auth/login/."""
        response = self.client.get("/")
        self.assertRedirects(response, "/auth/login/?next=/")

    def test_login_page_returns_200(self):
        """La page de login est accessible sans authentification."""
        response = self.client.get("/auth/login/")
        self.assertEqual(response.status_code, 200)

    def test_login_with_valid_credentials(self):
        """Un login valide redirige vers la page d'accueil."""
        response = self.client.post(
            "/auth/login/",
            {"username": "testuser", "password": "testpass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")

    def test_login_with_invalid_credentials(self):
        """Un login invalide reste sur la page de login."""
        response = self.client.post(
            "/auth/login/",
            {"username": "testuser", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login.html")

    def test_logout_post_redirects_to_login(self):
        """La déconnexion POST redirige vers la page de login."""
        self.client.force_login(self.user)
        response = self.client.post("/auth/logout/")
        self.assertRedirects(response, "/auth/login/", fetch_redirect_response=False)


class HomePageSmokeTest(TestCase):
    """Tests de la page d'accueil (utilisateur authentifié)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123!",
            role=User.Role.AUDIT,
        )
        self.client.force_login(self.user)

    def test_home_page_returns_200(self):
        """La page d'accueil renvoie 200 pour un utilisateur connecté."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_page_uses_correct_template(self):
        response = self.client.get("/")
        self.assertTemplateUsed(response, "home.html")

    def test_home_page_contains_sentinel_title(self):
        response = self.client.get("/")
        self.assertContains(response, "Sentinel")

    def test_security_headers_present(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")

