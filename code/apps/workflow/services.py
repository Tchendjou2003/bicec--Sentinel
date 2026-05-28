"""
Workflow App — Services (Convention HackSoft)

Logique d'écriture pour le cycle de vie des recommandations.
Chaque mutation est tracée dans l'Audit Log (NFR-SEC-05).

Spécifications couvertes :
    - FR5  : Création manuelle unitaire
    - FR6  : Soft Delete en état DRAFT
    - FR6b : État DRAFT pré-assignation
    - FR15 : Upload en brouillon DRAFT (soumission de preuves)
    - FR16 : Soumission verrouille les brouillons en PENDING
"""
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..audit.models import AuditLog
from .models import Deliverable, EvidenceFile, EvidenceSubmission, Recommendation
from .validators import (
    compute_sha256,
    detect_mime_type,
    validate_file_size,
    validate_magic_bytes,
)


def create_recommendation(
    *,
    data: dict,
    deliverables_data: list[str],
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Crée une recommandation et ses livrables attendus de manière atomique.

    Args:
        data: Dictionnaire des champs de la recommandation
              (reference, mission_date, mission_label, etc.).
        deliverables_data: Liste des intitulés de livrables à créer.
        performed_by: L'auditeur effectuant la création.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance créée.
    """
    with transaction.atomic():
        # Initialiser original_due_date avec due_date
        data["original_due_date"] = data["due_date"]
        data["created_by"] = performed_by

        recommendation = Recommendation(**data)
        recommendation.full_clean(exclude=['status'])
        recommendation.save()

        # Créer les livrables attendus
        deliverables = []
        for order, label in enumerate(deliverables_data):
            label = label.strip()
            if label:
                deliverables.append(
                    Deliverable(
                        recommendation=recommendation,
                        label=label,
                        order=order,
                    )
                )
        if deliverables:
            Deliverable.objects.bulk_create(deliverables)

        # Audit Log
        AuditLog.objects.create(
            action=AuditLog.Action.CREATE,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "reference": recommendation.reference,
                "source": recommendation.source,
                "priority": recommendation.priority,
                "status": recommendation.status,
                "deliverables_count": len(deliverables),
            },
            description=(
                f"Création de la recommandation {recommendation.reference} "
                f"avec {len(deliverables)} livrable(s) par {performed_by.username}"
            ),
            ip_address=ip_address,
        )

    return recommendation


def update_recommendation(
    *,
    recommendation: Recommendation,
    data: dict,
    performed_by,
    ip_address: str | None = None,
    formset=None,
) -> Recommendation:
    """
    Mise à jour partielle (FR4).

    Vérifie la validité des nouvelles données et génère un
    delta dans l'AuditLog. Modifie uniquement les champs fournis.
    Si un formset est fourni, il est sauvegardé dans la même transaction.

    Args:
        recommendation: L'instance à modifier.
        data: Dictionnaire des champs modifiés.
        performed_by: L'auditeur effectuant la modification.
        ip_address: Adresse IP du client.
        formset: Optionnel, formset des livrables à sauvegarder.

    Returns:
        Recommendation: L'instance mise à jour.
    """
    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Impossible de modifier une recommandation supprimée.")

        # Sécurité Backend (AC4) : bloquer toute modification POST hors DRAFT
        if recommendation.status != Recommendation.Status.DRAFT:
            raise ValueError(
                "La modification n'est autorisée qu'en état DRAFT. "
                f"Statut actuel : {recommendation.get_status_display()}"
            )

        # Calculer le delta avant/après
        delta = {}
        update_fields = []
        for field_name, new_value in data.items():
            old_value = getattr(recommendation, field_name)
            
            if old_value != new_value:
                # Extraire les IDs pour les clés étrangères
                old_val_rep = str(old_value.pk) if hasattr(old_value, "pk") else str(old_value) if old_value is not None else None
                new_val_rep = str(new_value.pk) if hasattr(new_value, "pk") else str(new_value) if new_value is not None else None
                
                delta[field_name] = [old_val_rep, new_val_rep]
                setattr(recommendation, field_name, new_value)
                update_fields.append(field_name)

        if formset:
            formset.save()
            if formset.has_changed():
                delta["deliverables_changed"] = [False, True]

        if update_fields or (formset and formset.has_changed()):
            if update_fields:
                recommendation.full_clean(exclude=['status'])
                recommendation.save(update_fields=update_fields + ["updated_at"])

            # Audit Log
            AuditLog.objects.create(
                action=AuditLog.Action.UPDATE,
                user=performed_by,
                content_type="Recommendation",
                object_id=recommendation.pk,
                changes=delta,
                description=(
                    f"Modification de {recommendation.reference} : "
                    f"{', '.join(update_fields)} par {performed_by.username}"
                ),
                ip_address=ip_address,
            )

    return recommendation


def soft_delete_recommendation(
    *,
    recommendation: Recommendation,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Soft delete d'une recommandation (FR6).

    Le soft delete est uniquement autorisé pour les recommandations
    en état DRAFT (pré-assignation).

    Args:
        recommendation: L'instance à supprimer logiquement.
        performed_by: L'auditeur effectuant la suppression.
        ip_address: Adresse IP du client.

    Raises:
        ValueError: Si la recommandation n'est pas en état DRAFT.

    Returns:
        Recommendation: L'instance avec is_deleted=True.
    """
    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Cette recommandation a déjà été supprimée.")

        # Vérifier que la recommandation est en DRAFT
        if recommendation.status != Recommendation.Status.DRAFT:
            raise ValueError(
                f"Le soft delete n'est autorisé que sur les brouillons (DRAFT). "
                f"Statut actuel : {recommendation.get_status_display()}"
            )

        recommendation.is_deleted = True
        recommendation.deleted_at = timezone.now()
        recommendation.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

        # Audit Log
        AuditLog.objects.create(
            action=AuditLog.Action.DELETE,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={"is_deleted": [False, True]},
            description=(
                f"Soft delete de {recommendation.reference} "
                f"par {performed_by.username}"
            ),
            ip_address=ip_address,
        )

    return recommendation


def assign_recommendation_to_dm(
    *,
    recommendation: Recommendation,
    dm,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Assigne une recommandation DRAFT à un Directeur Métier (FR11).

    Orchestre la transition FSM, le verrouillage pessimiste
    et la traçabilité dans l'Audit Log.

    Args:
        recommendation: L'instance en état DRAFT.
        dm: L'utilisateur cible (role=DM).
        performed_by: L'auditeur effectuant l'assignation.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance avec status=ASSIGNED.
    """
    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Impossible d'assigner une recommandation supprimée.")

        # Transition FSM : DRAFT → ASSIGNED
        recommendation.assign_to_dm(dm)
        recommendation.save(update_fields=["status", "assigned_dm", "updated_at"])

        # Nom lisible pour l'audit trail (pérennité réglementaire)
        dm_display = dm.get_full_name() or dm.username

        # Audit Log
        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "status": ["DRAFT", "ASSIGNED"],
                "assigned_dm": [None, str(dm.pk)],
            },
            description=(
                f"Assignation de {recommendation.reference} "
                f"au DM {dm_display} par {performed_by.username}"
            ),
            ip_address=ip_address,
        )

    return recommendation


def assign_recommendation_to_dg(
    *,
    recommendation: Recommendation,
    dg,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Assigne une recommandation DRAFT directement à un Directeur Général (Story 3.x).

    Contrairement au circuit DM (DRAFT → ASSIGNED), le DG n'a pas de phase
    d'acceptation intermédiaire : la transition FSM est DRAFT → IN_PROGRESS.
    Le champ ``assigned_dm`` est réutilisé pour stocker le DG assigné.

    Args:
        recommendation: L'instance en état DRAFT.
        dg: L'utilisateur cible (role=DG).
        performed_by: L'auditeur interne effectuant l'assignation.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance avec status=IN_PROGRESS et assigned_dm=dg.

    Raises:
        ValidationError: Si le rôle DG est invalide ou la direction absente.
        TransitionNotAllowed: Si la recommandation n'est plus en DRAFT.
    """
    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Impossible d'assigner une recommandation supprimée.")

        # Capturer la valeur initiale (avant la transition FSM)
        previous_assigned_dm = (
            str(recommendation.assigned_dm_id)
            if recommendation.assigned_dm_id
            else None
        )

        # Transition FSM : DRAFT → IN_PROGRESS (bypass de ASSIGNED)
        recommendation.assign_to_dg(dg)
        recommendation.save(update_fields=["status", "assigned_dm", "updated_at"])

        # Nom lisible pour l'audit trail (pérennité réglementaire)
        dg_display = dg.get_full_name() or dg.username

        # Audit Log (NFR-SEC-05 — traçabilité complète)
        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "status": ["DRAFT", "IN_PROGRESS"],
                "assigned_dm": [previous_assigned_dm, str(dg.pk)],
                "assigned_by_dg_direct": True,
            },
            description=(
                f"Assignation directe de {recommendation.reference} "
                f"au DG {dg_display} par {performed_by.username} "
                f"(bypass ASSIGNED — circuit DG)"
            ),
            ip_address=ip_address,
        )

    return recommendation


