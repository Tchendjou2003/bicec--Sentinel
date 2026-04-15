"""
Smoke tests — Story 1.1 non-regression
"""
from django.test import TestCase, Client


class HomePageSmokeTest(TestCase):
    """AC-3: Page d'accueil Django accessible."""

    def setUp(self):
        self.client = Client()

    def test_home_page_returns_200(self):
        """La page d'accueil renvoie un statut 200."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_page_uses_correct_template(self):
        """La page d'accueil utilise le template home.html."""
        response = self.client.get("/")
        self.assertTemplateUsed(response, "home.html")

    def test_home_page_contains_sentinel_title(self):
        """La page d'accueil contient le titre Sentinel."""
        response = self.client.get("/")
        self.assertContains(response, "Sentinel")

    def test_htmx_test_endpoint_returns_fragment(self):
        """AC-5: Le endpoint htmx-test renvoie un fragment HTML."""
        response = self.client.get("/htmx-test/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HTMX fonctionne")

    def test_security_headers_present(self):
        """AC-3: X-Frame-Options est présent."""
        response = self.client.get("/")
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
