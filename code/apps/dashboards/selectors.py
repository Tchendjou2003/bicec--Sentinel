"""
Dashboards App — Selectors (Convention HackSoft)

Fonctions de lecture seule pour les agrégations et vues dashboard.
Tous les sélecteurs utilisent get_recommendations_for_user() comme base
queryset pour garantir le RBAC fail-closed.
"""
import json
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.workflow.models import Recommendation
from apps.workflow.selectors import get_recommendations_for_user


# =============================================================================
# Helpers partagés (aging, breakdown direction, stacked bar JSON)
# =============================================================================


def _enrich_with_aging(qs) -> list[dict]:
    """
    Enrichit un queryset de recommandations avec leur bande d'aging.

    Logique partagée par les tableaux d'urgence (DM, ETP, DG) :
        - overdue : is_overdue=True → jours depuis original_due_date (positif)
        - warning : due_date <= aujourd'hui + 30j → jours restants
        - ok      : au-delà de J+30

    Returns:
        list[dict] avec clés : rec, aging_band, days_delta
    """
    today = timezone.localdate()
    warning_threshold = today + timedelta(days=30)

    rows = []
    for rec in qs:
        if rec.is_overdue:
            aging_band = "overdue"
            days_delta = (today - rec.original_due_date).days
        elif rec.due_date <= warning_threshold:
            aging_band = "warning"
            days_delta = (rec.due_date - today).days
        else:
            aging_band = "ok"
            days_delta = None

        rows.append({
            "rec": rec,
            "aging_band": aging_band,
            "days_delta": days_delta,
        })

    return rows


def _get_descendants_map():
    """
    Construit en mémoire la carte {direction racine: [ids self + descendants]}.

    Charge tout l'organigramme actif en UNE requête, puis fait la traversée
    en Python — évite les N traversées récursives de
    get_department_and_descendants_ids (une par direction racine).

    Returns:
        tuple (roots, descendants_by_root_id) :
            roots — list[Department] racines (parent=NULL, actives), triées par nom
            descendants_by_root_id — dict {root_id: [ids incluant la racine]}
    """
    from apps.users.models import Department

    # 1 requête : tout l'organigramme actif (id + parent)
    edges = Department.objects.filter(is_active=True).values_list("id", "parent_id")
    children_by_parent: dict = {}
    for dept_id, parent_id in edges:
        children_by_parent.setdefault(parent_id, []).append(dept_id)

    # 1 requête : les racines comme objets (pour accéder à .name)
    roots = list(
        Department.objects.filter(parent__isnull=True, is_active=True).order_by("name")
    )

    descendants_by_root_id = {}
    for root in roots:
        collected = [root.id]
        frontier = [root.id]
        while frontier:
            children = []
            for node_id in frontier:
                children.extend(children_by_parent.get(node_id, []))
            collected.extend(children)
            frontier = children
        descendants_by_root_id[root.id] = collected

    return roots, descendants_by_root_id


def _get_department_breakdown(base_qs) -> list[dict]:
    """
    Calcule la répartition par Direction racine (parent=NULL, active).

    Pour chaque direction de tête, agrège l'arbre complet (direction +
    descendants) : total, overdue, closed, critique_open, taux_cloture,
    overdue_pct, risk_level, et les segments de statut pour les barres empilées.

    L'organigramme est chargé une seule fois (_get_descendants_map). Reste
    une requête .aggregate() par direction racine (volume modéré BICEC).

    Returns:
        list[dict] — un dict par direction racine.
    """
    roots, descendants_by_root_id = _get_descendants_map()

    result = []
    for dept in roots:
        dept_ids = descendants_by_root_id[dept.id]
        dept_qs = base_qs.filter(department_id__in=dept_ids)
        agg = dept_qs.aggregate(
            total=Count("id"),
            overdue=Count("id", filter=Q(is_overdue=True)),
            closed=Count("id", filter=Q(status=Recommendation.Status.CLOSED_RESOLVED)),
            critique_open=Count(
                "id",
                filter=Q(priority=Recommendation.Priority.CRITIQUE)
                & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
            ),
            assigned=Count(
                "id",
                filter=Q(status=Recommendation.Status.ASSIGNED, is_overdue=False),
            ),
            in_progress=Count(
                "id",
                filter=Q(status=Recommendation.Status.IN_PROGRESS, is_overdue=False),
            ),
            pending_dm=Count(
                "id",
                filter=Q(status=Recommendation.Status.PENDING_DM_REVIEW, is_overdue=False),
            ),
            pending_audit=Count(
                "id",
                filter=Q(status=Recommendation.Status.PENDING_AUDIT_REVIEW, is_overdue=False),
            ),
        )

        total = agg["total"] or 0
        closed = agg["closed"] or 0
        overdue = agg["overdue"] or 0
        critique = agg["critique_open"] or 0
        actives = total - closed
        taux = round(closed / total * 100, 1) if total > 0 else 0.0
        overdue_pct = round(overdue / total * 100, 1) if total > 0 else 0.0

        if overdue_pct > 30 or critique > 5:
            risk = "CRITIQUE"
        elif overdue_pct > 15 or critique > 2:
            risk = "MODERE"
        else:
            risk = "FAIBLE"

        result.append({
            "department": dept,
            "total": total,
            "actives": actives,
            "overdue": overdue,
            "overdue_pct": overdue_pct,
            "closed": closed,
            "taux_cloture": taux,
            "critique_open": critique,
            "risk_level": risk,
            "assigned": agg["assigned"] or 0,
            "in_progress": agg["in_progress"] or 0,
            "pending_dm": agg["pending_dm"] or 0,
            "pending_audit": agg["pending_audit"] or 0,
        })

    return result


