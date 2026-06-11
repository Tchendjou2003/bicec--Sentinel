# Idempotence PAR DESTINATAIRE (revue PR #15 — ISSUE-016).
#
# unique=True global sur idempotency_key → après délégation, la notification
# de l'ancien porteur bloquait à vie celle du nouveau (perte silencieuse de
# notifications réglementaires J-7/J-3/OVERDUE). La contrainte composite
# (recipient, idempotency_key) conserve l'idempotence sans ce blocage.
# Les données existantes restent valides (unicité globale ⊃ unicité par paire).

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Sur la branche epic, 0003_add_provisioning_notification_types existe
        # déjà : on chaîne derrière elle pour garder un graphe linéaire
        # (une seule feuille). Sur la branche Epic 4, la dépendance était
        # 0002 — au merge, conserver cette version-ci.
        ('notifications', '0003_add_provisioning_notification_types'),
        ('workflow', '0016_repoint_nightly_schedule'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='idempotency_key',
            field=models.CharField(help_text="Format : '{TYPE}:{recommendation_pk}[:{extra}]'. Unique PAR DESTINATAIRE (contrainte composite) : après une délégation, le nouveau porteur reçoit sa propre notification pour le même événement — l'ancienne ne la bloque plus.", max_length=255, verbose_name="Clé d'idempotence"),
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(fields=('recipient', 'idempotency_key'), name='uniq_notif_recipient_idem_key'),
        ),
    ]