def delegate_recommendation_to_etp(
    *,
    recommendation: Recommendation,
    etp,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Délègue une recommandation ASSIGNED à un Employé Traitant (FR12 — Story 3.2).

    Orchestre le verrouillage pessimiste, la mise à jour du champ
    ``assigned_etp``, la transition FSM ASSIGNED → IN_PROGRESS,
    et la traçabilité dans l'Audit Log.

    Args:
        recommendation: L'instance en état ASSIGNED.
        etp: L'utilisateur cible (role=ETP, même département).
        performed_by: Le DM effectuant la délégation.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance avec status=IN_PROGRESS et assigned_etp renseigné.

    Raises:
        ValueError: Si la recommandation n'est pas ASSIGNED ou l'ETP invalide.
    """
    from apps.users.models import User

    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Impossible de déléguer une recommandation supprimée.")

        if recommendation.status != Recommendation.Status.ASSIGNED:
            raise ValueError(
                f"La délégation n'est possible qu'en état ASSIGNED. "
                f"Statut actuel : {recommendation.get_status_display()}"
            )

        # Vérifier le rôle ETP
        if not etp or etp.role != User.Role.ETP:
            raise ValueError("L'utilisateur sélectionné n'a pas le rôle ETP.")

        # Vérifier l'appartenance au même département (ou ses enfants)
        from apps.workflow.selectors import get_department_and_descendants_ids
        valid_dept_ids = get_department_and_descendants_ids(recommendation.department)
        
        if etp.department_id not in valid_dept_ids:
            raise ValueError(
                "L'ETP sélectionné n'appartient pas à la Direction concernée."
            )

        # Mise à jour du champ ETP
        recommendation.assigned_etp = etp

        # Transition FSM : ASSIGNED → IN_PROGRESS
        recommendation.start_processing()
        recommendation.save(
            update_fields=["status", "assigned_etp", "updated_at"]
        )

        # Nom lisible pour l'audit trail (pérennité réglementaire)
        etp_display = etp.get_full_name() or etp.username
        dm_display = performed_by.get_full_name() or performed_by.username

        # Audit Log
        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "status": ["ASSIGNED", "IN_PROGRESS"],
                "assigned_etp": [None, str(etp.pk)],
            },
            description=(
                f"Délégation de {recommendation.reference} "
                f"à l'ETP {etp_display} par le DM {dm_display}"
            ),
            ip_address=ip_address,
        )

    return recommendation


def submit_evidence_for_recommendation(
    *,
    recommendation: Recommendation,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Soumet un brouillon DRAFT existant et déclenche la transition FSM
    IN_PROGRESS → PENDING_DM_REVIEW (Story 3.3 — FR16).

    Le brouillon DRAFT de l'utilisateur doit déjà contenir au moins un
    fichier et un commentaire non vide. La soumission passe le brouillon
    de DRAFT → PENDING et verrouille les fichiers (immutabilité AC4).

    Les livrables sont désormais togglés indépendamment via
    ``toggle_deliverable_completion()``.

    Args:
        recommendation: L'instance en état IN_PROGRESS.
        performed_by: L'ETP assigné ou le DM Porteur effectuant la soumission.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance avec status=PENDING_DM_REVIEW.

    Raises:
        ValueError: Si la recommandation n'est pas IN_PROGRESS,
            l'utilisateur non autorisé, ou le brouillon invalide.
        django_fsm.TransitionNotAllowed: Si la transition FSM échoue.
    """
    with transaction.atomic():
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.status != Recommendation.Status.IN_PROGRESS:
            raise ValueError(
                f"La soumission de preuves n'est possible qu'en état IN_PROGRESS. "
                f"Statut actuel : {recommendation.get_status_display()}"
            )

        # RBAC : ETP assigné OU DM Porteur (assigned_etp=None et DM=performed_by)
        is_assigned_etp = (
            recommendation.assigned_etp is not None
            and recommendation.assigned_etp_id == performed_by.pk
        )
        is_dm_porteur = (
            recommendation.assigned_etp is None
            and recommendation.assigned_dm_id == performed_by.pk
        )
        if not (is_assigned_etp or is_dm_porteur):
            raise ValueError(
                "Seul l'ETP assigné ou le DM Porteur peut soumettre des preuves."
            )

        # Récupérer le brouillon DRAFT actif
        draft = (
            EvidenceSubmission.objects
            .select_for_update()
            .filter(
                recommendation=recommendation,
                submitted_by=performed_by,
                status=EvidenceSubmission.SubmissionStatus.DRAFT,
            )
            .first()
        )

        if not draft:
            raise ValueError(
                "Aucun brouillon de soumission trouvé. "
                "Veuillez d'abord uploader au moins un fichier."
            )

        # Validation : au moins un fichier
        files_count = draft.files.count()
        if files_count == 0:
            raise ValueError(
                "Le brouillon ne contient aucun fichier. "
                "Veuillez uploader au moins une preuve avant de soumettre."
            )

        # Validation : commentaire non vide (FR16)
        if not draft.comment.strip():
            raise ValueError(
                "Le commentaire de résolution est obligatoire pour soumettre."
            )

        # Transition du brouillon : DRAFT → PENDING (verrouille les fichiers)
        draft.status = EvidenceSubmission.SubmissionStatus.PENDING
        draft.save(update_fields=["status", "updated_at"])

        # Transition FSM recommandation : IN_PROGRESS → PENDING_DM_REVIEW
        recommendation.submit_evidence()
        recommendation.save(update_fields=["status", "updated_at"])

        submitter_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "status": ["IN_PROGRESS", "PENDING_DM_REVIEW"],
                "evidence_files_count": [0, files_count],
                "comment": draft.comment,
            },
            description=(
                f"Soumission de {files_count} preuve(s) pour "
                f"{recommendation.reference} par {submitter_display}"
            ),
            ip_address=ip_address,
        )

    return recommendation


