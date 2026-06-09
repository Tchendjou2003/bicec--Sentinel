# Migration 0010 — Story 3.7.b Phase A
# Crée la table workflow_recommendation_source et ajoute le FK nullable
# temporaire `source_new` sur Recommendation.
# Les deux colonnes (source CharField + source_new FK) coexistent
# jusqu'à la migration 0012 (finalisation).

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0009_add_extension_request"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Créer la table des sources paramétrables
        migrations.CreateModel(
            name="RecommendationSource",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        help_text="Identifiant technique immuable (ex: COBAC).",
                        max_length=30,
                        unique=True,
                        verbose_name="Code",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Libellé affiché dans l'UI et les exports.",
                        max_length=120,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "is_external",
                    models.BooleanField(
                        default=True,
                        help_text="True = autorité réglementaire externe.",
                        verbose_name="Source externe",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Sources inactives masquées du formulaire de création.",
                        verbose_name="Active",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Source de recommandation",
                "verbose_name_plural": "Sources de recommandation",
                "db_table": "workflow_recommendation_source",
                "ordering": ["is_external", "label"],
            },
        ),
        # 2. Ajouter le FK nullable temporaire sur Recommendation
        #    (sera renommé source en migration 0012)
        migrations.AddField(
            model_name="recommendation",
            name="source_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="recommendations",
                to="workflow.recommendationsource",
                verbose_name="Source",
            ),
        ),
    ]
