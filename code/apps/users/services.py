"""
Users App — Services (Convention HackSoft)

Logique d'écriture pour l'habilitation des comptes et le provisioning.
Chaque mutation est tracée dans l'Audit Log (NFR-SEC-05).

Spécifications couvertes :
    - FR3   : Attribution des rôles métiers
    - FR36  : Délégation is_audit_admin
    - ADR-10 : Séparation des fonctions
    - Story 6.2.0 : Maker/Checker provisioning
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from ..audit.models import AuditLog
from .models import Department, OrgUnitType, User, UserProvisioningRequest


def user_is_provisioning_approver(user: User) -> bool:
    """
    Retourne True si l'utilisateur est membre du groupe « Administrateurs Sentinel »
    ou superuser (Story 6.2.0).

    Utilisé à la fois dans les mixins de vues et dans le service assign_role.
    Mise en cache via requête groups unique (préférer select_related/prefetch
    en contexte de liste).
    """
    if user.is_superuser:
        return True
    return user.groups.filter(
        name=settings.PROVISIONING_APPROVER_GROUP_NAME
    ).exists()


def assign_role(
    *,
    target_user: User,
    role: str,
    department: Department | None,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """
    Attribue un rôle métier et un département à un utilisateur.

    Args:
        target_user: Le compte à habiliter.
        role: Le rôle métier (User.Role).
        department: Le département de rattachement (peut être None pour AUDIT/ADMIN).
        performed_by: L'administrateur Audit effectuant l'action.

    Raises:
        PermissionDenied: Si performed_by n'a pas le droit can_manage_users.
        ValueError: Si le rôle est invalide.
    """
    if not user_is_provisioning_approver(performed_by):
        raise PermissionDenied(
            "Seul un membre du groupe « Administrateurs Sentinel » peut attribuer des rôles."
        )

    valid_roles = {choice[0] for choice in User.Role.choices}
    if role and role not in valid_roles:
        raise ValueError(f"Rôle invalide : {role}")

    old_role = target_user.role
    old_dept = target_user.department

    target_user.role = role
    target_user.department = department
    target_user.save(update_fields=["role", "department"])

    # Trace dans l'Audit Log
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="User",
        object_id=target_user.pk,
        changes={
            "role": [old_role, role],
            "department": [
                str(old_dept.pk) if old_dept else None,
                str(department.pk) if department else None,
            ],
        },
        description=(
            f"Habilitation : rôle '{old_role or 'vide'}' → '{role}' "
            f"pour {target_user.username} par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return target_user


def toggle_audit_admin(
    *,
    target_user: User,
    grant: bool,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """
    Active ou désactive le flag is_audit_admin (FR36).

    Args:
        target_user: L'auditeur cible.
        grant: True pour accorder, False pour révoquer.
        performed_by: Le Directeur Audit effectuant la délégation.

    Raises:
        PermissionDenied: Si performed_by n'a pas le droit.
        ValueError: Si la cible n'est pas un Auditeur Interne.
    """
    if not (performed_by.can_manage_users or performed_by.is_superuser):
        raise PermissionDenied(
            "Seul un administrateur Audit peut déléguer ce droit."
        )

    if target_user.role != User.Role.AUDIT:
        raise ValueError(
            "Le flag is_audit_admin ne peut être attribué qu'aux Auditeurs Internes."
        )

    old_value = target_user.is_audit_admin
    target_user.is_audit_admin = grant
    target_user.save(update_fields=["is_audit_admin"])

    action_label = "accordée" if grant else "révoquée"
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="User",
        object_id=target_user.pk,
        changes={"is_audit_admin": [old_value, grant]},
        description=(
            f"Délégation admin {action_label} : "
            f"{target_user.username} par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return target_user


@transaction.atomic
def create_department_with_audit(
    *,
    form,
    performed_by: User,
    ip_address: str | None = None,
) -> Department:
    """Création d'un département avec trace d'audit."""
    dept = form.save()
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=performed_by,
        content_type="Department",
        object_id=dept.pk,
        changes={"name": [None, dept.name]},
        description=f"Création du département : {dept.name} par {performed_by.username}",
        ip_address=ip_address,
    )
    return dept


@transaction.atomic
def update_department_with_audit(
    *,
    form,
    performed_by: User,
    ip_address: str | None = None,
) -> Department:
    """Modification d'un département avec trace d'audit."""
    old_name = form.instance.name if form.instance.pk else None
    dept = form.save()
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="Department",
        object_id=dept.pk,
        changes={"name": [old_name, dept.name]},
        description=f"Modification du département : {dept.name} par {performed_by.username}",
        ip_address=ip_address,
    )
    return dept


@transaction.atomic
def soft_delete_department_with_audit(
    *, 
    department: Department, 
    performed_by: User,
    ip_address: str | None = None,
) -> Department:
    """Désactivation (soft-delete) d'un département avec trace d'audit."""
    if Department.objects.filter(parent=department, is_active=True).exists():
        raise ValueError("Impossible de supprimer une structure contenant des sous-structures actives.")
    if User.objects.filter(department=department, is_active=True).exists():
        raise ValueError("Impossible de supprimer une structure contenant des utilisateurs actifs.")
        
    department.is_active = False
    department.save(update_fields=["is_active"])
    AuditLog.objects.create(
        action=AuditLog.Action.DELETE,
        user=performed_by,
        content_type="Department",
        object_id=department.pk,
        changes={"is_active": [True, False]},
        description=f"Suppression (désactivation) du département : {department.name} par {performed_by.username}",
        ip_address=ip_address,
    )
    return department


@transaction.atomic
def create_org_unit_type(
    *,
    form,
    performed_by: User,
    ip_address: str | None = None,
) -> OrgUnitType:
    """
    Création d'un type d'unité organisationnelle avec trace d'audit.

    Le ``code`` est verrouillé à la création (immuable).
    """
    instance = form.save()
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=performed_by,
        content_type="OrgUnitType",
        object_id=instance.pk,
        changes={"code": [None, instance.code], "name": [None, instance.name]},
        description=(
            f"Création du type d'unité : {instance.name} ({instance.code}) "
            f"par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return instance


@transaction.atomic
def update_org_unit_type(
    *,
    form,
    performed_by: User,
    ip_address: str | None = None,
) -> OrgUnitType:
    """
    Modification du libellé ou du niveau d'un type d'unité.

    Le ``code`` est immuable — le formulaire doit le désactiver en édition.
    Seuls ``name``, ``level`` et ``is_active`` peuvent changer.
    """
    instance_before = form.instance
    old_name = instance_before.name
    old_level = instance_before.level
    instance = form.save()
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="OrgUnitType",
        object_id=instance.pk,
        changes={
            "name": [old_name, instance.name],
            "level": [old_level, instance.level],
        },
        description=(
            f"Modification du type d'unité : {instance.code} "
            f"par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return instance


@transaction.atomic
def toggle_org_unit_type(
    *,
    instance: OrgUnitType,
    performed_by: User,
    ip_address: str | None = None,
) -> OrgUnitType:
    """Active ou désactive un type d'unité organisationnelle."""
    old_value = instance.is_active
    instance.is_active = not old_value
    instance.save(update_fields=["is_active"])
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="OrgUnitType",
        object_id=instance.pk,
        changes={"is_active": [old_value, instance.is_active]},
        description=(
            f"Type d'unité {'activé' if instance.is_active else 'désactivé'} : "
            f"{instance.code} par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return instance


@transaction.atomic
def create_shell_account_with_audit(
    *,
    form,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """Création d'un compte coquille vide avec trace d'audit."""
    user = form.save()
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=performed_by,
        content_type="User",
        object_id=user.pk,
        changes={"username": [None, user.username]},
        description=f"Création du compte (coquille vide) : {user.username} par {performed_by.username}",
        ip_address=ip_address,
    )
    return user


# =============================================================================
# Services Maker/Checker Provisioning (Story 6.2.0)
# =============================================================================


def create_provisioning_request(
    *,
    maker: User,
    cleaned_data: dict,
    ip_address: str | None = None,
) -> UserProvisioningRequest:
    """
    Crée une demande de provisioning à l'état PENDING (Story 6.2.0 / AC1).

    Le mot de passe en clair (``cleaned_data["password"]``) est haché ici
    via ``make_password`` avant persistance. Le champ ``hashed_initial_password``
    ne contient jamais le clair.

    Notifie tous les membres du groupe « Administrateurs Sentinel ».
    Émet un AuditLog (CREATE, content_type="UserProvisioningRequest").
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import notify_group

    # Hachage du mot de passe en clair
    plain_password = cleaned_data.get("password", "")
    hashed = make_password(plain_password)

    req = UserProvisioningRequest(
        requested_username=cleaned_data["requested_username"],
        requested_first_name=cleaned_data.get("requested_first_name", ""),
        requested_last_name=cleaned_data.get("requested_last_name", ""),
        requested_email=cleaned_data["requested_email"],
        hashed_initial_password=hashed,
        requested_role=cleaned_data["requested_role"],
        requested_department=cleaned_data.get("requested_department"),
        # Champs mission EXT
        mission_organization=cleaned_data.get("mission_organization", ""),
        mission_scope=cleaned_data.get("mission_scope", ""),
        mission_start_date=cleaned_data.get("mission_start_date"),
        mission_end_date=cleaned_data.get("mission_end_date"),
        status=UserProvisioningRequest.Status.PENDING,
        requested_by=maker,
    )
    req.full_clean()
    req.save()

    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=maker,
        content_type="UserProvisioningRequest",
        object_id=req.pk,
        changes={
            "requested_username": [None, req.requested_username],
            "requested_role": [None, req.requested_role],
        },
        description=(
            f"Demande de provisioning créée : '{req.requested_username}' "
            f"({req.get_requested_role_display()}) par {maker.username}"
        ),
        ip_address=ip_address,
    )

    notify_group(
        group_name=settings.PROVISIONING_APPROVER_GROUP_NAME,
        notification_type=Notification.Type.PROVISIONING_REQUESTED,
        title=f"Nouvelle demande de compte : {req.requested_username}",
        key_prefix=f"PROVISIONING_REQUESTED:{req.pk}",
        body=(
            f"Demandé par {maker.username} — "
            f"Rôle : {req.get_requested_role_display()}"
        ),
        url=f"/auth/admin/provisioning/{req.pk}/",
    )

    return req


@transaction.atomic
def approve_provisioning_request(
    *,
    request: UserProvisioningRequest,
    checker: User,
    ip_address: str | None = None,
) -> User:
    """
    Approuve une demande PENDING et crée le User (Story 6.2.0 / AC2).

    Toute la séquence est atomique : création User + mise à jour Request
    + AuditLogs. Si le rôle est EXT, une ExternalMission est également
    créée dans la même transaction.

    ⚠️ Piège double-hachage : on affecte ``user.password`` directement
    (valeur déjà hachée) plutôt que ``create_user(password=...)``
    qui re-hacherait et rendrait le login impossible.
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification
    from .models import ExternalMission  # import local pour éviter la circularité

    if request.status != UserProvisioningRequest.Status.PENDING:
        raise ValueError("Seules les demandes PENDING peuvent être approuvées.")

    # Revalider l'unicité username/email (collision potentielle après soumission)
    if User.objects.filter(username__iexact=request.requested_username).exists():
        raise ValidationError(
            f"Le nom d'utilisateur '{request.requested_username}' est déjà pris."
        )
    if User.objects.filter(email__iexact=request.requested_email).exists():
        raise ValidationError(
            f"L'e-mail '{request.requested_email}' est déjà utilisé."
        )

    is_ext = request.requested_role == User.Role.EXT

    # Création du User (sans password dans create_user — cf. piège #1 Dev Notes)
    user = User(
        username=request.requested_username,
        email=request.requested_email,
        first_name=request.requested_first_name,
        last_name=request.requested_last_name,
        role=request.requested_role,
        department=request.requested_department,
        is_external=is_ext,
    )
    user.password = request.hashed_initial_password  # hash déjà calculé
    user.save()

    # AuditLog — création du User
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=checker,
        content_type="User",
        object_id=user.pk,
        changes={
            "username": [None, user.username],
            "role": [None, user.role],
            "department": [None, str(user.department_id) if user.department_id else None],
        },
        description=(
            f"Compte créé par approbation provisioning : '{user.username}' "
            f"({user.get_role_display()}) — approuvé par {checker.username}"
        ),
        ip_address=ip_address,
    )

    # Création ExternalMission si EXT (dans la même transaction)
    if is_ext:
        mission = ExternalMission(
            auditor=user,
            organization=request.mission_organization,
            scope_description=request.mission_scope,
            start_date=request.mission_start_date,
            end_date=request.mission_end_date,
            is_active=True,
        )
        mission.save()

        AuditLog.objects.create(
            action=AuditLog.Action.CREATE,
            user=checker,
            content_type="ExternalMission",
            object_id=mission.pk,
            changes={
                "auditor": [None, str(user.pk)],
                "organization": [None, mission.organization],
            },
            description=(
                f"Mission externe créée pour '{user.username}' "
                f"({mission.organization}) — provisioning approuvé par {checker.username}"
            ),
            ip_address=ip_address,
        )

    # Mise à jour de la demande
    now = timezone.now()
    request.status = UserProvisioningRequest.Status.APPROVED
    request.reviewed_by = checker
    request.reviewed_at = now
    request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    # AuditLog — approbation de la demande
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=checker,
        content_type="UserProvisioningRequest",
        object_id=request.pk,
        changes={"status": [UserProvisioningRequest.Status.PENDING, UserProvisioningRequest.Status.APPROVED]},
        description=(
            f"Demande de provisioning approuvée : '{request.requested_username}' "
            f"par {checker.username}"
        ),
        ip_address=ip_address,
    )

    # Notification au maker
    emit_notification(
        recipient=request.requested_by,
        notification_type=Notification.Type.PROVISIONING_APPROVED,
        title=f"Votre demande a été approuvée : {request.requested_username}",
        idempotency_key=f"PROVISIONING_APPROVED:{request.pk}",
        body=f"Approuvé par {checker.username}. L'utilisateur peut désormais se connecter.",
        url="/auth/admin/provisioning/",
    )

    return user