def reject_evidence_submission(
    *,
    recommendation: Recommendation,
    submission_id,
    reason: str,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Rejet des preuves soumises par l'ETP — Story 3.4 (AC1, AC2).

    Transitions :
        EvidenceSubmission : PENDING → REJECTED
        Recommendation FSM : PENDING_DM_REVIEW → IN_PROGRESS

    Args:
        recommendation: L'instance Recommendation en PENDING_DM_REVIEW.
        submission_id: UUID de l'EvidenceSubmission à rejeter.
        reason: Motif de rejet obligatoire (saisi par le DM).
        performed_by: Utilisateur DM qui rejette.
        ip_address: IP client pour l'AuditLog.

    Returns:
        Recommendation: L'instance avec status=IN_PROGRESS.

    Raises:
        ValueError: Si le DM est porteur (pas d'ETP), si le statut est incorrect,
                    ou si la soumission n'appartient pas à la recommandation.
        PermissionDenied: Si performed_by n'est pas le DM assigné.
    """
    # Guard DM Porteur — position #1 avant tout verrouillage
    if recommendation.assigned_etp is None:
        raise ValueError(
            "Un DM Porteur ne peut pas rejeter sa propre soumission."
        )

    with transaction.atomic():
        rec = (
            Recommendation.objects.select_for_update()
            .get(pk=recommendation.pk)
        )

        if rec.assigned_dm_id != performed_by.pk:
            raise PermissionDenied(
                "Seul le DM assigné peut rejeter les preuves de cette recommandation."
            )

        if rec.status != Recommendation.Status.PENDING_DM_REVIEW:
            raise ValueError(
                f"Le rejet n'est possible qu'en état PENDING_DM_REVIEW "
                f"(état actuel : {rec.get_status_display()})."
            )

        submission = (
            EvidenceSubmission.objects.select_for_update()
            .filter(recommendation=rec, pk=submission_id)
            .first()
        )
        if submission is None:
            raise ValueError("Soumission introuvable pour cette recommandation.")

        if submission.status != EvidenceSubmission.SubmissionStatus.PENDING:
            raise ValueError(
                "Seule une soumission en attente (PENDING) peut être rejetée."
            )

        # Mettre à jour la soumission
        submission.status = EvidenceSubmission.SubmissionStatus.REJECTED
        submission.review_comment = reason
        submission.reviewed_at = timezone.now()
        submission.reviewed_by = performed_by
        submission.save(update_fields=[
            "status", "review_comment", "reviewed_at", "reviewed_by", "updated_at"
        ])

        # Transition FSM : PENDING_DM_REVIEW → IN_PROGRESS
        rec.reject_evidence()
        rec.save(update_fields=["status", "updated_at"])

        dm_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "status": ["PENDING_DM_REVIEW", "IN_PROGRESS"],
                "review_comment": reason,
            },
            description=(
                f"Rejet de preuves par {dm_display} pour {rec.reference}"
            ),
            ip_address=ip_address,
        )

    return rec


def validate_evidence_for_audit(
    *,
    recommendation: Recommendation,
    submission_id: UUID,
    comment: str = "",
    pv_file=None,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Validation DM des preuves et envoi à l'Audit Interne — Story 3.5 (AC1, AC2).

    Transitions :
        EvidenceSubmission : PENDING → ACCEPTED
        Recommendation FSM : PENDING_DM_REVIEW → PENDING_AUDIT_REVIEW

    Exemption PV (FR19) : le DM peut uploader son propre PV de Recette (pv_file).
    Si fourni, il est sauvegardé comme EvidenceFile(tag=PV_RECETTE, uploaded_by=dm)
    sur la soumission, puis le commentaire DM devient optionnel.
    Sinon, le commentaire est requis.

    Args:
        recommendation: L'instance Recommendation en PENDING_DM_REVIEW.
        submission_id: UUID de l'EvidenceSubmission à valider.
        comment: Commentaire DM (optionnel si pv_file fourni, requis sinon).
        pv_file: Fichier PV de Recette uploadé par le DM (optionnel).
        performed_by: Utilisateur DM qui valide.
        ip_address: IP client pour l'AuditLog.

    Returns:
        Recommendation: L'instance avec status=PENDING_AUDIT_REVIEW.

    Raises:
        ValueError: Si le statut est incorrect, soumission introuvable,
                    ou commentaire manquant sans PV de Recette.
        PermissionDenied: Si performed_by n'est pas le DM assigné.
    """
    # Guard RBAC — avant tout verrouillage
    if recommendation.assigned_dm_id != performed_by.pk:
        raise PermissionDenied(
            "Seul le DM assigné peut valider les preuves de cette recommandation."
        )

    with transaction.atomic():
        rec = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if rec.status != Recommendation.Status.PENDING_DM_REVIEW:
            raise ValueError(
                f"La validation n'est possible qu'en état PENDING_DM_REVIEW "
                f"(état actuel : {rec.get_status_display()})."
            )

        submission = (
            EvidenceSubmission.objects.select_for_update()
            .filter(recommendation=rec, pk=submission_id)
            .first()
        )
        if submission is None:
            raise ValueError("Soumission introuvable pour cette recommandation.")

        if submission.status != EvidenceSubmission.SubmissionStatus.PENDING:
            raise ValueError(
                "Seule une soumission en attente (PENDING) peut être validée."
            )

        # Upload PV de Recette par le DM (FR19) — avant vérification d'exemption
        if pv_file is not None:
            validate_magic_bytes(pv_file, original_filename=pv_file.name)
            validate_file_size(pv_file)
            sha256 = compute_sha256(pv_file)
            mime = detect_mime_type(pv_file, original_filename=pv_file.name)
            EvidenceFile.objects.create(
                submission=submission,
                file=pv_file,
                original_filename=pv_file.name,
                file_size=pv_file.size,
                mime_type=mime,
                sha256_hash=sha256,
                tag=EvidenceFile.Tag.PV_RECETTE,
                uploaded_by=performed_by,
            )

        # Exemption PV de Recette (FR19) — inclut le fichier qu'on vient de créer
        has_pv_recette = submission.files.filter(
            tag=EvidenceFile.Tag.PV_RECETTE
        ).exists()

        if not has_pv_recette and not comment.strip():
            raise ValueError(
                "Un commentaire DM est requis si aucun PV de Recette n'est joint."
            )

        # Mettre à jour la soumission
        submission.status = EvidenceSubmission.SubmissionStatus.ACCEPTED
        submission.review_comment = comment
        submission.reviewed_at = timezone.now()
        submission.reviewed_by = performed_by
        submission.save(update_fields=[
            "status", "review_comment", "reviewed_at", "reviewed_by", "updated_at"
        ])

        # Transition FSM : PENDING_DM_REVIEW → PENDING_AUDIT_REVIEW
        rec.approve_for_audit()
        rec.save(update_fields=["status", "updated_at"])

        dm_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "status": ["PENDING_DM_REVIEW", "PENDING_AUDIT_REVIEW"],
            },
            description=(
                f"Validation DM {dm_display} → Audit pour {rec.reference}"
            ),
            ip_address=ip_address,
        )

    return rec


