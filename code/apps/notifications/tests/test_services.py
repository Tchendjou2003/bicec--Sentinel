"""Tests du service emit_notification — Story 4.0 (AC4)."""
from django.test import TestCase

from apps.notifications.models import Notification
from apps.notifications.services import emit_notification
from apps.users.models import User


class EmitNotificationServiceTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="notif_user", password="TestPass123!", role=User.Role.DM,
        )
        cls.other = User.objects.create_user(
            username="notif_other", password="TestPass123!", role=User.Role.AUDIT,
        )

    def _emit(self, key="test:key", **kwargs):
        defaults = dict(
            recipient=self.user,
            notification_type=Notification.Type.ASSIGNED,
            title="Test notification",
            idempotency_key=key,
        )
        defaults.update(kwargs)
        return emit_notification(**defaults)

    def test_emit_creates_notification(self):
        """Un premier appel crée la notification."""
        notif = self._emit()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "Test notification")
        self.assertEqual(notif.recipient, self.user)
        self.assertFalse(notif.is_read)

    def test_emit_idempotent_returns_none(self):
        """AC4 — le 2ᵉ appel avec la même clé retourne None (pas de doublon)."""
        self._emit(key="unique:reco:42")
        result = self._emit(key="unique:reco:42")
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.filter(idempotency_key="unique:reco:42").count(), 1)

    def test_emit_urgent_flag_preserved(self):
        """is_urgent=True est bien conservé sur la notification créée."""
        notif = self._emit(
            key="overdue:reco:42",
            notification_type=Notification.Type.OVERDUE,
            is_urgent=True,
        )
        self.assertTrue(notif.is_urgent)

    def test_emit_normal_not_urgent_by_default(self):
        """is_urgent=False par défaut pour les événements workflow."""
        notif = self._emit(key="assigned:reco:1")
        self.assertFalse(notif.is_urgent)

    def test_emit_different_keys_create_separate_notifications(self):
        """Deux clés différentes → deux notifications distinctes."""
        self._emit(key="key:a")
        self._emit(key="key:b")
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 2)

    def test_emit_same_key_different_recipient_creates_notification(self):
        """Scénario délégation (revue PR #15 — ISSUE-016) : la même clé pour un
        AUTRE destinataire crée bien une nouvelle notification — la notif de
        l'ancien porteur ne bloque plus celle du nouveau."""
        first = self._emit(key="DUE_SOON_J7:reco-1")                      # ancien porteur
        second = self._emit(key="DUE_SOON_J7:reco-1", recipient=self.other)  # nouveau porteur
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(
            Notification.objects.filter(idempotency_key="DUE_SOON_J7:reco-1").count(), 2
        )
        # L'idempotence par destinataire reste garantie
        self.assertIsNone(self._emit(key="DUE_SOON_J7:reco-1", recipient=self.other))
