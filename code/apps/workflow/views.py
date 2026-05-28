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

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView

from apps.users.mixins import AuditAdminRequiredMixin, AuditRequiredMixin, WorkflowAccessMixin
from apps.users.models import User

from . import selectors, services
from .admin_forms import RecommendationSourceForm
from .forms import (
    AssignDGForm,
    AssignDMForm,
    DelegateETPForm,
    DeliverableFormSet,
    EvidenceDMApprovalForm,
    EvidenceDraftCommentForm,
    EvidenceRejectForm,
    ExtensionApproveForm,
    ExtensionRejectForm,
    ExtensionRequestForm,
    RecommendationForm,
)
from .models import EvidenceFile, EvidenceSubmission, ExtensionRequest, Recommendation, RecommendationSource


def _get_client_ip(request) -> str | None:
    """Extrait l'adresse IP du client depuis les headers."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# =============================================================================
# Liste des recommandations (AC2, AC3)
# =============================================================================


class RecommendationListView(WorkflowAccessMixin, ListView):
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
            "import_status": self.request.GET.get("import_status", "recent"),
        }
        return selectors.get_recommendations_for_user(user=self.request.user, filters=filters)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "recommandations"
        context["topbar_title"] = "Recommandations"
        context["topbar_subtitle"] = "Suivi des recommandations d'audit"
        # Pour les filtres
        context["sources"] = selectors.get_active_sources()
        context["statuses"] = Recommendation.Status.choices
        context["priorities"] = Recommendation.Priority.choices
        # Filtres actuels
        context["current_source"] = self.request.GET.get("source", "")
        context["current_status"] = self.request.GET.get("status", "")
        context["current_priority"] = self.request.GET.get("priority", "")
        context["current_search"] = self.request.GET.get("q", "")
        context["current_import_status"] = self.request.GET.get("import_status", "recent")
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

        if form.is_valid() and formset.is_valid():
            # Extraire les labels de livrables depuis le formset
            deliverables_data = []
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


class RecommendationDetailView(WorkflowAccessMixin, DetailView):
    """
    Vue détail — Centre de Contrôle split 60/40.

    Affiche la recommandation complète avec ses livrables,
    la barre d'avancement et la timeline AuditLog.
    """

    template_name = "workflow/recommendation_detail.html"
    context_object_name = "recommendation"

    def get_object(self, queryset=None):
        return selectors.get_recommendation_detail_for_user(
            pk=self.kwargs["pk"], user=self.request.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rec = self.object
        context["active_route"] = "recommandations"
        context["topbar_title"] = f"Recommandation {rec.reference}"
        context["topbar_subtitle"] = rec.mission_label or "Détail"

        # Livrables
        context["deliverables"] = rec.deliverables.all()
        context["progress"] = rec.progress_percentage

        # AuditLog Timeline — 5 entrées inline + total pour le slide-over
        from apps.audit.models import AuditLog
        audit_log_qs = (
            AuditLog.objects
            .filter(content_type="Recommendation", object_id=rec.pk)
            .select_related("user")
            .order_by("-created_at")
        )
        context["audit_logs"] = audit_log_qs[:5]
        context["audit_log_total_count"] = audit_log_qs.count()

        # Preuves soumises — QuerySet de base (compat. ascendante) + splits filtrés
        submissions_qs = selectors.get_evidence_for_recommendation(
            recommendation=rec,
            user=self.request.user,
        )
        context["evidence_submissions"] = submissions_qs  # QuerySet — compat. tests
        context["active_submissions"] = submissions_qs.exclude(
            status=EvidenceSubmission.SubmissionStatus.REJECTED
        )
        context["rejected_submissions"] = submissions_qs.filter(
            status=EvidenceSubmission.SubmissionStatus.REJECTED
        )

        # Visibilité du bouton "Soumettre Preuves"
        user = self.request.user
        is_assigned_etp = (
            rec.assigned_etp is not None and rec.assigned_etp_id == user.pk
        )
        is_dm_porteur = (
            user.role == User.Role.DM   # DG utilise can_submit_dg, pas ce chemin
            and rec.assigned_etp is None
            and rec.assigned_dm is not None
            and rec.assigned_dm_id == user.pk
        )
        context["can_submit_evidence"] = (
            rec.status == Recommendation.Status.IN_PROGRESS
            and (is_assigned_etp or is_dm_porteur)
        )

        # Soumissions rejetées — QuerySet partagé entre l'accordéon et la bannière
        # (override de la version brute définie plus haut, avec select_related + order)
        context["rejected_submissions"] = submissions_qs.filter(
            status=EvidenceSubmission.SubmissionStatus.REJECTED
        ).select_related("reviewed_by", "submitted_by").order_by("-reviewed_at")

        rejected_submission = context["rejected_submissions"].first()
        context["rejected_submission"] = rejected_submission

        # Bannière de rejet — cuisine interne : visible uniquement ETP et DM
        context["show_rejection_banner"] = (
            rejected_submission is not None
            and rec.status == Recommendation.Status.IN_PROGRESS
            and user.role in (User.Role.DM, User.Role.ETP)
        )

        # Visibilité du bouton "Rejeter" (Story 3.4 — AC3)
        context["can_reject_evidence"] = (
            rec.status == Recommendation.Status.PENDING_DM_REVIEW
            and rec.assigned_etp is not None
            and rec.assigned_dm_id == user.pk
        )

        # Soumission PENDING pour le DM (Story 3.4 / 3.5)
        pending_submission = (
            EvidenceSubmission.objects
            .filter(
                recommendation=rec,
                status=EvidenceSubmission.SubmissionStatus.PENDING,
            )
            .prefetch_related("files")
            .first()
        )
        context["pending_submission"] = pending_submission

        # Visibilité du bouton "Valider vers l'Audit" (Story 3.5 — AC3)
        context["can_approve_evidence"] = (
            rec.status == Recommendation.Status.PENDING_DM_REVIEW
            and rec.assigned_dm_id == user.pk
        )

        # Exemption PV de Recette (FR19) — pour conditionner le label du commentaire
        context["has_pv_recette_in_submission"] = (
            pending_submission is not None
            and pending_submission.files.filter(
                tag=EvidenceFile.Tag.PV_RECETTE
            ).exists()
        )

        # ── Report d'Échéance (Story 3.6) ─────────────────────────────
        pending_extension = selectors.get_pending_extension_for_recommendation(
            recommendation=rec
        )
        context["pending_extension"] = pending_extension
        context["extension_history"] = selectors.get_extension_history_for_recommendation(
            recommendation=rec
        )

        # can_request_extension : DM ou DG personnellement assigné,
        # pas de demande PENDING en cours, reco non clôturée/brouillon (AC3)
        context["can_request_extension"] = (
            rec.assigned_dm is not None
            and rec.assigned_dm_id == user.pk
            and pending_extension is None
            and rec.status not in (
                Recommendation.Status.DRAFT,
                Recommendation.Status.CLOSED_RESOLVED,
            )
        )

        # can_review_extension : tout auditeur peut statuer (AC7)
        context["can_review_extension"] = (
            user.role == User.Role.AUDIT
            and pending_extension is not None
        )

        # ── Soumission Directe DG (Story 3.7 — FR33) ──────────────────────
        # Visible uniquement pour le DG personnellement assigné en ASSIGNED/IN_PROGRESS
        context["can_submit_dg"] = (
            user.role == User.Role.DG
            and rec.assigned_dm is not None
            and rec.assigned_dm_id == user.pk
            and rec.status in (
                Recommendation.Status.ASSIGNED,
                Recommendation.Status.IN_PROGRESS,
            )
        )

        return context


# =============================================================================
# Historique complet (slide-over HTMX)
# =============================================================================


class RecommendationAuditLogView(WorkflowAccessMixin, View):
    """
    Retourne le partial HTML de l'intégralité des entrées AuditLog
    pour une recommandation — chargé en HTMX lazy au premier clic sur
    "Voir tout l'historique" depuis la page détail.
    """

    def get(self, request, pk):
        from django.template.loader import render_to_string
        from apps.audit.models import AuditLog

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        audit_logs = (
            AuditLog.objects
            .filter(content_type="Recommendation", object_id=recommendation.pk)
            .order_by("-created_at")
            .select_related("user")
        )
        return HttpResponse(
            render_to_string(
                "workflow/partials/audit_log_drawer.html",
                {
                    "recommendation": recommendation,
                    "audit_logs": audit_logs,
                },
                request=request,
            )
        )


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
    """Render le partial de la modale d'assignation DM."""
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


