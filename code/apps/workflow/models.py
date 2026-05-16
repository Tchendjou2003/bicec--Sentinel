"""
Workflow App — Models (Convention HackSoft)

Modèles de données pour le cycle de vie des recommandations d'audit
et le suivi d'avancement via livrables.

Spécifications couvertes :
    - FR5  : Création manuelle unitaire
    - FR6  : Soft Delete en état DRAFT
    - FR6b : État DRAFT pré-assignation
    - FR9  : Conservation de la date de création originale
    - ADR-07 : django-fsm pour les transitions d'état

Architecture : HackSoft Styleguide — couche Model uniquement.
Les requêtes complexes sont dans selectors.py, la logique d'écriture dans services.py.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_fsm import FSMField, transition


# =============================================================================
# Managers
# =============================================================================


class ActiveRecommendationManager(models.Manager):
    """
    Manager par défaut : exclut les recommandations supprimées logiquement.

    Les recommandations marquées ``is_deleted=True`` sont invisibles
    pour toutes les requêtes passant par ``Recommendation.objects``.
    Pour accéder à l'intégralité des données (y compris les supprimées),
    utiliser ``Recommendation.all_objects``.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# =============================================================================
# Recommandation
# =============================================================================


class Recommendation(models.Model):
    """
    Recommandation d'audit issue d'une mission de contrôle.

    Représente les 10 colonnes métier du formalisme des recommandations BICEC :
    Référence, Date Mission, Direction contrôlée, Libellé mission,
    Observations, Dossiers en anomalies, Criticité, Livrables (via Deliverable),
    Direction concernée, Date de mise en œuvre.

    Le cycle de vie est piloté par django-fsm (ADR-07).
    Le soft delete est réservé aux brouillons (FR6).

    Ref. Architecture : §5.1 FSM, §7.2 ERD — table ``workflow_recommendation``
    """

    # ── Enums ─────────────────────────────────────────────────────────

    class Source(models.TextChoices):
        INTERNE = "INTERNE", _("Audit Interne")
        COBAC = "COBAC", _("COBAC")
        CAC = "CAC", _("CAC")
        ANIF = "ANIF", _("ANIF")
        BEAC = "BEAC", _("BEAC")
        ANTIC = "ANTIC", _("ANTIC")
        CONSULTANT = "CONSULTANT", _("Consultant")

    class Priority(models.TextChoices):
        CRITIQUE = "CRITIQUE", _("Critique")
        HAUTE = "HAUTE", _("Haute")
        MOYENNE = "MOYENNE", _("Moyenne")
        FAIBLE = "FAIBLE", _("Faible")

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Brouillon")
        ASSIGNED = "ASSIGNED", _("Assignée")
        IN_PROGRESS = "IN_PROGRESS", _("En cours")
        PENDING_DM_REVIEW = "PENDING_DM_REVIEW", _("Validation DM")
        PENDING_AUDIT_REVIEW = "PENDING_AUDIT_REVIEW", _("Validation Audit")
        CLOSED_RESOLVED = "CLOSED_RESOLVED", _("Clôturée")

    # ── Champs métier (10 colonnes réelles) ───────────────────────────

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    reference = models.CharField(
        _("Référence"),
        max_length=50,
        unique=True,
        help_text=_(
            "Identifiant métier de la recommandation (ex: REC-2026-042). "
            "Saisie manuelle par l'auditeur."
        ),
    )
    mission_date = models.DateField(
        _("Date de la mission"),
        null=True,
        blank=True,
        help_text=_("Date à laquelle la mission d'audit a eu lieu."),
    )
    mission_label = models.CharField(
        _("Libellé de la mission"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Nom complet de la mission d'audit (ex: Contrôle KYC Q3 2025)."),
    )
    controlled_department = models.ForeignKey(
        "users.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="controlled_recommendations",
        verbose_name=_("Direction contrôlée"),
        help_text=_(
            "La direction qui a été auditée lors de la mission. "
            "Peut différer de la direction concernée par la recommandation."
        ),
    )
    observations = models.TextField(
        _("Observations"),
        blank=True,
        default="",
        help_text=_("Constats et observations issus de la mission d'audit."),
    )
    anomalous_dossiers = models.TextField(
        _("Dossiers en anomalies"),
        blank=True,
        default="",
        help_text=_("Description des dossiers présentant des anomalies."),
    )
    description = models.TextField(
        _("Texte de la recommandation"),
        help_text=_(
            "Le texte prescriptif de la recommandation. "
            "Décrit ce qui doit être corrigé ou amélioré."
        ),
    )
    source = models.CharField(
        _("Source"),
        max_length=20,
        choices=Source.choices,
        help_text=_("Origine réglementaire de la recommandation."),
    )
    priority = models.CharField(
        _("Criticité"),
        max_length=10,
        choices=Priority.choices,
        help_text=_("Conditionne la couleur UI et la fréquence des relances."),
    )
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recommendations",
        verbose_name=_("Direction concernée"),
        help_text=_(
            "Direction organisationnelle qui doit implémenter la recommandation."
        ),
    )
    due_date = models.DateField(
        _("Date de mise en œuvre"),
        help_text=_("Date limite pour la résolution de la recommandation."),
    )

    # ── Champs techniques internes ────────────────────────────────────

    original_due_date = models.DateField(
        _("Date d'échéance originale"),
        help_text=_(
            "Préservée intacte même après un report approuvé. "
            "Base du calcul de vieillissement (aging) pour les rapports COBAC."
        ),
    )
    status = FSMField(
        _("Statut FSM"),
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        protected=True,
        help_text=_("Piloté par django-fsm. Ne pas modifier directement."),
    )
    is_overdue = models.BooleanField(
        _("En retard"),
        default=False,
        help_text=_("Flag calculé par le scheduler nocturne Django-Q2."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_recommendations",
        verbose_name=_("Créé par"),
        help_text=_("Auditeur ayant créé la recommandation."),
    )
    assigned_dm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_recommendations",
        verbose_name=_("DM assigné"),
        help_text=_("Directeur Métier responsable. Renseigné en Story 2.5."),
    )
    assigned_etp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegated_recommendations",
        verbose_name=_("ETP délégué"),
        help_text=_("Employé Traitant exécutant. Renseigné en Story 3.2."),
    )
    import_tag = models.CharField(
        _("Tag d'import"),
        max_length=10,
        null=True,
        blank=True,
        help_text=_("Valeur 'IMPORTED' inaltérable si import historique (FR9)."),
    )

    # ── Soft Delete ───────────────────────────────────────────────────

    is_deleted = models.BooleanField(
        _("Supprimé (soft)"),
        default=False,
        help_text=_("Soft delete — FR6. Possible uniquement en état DRAFT."),
    )
    deleted_at = models.DateTimeField(
        _("Date de suppression"),
        null=True,
        blank=True,
        help_text=_("Horodatage du soft delete."),
    )

    # ── Timestamps ────────────────────────────────────────────────────

    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)

    # ── Managers ──────────────────────────────────────────────────────

    objects = ActiveRecommendationManager()  # défaut : exclut is_deleted
    all_objects = models.Manager()  # admin : tout inclus

    # ── Meta ──────────────────────────────────────────────────────────

    class Meta:
        verbose_name = _("Recommandation")
        verbose_name_plural = _("Recommandations")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_reco_status"),
            models.Index(fields=["created_by"], name="idx_reco_created_by"),
            models.Index(fields=["assigned_dm"], name="idx_reco_assigned_dm"),
            models.Index(fields=["department"], name="idx_reco_department"),
            models.Index(fields=["is_overdue"], name="idx_reco_overdue"),
            models.Index(fields=["priority"], name="idx_reco_priority"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.get_priority_display()}"

    # ── Validation ────────────────────────────────────────────────────

    def clean(self):
        """
        Validation métier :
        - La date de mise en œuvre ne peut pas être dans le passé
          (sauf pour les imports historiques).
        """
        super().clean()
        if self.due_date and not self.import_tag:
            if self.due_date < timezone.now().date():
                raise ValidationError(
                    {"due_date": _("La date de mise en œuvre ne peut pas être dans le passé.")}
                )

    # ── Propriétés calculées ──────────────────────────────────────────

    @property
    def progress_percentage(self) -> int:
        """
        Taux d'avancement basé sur les livrables complétés.

        Returns:
            int: Pourcentage (0-100). 0 si aucun livrable défini.
        """
        total = self.deliverables.count()
        if total == 0:
            return 0
        completed = self.deliverables.filter(is_completed=True).count()
        return round((completed / total) * 100)

    # ── Transitions FSM ──────────────────────────────────────────────

    @transition(field=status, source=Status.DRAFT, target=Status.ASSIGNED)
    def assign_to_dm(self, dm):
        """
        Assigne la recommandation à un Directeur Métier (FR11).

        Cette transition est protégée par django-fsm :
        elle ne peut être appelée que depuis l'état DRAFT.

        Args:
            dm: Instance User avec role=DM.

        Raises:
            ValidationError: Si le DM est invalide ou incompatible.
        """
        from apps.users.models import User

        if not dm or dm.role != User.Role.DM:
            raise ValidationError(
                _("L'utilisateur sélectionné n'a pas le rôle Directeur Métier.")
            )
        if not self.department:
            raise ValidationError(
                _("La Direction concernée doit être renseignée avant l'assignation.")
            )
        if dm.department_id != self.department_id:
            raise ValidationError(
                _("Le DM sélectionné n'appartient pas à la Direction concernée.")
            )
        self.assigned_dm = dm


