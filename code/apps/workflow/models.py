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
from django.core.exceptions import PermissionDenied, ValidationError
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


class ImmutableQuerySet(models.QuerySet):
    """QuerySet qui bloque la suppression en masse des preuves soumises (AC4 story 3.3).

    Les fichiers rattachés à un brouillon DRAFT peuvent être supprimés.
    Les fichiers rattachés à une soumission PENDING/ACCEPTED sont immuables.
    """

    def delete(self):
        # Autoriser la suppression en masse uniquement pour les fichiers en brouillon DRAFT
        non_draft = self.exclude(submission__status="DRAFT")
        if non_draft.exists():
            raise PermissionDenied(
                "La suppression en masse de pièces justificatives soumises est interdite. "
                "Les preuves sont immuables (append-only)."
            )
        return super().delete()


class ImmutableManager(models.Manager):
    """Manager associé à ImmutableQuerySet pour les modèles append-only."""

    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)


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

    @property
    def active_draft(self):
        """
        Retourne le brouillon DRAFT actif de soumission de preuves, s'il existe.

        Utilisé par l'Audit pour afficher un indicateur d'activité discret
        sans révéler le contenu sensible du brouillon (PRD v2 §8).

        Returns:
            EvidenceSubmission | None: Le brouillon actif ou None.
        """
        return self.evidence_submissions.filter(
            status=EvidenceSubmission.SubmissionStatus.DRAFT
        ).first()

    @property
    def draft_progress_info(self) -> dict:
        """
        Dictionnaire d'activité du brouillon visible par l'Audit.

        Contient uniquement des métadonnées (présence, date, compteur)
        sans le contenu du commentaire ou les noms de fichiers.

        Returns:
            dict: {"has_draft": bool, "updated_at": datetime | None, "files_count": int}
        """
        draft = self.active_draft
        if not draft:
            return {"has_draft": False, "updated_at": None, "files_count": 0}
        return {
            "has_draft": True,
            "updated_at": draft.updated_at,
            "files_count": draft.files.count(),
        }

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

    @transition(field=status, source=Status.ASSIGNED, target=Status.IN_PROGRESS)
    def start_processing(self):
        """
        Transition vers IN_PROGRESS (FR12 — Story 3.2).

        Déclenchée lorsque le DM délègue à un ETP ou
        s'auto-assigne en tant que DM Porteur.

        Cette transition est protégée par django-fsm :
        elle ne peut être appelée que depuis l'état ASSIGNED.
        """
        pass

    @transition(field=status, source=Status.IN_PROGRESS, target=Status.PENDING_DM_REVIEW)
    def submit_evidence(self):
        """
        Transition vers PENDING_DM_REVIEW (Story 3.3).

        Déclenchée lorsque l'ETP (ou DM Porteur) soumet ses preuves.
        La logique de validation et la création des EvidenceFile
        sont orchestrées par le service layer avant cet appel.
        """
        pass

    @transition(field=status, source=Status.PENDING_DM_REVIEW, target=Status.IN_PROGRESS)
    def reject_evidence(self):
        """
        Transition PENDING_DM_REVIEW → IN_PROGRESS (Story 3.4 — AC1).

        Déclenchée lorsque le DM rejette les preuves soumises par l'ETP.
        La mise à jour de l'EvidenceSubmission (REJECTED + motif) est
        orchestrée par reject_evidence_submission() dans le service layer.
        """
        pass

    @transition(field=status, source=Status.PENDING_DM_REVIEW, target=Status.PENDING_AUDIT_REVIEW)
    def approve_for_audit(self):
        """
        Transition PENDING_DM_REVIEW → PENDING_AUDIT_REVIEW (Story 3.5 — AC1).

        Déclenchée lorsque le DM valide les preuves et les envoie à l'Audit Interne.
        La mise à jour de l'EvidenceSubmission (ACCEPTED + commentaire DM) et
        la vérification de l'exemption PV de Recette (FR19) sont orchestrées
        par validate_evidence_for_audit() dans le service layer.
        """
        pass


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


# =============================================================================
# Preuves de soumission (Story 3.3 — Immutabilité)
# =============================================================================