# =============================================================================
# Assignation directe au DG (Story 3.x)
# =============================================================================


class RecommendationAssignDGView(AuditRequiredMixin, View):
    """
    Vue d'assignation directe au DG — Modale HTMX (toggle DM ↔ DG).

    GET  : Retourne le partial de la modale DG (toggle côté DG actif).
    POST : Exécute la transition FSM DRAFT → IN_PROGRESS avec DG assigné.

    Sécurité :
        - AuditRequiredMixin : seul l'Audit peut assigner.
        - Garde Backend : vérifie status == DRAFT côté serveur.
        - Race condition : catch TransitionNotAllowed / ValidationError.
    """

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        if recommendation.status != Recommendation.Status.DRAFT:
            return HttpResponseForbidden(
                "L'assignation n'est possible qu'en état DRAFT."
            )

        form = AssignDGForm()
        has_dgs = form.fields["dg"].queryset.exists()

        return HttpResponse(
            _render_assign_dg_modal(request, recommendation, form, has_dgs),
        )

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        if recommendation.status != Recommendation.Status.DRAFT:
            return HttpResponseForbidden(
                "L'assignation n'est possible qu'en état DRAFT."
            )

        from django_fsm import TransitionNotAllowed

        form = AssignDGForm(request.POST)

        if form.is_valid():
            dg = form.cleaned_data["dg"]

            try:
                recommendation = services.assign_recommendation_to_dg(
                    recommendation=recommendation,
                    dg=dg,
                    performed_by=request.user,
                    ip_address=_get_client_ip(request),
                )
            except (TransitionNotAllowed, DjangoValidationError) as e:
                response = HttpResponse(status=422)
                response["HX-Trigger"] = json.dumps({
                    "notify": {
                        "msg": str(e) if str(e) else "Ce dossier a déjà été assigné.",
                        "type": "error",
                    },
                    "closeModal": True,
                    "refreshTable": True,
                })
                return response

            dg_name = dg.get_full_name() or dg.username
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"{recommendation.reference} assignée à {dg_name}",
                    "type": "success",
                },
            })
            response["HX-Refresh"] = "true"
            return response

        has_dgs = form.fields["dg"].queryset.exists()
        return HttpResponse(
            _render_assign_dg_modal(request, recommendation, form, has_dgs),
            status=422,
        )


def _render_assign_dg_modal(request, recommendation, form, has_dgs):
    """Render le partial de la modale d'assignation DG."""
    from django.template.loader import render_to_string

    return render_to_string(
        "workflow/partials/assign_dg_modal.html",
        {
            "recommendation": recommendation,
            "form": form,
            "has_dgs": has_dgs,
        },
        request=request,
    )


