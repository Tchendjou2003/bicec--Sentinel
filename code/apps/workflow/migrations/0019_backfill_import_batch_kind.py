from django.db import migrations


def backfill_kind(apps, schema_editor):
    ImportBatch = apps.get_model("workflow", "ImportBatch")
    historical_ids = (
        ImportBatch.objects
        .filter(recommendations__import_tag="IMPORTED")
        .values_list("pk", flat=True)
        .distinct()
    )
    ImportBatch.objects.filter(pk__in=list(historical_ids)).update(kind="HISTORICAL")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0018_add_import_batch_status'),
    ]

    operations = [
        migrations.RunPython(backfill_kind, noop_reverse),
    ]
