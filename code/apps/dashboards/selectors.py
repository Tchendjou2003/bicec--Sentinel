"""
Dashboards App — Selectors (Convention HackSoft)

Fonctions de lecture seule pour les agrégations et vues dashboard.
Tous les sélecteurs utilisent get_recommendations_for_user() comme base
queryset pour garantir le RBAC fail-closed.
"""

import json
import statistics
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.workflow.models import Recommendation
from apps.workflow.selectors import get_recommendations_for_user

# Poids réglementaire par criticité (COBAC — Story 6.9 AC7)
_PRIORITY_WEIGHTS = {
    Recommendation.Priority.CRITIQUE: 4,
    Recommendation.Priority.HAUTE: 3,
    Recommendation.Priority.MOYENNE: 2,
    Recommendation.Priority.FAIBLE: 1,
}


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

        rows.append(
            {
                "rec": rec,
                "aging_band": aging_band,
                "days_delta": days_delta,
            }
        )

    return rows


# =============================================================================
# Helpers analytiques — socle métriques KPI/KRI (Story 6.9)
# =============================================================================


def _aging_buckets(qs) -> dict:
    """
    Pyramide d'âge des recos en retard (is_overdue=True) : 0-30 / 30-90 / +90 j.

    Utilise original_due_date comme référence (date COBAC invariante).
    Chargement en Python pour compatibilité SQLite/PostgreSQL.
    """
    today = timezone.localdate()
    overdue_dates = list(
        qs.filter(is_overdue=True).values_list("original_due_date", flat=True)
    )
    b0_30 = b30_90 = b90 = 0
    for d in overdue_dates:
        days = (today - d).days
        if days <= 30:
            b0_30 += 1
        elif days <= 90:
            b30_90 += 1
        else:
            b90 += 1
    return {"overdue_0_30": b0_30, "overdue_30_90": b30_90, "overdue_90_plus": b90}


def _regulatory_stock_weighted(qs) -> int:
    """
    Σ poids_criticité sur les recos externes ouvertes (source.is_external=True).

    Mesure le stock de risque réglementaire pondéré à un instant T.
    Poids : CRITIQUE=4, HAUTE=3, MOYENNE=2, FAIBLE=1.
    """
    priorities = list(
        qs.exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .filter(source__is_external=True)
        .values_list("priority", flat=True)
    )
    return sum(_PRIORITY_WEIGHTS.get(p, 0) for p in priorities)


def _regulatory_aging_index(qs) -> int:
    """
    Σ (poids_criticité × jours_retard) sur les recos externes en retard.

    Mesure l'aggravation du risque réglementaire dans le temps.
    Seules les recos is_overdue=True et is_external=True sont comptées.
    """
    today = timezone.localdate()
    rows = list(
        qs.filter(is_overdue=True, source__is_external=True).values_list(
            "priority", "original_due_date"
        )
    )
    total = 0
    for priority, original_due_date in rows:
        days = (today - original_due_date).days
        total += _PRIORITY_WEIGHTS.get(priority, 0) * days
    return total


def _lead_time_stats(qs) -> dict:
    """
    Délai médian de remédiation (closed_at − created_at) par criticité.

    Utilise statistics.median (Python) pour compatibilité SQLite en tests
    (percentile_cont PostgreSQL casserait la suite de tests — piège 1).

    Returns:
        dict {priority_code: median_days} pour les priorités ayant des clôturées.
        Exemple : {"CRITIQUE": 45.0, "HAUTE": 30.0}
    """
    rows = list(
        qs.filter(
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at__isnull=False,
        ).values_list("priority", "created_at", "closed_at")
    )
    by_priority: dict = {}
    for priority, created_at, closed_at in rows:
        closed_date = closed_at.date() if hasattr(closed_at, "date") else closed_at
        created_date = created_at.date() if hasattr(created_at, "date") else created_at
        days = (closed_date - created_date).days
        by_priority.setdefault(priority, []).append(days)

    return {
        priority: statistics.median(days_list)
        for priority, days_list in by_priority.items()
    }


