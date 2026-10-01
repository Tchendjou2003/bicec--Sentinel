import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetricsSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "snapshot_date",
                    models.DateField(db_index=True, verbose_name="Date du snapshot"),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="metrics_snapshots",
                        to="users.department",
                        verbose_name="Direction (NULL = banque entière)",
                    ),
                ),
                ("total_actives", models.PositiveIntegerField(default=0)),
                ("overdue", models.PositiveIntegerField(default=0)),
                ("closed_total", models.PositiveIntegerField(default=0)),
                (
                    "closed_cumulative",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Total clôturées dans le périmètre à la date du snapshot",
                    ),
                ),
                ("critique_open", models.PositiveIntegerField(default=0)),
                (
                    "overdue_0_30",
                    models.PositiveIntegerField(
                        default=0, help_text="En retard depuis 0-30 j"
                    ),
                ),
                (
                    "overdue_30_90",
                    models.PositiveIntegerField(
                        default=0, help_text="En retard depuis 30-90 j"
                    ),
                ),
                (
                    "overdue_90_plus",
                    models.PositiveIntegerField(
                        default=0, help_text="En retard depuis +90 j"
                    ),
                ),
                (
                    "on_time_closed_strict",
                    models.PositiveIntegerField(
                        default=0, help_text="Clôturées ≤ original_due_date"
                    ),
                ),
                (
                    "on_time_closed_tolerant",
                    models.PositiveIntegerField(
                        default=0, help_text="Clôturées ≤ due_date courant"
                    ),
                ),
                (
                    "regulatory_stock_weighted",
                    models.PositiveIntegerField(
                        default=0, help_text="Σ poids_criticité sur externes ouvertes"
                    ),
                ),
                (
                    "regulatory_aging_index",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Σ (poids × jours_retard) sur externes en retard",
                    ),
                ),
                (
                    "submissions_total",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Recos avec au moins une soumission de preuve",
                    ),
                ),
                (
                    "rejected_by_dm",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Recos avec ≥1 reprise DM (EvidenceSubmission REJECTED)",
                    ),
                ),
                (
                    "rejected_by_audit",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Recos avec ≥1 reprise Audit (REJECTED_BY_AUDIT)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Snapshot métriques",
                "verbose_name_plural": "Snapshots métriques",
                "ordering": ["-snapshot_date"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["snapshot_date", "department"],
                        name="unique_snapshot_per_date_dept",
                    )
                ],
            },
        ),
    ]
