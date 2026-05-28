"""
Migration 0006 — Phase B Story 3.7.b

Étape 2/3 du pattern 3-step :
  - Crée les 7 enregistrements OrgUnitType correspondant aux valeurs
    de l'ancien enum Department.Type.
  - Assigne le FK `type_new` pour chaque Department existant
    en le faisant correspondre à son code actuel.
"""
from django.db import migrations


# Codes et libellés qui correspondent 1:1 aux anciens Department.Type choices.
# L'ordre du tuple est (code, name, level).
_ORG_UNIT_TYPES = [
    ("DG", "Direction Générale", 0),
    ("DIRECTION", "Direction", 1),
    ("SOUS_DIRECTION", "Sous-Direction", 2),
    ("DEPARTEMENT", "Département", 3),
    ("SERVICE", "Service", 4),
    ("REGION", "Direction Régionale", 5),
    ("AGENCE", "Agence", 6),
]


def seed_org_unit_types(apps, schema_editor):
    """Peuple OrgUnitType + assigne les FK type_new sur Department."""
    OrgUnitType = apps.get_model("users", "OrgUnitType")
    Department = apps.get_model("users", "Department")

    # Créer les types et construire un index code → instance
    type_map = {}
    for code, name, level in _ORG_UNIT_TYPES:
        obj = OrgUnitType.objects.create(code=code, name=name, level=level)
        type_map[code] = obj

    # Assigner type_new pour chaque département dont le code type existe
    for dept in Department.objects.all():
        if dept.type in type_map:
            dept.type_new = type_map[dept.type]
            dept.save(update_fields=["type_new"])


def reverse_seed(apps, schema_editor):
    """Supprime les OrgUnitType créés (laisse type_new NULL)."""
    OrgUnitType = apps.get_model("users", "OrgUnitType")
    OrgUnitType.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_create_org_unit_type"),
    ]

    operations = [
        migrations.RunPython(seed_org_unit_types, reverse_seed),
    ]