def become_dm_porteur(
    *,
    recommendation: Recommendation,
    performed_by,
    ip_address: str | None = None,
) -> Recommendation:
    """
    Le DM s'auto-assigne comme porteur de la recommandation (FR12 — Story 3.2).

    Le champ ``assigned_etp`` reste à null. La transition FSM
    ASSIGNED → IN_PROGRESS est effectuée, et l'action est tracée.

    Args:
        recommendation: L'instance en état ASSIGNED.
        performed_by: Le DM qui prend en charge personnellement.
        ip_address: Adresse IP du client.

    Returns:
        Recommendation: L'instance avec status=IN_PROGRESS, assigned_etp=null.

    Raises:
        ValueError: Si la recommandation n'est pas ASSIGNED.
    """
    with transaction.atomic():
        # Verrouiller pour concurrence (ADR-07 §5.4)
        recommendation = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        if recommendation.is_deleted:
            raise ValueError("Impossible de traiter une recommandation supprimée.")

        if recommendation.status != Recommendation.Status.ASSIGNED:
            raise ValueError(
                f"La prise en charge n'est possible qu'en état ASSIGNED. "
                f"Statut actuel : {recommendation.get_status_display()}"
            )

        # S'assurer que assigned_etp reste null
        recommendation.assigned_etp = None

        # Transition FSM : ASSIGNED → IN_PROGRESS
        recommendation.start_processing()
        recommendation.save(
            update_fields=["status", "assigned_etp", "updated_at"]
        )

        dm_display = performed_by.get_full_name() or performed_by.username

        # Audit Log
        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=recommendation.pk,
            changes={
                "status": ["ASSIGNED", "IN_PROGRESS"],
                "dm_porteur": [None, str(performed_by.pk)],
            },
            description=(
                f"DM Porteur : {dm_display} prend en charge "
                f"{recommendation.reference} personnellement"
            ),
            ip_address=ip_address,
        )

    return recommendation


