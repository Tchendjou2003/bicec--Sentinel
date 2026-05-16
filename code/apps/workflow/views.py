"""
Workflow App — Views (Convention HackSoft)

Vues pour le CRUD des recommandations et la navigation.

Spécifications couvertes :
    - AC1  : Stepper slide-over pour la création
    - AC2  : Tableau épuré avec filtres HTMX
    - AC4  : Actions contextuelles (menu ⋯)
    - AC5  : Soft Delete via HTMX
    - AC7  : RBAC — accès réservé aux Auditeurs
    - AC8  : Page Centre de Contrôle
    - AC9  : Modification via stepper prérempli
"""
import json

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView

from apps.users.mixins import AuditRequiredMixin

from . import selectors, services
from .forms import AssignDMForm, DeliverableFormSet, RecommendationForm
from .models import Recommendation


def _get_client_ip(request) -> str | None:
    """Extrait l'adresse IP du client depuis les headers."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# =============================================================================
# Liste des recommandations (AC2, AC3)
# =============================================================================


class RecommendationListView(AuditRequiredMixin, ListView):
    """
    Vue liste — Tableau épuré avec filtres HTMX.

    Affiche toutes les recommandations (non-supprimées) avec
    des filtres horizontaux compacts pour Source, Statut, Criticité
    et une recherche textuelle.
    """

    template_name = "workflow/recommendation_list.html"
    context_object_name = "recommendations"
    paginate_by = 25

    def get_queryset(self):
        filters = {
            "source": self.request.GET.get("source"),
            "status": self.request.GET.get("status"),
            "priority": self.request.GET.get("priority"),
            "q": self.request.GET.get("q"),
        }
        return selectors.get_recommendations_for_audit(user=self.request.user, filters=filters)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "recommandations"
        context["topbar_title"] = "Recommandations"
        context["topbar_subtitle"] = "Suivi des recommandations d'audit"
        # Pour les filtres
        context["sources"] = Recommendation.Source.choices
        context["statuses"] = Recommendation.Status.choices
        context["priorities"] = Recommendation.Priority.choices
        # Filtres actuels
        context["current_source"] = self.request.GET.get("source", "")
        context["current_status"] = self.request.GET.get("status", "")
        context["current_priority"] = self.request.GET.get("priority", "")
        context["current_search"] = self.request.GET.get("q", "")
        return context

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["workflow/partials/recommendation_table.html"]
        return [self.template_name]


# =============================================================================
# Création via Stepper (AC1)
# =============================================================================


class RecommendationCreateView(AuditRequiredMixin, View):
    """
    Vue de création — Stepper en slide-over.

    GET  : Retourne le partial du stepper (HTMX hx-get).
    POST : Crée la recommandation + livrables de manière atomique.
    """

    def get(self, request):
        form = RecommendationForm()
        formset = DeliverableFormSet()
        return HttpResponse(
            _render_stepper(request, form, formset),
        )

    def post(self, request):
        form = RecommendationForm(request.POST)
        formset = DeliverableFormSet(request.POST)

        if form.is_valid():
            # Extraire les labels de livrables depuis le formset
            deliverables_data = []
            if formset.is_valid():
                for f in formset.forms:
                    label = f.cleaned_data.get("label", "").strip()
                    if label and not f.cleaned_data.get("DELETE", False):
                        deliverables_data.append(label)

            recommendation = services.create_recommendation(
                data=form.cleaned_data,
                deliverables_data=deliverables_data,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )

            # Réponse HTMX avec toast de succès
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"Recommandation {recommendation.reference} créée avec succès",
                    "type": "success",
                },
                "closeSlideOver": True,
                "refreshTable": True,
            })
            return response

        # Formulaire invalide — re-render le stepper avec erreurs
        return HttpResponse(
            _render_stepper(request, form, formset),
            status=422,
        )


class RecommendationUpdateView(AuditRequiredMixin, View):
    """
    Vue de modification — Stepper en slide-over.

    GET  : Retourne le partial du stepper prérempli (HTMX hx-get).
    POST : Modifie la recommandation + livrables de manière atomique.
    """

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        if recommendation.status != "DRAFT":
            return HttpResponseForbidden()

        form = RecommendationForm(instance=recommendation)
        formset = DeliverableFormSet(instance=recommendation)
        return HttpResponse(
            _render_stepper(request, form, formset),
        )

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        if recommendation.status != "DRAFT":
            return HttpResponseForbidden()

        form = RecommendationForm(request.POST, instance=recommendation)
        formset = DeliverableFormSet(request.POST, instance=recommendation)

        if form.is_valid() and formset.is_valid():
            recommendation = services.update_recommendation(
                recommendation=recommendation,
                data=form.cleaned_data,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
                formset=formset,
            )

            # Réponse HTMX avec toast de succès
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"Recommandation {recommendation.reference} modifiée avec succès",
                    "type": "success",
                },
                "closeSlideOver": True,
                "refreshTable": True,
            })
            return response

        # Formulaire invalide — re-render le stepper avec erreurs
        return HttpResponse(
            _render_stepper(request, form, formset),
            status=422,
        )


def _render_stepper(request, form, formset):
    """Render le template stepper slide-over."""
    from django.template.loader import render_to_string
    is_update = not form.instance._state.adding
    return render_to_string(
        "workflow/partials/stepper_slideover.html",
        {"form": form, "formset": formset, "is_update": is_update},
        request=request,
    )


# =============================================================================
# Détail / Centre de Contrôle (AC8)
# =============================================================================


class RecommendationDetailView(AuditRequiredMixin, DetailView):
    """
    Vue détail — Centre de Contrôle split 60/40.

    Affiche la recommandation complète avec ses livrables,
    la barre d'avancement et la timeline AuditLog.
    """

    template_name = "workflow/recommendation_detail.html"
    context_object_name = "recommendation"

    def get_object(self, queryset=None):
        return selectors.get_recommendation_detail(pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rec = self.object
        context["active_route"] = "recommandations"
        context["topbar_title"] = f"Recommandation {rec.reference}"
        context["topbar_subtitle"] = rec.mission_label or "Détail"

        # Livrables
        context["deliverables"] = rec.deliverables.all()
        context["progress"] = rec.progress_percentage

        # AuditLog Timeline
        from apps.audit.models import AuditLog
        context["audit_logs"] = (
            AuditLog.objects
            .filter(content_type="Recommendation", object_id=rec.pk)
            .order_by("-created_at")[:20]
        )

        return context


# =============================================================================
# Soft Delete (AC5)
# =============================================================================


class RecommendationDeleteView(AuditRequiredMixin, View):
    """
    Vue de suppression — POST HTMX pour le soft-delete.

    Vérifie que la recommandation est en DRAFT avant de
    la marquer comme supprimée.
    """

    def post(self, request, pk):
        recommendation = get_object_or_404(Recommendation.objects, pk=pk)

        try:
            services.soft_delete_recommendation(
                recommendation=recommendation,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except ValueError as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": str(e),
                    "type": "error",
                },
            })
            return response

        response = HttpResponse(status=200)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": f"Recommandation {recommendation.reference} supprimée",
                "type": "success",
            },
            "refreshTable": True,
        })
        return response


# =============================================================================
# Assignation au DM (Story 2.5)
# =============================================================================


class RecommendationAssignView(AuditRequiredMixin, View):
    """
    Vue d'assignation — Modale HTMX pour assigner un DM.

    GET  : Retourne le partial de la modale d'assignation.
    POST : Exécute la transition FSM DRAFT → ASSIGNED.

    Sécurité :
        - AuditRequiredMixin : seul l'Audit peut assigner.
        - Garde Backend : vérifie status == DRAFT côté serveur.
        - Race condition : catch TransitionNotAllowed pour éviter les 500.
        - Département fantôme : signale l'absence de DM actif.
    """

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        # Garde de sécurité Backend (AC4)
        if recommendation.status != Recommendation.Status.DRAFT:
            return HttpResponseForbidden(
                "L'assignation n'est possible qu'en état DRAFT."
            )

        if not recommendation.department:
            return HttpResponseForbidden("La Direction concernée doit être renseignée.")

        form = AssignDMForm(department=recommendation.department)

        # Département Fantôme : détecter l'absence de DM
        has_dms = form.fields["dm"].queryset.exists()

        return HttpResponse(
            _render_assign_modal(request, recommendation, form, has_dms),
        )

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        # Garde de sécurité Backend (AC4)
        if recommendation.status != Recommendation.Status.DRAFT:
            return HttpResponseForbidden(
                "L'assignation n'est possible qu'en état DRAFT."
            )

        if not recommendation.department:
            return HttpResponseForbidden("La Direction concernée doit être renseignée.")

        from django_fsm import TransitionNotAllowed
        from django.core.exceptions import ValidationError

        form = AssignDMForm(
            request.POST, department=recommendation.department
        )

        if form.is_valid():
            dm = form.cleaned_data["dm"]

            try:
                recommendation = services.assign_recommendation_to_dm(
                    recommendation=recommendation,
                    dm=dm,
                    performed_by=request.user,
                    ip_address=_get_client_ip(request),
                )
            except (TransitionNotAllowed, ValidationError) as e:
                # Race condition : TransitionNotAllowed ou ValidationError
                response = HttpResponse(status=422)
                response["HX-Trigger"] = json.dumps({
                    "notify": {
                        "msg": str(e) if str(e) else "Ce dossier a déjà été assigné par un autre auditeur.",
                        "type": "error",
                    },
                    "closeModal": True,
                    "refreshTable": True,
                })
                return response

            dm_name = dm.get_full_name() or dm.username
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"{recommendation.reference} assignée à {dm_name}",
                    "type": "success",
                },
            })
            # La modale est sur la page de détail : un rafraîchissement complet
            # est nécessaire pour mettre à jour la timeline et l'en-tête (AC1).
            response["HX-Refresh"] = "true"
            return response

        # Formulaire invalide
        has_dms = form.fields["dm"].queryset.exists()
        return HttpResponse(
            _render_assign_modal(request, recommendation, form, has_dms),
            status=422,
        )


def _render_assign_modal(request, recommendation, form, has_dms):
    """Render le partial de la modale d'assignation."""
    from django.template.loader import render_to_string

    return render_to_string(
        "workflow/partials/assign_dm_modal.html",
        {
            "recommendation": recommendation,
            "form": form,
            "has_dms": has_dms,
        },
        request=request,
    )

