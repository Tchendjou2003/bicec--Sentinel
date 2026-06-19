"""
Audit App — Selectors (HackSoft Styleguide)

Requêtes en lecture seule sur AuditLog, exposées aux vues.
"""
from datetime import datetime, time

from .models import AuditLog

# ---------------------------------------------------------------------------
# Constantes de mapping module
# ---------------------------------------------------------------------------

# content_types techniques → groupe métier (clé utilisée dans le filtre GET)
MODULE_CHOICES: dict[str, list[str]] = {
    "workflow": [
        "Recommendation", "EvidenceFile", "EvidenceSubmission",
        "Deliverable", "RecommendationSource", "ImportBatch",
    ],
    "utilisateurs": [
        "User", "UserProvisioningRequest", "ExternalMission",
        "AccessAttempt", "Session",
    ],
    "organisation": [
        "Department", "OrgUnitType",
    ],
}

# Libellés FR affichés dans le <select> et les cellules du tableau
MODULE_LABELS: dict[str, str] = {
    "workflow":     "Recommandations & preuves",
    "utilisateurs": "Utilisateurs & accès",
    "organisation": "Organisation",
}

# Mapping à plat content_type → libellé FR (précalculé une fois)
CONTENT_TYPE_LABEL: dict[str, str] = {
    ct: MODULE_LABELS[group]
    for group, cts in MODULE_CHOICES.items()
    for ct in cts
}


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------

def get_audit_logs(
    *,
    action: str | None = None,
    content_type: str | None = None,
    user_id: str | None = None,
    date_from=None,
    date_to=None,
):
    """
    Retourne un QuerySet AuditLog filtré selon les critères fournis.

    ``content_type`` attend la clé de groupe (ex. "workflow", "utilisateurs"),
    pas le nom de classe technique. ``date_from``/``date_to`` sont des objets
    ``datetime.date`` (pas des chaînes).
    """
    qs = AuditLog.objects.select_related("user").order_by("-created_at")

    if action:
        qs = qs.filter(action=action)

    if content_type:
        # Filtre sur tous les content_types du groupe métier
        cts = MODULE_CHOICES.get(content_type, [content_type])
        qs = qs.filter(content_type__in=cts)

    if user_id:
        try:
            qs = qs.filter(user_id=user_id)
        except (ValueError, TypeError):
            pass

    if date_from:
        # SARGable : datetime complet pour préserver l'index btree sur created_at
        qs = qs.filter(created_at__gte=datetime.combine(date_from, time.min))

    if date_to:
        qs = qs.filter(created_at__lte=datetime.combine(date_to, time.max))

    return qs