# Palette de statuts pour les barres empilées (cohérente avec le donut DM)
_STACKED_SEGMENTS = [
    ("overdue", "En retard", "#EF4444"),
    ("assigned", "Assignée", "#3B82F6"),
    ("in_progress", "En cours", "#F59E0B"),
    ("pending_dm", "Validation DM", "#F97316"),
    ("pending_audit", "Validation Audit", "#6366F1"),
    ("closed", "Clôturée", "#10B981"),
]


def _get_stacked_bar_json(dept_breakdown) -> str:
    """
    Convertit un breakdown de directions en JSON Chart.js (barres empilées).

    Réutilise les données déjà en mémoire (pas de requête supplémentaire).

    Returns:
        str — JSON {labels: [...], datasets: [{label, data, backgroundColor}]}
    """
    labels = [d["department"].name for d in dept_breakdown]
    datasets = []
    for key, label, color in _STACKED_SEGMENTS:
        datasets.append({
            "label": label,
            "data": [d[key] for d in dept_breakdown],
            "backgroundColor": color,
        })
    return json.dumps({"labels": labels, "datasets": datasets})


# =============================================================================
# Sélecteurs DM (Directeur Métier)
# =============================================================================


def get_dm_kpis(*, user) -> dict:
    """
    Retourne les KPIs consolidés pour le dashboard DM.

    Utilise une seule requête ORM via aggregate() multi-Count — pas de N+1.

    Returns:
        dict avec clés :
            total_all          — total recos (actives + clôturées) dans le périmètre
            total_actives      — recos non-clôturées
            overdue            — is_overdue=True
            pending_dm_review  — status=PENDING_DM_REVIEW (action requise DM)
            closed_resolved    — status=CLOSED_RESOLVED
            critique_open      — CRITIQUE non clôturées
            taux_cloture       — float 0-100, arrondi à 1 décimale (0.0 si total=0)
    """
    qs = get_recommendations_for_user(user=user)

    agg = qs.aggregate(
        total_all=Count("id"),
        total_actives=Count(
            "id",
            filter=~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
        overdue=Count("id", filter=Q(is_overdue=True)),
        pending_dm_review=Count(
            "id",
            filter=Q(status=Recommendation.Status.PENDING_DM_REVIEW),
        ),
        closed_resolved=Count(
            "id",
            filter=Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
        critique_open=Count(
            "id",
            filter=Q(
                priority=Recommendation.Priority.CRITIQUE,
            ) & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
    )

    total = agg["total_all"] or 0
    closed = agg["closed_resolved"] or 0
    taux_cloture = round((closed / total) * 100, 1) if total > 0 else 0.0

    return {
        "total_all": total,
        "total_actives": agg["total_actives"] or 0,
        "overdue": agg["overdue"] or 0,
        "pending_dm_review": agg["pending_dm_review"] or 0,
        "closed_resolved": closed,
        "critique_open": agg["critique_open"] or 0,
        "taux_cloture": taux_cloture,
    }


def get_dm_donut_data(*, user) -> dict:
    """
    Retourne les données pour le donut Chart.js — répartition par statut/état.

    Segmentation :
      - OVERDUE    : is_overdue=True (toutes statuts actifs confondus)
      - ASSIGNED   : status=ASSIGNED, non overdue
      - IN_PROGRESS: status=IN_PROGRESS, non overdue
      - PENDING_DM : status=PENDING_DM_REVIEW, non overdue
      - PENDING_AU : status=PENDING_AUDIT_REVIEW, non overdue
      - CLOSED     : status=CLOSED_RESOLVED

    Chaque reco est comptée une seule fois — total cohérent.

    Returns:
        dict {labels: [...], values: [...], colors: [...]}
    """
    qs = get_recommendations_for_user(user=user)

    agg = qs.aggregate(
        overdue=Count(
            "id",
            filter=Q(is_overdue=True) & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
        assigned=Count(
            "id",
            filter=Q(status=Recommendation.Status.ASSIGNED, is_overdue=False),
        ),
        in_progress=Count(
            "id",
            filter=Q(status=Recommendation.Status.IN_PROGRESS, is_overdue=False),
        ),
        pending_dm_review=Count(
            "id",
            filter=Q(status=Recommendation.Status.PENDING_DM_REVIEW, is_overdue=False),
        ),
        pending_audit_review=Count(
            "id",
            filter=Q(status=Recommendation.Status.PENDING_AUDIT_REVIEW, is_overdue=False),
        ),
        closed_resolved=Count(
            "id",
            filter=Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
    )

    return {
        "labels": [
            "En retard",
            "Assignée",
            "En cours",
            "Validation DM",
            "Validation Audit",
            "Clôturée",
        ],
        "values": [
            agg["overdue"] or 0,
            agg["assigned"] or 0,
            agg["in_progress"] or 0,
            agg["pending_dm_review"] or 0,
            agg["pending_audit_review"] or 0,
            agg["closed_resolved"] or 0,
        ],
        "colors": [
            "#EF4444",  # rouge — overdue
            "#3B82F6",  # bleu — assigned
            "#F59E0B",  # ambre — in_progress
            "#F97316",  # orange — pending DM
            "#6366F1",  # indigo — pending Audit
            "#10B981",  # vert — closed
        ],
    }


def get_dm_pending_validation(*, user):
    """
    Retourne les recommandations en PENDING_DM_REVIEW pour le DM.

    Ce sont les preuves soumises par ses ETPs qui attendent sa décision.
    Scoped RBAC par get_recommendations_for_user.

    Returns:
        QuerySet[Recommendation] ordonné par due_date ASC.
    """
    return (
        get_recommendations_for_user(user=user)
        .filter(status=Recommendation.Status.PENDING_DM_REVIEW)
        .select_related("assigned_etp", "department")
        .order_by("due_date")
    )


def get_dm_urgency_rows(*, user, limit: int = 50) -> list[dict]:
    """
    Retourne les recommandations actives enrichies avec leur indicateur d'aging.

    Exclut : CLOSED_RESOLVED (clôturées) et DRAFT (brouillons).
    Limité à `limit` lignes (dashboard executif, pas une liste exhaustive).

    Calcul aging :
        - overdue  : is_overdue=True → jours depuis original_due_date
        - warning  : due_date <= aujourd'hui + 30j → jours restants (due_date courant)
        - ok       : due_date > J+30

    Returns:
        list[dict] avec clés : rec, aging_band, days_delta
    """
    qs = (
        get_recommendations_for_user(user=user)
        .exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .exclude(status=Recommendation.Status.DRAFT)
        .select_related("assigned_etp", "assigned_dm", "department")
        .order_by("-is_overdue", "due_date")
        [:limit]
    )
    return _enrich_with_aging(qs)


# =============================================================================
# Sélecteurs ETP (Entité / Collaborateur)
# =============================================================================


def get_etp_kpis(*, user) -> dict:
    """
    Retourne les KPIs pour le dashboard ETP (vue légère).

    Returns:
        dict avec clés : total_actives, overdue, in_progress, closed_resolved
    """
    qs = get_recommendations_for_user(user=user)

    agg = qs.aggregate(
        total_actives=Count(
            "id",
            filter=~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
        overdue=Count("id", filter=Q(is_overdue=True)),
        in_progress=Count(
            "id",
            filter=Q(status=Recommendation.Status.IN_PROGRESS),
        ),
        closed_resolved=Count(
            "id",
            filter=Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
    )

    return {
        "total_actives": agg["total_actives"] or 0,
        "overdue": agg["overdue"] or 0,
        "in_progress": agg["in_progress"] or 0,
        "closed_resolved": agg["closed_resolved"] or 0,
    }


def get_etp_rows(*, user):
    """
    Retourne les recommandations déléguées à l'ETP, non clôturées.

    Scoped RBAC par get_recommendations_for_user (ETP voit seulement
    ses recos : assigned_etp=user).

    Returns:
        list[dict] enrichi {rec, aging_band, days_delta}.
    """
    qs = (
        get_recommendations_for_user(user=user)
        .exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .select_related("department", "assigned_dm", "assigned_etp")
        .order_by("due_date")
    )
    return _enrich_with_aging(qs)


# =============================================================================
# Sélecteurs DG (Direction Générale) — vue globale banque (Option B)
# =============================================================================


def _get_dg_dashboard_qs():
    """
    Queryset banque entière pour le dashboard DG (Option B validée).

    Le DG voit TOUT pour le dashboard (comme l'Audit), mais sa liste de
    recommandations reste filtrée à ses assignations via
    get_recommendations_for_user. Exclut les brouillons DRAFT.
    """
    return Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)


def get_dg_kpis() -> dict:
    """
    KPIs macro-banque pour le dashboard DG.

    Returns:
        dict : total_all, total_actives, overdue, pending_dm_review,
               pending_audit_review, closed_resolved, critique_open, taux_cloture.
    """
    qs = _get_dg_dashboard_qs()
    agg = qs.aggregate(
        total_all=Count("id"),
        total_actives=Count(
            "id", filter=~Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        overdue=Count("id", filter=Q(is_overdue=True)),
        pending_dm_review=Count(
            "id", filter=Q(status=Recommendation.Status.PENDING_DM_REVIEW)
        ),
        pending_audit_review=Count(
            "id", filter=Q(status=Recommendation.Status.PENDING_AUDIT_REVIEW)
        ),
        closed_resolved=Count(
            "id", filter=Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        critique_open=Count(
            "id",
            filter=Q(priority=Recommendation.Priority.CRITIQUE)
            & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
    )
    total = agg["total_all"] or 0
    closed = agg["closed_resolved"] or 0
    taux = round(closed / total * 100, 1) if total > 0 else 0.0
    return {
        "total_all": total,
        "total_actives": agg["total_actives"] or 0,
        "overdue": agg["overdue"] or 0,
        "pending_dm_review": agg["pending_dm_review"] or 0,
        "pending_audit_review": agg["pending_audit_review"] or 0,
        "closed_resolved": closed,
        "critique_open": agg["critique_open"] or 0,
        "taux_cloture": taux,
    }


def get_dg_department_breakdown() -> list[dict]:
    """Répartition par direction racine — banque entière (heatmap + barres)."""
    return _get_department_breakdown(_get_dg_dashboard_qs())


def get_dg_my_recos_with_aging(*, user) -> list[dict]:
    """
    Recommandations personnellement assignées à la DG (scope RBAC normal),
    non clôturées, enrichies d'aging. Max 10 lignes.

    Returns:
        list[dict] {rec, aging_band, days_delta} — compatible urgency_table.html.
    """
    qs = (
        get_recommendations_for_user(user=user)
        .exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .select_related("department", "assigned_dm", "assigned_etp")
        .order_by("-is_overdue", "due_date")[:10]
    )
    return _enrich_with_aging(qs)


# =============================================================================
# Sélecteurs Audit Interne — contrôle global + files d'action
# =============================================================================


def get_audit_kpis(*, user) -> dict:
    """
    KPIs globaux Audit + métriques de performance (Section 5).

    L'Audit voit tout, MAIS on exclut les brouillons DRAFT de toutes les
    métriques (actives, taux, perf) — un brouillon n'est pas une reco formelle.
    Les brouillons restent surfacés via la file dédiée get_audit_draft_unassigned.
    Cohérent avec le scope DG (_get_dg_dashboard_qs).

    Returns:
        dict : total_all, total_actives, overdue, pending_audit_review,
               closed_resolved, critique_open, taux_cloture, taux_overdue,
               recos_crees_ce_mois, recos_closes_ce_mois.
    """
    qs = get_recommendations_for_user(user=user).exclude(
        status=Recommendation.Status.DRAFT
    )
    now = timezone.now()
    agg = qs.aggregate(
        total_all=Count("id"),
        total_actives=Count(
            "id", filter=~Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        overdue=Count("id", filter=Q(is_overdue=True)),
        pending_audit_review=Count(
            "id", filter=Q(status=Recommendation.Status.PENDING_AUDIT_REVIEW)
        ),
        closed_resolved=Count(
            "id", filter=Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        critique_open=Count(
            "id",
            filter=Q(priority=Recommendation.Priority.CRITIQUE)
            & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
        recos_crees_ce_mois=Count(
            "id",
            filter=Q(created_at__year=now.year, created_at__month=now.month),
        ),
        recos_closes_ce_mois=Count(
            "id",
            filter=Q(
                status=Recommendation.Status.CLOSED_RESOLVED,
                closed_at__isnull=False,
                closed_at__year=now.year,
                closed_at__month=now.month,
            ),
        ),
    )
    total = agg["total_all"] or 0
    closed = agg["closed_resolved"] or 0
    overdue = agg["overdue"] or 0
    taux_cloture = round(closed / total * 100, 1) if total > 0 else 0.0
    taux_overdue = round(overdue / total * 100, 1) if total > 0 else 0.0
    return {
        "total_all": total,
        "total_actives": agg["total_actives"] or 0,
        "overdue": overdue,
        "pending_audit_review": agg["pending_audit_review"] or 0,
        "closed_resolved": closed,
        "critique_open": agg["critique_open"] or 0,
        "taux_cloture": taux_cloture,
        "taux_overdue": taux_overdue,
        "recos_crees_ce_mois": agg["recos_crees_ce_mois"] or 0,
        "recos_closes_ce_mois": agg["recos_closes_ce_mois"] or 0,
    }


def get_audit_pending_review(*, user) -> list:
    """File 1 — preuves à examiner (PENDING_AUDIT_REVIEW). Max 10."""
    return list(
        get_recommendations_for_user(user=user)
        .filter(status=Recommendation.Status.PENDING_AUDIT_REVIEW)
        .select_related("department", "assigned_dm", "assigned_etp")
        .order_by("due_date")[:10]
    )


def get_audit_pending_review_count(*, user) -> int:
    """Count total preuves en attente de validation Audit (badge)."""
    return (
        get_recommendations_for_user(user=user)
        .filter(status=Recommendation.Status.PENDING_AUDIT_REVIEW)
        .count()
    )


def get_audit_pending_extensions() -> list:
    """
    File 2 — demandes de report en attente (ExtensionRequest.PENDING). Max 10.

    Sans paramètre user : seul l'Audit appelle ce sélecteur (depuis
    _audit_context) et voit toutes les demandes.
    """
    from apps.workflow.models import ExtensionRequest

    return list(
        ExtensionRequest.objects.filter(status=ExtensionRequest.Status.PENDING)
        .select_related("recommendation", "requested_by", "recommendation__department")
        .order_by("created_at")[:10]
    )


def get_audit_pending_extensions_count() -> int:
    """Count total demandes de report en attente (badge)."""
    from apps.workflow.models import ExtensionRequest

    return ExtensionRequest.objects.filter(
        status=ExtensionRequest.Status.PENDING
    ).count()


def get_audit_draft_unassigned(*, user) -> list:
    """File 3 — brouillons à assigner (DRAFT). Max 10."""
    return list(
        get_recommendations_for_user(user=user)
        .filter(status=Recommendation.Status.DRAFT)
        .select_related("department", "created_by")
        .order_by("created_at")[:10]
    )


def get_audit_draft_unassigned_count(*, user) -> int:
    """Count total brouillons non assignés (badge)."""
    return (
        get_recommendations_for_user(user=user)
        .filter(status=Recommendation.Status.DRAFT)
        .count()
    )


def get_audit_department_breakdown(*, user) -> list[dict]:
    """
    Répartition par direction — scope Audit via RBAC, brouillons DRAFT exclus.

    Cohérent avec get_audit_kpis et le scope DG : la heatmap de santé ne compte
    que les recos formelles, pas les brouillons en attente d'assignation.
    """
    base_qs = get_recommendations_for_user(user=user).exclude(
        status=Recommendation.Status.DRAFT
    )
    return _get_department_breakdown(base_qs)
