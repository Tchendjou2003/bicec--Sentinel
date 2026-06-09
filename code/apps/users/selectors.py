"""
Users App — Selectors (Convention HackSoft)

Requêtes en lecture seule pour l'interface d'habilitation.
Les selectors ne modifient jamais la base de données.

Spécifications couvertes :
    - FR3  : Liste des comptes à habiliter
    - FR28 : Filtrage par périmètre RBAC
"""
from django.db.models import QuerySet, Count, Q
from django.core.exceptions import ValidationError
from uuid import UUID

from .models import Department, OrgUnitType, User


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
    return Department.objects.filter(is_active=True).select_related("type").order_by("name")


def get_all_org_unit_types() -> QuerySet[OrgUnitType]:
    """
    Retourne tous les types d'unités organisationnelles, actifs et inactifs,
    triés par niveau indicatif puis libellé.
    """
    return OrgUnitType.objects.all().order_by("level", "name")


def get_active_org_unit_types() -> QuerySet[OrgUnitType]:
    """Retourne les types d'unités actifs pour les listes déroulantes."""
    return OrgUnitType.objects.filter(is_active=True).order_by("level", "name")


def count_shell_accounts() -> int:
    """Retourne le nombre de comptes « coquilles vides » (sans rôle)."""
    return User.objects.filter(role="").count()


def count_total_users() -> int:
    """Retourne le nombre total d'utilisateurs non-superuser."""
    return User.objects.filter(is_superuser=False).count()


def count_departments() -> int:
    """Retourne le nombre de départements actifs."""
    return Department.objects.filter(is_active=True).count()


def get_departments_for_level(parent_id: UUID | str | None = None) -> QuerySet[Department]:
    """
    Retourne les départements d'un niveau spécifique (racines si None)
    avec annotation dynamique du nombre d'enfants actifs.
    """
    qs = Department.objects.filter(is_active=True)
    if parent_id:
        try:
            qs = qs.filter(parent_id=parent_id)
        except (ValueError, ValidationError):
            return Department.objects.none()
    else:
        qs = qs.filter(parent__isnull=True)
    
    # Annotation du nombre d'enfants actifs (optimisation)
    qs = qs.annotate(
        child_count=Count("children", filter=Q(children__is_active=True))
    ).order_by("name")
    return qs


def get_department_breadcrumb(department_id: UUID | str) -> list[Department]:
    """
    Remonte récursivement l'arbre pour générer le fil d'Ariane.
    Retourne une liste ordonnée de la racine vers la feuille.
    """
    try:
        dept = Department.objects.get(pk=department_id, is_active=True)
    except (Department.DoesNotExist, ValueError, ValidationError):
        return []
        
    breadcrumb = []
    current = dept
    depth = 0
    while current and depth < 10:  # Sécurité anti-boucle
        breadcrumb.insert(0, current)
        current = current.parent
        depth += 1
    return breadcrumb


def search_departments(query: str, limit: int = 10) -> QuerySet[Department]:
    """
    Recherche globale dans l'organigramme (insensible à la casse).
    Inclut un prefetch du chemin ascendant via la relation de la base.
    """
    if not query or len(query.strip()) < 2:
        return Department.objects.none()
        
    qs = Department.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query),
        is_active=True
    ).select_related("parent", "parent__parent").order_by("name")[:limit]
    
    return qs
