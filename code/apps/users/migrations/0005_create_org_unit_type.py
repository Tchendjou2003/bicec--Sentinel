"""
Migration 0005 — Phase B Story 3.7.b

Étape 1/3 du pattern 3-step :
  - Crée le modèle OrgUnitType (catalogue dynamique des types d'unités org.)
  - Ajoute le champ nullable `type_new` (FK → OrgUnitType) sur Department
    en conservant l'ancien champ `type` (CharField) intact
    pour la migration de données.
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_enrich_organigramme"),
    ]

    operations = [
        # ── 1. Créer le modèle OrgUnitType ──────────────────────────────
        migrations.CreateModel(
            name="OrgUnitType",
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
                    "name",
                    models.CharField(
                        help_text="Nom affiché dans l'interface (ex : Direction Générale).",
                        max_length=60,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        help_text="Code technique court unique (ex : DG). Verrouillé après création.",
                        max_length=20,
                        unique=True,
                        verbose_name="Code",
                    ),
                ),
                (
                    "level",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Indication de profondeur dans l'organigramme (0 = sommet). Valeur indicative uniquement — ne constitue pas une contrainte.",
                        verbose_name="Niveau indicatif",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Désactiver plutôt que supprimer pour préserver l'intégrité des données existantes.",
                        verbose_name="Actif",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Modifié le"),
                ),
            ],
            options={
                "verbose_name": "Type d'unité organisationnelle",
                "verbose_name_plural": "Types d'unités organisationnelles",
                "ordering": ["level", "name"],
            },
        ),
        migrations.AddIndex(
            model_name="orgunittype",
            index=models.Index(
                fields=["code"], name="idx_orgunit_type_code"
            ),
        ),
        # ── 2. Ajouter la FK nullable `type_new` sur Department ─────────
        migrations.AddField(
            model_name="department",
            name="type_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="users.orgunittype",
                verbose_name="Type",
            ),
        ),
    ]
