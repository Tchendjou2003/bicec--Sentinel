"""
Audit App — Models (HackSoft Convention)
Stub pour Story 1.1 — sera implémenté complètement dans Epic 5

Le modèle AuditLog est volontairement simplifié pour le MVP.
L'intégration avec GenericForeignKey et ContentType sera faite
lors de l'Epic 5 (Confiance Réglementaire & Audit Trail).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """
    Journal d'audit append-only (NFR-SEC-05).

    Trace toutes les actions utilisateur et système pendant 12 mois.
    Chaque entrée est un enregistrement immuable.

    Ref. Architecture : §7.2 ERD — table ``audit_auditlog``
    """

    class Action(models.TextChoices):
        CREATE = "CREATE", _("Création")
        UPDATE = "UPDATE", _("Modification")
        DELETE = "DELETE", _("Suppression (soft)")
        LOGIN = "LOGIN", _("Connexion réussie")
        LOGIN_FAILED = "LOGIN_FAILED", _("Tentative de connexion échouée")
        LOGOUT = "LOGOUT", _("Déconnexion")
        TRANSITION = "TRANSITION", _("Transition FSM")
        SYSTEM = "SYSTEM", _("Action système")
        EXPORT = "EXPORT", _("Export")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    action = models.CharField(
        _("Action"),
        max_length=20,
        choices=Action.choices,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Utilisateur"),
    )
    content_type = models.CharField(
        _("Type d'entité"),
        max_length=50,
        blank=True,
    )
    object_id = models.UUIDField(
        _("ID de l'objet"),
        null=True,
        blank=True,
    )
    changes = models.JSONField(
        _("Changements"),
        null=True,
        blank=True,
        help_text=_("Format : {champ: [avant, après]}"),
    )
    ip_address = models.GenericIPAddressField(
        _("Adresse IP"),
        null=True,
        blank=True,
    )
    description = models.TextField(
        _("Description"),
        blank=True,
    )
    created_at = models.DateTimeField(
        _("Horodatage"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("Journal d'audit")
        verbose_name_plural = _("Journal d'audit")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} — {self.content_type} ({self.object_id}) par {self.user}"
