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
from django.urls import reverse
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


@transaction.atomic
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

    # Verrou exclusif sur la ligne utilisateur : deux admins ne peuvent pas
    # se chevaucher sur le même compte (AuditLog corrompu, rôle final imprévisible).
    target_user = User.objects.select_for_update().get(pk=target_user.pk)

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
def delegate_audit_admin_timed(
    *,
    delegated_to: User,
    valid_until,
    performed_by: User,
    ip_address: str | None = None,
):
    """Creates a timed is_audit_admin delegation for an internal auditor (FR36).

    The delegatee gains can_manage_users until valid_until (inclusive).
    The permanent admin keeps is_audit_admin=True regardless.

    Args:
        delegated_to: The AUDIT user receiving the temporary flag.
        valid_until: Last day the delegation is valid (datetime.date).
        performed_by: The permanent audit admin granting the flag.

    Raises:
        PermissionDenied: performed_by is not the permanent admin or superuser.
        ValueError: Target is self, non-AUDIT, past date, or already has an active delegation.
    """
    from apps.audit.models import AuditLog
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification
    from .models import AuditAdminDelegation

    if not (performed_by.is_audit_admin or performed_by.is_superuser):
        # Garde volontairement plus strict que can_manage_users : un délégué
        # temporaire ne doit pas pouvoir créer de sous-délégation qu'il serait
        # ensuite incapable de révoquer lui-même (revoke_audit_admin_delegation
        # n'autorise que l'admin permanent), et sans borne liée à sa propre
        # échéance. Seul l'admin permanent délègue (FR36).
        raise PermissionDenied("Seul l'administrateur Audit permanent peut déléguer ce droit.")
    if delegated_to == performed_by:
        raise ValueError("Un administrateur ne peut pas se déléguer le flag à lui-même.")
    if delegated_to.role != User.Role.AUDIT:
        raise ValueError("La délégation ne peut cibler qu'un Auditeur Interne.")
    if valid_until <= timezone.now().date():
        raise ValueError("La date de fin doit être dans le futur.")
    if delegated_to.received_delegations.filter(
        revoked_at__isnull=True,
        valid_until__gte=timezone.now().date(),
    ).exists():
        raise ValueError("Cet auditeur possède déjà une délégation active.")

    delegation = AuditAdminDelegation.objects.create(
        delegated_to=delegated_to,
        delegated_by=performed_by,
        valid_until=valid_until,
    )

    target_name = delegated_to.get_full_name() or delegated_to.username
    AuditLog.objects.create(
        action=AuditLog.Action.PRIVILEGE_GRANT,
        user=performed_by,
        content_type="User",
        object_id=delegated_to.pk,
        ip_address=ip_address,
        changes={"valid_until": str(valid_until), "delegation_id": str(delegation.pk)},
        description=f"Délégation is_audit_admin accordée à {target_name} jusqu'au {valid_until}.",
    )

    ts_key = timezone.now().strftime("%Y-%m-%d")
    emit_notification(
        recipient=delegated_to,
        notification_type=Notification.Type.PRIVILEGE_ALERT,
        title="Délégation Administrateur Audit reçue",
        body=(
            f"Le flag Administrateur Audit vous a été délégué par "
            f"{performed_by.get_full_name() or performed_by.username} "
            f"jusqu'au {valid_until}."
        ),
        idempotency_key=f"PRIVILEGE_GRANT:{delegation.pk}:{ts_key}",
        is_urgent=False,
    )
    return delegation


