"""
Users App — Tests des Vues d'Authentification

Vérifie la logique de connexion et la redirection conditionnelle (FR37).
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class SentinelLoginViewTest(TestCase):
    """Tests de la vue SentinelLoginView (redirection par rôle)."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("auth:login")
        
        # Utilisateur "coquille vide" (sans rôle)
        self.shell_user = User.objects.create_user(
            username="shell",
            password="testpass123",
            email="shell@bicec.cm",
        )
        
        # Utilisateur Admin
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="testpass123",
            email="admin@bicec.cm",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        
        # Utilisateur classique (DM)
        self.dm_user = User.objects.create_user(
            username="dm",
            password="testpass123",
            email="dm@bicec.cm",
            role=User.Role.DM,
        )

    def test_login_page_renders(self):
        """La page de login s'affiche correctement (GET)."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login.html")

    def test_login_invalid_credentials(self):
        """Des identifiants invalides ne connectent pas l'utilisateur."""
        response = self.client.post(self.login_url, {
            "username": "shell",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_login_redirect_shell_user_to_pending(self):
        """Un compte sans rôle est redirigé vers /auth/pending/ (FR37)."""
        response = self.client.post(self.login_url, {
            "username": "shell",
            "password": "testpass123"
        })
        self.assertRedirects(response, reverse("auth:pending"))

    def test_login_redirect_admin_to_dashboard(self):
        """L'Admin est redirigé vers le dashboard Admin IT (Story 1.4 / AC1)."""
        response = self.client.post(self.login_url, {
            "username": "admin_user",
            "password": "testpass123"
        })
        self.assertRedirects(response, reverse("auth:admin-dashboard"))

    def test_login_redirect_dm_to_home(self):
        """Un compte avec rôle (ex: DM) est redirigé vers la home par défaut."""
        response = self.client.post(self.login_url, {
            "username": "dm",
            "password": "testpass123"
        })
        # Par défaut, LOGIN_REDIRECT_URL est "/"
        self.assertRedirects(response, "/")


class PendingActivationViewTest(TestCase):
    """Tests de la vue PendingActivationView (protection)."""

    def setUp(self):
        self.client = Client()
        self.pending_url = reverse("auth:pending")
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

    def test_pending_page_requires_login(self):
        """Un utilisateur non connecté est redirigé vers le login."""
        response = self.client.get(self.pending_url)
        self.assertRedirects(response, f"{reverse('auth:login')}?next={self.pending_url}")

    def test_pending_page_accessible_for_shell_user(self):
        """Un compte sans rôle peut accéder à la page d'attente."""
        self.client.force_login(self.shell_user)
        response = self.client.get(self.pending_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/pending.html")

    def test_pending_page_redirect_if_has_role(self):
        """Un compte actif (avec rôle) est expulsé de la page d'attente vers la home."""
        self.client.force_login(self.dm_user)
        response = self.client.get(self.pending_url)
        self.assertRedirects(response, self.home_url)
