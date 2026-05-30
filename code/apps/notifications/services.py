"""
Notifications App — Services (Story 4.0)

Point d'entrée unique pour créer une notification in-app : ``emit_notification()``.
Idempotent par construction (get_or_create sur idempotency_key).
"""
from __future__ import annotations

from .models import Notification


def emit_notification(
    *,
    recipient,
    notification_type: str,
    title: str,
    idempotency_key: str,
    recommendation=None,
    body: str = "",
    url: str = "",
    is_urgent: bool = False,
) -> "Notification | None":
    """
    Émet une notification in-app idempotente (Story 4.0 / AC4).

    Si une notification avec la même ``idempotency_key`` existe déjà,
    **aucune** nouvelle entrée n'est créée et la fonction retourne ``None``.
    Cela garantit qu'un même événement n'est jamais notifié deux fois,
    même en cas d'appels répétés ou de race condition légère.

    Convention des clés (documentée en artifact 4.0) :
      - Événement workflow : ``"{TYPE}:{recommendation_pk}:{extra}"``
        ex. ``"ASSIGNED:{rec_pk}:{dm_pk}"``
      - Rupture/anticipation : ``"{TYPE}:{recommendation_pk}"``
        ex. ``"OVERDUE_J30:{rec_pk}"``

    Args:
        recipient: L'utilisateur destinataire.
        notification_type: Une valeur de ``Notification.Type``.
        title: Texte court affiché dans le dropdown.
        idempotency_key: Clé unique de l'événement (voir convention ci-dessus).
        recommendation: La recommandation liée (nullable).
        body: Précision facultative (motif, contexte…).
        url: URL relative de destination au clic.
        is_urgent: True pour ruptures et escalades (affichage prioritaire).

    Returns:
        La ``Notification`` créée, ou ``None`` si déjà existante.
    """
    notif, created = Notification.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "recipient": recipient,
            "notification_type": notification_type,
            "recommendation": recommendation,
            "title": title,
            "body": body,
            "url": url,
            "is_urgent": is_urgent,
        },
    )
    return notif if created else None


def _reco_url(recommendation) -> str:
    """Helper interne pour générer l'URL de destination d'une reco."""
    if not recommendation:
        return ""
    return f"/audit/recommandations/{recommendation.pk}/"


def notify_porteur(recommendation, *, type, title, actor, is_urgent=False, body="", key: str):
    """
    Notifie le porteur actuel (ETP si assigné, sinon DM).
    Skip si le porteur est lui-même l'acteur de l'événement.
    """
    recipient = recommendation.assigned_etp or recommendation.assigned_dm
    if not recipient or recipient == actor:
        return None
        
    return emit_notification(
        recipient=recipient,
        notification_type=type,
        title=title,
        idempotency_key=key,
        recommendation=recommendation,
        body=body,
        url=_reco_url(recommendation),
        is_urgent=is_urgent,
    )


def notify_dm(recommendation, *, type, title, actor, is_urgent=False, body="", key: str):
    """
    Notifie spécifiquement le Directeur Métier (DM).
    Skip si le DM est lui-même l'acteur de l'événement.
    """
    recipient = recommendation.assigned_dm
    if not recipient or recipient == actor:
        return None
        
    return emit_notification(
        recipient=recipient,
        notification_type=type,
        title=title,
        idempotency_key=key,
        recommendation=recommendation,
        body=body,
        url=_reco_url(recommendation),
        is_urgent=is_urgent,
    )


def notify_audit_owner(recommendation, *, type, title, actor, key: str, body="", is_urgent=False):
    """
    Notifie l'Auditeur propriétaire (created_by).
    Skip si l'auditeur est lui-même l'acteur de l'événement.
    """
    recipient = recommendation.created_by
    if not recipient or recipient == actor:
        return None
        
    return emit_notification(
        recipient=recipient,
        notification_type=type,
        title=title,
        idempotency_key=key,
        recommendation=recommendation,
        body=body,
        url=_reco_url(recommendation),
        is_urgent=is_urgent,
    )
