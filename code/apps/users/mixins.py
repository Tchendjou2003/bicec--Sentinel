"""
Users App — Mixins de sécurité (Convention HackSoft)

Mixins réutilisables pour les vues nécessitant des permissions spécifiques.

Spécifications couvertes :
    - ADR-10 : Séparation des fonctions (SoD)
    - FR3    : Attribution des rôles réservée aux Audit Admin
    - FR36   : Délégation is_audit_admin
    - Story 6.2.0 : ProvisioningApproverRequiredMixin (groupe IT Maker/Checker)
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


class ProvisioningApproverRequiredMixin(LoginRequiredMixin):
    """
    Mixin — Restreint l'accès aux membres du groupe « Administrateurs Sentinel »
    ou aux superusers (Story 6.2.0 / AC4).

    Protège les vues de gestion des habilitations, de l'organigramme et du
    flux de validation Maker/Checker. Remplace ``AuditAdminRequiredMixin``
    sur ces vues (coupure Audit → IT).
    """

    def dispatch(self, request, *args, **kwargs):
        from .services import user_is_provisioning_approver
        if request.user.is_authenticated and not user_is_provisioning_approver(request.user):
            raise PermissionDenied(
                "Accès réservé aux membres du groupe « Administrateurs Sentinel »."
            )
        return super().dispatch(request, *args, **kwargs)


class ProvisioningListAccessMixin(LoginRequiredMixin):
    """
    Mixin — Accès à la file des demandes de provisioning (Story 6.2.0).

    Autorise **deux profils** :
      - les Admin IT (makers, role=ADMIN / staff) → voient leurs propres demandes ;
      - les membres du groupe « Administrateurs Sentinel » (checkers) → voient tout.

    Le filtrage du queryset (maker = ses demandes / checker = toutes) est géré
    dans la vue ``ProvisioningRequestListView.get_queryset``. Ce mixin ne fait
    que le contrôle d'accès combiné. Les superusers passent toujours.
    """

    def dispatch(self, request, *args, **kwargs):
        from .models import User
        from .services import user_is_provisioning_approver

        if request.user.is_authenticated:
            is_admin_it = (
                request.user.role == User.Role.ADMIN
                or request.user.is_staff
                or request.user.is_superuser
            )
            if not (is_admin_it or user_is_provisioning_approver(request.user)):
                raise PermissionDenied(
                    "Accès réservé aux Admin IT et aux membres du groupe "
                    "« Administrateurs Sentinel »."
                )
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


class WorkflowAccessMixin(LoginRequiredMixin):
    """
    Mixin — Restreint l'accès aux acteurs du workflow (Story 3.1).

    Autorise les rôles AUDIT, DM, ETP, DG et superuser.
    Protège les vues de consultation (Liste et Détail).
    """

    def dispatch(self, request, *args, **kwargs):
        from .models import User
        if request.user.is_authenticated and not (
            request.user.role in [User.Role.AUDIT, User.Role.DM, User.Role.ETP, User.Role.DG]
            or request.user.is_superuser
        ):
            raise PermissionDenied("Accès réservé aux acteurs du workflow.")
        return super().dispatch(request, *args, **kwargs)
