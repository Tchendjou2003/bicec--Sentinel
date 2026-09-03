from django.conf import settings

from .models import User

# Constante de module — évaluée une seule fois au démarrage (pas à chaque requête)
_SIDEBAR_MAP = {
    User.Role.ADMIN: "partials/sidebar_admin.html",
    User.Role.AUDIT: "partials/sidebar_audit.html",
    User.Role.DM: "partials/sidebar_dm.html",
    User.Role.ETP: "partials/sidebar_etp.html",
    User.Role.DG: "partials/sidebar_dg.html",
    User.Role.EXT: "partials/sidebar_audit_ext.html",
}


def sidebar_context(request):
    """
    Injecte le chemin du template de sidebar adapté au rôle
    de l'utilisateur connecté dans tous les templates.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}

    role = getattr(request.user, "role", None)
    sidebar = _SIDEBAR_MAP.get(role, "partials/sidebar_default.html")  # type: ignore

    # Appartenance au groupe « Administrateurs Sentinel » (Story 6.2.0)
    # Permet aux templates de masquer les liens réservés au groupe (organigramme, types).
    is_provisioning_approver = (
        request.user.is_superuser
        or request.user.groups.filter(
            name=settings.PROVISIONING_APPROVER_GROUP_NAME
        ).exists()
    )

    return {
        "sidebar_template": sidebar,
        "user_role_label": request.user.get_role_display() if role else "Non habilité",
        "user_is_provisioning_approver": is_provisioning_approver,
    }