def _first_pass_rates(qs) -> dict:
    """
    Taux de reprise DM et Audit (qualité first-pass, Story 6.9 AC6).

    Reprise DM    = recos avec ≥1 EvidenceSubmission REJECTED.
    Reprise Audit = recos avec ≥1 EvidenceSubmission REJECTED_BY_AUDIT.
    Dénominateur = recos dans qs ayant au moins une soumission.

    Returns:
        dict {submissions_total, rejected_by_dm, rejected_by_audit,
              taux_reprise_dm, taux_reprise_audit}
    """
    from apps.workflow.models import EvidenceSubmission

    base_ids = list(qs.values_list("id", flat=True))
    subs = list(
        EvidenceSubmission.objects.filter(recommendation_id__in=base_ids).values(
            "recommendation_id", "status"
        )
    )

    with_subs: set = set()
    rejected_dm: set = set()
    rejected_audit: set = set()

    for sub in subs:
        reco_id = sub["recommendation_id"]
        with_subs.add(reco_id)
        if sub["status"] == EvidenceSubmission.SubmissionStatus.REJECTED:
            rejected_dm.add(reco_id)
        elif sub["status"] == EvidenceSubmission.SubmissionStatus.REJECTED_BY_AUDIT:
            rejected_audit.add(reco_id)

    total = len(with_subs)
    n_dm = len(rejected_dm)
    n_audit = len(rejected_audit)

    return {
        "submissions_total": total,
        "rejected_by_dm": n_dm,
        "rejected_by_audit": n_audit,
        "taux_reprise_dm": round(n_dm / total * 100, 1) if total > 0 else 0.0,
        "taux_reprise_audit": round(n_audit / total * 100, 1) if total > 0 else 0.0,
    }


def _on_time_rates(qs) -> dict:
    """
    Taux de clôture dans les délais strict et tolérant (Story 6.9 AC5).

    Strict    : closed_at ≤ original_due_date (date COBAC invariante).
    Tolérant  : closed_at ≤ due_date courant (après reports éventuels).
    L'écart strict−tolérant mesure la pression sur les extensions.

    Returns:
        dict {total_closed, on_time_strict, on_time_tolerant,
              taux_strict, taux_tolerant}
    """
    rows = list(
        qs.filter(
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at__isnull=False,
        ).values_list("closed_at", "due_date", "original_due_date")
    )

    total = strict = tolerant = 0
    for closed_at, due_date, original_due_date in rows:
        total += 1
        closed_date = closed_at.date() if hasattr(closed_at, "date") else closed_at
        if closed_date <= original_due_date:
            strict += 1
        if closed_date <= due_date:
            tolerant += 1

    return {
        "total_closed": total,
        "on_time_strict": strict,
        "on_time_tolerant": tolerant,
        "taux_strict": round(strict / total * 100, 1) if total > 0 else 0.0,
        "taux_tolerant": round(tolerant / total * 100, 1) if total > 0 else 0.0,
    }


