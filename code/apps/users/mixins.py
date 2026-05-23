"""
Users App — Mixins de sécurité (Convention HackSoft)

Mixins réutilisables pour les vues nécessitant des permissions spécifiques.

Spécifications couvertes :
    - ADR-10 : Séparation des fonctions (SoD)
    - FR3    : Attribution des rôles réservée aux Audit Admin
    - FR36   : Délégation is_audit_admin
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class AuditAdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin — Restreint l'accès aux utilisateurs can_manage_users ou superuser.

    Protège les vues d'habilitation (FR3, FR36, ADR-10).
    Un utilisateur sans le droit reçoit un 403 Forbidden.
    Les utilisateurs non connectés sont redirigés vers le login (via LoginRequiredMixin).

    Usage :
        class MaVue(AuditAdminRequiredMixin, ListView):
            ...
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (
            request.user.can_manage_users or request.user.is_superuser
        ):
            raise PermissionDenied("Accès réservé aux administrateurs Audit.")
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin — Restreint l'accès aux utilisateurs ADMIN ou staff.

    Protège les vues d'administration IT (Story 1.4, ADR-10).
    """

    def dispatch(self, request, *args, **kwargs):
        from .models import User
        if request.user.is_authenticated and not (
            request.user.role == User.Role.ADMIN
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise PermissionDenied("Accès réservé aux administrateurs IT.")
        return super().dispatch(request, *args, **kwargs)


class AuditRequiredMixin(LoginRequiredMixin):
    """
    Mixin — Restreint l'accès aux utilisateurs de rôle AUDIT ou superusers.

    Protège les vues du workflow des recommandations (Story 2.1, AC7).
    Les brouillons ne sont visibles que par le pool Audit.
    """

    def dispatch(self, request, *args, **kwargs):
        from .models import User
        if request.user.is_authenticated and not (
            request.user.role == User.Role.AUDIT
            or request.user.is_superuser
        ):
            raise PermissionDenied("Accès réservé aux Auditeurs Internes.")
        return super().dispatch(request, *args, **kwargs)
