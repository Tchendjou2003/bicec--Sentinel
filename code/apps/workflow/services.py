"""
Workflow App — Services (Convention HackSoft)

Logique d'écriture pour le cycle de vie des recommandations.
Chaque mutation est tracée dans l'Audit Log (NFR-SEC-05).

Spécifications couvertes :
    - FR5  : Création manuelle unitaire
    - FR6  : Soft Delete en état DRAFT
    - FR6b : État DRAFT pré-assignation
"""
from django.db import transaction
from django.utils import timezone

from ..audit.models import AuditLog
from .models import Deliverable, Recommendation


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