# =============================================================================
# Draft Evidence Services (Story 3.3 v2 — Brouillons Persistants)
# =============================================================================


def get_or_create_draft_submission(
    *,
    recommendation: Recommendation,
    user,
) -> tuple[EvidenceSubmission, bool]:
    """
    Retourne le brouillon DRAFT actif ou en crée un.

    Utilise ``select_for_update()`` pour éviter les race conditions
    avec la ``UniqueConstraint`` conditionnelle en dernier rempart.

    Args:
        recommendation: La recommandation cible.
        user: L'ETP ou DM Porteur.

    Returns:
        tuple[EvidenceSubmission, bool]: (brouillon, created).
    """
    with transaction.atomic():
        draft = (
            EvidenceSubmission.objects
            .select_for_update()
            .filter(
                recommendation=recommendation,
                submitted_by=user,
                status=EvidenceSubmission.SubmissionStatus.DRAFT,
            )
            .first()
        )
        if draft:
            return draft, False

        draft = EvidenceSubmission.objects.create(
            recommendation=recommendation,
            submitted_by=user,
            status=EvidenceSubmission.SubmissionStatus.DRAFT,
            comment="",
        )
        return draft, True


def _get_active_evidence_quota_used(recommendation: Recommendation) -> int:
    """
    Calcule le quota utilisé (en octets) par les preuves actives d'une recommandation.

    Inclut les fichiers DRAFT, PENDING et ACCEPTED.
    Exclut les REJECTED (NFR-SCA-01).

    Returns:
        int: Nombre d'octets utilisés.
    """
    return (
        EvidenceFile.objects
        .filter(
            submission__recommendation=recommendation,
            submission__status__in=[
                EvidenceSubmission.SubmissionStatus.DRAFT,
                EvidenceSubmission.SubmissionStatus.PENDING,
                EvidenceSubmission.SubmissionStatus.ACCEPTED,
            ],
        )
        .aggregate(total=Sum("file_size"))["total"] or 0
    )


def add_file_to_draft(
    *,
    submission: EvidenceSubmission,
    file,
    user,
    ip_address: str | None = None,
) -> EvidenceFile:
    """
    Ajoute un fichier au brouillon DRAFT.

    Exécute les validations : magic bytes, taille 6 Mo, quota 20 Mo global.
    Calcule le SHA-256 et détecte le MIME type réel.

    Args:
        submission: Le brouillon DRAFT.
        file: Fichier Django uploadé.
        user: L'utilisateur effectuant l'upload.
        ip_address: Adresse IP du client.

    Returns:
        EvidenceFile: Le fichier probatoire créé.

    Raises:
        ValueError: Si la soumission n'est pas en DRAFT.
        PermissionDenied: Si l'utilisateur n'est pas l'auteur du brouillon.
        ValidationError: Si le fichier est invalide (format, taille, quota).
    """
    if submission.status != EvidenceSubmission.SubmissionStatus.DRAFT:
        raise ValueError("L'ajout de fichier n'est possible que sur un brouillon DRAFT.")

    if submission.submitted_by_id != user.pk:
        raise PermissionDenied("Seul l'auteur du brouillon peut y ajouter des fichiers.")

    # Validations de sécurité (NFR-SEC-04)
    original_filename = file.name
    validate_magic_bytes(file, original_filename=original_filename)
    validate_file_size(file)

    # Calcul intégrité + détection MIME (hors transaction — opérations en lecture seule)
    sha256 = compute_sha256(file)
    mime = detect_mime_type(file, original_filename=original_filename)

    with transaction.atomic():
        # Verrou pessimiste pour sérialiser les uploads concurrents (NFR-SCA-01)
        submission = EvidenceSubmission.objects.select_for_update().get(pk=submission.pk)

        # Vérification quota global dans la transaction (évite la race condition)
        from django.core.exceptions import ValidationError
        existing_bytes = _get_active_evidence_quota_used(submission.recommendation)
        if existing_bytes + file.size > 20 * 1024 * 1024:
            raise ValidationError(
                f"Quota dépassé (NFR-SCA-01) : {existing_bytes / (1024 * 1024):.1f} Mo "
                f"utilisés + {file.size / (1024 * 1024):.1f} Mo > limite de 20 Mo."
            )

        evidence_file = EvidenceFile(
            submission=submission,
            original_filename=original_filename,
            file_size=file.size,
            mime_type=mime,
            sha256_hash=sha256,
            tag=EvidenceFile.Tag.JUSTIFICATIF,
            uploaded_by=user,
        )
        evidence_file.file = file
        evidence_file.save()

        # Touch le brouillon pour mettre à jour updated_at
        submission.save(update_fields=["updated_at"])

        AuditLog.objects.create(
            action=AuditLog.Action.UPDATE,
            user=user,
            content_type="EvidenceFile",
            object_id=evidence_file.pk,
            changes={
                "action": "draft_file_added",
                "file_size": file.size,
                "mime_type": mime,
            },
            description=(
                f"Ajout du fichier « {original_filename} » ({file.size / 1024:.0f} Ko) "
                f"au brouillon de {submission.recommendation.reference}"
            ),
            ip_address=ip_address,
        )

    return evidence_file