@transaction.atomic
def revoke_audit_admin_delegation(
    *,
    delegation,
    revoked_by: User,
    ip_address: str | None = None,
):
    """Revokes an active timed delegation before its expiry date (FR36).

    Only the permanent audit admin (is_audit_admin=True) or a superuser
    can revoke. A delegated admin cannot revoke another delegated admin.

    Raises:
        PermissionDenied: revoked_by is not the permanent admin or superuser.
        ValueError: delegation is already revoked.
    """
    from apps.audit.models import AuditLog
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification

    if not (revoked_by.is_audit_admin or revoked_by.is_superuser):
        raise PermissionDenied(
            "Seul l'administrateur Audit principal peut révoquer une délégation."
        )
    if delegation.revoked_at is not None:
        raise ValueError("Cette délégation est déjà révoquée.")

    delegation.revoked_at = timezone.now()
    delegation.revoked_by = revoked_by
    delegation.save(update_fields=["revoked_at", "revoked_by"])

    target_name = delegation.delegated_to.get_full_name() or delegation.delegated_to.username
    AuditLog.objects.create(
        action=AuditLog.Action.PRIVILEGE_REVOKE,
        user=revoked_by,
        content_type="User",
        object_id=delegation.delegated_to_id,
        ip_address=ip_address,
        changes={"delegation_id": str(delegation.pk), "revoked_early": True},
        description=f"Délégation is_audit_admin révoquée pour {target_name} (révocation manuelle).",
    )

    ts_key = timezone.now().strftime("%Y-%m-%d")
    emit_notification(
        recipient=delegation.delegated_to,
        notification_type=Notification.Type.PRIVILEGE_ALERT,
        title="Délégation Administrateur Audit révoquée",
        body=(
            f"Votre délégation is_audit_admin a été révoquée par "
            f"{revoked_by.get_full_name() or revoked_by.username}."
        ),
        idempotency_key=f"PRIVILEGE_REVOKE:{delegation.pk}:{ts_key}",
        is_urgent=False,
    )
    return delegation


def run_nightly_delegation_expiry_check() -> dict:
    """Logs newly expired delegations and notifies former delegatees.

    Targets delegations whose valid_until == yesterday (newly expired today).
    At runtime can_manage_users already denies access for expired delegations,
    so this function only adds the AuditLog trace and sends the expiry notification.

    Returns:
        {"expired": int}
    """
    from datetime import timedelta
    from apps.audit.models import AuditLog
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification
    from .models import AuditAdminDelegation

    yesterday = timezone.now().date() - timedelta(days=1)
    expired_qs = AuditAdminDelegation.objects.filter(
        revoked_at__isnull=True,
        valid_until=yesterday,
    ).select_related("delegated_to")

    count = 0
    for delegation in expired_qs:
        target = delegation.delegated_to
        target_name = target.get_full_name() or target.username
        AuditLog.objects.create(
            action=AuditLog.Action.PRIVILEGE_REVOKE,
            user=None,
            content_type="User",
            object_id=target.pk,
            changes={"delegation_id": str(delegation.pk), "expired": True},
            description=(
                f"Délégation is_audit_admin expirée pour {target_name} "
                f"(valide jusqu'au {delegation.valid_until})."
            ),
        )
        ts_key = timezone.now().strftime("%Y-%m-%d")
        emit_notification(
            recipient=target,
            notification_type=Notification.Type.PRIVILEGE_ALERT,
            title="Délégation Administrateur Audit expirée",
            body=f"Votre délégation is_audit_admin a expiré le {delegation.valid_until}.",
            idempotency_key=f"PRIVILEGE_EXPIRED:{delegation.pk}:{ts_key}",
            is_urgent=False,
        )
        count += 1

    return {"expired": count}


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
    if department.is_system:
        raise ValueError(
            "L'entité système « Support Applicatif » ne peut pas être supprimée. "
            "Elle héberge les administrateurs Sentinel."
        )
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
    # On ne peut pas désactiver un type utilisé par l'entité système (sinon
    # l'entité « Support Applicatif » deviendrait orpheline).
    if old_value and instance.departments.filter(is_system=True).exists():
        raise ValueError(
            "Ce type est utilisé par l'entité système « Support Applicatif » "
            "et ne peut pas être désactivé."
        )
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


