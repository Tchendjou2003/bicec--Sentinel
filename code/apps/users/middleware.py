"""
Users App — Middleware de sécurité
"""
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied


class IdleTimeoutMiddleware:
    """
    Déconnecte l'utilisateur après 30 min d'inactivité (NFR-SEC-02).

    Fonctionne indépendamment de SESSION_COOKIE_AGE comme filet de
    sécurité applicatif. Exclut les routes publiques pour éviter
    les boucles de redirection.
    """

    # Routes exclues du contrôle d'inactivité (paths exacts, PAS de préfixe large)
    PUBLIC_PATHS = ("/auth/login/", "/auth/logout/", "/auth/pending/", "/admin/login/")

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
    # Note : /admin/ retiré volontairement (M2) — les superusers sont déjà exclus
    ALLOWED_PATHS = (
        "/auth/login/",
        "/auth/logout/",
        "/auth/pending/",
        "/auth/external/",
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
        # Les superusers ne sont jamais bloqués (bootstrapping initial).
        if (
            request.user.is_authenticated
            and request.user.is_shell_account
            and not request.user.is_superuser
        ):
            if not any(request.path.startswith(p) for p in self.ALLOWED_PATHS):
                return redirect(reverse("auth:pending"))

        return self.get_response(request)


class ExternalIsolationMiddleware:
    """
    Middleware de sécurité pour l'isolation des auditeurs externes (Story 1.3).

    Deux protections complémentaires :
        1. **Read-Only (AC1)** : Bloque toute requête en écriture (POST, PUT,
           PATCH, DELETE) sauf la déconnexion (/auth/logout/).
        2. **Isolation des vues (AC3)** : Interdit l'accès aux URLs internes
           (home, admin, gestion) et redirige vers le dashboard externe.

    Ce middleware agit APRÈS l'authentification et le RoleRequiredMiddleware.
    """

    # Seules les routes autorisées pour un utilisateur externe
    EXTERNAL_ALLOWED_PATHS = (
        "/auth/login/",
        "/auth/logout/",
        "/auth/external/",
    )

    # Méthodes HTTP en écriture
    WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")

    # Routes autorisées en POST (même pour les EXT)
    WRITE_EXCEPTIONS = (
        "/auth/logout/",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Normalisation des préfixes (cohérent avec IdleTimeout et RoleRequired)
        self.static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        self.media_prefix = "/" + settings.MEDIA_URL.lstrip("/")

    def __call__(self, request):
        # Ne pas traiter les fichiers statiques/media
        if request.path.startswith(self.static_prefix) or request.path.startswith(self.media_prefix):
            return self.get_response(request)

        # Ne s'applique qu'aux utilisateurs externes authentifiés
        # On vérifie à la fois la propriété is_external et le rôle (M-04)
        is_ext = getattr(request.user, "is_external", False) or getattr(request.user, "role", None) == "EXT"
        if not (request.user.is_authenticated and is_ext):
            return self.get_response(request)

        # --- AC1 : Blocage des écritures ---
        if request.method in self.WRITE_METHODS:
            if not any(request.path == p for p in self.WRITE_EXCEPTIONS):
                raise PermissionDenied(
                    "Accès refusé : les auditeurs externes n'ont pas "
                    "le droit de modifier des données."
                )

        # --- AC3 : Blocage des vues internes ---
        if not any(request.path.startswith(p) for p in self.EXTERNAL_ALLOWED_PATHS):
            # UX (M-05) : Redirection gracieuse si tentative d'accès au login admin
            if request.path.startswith("/admin/login"):
                return redirect(reverse("auth:external-dashboard"))
            
            raise PermissionDenied(
                "Accès refusé : cette section est réservée aux "
                "utilisateurs internes de la BICEC."
            )

        return self.get_response(request)
