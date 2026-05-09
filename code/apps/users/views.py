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
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, TemplateView

from . import selectors, services
from .mixins import AdminRequiredMixin, AuditAdminRequiredMixin
from .models import Department, User
from .forms import DepartmentForm, ITUserCreationForm


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
            
        #TODO: Redirections spécifiques par rôle (Dashboards - Epic 6)
        # if user.role == User.Role.AUDIT: return reverse_lazy("dashboards:audit")
        # if user.role == User.Role.DM: return reverse_lazy("dashboards:dm")
            
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


class HabilitationListView(AuditAdminRequiredMixin, ListView):
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


class HabilitationEditView(AuditAdminRequiredMixin, View):
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

        return redirect("auth:habilitation-list")


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

        return redirect("auth:habilitation-list")


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


class OrganigrammeListView(AdminRequiredMixin, TemplateView):
    """
    Liste hiérarchique des départements (Story 1.4 / AC2, AC3).

    Affiche l'arborescence complète de l'organigramme BICEC.
    Les opérations CRUD sont effectuées via HTMX.
    """
    template_name = "admin_it/organigramme_list.html"

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get("parent_id")
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


class DepartmentCreateView(AdminRequiredMixin, View):
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


class DepartmentEditView(AdminRequiredMixin, View):
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


class DepartmentDeleteView(AdminRequiredMixin, View):
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


class DepartmentSearchView(AdminRequiredMixin, View):
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

