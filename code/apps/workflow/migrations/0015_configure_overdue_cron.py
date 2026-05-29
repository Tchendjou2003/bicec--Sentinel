# Story 3.9 — Bascule automatique OVERDUE (FR21)
#
# Enregistre un Schedule Django-Q2 quotidien qui appelle
# apps.workflow.services.flag_overdue_recommendations à minuit (Africa/Douala).
# Data-migration uniquement — aucun changement de schéma.

from django.db import migrations
from django.utils import timezone


def create_overdue_schedule(apps, schema_editor):
    try:
        from django_q.models import Schedule
    except ImportError:
        # Sécurité si django-q2 n'est pas présent dans l'environnement courant
        return

    Schedule.objects.get_or_create(
        name="Bascule quotidienne OVERDUE",
        defaults={
            "func": "apps.workflow.services.flag_overdue_recommendations",
            "schedule_type": "D",  # D pour Daily (Quotidien)
            "repeats": -1,         # Se répète indéfiniment
            # localtime() (pas now()) pour viser 00:00 Africa/Douala et non UTC.
            "next_run": timezone.localtime().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timezone.timedelta(days=1),
        },
    )


def remove_overdue_schedule(apps, schema_editor):
    try:
        from django_q.models import Schedule
        Schedule.objects.filter(name="Bascule quotidienne OVERDUE").delete()
    except ImportError:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0014_add_closure_fields_and_audit_rejection"),
        ("django_q", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_overdue_schedule,
            reverse_code=remove_overdue_schedule,
        ),
    ]
