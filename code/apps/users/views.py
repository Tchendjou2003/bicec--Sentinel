"""
Users App — Views (Auth, Onboarding & Habilitation)

Implémentation de l'authentification, de la redirection conditionnelle
et de l'interface d'habilitation des comptes (ADR-10).

Spécifications couvertes :
    - FR1  : Authentification locale
    - FR3  : Attribution des rôles via interface dédiée
    - FR36 : Délégation is_audit_admin
    - FR37 : Redirection des comptes sans rôle (coquilles vides)
    - ADR-10 : Séparation des comptes techniques et des habilitations
"""
import json
import uuid
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from . import selectors, services
from .mixins import (
    AdminRequiredMixin,
    AuditAdminRequiredMixin,
    ProvisioningApproverRequiredMixin,
    ProvisioningListAccessMixin,
)
from .models import Department, OrgUnitType, User, UserProvisioningRequest
from .forms import DepartmentForm, ITUserCreationForm, OrgUnitTypeForm, UserProvisioningRequestForm


class SentinelLoginView(LoginView):
    """
    Vue de connexion personnalisée.
    
    Gère l'authentification standard de Django et applique une
    redirection conditionnelle après connexion (FR37).
    """
    template_name = "auth/login.html"

    def get_success_url(self) -> str:
        """
        Détermine l'URL de redirection après une connexion réussie.
        
        Logique métier (ADR-10) :
        - Un utilisateur sans rôle est une coquille vide -> redirigé vers la page d'attente.
        - Un EXT est redirigé vers le tableau de bord externe isolé (Story 1.3 / AC2).
        - Un Admin est redirigé vers le Django Admin.
        - Les autres rôles sont redirigés vers leur tableau de bord respectif
          (temporairement vers la page d'accueil si le dashboard n'existe pas encore).
        """
        user = self.request.user
        assert isinstance(user, User)
        
        if user.is_shell_account:
            return reverse("auth:pending")
        if user.role == User.Role.EXT:
            return reverse("auth:external-dashboard")
        
        if user.role == User.Role.ADMIN or user.is_staff:
            return reverse("auth:admin-dashboard")
            
        # En attendant les tableaux de bord spécifiques de l'Epic 6,
        # tous les acteurs du workflow collab (Audit, DM, ETP, DG) sont redirigés
        # directement vers le suivi des recommandations (Story 3.1).
        if user.role in [User.Role.AUDIT, User.Role.DM, User.Role.ETP, User.Role.DG]:
            return reverse("workflow:recommendation-list")
            
        return super().get_success_url()

    def form_valid(self, form):
        """
        Gère la checkbox « Se souvenir de moi ».

        Si décochée, la session expire à la fermeture du navigateur
        (cookie de session). Si cochée, la durée par défaut
        SESSION_COOKIE_AGE (30 min) s’applique.
        """
        remember = self.request.POST.get("remember_me")
        if not remember:
            self.request.session.set_expiry(0)
        return super().form_valid(form)


class PendingActivationView(LoginRequiredMixin, TemplateView):
    """
    Page d'attente pour les comptes « coquilles vides » (FR37).
    
    Affiche un message indiquant que le compte a été créé par l'IT
    mais nécessite une habilitation par la Direction de l'Audit Interne.
    """
    template_name = "auth/pending.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Vérification de sécurité additionnelle : 
        Si un utilisateur actif (avec rôle) tente d'accéder à cette page,
        il est redirigé vers l'accueil pour éviter qu'il ne soit bloqué.
        """
        if request.user.is_authenticated and not request.user.is_shell_account:
            # L'utilisateur a déjà un rôle, il n'a rien à faire ici
            return redirect(reverse("home"))
            
        return super().dispatch(request, *args, **kwargs)


class ExternalDashboardView(LoginRequiredMixin, TemplateView):
    """
    Tableau de bord externe pour les auditeurs COBAC/BEAC/CAC (Story 1.3 / AC2).
    
    Espace isolé réservé aux utilisateurs ayant le rôle EXT.
    Tout utilisateur interne se voit refuser l'accès (403 Forbidden).
    """
    template_name = "external/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Vérification de sécurité : seuls les EXT avec is_external=True
        peuvent accéder à l’espace externe. Les utilisateurs internes
        ou les comptes EXT incohérents reçoivent un 403.
        """
        if request.user.is_authenticated and (
            request.user.role != User.Role.EXT or not request.user.is_external
        ):
            raise PermissionDenied(
                "Accès réservé aux auditeurs externes."
            )
        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# Habilitation Audit (Story 1.5 + 1.7)
