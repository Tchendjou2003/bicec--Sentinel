"""
Users App — Tests du Canal de Connexion Externe (Story 1.3, AC2)

Vérifie le canal de connexion isolé pour les auditeurs externes :
    - Redirection post-login vers l'espace externe pour les EXT
    - Template shell dédié (external_shell.html)
    - Isolation visuelle et fonctionnelle

Spécifications couvertes :
    - AC2 : Canal de connexion spécifique / redirection EXT
    - FR2 : Isolation des auditeurs externes
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class ExternalLoginRedirectionTest(TestCase):
    """Tests de redirection post-login pour les auditeurs externes (AC2)."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("auth:login")

        self.ext_user = User.objects.create_user(
            username="ext_cobac",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_internal",
            password="testpass123",
            role=User.Role.DM,
        )

    def test_ext_user_redirected_to_external_dashboard(self):
        """Un utilisateur EXT est redirigé vers le tableau de bord externe après login."""
        response = self.client.post(
            self.login_url,
            {"username": "ext_cobac", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("auth:external-dashboard"))

    def test_internal_user_not_redirected_to_external(self):
        """Un DM n'est pas redirigé vers le dashboard externe."""
        response = self.client.post(
            self.login_url,
            {"username": "dm_internal", "password": "testpass123"},
        )
        # DM doit être redirigé vers la home (pas le dashboard externe)
        self.assertNotEqual(
            response.url if hasattr(response, "url") else "",
            reverse("auth:external-dashboard"),
        )


class ExternalDashboardViewTest(TestCase):
    """Tests du tableau de bord externe (espace isolé — AC2)."""

    def setUp(self):
        self.client = Client()
        self.ext_user = User.objects.create_user(
            username="ext_beac",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )
        self.dm_user = User.objects.create_user(
            username="dm_test",
            password="testpass123",
            role=User.Role.DM,
        )

    def test_external_dashboard_accessible_by_ext_user(self):
        """Le tableau de bord externe est accessible par un utilisateur EXT."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_external_dashboard_forbidden_for_internal_user(self):
        """Un utilisateur interne (DM) ne peut pas accéder au tableau de bord externe."""
        self.client.force_login(self.dm_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_external_dashboard_uses_external_shell(self):
        """Le tableau de bord externe utilise le template external_shell.html."""
        self.client.force_login(self.ext_user)
        response = self.client.get(reverse("auth:external-dashboard"))
        # Vérifie que le template de l'espace externe est utilisé
        template_names = [t.name for t in response.templates]
        self.assertIn("external/dashboard.html", template_names)

    def test_external_dashboard_requires_login(self):
        """Le tableau de bord externe requiert une authentification."""
        response = self.client.get(reverse("auth:external-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)
