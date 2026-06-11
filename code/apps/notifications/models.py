"""
Notifications App — Modèle Notification (Story 4.0)

Socle channel-agnostic des notifications in-app. Toute notification est
idempotente via la paire ``(recipient, idempotency_key)`` (contrainte unique
composite). Le futur canal e-mail (post-MVP) consommera les mêmes instances
sans refonte du modèle.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """
    Notification in-app pour un utilisateur Sentinel.

    Idempotente via la paire ``(recipient, idempotency_key)`` : deux appels
    ``emit_notification()`` avec la même clé pour le même destinataire ne
    créent qu'une seule entrée (AC4). La clé seule n'est plus unique : un
    nouveau porteur (délégation) reçoit sa propre notification.

    Champ ``is_urgent`` : True pour les ruptures (OVERDUE, jalons, escalade)
    → affichage visuellement distinct dans le dropdown (AC2).
    """

    class Type(models.TextChoices):
        # ── Événements workflow ────────────────────────────────────────────
        ASSIGNED             = "ASSIGNED",             _("Recommandation assignée")
        DELEGATED            = "DELEGATED",            _("Délégation ETP")
        EVIDENCE_REJECTED    = "EVIDENCE_REJECTED",    _("Preuves rejetées")
        EVIDENCE_VALIDATED   = "EVIDENCE_VALIDATED",   _("Preuves validées")
        CLOSED               = "CLOSED",               _("Recommandation clôturée")
        EXTENSION_REQUESTED  = "EXTENSION_REQUESTED",  _("Demande de report soumise")
        EXTENSION_APPROVED   = "EXTENSION_APPROVED",   _("Report d'échéance approuvé")
        EXTENSION_REJECTED   = "EXTENSION_REJECTED",   _("Report d'échéance rejeté")
        # ── Soumission de preuves ─────────────────────────────────────────
        EVIDENCE_SUBMITTED   = "EVIDENCE_SUBMITTED",   _("Preuves soumises — revue requise")
        # ── Ruptures / Urgences (is_urgent=True) ──────────────────────────
        OVERDUE                = "OVERDUE",              _("Passage en retard")
        OVERDUE_J30            = "OVERDUE_J30",          _("Retard ≥ 30 jours")
        OVERDUE_J60_ESCALATION = "OVERDUE_J60_ESCALATION", _("Escalade retard 60 jours")
        # ── Anticipations ─────────────────────────────────────────────────
        DUE_SOON_J7          = "DUE_SOON_J7",          _("Échéance dans 7 jours")
        DUE_SOON_J3          = "DUE_SOON_J3",          _("Échéance dans 3 jours")

    URGENT_TYPES = frozenset({"OVERDUE", "OVERDUE_J30", "OVERDUE_J60_ESCALATION"})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
        verbose_name=_("Destinataire"),
    )
    notification_type = models.CharField(
        _("Type"), max_length=30, choices=Type.choices,
    )
    recommendation = models.ForeignKey(
        "workflow.Recommendation",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="notifications",
        verbose_name=_("Recommandation"),
    )
    title = models.CharField(
        _("Titre"), max_length=200,
        help_text=_("Texte court affiché dans le dropdown."),
    )
    body = models.TextField(
        _("Détail"), blank=True, default="",
        help_text=_("Précision facultative (ex. motif de rejet)."),
    )
    url = models.CharField(
        _("Lien"), max_length=500, blank=True, default="",
        help_text=_("URL relative vers laquelle redirige le clic."),
    )
    is_urgent = models.BooleanField(
        _("Urgent"), default=False,
        help_text=_("True pour ruptures / escalades (affichage prioritaire)."),
    )
    is_read = models.BooleanField(_("Lu"), default=False, db_index=True)
    idempotency_key = models.CharField(
        _("Clé d'idempotence"), max_length=255,
        help_text=_(
            "Format : '{TYPE}:{recommendation_pk}[:{extra}]'. "
            "Unique PAR DESTINATAIRE (contrainte composite) : après une "
            "délégation, le nouveau porteur reçoit sa propre notification "
            "pour le même événement — l'ancienne ne la bloque plus."
        ),
    )
    created_at = models.DateTimeField(_("Créée le"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "idempotency_key"],
                name="uniq_notif_recipient_idem_key",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="idx_notif_recipient_read"),
            models.Index(fields=["recipient", "-created_at"], name="idx_notif_recipient_date"),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.recipient}"
