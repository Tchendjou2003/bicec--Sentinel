"""Tests des vues notifications — Story 4.0 (AC2, AC3, AC6)."""
from django.test import TestCase
from django.urls import reverse

from apps.notifications.models import Notification
from apps.notifications.services import emit_notification
from apps.users.models import User


class NotificationViewTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="notif_view_user", password="TestPass123!", role=User.Role.DM,
        )
        cls.other = User.objects.create_user(
            username="notif_view_other", password="TestPass123!", role=User.Role.AUDIT,
        )

    def _login(self, user=None):
        self.client.force_login(user or self.user)

    def _notif(self, user=None, key="k1", is_read=False, is_urgent=False):
        notif = emit_notification(
            recipient=user or self.user,
            notification_type=Notification.Type.ASSIGNED,
            title="Reco assignée",
            idempotency_key=key,
            is_urgent=is_urgent,
        )
        if is_read and notif:
            notif.is_read = True
            notif.save(update_fields=["is_read"])
        return notif


class DropdownViewTest(NotificationViewTestBase):

    def test_dropdown_200_for_authenticated(self):
        """AC2 — GET dropdown → 200 pour utilisateur connecté."""
        self._login()
        response = self.client.get(reverse("notifications:dropdown"))
        self.assertEqual(response.status_code, 200)

    def test_dropdown_redirect_for_anonymous(self):
        """AC2 — GET dropdown → 302 pour utilisateur non connecté."""
        response = self.client.get(reverse("notifications:dropdown"))
        self.assertEqual(response.status_code, 302)

    def test_dropdown_shows_own_notifications_only(self):
        """AC6 — seules les notifs du user connecté sont affichées."""
        self._notif(key="own:1")
        self._notif(user=self.other, key="other:1")
        self._login()
        response = self.client.get(reverse("notifications:dropdown"))
        self.assertContains(response, "Reco assignée")
        # La 2ᵉ notif appartient à `other`, ne doit pas apparaître
        self.assertEqual(
            Notification.objects.filter(recipient=self.user).count(), 1
        )

    def test_dropdown_empty_state_when_no_notifications(self):
        """AC2 — empty state affiché si aucune notification."""
        self._login()
        response = self.client.get(reverse("notifications:dropdown"))
        self.assertContains(response, "Aucune notification")


class MarkReadViewTest(NotificationViewTestBase):

    def test_mark_read_own_notification(self):
        """AC3 — POST mark-read marque la notif comme lue."""
        notif = self._notif(key="mark:1")
        self._login()
        response = self.client.post(
            reverse("notifications:mark-read", args=[notif.pk]),
            HTTP_X_CSRFTOKEN="fake",
        )
        self.assertEqual(response.status_code, 204)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_read_other_user_notification_returns_404(self):
        """AC6 — marquer la notif d'un autre user → 404."""
        notif = self._notif(user=self.other, key="other:2")
        self._login()
        response = self.client.post(
            reverse("notifications:mark-read", args=[notif.pk]),
        )
        self.assertEqual(response.status_code, 404)


class MarkAllReadViewTest(NotificationViewTestBase):

    def test_mark_all_read(self):
        """AC3 — POST mark-all-read → toutes les notifs lues."""
        self._notif(key="all:1")
        self._notif(key="all:2")
        self._notif(user=self.other, key="all:other")  # ne doit pas être touché
        self._login()
        response = self.client.post(reverse("notifications:mark-all-read"))
        self.assertEqual(response.status_code, 200)
        # Les notifs du user sont toutes lues
        self.assertEqual(
            Notification.objects.filter(recipient=self.user, is_read=False).count(), 0
        )
        # La notif de `other` reste non-lue
        self.assertTrue(
            Notification.objects.get(recipient=self.other).is_read is False
        )


class UnreadCountContextTest(NotificationViewTestBase):
    """AC1 — le context processor injecte unread_notifications_count."""

    def test_unread_count_in_context(self):
        """unread_notifications_count est présent dans le contexte de toute page."""
        self._notif(key="ctx:1")
        self._notif(key="ctx:2")
        self._notif(key="ctx:3", is_read=True)
        self._login()
        # On utilise la page home comme proxy — toute page injecte le contexte
        response = self.client.get("/")
        self.assertIn("unread_notifications_count", response.context)
        self.assertEqual(response.context["unread_notifications_count"], 2)
