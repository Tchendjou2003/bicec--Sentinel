from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0019_backfill_import_batch_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='updated_at',
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
                help_text=(
                    "Touché à chaque transition de statut et à chaque point de "
                    "progression. Sert à détecter un batch resté bloqué en "
                    "PROCESSING après un crash du worker."
                ),
                verbose_name='Modifié le',
            ),
            preserve_default=False,
        ),
    ]
