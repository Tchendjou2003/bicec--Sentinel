"""
Audit App — Services Crypto (Story 3.10)

Génération et vérification du sceau cryptographique HMAC-SHA256 de clôture
(FR24 / NFR-SEC-03). Le sceau scelle un snapshot figé des métadonnées métier et
les hashs SHA-256 des preuves acceptées, calculé avec ``HMAC_SECRET_KEY``
(distincte de ``SECRET_KEY`` — ADR-07).

Invariant de sûreté : le payload n'utilise QUE des identifiants stables
(UUID, codes) — jamais de libellés mutables (noms, intitulés) — afin que
``verify_recommendation_seal`` (qui recalcule depuis l'état courant) reste fiable
même après un renommage d'utilisateur ou de direction.
"""
import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone

from .models import HmacSeal


def _build_seal_payload(recommendation) -> tuple[dict, dict, str]:
    """
    Construit le payload canonique d'une recommandation et calcule son HMAC.

    Source unique de vérité partagée par la génération et la vérification :
    garantit que ``verify`` recompose un canonical identique à la génération.

    Args:
        recommendation: La recommandation (idéalement chargée avec
            ``select_related("source", "controlled_department", "department")``
            et ``prefetch_related`` des soumissions acceptées + fichiers).

    Returns:
        tuple: ``(sealed_metadata, file_hashes, hmac_hash)``.
    """
    from apps.workflow.models import EvidenceSubmission

    accepted = (
        recommendation.evidence_submissions
        .filter(status=EvidenceSubmission.SubmissionStatus.ACCEPTED)
        .order_by("created_at")
        .prefetch_related("files")
    )

    file_hashes: dict[str, str] = {}
    submissions: list[dict] = []
    for sub in accepted:
        submissions.append({
            "id": str(sub.id),
            "submitted_by": str(sub.submitted_by_id),
            "comment": sub.comment,
        })
        for evidence_file in sub.files.all():
            file_hashes[str(evidence_file.id)] = evidence_file.sha256_hash

    # Dates stringifiées (str stable) → JSONField sérialisable + canonical déterministe.
    sealed_metadata = {
        "reference": recommendation.reference,
        "mission_label": recommendation.mission_label,
        "description": recommendation.description,
        "source": recommendation.source.code,  # FK NOT NULL
        "controlled_department": (
            recommendation.controlled_department.code
            if recommendation.controlled_department_id else None
        ),
        "department": (
            recommendation.department.code
            if recommendation.department_id else None
        ),
        "priority": recommendation.priority,
        "due_date": str(recommendation.due_date),
        "original_due_date": str(recommendation.original_due_date),
        "created_at": str(recommendation.created_at),
        "closed_at": str(recommendation.closed_at),
        "closed_by": str(recommendation.closed_by_id),
        "assigned_dm": str(recommendation.assigned_dm_id),
        "status": recommendation.status,
        "submissions": submissions,
    }

    payload = {"metadata": sealed_metadata, "files": file_hashes}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    hmac_hash = hmac.new(
        settings.HMAC_SECRET_KEY.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()

    return sealed_metadata, file_hashes, hmac_hash


def generate_recommendation_seal(*, recommendation, sealed_by) -> HmacSeal:
    """
    Génère le sceau HMAC d'une recommandation (idempotent — relation 1:1).

    Destinée à être appelée dans la transaction atomique de clôture
    (``close_recommendation_by_audit``). Si un sceau existe déjà, il est
    retourné sans recalcul (pas de doublon — AC7).

    Args:
        recommendation: La recommandation clôturée à sceller.
        sealed_by: L'auditeur signataire (FK navigable).

    Returns:
        HmacSeal: Le sceau (créé ou existant).
    """
    sealed_metadata, file_hashes, hmac_hash = _build_seal_payload(recommendation)
    seal, _created = HmacSeal.objects.get_or_create(
        recommendation=recommendation,
        defaults={
            "hmac_hash": hmac_hash,
            "sealed_metadata": sealed_metadata,
            "file_hashes": file_hashes,
            "sealed_by": sealed_by,
            "sealed_at": timezone.now(),
        },
    )
    return seal


def verify_recommendation_seal(recommendation) -> bool:
    """
    Vérifie l'intégrité du dossier : recalcule le HMAC depuis l'état courant et
    le compare (constant-time) au sceau stocké.

    Returns:
        bool: ``True`` si intègre, ``False`` si altéré ou non scellé.
    """
    seal = getattr(recommendation, "hmac_seal", None)
    if seal is None:
        return False
    _, _, recomputed = _build_seal_payload(recommendation)
    return hmac.compare_digest(recomputed, seal.hmac_hash)