# =============================================================================
# Délégation ETP / DM Porteur (Story 3.2)
# =============================================================================


class RecommendationDelegateView(WorkflowAccessMixin, View):
    """
    Vue de délégation — Modale HTMX pour déléguer à un ETP ou devenir DM Porteur.

    GET  : Retourne le partial de la modale de délégation.
    POST : Exécute la délégation ou l'auto-assignation DM Porteur.

    Sécurité :
        - WorkflowAccessMixin : accès restreint aux rôles workflow.
        - Garde Backend : vérifie request.user == recommendation.assigned_dm.
        - Race condition : catch TransitionNotAllowed pour éviter les 500.
    """

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        # Garde RBAC : seul le DM assigné peut déléguer
        if recommendation.assigned_dm != request.user:
            return HttpResponseForbidden(
                "Seul le DM assigné peut déléguer cette recommandation."
            )

        # Garde de statut : uniquement ASSIGNED
        if recommendation.status != Recommendation.Status.ASSIGNED:
            return HttpResponseForbidden(
                "La délégation n'est possible qu'en état ASSIGNED."
            )

        if not recommendation.department:
            return HttpResponseForbidden(
                "La Direction concernée doit être renseignée."
            )

        form = DelegateETPForm(department=recommendation.department)
        has_etps = form.fields["etp"].queryset.exists()

        return HttpResponse(
            _render_delegate_modal(request, recommendation, form, has_etps),
        )

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(
            pk=pk, user=request.user
        )

        # Garde RBAC : seul le DM assigné peut déléguer
        if recommendation.assigned_dm != request.user:
            return HttpResponseForbidden(
                "Seul le DM assigné peut déléguer cette recommandation."
            )

        # Garde de statut : uniquement ASSIGNED
        if recommendation.status != Recommendation.Status.ASSIGNED:
            return HttpResponseForbidden(
                "La délégation n'est possible qu'en état ASSIGNED."
            )

        from django_fsm import TransitionNotAllowed
        from django.core.exceptions import ValidationError

        form = DelegateETPForm(
            request.POST, department=recommendation.department
        )

        if form.is_valid():
            action = form.cleaned_data["action"]

            try:
                if action == DelegateETPForm.ACTION_DELEGATE_ETP:
                    etp = form.cleaned_data["etp"]
                    recommendation = services.delegate_recommendation_to_etp(
                        recommendation=recommendation,
                        etp=etp,
                        performed_by=request.user,
                        ip_address=_get_client_ip(request),
                    )
                    etp_name = etp.get_full_name() or etp.username
                    msg = (
                        f"{recommendation.reference} déléguée à {etp_name}"
                    )
                else:
                    recommendation = services.become_dm_porteur(
                        recommendation=recommendation,
                        performed_by=request.user,
                        ip_address=_get_client_ip(request),
                    )
                    msg = (
                        f"Vous êtes maintenant DM Porteur de "
                        f"{recommendation.reference}"
                    )

            except (TransitionNotAllowed, ValidationError, ValueError) as e:
                response = HttpResponse(status=422)
                response["HX-Trigger"] = json.dumps({
                    "notify": {
                        "msg": str(e) if str(e) else "Cette recommandation a déjà été traitée.",
                        "type": "error",
                    },
                    "closeModal": True,
                    "refreshTable": True,
                })
                return response

            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": msg,
                    "type": "success",
                },
            })
            response["HX-Refresh"] = "true"
            return response

        # Formulaire invalide
        has_etps = form.fields["etp"].queryset.exists()
        return HttpResponse(
            _render_delegate_modal(request, recommendation, form, has_etps),
            status=422,
        )


def _render_delegate_modal(request, recommendation, form, has_etps):
    """Render le partial de la modale de délégation."""
    from django.template.loader import render_to_string

    return render_to_string(
        "workflow/partials/delegate_etp_modal.html",
        {
            "recommendation": recommendation,
            "form": form,
            "has_etps": has_etps,
        },
        request=request,
    )


# =============================================================================
# Soumission de Preuves (Story 3.3)
# =============================================================================


class RecommendationSubmitEvidenceView(WorkflowAccessMixin, View):
    """
    Vue de soumission de preuves — Slide-over HTMX avec brouillons persistants.

    GET  : Charge le slide-over avec le brouillon DRAFT (créé si nécessaire).
    POST : Finalise la soumission : DRAFT → PENDING + FSM IN_PROGRESS → PENDING_DM_REVIEW.

    Sécurité (AC6) :
        - Garde RBAC : ETP assigné OU DM Porteur.
        - Garde de statut : status == IN_PROGRESS.
        - Validation fichiers : déléguée au service (magic bytes, taille, SHA-256).
    """

    def _check_permission(self, request, recommendation):
        """Retourne True si l'utilisateur peut soumettre des preuves."""
        user = request.user
        is_assigned_etp = (
            recommendation.assigned_etp is not None
            and recommendation.assigned_etp_id == user.pk
        )
        is_dm_porteur = (
            recommendation.assigned_etp is None
            and recommendation.assigned_dm is not None
            and recommendation.assigned_dm_id == user.pk
        )
        return is_assigned_etp or is_dm_porteur

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)

        if recommendation.status != Recommendation.Status.IN_PROGRESS:
            return HttpResponseForbidden(
                "La soumission de preuves n'est possible qu'en état IN_PROGRESS."
            )

        if not self._check_permission(request, recommendation):
            return HttpResponseForbidden(
                "Seul l'ETP assigné ou le DM Porteur peut soumettre des preuves."
            )

        # Créer ou récupérer le brouillon DRAFT
        draft, _created = services.get_or_create_draft_submission(
            recommendation=recommendation,
            user=request.user,
        )

        return HttpResponse(
            _render_submit_evidence_modal(
                request, recommendation, draft,
            ),
        )

    def post(self, request, pk):
        from django_fsm import TransitionNotAllowed

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)

        if recommendation.status != Recommendation.Status.IN_PROGRESS:
            return HttpResponseForbidden(
                "La soumission de preuves n'est possible qu'en état IN_PROGRESS."
            )

        if not self._check_permission(request, recommendation):
            return HttpResponseForbidden(
                "Seul l'ETP assigné ou le DM Porteur peut soumettre des preuves."
            )

        try:
            services.submit_evidence_for_recommendation(
                recommendation=recommendation,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except (TransitionNotAllowed, ValueError) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": str(e) or "Une erreur est survenue lors de la soumission.",
                    "type": "error",
                },
            })
            return response

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": (
                    "Vos preuves ont été soumises avec succès. "
                    "En attente de validation par votre Directeur Métier."
                ),
                "type": "success",
            },
        })
        response["HX-Refresh"] = "true"
        return response


