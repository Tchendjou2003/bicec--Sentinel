# Story 4.2 — Repointe le Schedule nocturne vers run_nightly_notifications
# (OVERDUE/ruptures 3.9-4.1 + anticipation J-7/J-3 4.2), un seul cron.

from django.db import migrations

OLD_NAME = "Bascule quotidienne OVERDUE"
NEW_NAME = "Notifications nocturnes (OVERDUE + anticipation)"
OLD_FUNC = "apps.workflow.services.flag_overdue_recommendations"
NEW_FUNC = "apps.workflow.services.run_nightly_notifications"


def repoint_forward(apps, schema_editor):
    try:
        from django_q.models import Schedule
    except ImportError:
        return
    Schedule.objects.filter(name=OLD_NAME).update(name=NEW_NAME, func=NEW_FUNC)


def repoint_backward(apps, schema_editor):
    try:
        from django_q.models import Schedule
    except ImportError:
        return
    Schedule.objects.filter(name=NEW_NAME).update(name=OLD_NAME, func=OLD_FUNC)


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0015_configure_overdue_cron"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(repoint_forward, reverse_code=repoint_backward),
    ]
