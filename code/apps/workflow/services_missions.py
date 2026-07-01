"""
Workflow App — Services Missions Externes (Convention HackSoft)

Mutations des missions d'audit externe (création, modification, transition de
statut). Chaque opération est tracée dans l'AuditLog (doctrine chaîne
AUDIT-fermée, FR25) — contrairement à un appel direct à form.save() dans la vue.
"""
from django.db import transaction

from apps.audit.models import AuditLog
from apps.users.models import ExternalMission


@transaction.atomic
def create_mission(*, form, created_by, ip_address=None) -> ExternalMission:
    """Crée une mission depuis un ExternalMissionForm validé et trace l'action."""
    mission = form.save(commit=False)
    mission.created_by = created_by
    mission.save()
    form.save_m2m()

    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=created_by,
        content_type="ExternalMission",
        object_id=mission.pk,
        changes={
            "name": mission.name,
            "organisation": str(mission.organisation) if mission.organisation else None,
            "status": mission.status,
        },
        description=f"Mission externe '{mission.name}' créée.",
        ip_address=ip_address,
    )
    return mission


@transaction.atomic
def update_mission(*, mission, form, performed_by, ip_address=None) -> ExternalMission:
    """Met à jour une mission depuis un ExternalMissionForm validé et trace l'action."""
    mission = form.save()

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="ExternalMission",
        object_id=mission.pk,
        changes={
            "name": mission.name,
            "organisation": str(mission.organisation) if mission.organisation else None,
            "status": mission.status,
        },
        description=f"Mission externe '{mission.name}' modifiée.",
        ip_address=ip_address,
    )
    return mission


def toggle_mission_status(*, mission, new_status, performed_by, ip_address=None) -> ExternalMission:
    """
    Change le statut d'une mission. Lève ValueError si la transition est invalide.

    Transitions autorisées : PREPARATION → ACTIVE → CLOSED uniquement.
    Positionne approved_by lors du premier passage en ACTIVE.
    """
    _VALID_TRANSITIONS = {
        ExternalMission.Status.PREPARATION: {ExternalMission.Status.ACTIVE},
        ExternalMission.Status.ACTIVE: {ExternalMission.Status.CLOSED},
    }

    with transaction.atomic():
        # Verrou pessimiste — sérialise les transitions concurrentes
        mission = ExternalMission.objects.select_for_update().get(pk=mission.pk)

        allowed = _VALID_TRANSITIONS.get(mission.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Transition de statut invalide : {mission.status} → {new_status}. "
                f"Transitions autorisées depuis « {mission.status} » : "
                f"{', '.join(allowed) if allowed else 'aucune'}."
            )

        old_status = mission.status
        mission.status = new_status
        update_fields = ["status"]
        if new_status == ExternalMission.Status.ACTIVE and not mission.approved_by:
            mission.approved_by = performed_by
            update_fields.append("approved_by")
        mission.save(update_fields=update_fields)

        AuditLog.objects.create(
            action=AuditLog.Action.TRANSITION,
            user=performed_by,
            content_type="ExternalMission",
            object_id=mission.pk,
            changes={"status": [old_status, new_status]},
            description=(
                f"Statut de la mission '{mission.name}' : "
                f"{old_status} → {new_status}."
            ),
            ip_address=ip_address,
        )
    return mission
