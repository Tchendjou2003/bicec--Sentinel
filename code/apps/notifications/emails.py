"""
Notifications App — Canal e-mail « alarme incendie » (Story 4.3)

Envoi asynchrone (Django-Q2) d'un e-mail multipart texte + HTML pour les seuls
types whitelistés dans ``settings.EMAIL_NOTIFICATION_TYPES``. Le canal entier
est gardé par ``settings.EMAIL_NOTIFICATIONS_ENABLED`` (False par défaut : la
prod reste muette tant que les SMTP BICEC ne sont pas configurés).

Contrainte on-premise : le HTML est autonome (CSS inline, polices système,
aucune image, aucune ressource distante). La partie texte brut sert de
fallback pour les clients mail qui bloquent le HTML.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_email_for_notification(notification_id) -> str:
    """Point d'entrée Django-Q2 : envoie l'e-mail d'une notification whitelistée.

    L'état est revérifié ici plutôt que de faire confiance au contexte
    d'enqueue : entre l'enqueue et l'exécution, le flag a pu changer, le compte
    a pu être désactivé, ou un rejeu de tâche peut viser une notification déjà
    servie. ``email_sent_at`` fait office de verrou d'idempotence.

    Le nom de cette fonction est sérialisé tel quel par Django-Q2 dans la table
    des tâches : ne pas la renommer sans migrer les tâches en vol.

    Returns:
        str: Un court libellé de résultat, visible dans l'admin Django-Q2.
    """
    from .models import Notification

    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return "skipped: channel disabled"

    try:
        notification = Notification.objects.select_related("recipient").get(
            pk=notification_id
        )
    except Notification.DoesNotExist:
        # Notification supprimée entre l'enqueue et l'exécution (réconciliation
        # nocturne, suppression manuelle) : plus rien à envoyer.
        return "skipped: notification deleted"

    if notification.notification_type not in settings.EMAIL_NOTIFICATION_TYPES:
        return "skipped: type not whitelisted"

    # Verrou d'idempotence atomique : on pose email_sent_at avant l'envoi SMTP
    # (UPDATE WHERE email_sent_at IS NULL) pour qu'un worker concurrent qui
    # lirait aussi NULL ne puisse pas passer la garde et envoyer un doublon.
    # Si aucune ligne n'est mise à jour (updated=0), un autre worker a déjà
    # réservé cet envoi — on s'arrête ici.
    from .models import Notification as _Notification  # évite import circulaire
    now = timezone.now()
    updated = _Notification.objects.filter(
        pk=notification.pk, email_sent_at__isnull=True
    ).update(email_sent_at=now)
    if updated == 0:
        return "skipped: already sent"
    # Rafraîchir l'instance locale pour que les templates aient l'état exact
    notification.email_sent_at = now

    recipient = notification.recipient
    # Garder le check APRÈS la réservation pour ne pas bloquer sur les comptes
    # sans adresse (le champ email_sent_at sert ici aussi de jeton d'occupation
    # mais un re-envoi est acceptable si l'adresse est ajoutée ultérieurement).
    if not recipient.is_active or not (recipient.email or "").strip():
        # Comptes bootstrap/historiques sans adresse : l'in-app a déjà porté
        # l'alerte, on trace le manque sans faire échouer la tâche.
        # On annule la réservation pour qu'un éventuel futur re-enqueue puisse retenter.
        _Notification.objects.filter(pk=notification.pk).update(email_sent_at=None)
        logger.info(
            "E-mail non envoyé pour la notification %s : destinataire %s "
            "inactif ou sans adresse e-mail.",
            notification.pk,
            recipient.pk,
        )
        return "skipped: recipient has no email"

    # Normaliser SITE_BASE_URL : supprimer le slash final éventuel pour éviter
    # les doubles slashes si notification.url commence par '/'.
    base_url = settings.SITE_BASE_URL.rstrip("/")
    absolute_url = f"{base_url}{notification.url}" if notification.url else ""

    context = {
        "notification": notification,
        "recipient": recipient,
        "absolute_url": absolute_url,
    }
    subject = f"{settings.EMAIL_SUBJECT_PREFIX}{notification.title}"
    text_body = render_to_string("notifications/email/alert.txt", context)
    html_body = render_to_string("notifications/email/alert.html", context)

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception:
        # L'échec SMTP ne doit jamais remonter au workflow : la notification
        # in-app existe déjà, l'e-mail n'est qu'un canal de renfort.
        # On réinitialise email_sent_at pour qu'un rejeu Django-Q2 puisse retenter.
        _Notification.objects.filter(pk=notification.pk).update(email_sent_at=None)
        logger.exception(
            "Échec d'envoi e-mail pour la notification %s (destinataire %s).",
            notification.pk,
            recipient.pk,
        )
        return "failed: smtp error (logged)"

    return "sent"


def enqueue_email_for_notification(notification) -> None:
    """Enqueue l'envoi e-mail d'une notification si le canal et le type le permettent.

    Appelé par ``emit_notification`` juste après la création. Toutes les gardes
    bloquantes (flag, whitelist) sont évaluées ici pour éviter d'encombrer la
    file Django-Q2 avec des tâches qui se skipperaient elles-mêmes ; la tâche
    les revérifie malgré tout à l'exécution.

    Une panne du broker ne doit jamais casser l'émission in-app : l'enqueue est
    enveloppé dans un try/except large avec log.
    """
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return
    if notification.notification_type not in settings.EMAIL_NOTIFICATION_TYPES:
        return

    notification_pk = notification.pk

    def _enqueue():
        """Enqueue réel, exécuté après le commit de la transaction courante.

        Sans ce différé, si emit_notification est appelé depuis un bloc
        transaction.atomic() (ex. service workflow), le worker Django-Q2
        peut démarrer avant que la ligne Notification soit visible en base,
        déclenchant un Notification.DoesNotExist silencieux.

        En tests : Django TestCase enveloppe chaque test dans une transaction
        qui ne commit jamais. Entourer l'appel avec
        ``TestCase.captureOnCommitCallbacks(execute=True)`` pour forcer
        l'exécution des callbacks on_commit sans avoir besoin de committer.
        """
        try:
            from django_q.tasks import async_task

            async_task(
                "apps.notifications.emails.send_email_for_notification",
                notification_pk,
            )
        except Exception:
            logger.exception(
                "Échec d'enqueue de l'e-mail pour la notification %s — "
                "la notification in-app reste servie.",
                notification_pk,
            )

    transaction.on_commit(_enqueue)