class EvidenceSubmission(models.Model):
    """
    Groupe d'une soumission de preuves par un ETP ou DM Porteur.

    Chaque soumission contient un commentaire de résolution global
    et N fichiers probatoires. Une recommandation peut avoir plusieurs
    soumissions en cas de rejet DM suivi d'une resoumission.

    Le cycle de vie est : DRAFT → PENDING → ACCEPTED / REJECTED.
    - **DRAFT** : Brouillon de l'ETP, visible uniquement par lui (PRD v2 FR15).
      Les fichiers peuvent être ajoutés/supprimés librement.
    - **PENDING** : Soumis au DM pour validation. Les fichiers deviennent immuables.
    - **ACCEPTED / REJECTED** : Piloté par le DM (Story 3.4).

    Les soumissions REJECTED ne comptent plus dans le quota de 20 Mo actifs
    de la recommandation (NFR-SCA-01).

    Ref. Architecture : Story 3.3 — FR13, AC3, AC7 ; Story 3.4 — AC2.
    """

    class SubmissionStatus(models.TextChoices):
        DRAFT    = "DRAFT",    _("Brouillon")
        PENDING  = "PENDING",  _("En attente de validation")
        ACCEPTED = "ACCEPTED", _("Acceptée")
        REJECTED = "REJECTED", _("Rejetée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name="evidence_submissions",
        verbose_name=_("Recommandation"),
    )
    comment = models.TextField(
        _("Commentaire de résolution"),
        blank=True,
        default="",
        help_text=_(
            "Explication de l'ETP sur les actions menées pour résoudre la recommandation. "
            "Vide en brouillon, obligatoire à la soumission."
        ),
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evidence_submissions",
        verbose_name=_("Soumis par"),
    )
    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.DRAFT,
        help_text=_(
            "DRAFT à la création du brouillon. PENDING à la soumission. "
            "ACCEPTED/REJECTED piloté par le DM (Story 3.4)."
        ),
    )
    review_comment = models.TextField(
        _("Motif de rejet"),
        blank=True,
        default="",
        help_text=_("Motif saisi par le DM lors du rejet (Story 3.4 — AC2)."),
    )
    reviewed_at = models.DateTimeField(
        _("Rejeté le"),
        null=True,
        blank=True,
        help_text=_("Horodatage du rejet par le DM."),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_submissions",
        verbose_name=_("Rejeté par"),
        help_text=_(
            "DM qui a rejeté la soumission. Dénormalisé pour requêtes analytiques "
            "rapides sans JOIN sur AuditLog (Story 3.4 — L2)."
        ),
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(
        _("Modifié le"),
        auto_now=True,
        help_text=_(
            "Dernière activité sur le brouillon (ajout/suppression fichier, "
            "modification commentaire). Visible par l'Audit sans contenu sensible."
        ),
    )

    class Meta:
        verbose_name = _("Soumission de preuves")
        verbose_name_plural = _("Soumissions de preuves")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recommendation", "submitted_by"],
                condition=models.Q(status="DRAFT"),
                name="unique_draft_per_reco_user",
            ),
        ]
        indexes = [
            models.Index(fields=["recommendation", "status"]),
            models.Index(fields=["submitted_by", "status"]),
        ]

    def __str__(self):
        return f"Soumission {self.recommendation.reference} — {self.get_status_display()} — {self.created_at:%Y-%m-%d}"


