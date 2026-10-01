"""
Commande de démonstration — Scénario « altération d'un dossier scellé »

Prépare et rejoue à volonté le clou de la démo de soutenance : une
recommandation clôturée et scellée (HMAC-SHA256) est falsifiée par un
UPDATE SQL direct, puis Sentinel détecte l'altération et alerte les
Admins Audit et IT (in-app + e-mail).

Chaque --prepare crée une recommandation FRAÎCHE (référence horodatée) :
l'idempotence 24 h de log_tamper_detected est calée sur la paire
(recommandation, date), donc rejouer la démo sur le même dossier le même
jour n'alerterait plus rien. Une reco neuve à chaque run garantit la
répétabilité.

Usage (dans le conteneur web) :
    docker compose exec web python manage.py demo_alteration --prepare
    docker compose exec web python manage.py demo_alteration --tamper
    docker compose exec web python manage.py demo_alteration --verify-now
    docker compose exec web python manage.py demo_alteration --cleanup
"""
import hashlib
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

REF_PREFIX = "DEMO-SOUT-"

# Contenu PDF minimal mais réel : la preuve est cliquable pendant la démo
# et son hash SHA-256 entre dans le sceau (rien n'est factice à l'écran).
PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

TAMPERED_DESCRIPTION = (
    "MONTANT FALSIFIÉ : provision ramenée de 850 000 000 FCFA à 85 000 FCFA "
    "— modification opérée directement en base de données, hors application."
)

MAILPIT_HOSTS = (
    "http://mailpit:8025",     # depuis le conteneur web (réseau compose)
    "http://localhost:8025",   # depuis la machine hôte
    "http://127.0.0.1:8025",
)