@transaction.atomic
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

    from .account_templates import resolve_system_department

    is_modify = cleaned_data.get("request_type") == UserProvisioningRequest.RequestType.MODIFY
    target_user = cleaned_data.get("target_user")

    # Garde : un admin ne peut pas soumettre une modification sur lui-même.
    if is_modify and target_user and target_user.pk == maker.pk:
        raise PermissionDenied(
            "Vous ne pouvez pas soumettre une demande de modification sur votre propre compte."
        )

    if is_modify:
        if target_user is None:
            raise ValidationError("target_user est requis pour une demande de modification.")
        hashed = ""
        username = target_user.username
        email = target_user.email
        first_name = target_user.first_name
        last_name = target_user.last_name
    else:
        plain_password = cleaned_data.get("password", "")
        hashed = make_password(plain_password)
        username = cleaned_data["requested_username"]
        email = cleaned_data["requested_email"]
        first_name = cleaned_data.get("requested_first_name", "")
        last_name = cleaned_data.get("requested_last_name", "")

    # Profil ADMIN : rattachement automatique à l'entité système (le formulaire
    # soumet un département vide, car l'entité système est exclue du sélecteur).
    requested_role = cleaned_data["requested_role"]
    requested_department = cleaned_data.get("requested_department")
    if requested_role == User.Role.ADMIN:
        system_dept = resolve_system_department()
        if system_dept is None:
            raise ValidationError(
                "L'entité système « Support Applicatif » est introuvable. "
                "Vérifiez que les migrations ont bien été appliquées."
            )
        requested_department = system_dept

    req = UserProvisioningRequest(
        requested_username=username,
        requested_first_name=first_name,
        requested_last_name=last_name,
        requested_email=email,
        hashed_initial_password=hashed,
        requested_role=requested_role,
        requested_department=requested_department,
        requested_is_audit_admin=cleaned_data.get("requested_is_audit_admin", False),
        requested_job_title=cleaned_data.get("requested_job_title", ""),
        requested_profile=cleaned_data.get("requested_profile", ""),
        status=UserProvisioningRequest.Status.PENDING,
        requested_by=maker,
        request_type=cleaned_data.get("request_type", UserProvisioningRequest.RequestType.CREATE),
        target_user=target_user,
    )
    # Pour les demandes MODIFY, username/email/mot de passe proviennent du
    # target_user existant et peuvent être vides ou inchangés — on les exclut
    # de full_clean() pour éviter les faux positifs de validation.
    exclude_fields = ["requested_email", "hashed_initial_password"] if is_modify else []
    req.full_clean(exclude=exclude_fields)
    req.save()

    action_label = "Demande de modification" if is_modify else "Demande de provisioning créée"
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=maker,
        content_type="UserProvisioningRequest",
        object_id=req.pk,
        changes={
            "requested_username": [None, req.requested_username],
            "requested_role": [None, req.requested_role],
            "request_type": [None, req.request_type],
        },
        description=(
            f"{action_label} : '{req.requested_username}' "
            f"({req.get_requested_role_display()}) par {maker.username}"
        ),
        ip_address=ip_address,
    )

    notify_group(
        group_name=settings.PROVISIONING_APPROVER_GROUP_NAME,
        notification_type=Notification.Type.PROVISIONING_REQUESTED,
        title=f"{'Modification' if is_modify else 'Nouvelle demande'} : {req.requested_username}",
        key_prefix=f"PROVISIONING_REQUESTED:{req.pk}",
        body=(
            f"Demandé par {maker.username} — "
            f"Rôle : {req.get_requested_role_display()}"
        ),
        url=reverse("auth:user-management"),
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
    + AuditLogs. Pour le rôle EXT, le compte est créé sans mission ;
    les missions sont gérées séparément par l'Audit Interne (Story 6.7).

    ⚠️ Piège double-hachage : on affecte ``user.password`` directement
    (valeur déjà hachée) plutôt que ``create_user(password=...)``
    qui re-hacherait et rendrait le login impossible.
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import emit_notification

    # Verrou anti-course : la vue charge l'instance sans lock — sans re-fetch
    # verrouillé, une décision concurrente (cancel/reject) passerait aussi la
    # garde d'état et serait écrasée par ce save().
    request = UserProvisioningRequest.objects.select_for_update().get(pk=request.pk)

    if request.status != UserProvisioningRequest.Status.PENDING:
        raise ValueError("Seules les demandes PENDING peuvent être approuvées.")

    # Séparation des fonctions (ADR-10) : un checker ne peut pas valider sa propre
    # demande. Exception bootstrap : levée si un seul admin actif existe (deadlock
    # impossible à éviter autrement — tracé explicitement dans l'AuditLog).
    if request.requested_by_id == checker.pk:
        solo_admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).count() == 1
        if not solo_admin:
            raise PermissionDenied(
                "Séparation des fonctions : vous ne pouvez pas approuver votre propre demande."
            )

    is_modify = request.request_type == UserProvisioningRequest.RequestType.MODIFY

    if is_modify:
        # ── Branche MODIFY : mise à jour du User existant ─────────────────────
        if request.target_user is None:
            raise ValidationError("La demande MODIFY n'a pas de target_user associé.")
        user = request.target_user

        old_role = user.role
        old_dept_id = str(user.department_id) if user.department_id else None
        old_audit_admin = user.is_audit_admin
        old_job_title = user.job_title

        user.role = request.requested_role
        user.department = request.requested_department
        user.is_audit_admin = request.requested_is_audit_admin
        user.job_title = request.requested_job_title
        user.save(update_fields=["role", "department", "is_audit_admin", "job_title"])

        AuditLog.objects.create(
            action=AuditLog.Action.UPDATE,
            user=checker,
            content_type="User",
            object_id=user.pk,
            changes={
                "role": [old_role, user.role],
                "department": [old_dept_id, str(user.department_id) if user.department_id else None],
                "is_audit_admin": [old_audit_admin, user.is_audit_admin],
                "job_title": [old_job_title, user.job_title],
            },
            description=(
                f"Profil modifié par approbation provisioning : '{user.username}' "
                f"— approuvé par {checker.username}"
            ),
            ip_address=ip_address,
        )
    else:
        # ── Branche CREATE : création d'un nouveau User ───────────────────────
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

        user = User(
            username=request.requested_username,
            email=request.requested_email,
            first_name=request.requested_first_name,
            last_name=request.requested_last_name,
            role=request.requested_role,
            department=request.requested_department,
            is_external=is_ext,
            is_audit_admin=request.requested_is_audit_admin,
            job_title=request.requested_job_title,
        )
        user.password = request.hashed_initial_password
        user.save()

        AuditLog.objects.create(
            action=AuditLog.Action.CREATE,
            user=checker,
            content_type="User",
            object_id=user.pk,
            changes={
                "username": [None, user.username],
                "role": [None, user.role],
                "department": [None, str(user.department_id) if user.department_id else None],
                "is_audit_admin": [None, user.is_audit_admin],
                "job_title": [None, user.job_title],
                "profile_template": [None, request.requested_profile or None],
            },
            description=(
                f"Compte créé par approbation provisioning : '{user.username}' "
                f"({user.get_role_display()}"
                f"{' — Admin Audit' if user.is_audit_admin else ''}) "
                f"— profil '{request.requested_profile or 'manuel'}', "
                f"approuvé par {checker.username}"
                f"{' [BOOTSTRAP — auto-approbation admin unique]' if request.requested_by_id == checker.pk else ''}"
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
        url=reverse("auth:user-management"),
    )

    return user


@transaction.atomic
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

    # Verrou anti-course (cf. approve_provisioning_request)
    request = UserProvisioningRequest.objects.select_for_update().get(pk=request.pk)

    if request.status != UserProvisioningRequest.Status.PENDING:
        raise ValueError("Seules les demandes PENDING peuvent être rejetées.")

    # Séparation des fonctions (ADR-10) : pas d'auto-rejet de sa propre demande
    # (cohérent avec l'approbation ; l'auteur dispose de l'annulation à la place).
    if request.requested_by_id == checker.pk:
        raise PermissionDenied(
            "Séparation des fonctions : vous ne pouvez pas rejeter votre propre demande."
        )

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
        url=reverse("auth:user-management"),
    )

    return request