def _get_breakdown_groups():
    """
    Détermine les groupes d'agrégation du tableau « Santé par Direction » et
    leur sous-arbre, en ancrant l'analyse sur les **directions métier** (un cran
    sous le sommet DG) plutôt que sur les racines brutes de l'arbre.

    Sans ce découplage, comme la DG est le sommet unique, toutes les directions
    seraient ses descendantes et se replieraient dans une seule ligne « DG ».

    Règle d'ancrage (3 cas, durcie pour qu'aucune reco ne soit invisible) :
      1. Une seule racine non système → apex = cette racine ;
         groupes = ses enfants directs actifs.
      2. Plusieurs racines dont exactement une de type DG → apex = DG ;
         groupes = enfants directs de DG + les autres racines non-DG.
      3. Sinon → fallback : groupes = racines non système, sans apex.

    L'entité système (is_system=True) et son sous-arbre sont exclus partout.

    Returns:
        tuple (groups, descendants_by_group_id, apex) :
            groups — list[Department] anchors d'agrégation, triés par nom
            descendants_by_group_id — dict {group_id: [ids self + descendants]}
            apex — Department | None : sommet DG, pour la ligne « rattachement direct »
    """
    from apps.users.models import Department

    # 1 requête : tout l'organigramme actif NON système (id + parent)
    edges = Department.objects.filter(is_active=True, is_system=False).values_list(
        "id", "parent_id"
    )
    children_by_parent: dict = {}
    for dept_id, parent_id in edges:
        children_by_parent.setdefault(parent_id, []).append(dept_id)

    # Racines métier : parent NULL, actives, hors entité système
    non_system_roots = list(
        Department.objects.filter(parent__isnull=True, is_active=True, is_system=False)
        .select_related("type")
        .order_by("name")
    )

    apex = None
    if len(non_system_roots) == 1:
        # Cas 1 — sommet DG unique : on descend d'un cran.
        apex = non_system_roots[0]
        group_ids = list(children_by_parent.get(apex.id, []))
    else:
        dg_roots = [r for r in non_system_roots if r.type and r.type.code == "DG"]
        if len(dg_roots) == 1:
            # Cas 2 — DG + autres racines : enfants de la DG + autres racines,
            # pour qu'aucune racine non-DG ne devienne orpheline.
            apex = dg_roots[0]
            other_root_ids = [r.id for r in non_system_roots if r.id != apex.id]
            group_ids = list(children_by_parent.get(apex.id, [])) + other_root_ids
        else:
            # Cas 3 — fallback : pas de sommet identifiable, on groupe par racines.
            group_ids = [r.id for r in non_system_roots]

    # Groupes comme objets (badge type + nom), triés par nom
    groups = list(
        Department.objects.filter(id__in=group_ids, is_active=True)
        .select_related("type")
        .order_by("name")
    )

    descendants_by_group_id = {}
    for group in groups:
        collected = [group.id]
        visited = {group.id}
        frontier = [group.id]
        while frontier:
            children = []
            for node_id in frontier:
                for child_id in children_by_parent.get(node_id, []):
                    if child_id not in visited:
                        visited.add(child_id)
                        children.append(child_id)
            collected.extend(children)
            frontier = children
        descendants_by_group_id[group.id] = collected

    return groups, descendants_by_group_id, apex


def _breakdown_row(dept_qs, *, department, label, is_direct=False) -> dict:
    """
    Agrège un queryset de recos (déjà filtré sur un périmètre) en une ligne de
    breakdown. Factorisé pour être réutilisé par les groupes ET la ligne
    « rattachement direct » (même calcul, mêmes seuils de risque).
    """
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
            filter=Q(
                status=Recommendation.Status.PENDING_AUDIT_REVIEW, is_overdue=False
            ),
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

    return {
        "department": department,
        "label": label,
        "is_direct": is_direct,
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
    }


