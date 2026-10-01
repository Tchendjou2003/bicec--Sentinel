"""Tests du canal e-mail « alarme incendie » — Story 4.3.

Le settings de test force EMAIL_NOTIFICATIONS_ENABLED=True et le backend
locmem : les envois atterrissent dans django.core.mail.outbox, et Django-Q2
tourne en sync=True, donc la chaîne emit → enqueue → tâche → envoi s'exécute
entièrement dans le thread de test.

Note sur transaction.on_commit :
    enqueue_email_for_notification diffère l'enqueue via transaction.on_commit.
    Django TestCase enveloppe chaque test dans une transaction qui ne commit
    jamais. Il faut donc entourer chaque appel d'émission avec
    ``self.captureOnCommitCallbacks(execute=True)`` pour que le callback
    on_commit se déclenche dans le test.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings

from apps.notifications.emails import send_email_for_notification
from apps.notifications.models import Notification
from apps.notifications.services import emit_notification
from apps.users.models import User


class EmailChannelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="email_admin", password="TestPass123!",
            role=User.Role.AUDIT, is_audit_admin=True,
            email="admin@bicec.cm",
        )
        cls.no_email_user = User.objects.create_user(
            username="email_none", password="TestPass123!",
            role=User.Role.DM,
        )

    def _emit_tamper(self, recipient=None, key="TAMPER_DETECTED:rec-1"):
        """Émet un TAMPER_ALERT et exécute les callbacks on_commit immédiatement."""
        with self.captureOnCommitCallbacks(execute=True):
            notif = emit_notification(
                recipient=recipient or self.admin,
                notification_type=Notification.Type.TAMPER_ALERT,
                title="Altération détectée — REC-2026-001",
                idempotency_key=key,
                body="Le sceau HMAC de REC-2026-001 est invalide.",
                url="/audit/recommandations/42/",
                is_urgent=True,
            )
        return notif

    # ── AC1 + AC4 — whitelist et format multipart ─────────────────────────

    def test_tamper_alert_sends_multipart_email(self):
        """Un TAMPER_ALERT part par e-mail : sujet préfixé, texte + alternative HTML."""
        notif = self._emit_tamper()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertTrue(message.subject.startswith("[SENTINEL] "))
        self.assertIn("REC-2026-001", message.subject)
        self.assertIn("sceau HMAC", message.body)
        self.assertEqual(len(message.alternatives), 1)
        html_body, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("SENTINEL", html_body)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.email_sent_at)

    def test_html_contains_no_external_url(self):
        """Garde on-premise : la seule URL http du HTML est celle de SITE_BASE_URL."""
        self._emit_tamper()
        html_body = mail.outbox[0].alternatives[0][0]
        from django.conf import settings
        stripped = html_body.replace(settings.SITE_BASE_URL, "")
        self.assertNotIn("http://", stripped)
        self.assertNotIn("https://", stripped)

    def test_routine_type_sends_no_email(self):
        """DUE_SOON_J7 (routinier) reste in-app : aucun e-mail (doctrine alarme incendie)."""
        with self.captureOnCommitCallbacks(execute=True):
            emit_notification(
                recipient=self.admin,
                notification_type=Notification.Type.DUE_SOON_J7,
                title="Échéance dans 7 jours",
                idempotency_key="DUE_SOON_J7:rec-1",
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_assigned_sends_email(self):
        """ASSIGNED est whitelisté (décision 2026-07-16) : e-mail au destinataire."""
        with self.captureOnCommitCallbacks(execute=True):
            notif = emit_notification(
                recipient=self.admin,
                notification_type=Notification.Type.ASSIGNED,
                title="Recommandation assignée — REC-2026-002",
                idempotency_key="ASSIGNED:rec-2:1",
                url="/audit/recommandations/2/",
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("REC-2026-002", mail.outbox[0].subject)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.email_sent_at)

    def test_evidence_rejected_sends_email(self):
        """EVIDENCE_REJECTED est whitelisté (décision 2026-07-16) : e-mail au porteur."""
        with self.captureOnCommitCallbacks(execute=True):
            notif = emit_notification(
                recipient=self.admin,
                notification_type=Notification.Type.EVIDENCE_REJECTED,
                title="Preuves rejetées — REC-2026-003",
                idempotency_key="EVIDENCE_REJECTED:rec-3:sub-1",
                body="Motif : justificatif illisible, merci de re-soumettre.",
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Preuves rejetées", mail.outbox[0].subject)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.email_sent_at)

    def test_overdue_simple_sends_no_email(self):
        """OVERDUE simple est exclu de la whitelist (trop générique → spam)."""
        with self.captureOnCommitCallbacks(execute=True):
            emit_notification(
                recipient=self.admin,
                notification_type=Notification.Type.OVERDUE,
                title="Recommandation en retard",
                idempotency_key="OVERDUE:rec-1",
                is_urgent=True,
            )
        self.assertEqual(len(mail.outbox), 0)

    # ── AC2 — feature flag ────────────────────────────────────────────────

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_flag_off_sends_nothing(self):
        """Flag maître désactivé : la notification in-app existe, zéro e-mail."""
        with self.captureOnCommitCallbacks(execute=True):
            notif = self._emit_tamper(key="TAMPER_DETECTED:rec-flag-off")
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 0)
        notif.refresh_from_db()
        self.assertIsNone(notif.email_sent_at)

    # ── AC5 — idempotence d'envoi ─────────────────────────────────────────

    def test_replayed_task_sends_no_duplicate(self):
        """Une tâche rejouée sur une notification déjà servie n'envoie rien."""
        notif = self._emit_tamper(key="TAMPER_DETECTED:rec-replay")
        self.assertEqual(len(mail.outbox), 1)
        result = send_email_for_notification(notif.pk)
        self.assertEqual(result, "skipped: already sent")
        self.assertEqual(len(mail.outbox), 1)

    # ── AC6 — destinataire sans adresse ───────────────────────────────────

    def test_recipient_without_email_is_skipped(self):
        """Compte sans adresse : skip loggé, pas d'exception, pas d'e-mail."""
        notif = self._emit_tamper(
            recipient=self.no_email_user, key="TAMPER_DETECTED:rec-noemail",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 0)
        notif.refresh_from_db()
        self.assertIsNone(notif.email_sent_at)

    # ── AC3 — l'échec SMTP ne remonte jamais ──────────────────────────────

    def test_smtp_failure_does_not_break_emit(self):
        """Un backend SMTP en panne laisse la notification in-app intacte."""
        with patch(
            "apps.notifications.emails.EmailMultiAlternatives.send",
            side_effect=OSError("SMTP down"),
        ):
            notif = self._emit_tamper(key="TAMPER_DETECTED:rec-smtp-down")
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 0)
        notif.refresh_from_db()
        # email_sent_at est réinitialisé à None après échec SMTP pour permettre le rejeu.
        self.assertIsNone(notif.email_sent_at)
        self.assertEqual(
            Notification.objects.filter(
                idempotency_key="TAMPER_DETECTED:rec-smtp-down"
            ).count(),
            1,
        )

    # ── AC7 — SYSTEM_ALERT réel pour l'échec du cron ──────────────────────

    def test_cron_failure_alert_uses_system_alert_type(self):
        """_alert_cron_failure bascule sur SYSTEM_ALERT maintenant que le type existe."""
        from apps.workflow.services import _alert_cron_failure

        with self.captureOnCommitCallbacks(execute=True):
            _alert_cron_failure(["overdue"], {"overdue": {"error": "boom"}})
        notif = Notification.objects.filter(recipient=self.admin).latest("created_at")
        self.assertEqual(notif.notification_type, Notification.Type.SYSTEM_ALERT)
        # SYSTEM_ALERT est whitelisté : l'alerte cron part aussi par e-mail.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Alerte cron", mail.outbox[0].subject)

    # ── Fix: garde adresse e-mail avec espaces ────────────────────────────────

    def test_whitespace_email_is_skipped(self):
        """Adresse e-mail composée uniquement d'espaces : skip loggé, aucun envoi."""
        whitespace_user = User.objects.create_user(
            username="email_whitespace", password="TestPass123!",
            role=User.Role.DM,
            email="   ",  # non vide mais seulement des espaces
        )
        notif = self._emit_tamper(
            recipient=whitespace_user, key="TAMPER_DETECTED:rec-whitespace",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 0)
        notif.refresh_from_db()
        self.assertIsNone(notif.email_sent_at)

    # ── Fix: normalisation du slash de SITE_BASE_URL ──────────────────────────

    @override_settings(SITE_BASE_URL="http://localhost:8000/")
    def test_trailing_slash_base_url_no_double_slash(self):
        """SITE_BASE_URL avec slash final ne produit pas de double slash dans l'URL du bouton."""
        self._emit_tamper(key="TAMPER_DETECTED:rec-trailingslash")
        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0][0]
        # L'URL cible est /audit/recommandations/42/ : on ne doit pas voir //audit
        self.assertNotIn("//audit", html_body)
        self.assertIn("/audit/recommandations/42/", html_body)

    # ── Fix: transaction.on_commit ─────────────────────────────────────────
    # NOTE : ce test est dans TransactionTestCase ci-dessous pour qu'
    # on_commit se déclenche réellement (TestCase ne commit jamais).
    # Voir OnCommitEnqueueTest.