def delete_draft_file(
    *,
    file: EvidenceFile,
    user,
    ip_address: str | None = None,
) -> None:
    """
    Supprime un fichier du brouillon DRAFT.

    La méthode ``EvidenceFile.delete()`` conditionnelle autorise
    la suppression uniquement si la soumission est en DRAFT.

    Args:
        file: Le fichier probatoire à supprimer.
        user: L'utilisateur effectuant la suppression.
        ip_address: Adresse IP du client.

    Raises:
        PermissionDenied: Si l'utilisateur n'est pas l'auteur du brouillon
            ou si la soumission n'est pas en DRAFT.
    """
    submission = file.submission

    if submission.submitted_by_id != user.pk:
        raise PermissionDenied("Seul l'auteur du brouillon peut supprimer ses fichiers.")

    # Stocker les infos avant suppression pour l'audit log
    filename = file.original_filename
    file_pk = file.pk
    reco_ref = submission.recommendation.reference

    with transaction.atomic():
        # EvidenceFile.delete() vérifie le statut DRAFT de la soumission
        file.delete()

        # Touch le brouillon pour mettre à jour updated_at
        submission.save(update_fields=["updated_at"])

        AuditLog.objects.create(
            action=AuditLog.Action.DELETE,
            user=user,
            content_type="EvidenceFile",
            object_id=file_pk,
            changes={
                "action": "draft_file_deleted",
                "original_filename": filename,
            },
            description=(
                f"Suppression du fichier « {filename} » du brouillon de {reco_ref}"
            ),
            ip_address=ip_address,
        )


def save_draft_comment(
    *,
    submission: EvidenceSubmission,
    comment: str,
    user,
) -> EvidenceSubmission:
    """
    Met à jour le commentaire du brouillon DRAFT (autosave).

    Args:
        submission: Le brouillon DRAFT.
        comment: Le nouveau texte du commentaire.
        user: L'utilisateur effectuant la modification.

    Returns:
        EvidenceSubmission: Le brouillon mis à jour.

    Raises:
        ValueError: Si la soumission n'est pas en DRAFT.
        PermissionDenied: Si l'utilisateur n'est pas l'auteur du brouillon.
    """
    if submission.status != EvidenceSubmission.SubmissionStatus.DRAFT:
        raise ValueError("La modification du commentaire n'est possible que sur un brouillon DRAFT.")

    if submission.submitted_by_id != user.pk:
        raise PermissionDenied("Seul l'auteur du brouillon peut modifier le commentaire.")

    submission.comment = comment
    submission.save(update_fields=["comment", "updated_at"])

    return submission


def toggle_deliverable_completion(
    *,
    deliverable: Deliverable,
    user,
    ip_address: str | None = None,
) -> Deliverable:
    """
    Bascule l'état de complétion d'un livrable (toggle on/off).

    Args:
        deliverable: Le livrable à toggler.
        user: L'utilisateur effectuant le toggle.
        ip_address: Adresse IP du client.

    Returns:
        Deliverable: Le livrable mis à jour.
    """
    with transaction.atomic():
        if deliverable.is_completed:
            # Décochage
            deliverable.is_completed = False
            deliverable.completed_at = None
            deliverable.completed_by = None
        else:
            # Cochage
            deliverable.is_completed = True
            deliverable.completed_at = timezone.now()
            deliverable.completed_by = user

        deliverable.save(
            update_fields=["is_completed", "completed_at", "completed_by"]
        )

        user_display = user.get_full_name() or user.username
        action_label = "coché" if deliverable.is_completed else "décoché"

        AuditLog.objects.create(
            action=AuditLog.Action.UPDATE,
            user=user,
            content_type="Deliverable",
            object_id=deliverable.pk,
            changes={
                "is_completed": [not deliverable.is_completed, deliverable.is_completed],
                "label": deliverable.label,
            },
            description=(
                f"Livrable « {deliverable.label} » {action_label} "
                f"par {user_display}"
            ),
            ip_address=ip_address,
        )

    return deliverable


def cleanup_abandoned_drafts(
    *,
    max_age_days: int = 90,
) -> int:
    """
    Supprime les brouillons DRAFT abandonnés (non modifiés depuis max_age_days).

    Supprime les fichiers physiques associés et les enregistrements DB.
    Destiné à être appelé par un CRON quotidien (Django-Q2).

    Args:
        max_age_days: Nombre de jours d'inactivité avant nettoyage (défaut: 90).

    Returns:
        int: Nombre de brouillons supprimés.
    """
    cutoff = timezone.now() - timezone.timedelta(days=max_age_days)

    abandoned = EvidenceSubmission.objects.filter(
        status=EvidenceSubmission.SubmissionStatus.DRAFT,
        updated_at__lt=cutoff,
    )

    count = abandoned.count()
    if count == 0:
        return 0

    with transaction.atomic():
        # Supprimer les fichiers physiques des brouillons abandonnés
        for draft in abandoned.prefetch_related("files"):
            for evidence_file in draft.files.all():
                if evidence_file.file:
                    evidence_file.file.delete(save=False)

        # Supprimer les enregistrements DB (CASCADE supprime les EvidenceFile)
        abandoned.delete()

        AuditLog.objects.create(
            action=AuditLog.Action.DELETE,
            user=None,
            content_type="EvidenceSubmission",
            object_id=None,
            changes={
                "action": "cleanup_abandoned_drafts",
                "count": count,
                "max_age_days": max_age_days,
            },
            description=(
                f"Nettoyage CRON : {count} brouillon(s) abandonné(s) "
                f"supprimé(s) (inactifs depuis > {max_age_days} jours)"
            ),
        )

    return count