def _get_department_breakdown(base_qs) -> list[dict]:
    """
    Calcule la répartition par **direction métier / région** (un cran sous le
    sommet DG), chacune agrégeant son propre sous-arbre. Ancrage et exclusion
    de l'entité système : cf. ``_get_breakdown_groups``.

    Une ligne « rattachement direct » est ajoutée pour les recos attachées au
    nœud DG lui-même (sinon invisibles) → garantit la réconciliation
    Σ(lignes) = total macro (hors DRAFT, hors entité système).

    L'organigramme est chargé une seule fois. Reste une requête ``.aggregate()``
    par groupe (volume modéré BICEC).

    Returns:
        list[dict] — un dict par groupe (+ éventuelle ligne directe). Chaque
        dict porte ``label`` (libellé d'affichage) et ``is_direct`` (drapeau UI).
    """
    groups, descendants_by_group_id, apex = _get_breakdown_groups()

    result = [
        _breakdown_row(
            base_qs.filter(department_id__in=descendants_by_group_id[dept.id]),
            department=dept,
            label=dept.name,
        )
        for dept in groups
    ]

    # Ligne « rattachement direct » : recos sur le nœud DG lui-même (apex),
    # qui ne sont rattachées à aucune direction métier.
    if apex is not None:
        direct_row = _breakdown_row(
            base_qs.filter(department_id=apex.id),
            department=apex,
            label=f"{apex.name} · rattachement direct",
            is_direct=True,
        )
        if direct_row["total"] > 0:
            result.append(direct_row)

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
    labels = [d.get("label") or d["department"].name for d in dept_breakdown]
    datasets = []
    for key, label, color in _STACKED_SEGMENTS:
        datasets.append(
            {
                "label": label,
                "data": [d[key] for d in dept_breakdown],
                "backgroundColor": color,
            }
        )
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
            )
            & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
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
            filter=Q(is_overdue=True)
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
        pending_dm_review=Count(
            "id",
            filter=Q(status=Recommendation.Status.PENDING_DM_REVIEW, is_overdue=False),
        ),
        pending_audit_review=Count(
            "id",
            filter=Q(
                status=Recommendation.Status.PENDING_AUDIT_REVIEW, is_overdue=False
            ),
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
        .order_by("-is_overdue", "due_date")[:limit]
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


# =============================================================================
# Sélecteurs KPI Efficacité — Sprint B (Story 6.9 AC2, AC5, AC6)
# =============================================================================


def get_efficiency_kpis() -> dict:
    """
    KPIs d'efficacité du dispositif de remédiation — banque entière, hors DRAFT.

    Partagé par les dashboards DG et Audit (même périmètre que get_dg_kpis).

    Returns:
        dict :
            on_time_strict      — % clôturées ≤ original_due_date
            on_time_tolerant    — % clôturées ≤ due_date courant
            ecart_on_time       — tolérant − strict (pression sur les extensions)
            taux_reprise_dm     — % recos avec ≥1 reprise DM
            taux_reprise_audit  — % recos avec ≥1 reprise Audit
            lead_time           — dict {priority: median_days}
            total_closed        — nombre de clôturées (base des taux)
    """
    qs = _get_dg_dashboard_qs()
    on_time = _on_time_rates(qs)
    first_pass = _first_pass_rates(qs)
    lead_time = _lead_time_stats(qs)

    return {
        "on_time_strict": on_time["taux_strict"],
        "on_time_tolerant": on_time["taux_tolerant"],
        "ecart_on_time": round(on_time["taux_tolerant"] - on_time["taux_strict"], 1),
        "taux_reprise_dm": first_pass["taux_reprise_dm"],
        "taux_reprise_audit": first_pass["taux_reprise_audit"],
        "lead_time": lead_time,
        "total_closed": on_time["total_closed"],
    }


def get_throughput_series_json(*, periods: int = 12) -> str:
    """
    Flux mensuel : créées, clôturées et backlog actif sur les `periods` derniers mois.

    Les séries créées/clôturées sont calculées depuis created_at/closed_at (exacts
    rétrospectivement). La série "actives" préfère MetricsSnapshot si disponible,
    sinon approxime depuis l'état courant (recos créées avant month_end non encore
    clôturées à cette date).

    Returns:
        str — JSON Chart.js {labels, datasets} prêt pour line_chart.html.
    """
    import calendar
    from datetime import date

    from django.db.models import Q as Qsub

    from .models import MetricsSnapshot

    today = timezone.localdate()
    labels = []
    created_data = []
    closed_data = []
    actives_data = []

    for i in range(periods - 1, -1, -1):
        # Mois i mois avant aujourd'hui
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])

        created = (
            Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
            .filter(created_at__date__gte=month_start, created_at__date__lte=month_end)
            .count()
        )

        closed = Recommendation.objects.filter(
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at__isnull=False,
            closed_at__date__gte=month_start,
            closed_at__date__lte=month_end,
        ).count()

        # Actives au dernier snapshot du mois (si dispo), sinon reconstruction directe
        snap = (
            MetricsSnapshot.objects.filter(
                snapshot_date__gte=month_start,
                snapshot_date__lte=month_end,
                department__isnull=True,
            )
            .order_by("-snapshot_date")
            .first()
        )

        if snap is not None:
            actives = snap.total_actives
        else:
            # Recos créées avant la fin du mois, non encore clôturées à cette date
            actives = (
                Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
                .filter(created_at__date__lte=month_end)
                .filter(
                    Qsub(closed_at__isnull=True) | Qsub(closed_at__date__gt=month_end)
                )
                .count()
            )

        labels.append(month_start.strftime("%b %Y"))
        created_data.append(created)
        closed_data.append(closed)
        actives_data.append(actives)

    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "Créées",
                    "data": created_data,
                    "borderColor": "#3B82F6",
                    "backgroundColor": "rgba(59,130,246,0.08)",
                    "fill": True,
                    "tension": 0.35,
                    "pointRadius": 3,
                },
                {
                    "label": "Clôturées",
                    "data": closed_data,
                    "borderColor": "#10B981",
                    "backgroundColor": "rgba(16,185,129,0.08)",
                    "fill": True,
                    "tension": 0.35,
                    "pointRadius": 3,
                },
                {
                    "label": "Actives (stock)",
                    "data": actives_data,
                    "borderColor": "#F59E0B",
                    "backgroundColor": "transparent",
                    "fill": False,
                    "tension": 0.35,
                    "pointRadius": 3,
                    "borderDash": [5, 3],
                },
            ],
        }
    )