def _render_submit_evidence_modal(request, recommendation, draft):
    """Render le partial du slide-over de soumission de preuves."""
    from django.template.loader import render_to_string
    from django.db.models import Sum

    # Calcul du quota utilisé
    quota_used = services._get_active_evidence_quota_used(recommendation)
    quota_max = 20 * 1024 * 1024  # 20 Mo

    return render_to_string(
        "workflow/partials/submit_evidence_modal.html",
        {
            "recommendation": recommendation,
            "draft": draft,
            "draft_files": draft.files.all(),
            "deliverables": recommendation.deliverables.all(),
            "quota_used": quota_used,
            "quota_max": quota_max,
            "quota_used_mb": quota_used / (1024 * 1024),
            "quota_max_mb": quota_max / (1024 * 1024),
            "quota_percentage": min(round((quota_used / quota_max) * 100), 100) if quota_max else 0,
        },
        request=request,
    )


# =============================================================================
# Rejet de preuves par le DM (Story 3.4)
# =============================================================================


class EvidenceRejectView(WorkflowAccessMixin, View):
    """
    Vue de rejet de preuves — Modale HTMX pour le DM.

    GET  : Retourne la modale avec le formulaire de motif.
    POST : Appelle reject_evidence_submission() et renvoie HX-Refresh.

    Sécurité (AC3) :
        - WorkflowAccessMixin : rôles workflow uniquement.
        - Garde RBAC : seul recommendation.assigned_dm peut rejeter.
        - Garde DM Porteur : rejet impossible si assigned_etp is None.
        - Garde de statut : status == PENDING_DM_REVIEW.
    """

    def _check_permission(self, request, recommendation):
        """Retourne une erreur texte ou None si OK (RBAC uniquement).

        La règle DM Porteur (domain rule) est gérée par le service → ValueError → 422.
        """
        if recommendation.assigned_dm_id != request.user.pk:
            return "Seul le DM assigné peut rejeter les preuves."
        if recommendation.status != Recommendation.Status.PENDING_DM_REVIEW:
            return "Le rejet n'est possible qu'en état PENDING_DM_REVIEW."
        return None

    def get(self, request, pk, submission_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        error = self._check_permission(request, recommendation)
        if error:
            return HttpResponseForbidden(error)

        form = EvidenceRejectForm()
        return HttpResponse(
            _render_reject_evidence_modal(request, recommendation, submission_id, form)
        )

    def post(self, request, pk, submission_id):
        from django_fsm import TransitionNotAllowed

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        error = self._check_permission(request, recommendation)
        if error:
            return HttpResponseForbidden(error)

        form = EvidenceRejectForm(request.POST)
        if not form.is_valid():
            return HttpResponse(
                _render_reject_evidence_modal(
                    request, recommendation, submission_id, form
                )
            )

        try:
            services.reject_evidence_submission(
                recommendation=recommendation,
                submission_id=submission_id,
                reason=form.cleaned_data["reason"],
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except (TransitionNotAllowed, ValueError) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Preuves rejetées. Le dossier est retourné en cours de traitement.",
                "type": "warning",
            },
        })
        response["HX-Refresh"] = "true"
        return response


def _render_reject_evidence_modal(request, recommendation, submission_id, form):
    """Render le partial de la modale de rejet."""
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/partials/reject_evidence_modal.html",
        {
            "recommendation": recommendation,
            "submission_id": submission_id,
            "form": form,
        },
        request=request,
    )


# =============================================================================
# Validation DM → Audit (Story 3.5)
# =============================================================================


