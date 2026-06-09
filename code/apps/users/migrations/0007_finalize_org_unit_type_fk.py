"""
Migration 0007 — Phase B Story 3.7.b

Étape 3/3 du pattern 3-step :
  - Supprime le champ `type` (CharField) devenu obsolète.
  - Renomme `type_new` → `type`.
  - Rend le champ non-null (toutes les lignes ont été alimentées en 0006).
  - Supprime l'index idx_dept_type (était sur l'ancien CharField ;
    Django crée automatiquement un index sur la colonne FK).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_seed_org_unit_types"),
    ]

    operations = [
        # ── 1. Supprimer l'ancien index sur le CharField type ────────────
        migrations.RemoveIndex(
            model_name="department",
            name="idx_dept_type",
        ),
        # ── 2. Supprimer l'ancien CharField `type` ───────────────────────
        migrations.RemoveField(
            model_name="department",
            name="type",
        ),
        # ── 3. Renommer `type_new` → `type` ─────────────────────────────
        migrations.RenameField(
            model_name="department",
            old_name="type_new",
            new_name="type",
        ),
        # ── 4. Rendre le FK non-null ─────────────────────────────────────
        migrations.AlterField(
            model_name="department",
            name="type",
            field=models.ForeignKey(
                help_text="Catégorie structurelle dans l'organigramme BICEC.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="users.orgunittype",
                verbose_name="Type",
            ),
        ),
    ]
