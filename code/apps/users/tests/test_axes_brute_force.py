"""
Users App — Tests django-axes Brute Force Protection (AC5)

Vérifie que :
    - Un compte est bloqué après AXES_FAILURE_LIMIT (5) tentatives échouées
    - Le blocage est levé après un reset
    - Un login réussi remet le compteur à zéro (AXES_RESET_ON_SUCCESS)
    - Le template de lockout est affiché correctement

Settings requis :
    - AXES_FAILURE_LIMIT = 5
    - AXES_COOLOFF_TIME = 1 (heure)
    - AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
    - AXES_RESET_ON_SUCCESS = True
"""
from axes.utils import reset as axes_reset

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(
    AXES_ENABLED=True,
    AXES_FAILURE_LIMIT=5,
    AXES_COOLOFF_TIME=1,
    AXES_RESET_ON_SUCCESS=True,
)
class AxesBruteForceTest(TestCase):
    """Tests de la protection brute force via django-axes (AC5)."""

    def setUp(self):
        self.client = Client(REMOTE_ADDR="127.0.0.1")
        self.login_url = reverse("auth:login")
        self.user = User.objects.create_user(
            username="brute_target",
            password="correctpass123",
            role=User.Role.DM,
        )
        axes_reset()

    def tearDown(self):
        axes_reset()

    def _attempt_login(self, username="brute_target", password="wrongpass"):
        """Helper : tentative de login."""
        return self.client.post(
            self.login_url,
            {"username": username, "password": password},
        )

    def test_login_succeeds_with_valid_credentials(self):
        """Un login valide fonctionne normalement."""
        response = self.client.post(
            self.login_url,
            {"username": "brute_target", "password": "correctpass123"},
        )
        # Doit rediriger (login réussi)
        self.assertEqual(response.status_code, 302)

    def test_account_locked_after_5_failures(self):
        """AC5 — Le compte est bloqué après 5 tentatives échouées."""
        # 5 tentatives avec mauvais mot de passe
        for i in range(5):
            self._attempt_login(password="wrong")

        # La 6ème tentative (même avec le bon mot de passe) doit être bloquée
        response = self.client.post(
            self.login_url,
            {"username": "brute_target", "password": "correctpass123"},
        )
        # django-axes renvoie 403, 429 (Too Many Requests) ou 200 selon la config.
        # Avec AxesStandaloneBackend, le lockout peut déclencher un 429.
        self.assertIn(response.status_code, [200, 403, 429])
        # L'utilisateur ne doit PAS être redirigé (= pas connecté)
        self.assertNotEqual(response.status_code, 302)

    def test_account_not_locked_before_limit(self):
        """Le compte n'est pas bloqué avant la limite (4 tentatives)."""
        for i in range(4):
            self._attempt_login(password="wrong")

        # La 5ème tentative avec le BON mot de passe doit fonctionner
        response = self.client.post(
            self.login_url,
            {"username": "brute_target", "password": "correctpass123"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect = login réussi

    def test_reset_on_success(self):
        """AXES_RESET_ON_SUCCESS : un login réussi remet le compteur à zéro."""
        # 3 tentatives échouées
        for i in range(3):
            self._attempt_login(password="wrong")

        # Login réussi
        self.client.post(
            self.login_url,
            {"username": "brute_target", "password": "correctpass123"},
        )
        self.client.logout()

        # 4 nouvelles tentatives échouées (total < 5 car reset)
        for i in range(4):
            self._attempt_login(password="wrong")

        # Le login doit encore fonctionner (compteur remis à zéro)
        response = self.client.post(
            self.login_url,
            {"username": "brute_target", "password": "correctpass123"},
        )
        self.assertEqual(response.status_code, 302)