class EvidenceDMApprovalView(WorkflowAccessMixin, View):
    """
    Vue de validation DM et envoi à l'Audit — Modale HTMX (Story 3.5).

    GET  : Retourne la modale avec le formulaire de commentaire DM.
    POST : Appelle validate_evidence_for_audit() et renvoie HX-Refresh.

    Sécurité (AC3) :
        - WorkflowAccessMixin : rôles workflow uniquement.
        - Garde RBAC : seul recommendation.assigned_dm peut valider.
        - Garde de statut : status == PENDING_DM_REVIEW.
        - Exemption PV (FR19) : commentaire optionnel si PV_RECETTE détecté.
    """

    def _check_permission(self, request, recommendation):
        """Retourne un message d'erreur texte ou None si OK."""
        if recommendation.assigned_dm_id != request.user.pk:
            return "Seul le DM assigné peut valider les preuves."
        if recommendation.status != Recommendation.Status.PENDING_DM_REVIEW:
            return "La validation n'est possible qu'en état PENDING_DM_REVIEW."
        return None

    def _get_pending_submission(self, recommendation, submission_id):
        """Récupère la soumission PENDING ciblée, ou None si absente."""
        return (
            EvidenceSubmission.objects
            .filter(recommendation=recommendation, pk=submission_id)
            .prefetch_related("files")
            .first()
        )

    def get(self, request, pk, submission_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        error = self._check_permission(request, recommendation)
        if error:
            return HttpResponseForbidden(error)

        submission = self._get_pending_submission(recommendation, submission_id)
        has_pv_recette = (
            submission is not None
            and submission.files.filter(tag=EvidenceFile.Tag.PV_RECETTE).exists()
        )
        form = EvidenceDMApprovalForm()
        return HttpResponse(
            _render_approve_evidence_modal(
                request, recommendation, submission_id, form,
                submission=submission, has_pv_recette=has_pv_recette,
            )
        )

    def post(self, request, pk, submission_id):
        from django_fsm import TransitionNotAllowed

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        error = self._check_permission(request, recommendation)
        if error:
            return HttpResponseForbidden(error)

        form = EvidenceDMApprovalForm(request.POST, request.FILES)
        if not form.is_valid():
            submission = self._get_pending_submission(recommendation, submission_id)
            has_pv_recette = (
                submission is not None
                and submission.files.filter(tag=EvidenceFile.Tag.PV_RECETTE).exists()
            )
            return HttpResponse(
                _render_approve_evidence_modal(
                    request, recommendation, submission_id, form,
                    submission=submission, has_pv_recette=has_pv_recette,
                )
            )

        try:
            services.validate_evidence_for_audit(
                recommendation=recommendation,
                submission_id=submission_id,
                comment=form.cleaned_data.get("comment", ""),
                pv_file=request.FILES.get("pv_recette"),
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except (TransitionNotAllowed, ValueError, DjangoValidationError) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Preuves validées. Le dossier est transmis à l'Audit Interne.",
                "type": "success",
            },
        })
        response["HX-Refresh"] = "true"
        return response


def _render_approve_evidence_modal(
    request, recommendation, submission_id, form, *, submission, has_pv_recette
):
    """Render le partial de la modale de validation DM → Audit."""
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/partials/approve_evidence_modal.html",
        {
            "recommendation": recommendation,
            "submission_id": submission_id,
            "submission": submission,
            "has_pv_recette": has_pv_recette,
            "form": form,
        },
        request=request,
    )


# =============================================================================
# Endpoints HTMX pour brouillons (Story 3.3 v2)
# =============================================================================


def _require_evidence_permission(recommendation, user):
    """Lève PermissionDenied si l'utilisateur n'est ni ETP assigné ni DM Porteur."""
    is_assigned_etp = (
        recommendation.assigned_etp is not None
        and recommendation.assigned_etp_id == user.pk
    )
    is_dm_porteur = (
        recommendation.assigned_etp is None
        and recommendation.assigned_dm is not None
        and recommendation.assigned_dm_id == user.pk
    )
    if not (is_assigned_etp or is_dm_porteur):
        raise PermissionDenied("Accès réservé à l'ETP assigné ou au DM Porteur.")


class DraftUploadFileView(WorkflowAccessMixin, View):
    """
    Upload individuel d'un fichier vers le brouillon DRAFT.

    POST : Reçoit un fichier unique en multipart, le valide et le rattache au brouillon.
    Retourne le fragment HTML de la carte fichier (hx-swap="beforeend").
    """

    def post(self, request, pk):
        from django.core.exceptions import ValidationError

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        _require_evidence_permission(recommendation, request.user)

        draft = selectors.get_draft_submission_for_recommendation(
            recommendation=recommendation, user=request.user,
        )
        if not draft:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": "Aucun brouillon trouvé.", "type": "error"},
            })
            return response

        file = request.FILES.get("file")
        if not file:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": "Aucun fichier reçu.", "type": "error"},
            })
            return response

        try:
            evidence_file = services.add_file_to_draft(
                submission=draft,
                file=file,
                user=request.user,
                ip_address=_get_client_ip(request),
            )
        except (ValidationError, ValueError, PermissionError) as e:
            error_msg = str(e) if isinstance(e, (ValueError, PermissionError)) else str(e.message)
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": error_msg, "type": "error"},
            })
            return response

        from django.template.loader import render_to_string
        html = render_to_string(
            "workflow/partials/_draft_file_card.html",
            {
                "file": evidence_file,
                "recommendation": recommendation,
            },
            request=request,
        )

        response = HttpResponse(html)
        # Déclencher la mise à jour du compteur de quota
        quota_used = services._get_active_evidence_quota_used(recommendation)
        response["HX-Trigger"] = json.dumps({
            "quota-updated": {
                "used": quota_used,
                "max": 20 * 1024 * 1024,
            },
        })
        return response


class DraftDeleteFileView(WorkflowAccessMixin, View):
    """
    Suppression d'un fichier brouillon DRAFT.

    DELETE : Supprime le fichier physique et l'enregistrement DB.
    Retourne un swap HTMX vide (hx-swap="delete").
    """

    def delete(self, request, pk, file_id):
        from django.core.exceptions import PermissionDenied

        evidence_file = get_object_or_404(
            EvidenceFile,
            pk=file_id,
            submission__recommendation_id=pk,
        )

        try:
            services.delete_draft_file(
                file=evidence_file,
                user=request.user,
                ip_address=_get_client_ip(request),
            )
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))
        except ValueError as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        quota_used = services._get_active_evidence_quota_used(recommendation)

        response = HttpResponse(status=200)
        response["HX-Trigger"] = json.dumps({
            "quota-updated": {
                "used": quota_used,
                "max": 20 * 1024 * 1024,
            },
        })
        return response