def _evidence_upload_path(instance, filename):
    """Calcule le chemin de stockage avec UUID comme nom de fichier (évite les collisions)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"evidence/{instance.submission.recommendation_id}/{timezone.now():%Y/%m}/{uuid.uuid4()}.{ext}"


class EvidenceFile(models.Model):
    """
    Fichier probatoire individuel.

    L'immutabilité est **conditionnelle** au statut de la soumission parente :
    - DRAFT : le fichier peut être supprimé librement par son auteur.
    - PENDING / ACCEPTED / REJECTED : le fichier est immuable (append-only, AC4).

    Le nom physique sur disque est un UUID pour éviter les collisions et
    les attaques par path traversal. Le nom original est conservé en DB.

    Ref. Architecture : Story 3.3 — FR13, AC1, AC2, AC4, NFR-SEC-04.
    """

    class Tag(models.TextChoices):
        JUSTIFICATIF = "JUSTIFICATIF", _("Justificatif")
        PV_RECETTE = "PV_RECETTE", _("PV de recette")
        RAPPORT = "RAPPORT", _("Rapport")
        AUTRE = "AUTRE", _("Autre")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        EvidenceSubmission,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name=_("Soumission"),
    )
    file = models.FileField(
        _("Fichier"),
        upload_to=_evidence_upload_path,
    )
    original_filename = models.CharField(
        _("Nom original"),
        max_length=255,
        help_text=_("Nom du fichier tel que fourni par l'utilisateur."),
    )
    file_size = models.PositiveIntegerField(
        _("Taille (octets)"),
        help_text=_("Taille du fichier en octets au moment du dépôt."),
    )
    mime_type = models.CharField(
        _("Type MIME"),
        max_length=100,
        help_text=_("Type MIME détecté depuis les magic bytes, pas l'extension."),
    )
    sha256_hash = models.CharField(
        _("Hash SHA-256"),
        max_length=64,
        help_text=_("Empreinte intègre du fichier pour vérification d'intégrité."),
    )
    tag = models.CharField(
        _("Catégorie"),
        max_length=20,
        choices=Tag.choices,
        default=Tag.JUSTIFICATIF,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_evidence_files",
        verbose_name=_("Déposé par"),
    )
    created_at = models.DateTimeField(_("Déposé le"), auto_now_add=True)

    objects = ImmutableManager()

    class Meta:
        verbose_name = _("Fichier probatoire")
        verbose_name_plural = _("Fichiers probatoires")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["submission", "tag"]),
        ]

    @property
    def file_size_display(self) -> str:
        if self.file_size < 1_048_576:
            return f"{self.file_size / 1024:.0f} Ko"
        return f"{self.file_size / 1_048_576:.1f} Mo"

    def __str__(self):
        return f"{self.original_filename} ({self.get_tag_display()})"

    def delete(self, *args, **kwargs):
        """
        Suppression conditionnelle au statut de la soumission parente.

        - DRAFT : suppression autorisée (fichier physique + enregistrement DB).
        - PENDING / ACCEPTED / REJECTED : interdit (AC4 — immutabilité).

        Raises:
            PermissionDenied: Si la soumission n'est pas en DRAFT.
        """
        if self.submission.status != EvidenceSubmission.SubmissionStatus.DRAFT:
            raise PermissionDenied(
                "Les fichiers probatoires soumis sont immuables "
                "et ne peuvent pas être supprimés."
            )
        # Suppression physique du fichier sur disque
        if self.file:
            self.file.delete(save=False)
        super(EvidenceFile, self).delete(*args, **kwargs)


# =============================================================================
# Demande de Report d'Échéance (Story 3.6 — FR13, FR14, FR34)
# =============================================================================


class ExtensionRequest(models.Model):
    """
    Demande formelle de report d'échéance émise par le DM ou DG assigné.

    Modèle satellite de Recommendation — ne déclenche aucune transition FSM.
    Une seule demande PENDING est autorisée par recommandation à la fois.

    Workflow :
        PENDING (soumis) → APPROVED (Audit approuve) : due_date est mis à jour.
        PENDING (soumis) → REJECTED (Audit rejette) : due_date est inchangé.

    Plusieurs demandes peuvent exister par reco (historique APPROVED/REJECTED conservé),
    mais une seule en PENDING simultanément (guard dans request_extension()).

    Ref. Architecture : Story 3.6 — FR13, FR14, FR34.
    """

    class Status(models.TextChoices):
        PENDING  = "PENDING",  _("En attente")
        APPROVED = "APPROVED", _("Approuvée")
        REJECTED = "REJECTED", _("Rejetée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name="extension_requests",
        verbose_name=_("Recommandation"),
    )

    # ── Demande DM / DG ──────────────────────────────────────────────

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="extension_requests_made",
        verbose_name=_("Demandeur"),
        help_text=_("DM ou DG personnellement assigné ayant soumis la demande."),
    )
    requested_date = models.DateField(
        _("Nouvelle date souhaitée"),
        help_text=_("Date proposée par le demandeur pour la nouvelle échéance."),
    )
    reason = models.TextField(
        _("Motif de la demande"),
        max_length=2000,
        help_text=_("Justification obligatoire de la demande de report."),
    )

    # ── Réponse Audit ────────────────────────────────────────────────

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extension_requests_reviewed",
        verbose_name=_("Statué par"),
        help_text=_("Auditeur ayant approuvé ou rejeté la demande."),
    )
    reviewed_at = models.DateTimeField(
        _("Statué le"),
        null=True,
        blank=True,
    )
    audit_comment = models.TextField(
        _("Commentaire Audit"),
        max_length=2000,
        blank=True,
        default="",
        help_text=_(
            "Optionnel lors de l'approbation. "
            "Obligatoire lors du rejet (AC5)."
        ),
    )

    status = models.CharField(
        _("Statut"),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("Demande de report")
        verbose_name_plural = _("Demandes de report")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recommendation", "status"],
                name="idx_ext_req_reco_status",
            ),
        ]

    def __str__(self):
        return (
            f"Report {self.recommendation.reference} — "
            f"{self.get_status_display()} — {self.created_at:%Y-%m-%d}"
        )