# =============================================================================
# Demandes de Report d'Échéance (Story 3.6 — FR13, FR14, FR34)
# =============================================================================


def request_extension(
    *,
    recommendation: Recommendation,
    requested_date,
    reason: str,
    performed_by,
    ip_address: str | None = None,
):
    """
    Soumet une demande de report d'échéance (FR13 — DM, FR34 — DG).

    Guard RBAC : seul l'utilisateur dont ``recommendation.assigned_dm == performed_by``
    est autorisé, qu'il soit DM ou DG. L'assignation personnelle est le seul critère.

    Args:
        recommendation: La recommandation concernée.
        requested_date: Nouvelle date souhaitée (doit être > due_date).
        reason: Motif obligatoire.
        performed_by: DM ou DG personnellement assigné.
        ip_address: Adresse IP du client.

    Returns:
        ExtensionRequest: L'instance PENDING créée.

    Raises:
        PermissionDenied: Si performed_by n'est pas le DM/DG assigné.
        ValueError: Si l'état FSM interdit la demande, si une demande PENDING
                    existe déjà, ou si la date est invalide.
    """
    from .models import ExtensionRequest

    # Guard RBAC — assignation personnelle (FR13 + FR34)
    if performed_by != recommendation.assigned_dm:
        raise PermissionDenied(
            "Seul le directeur personnellement assigné peut soumettre une demande de report."
        )

    with transaction.atomic():
        rec = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        # Guard état FSM — impossible en DRAFT ou CLOSED_RESOLVED
        if rec.status in (
            Recommendation.Status.DRAFT,
            Recommendation.Status.CLOSED_RESOLVED,
        ):
            raise ValueError(
                f"Une demande de report n'est pas possible en état "
                f"« {rec.get_status_display()} »."
            )

        # Guard doublon — une seule demande PENDING à la fois
        if ExtensionRequest.objects.filter(
            recommendation=rec,
            status=ExtensionRequest.Status.PENDING,
        ).exists():
            raise ValueError(
                "Une demande de report est déjà en attente pour cette recommandation."
            )

        # Guard date — doit être postérieure à l'échéance actuelle
        if requested_date <= rec.due_date:
            raise ValueError(
                "La nouvelle date doit être postérieure à l'échéance actuelle."
            )

        ext = ExtensionRequest.objects.create(
            recommendation=rec,
            requested_by=performed_by,
            requested_date=requested_date,
            reason=reason,
            status=ExtensionRequest.Status.PENDING,
        )

        requester_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.EXTENSION_REQUESTED,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "extension_id": str(ext.pk),
                "requested_date": str(requested_date),
                "reason": reason[:100],
                "current_due_date": str(rec.due_date),
            },
            description=(
                f"Demande de report soumise par {requester_display} "
                f"pour {rec.reference} — nouvelle date : {requested_date}"
            ),
            ip_address=ip_address,
        )

    return ext


def approve_extension(
    *,
    extension_request,
    performed_by,
    audit_comment: str = "",
    ip_address: str | None = None,
):
    """
    Approuve une demande de report d'échéance (FR14 — AC4).

    Met à jour ``Recommendation.due_date`` avec ``ExtensionRequest.requested_date``.
    N'altère JAMAIS ``original_due_date`` (invariant COBAC — AC8).
    Le commentaire est optionnel lors de l'approbation.

    Args:
        extension_request: L'instance ExtensionRequest PENDING.
        performed_by: Auditeur qui approuve (role == AUDIT).
        audit_comment: Commentaire optionnel (défaut vide).
        ip_address: Adresse IP du client.

    Returns:
        ExtensionRequest: L'instance mise à jour (status=APPROVED).

    Raises:
        PermissionDenied: Si performed_by n'est pas AUDIT.
        ValueError: Si la demande n'est pas en PENDING.
    """
    from apps.users.models import User
    from .models import ExtensionRequest

    # Guard RBAC — tout auditeur peut approuver (AC7 : is_audit_admin NON requis)
    if performed_by.role != User.Role.AUDIT:
        raise PermissionDenied(
            "Seul un Auditeur Interne peut approuver une demande de report."
        )

    # Guard état — demande PENDING uniquement
    if extension_request.status != ExtensionRequest.Status.PENDING:
        raise ValueError(
            f"Seule une demande en attente peut être approuvée "
            f"(statut actuel : {extension_request.get_status_display()})."
        )

    with transaction.atomic():
        ext = (
            ExtensionRequest.objects
            .select_for_update()
            .get(pk=extension_request.pk)
        )
        rec = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=ext.recommendation_id)
        )

        old_due_date = rec.due_date
        new_due_date = ext.requested_date

        # Mise à jour de la demande
        ext.status = ExtensionRequest.Status.APPROVED
        ext.reviewed_by = performed_by
        ext.reviewed_at = timezone.now()
        ext.audit_comment = audit_comment  # Peut être vide (AC4)
        ext.save(update_fields=["status", "reviewed_by", "reviewed_at", "audit_comment"])

        # Mise à jour de l'échéance (JAMAIS original_due_date — AC8)
        rec.due_date = new_due_date
        rec.save(update_fields=["due_date", "updated_at"])

        auditor_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.EXTENSION_APPROVED,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "extension_id": str(ext.pk),
                "due_date": [str(old_due_date), str(new_due_date)],
            },
            description=(
                f"Report approuvé par {auditor_display} pour "
                f"{rec.reference} — nouvelle échéance : {new_due_date}"
            ),
            ip_address=ip_address,
        )

    return ext


