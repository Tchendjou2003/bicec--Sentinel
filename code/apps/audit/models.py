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
from django.utils import timezone
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
        # Story 3.6 — Demandes de report d'échéance (FR13, FR14, FR34)
        EXTENSION_REQUESTED = "EXTENSION_REQUESTED", _("Demande de report soumise")
        EXTENSION_APPROVED  = "EXTENSION_APPROVED",  _("Demande de report approuvée")
        EXTENSION_REJECTED  = "EXTENSION_REJECTED",  _("Demande de report rejetée")

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


class HmacSeal(models.Model):
    """
    Sceau cryptographique HMAC-SHA256 d'une recommandation clôturée (FR24 / NFR-SEC-03).

    Généré comme effet de bord de la transaction de clôture (Story 3.10, ADR-07) :
    une empreinte inaltérable du dossier (métadonnées figées + hashs SHA-256 des
    preuves acceptées) calculée avec ``HMAC_SECRET_KEY`` (distincte de ``SECRET_KEY``).

    Relation 1:1 avec ``Recommendation``. Toute altération post-clôture d'un champ
    scellé rompt le hash et est détectable via ``verify_recommendation_seal()``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recommendation = models.OneToOneField(
        "workflow.Recommendation",
        on_delete=models.PROTECT,
        related_name="hmac_seal",
        verbose_name=_("Recommandation"),
    )
    hmac_hash = models.CharField(
        _("Empreinte HMAC-SHA256"),
        max_length=64,
        help_text=_("Digest hexadécimal HMAC-SHA256 du dossier scellé."),
    )
    sealed_metadata = models.JSONField(
        _("Métadonnées scellées"),
        help_text=_("Snapshot figé des champs métier entrant dans le calcul HMAC."),
    )
    file_hashes = models.JSONField(
        _("Hashs des preuves"),
        default=dict,
        help_text=_("{evidence_file_id: sha256_hash} des preuves acceptées."),
    )
    sealed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sealed_recommendations",
        verbose_name=_("Scellé par"),
        help_text=_("Auditeur ayant clôturé et scellé le dossier."),
    )
    sealed_at = models.DateTimeField(_("Scellé le"), default=timezone.now)
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)

    class Meta:
        db_table = "audit_hmac_seal"
        verbose_name = _("Sceau HMAC")
        verbose_name_plural = _("Sceaux HMAC")
        ordering = ["-sealed_at"]

    def __str__(self):
        return f"Sceau {self.hmac_hash[:12]}… (reco {self.recommendation_id})"
