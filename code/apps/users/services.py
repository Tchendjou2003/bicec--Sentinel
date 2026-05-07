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

from apps.audit.models import AuditLog
from apps.users.models import Department, User


def assign_role(
    *,
    target_user: User,
    role: str,
    department: Department | None,
    performed_by: User,
) -> User:
    """
    Attribue un rôle métier et un département à un utilisateur.

    Args:
        target_user: Le compte à habiliter.
        role: Le rôle métier (User.Role).
        department: Le département de rattachement (peut être None pour AUDIT/RSSI).
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
    )
    return target_user


def toggle_audit_admin(
    *,
    target_user: User,
    grant: bool,
    performed_by: User,
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
    )
    return target_user
