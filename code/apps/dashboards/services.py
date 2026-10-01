"""
Dashboards App — Services (HackSoft Convention)

Écriture analytique uniquement : capture de snapshots métriques (MetricsSnapshot).
Aucune mutation de Recommendation, aucune transition FSM, aucune notif.
"""

import logging
from datetime import date

from django.db.models import Count, Q
from django.utils import timezone

from apps.workflow.models import Recommendation

from . import selectors
from .models import MetricsSnapshot

logger = logging.getLogger(__name__)


def _compute_snapshot_metrics(qs, snapshot_date: date) -> dict:
    """
    Calcule l'ensemble des champs MetricsSnapshot depuis un queryset borné.

    snapshot_date est utilisé pour les calculs d'aging et de closed_cumulative.
    Le queryset doit déjà exclure les DRAFT (cohérence avec _get_dg_dashboard_qs).
    """
    agg = qs.aggregate(
        total_actives=Count(
            "id", filter=~Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        overdue=Count("id", filter=Q(is_overdue=True)),
        closed_total=Count(
            "id", filter=Q(status=Recommendation.Status.CLOSED_RESOLVED)
        ),
        critique_open=Count(
            "id",
            filter=Q(priority=Recommendation.Priority.CRITIQUE)
            & ~Q(status=Recommendation.Status.CLOSED_RESOLVED),
        ),
    )

    buckets = selectors._aging_buckets(qs)
    on_time = selectors._on_time_rates(qs)
    first_pass = selectors._first_pass_rates(qs)
    reg_stock = selectors._regulatory_stock_weighted(qs)
    reg_aging = selectors._regulatory_aging_index(qs)

    closed_cumulative = qs.filter(
        status=Recommendation.Status.CLOSED_RESOLVED,
        closed_at__isnull=False,
        closed_at__date__lte=snapshot_date,
    ).count()

    return {
        "total_actives": agg["total_actives"] or 0,
        "overdue": agg["overdue"] or 0,
        "closed_total": agg["closed_total"] or 0,
        "closed_cumulative": closed_cumulative,
        "critique_open": agg["critique_open"] or 0,
        **buckets,
        "on_time_closed_strict": on_time["on_time_strict"],
        "on_time_closed_tolerant": on_time["on_time_tolerant"],
        "regulatory_stock_weighted": reg_stock,
        "regulatory_aging_index": reg_aging,
        "submissions_total": first_pass["submissions_total"],
        "rejected_by_dm": first_pass["rejected_by_dm"],
        "rejected_by_audit": first_pass["rejected_by_audit"],
    }


def capture_daily_snapshot(*, snapshot_date: date | None = None) -> dict:
    """
    Calcule et persiste les métriques du jour pour la banque entière et chaque
    direction métier active (groupes _get_breakdown_groups).

    Idempotent : update_or_create sur (snapshot_date, department).
    Pur calcul analytique — aucune écriture sur Recommendation.

    Args:
        snapshot_date: date du snapshot. None → aujourd'hui (usage cron).

    Returns:
        dict {"created": N, "updated": N, "date": "YYYY-MM-DD"}
    """
    if snapshot_date is None:
        snapshot_date = timezone.localdate()

    base_qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)

    created_count = updated_count = 0

    def _persist(qs, department):
        nonlocal created_count, updated_count
        metrics = _compute_snapshot_metrics(qs, snapshot_date)
        _, was_created = MetricsSnapshot.objects.update_or_create(
            snapshot_date=snapshot_date,
            department=department,
            defaults=metrics,
        )
        if was_created:
            created_count += 1
        else:
            updated_count += 1

    # Snapshot banque entière (department=NULL)
    _persist(base_qs, department=None)

    # Snapshots par direction métier (même ancrage que le tableau heatmap)
    groups, descendants_by_group_id, _ = selectors._get_breakdown_groups()
    for group in groups:
        dept_qs = base_qs.filter(department_id__in=descendants_by_group_id[group.id])
        _persist(dept_qs, department=group)

    logger.info(
        "MetricsSnapshot capturé pour %s : %d créés, %d mis à jour",
        snapshot_date,
        created_count,
        updated_count,
    )
    return {
        "created": created_count,
        "updated": updated_count,
        "date": str(snapshot_date),
    }


# =============================================================================
# Export reddition Excel — Sprint D (Story 6.9 AC4)
# =============================================================================


def build_governance_excel(*, user) -> bytes:
    """
    Génère le pack de reddition Excel (2 onglets).

    Onglet 1 — Top risques : recos à score composite le plus élevé.
    Onglet 2 — Tendances : snapshots MetricsSnapshot banque entière (90 derniers jours).

    Emet AuditLog action=EXPORT (NFR-SEC-05).

    Returns:
        Octets Excel (openpyxl WorkBook.save).
    """
    import io

    import openpyxl
    from openpyxl.styles import Font, PatternFill

    from apps.audit.models import AuditLog

    from . import selectors
    from .models import MetricsSnapshot

    summary = selectors.get_governance_summary(user=user)

    wb = openpyxl.Workbook()

    # ── Onglet 1 : Top risques ───────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Top Risques"
    header_font = Font(bold=True)
    header_fill = PatternFill(fill_type="solid", fgColor="F3F4F6")
    headers1 = [
        "Référence",
        "Criticité",
        "Direction",
        "Échéance",
        "Retard (j)",
        "Reports approuvés",
        "Score composite",
        "Source",
    ]
    for col, h in enumerate(headers1, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill

    today = timezone.localdate()
    for row_idx, r in enumerate(summary["top_risk"], 2):
        days_late = max(0, (today - r.original_due_date).days) if r.is_overdue else 0
        ws1.cell(row=row_idx, column=1, value=r.reference)
        ws1.cell(row=row_idx, column=2, value=r.get_priority_display())
        ws1.cell(
            row=row_idx, column=3, value=r.department.name if r.department else "—"
        )
        ws1.cell(row=row_idx, column=4, value=str(r.due_date))
        ws1.cell(row=row_idx, column=5, value=days_late)
        ws1.cell(row=row_idx, column=6, value=r.approved_extensions)
        ws1.cell(row=row_idx, column=7, value=r.composite_score)
        ws1.cell(
            row=row_idx,
            column=8,
            value=r.source.label if r.source else "—",
        )

    # ── Onglet 2 : Tendances snapshots ──────────────────────────────────────
    ws2 = wb.create_sheet("Tendances 90j")
    headers2 = [
        "Date",
        "Actives",
        "En retard",
        "Retard +90j",
        "Clôturées",
        "Stock régl.",
        "Vieillissement régl.",
    ]
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill

    snaps = list(
        MetricsSnapshot.objects.filter(department__isnull=True).order_by(
            "-snapshot_date"
        )[:90]
    )
    for row_idx, s in enumerate(snaps, 2):
        ws2.cell(row=row_idx, column=1, value=str(s.snapshot_date))
        ws2.cell(row=row_idx, column=2, value=s.total_actives)
        ws2.cell(row=row_idx, column=3, value=s.overdue)
        ws2.cell(row=row_idx, column=4, value=s.overdue_90_plus)
        ws2.cell(row=row_idx, column=5, value=s.closed_total)
        ws2.cell(row=row_idx, column=6, value=s.regulatory_stock_weighted)
        ws2.cell(row=row_idx, column=7, value=s.regulatory_aging_index)

    # ── AuditLog EXPORT ──────────────────────────────────────────────────────
    AuditLog.objects.create(
        action=AuditLog.Action.EXPORT,
        user=user,
        content_type="GovernanceSummary",
        description=f"Export reddition gouvernance par {user.get_full_name() or user.email}",
    )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