# =============================================================================
# Série temporelle KRI — Task 8 (Story 6.9 AC3)
# =============================================================================


def get_risk_trend_series(*, periods: int = 6) -> str:
    """
    Évolution mensuelle des KRI depuis MetricsSnapshot (banque entière).

    Retourne un JSON Chart.js avec 4 séries :
        - En retard total
        - Retard +90j (critique)
        - Stock réglementaire pondéré
        - Vieillissement réglementaire

    `periods` : nombre de mois à afficher (défaut 6 — lisible sans scroll).
    Si aucun snapshot disponible pour un mois, la valeur est null (Chart.js
    interpole ou coupe la ligne selon la config).

    Returns:
        str — JSON {labels, datasets} prêt pour line_chart.html.
    """
    import calendar
    import datetime as _dt

    from .models import MetricsSnapshot

    today = timezone.localdate()
    labels = []
    overdue_data = []
    overdue_90_data = []
    reg_stock_data = []
    reg_aging_data = []

    for i in range(periods - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_start = _dt.date(year, month, 1)
        month_end = _dt.date(year, month, calendar.monthrange(year, month)[1])
        labels.append(f"{month:02d}/{year}")

        # Dernier snapshot du mois (banque entière)
        snap = (
            MetricsSnapshot.objects.filter(
                snapshot_date__range=(month_start, month_end),
                department__isnull=True,
            )
            .order_by("-snapshot_date")
            .first()
        )

        if snap:
            overdue_data.append(snap.overdue)
            overdue_90_data.append(snap.overdue_90_plus)
            reg_stock_data.append(snap.regulatory_stock_weighted)
            reg_aging_data.append(snap.regulatory_aging_index)
        else:
            overdue_data.append(None)
            overdue_90_data.append(None)
            reg_stock_data.append(None)
            reg_aging_data.append(None)

    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "En retard",
                    "data": overdue_data,
                    "borderColor": "#F59E0B",
                    "backgroundColor": "rgba(245,158,11,0.08)",
                    "fill": True,
                    "tension": 0.35,
                    "pointRadius": 3,
                    "spanGaps": True,
                },
                {
                    "label": "Retard +90j",
                    "data": overdue_90_data,
                    "borderColor": "#EF4444",
                    "backgroundColor": "rgba(239,68,68,0.08)",
                    "fill": False,
                    "tension": 0.35,
                    "pointRadius": 3,
                    "spanGaps": True,
                    "borderDash": [5, 3],
                },
                {
                    "label": "Stock régl. pondéré",
                    "data": reg_stock_data,
                    "borderColor": "#8B5CF6",
                    "backgroundColor": "rgba(139,92,246,0.06)",
                    "fill": False,
                    "tension": 0.35,
                    "pointRadius": 3,
                    "spanGaps": True,
                    "yAxisID": "y1",
                },
            ],
        }
    )


# =============================================================================
# Sélecteurs KRI Risque — Sprint C (Story 6.9 AC3, AC7, AC8)
# =============================================================================