def reject_extension(
    *,
    extension_request,
    performed_by,
    audit_comment: str,
    ip_address: str | None = None,
):
    """
    Rejette une demande de report d'échéance (FR14 — AC5).

    ``Recommendation.due_date`` reste inchangé.
    Le commentaire est OBLIGATOIRE (différence clé vs approve_extension).

    Args:
        extension_request: L'instance ExtensionRequest PENDING.
        performed_by: Auditeur qui rejette (role == AUDIT).
        audit_comment: Motif de rejet obligatoire.
        ip_address: Adresse IP du client.

    Returns:
        ExtensionRequest: L'instance mise à jour (status=REJECTED).

    Raises:
        PermissionDenied: Si performed_by n'est pas AUDIT.
        ValueError: Si la demande n'est pas PENDING ou si le motif est vide.
    """
    from apps.users.models import User
    from .models import ExtensionRequest

    # Guard RBAC — tout auditeur peut rejeter (AC7)
    if performed_by.role != User.Role.AUDIT:
        raise PermissionDenied(
            "Seul un Auditeur Interne peut rejeter une demande de report."
        )

    # Guard motif — obligatoire au rejet (AC5)
    if not audit_comment or not audit_comment.strip():
        raise ValueError("Le motif de rejet est obligatoire.")

    # Guard état — demande PENDING uniquement
    if extension_request.status != ExtensionRequest.Status.PENDING:
        raise ValueError(
            f"Seule une demande en attente peut être rejetée "
            f"(statut actuel : {extension_request.get_status_display()})."
        )

    with transaction.atomic():
        ext = (
            ExtensionRequest.objects
            .select_for_update()
            .get(pk=extension_request.pk)
        )
        rec = Recommendation.all_objects.get(pk=ext.recommendation_id)

        ext.status = ExtensionRequest.Status.REJECTED
        ext.reviewed_by = performed_by
        ext.reviewed_at = timezone.now()
        ext.audit_comment = audit_comment
        ext.save(update_fields=["status", "reviewed_by", "reviewed_at", "audit_comment"])

        # due_date de la recommandation est INCHANGÉ (AC5)

        auditor_display = performed_by.get_full_name() or performed_by.username

        AuditLog.objects.create(
            action=AuditLog.Action.EXTENSION_REJECTED,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "extension_id": str(ext.pk),
                "audit_comment": audit_comment[:100],
                "due_date_maintained": str(rec.due_date),
            },
            description=(
                f"Report rejeté par {auditor_display} pour "
                f"{rec.reference} — échéance maintenue : {rec.due_date}"
            ),
            ip_address=ip_address,
        )

    return ext


# =============================================================================
# Soumission Directe DG (Story 3.7 — FR33)
# =============================================================================


def submit_evidence_by_dg(
    *,
    recommendation,
    performed_by,
    ip_address=None,
):
    """
    Soumet directement des preuves à l'Audit Interne au nom du DG assigné (FR33).

    Bypass complet du circuit DM Review : la recommandation passe de ASSIGNED/IN_PROGRESS
    directement à PENDING_AUDIT_REVIEW sans transiter par PENDING_DM_REVIEW.

    Args:
        recommendation: La recommandation cible (doit être ASSIGNED ou IN_PROGRESS).
        performed_by: L'utilisateur DG effectuant la soumission.
        ip_address: L'adresse IP du client (pour l'AuditLog).

    Returns:
        Recommendation: La recommandation mise à jour (status=PENDING_AUDIT_REVIEW).

    Raises:
        PermissionDenied: Si performed_by n'a pas le rôle DG ou n'est pas assigned_dm.
        ValueError: Si l'état FSM ne permet pas la soumission directe (AC6),
                    ou si le draft est vide (AC3).

    ACs couverts : AC2, AC3, AC4, AC5, AC6.
    """
    from apps.users.models import User

    # Guard RBAC pré-transaction (AC5) — rôle DG obligatoire
    if performed_by.role != User.Role.DG:
        raise PermissionDenied(
            "Endpoint réservé au rôle DG."
        )
    # Guard RBAC pré-transaction (AC5) — DG doit être assigned_dm
    if recommendation.assigned_dm_id != performed_by.pk:
        raise PermissionDenied(
            "Vous n'êtes pas le DG assigné à cette recommandation."
        )

    with transaction.atomic():
        rec = (
            Recommendation.all_objects
            .select_for_update()
            .get(pk=recommendation.pk)
        )

        # Re-vérification RBAC sur instance fraîche (parade TOCTOU)
        if rec.assigned_dm_id != performed_by.pk:
            raise PermissionDenied(
                "Vous n'êtes plus le DG assigné à cette recommandation."
            )

        # Guard FSM (AC6) — soumission directe impossible hors ASSIGNED/IN_PROGRESS
        if rec.status not in (
            Recommendation.Status.ASSIGNED,
            Recommendation.Status.IN_PROGRESS,
        ):
            raise ValueError(
                f"Soumission directe impossible depuis l'état « {rec.status} »."
            )

        # Récupérer ou créer le draft DG (AC2 — réutilise get_or_create_draft_submission)
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=performed_by)

        # Guard contenu (AC3) — au moins un fichier OU un commentaire non vide
        if not draft.files.exists() and not draft.comment.strip():
            raise ValueError(
                "Veuillez joindre au moins un fichier ou saisir un commentaire."
            )

        source_status = rec.status

        # Valider le draft directement (AC2) — bypass DM Review
        draft.status = EvidenceSubmission.SubmissionStatus.ACCEPTED
        draft.reviewed_by = performed_by
        draft.reviewed_at = timezone.now()
        draft.save()

        # Transition FSM directe (AC2)
        rec.submit_directly_to_audit()
        rec.save()

        # AuditLog (AC4 — NFR-SEC-05 append-only)
        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="Recommendation",
            object_id=rec.pk,
            changes={
                "status": [source_status, Recommendation.Status.PENDING_AUDIT_REVIEW],
                "submitted_by_dg": True,
            },
            description=(
                f"Soumission directe DG {performed_by.get_full_name()} "
                f"pour {rec.reference}"
            ),
            ip_address=ip_address,
        )

    return rec