# =============================================================================


class HabilitationListView(ProvisioningApproverRequiredMixin, ListView):
    """
    Liste des utilisateurs pour l'interface d'habilitation (FR3).

    Accessible uniquement aux auditeurs avec is_audit_admin=True
    ou aux superusers (bootstrapping initial).
    Intègre le toggle is_audit_admin inline (Story 1.7 / FR36).
    """

    template_name = "habilitation/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        qs = selectors.get_all_manageable_users()
        filtre = self.request.GET.get("filtre", "")
        if filtre == "shell":
            qs = qs.filter(role="")
        elif filtre == "actif":
            qs = qs.exclude(role="")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtre_actif"] = self.request.GET.get("filtre", "")
        context["total_shell"] = selectors.count_shell_accounts()
        return context


class HabilitationEditView(ProvisioningApproverRequiredMixin, View):
    """
    Formulaire d'édition du rôle et département d'un utilisateur (FR3).

    GET  : affiche le formulaire pré-rempli.
    POST : appelle le service assign_role() et redirige.
    """

    def get(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        departments = selectors.get_active_departments()
        return render(request, "habilitation/user_edit.html", {
            "target_user": target_user,
            "departments": departments,
            "roles": User.Role.choices,
        })

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        role = request.POST.get("role", "")
        dept_id = request.POST.get("department", "")
        department = None
        if dept_id:
            department = get_object_or_404(Department, pk=dept_id)

        try:
            services.assign_role(
                target_user=target_user,
                role=role,
                department=department,
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(
                request,
                f"Rôle '{target_user.get_role_display()}' attribué à "
                f"{target_user.username}.",
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect("workflow:habilitation-list")


class HabilitationToggleAdminView(AuditAdminRequiredMixin, View):
    """
    Toggle inline du flag is_audit_admin (Story 1.7 / FR36).

    Appelé en POST depuis la liste d'habilitation (bouton dans la ligne).
    Inverse la valeur actuelle du flag pour un Auditeur Interne.
    """

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        new_value = not target_user.is_audit_admin

        try:
            services.toggle_audit_admin(
                target_user=target_user,
                grant=new_value,
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            action = "accordée" if new_value else "révoquée"
            msg = f"Délégation admin {action} pour {target_user.username}."
            
            if request.headers.get("HX-Request") == "true":
                response = render(request, "habilitation/partials/toggle_admin.html", {"u": target_user})
                response["HX-Trigger"] = json.dumps({
                    "notify": {"msg": msg, "type": "success"}
                })
                return response

            messages.success(request, msg)
        except (ValueError, PermissionDenied) as e:
            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=204)
                response["HX-Trigger"] = json.dumps({
                    "notify": {"msg": str(e), "type": "error"}
                })
                return response
            
            messages.error(request, str(e))

        # Rediriger vers la vue dédiée Audit (Story 6.2.0 / AC5)
        # habilitation-list est désormais réservée au groupe IT
        return redirect("auth:audit-admin-members")


# =============================================================================
# Administration IT — Dashboard & Organigramme (Story 1.4)
# =============================================================================





class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """
    Tableau de bord de l'Admin (Story 1.4 / AC1).

    Affiche les indicateurs clés : nombre d'utilisateurs,
    nombre de coquilles vides en attente, nombre de départements.
    """
    template_name = "admin_it/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "dashboard"
        context["topbar_title"] = "Tableau de bord"
        context["topbar_subtitle"] = "Administration IT"
        context["total_users"] = selectors.count_total_users()
        context["total_shell"] = selectors.count_shell_accounts()
        context["total_departments"] = selectors.count_departments()
        return context


class OrganigrammeListView(ProvisioningApproverRequiredMixin, TemplateView):
    """
    Liste hiérarchique des départements (Story 1.4 / AC2, AC3).

    Affiche l'arborescence complète de l'organigramme BICEC.
    Les opérations CRUD sont effectuées via HTMX.
    """
    template_name = "admin_it/organigramme_list.html"

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get("parent_id")
        if parent_id:
            try:
                uuid.UUID(parent_id)
            except ValueError:
                parent_id = None
        departments = selectors.get_departments_for_level(parent_id)
        breadcrumb = selectors.get_department_breadcrumb(parent_id) if parent_id else []

        context = self.get_context_data(**kwargs)
        context.update({
            "departments": departments,
            "breadcrumb": breadcrumb,
            "current_parent_id": parent_id,
        })

        if request.headers.get("HX-Request") == "true":
            return render(request, "admin_it/partials/organigramme_drilldown.html", context)
            
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "organigramme"
        context["topbar_title"] = "Organigramme"
        context["topbar_subtitle"] = "Structure institutionnelle BICEC"
        context["total_departments"] = selectors.count_departments()
        return context


class DepartmentCreateView(ProvisioningApproverRequiredMixin, View):
    """
    Création d'un département (HTMX — Story 1.4 / AC2, AC3).
    """

    def get(self, request):
        parent_id = request.GET.get("parent_id")
        initial = {"parent": parent_id} if parent_id else None
        form = DepartmentForm(initial=initial)
        return render(request, "admin_it/partials/department_form.html", {
            "form": form,
            "is_edit": False,
        })

    def post(self, request):
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = services.create_department_with_audit(
                form=form, 
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            msg = f"Département « {dept.name} » créé avec succès."
            messages.success(request, msg)
            if request.headers.get("HX-Request") == "true":
                parent_id = dept.parent_id if dept.parent else None
                departments = selectors.get_departments_for_level(parent_id)
                breadcrumb = selectors.get_department_breadcrumb(parent_id) if parent_id else []
                response = render(request, "admin_it/partials/organigramme_drilldown.html", {
                    "departments": departments,
                    "breadcrumb": breadcrumb,
                    "current_parent_id": parent_id,
                })
                response["HX-Retarget"] = "#organigramme-content"
                response["HX-Trigger"] = json.dumps({
                    "notify": {"msg": msg, "type": "success"}
                })
                return response
            return redirect("auth:organigramme-list")
        return render(request, "admin_it/partials/department_form.html", {
            "form": form,
            "is_edit": False,
        })


class DepartmentEditView(ProvisioningApproverRequiredMixin, View):
    """
    Modification d'un département (HTMX — Story 1.4 / AC2).
    """

    def get(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        form = DepartmentForm(instance=dept)
        return render(request, "admin_it/partials/department_form.html", {
            "form": form,
            "department": dept,
            "is_edit": True,
        })

    def post(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            dept = services.update_department_with_audit(
                form=form, 
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            msg = f"Département « {dept.name} » modifié."
            messages.success(request, msg)
            if request.headers.get("HX-Request") == "true":
                parent_id = dept.parent_id if dept.parent else None
                departments = selectors.get_departments_for_level(parent_id)
                breadcrumb = selectors.get_department_breadcrumb(parent_id) if parent_id else []
                response = render(request, "admin_it/partials/organigramme_drilldown.html", {
                    "departments": departments,
                    "breadcrumb": breadcrumb,
                    "current_parent_id": parent_id,
                })
                response["HX-Retarget"] = "#organigramme-content"
                response["HX-Trigger"] = json.dumps({
                    "notify": {"msg": msg, "type": "success"}
                })
                return response
            return redirect("auth:organigramme-list")
        return render(request, "admin_it/partials/department_form.html", {
            "form": form,
            "department": dept,
            "is_edit": True,
        })


class DepartmentDeleteView(ProvisioningApproverRequiredMixin, View):
    """
    Suppression logique (soft-delete) d'un département (HTMX).
    """
    def post(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        parent_id = dept.parent_id if dept.parent else None
        
        msg = f"La structure « {dept.name} » a été supprimée."
        msg_type = "success"
        try:
            services.soft_delete_department_with_audit(
                department=dept, 
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, msg)
        except ValueError as e:
            msg = str(e)
            msg_type = "error"
            messages.error(request, msg)
            
        if request.headers.get("HX-Request") == "true":
            departments = selectors.get_departments_for_level(parent_id)
            breadcrumb = selectors.get_department_breadcrumb(parent_id) if parent_id else []
            response = render(request, "admin_it/partials/organigramme_drilldown.html", {
                "departments": departments,
                "breadcrumb": breadcrumb,
                "current_parent_id": parent_id,
            })
            # Notification Alpine.js via HX-Trigger
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": msg, "type": msg_type}
            })
            return response
        return redirect("auth:organigramme-list")


class DepartmentSearchView(ProvisioningApproverRequiredMixin, View):
    """
    Recherche en temps réel (HTMX) dans l'organigramme.
    """
    def get(self, request):
        query = request.GET.get("q", "")
        results = selectors.search_departments(query)
        return render(request, "admin_it/partials/organigramme_search_results.html", {
            "results": results,
            "query": query,
        })


class ITUserListView(AdminRequiredMixin, ListView):
    """
    Liste des comptes utilisateurs gérés par l'Admin IT (Story 1.4 / AC4).
    """
    template_name = "admin_it/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        qs = User.objects.filter(is_superuser=False).select_related("department").order_by("username")
        filtre = self.request.GET.get("filtre", "")
        if filtre == "shell":
            qs = qs.filter(role="")
        elif filtre == "actif":
            qs = qs.exclude(role="")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "utilisateurs"
        context["topbar_title"] = "Utilisateurs"
        context["topbar_subtitle"] = "Gestion des comptes IT"
        context["filtre_actif"] = self.request.GET.get("filtre", "")
        context["total_shell"] = selectors.count_shell_accounts()
        context["total_users"] = selectors.count_total_users()
        return context


class ITUserCreateView(AdminRequiredMixin, View):
    """
    Création d'un compte « coquille vide » (Story 1.4 / AC4).

    Le formulaire ne propose AUCUN champ rôle. Le compte créé
    est automatiquement sans rôle et sera capté par le middleware
    RoleRequiredMiddleware (FR37).
    """

    def get(self, request):
        form = ITUserCreationForm()
        return render(request, "admin_it/user_create.html", {
            "form": form,
            "active_route": "utilisateurs",
            "topbar_title": "Nouveau compte",
            "topbar_subtitle": "Création d'un compte coquille vide",
        })

    def post(self, request):
        form = ITUserCreationForm(request.POST)
        if form.is_valid():
            user = services.create_shell_account_with_audit(
                form=form, 
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(
                request,
                f"Compte « {user.username} » créé. "
                f"En attente d'habilitation par la Direction de l'Audit.",
            )
            return redirect("auth:admin-user-list")
        return render(request, "admin_it/user_create.html", {
            "form": form,
            "active_route": "utilisateurs",
            "topbar_title": "Nouveau compte",
            "topbar_subtitle": "Création d'un compte coquille vide",
        })


# =============================================================================
# Provisioning Maker/Checker (Story 6.2.0)
# =============================================================================


class ProvisioningRequestListView(ProvisioningListAccessMixin, ListView):
    """
    File des demandes de provisioning (Story 6.2.0).

    Accessible à tous les Admin IT (makers voient leurs propres demandes ;
    membres du groupe « Administrateurs Sentinel » voient tout).
    Un Admin IT hors groupe voit uniquement ses propres soumissions — il
    peut les annuler mais ne peut pas approuver/rejeter.
    """

    template_name = "admin_it/provisioning_list.html"
    context_object_name = "requests"
    paginate_by = 25

    def get_queryset(self):
        qs = UserProvisioningRequest.objects.select_related(
            "requested_by", "reviewed_by", "requested_department"
        )
        # Les checkers (membres du groupe) voient toutes les demandes.
        # Les makers (Admin IT hors groupe) ne voient que les leurs.
        if not services.user_is_provisioning_approver(self.request.user):
            qs = qs.filter(requested_by=self.request.user)

        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "provisioning"
        context["topbar_title"] = "Provisioning des comptes"
        context["topbar_subtitle"] = "Demandes de création — file Maker/Checker"
        context["status_choices"] = UserProvisioningRequest.Status.choices
        context["status_filter"] = self.request.GET.get("status", "")
        context["is_approver"] = services.user_is_provisioning_approver(self.request.user)
        context["pending_count"] = UserProvisioningRequest.objects.filter(
            status=UserProvisioningRequest.Status.PENDING
        ).count()
        return context


class ProvisioningRequestCreateView(AdminRequiredMixin, View):
    """
    Création d'une demande de provisioning par l'Admin IT (maker).

    GET  : affiche la modale de création.
    POST : crée la UserProvisioningRequest (PENDING) — aucun User créé.
    """

    def get(self, request):
        form = UserProvisioningRequestForm()
        return render(request, "admin_it/partials/provisioning_create_modal.html", {
            "form": form,
        })

    def post(self, request):
        form = UserProvisioningRequestForm(request.POST)
        if form.is_valid():
            try:
                req = services.create_provisioning_request(
                    maker=request.user,
                    cleaned_data=form.cleaned_data,
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = json.dumps({
                    "notify": {
                        "msg": f"Demande soumise pour « {req.requested_username} ». "
                               f"En attente de validation.",
                        "type": "success",
                    },
                    "provisioningCreated": True,
                })
                return response
            except Exception as e:
                messages.error(request, str(e))

        # Construire un message d'erreur synthétique pour le toast
        error_fields = []
        field_labels = {
            "requested_username": "Identifiant",
            "requested_email": "E-mail",
            "password": "Mot de passe",
            "requested_role": "Rôle",
            "requested_department": "Département",
            "mission_organization": "Organisation",
            "mission_start_date": "Date de début",
        }
        for field_name, errors in form.errors.items():
            if field_name == "__all__":
                continue
            label = field_labels.get(field_name, field_name)
            error_fields.append(label)

        if error_fields:
            error_msg = f"Champs à corriger : {', '.join(error_fields)}."
        else:
            error_msg = "Veuillez corriger les erreurs du formulaire."

        response = render(
            request,
            "admin_it/partials/provisioning_create_modal.html",
            {"form": form},
            status=422,
        )
        response["HX-Trigger"] = json.dumps({
            "notify": {"msg": error_msg, "type": "error"}
        })
        return response


class ProvisioningRequestApproveView(ProvisioningApproverRequiredMixin, View):
    """
    Approbation d'une demande PENDING par un checker (Story 6.2.0 / AC2).
    Crée le User atomiquement.
    """

    def post(self, request, pk):
        req = get_object_or_404(UserProvisioningRequest, pk=pk)
        try:
            user = services.approve_provisioning_request(
                request=req,
                checker=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"Compte « {user.username} » créé avec succès.",
                    "type": "success",
                },
                "provisioningUpdated": True,
            })
            return response
        except Exception as e:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"}
            })
            return response


class ProvisioningRequestRejectView(ProvisioningApproverRequiredMixin, View):
    """
    Rejet d'une demande PENDING avec motif obligatoire (Story 6.2.0 / AC3).

    GET  : affiche la sous-modale de saisie du motif.
    POST : rejette la demande.
    """

    def get(self, request, pk):
        req = get_object_or_404(UserProvisioningRequest, pk=pk)
        return render(request, "admin_it/partials/provisioning_reject_modal.html", {
            "req": req,
        })

    def post(self, request, pk):
        req = get_object_or_404(UserProvisioningRequest, pk=pk)
        reason = request.POST.get("rejection_reason", "").strip()
        try:
            services.reject_provisioning_request(
                request=req,
                checker=request.user,
                reason=reason,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"Demande « {req.requested_username} » rejetée.",
                    "type": "warning",
                },
                "provisioningUpdated": True,
            })
            return response
        except Exception as e:
            return render(
                request,
                "admin_it/partials/provisioning_reject_modal.html",
                {"req": req, "error": str(e)},
                status=422,
            )


class ProvisioningRequestCancelView(AdminRequiredMixin, View):
    """
    Annulation d'une demande PENDING par le maker (Story 6.2.0 / AC3).
    Vérifié dans le service : seul l'auteur peut annuler.
    """

    def post(self, request, pk):
        req = get_object_or_404(UserProvisioningRequest, pk=pk)
        try:
            services.cancel_provisioning_request(
                request=req,
                maker=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "notify": {
                    "msg": f"Demande « {req.requested_username} » annulée.",
                    "type": "info",
                },
                "provisioningUpdated": True,
            })
            return response
        except Exception as e:
            response = HttpResponse(status=403)
            response["HX-Trigger"] = json.dumps({
                "notify": {"msg": str(e), "type": "error"}
            })
            return response


# Point d'entrée Audit dédié — toggle is_audit_admin (Story 6.2.0 / AC5)


class AuditAdminMembersView(AuditAdminRequiredMixin, ListView):
    """
    Liste des auditeurs internes avec toggle is_audit_admin.

    Accessible uniquement aux Audit Admins (auto-gouvernance exclusive Audit).
    Découplé de la liste d'habilitation générale (passée à l'IT).
    """

    template_name = "habilitation/audit_admin_members.html"
    context_object_name = "auditors"

    def get_queryset(self):
        return User.objects.filter(
            role=User.Role.AUDIT
        ).order_by("username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["topbar_title"] = "Administrateurs Audit"
        context["topbar_subtitle"] = "Délégation du flag is_audit_admin"
        return context


# =============================================================================
# OrgUnitType Admin (Story 3.7.b / Phase B — AuditAdmin uniquement)
# =============================================================================


def _render_org_unit_type_form(request, form, instance=None):
    """Helper : rendu du formulaire modal OrgUnitType avec gestion des erreurs."""
    status = 422 if form.errors else 200
    return render(
        request,
        "admin_it/org_unit_types/_form_modal.html",
        {"form": form, "org_unit_type": instance},
        status=status,
    )


class OrgUnitTypeListView(ProvisioningApproverRequiredMixin, ListView):
    """
    Liste des types d'unités organisationnelles paramétrables.
    Accessible uniquement aux Audit Admins (Story 3.7.b Phase B).
    """
    template_name = "admin_it/org_unit_types/list.html"
    context_object_name = "org_unit_types"

    def get_queryset(self):
        return selectors.get_all_org_unit_types()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_route"] = "org-unit-types"
        context["topbar_title"] = "Types d'unités org."
        context["topbar_subtitle"] = "Paramétrage des types structurels"
        return context


class OrgUnitTypeCreateView(ProvisioningApproverRequiredMixin, View):
    """Création d'un type d'unité organisationnelle (HTMX)."""

    def get(self, request):
        return _render_org_unit_type_form(request, OrgUnitTypeForm())

    def post(self, request):
        form = OrgUnitTypeForm(request.POST)
        if form.is_valid():
            services.create_org_unit_type(
                form=form,
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            response = HttpResponse(status=204)
            response["HX-Refresh"] = "true"
            return response
        return _render_org_unit_type_form(request, form)


class OrgUnitTypeEditView(ProvisioningApproverRequiredMixin, View):
    """Modification d'un type d'unité organisationnelle (HTMX)."""

    def get(self, request, pk):
        instance = get_object_or_404(OrgUnitType, pk=pk)
        return _render_org_unit_type_form(request, OrgUnitTypeForm(instance=instance), instance)

    def post(self, request, pk):
        instance = get_object_or_404(OrgUnitType, pk=pk)
        form = OrgUnitTypeForm(request.POST, instance=instance)
        if form.is_valid():
            services.update_org_unit_type(
                form=form,
                performed_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            response = HttpResponse(status=204)
            response["HX-Refresh"] = "true"
            return response
        return _render_org_unit_type_form(request, form, instance)


class OrgUnitTypeToggleView(ProvisioningApproverRequiredMixin, View):
    """Active ou désactive un type d'unité (POST uniquement, HTMX)."""

    def post(self, request, pk):
        instance = get_object_or_404(OrgUnitType, pk=pk)
        services.toggle_org_unit_type(
            instance=instance,
            performed_by=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
