# Migration 0012 — Story 3.7.b Phase A (finalisation)
#
# Bascule définitive : supprime le CharField `source`, renomme `source_new`
# en `source`, puis rend le FK non-nullable.
#
# Ordre d'exécution (doc Story 3.7.b) :
#   0010 → 0011 → [services/views/forms/templates adaptés] → 0012 → bascule Python
#
# IMPORTANT : n'appliquer cette migration QU'APRÈS avoir adapté tous les
# appels qui référençaient l'ancien CharField (vues, forms, templates, tests).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0011_seed_sources_and_populate_fk"),
    ]

    operations = [
        # 1. Supprimer l'ancien CharField `source`
        migrations.RemoveField(
            model_name="recommendation",
            name="source",
        ),
        # 2. Renommer le FK temporaire source_new → source
        migrations.RenameField(
            model_name="recommendation",
            old_name="source_new",
            new_name="source",
        ),
        # 3. Rendre le FK non-nullable (toutes les lignes sont déjà peuplées
        #    par la data migration 0011)
        migrations.AlterField(
            model_name="recommendation",
            name="source",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="recommendations",
                to="workflow.recommendationsource",
                verbose_name="Source",
            ),
        ),
    ]
