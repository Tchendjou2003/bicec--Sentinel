"""
Migration 0009 — Création du groupe « Administrateurs Sentinel » (Story 6.2.0)

Data migration idempotente : crée le groupe Django natif dont les membres
servent de « checkers » dans le flux Maker/Checker de provisioning des comptes.

Ce groupe est peuplé manuellement par l'administrateur initial (superuser).
"""
from django.db import migrations


def create_approvers_group(apps, schema_editor):
    """Crée le groupe 'Administrateurs Sentinel' de façon idempotente."""
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Administrateurs Sentinel")


def remove_approvers_group(apps, schema_editor):
    """Supprime le groupe lors d'un rollback de la migration."""
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Administrateurs Sentinel").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_create_user_provisioning_request"),
        ("auth", "__first__"),
    ]

    operations = [
        migrations.RunPython(
            create_approvers_group,
            reverse_code=remove_approvers_group,
        ),
    ]
