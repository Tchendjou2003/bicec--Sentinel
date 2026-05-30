"""
Notifications App — Vues (Story 4.0)

Trois endpoints HTMX :
  - NotificationDropdownView  : GET  → partial HTML du dropdown (lazy)
  - NotificationMarkReadView  : POST → marque une notif comme lue
  - NotificationMarkAllReadView: POST → marque toutes comme lues
"""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import ListView

from .models import Notification

# Nombre de notifications affichées dans le dropdown
DROPDOWN_LIMIT = 10


class NotificationDropdownView(LoginRequiredMixin, View):
    """
    GET /notifications/dropdown/ → partial HTMX du dropdown.

    Chargé en lazy (hx-trigger="click once") → aucune requête au
    chargement de page. Renvoie les 10 dernières notifications (AC2).
    """

    def get(self, request):
        notifications = (
            Notification.objects.filter(recipient=request.user)
            .select_related("recommendation")
            .order_by("-created_at")[:DROPDOWN_LIMIT]
        )
        html = render_to_string(
            "notifications/partials/notification_dropdown.html",
            {
                "notifications": notifications,
                "unread_count": Notification.objects.filter(
                    recipient=request.user, is_read=False
                ).count(),
            },
            request=request,
        )
        return HttpResponse(html)


class NotificationListView(LoginRequiredMixin, ListView):
    """
    GET /notifications/ → Page dédiée affichant l'historique complet.
    
    Pagination élégante et vue exhaustive des notifications.
    """
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related("recommendation")
        
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
            
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = Notification.objects.filter(
            recipient=self.request.user, is_read=False
        ).count()
        context["search_query"] = self.request.GET.get("q", "")
        context["topbar_title"] = "SENTINEL"
        context["topbar_subtitle"] = "Notifications"
        return context


class NotificationMarkReadView(LoginRequiredMixin, View):
    """
    POST /notifications/{pk}/mark-read/ → marque comme lue + redirige (AC3).

    Sécurité (AC6) : l'utilisateur ne peut agir que sur ses propres notifications.
    Renvoie HX-Redirect vers l'URL de la notification.
    """

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            raise Http404

        notif.is_read = True
        notif.save(update_fields=["is_read"])

        # Rafraîchit le badge via OOB et redirige vers l'URL de destination.
        redirect_url = notif.url or "/"
        response = HttpResponse(status=204)
        response["HX-Redirect"] = redirect_url
        response["HX-Trigger"] = json.dumps({"badge-refresh": True})
        return response


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """
    POST /notifications/mark-all-read/ → marque toutes les notifs comme lues (AC3).

    Renvoie le dropdown mis à jour + déclenche le refresh du badge via HX-Trigger.
    """

    def post(self, request):
        Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)

        # Re-rend le dropdown (maintenant tout lu) + refreshe le badge.
        notifications = (
            Notification.objects.filter(recipient=request.user)
            .select_related("recommendation")
            .order_by("-created_at")[:DROPDOWN_LIMIT]
        )
        html = render_to_string(
            "notifications/partials/notification_dropdown.html",
            {"notifications": notifications, "unread_count": 0},
            request=request,
        )
        response = HttpResponse(html)
        response["HX-Trigger"] = json.dumps({"badge-refresh": True})
        return response


class NotificationDeleteView(LoginRequiredMixin, View):
    """
    POST /notifications/{pk}/delete/ → Supprime la notification de l'historique.
    
    Retourne un 200 vide pour que HTMX retire l'élément du DOM fluide.
    """

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
            notif.delete()
        except Notification.DoesNotExist:
            raise Http404

        # Refresh the badge since we might have deleted an unread notification
        response = HttpResponse("")
        response["HX-Trigger"] = json.dumps({"badge-refresh": True})
        return response

