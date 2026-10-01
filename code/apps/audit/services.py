"""
Audit App — Services Crypto (Story 3.10)

Génération et vérification du sceau cryptographique HMAC-SHA256 de clôture
(FR24 / NFR-SEC-03). Le sceau scelle un snapshot figé des métadonnées métier et
les hashs SHA-256 des preuves acceptées, calculé avec ``HMAC_SECRET_KEY``
(distincte de ``SECRET_KEY`` — ADR-07).

Le payload inclut à la fois des identifiants stables (UUID, codes) et des champs
texte (description, mission_label, commentaires de soumission). En conséquence,
``verify_recommendation_seal`` détectera toute modification post-clôture de ces
champs — c'est le comportement voulu (tamper detection). L'intégrité repose sur
la garde DRAFT-only de ``update_recommendation`` qui bloque toute modification
en dehors de l'état DRAFT. Ne pas contourner cette garde sans mettre à jour le
sceau.
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.utils import timezone

from .models import HmacSeal

logger = logging.getLogger(__name__)


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


def generate_recommendation_seal(
    *, recommendation, sealed_by, allow_empty_files: bool = False
) -> HmacSeal:
    """
    Génère le sceau HMAC d'une recommandation (idempotent — relation 1:1).

    Destinée à être appelée dans la transaction atomique de clôture
    (``close_recommendation_by_audit``). Si un sceau existe déjà, il est
    retourné sans recalcul (pas de doublon — AC7).

    Args:
        recommendation: La recommandation clôturée à sceller.
        sealed_by: L'auditeur signataire (FK navigable).
        allow_empty_files: Si True, permet de sceller même sans preuves (réservé
            à l'import historique Story 6.8 pour protéger l'intégrité des métadonnées).
            Par défaut False — garde réglementaire COBAC intacte pour les clôtures natives.

    Returns:
        HmacSeal: Le sceau (créé ou existant).
    """
    sealed_metadata, file_hashes, hmac_hash = _build_seal_payload(recommendation)

    # F3 — Guard réglementaire : refuser de sceller un dossier sans preuve fichier.
    # Un sceau sans file_hashes ne certifie aucune preuve documentaire (COBAC / NFR-SEC-04).
    # La garde F2 dans close_recommendation_by_audit() devrait déjà bloquer avant ici,
    # mais cette double protection garantit l'intégrité du sceau indépendamment du contexte d'appel.
    # Exception : allow_empty_files=True pour l'import historique (Story 6.8) — le sceau
    # protège l'intégrité des métadonnées importées même si les preuves ne sont pas numérisées.
    if not file_hashes and not allow_empty_files:
        raise ValueError(
            "Scellement impossible : le dossier ne contient aucun fichier probatoire accepté. "
            "Un sceau HMAC sans preuve documentaire n'a aucune valeur réglementaire (COBAC)."
        )

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


def diff_seal(recommendation) -> dict:
    """Compares a recommendation's current state to its stored HMAC seal.

    Reads seal.sealed_metadata and seal.file_hashes from the DB, then compares
    them to the recomputed current values. No file I/O — all comparisons are in RAM.

    Returns an empty dict if the recommendation has no seal.
    """
    seal = getattr(recommendation, "hmac_seal", None)
    if seal is None:
        return {}

    current_metadata, current_file_hashes, _ = _build_seal_payload(recommendation)

    sealed_meta = seal.sealed_metadata
    all_fields = set(sealed_meta.keys()) | set(current_metadata.keys())
    metadata_changes = {
        field: [sealed_meta.get(field), current_metadata.get(field)]
        for field in all_fields
        if sealed_meta.get(field) != current_metadata.get(field)
    }

    sealed_files = seal.file_hashes
    all_file_ids = set(sealed_files.keys()) | set(current_file_hashes.keys())
    file_changes: dict[str, str] = {}
    for fid in all_file_ids:
        if fid not in sealed_files:
            file_changes[fid] = "ajouté"
        elif fid not in current_file_hashes:
            file_changes[fid] = "supprimé"
        elif sealed_files[fid] != current_file_hashes[fid]:
            file_changes[fid] = "modifié"

    return {"metadata_changes": metadata_changes, "file_changes": file_changes}


def log_tamper_detected(
    recommendation,
    *,
    detected_by,
    diff: dict,
    ip_address: str | None = None,
) -> None:
    """Writes a TAMPER_DETECTED AuditLog entry and sends urgent notifications to audit admins.

    Idempotent over a 24-hour window per recommendation. Repeated page loads or
    multiple CRON runs do not create duplicate entries or notifications.

    Args:
        recommendation: The recommendation with an invalid HMAC seal.
        detected_by: The user who triggered the detection (None for CRON).
        diff: Output of diff_seal() describing altered fields and files.
        ip_address: Client IP when detected via the web view.
    """
    from datetime import timedelta

    from .models import AuditLog
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification
    from apps.users.models import User

    window_start = timezone.now() - timedelta(hours=24)
    already_logged = AuditLog.objects.filter(
        action=AuditLog.Action.TAMPER_DETECTED,
        content_type="Recommendation",
        object_id=recommendation.pk,
        created_at__gte=window_start,
    ).exists()
    if already_logged:
        return

    ref = getattr(recommendation, "reference", str(recommendation.pk))

    # detector_label : nom lisible pour la description, sans FK (detected_by peut être None)
    if detected_by is not None:
        detector_label = detected_by.get_full_name() or str(detected_by)
        detector_desc = f"lors de la consultation par {detector_label}"
    else:
        detector_label = None
        detector_desc = "lors de la vérification nocturne"

    # On ne met pas user=detected_by : le détecteur n'est pas l'auteur de l'altération.
    # L'auteur réel a agi hors application (SQL direct) et est inconnu ici.
    # Le détecteur et son IP sont consignés dans changes pour la traçabilité.
    changes_with_detector = {
        **diff,
        "detected_by": detector_label,
        "detector_ip": ip_address,
    }

    try:
        AuditLog.objects.create(
            action=AuditLog.Action.TAMPER_DETECTED,
            user=None,
            content_type="Recommendation",
            object_id=recommendation.pk,
            ip_address=None,
            changes=changes_with_detector,
            description=(
                f"Sceau HMAC invalide sur {ref}, détecté {detector_desc}. "
                f"Auteur de l'altération inconnu (accès direct probable à la base de données). "
                f"Champs : {list(diff.get('metadata_changes', {}).keys())}. "
                f"Fichiers : {list(diff.get('file_changes', {}).keys())}."
            ),
        )
    except Exception:
        # Ne bloque pas la notification qui suit même si l'écriture échoue, mais
        # la logge : un incident d'altération réelle ne doit jamais disparaître
        # sans laisser de trace exploitable, même quand l'AuditLog lui-même échoue.
        logger.exception(
            "Échec d'écriture de l'entrée AuditLog TAMPER_DETECTED pour %s", ref,
        )

    try:
        from django.db.models import Q
        ts_key = timezone.now().strftime("%Y-%m-%d")
        # Audit admins + admins IT : l'altération est un incident de sécurité pour les deux
        recipients = User.objects.filter(
            Q(role=User.Role.AUDIT, is_audit_admin=True) | Q(role=User.Role.ADMIN),
            is_active=True,
        )
        for admin in recipients:
            # Les vues workflow (détail recommandation) sont réservées à
            # AUDIT/DM/ETP/DG — un Admin IT y reçoit un 403. On le renvoie
            # plutôt vers le journal d'audit global (Story 5.1), filtré sur
            # l'action qui l'intéresse.
            if admin.role == User.Role.ADMIN:
                url = "/auth/admin/audit-trail/?action=TAMPER_DETECTED"
            else:
                url = f"/audit/recommandations/{recommendation.pk}/"

            emit_notification(
                recipient=admin,
                notification_type=Notification.Type.TAMPER_ALERT,
                title=f"Altération détectée — {ref}",
                idempotency_key=f"TAMPER_DETECTED:{recommendation.pk}:{ts_key}:{admin.pk}",
                recommendation=recommendation,
                body=(
                    f"Le sceau HMAC de {ref} est invalide. "
                    f"Un accès direct à la base de données est probable."
                ),
                url=url,
                is_urgent=True,
            )
    except Exception:
        logger.exception(
            "Échec d'envoi des notifications TAMPER_ALERT pour %s", ref,
        )


def run_nightly_seal_verification() -> dict:
    """Checks all stored HMAC seals and logs any anomalies found.

    DB reads only. No file I/O. log_tamper_detected() applies a 24-hour idempotence
    guard per recommendation, so duplicate notifications are not emitted.

    Each seal is checked in isolation: a single corrupt recommendation (broken
    FK, malformed related row) must not stop the remaining seals from being
    verified that night, since this loop is the only nightly control against
    undetected tampering (NFR-SEC-03).

    Returns:
        {"checked": int, "tampered": int, "errors": int}
    """
    checked = 0
    tampered = 0
    errors = 0

    for seal in HmacSeal.objects.select_related(
        "recommendation",
        "recommendation__source",
        "recommendation__controlled_department",
        "recommendation__department",
    ).iterator():
        checked += 1
        rec = seal.recommendation
        try:
            if not verify_recommendation_seal(rec):
                tampered += 1
                log_tamper_detected(rec, detected_by=None, diff=diff_seal(rec))
        except Exception:
            errors += 1
            logger.exception(
                "Vérification nocturne du sceau HMAC : échec sur la recommandation %s",
                getattr(rec, "pk", None),
            )

    return {"checked": checked, "tampered": tampered, "errors": errors}


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


def run_tamper_detection_task(
    *,
    recommendation_id: str,
    detected_by_id: int | None = None,
    ip_address: str | None = None,
) -> str:
    """Point d'entrée Django-Q2 pour la détection d'altération déclenchée par
    la consultation d'une recommandation (RecommendationDetailView).

    Une vue GET ne doit pas exécuter d'écriture bloquante (AuditLog + envoi de
    notifications urgentes) comme simple effet de bord du rendu — la vue
    enqueue cette tâche au lieu d'appeler log_tamper_detected directement.
    Le sceau est re-vérifié ici plutôt que de faire confiance à l'état capturé
    par la vue : entre l'enqueue et l'exécution, le dossier a pu être corrigé.

    Le nom de cette fonction est sérialisé tel quel par Django-Q2 dans la table
    des tâches : ne pas la renommer sans migrer les tâches en vol.
    """
    from django.contrib.auth import get_user_model

    from apps.workflow.models import Recommendation

    rec = Recommendation.all_objects.select_related(
        "hmac_seal", "source", "controlled_department", "department",
    ).get(pk=recommendation_id)

    if verify_recommendation_seal(rec):
        return "intact: no action"

    detected_by = None
    if detected_by_id is not None:
        detected_by = get_user_model().objects.filter(pk=detected_by_id).first()

    log_tamper_detected(
        rec, detected_by=detected_by, diff=diff_seal(rec), ip_address=ip_address,
    )
    return "tamper logged"


# ---------------------------------------------------------------------------
# Services de traçabilité d'authentification (signaux Django)
# ---------------------------------------------------------------------------

def log_user_login(*, user, ip_address: str | None = None) -> None:
    """Trace une connexion réussie (appelé depuis le signal user_logged_in)."""
    from .models import AuditLog
    AuditLog.objects.create(
        action=AuditLog.Action.LOGIN,
        user=user,
        content_type="User",
        object_id=user.pk,
        ip_address=ip_address,
        description=f"Connexion réussie — {user.get_full_name() or user.username}",
    )


def log_user_logout(*, user, ip_address: str | None = None) -> None:
    """Trace une déconnexion (appelé depuis le signal user_logged_out)."""
    from .models import AuditLog
    AuditLog.objects.create(
        action=AuditLog.Action.LOGOUT,
        user=user,
        content_type="User",
        object_id=user.pk,
        ip_address=ip_address,
        description=f"Déconnexion — {user.get_full_name() or user.username}",
    )


def log_login_failed(*, username: str, ip_address: str | None = None) -> None:
    """Trace une tentative de connexion échouée (appelé depuis le signal user_login_failed).

    L'utilisateur n'est pas résolu à ce stade — on stocke l'identifiant saisi,
    sans FK user ni object_id.
    """
    from .models import AuditLog
    AuditLog.objects.create(
        action=AuditLog.Action.LOGIN_FAILED,
        user=None,
        content_type="User",
        object_id=None,
        ip_address=ip_address,
        description=f"Échec de connexion — identifiant : « {username} »",
    )
