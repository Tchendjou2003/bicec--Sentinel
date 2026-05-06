"""
Users App — Views (Auth & Onboarding)

Implémentation de l'authentification et de la redirection conditionnelle
basée sur le RBAC (Role-Based Access Control) et la gouvernance ADR-10.

Spécifications couvertes :
    - FR1 : Authentification locale
    - FR37 : Redirection des comptes sans rôle (coquilles vides)
    - ADR-10 : Séparation des comptes techniques et des habilitations
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from apps.users.models import User


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