class Command(BaseCommand):
    help = "Scénario de démo : falsification d'un dossier scellé et détection HMAC"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--prepare", action="store_true",
            help="Crée une recommandation clôturée + scellée fraîche et vide Mailpit",
        )
        group.add_argument(
            "--tamper", action="store_true",
            help="Falsifie la dernière reco DEMO-SOUT par UPDATE SQL direct",
        )
        group.add_argument(
            "--verify-now", action="store_true", dest="verify_now",
            help="Lance immédiatement la vérification nocturne de tous les sceaux",
        )
        group.add_argument(
            "--cleanup", action="store_true",
            help="Purge les recos DEMO-SOUT et répare les dossiers de démo corrompus",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        # Garde de production : la commande écrit des données fictives et
        # falsifie volontairement des enregistrements — dev/démo uniquement.
        if not settings.DEBUG:
            raise CommandError(
                "demo_alteration est une commande de démonstration. "
                "Exécution refusée hors DEBUG."
            )

        if options["prepare"]:
            self._prepare()
        elif options["tamper"]:
            self._tamper()
        elif options["verify_now"]:
            self._verify_now()
        elif options["cleanup"]:
            self._cleanup()

    # ── --prepare ─────────────────────────────────────────────────────────

    def _prepare(self):
        from django.core.files.base import ContentFile

        from apps.audit.services import generate_recommendation_seal, verify_recommendation_seal
        from apps.users.models import Department, User
        from apps.workflow.models import (
            EvidenceFile,
            EvidenceSubmission,
            Recommendation,
            RecommendationSource,
        )
        from apps.workflow.services import create_recommendation

        audit_user = (
            User.objects.filter(role=User.Role.AUDIT, is_audit_admin=True, is_active=True).first()
            or User.objects.filter(role=User.Role.AUDIT, is_active=True).first()
        )
        dm_user = User.objects.filter(role=User.Role.DM, is_active=True).first()
        department = Department.objects.filter(is_active=True).first()
        if not (audit_user and dm_user and department):
            raise CommandError(
                "Il faut au moins un utilisateur AUDIT, un DM et un département actifs."
            )

        source, _ = RecommendationSource.objects.get_or_create(
            code="DEMO", defaults={"label": "Démo", "is_external": False},
        )

        now = timezone.now()
        ref = f"{REF_PREFIX}{now.strftime('%H%M%S')}"

        rec = create_recommendation(
            data={
                "reference": ref,
                "mission_date": now.date(),
                "mission_label": "Mission d'audit — provisions sur créances douteuses",
                "controlled_department": department,
                "observations": (
                    "Sous-provisionnement constaté sur le portefeuille de créances "
                    "douteuses de la direction contrôlée."
                ),
                "anomalous_dossiers": "",
                "description": (
                    "Constituer une provision complémentaire de 850 000 000 FCFA "
                    "sur les créances douteuses identifiées, conformément au "
                    "règlement COBAC R-2018/01."
                ),
                "source": source,
                "priority": Recommendation.Priority.CRITIQUE,
                "department": department,
                "due_date": now.date(),
            },
            deliverables_data=[],
            performed_by=audit_user,
        )

        # États posés directement en base, sans rejouer chaque transition FSM —
        # même technique que seed_dashboard_demo et l'import historique (6.8).
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=Recommendation.Status.CLOSED_RESOLVED,
            assigned_dm=dm_user,
            closed_at=now,
            closed_by=audit_user,
        )
        rec = Recommendation.all_objects.get(pk=rec.pk)

        submission = EvidenceSubmission.objects.create(
            recommendation=rec,
            submitted_by=dm_user,
            status=EvidenceSubmission.SubmissionStatus.ACCEPTED,
            comment="Justificatif comptable de la provision constituée.",
        )
        evidence = EvidenceFile(
            submission=submission,
            original_filename="justificatif_provision.pdf",
            file_size=len(PDF_BYTES),
            mime_type="application/pdf",
            sha256_hash=hashlib.sha256(PDF_BYTES).hexdigest(),
            uploaded_by=dm_user,
        )
        evidence.file.save(f"{ref}_justificatif.pdf", ContentFile(PDF_BYTES), save=True)

        rec = Recommendation.all_objects.select_related(
            "source", "controlled_department", "department",
        ).get(pk=rec.pk)
        generate_recommendation_seal(recommendation=rec, sealed_by=audit_user)
        rec = Recommendation.all_objects.select_related("hmac_seal").get(pk=rec.pk)

        flushed = self._flush_mailpit()

        self.stdout.write(self.style.SUCCESS(f"\n  ✅ Recommandation scellée : {ref}"))
        self.stdout.write(f"  Sceau HMAC valide : {verify_recommendation_seal(rec)}")
        self.stdout.write(f"  Boîte Mailpit vidée : {'oui' if flushed else 'non (Mailpit injoignable)'}")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n  → Page à ouvrir pour la démo :\n"
            f"    http://localhost:8000/audit/recommandations/{rec.pk}/\n"
        ))

    # ── --tamper ──────────────────────────────────────────────────────────

    def _tamper(self):
        from apps.audit.services import verify_recommendation_seal
        from apps.workflow.models import Recommendation

        rec = (
            Recommendation.all_objects.filter(reference__startswith=REF_PREFIX)
            .select_related("hmac_seal")
            .order_by("-created_at")
            .first()
        )
        if rec is None:
            raise CommandError("Aucune reco DEMO-SOUT en base — lancer d'abord --prepare.")

        self.stdout.write(self.style.WARNING(
            f"\n  🕵  Simulation : un utilisateur malveillant disposant d'un accès "
            f"SQL direct falsifie le dossier clôturé {rec.reference},\n"
            f"      en contournant totalement l'application et son workflow…\n"
        ))

        # L'attaque : un UPDATE brut, comme le ferait un DBA indélicat.
        # Aucune API Sentinel n'est utilisée — c'est tout l'intérêt du sceau.
        Recommendation.all_objects.filter(pk=rec.pk).update(
            description=TAMPERED_DESCRIPTION,
        )
        rec = Recommendation.all_objects.select_related(
            "hmac_seal", "source", "controlled_department", "department",
        ).get(pk=rec.pk)

        valid = verify_recommendation_seal(rec)
        style = self.style.ERROR if not valid else self.style.SUCCESS
        self.stdout.write(f"  Description en base : « {rec.description[:70]}… »")
        self.stdout.write(style(f"  Verdict du sceau HMAC : {'VALIDE' if valid else 'INVALIDE — altération détectable'}\n"))
        self.stdout.write(
            "  → Recharger la page de la recommandation (déclenche l'alerte),\n"
            "    ou lancer --verify-now pour la détection « nocturne » immédiate.\n"
        )

    # ── --verify-now ──────────────────────────────────────────────────────

    def _verify_now(self):
        from apps.audit.services import run_nightly_seal_verification

        self.stdout.write("\n  🌙 Vérification nocturne des sceaux (déclenchée manuellement)…")
        result = run_nightly_seal_verification()
        style = self.style.ERROR if result["tampered"] else self.style.SUCCESS
        self.stdout.write(style(
            f"  Sceaux contrôlés : {result['checked']} — "
            f"altérations détectées : {result['tampered']} — "
            f"erreurs : {result['errors']}\n"
        ))
        if result["tampered"]:
            self.stdout.write(
                "  → Alertes urgentes émises aux Admins Audit et IT "
                "(cloche in-app + e-mails dans Mailpit).\n"
            )

    # ── --cleanup ─────────────────────────────────────────────────────────

    def _cleanup(self):
        from apps.audit.models import AuditLog, HmacSeal
        from apps.audit.services import verify_recommendation_seal
        from apps.notifications.models import Notification
        from apps.workflow.models import Recommendation

        recos = Recommendation.all_objects.filter(reference__startswith=REF_PREFIX)
        reco_ids = list(recos.values_list("pk", flat=True))

        deleted_notifs, _ = Notification.objects.filter(
            recommendation_id__in=reco_ids,
        ).delete()
        deleted_logs, _ = AuditLog.objects.filter(
            content_type="Recommendation", object_id__in=reco_ids,
        ).delete()
        HmacSeal.objects.filter(recommendation_id__in=reco_ids).delete()
        count = len(reco_ids)
        recos.delete()

        self.stdout.write(self.style.SUCCESS(
            f"\n  🧹 {count} reco(s) DEMO-SOUT supprimée(s) "
            f"({deleted_notifs} notifications, {deleted_logs} entrées AuditLog)."
        ))

        # Répare les dossiers corrompus lors de tests/démos précédents : le
        # sceau conserve les métadonnées d'origine, on restaure la description
        # depuis le snapshot scellé — le sceau redevient mathématiquement valide.
        # Balaye TOUS les sceaux : un dossier resté altéré re-déclencherait des
        # alertes parasites (--verify-now, cron nocturne) pendant la soutenance.
        repaired = 0
        still_invalid = []
        for seal in HmacSeal.objects.select_related(
            "recommendation__source",
            "recommendation__controlled_department",
            "recommendation__department",
        ):
            rec = seal.recommendation
            if verify_recommendation_seal(rec):
                continue
            Recommendation.all_objects.filter(pk=rec.pk).update(
                description=seal.sealed_metadata.get("description", rec.description),
            )
            rec = Recommendation.all_objects.select_related(
                "hmac_seal", "source", "controlled_department", "department",
            ).get(pk=rec.pk)
            if verify_recommendation_seal(rec):
                repaired += 1
                Notification.objects.filter(
                    recommendation=rec,
                    notification_type=Notification.Type.TAMPER_ALERT,
                ).delete()
                AuditLog.objects.filter(
                    action=AuditLog.Action.TAMPER_DETECTED,
                    content_type="Recommendation",
                    object_id=rec.pk,
                ).delete()
            else:
                still_invalid.append(rec.reference)

        if repaired:
            self.stdout.write(self.style.SUCCESS(
                f"  🔧 {repaired} dossier(s) corrompu(s) réparé(s) depuis leur sceau."
            ))
        if still_invalid:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ Sceaux toujours invalides (champs altérés au-delà de la "
                f"description) : {', '.join(still_invalid)}"
            ))

    # ── Helpers ───────────────────────────────────────────────────────────

    def _flush_mailpit(self) -> bool:
        """Vide la boîte Mailpit (best-effort : la démo part d'une boîte propre)."""
        for host in MAILPIT_HOSTS:
            try:
                req = urllib.request.Request(
                    f"{host}/api/v1/messages", method="DELETE",
                )
                with urllib.request.urlopen(req, timeout=3):
                    return True
            except Exception:
                continue
        return False