class DraftSaveCommentView(WorkflowAccessMixin, View):
    """
    Autosave du commentaire de résolution via HTMX debounce.

    POST : Met à jour le commentaire du brouillon DRAFT.
    Retourne un indicateur "Sauvegardé" (fragment HTML).
    """

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        _require_evidence_permission(recommendation, request.user)

        draft = selectors.get_draft_submission_for_recommendation(
            recommendation=recommendation, user=request.user,
        )
        if not draft:
            return HttpResponse(status=404)

        comment = request.POST.get("comment", "")

        try:
            services.save_draft_comment(
                submission=draft,
                comment=comment,
                user=request.user,
            )
        except (ValueError, PermissionError) as e:
            return HttpResponse(status=422)

        from django.template.loader import render_to_string
        return HttpResponse(
            render_to_string("workflow/partials/_saved_indicator.html", {}, request=request)
        )


class DraftToggleDeliverableView(WorkflowAccessMixin, View):
    """
    Toggle de complétion d'un livrable via HTMX.

    POST : Bascule is_completed et retourne la checklist mise à jour.
    """

    def post(self, request, pk, del_id):
        from .models import Deliverable

        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        _require_evidence_permission(recommendation, request.user)
        deliverable = get_object_or_404(
            Deliverable,
            pk=del_id,
            recommendation=recommendation,
        )

        services.toggle_deliverable_completion(
            deliverable=deliverable,
            user=request.user,
            ip_address=_get_client_ip(request),
        )

        from django.template.loader import render_to_string
        html = render_to_string(
            "workflow/partials/_deliverable_checklist.html",
            {
                "deliverables": recommendation.deliverables.all(),
                "recommendation": recommendation,
                "progress": recommendation.progress_percentage,
            },
            request=request,
        )
        return HttpResponse(html)


# =============================================================================
# Téléchargement sécurisé de preuves (Story 3.3)
# =============================================================================


class EvidenceFileDownloadView(WorkflowAccessMixin, View):
    """
    Vue de téléchargement sécurisé des fichiers probatoires.

    RBAC via get_recommendations_for_user() pour cohérence automatique
    avec la hiérarchie DM/DG (Story 3.2). Seuls les utilisateurs ayant
    accès à la recommandation parente peuvent télécharger ses preuves.

    Les fichiers DRAFT ne sont accessibles qu'à leur auteur (PRD v2 FR15).
    Les fichiers ne sont pas servis directement par Nginx (/media/ bloqué).
    """

    def get(self, request, pk, file_id):
        evidence_file = get_object_or_404(
            EvidenceFile,
            pk=file_id,
            submission__recommendation_id=pk,
        )

        # RBAC fichiers DRAFT : seul l'auteur peut télécharger
        if evidence_file.submission.status == EvidenceSubmission.SubmissionStatus.DRAFT:
            if evidence_file.submission.submitted_by_id != request.user.pk:
                return HttpResponseForbidden(
                    "Les fichiers en brouillon ne sont accessibles qu'à leur auteur."
                )
        else:
            # RBAC via le sélecteur global — cohérent avec les permissions de la liste
            visible_qs = selectors.get_recommendations_for_user(user=request.user)
            if not visible_qs.filter(pk=pk).exists():
                return HttpResponseForbidden(
                    "Vous n'avez pas accès à ces pièces justificatives."
                )

            # Vision B : AUDIT/EXT ne peuvent télécharger que des fichiers de soumissions ACCEPTED
            from apps.users.models import User
            if request.user.role in (User.Role.AUDIT, User.Role.EXT) and not request.user.is_superuser:
                if evidence_file.submission.status != EvidenceSubmission.SubmissionStatus.ACCEPTED:
                    return HttpResponseForbidden(
                        "Les preuves ne sont accessibles à l'Audit qu'après validation interne."
                    )

        response = FileResponse(
            open(evidence_file.file.path, "rb"),
            content_type=evidence_file.mime_type or "application/octet-stream",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{evidence_file.original_filename}"'
        )
        return response


# =============================================================================
# Demande de Report d'Échéance (Story 3.6 — FR13, FR14, FR34)
# =============================================================================


class ExtensionRequestView(WorkflowAccessMixin, View):
    """
    Vue de demande de report — Modale HTMX pour le DM ou DG assigné.

    GET  : Retourne la modale avec le formulaire.
    POST : Appelle request_extension() et renvoie HX-Refresh.

    Sécurité (AC3) :
        - WorkflowAccessMixin : rôles workflow uniquement.
        - Garde RBAC service : seul recommendation.assigned_dm peut demander.
    """

    def get(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)

        # Garde préventive : n'affiche la modale qu'aux ayants-droit
        if recommendation.assigned_dm_id != request.user.pk:
            return HttpResponseForbidden(
                "Seul le directeur assigné peut demander un report."
            )

        form = ExtensionRequestForm(due_date=recommendation.due_date)
        return HttpResponse(
            _render_extension_request_modal(request, recommendation, form)
        )

    def post(self, request, pk):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)

        if recommendation.assigned_dm_id != request.user.pk:
            return HttpResponseForbidden(
                "Seul le directeur assigné peut demander un report."
            )

        form = ExtensionRequestForm(
            request.POST, due_date=recommendation.due_date
        )
        if not form.is_valid():
            # Extraire le premier message d'erreur pour le toast
            first_errors = list(form.errors.values())
            toast_msg = str(first_errors[0][0]) if first_errors else "Données invalides."
            response = HttpResponse(
                _render_extension_request_modal(request, recommendation, form),
                status=422,
            )
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": toast_msg, "type": "error"},
            })
            return response

        try:
            services.request_extension(
                recommendation=recommendation,
                requested_date=form.cleaned_data["requested_date"],
                reason=form.cleaned_data["reason"],
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except (ValueError, PermissionDenied) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Votre demande de report a été soumise à l'Audit Interne.",
                "type": "success",
            },
        })
        response["HX-Refresh"] = "true"
        return response


