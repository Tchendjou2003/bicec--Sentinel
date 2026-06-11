"""
Commande de démonstration — Workflow DG complet (Story 4.0)

Simule le parcours complet d'une recommandation DG pour observer les
notifications in-app dans le navigateur :

  1. Audit crée la recommandation
  2. Audit assigne directement au DG         → 🔔 notif DG  : assignée
  3. DG crée un brouillon + soumet preuves   → 🔔 notif Audit : preuves à revoir
  4. Audit rejette les preuves               → 🔔 notif DG  : preuves rejetées
  5. DG demande un report d'échéance         → 🔔 notif Audit : demande de report
  6. Audit rejette le report                 → 🔔 notif DG  : report rejeté
  7. DG soumet de nouvelles preuves          → 🔔 notif Audit : preuves à revoir
  8. Audit clôture et scelle la reco         → 🔔 notif DG  : reco clôturée

Usage :
    docker compose exec web python manage.py demo_dg_workflow
    docker compose exec web python manage.py demo_dg_workflow --reset
"""
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Démonstration du workflow DG complet avec notifications in-app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime la reco DEMO existante avant de relancer",
        )
        parser.add_argument(
            "--pause",
            type=float,
            default=1.5,
            help="Secondes d'attente entre chaque étape (défaut: 1.5)",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from django.core.management.base import CommandError

        # Garde de production : cette commande ÉCRIT des données de démo
        # (reco DEMO, notifications, fichiers) qui pollueraient la base et
        # l'AuditLog d'un environnement réel.
        if not settings.DEBUG:
            raise CommandError(
                "demo_dg_workflow est une commande de démonstration : elle crée "
                "des données fictives en base. Exécution refusée hors DEBUG."
            )

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.audit.services import verify_recommendation_seal
        from apps.notifications.models import Notification
        from apps.notifications.services import emit_notification
        from apps.users.models import User
        from apps.workflow.models import (
            ExtensionRequest,
            Recommendation,
            RecommendationSource,
        )
        from apps.workflow.services import (
            add_file_to_draft,
            assign_recommendation_to_dg,
            close_recommendation_by_audit,
            create_recommendation,
            get_or_create_draft_submission,
            reject_extension,
            reject_recommendation_by_audit,
            request_extension,
            save_draft_comment,
            submit_evidence_by_dg,
        )

        pause = options["pause"]

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("  SENTINEL — Démo workflow DG + Notifications"))
        self.stdout.write("═" * 60 + "\n")

        # ── Récupération des utilisateurs ─────────────────────────────
        try:
            audit_user = User.objects.filter(role=User.Role.AUDIT, is_superuser=True).first() \
                         or User.objects.filter(role=User.Role.AUDIT).first()
            dg_user = User.objects.filter(role=User.Role.DG).first()
        except Exception as exc:
            self.stderr.write(f"Erreur récupération utilisateurs : {exc}")
            return

        if not audit_user or not dg_user:
            self.stderr.write("❌  Utilisateurs AUDIT et DG introuvables. Vérifiez la BDD.")
            return

        self.stdout.write(f"👤  Audit    : {audit_user.get_full_name() or audit_user.username}")
        self.stdout.write(f"👤  DG       : {dg_user.get_full_name() or dg_user.username}")
        self.stdout.write("")

        # ── Nettoyage optionnel ───────────────────────────────────────
        if options["reset"]:
            from apps.audit.models import HmacSeal
            old_recos = Recommendation.all_objects.filter(
                reference__startswith="DEMO-DG-"
            )
            # Supprimer d'abord les sceaux HMAC (FK PROTECT) avant les recos.
            HmacSeal.objects.filter(recommendation__in=old_recos).delete()
            deleted, _ = old_recos.delete()
            self.stdout.write(f"🗑️   Ancienne(s) reco DEMO supprimée(s) : {deleted}")

        # ── Source ────────────────────────────────────────────────────
        source, _ = RecommendationSource.objects.get_or_create(
            code="DEMO", defaults={"label": "Démo", "is_external": False}
        )

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 1 — Créer la recommandation
        # ─────────────────────────────────────────────────────────────
        self._step("1", "Audit crée la recommandation")
        ref = f"DEMO-DG-{timezone.now().strftime('%H%M%S')}"
        rec = create_recommendation(
            data={
                "reference": ref,
                "mission_date": timezone.now().date(),
                "mission_label": "Démo — Mission Contrôle Opérationnel",
                "controlled_department": dg_user.department,
                "observations": "Risque opérationnel détecté lors de la mission.",
                "anomalous_dossiers": "Dossiers 2024-Q3 présentant des anomalies.",
                "description": (
                    "Mettre en place un contrôle interne renforcé sur les "
                    "opérations de crédit à la consommation afin de réduire "
                    "le taux de contentieux de 3% à moins de 1% (cible COBAC)."
                ),
                "source": source,
                "priority": Recommendation.Priority.CRITIQUE,
                "department": dg_user.department,
                "due_date": timezone.now().date() + timedelta(days=45),
            },
            deliverables_data=[],
            performed_by=audit_user,
        )
        self.stdout.write(f"   ✓ Reco créée : {rec.reference}  (DRAFT, priorité CRITIQUE)")
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 2 — Assigner au DG
        # ─────────────────────────────────────────────────────────────
        self._step("2", "Audit assigne la reco au DG")
        rec = assign_recommendation_to_dg(
            recommendation=rec, dg=dg_user, performed_by=audit_user,
        )
        notif = emit_notification(
            recipient=dg_user,
            notification_type=Notification.Type.ASSIGNED,
            title=f"{rec.reference} — assignée à votre portefeuille",
            body="Mission Contrôle Opérationnel — priorité Critique",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_ASSIGNED:{rec.pk}",
        )
        self.stdout.write(
            f"   ✓ Reco assignée au DG → statut : {rec.status}  "
            f"|  🔔 Notif → {dg_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 3 — DG crée un brouillon + soumet ses premières preuves
        # ─────────────────────────────────────────────────────────────
        self._step("3", "DG prépare et soumet ses premières preuves")
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=dg_user)
        pdf1 = SimpleUploadedFile(
            "procedures_controle_v1.pdf",
            b"%PDF-1.4 1 0 obj<</Type /Catalog>> endobj %% Procedures controle interne v1",
            content_type="application/pdf",
        )
        add_file_to_draft(submission=draft, file=pdf1, user=dg_user)
        save_draft_comment(
            submission=draft,
            comment="Procédures de contrôle interne mises à jour — première version.",
            user=dg_user,
        )
        rec = submit_evidence_by_dg(recommendation=rec, performed_by=dg_user)
        notif = emit_notification(
            recipient=audit_user,
            notification_type=Notification.Type.EVIDENCE_SUBMITTED,
            title=f"{rec.reference} — preuves soumises, revue requise",
            body=f"Soumis par {dg_user.get_full_name() or dg_user.username}",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_SUBMITTED_1:{rec.pk}",
        )
        self.stdout.write(
            f"   ✓ Preuves soumises → statut : {rec.status}  "
            f"|  🔔 Notif → {audit_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 4 — Audit rejette les preuves
        # ─────────────────────────────────────────────────────────────
        self._step("4", "Audit rejette les preuves (insuffisantes)")
        motif_rejet = (
            "Les pièces jointes ne couvrent pas l'intégralité des dossiers "
            "en anomalie identifiés en Q3. Merci de fournir le rapport complet "
            "de contrôle avec les mesures correctives chiffrées."
        )
        rec = reject_recommendation_by_audit(
            recommendation=rec, reason=motif_rejet, performed_by=audit_user,
        )
        notif = emit_notification(
            recipient=dg_user,
            notification_type=Notification.Type.EVIDENCE_REJECTED,
            title=f"{rec.reference} — preuves rejetées par l'Audit",
            body=motif_rejet[:80] + "…",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_REJECTED_1:{rec.pk}",
            is_urgent=True,
        )
        self.stdout.write(
            f"   ✓ Preuves rejetées → statut : {rec.status}  "
            f"|  🔔 Notif urgente → {dg_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 5 — DG demande un report d'échéance
        # ─────────────────────────────────────────────────────────────
        self._step("5", "DG demande un report d'échéance (+30 jours)")
        nouvelle_date = timezone.now().date() + timedelta(days=75)
        ext = request_extension(
            recommendation=rec,
            requested_date=nouvelle_date,
            reason=(
                "Collecte des données complémentaires en cours auprès des agences. "
                "Délai supplémentaire de 30 jours nécessaire pour produire un rapport exhaustif."
            ),
            performed_by=dg_user,
        )
        notif = emit_notification(
            recipient=audit_user,
            notification_type=Notification.Type.EXTENSION_REQUESTED,
            title=f"{rec.reference} — demande de report au {nouvelle_date.strftime('%d/%m/%Y')}",
            body="Motif : collecte complémentaire auprès des agences",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_EXT_REQ:{rec.pk}:{ext.pk}",
        )
        self.stdout.write(
            f"   ✓ Report demandé → {nouvelle_date}  "
            f"|  🔔 Notif → {audit_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 6 — Audit rejette le report
        # ─────────────────────────────────────────────────────────────
        self._step("6", "Audit rejette la demande de report")
        # Recharger l'extension depuis la BDD
        ext.refresh_from_db()
        ext = reject_extension(
            extension_request=ext,
            audit_comment=(
                "Le délai accordé initialement était suffisant. "
                "Les données de Q3 sont disponibles dans le système central."
            ),
            performed_by=audit_user,
        )
        notif = emit_notification(
            recipient=dg_user,
            notification_type=Notification.Type.EXTENSION_REJECTED,
            title=f"{rec.reference} — report refusé, échéance maintenue",
            body="L'Audit considère le délai initial suffisant.",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_EXT_REJ:{rec.pk}",
            is_urgent=True,
        )
        self.stdout.write(
            f"   ✓ Report rejeté  "
            f"|  🔔 Notif urgente → {dg_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 7 — DG soumet les bonnes preuves (2ᵉ tentative)
        # ─────────────────────────────────────────────────────────────
        self._step("7", "DG soumet de nouvelles preuves complètes")
        # Recharger la reco depuis la BDD (statut frais après reject_extension)
        rec = Recommendation.all_objects.get(pk=rec.pk)
        draft2, _ = get_or_create_draft_submission(recommendation=rec, user=dg_user)
        pdf2 = SimpleUploadedFile(
            "rapport_complet_q3.pdf",
            b"%PDF-1.4 1 0 obj<</Type /Catalog>> endobj %% Rapport complet Q3 mesures correctives",
            content_type="application/pdf",
        )
        add_file_to_draft(submission=draft2, file=pdf2, user=dg_user)
        save_draft_comment(
            submission=draft2,
            comment=(
                "Rapport complet de contrôle interne Q3 joint. "
                "Taux de contentieux ramené à 0,8% suite aux mesures correctives. "
                "Détail des 47 dossiers traités disponible en annexe."
            ),
            user=dg_user,
        )
        rec = submit_evidence_by_dg(recommendation=rec, performed_by=dg_user)
        notif = emit_notification(
            recipient=audit_user,
            notification_type=Notification.Type.EVIDENCE_SUBMITTED,
            title=f"{rec.reference} — nouvelles preuves soumises",
            body="Rapport complet Q3 avec mesures correctives chiffrées",
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_SUBMITTED_2:{rec.pk}",
        )
        self.stdout.write(
            f"   ✓ Nouvelles preuves soumises → statut : {rec.status}  "
            f"|  🔔 Notif → {audit_user.username} : {notif.title if notif else '(déjà existante)'}"
        )
        time.sleep(pause)

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 8 — Audit clôture et scelle
        # ─────────────────────────────────────────────────────────────
        self._step("8", "Audit clôture définitivement et scelle la reco")
        rec = close_recommendation_by_audit(recommendation=rec, performed_by=audit_user)
        # Recharger pour accéder au hmac_seal généré par la clôture
        rec = Recommendation.all_objects.select_related("hmac_seal").get(pk=rec.pk)
        seal = getattr(rec, "hmac_seal", None)
        seal_valid = verify_recommendation_seal(rec) if seal else False

        notif = emit_notification(
            recipient=dg_user,
            notification_type=Notification.Type.CLOSED,
            title=f"{rec.reference} — clôturée et scellée définitivement",
            body=(
                f"Sceau HMAC : {seal.hmac_hash[:16]}…" if seal
                else "Dossier clôturé"
            ),
            url=f"/audit/recommandations/{rec.pk}/",
            idempotency_key=f"DEMO_CLOSED:{rec.pk}",
        )
        self.stdout.write(
            f"   ✓ Reco clôturée → statut : {rec.status}  "
            f"|  🔒 Sceau : {seal.hmac_hash[:20]}…  |  Intègre : {seal_valid}  "
            f"|  🔔 Notif → {dg_user.username} : {notif.title if notif else '(déjà existante)'}"
        )

        # ─────────────────────────────────────────────────────────────
        # RÉSUMÉ
        # ─────────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.SUCCESS("  ✅  Workflow complet terminé !"))
        self.stdout.write("─" * 60)
        self.stdout.write(f"\n  Reco  : {rec.reference}")
        self.stdout.write(f"  Statut: {rec.status}")
        self.stdout.write(f"  URL   : http://localhost:8080/audit/recommandations/{rec.pk}/\n")

        total_notifs = Notification.objects.filter(
            idempotency_key__startswith="DEMO_",
        ).count()
        unread_dg = Notification.objects.filter(
            recipient=dg_user, is_read=False,
            idempotency_key__startswith="DEMO_",
        ).count()
        unread_audit = Notification.objects.filter(
            recipient=audit_user, is_read=False,
            idempotency_key__startswith="DEMO_",
        ).count()

        self.stdout.write("  Notifications émises :")
        self.stdout.write(f"    → {dg_user.username} (DG)    : {unread_dg} non-lues")
        self.stdout.write(f"    → {audit_user.username} (Audit) : {unread_audit} non-lues")
        self.stdout.write(f"    Total DEMO                 : {total_notifs}\n")

        self.stdout.write("  Pour observer dans le navigateur :")
        self.stdout.write(f"    1. Connecte-toi en tant que '{dg_user.username}'")
        self.stdout.write(f"       → badge devrait afficher {unread_dg}")
        self.stdout.write(f"    2. Connecte-toi en tant que '{audit_user.username}'")
        self.stdout.write(f"       → badge devrait afficher {unread_audit}\n")

    def _step(self, num, description):
        """Affiche un en-tête d'étape."""
        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO(f"  ┌─ Étape {num}/8 ─────────────────────────────────────")
        )
        self.stdout.write(
            self.style.HTTP_INFO(f"  │  {description}")
        )
        self.stdout.write(
            self.style.HTTP_INFO( "  └────────────────────────────────────────────────────")
        )