@transaction.atomic
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
    # Verrou anti-course (cf. approve_provisioning_request)
    request = UserProvisioningRequest.objects.select_for_update().get(pk=request.pk)

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


# ── Actions rapides Admin IT (Story 8.x) ─────────────────────────────────────

@transaction.atomic
def reset_user_password(
    *,
    target_user: User,
    new_password: str,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """Réinitialise le mot de passe d'un utilisateur par un Admin IT."""
    from django.contrib.auth.password_validation import validate_password

    if not new_password:
        raise ValidationError("Le nouveau mot de passe ne peut pas être vide.")
    validate_password(new_password, target_user)

    target_user.set_password(new_password)
    target_user.save(update_fields=["password"])

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="User",
        object_id=target_user.pk,
        changes={"password": ["***", "***"]},
        description=(
            f"[PASSWORD_RESET] Mot de passe réinitialisé pour '{target_user.username}' "
            f"par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return target_user


@transaction.atomic
def deactivate_user(
    *,
    target_user: User,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """Désactive un compte et invalide toutes ses sessions actives."""
    if target_user.pk == performed_by.pk:
        raise PermissionDenied("Vous ne pouvez pas désactiver votre propre compte.")
    if target_user.is_superuser:
        raise PermissionDenied("Les superusers ne peuvent pas être désactivés via cette interface.")

    target_user.is_active = False
    target_user.save(update_fields=["is_active"])

    from .selectors import get_sessions_for_user
    from django.contrib.sessions.models import Session
    session_keys = get_sessions_for_user(target_user)
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="User",
        object_id=target_user.pk,
        changes={"is_active": [True, False]},
        description=(
            f"Compte désactivé : '{target_user.username}' "
            f"par {performed_by.username} "
            f"({len(session_keys)} session(s) invalidée(s))"
        ),
        ip_address=ip_address,
    )
    return target_user


@transaction.atomic
def reactivate_user(
    *,
    target_user: User,
    performed_by: User,
    ip_address: str | None = None,
) -> User:
    """Réactive un compte désactivé."""
    target_user.is_active = True
    target_user.save(update_fields=["is_active"])

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="User",
        object_id=target_user.pk,
        changes={"is_active": [False, True]},
        description=(
            f"Compte réactivé : '{target_user.username}' "
            f"par {performed_by.username}"
        ),
        ip_address=ip_address,
    )
    return target_user


@transaction.atomic
def change_own_password(
    *,
    user: User,
    old_password: str,
    new_password: str,
    request=None,
    ip_address: str | None = None,
) -> User:
    """Auto-service : l'utilisateur change son propre mot de passe."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password

    if not user.check_password(old_password):
        raise ValidationError({"old_password": "Mot de passe actuel incorrect."})
    if not new_password:
        raise ValidationError({"new_password": "Le nouveau mot de passe ne peut pas être vide."})
    try:
        validate_password(new_password, user)
    except ValidationError as e:
        raise ValidationError({"new_password": e.messages})

    user.set_password(new_password)
    user.save(update_fields=["password"])

    if request is not None:
        update_session_auth_hash(request, user)

    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=user,
        content_type="User",
        object_id=user.pk,
        changes={"password": ["***", "***"]},
        description=f"[PASSWORD_CHANGE] Auto-service : '{user.username}' a changé son mot de passe",
        ip_address=ip_address,
    )
    return user


# ── Bootstrap gouverné du premier administrateur (Story 7.2) ─────────────────

@transaction.atomic
def bootstrap_create_admin(
    *,
    username: str,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    performed_by: User | None = None,
    ip_address: str | None = None,
) -> User:
    """
    Crée un administrateur Sentinel en mode bootstrap (Story 7.2).

    Dérogation contrôlée au flux Maker/Checker, réservée à l'amorçage : permet
    de créer les 1er et 2e administrateurs sans Django Admin, via la commande
    `bootstrap_admin`. Au-delà de 2 administrateurs actifs, la fonction refuse
    (le bootstrap est terminé ; les comptes suivants passent par Maker/Checker).

    Gouvernance :
        - 1er admin (count == 0) → ajouté au groupe « Administrateurs Sentinel »
          (= Checker / tête de l'entité système).
        - 2e admin → Maker (hors groupe).
        - Rattachement automatique à l'entité système « Support Applicatif ».
        - Mot de passe en clair → create_user() le hache normalement (pas de
          double-hachage ici, contrairement à approve_provisioning_request).
    """
    from django.contrib.auth.models import Group
    from .account_templates import resolve_system_department

    # select_for_update() pose un verrou exclusif sur les lignes admin existantes
    # avant de compter, empêchant deux appels concurrents de passer tous les deux
    # le guard >= 2 et de créer un 3e admin.
    existing_admins = list(
        User.objects.filter(role=User.Role.ADMIN, is_active=True).select_for_update()
    )
    admin_count = len(existing_admins)
    if admin_count >= 2:
        raise PermissionDenied(
            "Le mode bootstrap est désactivé : au moins 2 administrateurs actifs "
            "existent déjà. Utilisez le flux Maker/Checker pour les comptes suivants."
        )

    system_dept = resolve_system_department()
    if system_dept is None:
        raise ValidationError(
            "L'entité système « Support Applicatif » est introuvable. "
            "Vérifiez que les migrations ont bien été appliquées."
        )

    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError(f"Le nom d'utilisateur '{username}' est déjà pris.")
    if email and User.objects.filter(email__iexact=email).exists():
        raise ValidationError(f"L'e-mail '{email}' est déjà utilisé.")

    is_checker = admin_count == 0

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.ADMIN,
        department=system_dept,
        job_title="Administrateur Sentinel",
        is_staff=False,
    )

    # Seul le 1er admin devient Checker (membre du groupe approbateur).
    if is_checker:
        group, _ = Group.objects.get_or_create(
            name=settings.PROVISIONING_APPROVER_GROUP_NAME
        )
        user.groups.add(group)

    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=performed_by,
        content_type="User",
        object_id=user.pk,
        changes={
            "username": [None, user.username],
            "role": [None, User.Role.ADMIN],
            "bootstrap": [None, True],
            "is_checker": [None, is_checker],
        },
        description=(
            f"[BOOTSTRAP] Administrateur Sentinel créé : '{user.username}' "
            f"({'Checker' if is_checker else 'Maker'}) — entité « {system_dept.name} »"
            + (f" par {performed_by.username}" if performed_by else " (CLI)")
        ),
        ip_address=ip_address,
    )

    return user


# ── Monitoring & Surveillance (Story 7.1) ─────────────────────────────────────

@transaction.atomic
def unlock_account(
    *,
    access_attempt_pk: int,
    performed_by: User,
    ip_address: str | None = None,
) -> None:
    """Supprime un lockout axes et trace l'action dans l'AuditLog (atomique : pas de déblocage sans trace)."""
    from axes.models import AccessAttempt
    from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
    attempt = AccessAttempt.objects.get(pk=access_attempt_pk)
    username = attempt.username
    # Interdire le déblocage d'un compte superutilisateur (IDOR — séparation des droits ADR-10).
    target = User.objects.filter(username=username).first()
    if target and target.is_superuser:
        raise DjangoPermissionDenied(
            "Le déblocage d'un compte superutilisateur est interdit via cette interface."
        )
    attempt.delete()
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="AccessAttempt",
        description=f"Compte débloqué : '{username}' par {performed_by.username}",
        changes={"action": [None, "unlock"], "username": [None, username]},
        ip_address=ip_address,
    )


@transaction.atomic
def force_logout_session(
    *,
    session_key: str,
    target_username: str,
    performed_by: User,
    ip_address: str | None = None,
) -> None:
    """Invalide une session Django et trace l'action dans l'AuditLog (atomique : pas d'invalidation sans trace)."""
    from django.contrib.sessions.models import Session
    Session.objects.filter(session_key=session_key).delete()
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        user=performed_by,
        content_type="Session",
        description=(
            f"Session invalidée pour '{target_username}' "
            f"par {performed_by.username}"
        ),
        changes={"action": [None, "force_logout"], "target_user": [None, target_username]},
        ip_address=ip_address,
    )