def get_risk_kris() -> dict:
    """
    KRI de risque émergent — banque entière, hors DRAFT.

    Partagé par les dashboards DG et Audit (même périmètre que get_dg_kpis).

    Returns:
        dict :
            aging_buckets     — pyramide d'âge {overdue_0_30, overdue_30_90, overdue_90_plus}
            regulatory_stock  — int : Σ poids_criticité externes ouvertes
            regulatory_aging  — int : Σ (poids × jours_retard) externes en retard
            taux_glissement   — float : % recos actives avec ≥1 report approuvé
            derive_moyenne    — float : écart moyen due_date − original_due_date (jours)
            with_approved_ext — int : nombre de recos ayant subi ≥1 report
            total_actives     — int : base des calculs de glissement
    """
    from apps.workflow.models import ExtensionRequest

    qs = _get_dg_dashboard_qs()
    active_qs = qs.exclude(status=Recommendation.Status.CLOSED_RESOLVED)

    buckets = _aging_buckets(qs)
    reg_stock = _regulatory_stock_weighted(qs)
    reg_aging = _regulatory_aging_index(qs)

    total_actives = active_qs.count()

    with_approved_ext = (
        active_qs.filter(extension_requests__status=ExtensionRequest.Status.APPROVED)
        .distinct()
        .count()
    )
    taux_glissement = (
        round(with_approved_ext / total_actives * 100, 1) if total_actives > 0 else 0.0
    )

    # Dérive moyenne : écart moyen due_date − original_due_date sur les recos glissées
    derive_rows = list(
        active_qs.filter(extension_requests__status=ExtensionRequest.Status.APPROVED)
        .distinct()
        .values_list("due_date", "original_due_date")
    )
    if derive_rows:
        import statistics as _stats

        deltas = [(dd - odd).days for dd, odd in derive_rows]
        derive_moyenne = round(_stats.mean(deltas), 1)
    else:
        derive_moyenne = 0.0

    return {
        "aging_buckets": buckets,
        "regulatory_stock": reg_stock,
        "regulatory_aging": reg_aging,
        "taux_glissement": taux_glissement,
        "derive_moyenne": derive_moyenne,
        "with_approved_ext": with_approved_ext,
        "total_actives": total_actives,
    }


def get_at_risk_recommendations(*, user, limit: int = 20) -> list:
    """
    Recos « à risque de bascule » : non clôturées, échéance dans ≤30j, progression < 50%.

    Utilise Count annoté (pas @property progress_percentage) pour éviter le N+1.
    Piège 2 story 6.9 : progress_percentage fait 2 COUNT par appel → N×2 requêtes en boucle.

    RBAC : get_recommendations_for_user (DG/Audit voient tout ; DM/ETP scoped).
    """
    today = timezone.localdate()
    deadline = today + timedelta(days=30)

    qs = (
        get_recommendations_for_user(user=user)
        .exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .exclude(status=Recommendation.Status.DRAFT)
        .filter(due_date__range=(today, deadline))
        .annotate(
            deliverables_total=Count("deliverables"),
            deliverables_done=Count(
                "deliverables", filter=Q(deliverables__is_completed=True)
            ),
        )
        .select_related("department", "assigned_dm", "assigned_etp", "source")
        .order_by("due_date")[:limit]
    )

    # Filtre progress < 50% en Python : 1 seul hit DB, aucun N+1
    return [
        r
        for r in qs
        if r.deliverables_total == 0 or r.deliverables_done < r.deliverables_total * 0.5
    ]


def get_stuck_recommendations(*, user, limit: int = 20) -> list:
    """
    Recos « enlisées » : ≥2 reports approuvés OU (CRITIQUE sans activité depuis 30j).

    RBAC : get_recommendations_for_user.
    """
    from apps.workflow.models import ExtensionRequest

    qs = (
        get_recommendations_for_user(user=user)
        .exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .exclude(status=Recommendation.Status.DRAFT)
        .annotate(
            approved_extensions=Count(
                "extension_requests",
                filter=Q(extension_requests__status=ExtensionRequest.Status.APPROVED),
            )
        )
        .filter(
            Q(approved_extensions__gte=2)
            | Q(
                priority=Recommendation.Priority.CRITIQUE,
                updated_at__lt=timezone.now() - timedelta(days=30),
            )
        )
        .select_related("department", "assigned_dm", "assigned_etp", "source")
        .order_by("-priority", "due_date")[:limit]
    )
    return list(qs)


# =============================================================================
# Sélecteur Reddition — Sprint D (Story 6.9 AC4)
# =============================================================================


