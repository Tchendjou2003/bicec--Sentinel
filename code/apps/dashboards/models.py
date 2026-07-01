"""
Dashboards App — Models (HackSoft Convention)
"""

from django.db import models


class MetricsSnapshot(models.Model):
    """
    Snapshot quotidien des métriques analytiques. Alimenté par la 3e phase du cron nocturne.

    Une ligne banque-entière (department=NULL) + une ligne par direction métier
    active (groupes _get_breakdown_groups). Clé d'unicité (snapshot_date, department)
    → idempotent via update_or_create.

    Les buckets d'aging historiques sont approximatifs en backfill (is_overdue passé
    non stocké) ; les volumes créées/clôturées sont exacts depuis created_at/closed_at.
    """

    snapshot_date = models.DateField(db_index=True, verbose_name="Date du snapshot")
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="metrics_snapshots",
        verbose_name="Direction (NULL = banque entière)",
    )

    # Volumes actives / clôturées
    total_actives = models.PositiveIntegerField(default=0)
    overdue = models.PositiveIntegerField(default=0)
    closed_total = models.PositiveIntegerField(default=0)
    closed_cumulative = models.PositiveIntegerField(
        default=0,
        help_text="Total clôturées dans le périmètre à la date du snapshot",
    )
    critique_open = models.PositiveIntegerField(default=0)

    # Buckets d'aging (recos en retard, par ancienneté du retard)
    overdue_0_30 = models.PositiveIntegerField(
        default=0, help_text="En retard depuis 0-30 j"
    )
    overdue_30_90 = models.PositiveIntegerField(
        default=0, help_text="En retard depuis 30-90 j"
    )
    overdue_90_plus = models.PositiveIntegerField(
        default=0, help_text="En retard depuis +90 j"
    )

    # On-time (stricte vs tolérante)
    on_time_closed_strict = models.PositiveIntegerField(
        default=0, help_text="Clôturées ≤ original_due_date"
    )
    on_time_closed_tolerant = models.PositiveIntegerField(
        default=0, help_text="Clôturées ≤ due_date courant"
    )

    # Exposition réglementaire (sources externes)
    regulatory_stock_weighted = models.PositiveIntegerField(
        default=0, help_text="Σ poids_criticité sur externes ouvertes"
    )
    regulatory_aging_index = models.PositiveIntegerField(
        default=0, help_text="Σ (poids × jours_retard) sur externes en retard"
    )

    # Qualité first-pass (reprises DM et Audit séparées)
    submissions_total = models.PositiveIntegerField(
        default=0, help_text="Recos avec au moins une soumission de preuve"
    )
    rejected_by_dm = models.PositiveIntegerField(
        default=0, help_text="Recos avec ≥1 reprise DM (EvidenceSubmission REJECTED)"
    )
    rejected_by_audit = models.PositiveIntegerField(
        default=0, help_text="Recos avec ≥1 reprise Audit (REJECTED_BY_AUDIT)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot_date", "department"],
                name="unique_snapshot_per_date_dept",
            )
        ]
        ordering = ["-snapshot_date"]
        verbose_name = "Snapshot métriques"
        verbose_name_plural = "Snapshots métriques"

    def __str__(self):
        dept_label = self.department.name if self.department_id else "Banque entière"
        return f"[{self.snapshot_date}] {dept_label}"
