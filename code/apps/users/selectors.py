"""
Users App — Selectors (Convention HackSoft)

Requêtes en lecture seule pour l'interface d'habilitation.
Les selectors ne modifient jamais la base de données.

Spécifications couvertes :
    - FR3  : Liste des comptes à habiliter
    - FR28 : Filtrage par périmètre RBAC
"""
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.db.models import QuerySet, Count, Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from uuid import UUID

from .models import Department, OrgUnitType, User, UserProvisioningRequest


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


def get_departments_tree() -> QuerySet[Department]:
    """Racines actives avec enfants récursifs prefetchés (4 niveaux)."""
    return (
        Department.objects.filter(is_active=True, parent__isnull=True)
        .select_related("type")
        .prefetch_related(
            "children__type",
            "children__children__type",
            "children__children__children__type",
            "children__children__children__children__type",
        )
        .order_by("name")
    )


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


# ── Monitoring & Surveillance (Story 7.1) ─────────────────────────────────────

def get_active_lockouts() -> list[dict]:
    """Retourne les entrées axes AccessAttempt (comptes bloqués)."""
    try:
        from axes.models import AccessAttempt
        return list(
            AccessAttempt.objects
            .order_by("-attempt_time")
            .values("id", "username", "ip_address", "failures_since_start", "attempt_time")
        )
    except ImportError:
        return []


def get_active_sessions() -> list[dict]:
    """Retourne les sessions Django non expirées avec utilisateur résolu."""
    now = timezone.now()
    sessions = Session.objects.filter(expire_date__gt=now).order_by("-expire_date")
    result = []
    user_cache: dict[str, User | None] = {}
    for session in sessions:
        try:
            data = session.get_decoded()
        except Exception:
            continue
        user_id = data.get("_auth_user_id")
        if not user_id:
            continue
        if user_id not in user_cache:
            user_cache[user_id] = (
                User.objects.filter(pk=user_id)
                .select_related("department")
                .first()
            )
        user = user_cache[user_id]
        if user:
            result.append({
                "session_key": session.session_key,
                "expire_date": session.expire_date,
                "user": user,
                "is_superuser": user.is_superuser,
            })
    return result


def get_inactive_users(days: int = 30) -> QuerySet[User]:
    """Retourne les utilisateurs non superusers sans activité depuis `days` jours."""
    cutoff = timezone.now() - timedelta(days=days)
    return (
        User.objects.filter(is_superuser=False)
        .filter(Q(last_login__lt=cutoff) | Q(last_login__isnull=True))
        .select_related("department")
        .order_by("last_login", "username")
    )


def get_worker_health() -> dict:
    """Retourne les stats de santé du worker Django-Q."""
    try:
        from django_q.models import OrmQ, Success, Failure
        cutoff = timezone.now() - timedelta(hours=24)
        queued = OrmQ.objects.count()
        successes = Success.objects.filter(stopped__gte=cutoff).count()
        failures = Failure.objects.filter(stopped__gte=cutoff).count()
        last_success = Success.objects.order_by("-stopped").values_list("stopped", flat=True).first()
        total = successes + failures
        error_rate = round(failures / total * 100) if total > 0 else 0
        return {
            "queued": queued,
            "successes_24h": successes,
            "failures_24h": failures,
            "last_success": last_success,
            "error_rate": error_rate,
            "status": "alert" if error_rate >= 5 else "ok",
        }
    except ImportError:
        return {
            "queued": 0, "successes_24h": 0, "failures_24h": 0,
            "last_success": None, "error_rate": 0, "status": "unknown",
        }


def get_usage_stats() -> dict:
    """Retourne des statistiques d'utilisation applicative."""
    cutoff_30d = timezone.now() - timedelta(days=30)
    active_30d = User.objects.filter(
        is_superuser=False, last_login__gte=cutoff_30d
    ).count()
    role_breakdown = (
        User.objects.filter(is_superuser=False)
        .values("role")
        .annotate(count=Count("id"))
        .order_by("role")
    )
    return {
        "active_30d": active_30d,
        "role_breakdown": list(role_breakdown),
    }


def get_pending_provisioning_count() -> int:
    """Retourne le nombre de demandes de provisioning en attente."""
    return UserProvisioningRequest.objects.filter(
        status=UserProvisioningRequest.Status.PENDING
    ).count()
