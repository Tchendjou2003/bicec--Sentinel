"""
Workflow App — Selectors (Convention HackSoft)

Fonctions de lecture seule pour les recommandations.
Aucune mutation ici — tout passe par services.py.

Spécifications couvertes :
    - FR28 : Visibilité restreinte par périmètre RBAC
"""
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .models import Recommendation


def get_recommendations_for_audit(*, user, filters: dict | None = None) -> QuerySet[Recommendation]:
    """
    Retourne toutes les recommandations non-supprimées.

    Pour le rôle Audit, il n'y a pas de filtre par département —
    les auditeurs voient tout le périmètre.

    Args:
        user: L'utilisateur connecté (rôle AUDIT vérifié par le mixin).
        filters: Dictionnaire optionnel de filtres (source, status, priority, q).

    Returns:
        QuerySet: Recommandations triées par date de création (desc).
    """
    qs = (
        Recommendation.objects
        .select_related("created_by", "department", "controlled_department", "assigned_dm")
        .all()
    )

    if filters:
        source = filters.get("source")
        status = filters.get("status")
        priority = filters.get("priority")
        search = filters.get("q")

        if source:
            qs = qs.filter(source=source)
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(reference__icontains=search) | Q(mission_label__icontains=search)
            )

    return qs


def get_recommendation_by_id(*, pk, user) -> Recommendation:
    """
    Retourne une recommandation par son PK avec contrôle RBAC basique.

    Le mixin AuditRequiredMixin a déjà vérifié le rôle.
    On utilise le manager par défaut (exclut les soft-deleted).

    Args:
        pk: UUID de la recommandation.
        user: L'utilisateur connecté.

    Returns:
        Recommendation: L'instance trouvée.

    Raises:
        Http404: Si la recommandation n'existe pas ou est soft-deleted.
    """
    return get_object_or_404(
        Recommendation.objects.select_related(
            "created_by", "department", "controlled_department",
            "assigned_dm", "assigned_etp",
        ),
        pk=pk,
    )


def get_recommendation_detail(*, pk) -> Recommendation:
    """
    Retourne une recommandation avec ses livrables pour la page de détail.

    Utilise prefetch_related pour optimiser le chargement des livrables.

    Args:
        pk: UUID de la recommandation.

    Returns:
        Recommendation: L'instance avec livrables préchargés.

    Raises:
        Http404: Si la recommandation n'existe pas.
    """
    return get_object_or_404(
        Recommendation.objects
        .select_related(
            "created_by", "department", "controlled_department",
            "assigned_dm", "assigned_etp",
        )
        .prefetch_related("deliverables"),
        pk=pk,
    )


def get_available_dms_for_department(*, department) -> QuerySet:
    """
    Retourne les Directeurs Métier actifs rattachés à un département.

    Utilisé par le formulaire d'assignation (Story 2.5 / AC2).

    Args:
        department: Instance OrganizationalUnit (Direction cible).

    Returns:
        QuerySet[User]: DMs actifs filtrés par département.
    """
    from apps.users.models import User

    return User.objects.filter(
        role=User.Role.DM,
        department=department,
        is_active=True,
    ).order_by("last_name", "first_name")

