# Generated for Django-Q2 async import processing

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0017_importbatch_and_import_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'En attente'),
                    ('PROCESSING', 'En cours'),
                    ('DONE', 'Terminé'),
                    ('FAILED', 'Échoué'),
                    ('CANCELLED', 'Annulé'),
                ],
                default='DONE',
                help_text='DONE par défaut pour les lots créés avant le traitement asynchrone.',
                max_length=10,
                verbose_name='Statut',
            ),
        ),
        migrations.AddField(
            model_name='importbatch',
            name='kind',
            field=models.CharField(
                choices=[('EXCEL', 'Import Excel'), ('HISTORICAL', 'Import historique')],
                default='EXCEL',
                max_length=10,
                verbose_name="Type d'import",
            ),
        ),
        migrations.AddField(
            model_name='importbatch',
            name='error_message',
            field=models.TextField(blank=True, default='', verbose_name="Message d'erreur"),
        ),
        migrations.AddField(
            model_name='importbatch',
            name='processed_rows',
            field=models.PositiveIntegerField(default=0, verbose_name='Lignes traitées'),
        ),
        migrations.AddField(
            model_name='importbatch',
            name='total_rows',
            field=models.PositiveIntegerField(default=0, verbose_name='Total de lignes'),
        ),
    ]