def _render_extension_request_modal(request, recommendation, form):
    """Render le partial de la modale de demande de report."""
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/partials/extension_request_modal.html",
        {"recommendation": recommendation, "form": form},
        request=request,
    )


class ExtensionApproveView(AuditRequiredMixin, View):
    """
    Vue d'approbation de report — POST HTMX pour l'Audit.

    GET  : Retourne la modale de décision (mode approve).
    POST : Appelle approve_extension() et renvoie HX-Refresh.

    Sécurité (AC7) :
        - AuditRequiredMixin : AUDIT uniquement.
        - is_audit_admin NON requis.
    """

    def _get_extension(self, pk, ext_id):
        return get_object_or_404(
            ExtensionRequest,
            pk=ext_id,
            recommendation__pk=pk,
        )

    def get(self, request, pk, ext_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        ext = self._get_extension(pk, ext_id)
        form = ExtensionApproveForm()
        return HttpResponse(
            _render_extension_review_modal(
                request, recommendation, ext, form, action="approve"
            )
        )

    def post(self, request, pk, ext_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        ext = self._get_extension(pk, ext_id)

        form = ExtensionApproveForm(request.POST)
        if not form.is_valid():
            return HttpResponse(
                _render_extension_review_modal(
                    request, recommendation, ext, form, action="approve"
                ),
                status=422,
            )

        try:
            services.approve_extension(
                extension_request=ext,
                performed_by=request.user,
                audit_comment=form.cleaned_data.get("audit_comment", ""),
                ip_address=_get_client_ip(request),
            )
        except (ValueError, PermissionDenied) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Demande de report approuvée. L'échéance a été mise à jour.",
                "type": "success",
            },
        })
        response["HX-Refresh"] = "true"
        return response


class ExtensionRejectView(AuditRequiredMixin, View):
    """
    Vue de rejet de report — POST HTMX pour l'Audit.

    GET  : Retourne la modale de décision (mode reject).
    POST : Appelle reject_extension() et renvoie HX-Refresh.

    Sécurité (AC7) :
        - AuditRequiredMixin : AUDIT uniquement.
        - audit_comment obligatoire (AC5 — validé par ExtensionRejectForm).
    """

    def _get_extension(self, pk, ext_id):
        return get_object_or_404(
            ExtensionRequest,
            pk=ext_id,
            recommendation__pk=pk,
        )

    def get(self, request, pk, ext_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        ext = self._get_extension(pk, ext_id)
        form = ExtensionRejectForm()
        return HttpResponse(
            _render_extension_review_modal(
                request, recommendation, ext, form, action="reject"
            )
        )

    def post(self, request, pk, ext_id):
        recommendation = selectors.get_recommendation_by_id(pk=pk, user=request.user)
        ext = self._get_extension(pk, ext_id)

        form = ExtensionRejectForm(request.POST)
        if not form.is_valid():
            return HttpResponse(
                _render_extension_review_modal(
                    request, recommendation, ext, form, action="reject"
                ),
                status=422,
            )

        try:
            services.reject_extension(
                extension_request=ext,
                performed_by=request.user,
                audit_comment=form.cleaned_data["audit_comment"],
                ip_address=_get_client_ip(request),
            )
        except (ValueError, PermissionDenied) as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"},
            })
            return response

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Demande de report rejetée. L'échéance est maintenue.",
                "type": "warning",
            },
        })
        response["HX-Refresh"] = "true"
        return response


def _render_extension_review_modal(request, recommendation, ext, form, *, action):
    """Render le partial de la modale de décision Audit (approve ou reject)."""
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/partials/extension_review_modal.html",
        {
            "recommendation": recommendation,
            "extension": ext,
            "form": form,
            "action": action,
        },
        request=request,
    )


# =============================================================================
# Soumission Directe DG (Story 3.7 — FR33)
# =============================================================================


def _render_dg_submission_panel(request, recommendation, draft, error_message=None):
    """Render le partial du panneau de soumission directe DG (side drawer).

    Lecture pure — le draft est créé en amont par la vue (GET) ou récupéré
    avant le re-rendu (POST en erreur).
    """
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/partials/dg_submit_evidence_panel.html",
        {
            "recommendation": recommendation,
            "draft": draft,
            "error_message": error_message,
        },
        request=request,
    )


