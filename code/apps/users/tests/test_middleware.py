"""
Users App — Tests Middleware

Vérifie :
    - RoleRequiredMiddleware : protection globale par rôle (FR37)
    - IdleTimeoutMiddleware : déconnexion après 30 min d'inactivité (AC2 / NFR-SEC-02)
"""
import time

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
        response = self.client.get(self.home_url)
        self.assertRedirects(response, f"{self.login_url}?next={self.home_url}")


class IdleTimeoutMiddlewareTest(TestCase):
    """Tests du middleware d'inactivité (AC2 / NFR-SEC-02).

    Vérifie que :
        - Un utilisateur inactif > 30 min est déconnecté
        - L'activité remet le compteur à zéro
        - Les routes publiques ne déclenchent pas le timeout
        - Les utilisateurs anonymes ne sont pas impactés
    """

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("auth:login")
        self.home_url = reverse("home")

        self.user = User.objects.create_user(
            username="timeout_test",
            password="testpass123",
            role=User.Role.DM,
        )

    def test_session_expires_after_inactivity(self):
        """AC2 — Après 30+ min d'inactivité, l'utilisateur est déconnecté."""
        self.client.force_login(self.user)

        # Première requête : initialise _last_activity
        self.client.get(self.home_url)

        # Simuler 31 min d'inactivité en manipulant la session
        session = self.client.session
        session["_last_activity"] = time.time() - 1860  # 31 minutes ago
        session.save()

        # La requête suivante doit déclencher la déconnexion
        response = self.client.get(self.home_url)
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)

    def test_session_renewed_on_activity(self):
        """L'activité remet le compteur d'inactivité à zéro."""
        self.client.force_login(self.user)

        # Première requête
        self.client.get(self.home_url)
        session = self.client.session
        first_activity = session.get("_last_activity")
        self.assertIsNotNone(first_activity)

        # Deuxième requête (simule une activité)
        self.client.get(self.home_url)
        session = self.client.session
        second_activity = session.get("_last_activity")

        # Le timestamp doit avoir été mis à jour
        self.assertGreaterEqual(second_activity, first_activity)

    def test_session_not_expired_within_timeout(self):
        """Un utilisateur actif dans les 30 min n'est pas déconnecté."""
        self.client.force_login(self.user)

        # Requête initiale
        self.client.get(self.home_url)

        # Simuler 25 min d'inactivité (dans la limite)
        session = self.client.session
        session["_last_activity"] = time.time() - 1500  # 25 minutes ago
        session.save()

        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

    def test_login_page_excluded_from_timeout(self):
        """Les routes publiques (/auth/login/) ne déclenchent pas le timeout."""
        self.client.force_login(self.user)

        # Simuler une session expirée
        session = self.client.session
        session["_last_activity"] = time.time() - 3600  # 1 heure
        session.save()

        # L'accès au login ne doit PAS déclencher la déconnexion
        response = self.client.get(self.login_url)
        self.assertNotEqual(response.status_code, 302)

    def test_anonymous_user_not_affected_by_timeout(self):
        """Un utilisateur anonyme n'est pas impacté par le middleware."""
        response = self.client.get(self.home_url)
        # Redirigé vers login par login_required, pas par le middleware timeout
        self.assertRedirects(
            response,
            f"{self.login_url}?next={self.home_url}",
        )

    def test_timeout_message_displayed(self):
        """Le message d'expiration est ajouté aux messages Django."""
        self.client.force_login(self.user)
        self.client.get(self.home_url)

        session = self.client.session
        session["_last_activity"] = time.time() - 1860
        session.save()

        response = self.client.get(self.home_url, follow=True)
        messages = list(response.context.get("messages", []))
        self.assertTrue(
            any("inactivité" in str(m) for m in messages),
            "Le message d'expiration doit contenir 'inactivité'.",
        )
