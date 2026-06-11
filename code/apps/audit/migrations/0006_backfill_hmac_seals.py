# Story 3.10 — Backfill des sceaux HMAC pour les recommandations déjà clôturées.
#
# Les migrations ne doivent pas importer les services applicatifs : la logique de
# construction du payload est donc RÉPLIQUÉE ici. Elle DOIT rester strictement
# synchronisée avec apps/audit/services.py::_build_seal_payload (mêmes champs,
# même ordre/canonicalisation), sinon verify_recommendation_seal() renverra False
# sur les recos backfillées.

import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def _compute_payload(rec, accepted_subs, files_by_submission):
    # accepted_subs / files_by_submission sont préchargés en masse par
    # backfill_seals() (2 requêtes au total) — pas de requête par reco ici,
    # sinon N+1 sur une base avec des centaines de recos clôturées.
    file_hashes = {}
    submissions = []
    for sub in accepted_subs:
        submissions.append({
            "id": str(sub.id),
            "submitted_by": str(sub.submitted_by_id),
            "comment": sub.comment,
        })
        for ef in files_by_submission.get(sub.id, []):
            file_hashes[str(ef.id)] = ef.sha256_hash

    sealed_metadata = {
        "reference": rec.reference,
        "mission_label": rec.mission_label,
        "description": rec.description,
        "source": rec.source.code,
        "controlled_department": (
            rec.controlled_department.code if rec.controlled_department_id else None
        ),
        "department": (rec.department.code if rec.department_id else None),
        "priority": rec.priority,
        "due_date": str(rec.due_date),
        "original_due_date": str(rec.original_due_date),
        "created_at": str(rec.created_at),
        "closed_at": str(rec.closed_at),
        "closed_by": str(rec.closed_by_id),
        "assigned_dm": str(rec.assigned_dm_id),
        "status": rec.status,
        "submissions": submissions,
    }

    payload = {"metadata": sealed_metadata, "files": file_hashes}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    hmac_hash = hmac.new(
        settings.HMAC_SECRET_KEY.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    return sealed_metadata, file_hashes, hmac_hash


def backfill_seals(apps, schema_editor):
    Recommendation = apps.get_model("workflow", "Recommendation")
    EvidenceSubmission = apps.get_model("workflow", "EvidenceSubmission")
    EvidenceFile = apps.get_model("workflow", "EvidenceFile")
    HmacSeal = apps.get_model("audit", "HmacSeal")

    closed = list(
        Recommendation.objects
        .filter(status="CLOSED_RESOLVED", hmac_seal__isnull=True)
        .select_related("source", "controlled_department", "department")
    )
    if not closed:
        return

    # Préchargement en masse (2 requêtes) — évite le N+1 par reco/soumission.
    accepted_subs = (
        EvidenceSubmission.objects
        .filter(recommendation__in=closed, status="ACCEPTED")
        .order_by("created_at")
    )
    subs_by_reco = {}
    for sub in accepted_subs:
        subs_by_reco.setdefault(sub.recommendation_id, []).append(sub)

    files_by_submission = {}
    for ef in EvidenceFile.objects.filter(submission__in=accepted_subs):
        files_by_submission.setdefault(ef.submission_id, []).append(ef)

    skipped = 0
    for rec in closed:
        sealed_metadata, file_hashes, hmac_hash = _compute_payload(
            rec, subs_by_reco.get(rec.pk, []), files_by_submission
        )
        # Invariant réglementaire : un sceau sans preuve documentaire n'a
        # aucune valeur juridique — ne pas sceller les recos historiques
        # clôturées sans fichier probatoire accepté.
        if not file_hashes:
            skipped += 1
            continue
        HmacSeal.objects.create(
            id=uuid.uuid4(),
            recommendation=rec,
            hmac_hash=hmac_hash,
            sealed_metadata=sealed_metadata,
            file_hashes=file_hashes,
            sealed_by_id=rec.closed_by_id,
            sealed_at=rec.closed_at or timezone.now(),
        )
    if skipped:
        print(
            f"\n  [backfill HMAC] {skipped} recommandation(s) clôturée(s) sans "
            f"preuve acceptée — non scellée(s) (invariant : pas de sceau sans preuve)."
        )


def remove_backfilled_seals(apps, schema_editor):
    # Volontairement NO-OP : les sceaux HMAC sont des traces d'audit immuables.
    # Un all().delete() détruirait aussi les sceaux créés par de vraies clôtures
    # postérieures à l'apply — perte irréversible en cas de rollback accidentel.
    print(
        "\n  [backfill HMAC] Rollback no-op : les sceaux HMAC sont des données "
        "d'audit immuables et ne sont jamais supprimés automatiquement."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0005_hmacseal"),
        ("workflow", "0015_configure_overdue_cron"),
    ]

    operations = [
        migrations.RunPython(backfill_seals, reverse_code=remove_backfilled_seals),
    ]
