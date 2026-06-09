# Migration 0011 — Story 3.7.b Phase A
# Data migration :
#   1. Crée les 7 sources historiques dans workflow_recommendation_source
#   2. Remplit source_new (FK) à partir de source (CharField) pour toutes
#      les recommandations existantes
#
# Convention : apps.get_model() obligatoire (modèles historiques).

from django.db import migrations

DEFAULT_SOURCES = [
    # (code, label, is_external)
    ("INTERNE",    "Audit Interne", False),
    ("COBAC",      "COBAC",         True),
    ("CAC",        "CAC",           True),
    ("ANIF",       "ANIF",          True),
    ("BEAC",       "BEAC",          True),
    ("ANTIC",      "ANTIC",         True),
    ("CONSULTANT", "Consultant",    True),
]


def seed_and_populate(apps, schema_editor):
    """Seed les 7 sources puis bascule les FK sur les recommandations existantes."""
    Source = apps.get_model("workflow", "RecommendationSource")
    Recommendation = apps.get_model("workflow", "Recommendation")

    # 1. Créer les sources (idempotent via get_or_create)
    for code, label, is_external in DEFAULT_SOURCES:
        Source.objects.get_or_create(
            code=code,
            defaults={
                "label": label,
                "is_external": is_external,
                "is_active": True,
            },
        )

    # 2. Peupler source_new depuis le CharField source
    for rec in Recommendation.objects.all():
        if rec.source:
            try:
                rec.source_new = Source.objects.get(code=rec.source)
                rec.save(update_fields=["source_new"])
            except Source.DoesNotExist:
                # Source inconnue : créer une source désactivée pour préserver l'intégrité
                src, _ = Source.objects.get_or_create(
                    code=rec.source,
                    defaults={
                        "label": rec.source,
                        "is_external": True,
                        "is_active": False,
                    },
                )
                rec.source_new = src
                rec.save(update_fields=["source_new"])


def reverse(apps, schema_editor):
    """Annule : vide source_new puis supprime les 7 sources seedées."""
    Source = apps.get_model("workflow", "RecommendationSource")
    Recommendation = apps.get_model("workflow", "Recommendation")

    Recommendation.objects.update(source_new=None)
    Source.objects.filter(code__in=[c for c, _, _ in DEFAULT_SOURCES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0010_create_recommendation_source"),
    ]

    operations = [
        migrations.RunPython(seed_and_populate, reverse_code=reverse),
    ]