class OnCommitEnqueueTest(TransactionTestCase):
    """Valide que l'enqueue e-mail est différé au commit quand on est dans
    un bloc atomique, et qu'un rollback empêche bien l'envoi.

    Doit être un TransactionTestCase car Django.TestCase enveloppe chaque
    test dans une transaction qui ne commit jamais — on_commit ne se
    déclencherait pas avec un TestCase ordinaire.
    """

    def test_email_not_sent_on_rollback(self):
        """L'envoi e-mail est inhibé lorsque la transaction extérieure est rollbackée."""
        from django.db import transaction as db_transaction

        admin = User.objects.create_user(
            username="txn_admin", password="TestPass123!",
            role=User.Role.AUDIT, is_audit_admin=True,
            email="txnadmin@bicec.cm",
        )
        try:
            with db_transaction.atomic():
                emit_notification(
                    recipient=admin,
                    notification_type=Notification.Type.TAMPER_ALERT,
                    title="Alteration test txn",
                    idempotency_key="TAMPER_DETECTED:txn-rollback",
                    url="/audit/recommandations/1/",
                    is_urgent=True,
                )
                # Provoquer un rollback : ni la notification ni l'e-mail
                # ne doivent persister.
                raise ValueError("force rollback")
        except ValueError:
            pass

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            Notification.objects.filter(
                idempotency_key="TAMPER_DETECTED:txn-rollback"
            ).exists()
        )