class EvidenceDGDirectSubmitView(WorkflowAccessMixin, View):
    """
    Vue de soumission directe à l'Audit par le DG (Story 3.7 — FR33).

    GET  : Retourne le partial HTML du side drawer de soumission DG.
    POST : Appelle submit_evidence_by_dg() et renvoie HX-Refresh.

    Sécurité (AC5) :
        - WorkflowAccessMixin : rôles workflow uniquement.
        - dispatch() : guard RBAC précoce — DG assigné uniquement.
    """

    def _get_recommendation(self, pk):
        return selectors.get_recommendation_detail_for_user(
            pk=pk,
            user=self.request.user,
        )

    def dispatch(self, request, *args, **kwargs):
        rec = self._get_recommendation(kwargs["pk"])
        # Guard RBAC précoce (AC5) — DG assigné uniquement
        if (
            request.user.role != User.Role.DG
            or rec.assigned_dm_id != request.user.pk
        ):
            raise PermissionDenied("Réservé au DG assigné à cette recommandation.")
        self._rec = rec
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        # Créer le draft DG dès l'ouverture du panneau pour que
        # DraftUploadFileView puisse le retrouver lors d'un upload.
        draft, _ = services.get_or_create_draft_submission(
            recommendation=self._rec, user=request.user
        )
        return HttpResponse(
            _render_dg_submission_panel(request, self._rec, draft)
        )

    def post(self, request, pk):
        try:
            services.submit_evidence_by_dg(
                recommendation=self._rec,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except (ValueError, PermissionDenied) as exc:
            draft, _ = services.get_or_create_draft_submission(
                recommendation=self._rec, user=request.user
            )
            response = HttpResponse(
                _render_dg_submission_panel(
                    request, self._rec, draft, error_message=str(exc)
                ),
                status=422,
            )
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(exc), "type": "error"},
            })
            return response

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {
                "msg": "Preuves soumises directement à l'Audit.",
                "type": "success",
            },
        })
        response["HX-Refresh"] = "true"
        return response


# =============================================================================
# Administration des Sources de Recommandation (Story 3.7.b — Audit Admin)
# =============================================================================


def _render_source_form(request, form, source=None):
    """Rendu du partial formulaire (modal) de source."""
    from django.template.loader import render_to_string
    return render_to_string(
        "workflow/admin/sources/_form_modal.html",
        {"form": form, "source": source},
        request=request,
    )


class RecommendationSourceListView(AuditAdminRequiredMixin, ListView):
    """
    Vue liste — Administration des sources de recommandation.

    Accès : Audit Admin uniquement (role=AUDIT AND is_audit_admin=True).
    Affiche toutes les sources (actives et inactives) avec leur statut.
    """

    template_name = "workflow/admin/sources/list.html"
    context_object_name = "sources"

    def get_queryset(self):
        return selectors.get_all_sources()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "sources-admin"
        context["topbar_title"] = "Sources de recommandation"
        context["topbar_subtitle"] = "Paramétrage des sources (internes et externes)"
        return context


class RecommendationSourceCreateView(AuditAdminRequiredMixin, View):
    """
    Création d'une source de recommandation.

    GET  : Retourne le partial formulaire vide (HTMX hx-get).
    POST : Crée la source via le service. Retourne 204+HX-Refresh ou 422+form.
    """

    def get(self, request):
        form = RecommendationSourceForm()
        return HttpResponse(_render_source_form(request, form))

    def post(self, request):
        form = RecommendationSourceForm(request.POST)
        if not form.is_valid():
            return HttpResponse(_render_source_form(request, form), status=422)

        try:
            services.create_recommendation_source(
                code=form.cleaned_data["code"],
                label=form.cleaned_data["label"],
                is_external=form.cleaned_data["is_external"],
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return HttpResponse(_render_source_form(request, form), status=422)

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {"msg": "Source créée avec succès.", "type": "success"},
            "closeModal": True,
        })
        response["HX-Refresh"] = "true"
        return response


class RecommendationSourceEditView(AuditAdminRequiredMixin, View):
    """
    Modification d'une source de recommandation (libellé + is_external).

    GET  : Retourne le partial formulaire prérempli.
    POST : Met à jour via le service. Retourne 204+HX-Refresh ou 422+form.

    Note : le champ `code` est rendu disabled en édition (AC5 — immuable).
    """

    def _get_source(self, pk):
        return get_object_or_404(RecommendationSource, pk=pk)

    def get(self, request, pk):
        source = self._get_source(pk)
        form = RecommendationSourceForm(instance=source)
        return HttpResponse(_render_source_form(request, form, source=source))

    def post(self, request, pk):
        source = self._get_source(pk)
        form = RecommendationSourceForm(request.POST, instance=source)
        if not form.is_valid():
            return HttpResponse(_render_source_form(request, form, source=source), status=422)

        try:
            services.update_recommendation_source(
                source=source,
                label=form.cleaned_data["label"],
                is_external=form.cleaned_data["is_external"],
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return HttpResponse(_render_source_form(request, form, source=source), status=422)

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {"msg": "Source mise à jour.", "type": "success"},
            "closeModal": True,
        })
        response["HX-Refresh"] = "true"
        return response


class RecommendationSourceToggleView(AuditAdminRequiredMixin, View):
    """
    Activation / désactivation d'une source (toggle is_active).

    POST uniquement — sécurité CSRF assurée par le middleware Django.
    Retourne 204 + HX-Refresh pour recharger le tableau.
    """

    def post(self, request, pk):
        source = get_object_or_404(RecommendationSource, pk=pk)
        try:
            services.toggle_recommendation_source(
                source=source,
                performed_by=request.user,
                ip_address=_get_client_ip(request),
            )
        except Exception as exc:
            response = HttpResponse(str(exc), status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(exc), "type": "error"},
            })
            return response

        action = "activée" if source.is_active else "désactivée"
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({
            "notify": {"msg": f"Source {action}.", "type": "success"},
        })
        response["HX-Refresh"] = "true"
        return response

