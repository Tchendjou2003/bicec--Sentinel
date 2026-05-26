"""
Workflow App — Selectors (Convention HackSoft)

Fonctions de lecture seule pour les recommandations.
Aucune mutation ici — tout passe par services.py.

Spécifications couvertes :
    - FR28 : Visibilité restreinte par périmètre RBAC
"""
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .models import EvidenceSubmission, ExtensionRequest, Recommendation


def get_recommendations_for_user(*, user, filters: dict | None = None) -> QuerySet[Recommendation]:
    """
    Retourne toutes les recommandations visibles pour un utilisateur (FR28).

    Logique RBAC :
    - AUDIT / superuser : Voient tout le périmètre.
    - DM / DG : Ne voient que leur département, et jamais les brouillons (DRAFT).
    - ETP : Ne voient que ce qui leur est explicitement assigné, et jamais les brouillons.

    Args:
        user: L'utilisateur connecté.
        filters: Dictionnaire optionnel de filtres (source, status, priority, q, import_status).

    Returns:
        QuerySet: Recommandations triées (-is_overdue, -created_at).
    """
    from apps.users.models import User

    qs = (
        Recommendation.objects
        .select_related("created_by", "department", "controlled_department", "assigned_dm", "assigned_etp")
        .all()
    )

    # 1. Filtre RBAC strict
    if not (user.role == User.Role.AUDIT or user.is_superuser):
        qs = qs.exclude(status=Recommendation.Status.DRAFT)
        
        if user.role in [User.Role.DM, User.Role.DG]:
            if user.department:
                dept_ids = get_department_and_descendants_ids(user.department)
                qs = qs.filter(department_id__in=dept_ids)
            else:
                return qs.none()
        elif user.role == User.Role.ETP:
            qs = qs.filter(assigned_etp=user)
        else:
            # Sécurité défensive (Fail-Closed) pour les rôles non pris en charge (ex: ADMIN, EXT)
            return qs.none()

    # 2. Application des filtres utilisateur
    if filters:
        source = filters.get("source")
        status = filters.get("status")
        priority = filters.get("priority")
        search = filters.get("q")
        import_status = filters.get("import_status", "recent")

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

        # Filtre Historique vs Récent (Story 3.1)
        from django.db.models import Q
        if import_status == "historical":
            qs = qs.filter(Q(import_tag__isnull=False) & ~Q(import_tag=""))
        elif import_status == "recent":
            qs = qs.filter(Q(import_tag__isnull=True) | Q(import_tag=""))
        elif import_status == "all":
            pass

    # 3. Tri optimisé
    return qs.order_by("-is_overdue", "-created_at")


def get_recommendation_by_id(*, pk, user) -> Recommendation:
    """
    Retourne une recommandation par son PK avec contrôle RBAC strict (FR28).

    Utilise get_recommendations_for_user() comme base pour garantir
    que l'utilisateur ne peut accéder qu'aux recommandations de son périmètre.

    Args:
        pk: UUID de la recommandation.
        user: L'utilisateur connecté — appliqué au filtre RBAC.

    Returns:
        Recommendation: L'instance trouvée et autorisée.

    Raises:
        Http404: Si la recommandation n'existe pas, est soft-deleted,
                 ou est hors périmètre RBAC de l'utilisateur.
    """
    qs = get_recommendations_for_user(user=user).select_related(
        "created_by", "department", "controlled_department",
        "assigned_dm", "assigned_etp",
    )
    return get_object_or_404(qs, pk=pk)


def get_recommendation_detail_for_user(*, pk, user) -> Recommendation:
    """
    Retourne une recommandation avec ses livrables pour la page de détail,
    avec contrôle RBAC strict (FR28).

    Utilise get_recommendations_for_user() comme base pour garantir
    que l'utilisateur ne peut voir que les recommandations de son périmètre.
    Précharge les livrables pour optimiser le rendu de la page de détail.

    Args:
        pk: UUID de la recommandation.
        user: L'utilisateur connecté — appliqué au filtre RBAC.

    Returns:
        Recommendation: L'instance avec livrables préchargés et autorisée.

    Raises:
        Http404: Si la recommandation n'existe pas, est soft-deleted,
                 ou est hors périmètre RBAC de l'utilisateur.
    """
    qs = get_recommendations_for_user(user=user).select_related(
        "created_by", "department", "controlled_department",
        "assigned_dm", "assigned_etp",
    ).prefetch_related("deliverables")
    return get_object_or_404(qs, pk=pk)


def get_department_and_descendants_ids(department) -> list:
    """
    Retourne la liste des IDs du département et de tous ses descendants (enfants, petits-enfants...).
    Permet d'inclure les sous-directions, départements et services d'une Direction.
    """
    if not department:
        return []
    ids = [department.id]
    current_level_ids = [department.id]
    
    from apps.users.models import Department
    while current_level_ids:
        children_ids = list(
            Department.objects.filter(parent_id__in=current_level_ids, is_active=True)
            .values_list("id", flat=True)
        )
        ids.extend(children_ids)
        current_level_ids = children_ids
        
    return ids