def get_governance_summary(*, user) -> dict:
    """
    Résumé de gouvernance trimestriel — lecture seule, partagé DG/Audit.

    Returns:
        dict :
            seal_coverage  — {sealed, total_closed, pct} couverture HMAC
            top_risk       — list[Recommendation] top 10 score composite (attr _composite_score)
            trend          — {current, previous} tendances trimestrielles (MetricsSnapshot)
            lead_times     — dict {priority: median_days}
            efficiency     — dict get_efficiency_kpis()
    """
    from apps.audit.models import HmacSeal
    from apps.workflow.models import ExtensionRequest

    base_qs = get_recommendations_for_user(user=user).exclude(
        status=Recommendation.Status.DRAFT
    )

    # Couverture de scellement
    closed_qs = base_qs.filter(status=Recommendation.Status.CLOSED_RESOLVED)
    total_closed = closed_qs.count()
    sealed_count = HmacSeal.objects.filter(recommendation__in=closed_qs).count()
    seal_coverage = {
        "sealed": sealed_count,
        "total_closed": total_closed,
        "pct": round(sealed_count / total_closed * 100, 1) if total_closed > 0 else 0.0,
    }

    # Top 10 score composite : poids_criticite x jours_retard + ext_approuvees x poids x 15
    # Python-only pour compatibilite SQLite/PostgreSQL (piege 1).
    today = timezone.localdate()
    active_rows = list(
        base_qs.exclude(status=Recommendation.Status.CLOSED_RESOLVED)
        .annotate(
            approved_extensions=Count(
                "extension_requests",
                filter=Q(extension_requests__status=ExtensionRequest.Status.APPROVED),
            )
        )
        .select_related("department", "source", "assigned_dm")
    )
    for r in active_rows:
        weight = _PRIORITY_WEIGHTS.get(r.priority, 1)
        days_late = max(0, (today - r.original_due_date).days) if r.is_overdue else 0
        r.composite_score = weight * days_late + r.approved_extensions * weight * 15
    top_risk = sorted(active_rows, key=lambda r: r.composite_score, reverse=True)[:10]

    # Tendances trimestrielles depuis MetricsSnapshot
    trend = _quarterly_trend()

    # Delais de remediation
    lead_times = _lead_time_stats(base_qs)

    # KPI efficacite (reutilise Sprint B)
    efficiency = get_efficiency_kpis()

    return {
        "seal_coverage": seal_coverage,
        "top_risk": top_risk,
        "trend": trend,
        "lead_times": lead_times,
        "efficiency": efficiency,
    }


def _quarterly_trend() -> dict:
    """
    Compare le trimestre courant au trimestre precedent depuis MetricsSnapshot (banque entiere).

    Retourne 2 dicts {total_actives, overdue, closed_total, taux_retard, overdue_90_plus,
    regulatory_stock} ou None si pas assez de snapshots.
    """
    import datetime as _dt

    from django.db.models import Avg, Sum

    from .models import MetricsSnapshot

    today = timezone.localdate()
    q_start_month = ((today.month - 1) // 3) * 3 + 1
    q_start = _dt.date(today.year, q_start_month, 1)
    pq_end = q_start - _dt.timedelta(days=1)
    pq_start_month = ((pq_end.month - 1) // 3) * 3 + 1
    pq_start = _dt.date(pq_end.year, pq_start_month, 1)

    def _agg_quarter(start, end):
        snaps = MetricsSnapshot.objects.filter(
            department__isnull=True,
            snapshot_date__range=(start, end),
        ).order_by("-snapshot_date")
        if not snaps.exists():
            return None
        latest = snaps.first()
        agg = snaps.aggregate(
            avg_actives=Avg("total_actives"),
            avg_overdue=Avg("overdue"),
            sum_closed=Sum("closed_total"),
        )
        total_a = round(agg["avg_actives"] or 0)
        total_o = round(agg["avg_overdue"] or 0)
        return {
            "total_actives": total_a,
            "overdue": total_o,
            "closed_total": agg["sum_closed"] or 0,
            "taux_retard": round(total_o / total_a * 100, 1) if total_a > 0 else 0.0,
            "overdue_90_plus": latest.overdue_90_plus,
            "regulatory_stock": latest.regulatory_stock_weighted,
        }

    return {
        "current": _agg_quarter(q_start, today),
        "previous": _agg_quarter(pq_start, pq_end),
    }
