"""
Notifications App — Context Processor (Story 4.0)

Injecte ``unread_notifications_count`` dans tous les templates.
Requête COUNT légère (index sur recipient+is_read, < 1 ms).
"""
from .models import Notification


def notifications_context(request):
    """
    Injecte le nombre de notifications non-lues de l'utilisateur courant.

    Retourne 0 si non authentifié (pas de requête DB).
    Calqué sur ``apps.users.context_processors.sidebar_context``.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return {"unread_notifications_count": count}
