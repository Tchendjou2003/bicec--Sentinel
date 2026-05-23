from django.db import migrations
from django.utils import timezone


def create_cleanup_schedule(apps, schema_editor):
    try:
        from django_q.models import Schedule
    except ImportError:
        # Sécurité si django-q2 n'est pas présent dans l'environnement courant
        return

    # Configuration du cron quotidien
    Schedule.objects.get_or_create(
        name="Nettoyage quotidien des brouillons de preuves abandonnes",
        defaults={
            "func": "apps.workflow.services.cleanup_abandoned_drafts",
            "schedule_type": "D",  # D pour Daily (Quotidien)
            "repeats": -1,         # Se répète indéfiniment
            "next_run": timezone.now().replace(
                hour=2, minute=0, second=0, microsecond=0
            ) + timezone.timedelta(days=1),
        }
    )


def remove_cleanup_schedule(apps, schema_editor):
    try:
        from django_q.models import Schedule
        Schedule.objects.filter(
            name="Nettoyage quotidien des brouillons de preuves abandonnes"
        ).delete()
    except ImportError:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0004_add_draft_status_to_evidence_submission'),
        ('django_q', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_cleanup_schedule,
            reverse_code=remove_cleanup_schedule
        ),
    ]
