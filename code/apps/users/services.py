"""
Users App — Services (Convention HackSoft)

Logique d'écriture pour l'habilitation des comptes.
Chaque mutation est tracée dans l'Audit Log (NFR-SEC-05).

Spécifications couvertes :
    - FR3  : Attribution des rôles métiers
    - FR36 : Délégation is_audit_admin
    - ADR-10 : Séparation des fonctions
"""
from django.core.exceptions import PermissionDenied

from ..audit.models import AuditLog
from .models import Department, OrgUnitType, User
from django.db import transaction


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
    if not (performed_by.can_manage_users or performed_by.is_superuser):
        raise PermissionDenied(
            "Seul un auditeur avec is_audit_admin peut attribuer des rôles."
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

