"""
Users App — Middleware de sécurité
"""
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


class IdleTimeoutMiddleware:
    """
    Déconnecte l'utilisateur après 30 min d'inactivité (NFR-SEC-02).

    Fonctionne indépendamment de SESSION_COOKIE_AGE comme filet de
    sécurité applicatif. Exclut les routes publiques pour éviter
    les boucles de redirection.
    """

    # Routes exclues du contrôle d'inactivité
    PUBLIC_PATHS = ("/auth/", "/admin/login/")

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, "SESSION_COOKIE_AGE", 1800)
        # Normalisation des préfixes
        self.static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        self.media_prefix = "/" + settings.MEDIA_URL.lstrip("/")

    def __call__(self, request):
        # Ne pas traiter les routes publiques ni les requêtes statiques/media
        if any(request.path.startswith(p) for p in self.PUBLIC_PATHS):
            return self.get_response(request)
            
        # Utilisation des préfixes normalisés
        if request.path.startswith(self.static_prefix) or request.path.startswith(self.media_prefix):
            return self.get_response(request)

        if request.user.is_authenticated:
            now = time.time()
            last_activity = request.session.get("_last_activity")

            if last_activity and (now - last_activity) > self.timeout:
                logout(request)
                messages.info(request, _("Session expirée pour inactivité."))
                return redirect(settings.LOGIN_URL)

            request.session["_last_activity"] = now

        return self.get_response(request)


class RoleRequiredMiddleware:
    """
    Protection globale (ADR-10, FR37) bloquant l'accès aux comptes 
    « coquilles vides » (sans rôle).
    
    Intercepte toutes les requêtes des utilisateurs authentifiés.
    Si l'utilisateur n'a pas de rôle, il est redirigé vers la page 
    d'attente, sauf s'il essaie d'accéder aux routes publiques (login, logout, pending).
    """
    
    # Routes accessibles même pour une coquille vide
    ALLOWED_PATHS = (
        "/auth/login/",
        "/auth/logout/",
        "/auth/pending/",
        "/admin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Normalisation des préfixes
        self.static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        self.media_prefix = "/" + settings.MEDIA_URL.lstrip("/")

    def __call__(self, request):
        # Vérification des requêtes statiques/media
        if request.path.startswith(self.static_prefix) or request.path.startswith(self.media_prefix):
            return self.get_response(request)

        # Si l'utilisateur est connecté et est une coquille vide
        if request.user.is_authenticated and request.user.is_shell_account:
            # S'il tente d'accéder à une route NON autorisée, on le redirige vers /auth/pending/
            # Note: Le Django Admin gère ses propres permissions (is_staff). 
            # Le RSSI est une coquille vide (is_shell_account = True ? Non, le RSSI a role="RSSI", donc has_role = True, is_shell_account = False).
            # Les VRAIES coquilles vides n'ont aucun rôle.
            if not any(request.path.startswith(p) for p in self.ALLOWED_PATHS):
                return redirect(reverse_lazy("auth:pending"))

        return self.get_response(request)
