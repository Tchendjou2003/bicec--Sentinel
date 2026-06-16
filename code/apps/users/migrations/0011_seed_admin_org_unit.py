"""
Migration 0011 — Seed de l'entité système « Support Applicatif » (Story 7.2)

Data migration idempotente : crée l'unité organisationnelle technique qui
héberge les administrateurs Sentinel, dès le premier `migrate`.

- OrgUnitType `SUPPORT` (level 0) : type structurel de l'entité système.
- Department `SUPPORT` (is_system=True, racine) : foyer des comptes ADMIN.

L'entité est renommable mais protégée contre la suppression/désactivation
(garde dans Department.clean()). Idempotente via get_or_create.
"""
from django.db import migrations

SUPPORT_CODE = "SUPPORT"
SUPPORT_NAME = "Support Applicatif"


def seed_admin_org_unit(apps, schema_editor):
    """Crée l'OrgUnitType et le Department système de façon idempotente."""
    OrgUnitType = apps.get_model("users", "OrgUnitType")
    Department = apps.get_model("users", "Department")

    org_type, _ = OrgUnitType.objects.get_or_create(
        code=SUPPORT_CODE,
        defaults={"name": SUPPORT_NAME, "level": 0, "is_active": True},
    )

    Department.objects.get_or_create(
        code=SUPPORT_CODE,
        defaults={
            "name": SUPPORT_NAME,
            "type": org_type,
            "parent": None,
            "is_active": True,
            "is_system": True,
        },
    )


def remove_admin_org_unit(apps, schema_editor):
    """Retire l'entité système seedée (rollback)."""
    Department = apps.get_model("users", "Department")
    OrgUnitType = apps.get_model("users", "OrgUnitType")
    Department.objects.filter(code=SUPPORT_CODE, is_system=True).delete()
    OrgUnitType.objects.filter(code=SUPPORT_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_admin_entity_fields"),
    ]

    operations = [
        migrations.RunPython(seed_admin_org_unit, remove_admin_org_unit),
    ]