# =============================================================================
# Livrable attendu
# =============================================================================


class Deliverable(models.Model):
    """
    Livrable attendu pour une recommandation.

    Chaque recommandation a N livrables. L'opérationnel (ETP/DM)
    coche les livrables terminés pour faire avancer le pourcentage.
    Le taux d'avancement est calculé via ``Recommendation.progress_percentage``.

    Ref. Architecture : §7.2 ERD — table ``workflow_deliverable``
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name="deliverables",
        verbose_name=_("Recommandation"),
        help_text=_("Recommandation parente à laquelle ce livrable est rattaché."),
    )
    label = models.CharField(
        _("Intitulé du livrable"),
        max_length=255,
        help_text=_("Ex: Procédure KYC mise à jour, Formation des agents."),
    )
    order = models.PositiveIntegerField(
        _("Ordre d'affichage"),
        default=0,
        help_text=_("Position du livrable dans la checklist."),
    )
    is_completed = models.BooleanField(
        _("Terminé"),
        default=False,
        help_text=_("Coché par l'opérationnel (ETP/DM) quand le livrable est terminé."),
    )
    completed_at = models.DateTimeField(
        _("Date de complétion"),
        null=True,
        blank=True,
        help_text=_("Horodatage automatique lors du cochage."),
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_deliverables",
        verbose_name=_("Complété par"),
        help_text=_("Utilisateur ayant marqué le livrable comme terminé."),
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("Livrable")
        verbose_name_plural = _("Livrables")
        ordering = ["order", "created_at"]

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.label}"
