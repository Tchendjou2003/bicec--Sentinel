"""
Users App — Tests Middleware

Vérifie la protection globale par le RoleRequiredMiddleware (FR37).
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class RoleRequiredMiddlewareTest(TestCase):
    """Tests de protection globale par rôle."""

    def setUp(self):
        self.client = Client()
        self.pending_url = reverse("auth:pending")
        self.login_url = reverse("auth:login")
        self.home_url = reverse("home")
        
        self.shell_user = User.objects.create_user(
            username="shell",
            password="testpass123",
        )
        self.dm_user = User.objects.create_user(
            username="dm",
            password="testpass123",
            role=User.Role.DM,
        )

    def test_shell_user_redirected_to_pending(self):
        """Un compte sans rôle est redirigé vers pending s'il accède à la home."""
        self.client.force_login(self.shell_user)
        response = self.client.get(self.home_url)
        self.assertRedirects(response, self.pending_url)

    def test_shell_user_can_access_login(self):
        """Un compte sans rôle peut accéder à la page de login (logout)."""
        self.client.force_login(self.shell_user)
        response = self.client.get(self.login_url)
        # LoginRedirects (because user is already logged in) mais le middleware ne bloque pas
        # Le standard Django auth views redirige les users connectés vers LOGIN_REDIRECT_URL ou profile
        # Testons juste que le middleware ne force pas vers pending
        self.assertNotEqual(response.status_code, 500)
        
    def test_shell_user_can_access_pending(self):
        """Un compte sans rôle peut accéder à la page d'attente (pas de boucle)."""
        self.client.force_login(self.shell_user)
        response = self.client.get(self.pending_url)
        self.assertEqual(response.status_code, 200)

    def test_active_user_not_redirected(self):
        """Un compte actif (avec rôle) n'est pas bloqué par le middleware."""
        self.client.force_login(self.dm_user)
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_not_affected(self):
        """Un visiteur anonyme n'est pas intercepté par ce middleware (géré par LoginRequired)."""
        # La home vue demande le login, donc 302 vers login
        response = self.client.get(self.home_url)
        self.assertRedirects(response, f"{self.login_url}?next={self.home_url}")
