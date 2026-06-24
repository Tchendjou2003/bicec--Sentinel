from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.users.mixins import AuditRequiredMixin, WorkflowAccessMixin
from apps.users.models import ExternalMission, User
from apps.workflow.models import Recommendation

from .forms_missions import ExternalMissionForm
from . import services_export
from . import services_missions


def _client_ip(request):
    """IP réelle derrière le reverse proxy (X-Forwarded-For), sinon REMOTE_ADDR."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ExternalPortalZipExportView(WorkflowAccessMixin, View):
    """
    Exporte en ZIP l'ensemble des preuves des missions actives de l'auditeur externe.
    Réservé au rôle EXT uniquement.
    """
    def get(self, request, *args, **kwargs):
        if request.user.role != User.Role.EXT:
            from django.http import Http404
            raise Http404
        try:
            zip_buffer, filename = services_export.generate_mission_evidence_zip(user=request.user)
        except ValueError:
            from django.shortcuts import redirect
            return redirect("workflow:external-waiting")
        response = FileResponse(zip_buffer, as_attachment=True, filename=filename)
        return response


class RecommendationZipExportView(WorkflowAccessMixin, View):
    """
    Exporte en ZIP l'ensemble des preuves d'une recommandation spécifique.
    Accessible aux acteurs du workflow (AUDIT, DM, ETP, EXT).
    """
    def get(self, request, pk, *args, **kwargs):
        from . import selectors
        # On passe par le sélecteur avec contrôle RBAC
        reco = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        zip_buffer, filename = services_export.generate_single_recommendation_zip(user=request.user, reco=reco)
        response = FileResponse(zip_buffer, as_attachment=True, filename=filename)
        return response


class ExternalWaitingView(WorkflowAccessMixin, TemplateView):
    """
    Page d'attente pour les auditeurs externes n'ayant aucune mission active.
    """
    template_name = "workflow/external_waiting.html"


class ExternalMissionListView(AuditRequiredMixin, ListView):
    """
    Vue liste des missions externes (Audit Interne).
    """
    model = ExternalMission
    template_name = "workflow/missions_list.html"
    context_object_name = "missions"
    paginate_by = 20

    def get_queryset(self):
        qs = ExternalMission.objects.prefetch_related("auditors", "recommendations")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(organisation__label__icontains=q) |
                Q(organisation__code__icontains=q)
            )
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)

        return qs.order_by("-start_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_route"] = "missions"
        ctx["topbar_title"] = "Missions Externes"
        ctx["topbar_subtitle"] = "Gestion des audits externes (COBAC, CAC, etc.)"
        ctx["q"] = self.request.GET.get("q", "")
        ctx["status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = ExternalMission.Status.choices
        return ctx


class ExternalMissionCreateView(AuditRequiredMixin, View):
    """
    Création d'une mission (Slide-over HTMX).
    """
    def get(self, request):
        form = ExternalMissionForm()
        return render(request, "workflow/partials/mission_form.html", {
            "form": form,
            "action_url": reverse("workflow:mission-create"),
            "title": "Nouvelle Mission Externe",
        })

    def post(self, request):
        form = ExternalMissionForm(request.POST)
        if form.is_valid():
            mission = services_missions.create_mission(
                form=form,
                created_by=request.user,
                ip_address=_client_ip(request),
            )
            messages.success(request, f"La mission '{mission.name}' a été créée.")
            response = HttpResponse()
            response["HX-Redirect"] = reverse("workflow:mission-list")
            return response

        return render(request, "workflow/partials/mission_form.html", {
            "form": form,
            "action_url": reverse("workflow:mission-create"),
            "title": "Nouvelle Mission Externe",
        })


class ExternalMissionUpdateView(AuditRequiredMixin, View):
    """
    Modification d'une mission (Slide-over HTMX).
    """
    def get(self, request, pk):
        mission = get_object_or_404(ExternalMission, pk=pk)
        form = ExternalMissionForm(instance=mission)
        return render(request, "workflow/partials/mission_form.html", {
            "form": form,
            "action_url": reverse("workflow:mission-update", args=[pk]),
            "title": f"Modifier : {mission.name}",
        })

    def post(self, request, pk):
        mission = get_object_or_404(ExternalMission, pk=pk)
        form = ExternalMissionForm(request.POST, instance=mission)
        if form.is_valid():
            services_missions.update_mission(
                mission=mission,
                form=form,
                performed_by=request.user,
                ip_address=_client_ip(request),
            )
            messages.success(request, f"La mission '{mission.name}' a été mise à jour.")
            response = HttpResponse()
            response["HX-Redirect"] = reverse("workflow:mission-list")
            return response

        return render(request, "workflow/partials/mission_form.html", {
            "form": form,
            "action_url": reverse("workflow:mission-update", args=[pk]),
            "title": f"Modifier : {mission.name}",
        })


class ExternalMissionToggleStatusView(AuditRequiredMixin, View):
    """
    Bascule le statut d'une mission (PREPARATION -> ACTIVE -> CLOSED).
    """
    def post(self, request, pk):
        mission = get_object_or_404(ExternalMission, pk=pk)
        new_status = request.POST.get("status")

        try:
            mission = services_missions.toggle_mission_status(
                mission=mission,
                new_status=new_status,
                performed_by=request.user,
                ip_address=_client_ip(request),
            )
            messages.success(request, f"Statut modifié : {mission.get_status_display()}")
        except ValueError as exc:
            messages.error(request, str(exc))

        response = HttpResponse()
        response["HX-Redirect"] = reverse("workflow:mission-list")
        return response
