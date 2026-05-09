"""
Users App — Selectors (Convention HackSoft)

Requêtes en lecture seule pour l'interface d'habilitation.
Les selectors ne modifient jamais la base de données.

Spécifications couvertes :
    - FR3  : Liste des comptes à habiliter
    - FR28 : Filtrage par périmètre RBAC
"""
from django.db.models import QuerySet

from apps.users.models import Department, User


def get_shell_accounts() -> QuerySet[User]:
    """Retourne les comptes « coquilles vides » (sans rôle)."""
    return User.objects.filter(role="").select_related("department")


def get_all_manageable_users() -> QuerySet[User]:
    """Retourne tous les utilisateurs non-superuser pour la gestion."""
    return (
        User.objects.filter(is_superuser=False)
        .select_related("department")
        .order_by("role", "username")
    )


def get_active_departments() -> QuerySet[Department]:
    """Retourne les départements actifs pour les listes déroulantes."""
    return Department.objects.filter(is_active=True).order_by("name")
