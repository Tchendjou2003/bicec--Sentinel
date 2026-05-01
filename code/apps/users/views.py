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
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.users import selectors, services
from apps.users.models import Department, User


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
        - Un RSSI est redirigé vers le Django Admin.
        - Les autres rôles sont redirigés vers leur tableau de bord respectif
          (temporairement vers la page d'accueil si le dashboard n'existe pas encore).
        """
        user: User = self.request.user
        
        if user.is_shell_account:
            return reverse_lazy("auth:pending")
        if user.role == User.Role.RSSI or user.is_staff:
            return reverse_lazy("admin:index")
            
        #TODO: Redirections spécifiques par rôle (Dashboards - Epic 6)
        # if user.role == User.Role.AUDIT: return reverse_lazy("dashboards:audit")
        # if user.role == User.Role.DM: return reverse_lazy("dashboards:dm")
            
        return super().get_success_url()


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
            return redirect(reverse_lazy("home"))
            
        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# Habilitation Audit (Story 1.5 + 1.7)
# =============================================================================


class HabilitationListView(LoginRequiredMixin, ListView):
    """
    Liste des utilisateurs pour l'interface d'habilitation (FR3).

    Accessible uniquement aux auditeurs avec is_audit_admin=True
    ou aux superusers (bootstrapping initial).
    Intègre le toggle is_audit_admin inline (Story 1.7 / FR36).
    """

    template_name = "habilitation/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.can_manage_users or request.user.is_superuser):
            raise PermissionDenied("Accès réservé aux administrateurs Audit.")
        return super().dispatch(request, *args, **kwargs)

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
        context["total_shell"] = User.objects.filter(role="").count()
        return context


class HabilitationEditView(LoginRequiredMixin, View):
    """
    Formulaire d'édition du rôle et département d'un utilisateur (FR3).

    GET  : affiche le formulaire pré-rempli.
    POST : appelle le service assign_role() et redirige.
    """

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.can_manage_users or request.user.is_superuser):
            raise PermissionDenied("Accès réservé aux administrateurs Audit.")
        return super().dispatch(request, *args, **kwargs)

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
            )
            messages.success(
                request,
                f"Rôle '{target_user.get_role_display()}' attribué à "
                f"{target_user.username}.",
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect("auth:habilitation-list")


class HabilitationToggleAdminView(LoginRequiredMixin, View):
    """
    Toggle inline du flag is_audit_admin (Story 1.7 / FR36).

    Appelé en POST depuis la liste d'habilitation (bouton dans la ligne).
    Inverse la valeur actuelle du flag pour un Auditeur Interne.
    """

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.can_manage_users or request.user.is_superuser):
            raise PermissionDenied("Accès réservé aux administrateurs Audit.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        new_value = not target_user.is_audit_admin

        try:
            services.toggle_audit_admin(
                target_user=target_user,
                grant=new_value,
                performed_by=request.user,
            )
            action = "accordée" if new_value else "révoquée"
            messages.success(
                request,
                f"Délégation admin {action} pour {target_user.username}.",
            )
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))

        return redirect("auth:habilitation-list")