def reject_provisioning_request(
    *,
    request: UserProvisioningRequest,
    checker: User,
    reason: str,
    ip_address: str | None = None,
) -> UserProvisioningRequest:
    """
    Rejette une demande PENDING avec un motif obligatoire (Story 6.2.0 / AC3).

    La demande passe à REJECTED et ne peut pas être recyclée.
    Aucun User n'est créé.
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification

    if request.status != UserProvisioningRequest.Status.PENDING:
        raise ValueError("Seules les demandes PENDING peuvent être rejetées.")

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Le motif de rejet est obligatoire.")

    now = timezone.now()
    request.status = UserProvisioningRequest.Status.REJECTED
    request.rejection_reason = reason
    request.reviewed_by = checker
    request.reviewed_at = now
    request.save(update_fields=[
        "status", "rejection_reason", "reviewed_by", "reviewed_at"
    ])

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=checker,
        content_type="UserProvisioningRequest",
        object_id=request.pk,
        changes={"status": [UserProvisioningRequest.Status.PENDING, UserProvisioningRequest.Status.REJECTED]},
        description=(
            f"Demande de provisioning rejetée : '{request.requested_username}' "
            f"par {checker.username} — motif : {reason[:100]}"
        ),
        ip_address=ip_address,
    )

    emit_notification(
        recipient=request.requested_by,
        notification_type=Notification.Type.PROVISIONING_REJECTED,
        title=f"Votre demande a été rejetée : {request.requested_username}",
        idempotency_key=f"PROVISIONING_REJECTED:{request.pk}",
        body=f"Motif : {reason}",
        url="/auth/admin/provisioning/",
    )

    return request


def cancel_provisioning_request(
    *,
    request: UserProvisioningRequest,
    maker: User,
    ip_address: str | None = None,
) -> UserProvisioningRequest:
    """
    Annule une demande PENDING par le maker lui-même (Story 6.2.0 / AC3).

    Seul l'auteur de la demande peut l'annuler et uniquement si elle est PENDING.
    """
    if request.requested_by_id != maker.pk:
        raise PermissionDenied(
            "Seul l'auteur de la demande peut l'annuler."
        )
    if request.status != UserProvisioningRequest.Status.PENDING:
        raise ValueError(
            "Seules les demandes PENDING peuvent être annulées."
        )

    request.status = UserProvisioningRequest.Status.CANCELLED
    request.save(update_fields=["status"])

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=maker,
        content_type="UserProvisioningRequest",
        object_id=request.pk,
        changes={"status": [UserProvisioningRequest.Status.PENDING, UserProvisioningRequest.Status.CANCELLED]},
        description=(
            f"Demande de provisioning annulée par le maker : "
            f"'{request.requested_username}' — {maker.username}"
        ),
        ip_address=ip_address,
    )

    return request

