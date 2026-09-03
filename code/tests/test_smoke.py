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
        """Un login valide redirige vers le suivi des recommandations."""
        response = self.client.post(
            "/auth/login/",
            {"username": "testuser", "password": "testpass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workflow/recommendation_list.html")

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

    def test_home_redirects_to_dashboard(self):
        """
        Depuis la Story 6.1a, « / » redirige (302) vers le tableau de bord.
        On suit la redirection et on vérifie qu'elle aboutit à une page 200.
        """
        response = self.client.get("/", follow=True)
        self.assertEqual(response.status_code, 200)
        # Au moins une redirection a eu lieu (/ → dashboards:home)
        self.assertTrue(len(response.redirect_chain) >= 1)

    def test_home_page_contains_sentinel_title(self):
        """La page de destination contient le branding Sentinel (base.html)."""
        response = self.client.get("/", follow=True)
        self.assertContains(response, "Sentinel")

    def test_security_headers_present(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")

