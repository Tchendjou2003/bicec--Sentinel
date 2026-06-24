"""
Workflow App — Services d'Export
"""
import io
import os
import zipfile

from django.db.models import Prefetch
from django.utils import timezone

from apps.users.models import User
from apps.workflow.models import EvidenceSubmission
from apps.audit.models import AuditLog
from apps.workflow import selectors


def _sanitize_segment(value: str, *, allow_dash: bool = False) -> str:
    """
    Nettoie une chaîne pour servir de segment de chemin dans une archive ZIP.

    allow_dash : conserve le tiret (utile pour les références REF-2026-0001).
    """
    return "".join(
        c if c.isalnum() or (allow_dash and c == "-") else "_" for c in value
    )


def _add_file_dedup(zip_file, *, file_path, folder, filename, used_names) -> None:
    """
    Ajoute un fichier au ZIP en évitant l'écrasement silencieux : si deux preuves
    portent le même nom dans le même dossier, on préfixe par un compteur
    (rapport.pdf, 1_rapport.pdf, 2_rapport.pdf…).

    Un fichier introuvable/illisible sur le disque est ignoré (try/except OSError)
    pour que la génération aboutisse et que la trace AuditLog soit toujours écrite.
    """
    arcname = f"{folder}/{filename}"
    counter = 1
    while arcname in used_names:
        arcname = f"{folder}/{counter}_{filename}"
        counter += 1
    used_names.add(arcname)
    try:
        zip_file.write(file_path, arcname=arcname)
    except OSError:
        # Fichier corrompu / supprimé / permissions : on saute sans avorter l'export.
        used_names.discard(arcname)


def _accepted_submissions_prefetch():
    """Prefetch des soumissions ACCEPTED (+ leurs fichiers) sous l'attribut accepted_submissions."""
    accepted = EvidenceSubmission.objects.filter(
        status=EvidenceSubmission.SubmissionStatus.ACCEPTED
    ).prefetch_related("files")
    return Prefetch(
        "recommendations__evidence_submissions",
        queryset=accepted,
        to_attr="accepted_submissions",
    )


def generate_mission_evidence_zip(user: User) -> tuple[io.BytesIO, str]:
    """
    Génère une archive ZIP en mémoire contenant toutes les preuves validées
    associées aux recommandations des missions actives de l'auditeur externe.

    Structure de l'archive :
    Nom_Mission_YYYY-MM-DD/
        REF-RECO/
            fichier1.pdf
            fichier2.png
    """
    now = timezone.now().date()
    active_missions = selectors.get_active_missions_for_user(user=user).prefetch_related(
        "recommendations", _accepted_submissions_prefetch()
    )

    # Capturé avant toute construction : sert à la fois de garde et de trace AuditLog,
    # sans ré-évaluer le QuerySet après la boucle.
    mission_names = [m.name for m in active_missions]
    if not mission_names:
        raise ValueError("Aucune mission active pour cet auditeur.")

    zip_buffer = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for mission in active_missions:
            safe_mission_name = _sanitize_segment(mission.name)
            mission_folder = f"{safe_mission_name}_{now.strftime('%Y-%m-%d')}"

            for reco in mission.recommendations.all():
                safe_reco_ref = _sanitize_segment(reco.reference, allow_dash=True)
                reco_folder = f"{mission_folder}/{safe_reco_ref}"

                for sub in reco.accepted_submissions:
                    for evidence_file in sub.files.all():
                        if evidence_file.file and hasattr(evidence_file.file, "path"):
                            if os.path.exists(evidence_file.file.path):
                                _add_file_dedup(
                                    zip_file,
                                    file_path=evidence_file.file.path,
                                    folder=reco_folder,
                                    filename=evidence_file.original_filename,
                                    used_names=used_names,
                                )

    # Trace AuditLog (FR25) — toujours écrite : la boucle ne lève plus d'OSError.
    AuditLog.objects.create(
        action=AuditLog.Action.EXPORT,
        user=user,
        content_type="User",
        object_id=user.pk,
        changes={
            "missions": mission_names,
            "timestamp": timezone.now().isoformat(),
        },
        description="L'auditeur externe a téléchargé l'archive ZIP de toutes les preuves de ses missions.",
    )

    zip_buffer.seek(0)
    filename = f"Export_Preuves_Audit_{now.strftime('%Y%m%d')}.zip"
    return zip_buffer, filename


def generate_single_recommendation_zip(user: User, reco) -> tuple[io.BytesIO, str]:
    """
    Génère une archive ZIP contenant les preuves validées d'une seule recommandation.
    """
    zip_buffer = io.BytesIO()
    safe_reco_ref = _sanitize_segment(reco.reference, allow_dash=True)
    used_names: set[str] = set()

    submissions = (
        EvidenceSubmission.objects.filter(
            recommendation=reco,
            status=EvidenceSubmission.SubmissionStatus.ACCEPTED,
        )
        .prefetch_related("files")
    )

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for sub in submissions:
            for evidence_file in sub.files.all():
                if evidence_file.file and hasattr(evidence_file.file, "path"):
                    if os.path.exists(evidence_file.file.path):
                        _add_file_dedup(
                            zip_file,
                            file_path=evidence_file.file.path,
                            folder=safe_reco_ref,
                            filename=evidence_file.original_filename,
                            used_names=used_names,
                        )

    AuditLog.objects.create(
        action=AuditLog.Action.EXPORT,
        user=user,
        content_type="Recommendation",
        object_id=reco.pk,
        description=f"Export ZIP des preuves de la recommandation {reco.reference}.",
    )

    zip_buffer.seek(0)
    filename = f"Preuves_{safe_reco_ref}_{timezone.now().strftime('%Y%m%d')}.zip"
    return zip_buffer, filename