def get_available_dms_for_department(*, department) -> QuerySet:
    """
    Retourne les Directeurs Métier actifs rattachés à un département ou ses sous-départements.

    Utilisé par le formulaire d'assignation (Story 2.5 / AC2).

    Args:
        department: Instance OrganizationalUnit (Direction cible).

    Returns:
        QuerySet[User]: DMs actifs filtrés par la branche du département.
    """
    from apps.users.models import User
    dept_ids = get_department_and_descendants_ids(department)

    return User.objects.filter(
        role=User.Role.DM,
        department_id__in=dept_ids,
        is_active=True,
    ).order_by("last_name", "first_name")


def get_evidence_for_recommendation(*, recommendation, user=None) -> QuerySet[EvidenceSubmission]:
    """
    Retourne les soumissions de preuves publiées pour une recommandation.

    Exclut les brouillons DRAFT (visibles uniquement par leur auteur
    dans le slide-over de soumission — PRD v2 FR15).

    Règle de chaîne de commandement (FR20) :
        - ETP / DM / DG (participants) : voient toutes les soumissions non-DRAFT.
        - Audit / superuser : ne voient les preuves que lorsque la recommandation
          a atteint PENDING_AUDIT_REVIEW ou CLOSED_RESOLVED (après validation DM).
          Cela garantit que la revue interne DM ↔ ETP reste une affaire
          départementale et que l'Audit ne reçoit que le dossier « signé » par le DM.

    Args:
        recommendation: L'instance Recommendation.
        user: L'utilisateur connecté (optionnel pour rétro-compatibilité).

    Returns:
        QuerySet[EvidenceSubmission]: Soumissions PENDING/ACCEPTED/REJECTED triées.
    """
    from apps.users.models import User

    # Si l'utilisateur est Audit ou superuser, vérifier le statut de la recommandation
    if user and (user.role == User.Role.AUDIT or user.is_superuser):
        audit_visible_statuses = [
            Recommendation.Status.PENDING_AUDIT_REVIEW,
            Recommendation.Status.CLOSED_RESOLVED,
        ]
        if recommendation.status not in audit_visible_statuses:
            return EvidenceSubmission.objects.none()

    qs = (
        EvidenceSubmission.objects
        .filter(recommendation=recommendation)
        .exclude(status=EvidenceSubmission.SubmissionStatus.DRAFT)
        .select_related("submitted_by")
        .prefetch_related("files")
    )

    # Rôles de contrôle externe : seulement les soumissions acceptées par le DM
    if user and user.role in (User.Role.AUDIT, User.Role.EXT) and not user.is_superuser:
        qs = qs.filter(status=EvidenceSubmission.SubmissionStatus.ACCEPTED)

    return qs.order_by("-created_at")


def get_available_etps_for_department(*, department) -> QuerySet:
    """
    Retourne les Employés Traitants (ETP) actifs rattachés à un département ou ses sous-départements.

    Utilisé par le formulaire de délégation (Story 3.2 / AC1, AC3).

    Args:
        department: Instance Department (Direction cible).

    Returns:
        QuerySet[User]: ETPs actifs filtrés par la branche du département.
    """
    from apps.users.models import User
    dept_ids = get_department_and_descendants_ids(department)

    return User.objects.filter(
        role=User.Role.ETP,
        department_id__in=dept_ids,
        is_active=True,
    ).order_by("last_name", "first_name")


def get_draft_submission_for_recommendation(
    *, recommendation, user
) -> EvidenceSubmission | None:
    """
    Retourne le brouillon DRAFT actif de l'utilisateur pour une recommandation.

    Args:
        recommendation: L'instance Recommendation.
        user: L'utilisateur auteur du brouillon.

    Returns:
        EvidenceSubmission | None: Le brouillon actif ou None.
    """
    return (
        EvidenceSubmission.objects
        .filter(
            recommendation=recommendation,
            submitted_by=user,
            status=EvidenceSubmission.SubmissionStatus.DRAFT,
        )
        .select_related("submitted_by")
        .prefetch_related("files")
        .first()
    )


# =============================================================================
# Sélecteurs Report d'Échéance (Story 3.6)
# =============================================================================


def get_pending_extension_for_recommendation(
    *, recommendation
) -> ExtensionRequest | None:
    """
    Retourne la demande de report PENDING pour une recommandation, ou None.

    Args:
        recommendation: L'instance Recommendation.

    Returns:
        ExtensionRequest | None: La demande en attente, ou None si aucune.
    """
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation, status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by")
        .first()
    )


def get_extension_history_for_recommendation(
    *, recommendation
) -> QuerySet[ExtensionRequest]:
    """
    Retourne l'historique des demandes de report (APPROVED + REJECTED)
    pour une recommandation, triées du plus récent au plus ancien.

    Exclut les demandes PENDING (gérées séparément par get_pending_extension_for_recommendation).

    Args:
        recommendation: L'instance Recommendation.

    Returns:
        QuerySet[ExtensionRequest]: Historique APPROVED/REJECTED.
    """
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation)
        .exclude(status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by", "reviewed_by")
        .order_by("-reviewed_at")
    )

