from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0020_importbatch_updated_at'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='importbatch',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status__in', ['PENDING', 'PROCESSING'])),
                fields=('created_by',),
                name='uniq_active_import_batch_per_user',
            ),
        ),
    ]
