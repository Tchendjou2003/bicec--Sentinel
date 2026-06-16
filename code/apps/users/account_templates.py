"""
Users App — Account Templates (Story 7.2)

Profils de création de comptes prédéfinis pour le formulaire de provisioning
Maker/Checker. Chaque profil est un raccourci métier qui pré-remplit les champs
techniques (rôle, flags, fonction, département automatique).

⚠️ DISTINCTION CRITIQUE :
    Profil de création  ≠  Rôle workflow  ≠  Permission
    - Le profil est un confort UX côté formulaire (l'Admin IT pense « métier »).
    - Le rôle workflow (User.Role) reste la source de vérité du RBAC.
    - Les permissions/capacités passent par les groupes Django.

Le catalogue est de la DONNÉE (pas un modèle BDD) : extensible sans migration,
sans éditeur d'administration (YAGNI). Pour ajouter un profil, éditer la liste.

Doctrine (Story 7.2) :
    - L'Audit reste exclusivement auditeur : le « Directeur de l'Audit » est
      AUDIT + is_audit_admin (jamais DM, jamais audité).
    - ADMIN est un rôle purement système, rattaché à l'entité « Support
      Applicatif » (Department.is_system=True).
"""
from .models import Department, User

# Sentinelle pour auto_department : rattachement automatique à l'entité système.
SYSTEM_DEPARTMENT = "SYSTEM"


ACCOUNT_TEMPLATES = [
    {
        "key": "ADMIN_SENTINEL",
        "label": "Administrateur Sentinel",
        "category": "Administration",
        "icon": "⚙️",
        "description": "Gestion de l'application, de l'organigramme et support technique.",
        "role": User.Role.ADMIN,
        "is_audit_admin": False,
        "is_external": False,
        "auto_department": SYSTEM_DEPARTMENT,
        "suggested_job_title": "Administrateur Sentinel",
    },
    {
        "key": "DIRECTEUR_AUDIT",
        "label": "Directeur de l'Audit",
        "category": "Audit",
        "icon": "👑",
        "description": "Supervise le processus d'audit et gère les habilitations des auditeurs.",
        "role": User.Role.AUDIT,
        "is_audit_admin": True,
        "is_external": False,
        "auto_department": None,
        "suggested_job_title": "Directeur de l'Audit Interne",
    },
    {
        "key": "AUDITEUR_INTERNE",
        "label": "Auditeur Interne",
        "category": "Audit",
        "icon": "🔍",
        "description": "Création et suivi des recommandations d'audit.",
        "role": User.Role.AUDIT,
        "is_audit_admin": False,
        "is_external": False,
        "auto_department": None,
        "suggested_job_title": "",
    },
    {
        "key": "AUDITEUR_EXTERNE",
        "label": "Auditeur Externe",
        "category": "Audit",
        "icon": "🌍",
        "description": "Accès limité à une mission spécifique (COBAC, BEAC, CAC).",
        "role": User.Role.EXT,
        "is_audit_admin": False,
        "is_external": True,
        "auto_department": None,
        "suggested_job_title": "",
    },
    {
        "key": "DIRECTEUR_METIER",
        "label": "Directeur Métier",
        "category": "Métier (audités)",
        "icon": "📊",
        "description": "Reçoit les recommandations et les délègue aux employés traitants.",
        "role": User.Role.DM,
        "is_audit_admin": False,
        "is_external": False,
        "auto_department": None,
        "suggested_job_title": "",
    },
    {
        "key": "EMPLOYE_TRAITANT",
        "label": "Employé Traitant",
        "category": "Métier (audités)",
        "icon": "👤",
        "description": "Exécute les actions correctives et soumet les preuves.",
        "role": User.Role.ETP,
        "is_audit_admin": False,
        "is_external": False,
        "auto_department": None,
        "suggested_job_title": "",
    },
    {
        "key": "DIRECTION_GENERALE",
        "label": "Direction Générale",
        "category": "Gouvernance",
        "icon": "🏛️",
        "description": "Vision globale et supervision du processus d'audit.",
        "role": User.Role.DG,
        "is_audit_admin": False,
        "is_external": False,
        "auto_department": None,
        "suggested_job_title": "",
    },
]

# Ordre d'affichage des catégories dans le sélecteur.
TEMPLATE_CATEGORIES = ["Administration", "Audit", "Métier (audités)", "Gouvernance"]


def get_template(key: str) -> dict | None:
    """Retourne un profil par sa clé, ou None."""
    return next((t for t in ACCOUNT_TEMPLATES if t["key"] == key), None)


def get_templates_grouped() -> list[dict]:
    """
    Retourne les profils groupés par catégorie pour le sélecteur UI.

    Format : [{"category": str, "templates": [dict, ...]}, ...] dans l'ordre
    de TEMPLATE_CATEGORIES.
    """
    grouped = []
    for category in TEMPLATE_CATEGORIES:
        templates = [t for t in ACCOUNT_TEMPLATES if t["category"] == category]
        if templates:
            grouped.append({"category": category, "templates": templates})
    return grouped


def resolve_system_department() -> "Department | None":
    """
    Retourne le Department système (is_system=True), ou None s'il est absent.

    Seedé par la migration 0011. Sert au rattachement automatique du profil
    « Administrateur Sentinel » et au bootstrap.
    """
    return Department.objects.filter(is_system=True, is_active=True).first()
