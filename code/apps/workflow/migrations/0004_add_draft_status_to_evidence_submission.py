# Migration générée manuellement — Refonte brouillons persistants (Story 3.3 v2)
#
# Changements :
#   1. Ajout du choix DRAFT dans SubmissionStatus + changement du default
#   2. Champ comment rendu optionnel (blank=True, default="")
#   3. Ajout du champ updated_at (auto_now=True)
#   4. Ajout d'une UniqueConstraint conditionnelle (un seul DRAFT par user/reco)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0003_add_evidence_submission_status"),
    ]

    operations = [
        # 1. Modifier le champ status : ajouter DRAFT + changer default
        migrations.AlterField(
            model_name="evidencesubmission",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Brouillon"),
                    ("PENDING", "En attente de validation"),
                    ("ACCEPTED", "Acceptée"),
                    ("REJECTED", "Rejetée"),
                ],
                default="DRAFT",
                help_text=(
                    "DRAFT à la création du brouillon. PENDING à la soumission. "
                    "ACCEPTED/REJECTED piloté par le DM (Story 3.4)."
                ),
                max_length=20,
                verbose_name="Statut",
            ),
        ),
        # 2. Rendre le champ comment optionnel
        migrations.AlterField(
            model_name="evidencesubmission",
            name="comment",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Explication de l'ETP sur les actions menées pour résoudre la recommandation. "
                    "Vide en brouillon, obligatoire à la soumission."
                ),
                verbose_name="Commentaire de résolution",
            ),
        ),
        # 3. Ajouter le champ updated_at
        migrations.AddField(
            model_name="evidencesubmission",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                help_text=(
                    "Dernière activité sur le brouillon (ajout/suppression fichier, "
                    "modification commentaire). Visible par l'Audit sans contenu sensible."
                ),
                verbose_name="Modifié le",
            ),
        ),
        # 4. UniqueConstraint conditionnelle : un seul DRAFT par user/reco
        migrations.AddConstraint(
            model_name="evidencesubmission",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "DRAFT")),
                fields=("recommendation", "submitted_by"),
                name="unique_draft_per_reco_user",
            ),
        ),
    ]
