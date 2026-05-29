# Story 3.8 — Clôture Définitive par l'Audit Interne (FR20)
#
# Modifications :
#   - Recommendation.closed_at  (DateTimeField nullable)
#   - Recommendation.closed_by  (FK → User, nullable, PROTECT)
#   - EvidenceSubmission.status  (AlterField — ajout REJECTED_BY_AUDIT dans choices)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0013_align_field_attributes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── closed_at ──────────────────────────────────────────────────────
        migrations.AddField(
            model_name="recommendation",
            name="closed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Clôturée le",
                help_text=(
                    "Horodatage exact de la clôture par l'Audit Interne (Story 3.8). "
                    "Alimentera le sceau HMAC-SHA256 en Story 3.10."
                ),
            ),
        ),
        # ── closed_by ──────────────────────────────────────────────────────
        migrations.AddField(
            model_name="recommendation",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="closed_recommendations",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Clôturée par",
                help_text=(
                    "Auditeur responsable de la clôture définitive. "
                    "Référence Story 3.10 (HMAC) pour l'identité du signataire."
                ),
            ),
        ),
        # ── EvidenceSubmission.status — ajout REJECTED_BY_AUDIT ───────────
        migrations.AlterField(
            model_name="evidencesubmission",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Brouillon"),
                    ("PENDING", "En attente de validation"),
                    ("ACCEPTED", "Acceptée"),
                    ("REJECTED", "Rejetée"),
                    ("REJECTED_BY_AUDIT", "Rejetée par l'Audit"),
                ],
                default="DRAFT",
                max_length=20,
                verbose_name="Statut",
                help_text=(
                    "DRAFT à la création du brouillon. PENDING à la soumission. "
                    "ACCEPTED/REJECTED piloté par le DM (Story 3.4). "
                    "REJECTED_BY_AUDIT piloté par l'Audit Interne (Story 3.8)."
                ),
            ),
        ),
    ]
