"""
Users App — Models (Convention HackSoft)

Modèles de données pour la gestion des utilisateurs et de l'organigramme
institutionnel de la BICEC.

Spécifications couvertes :
    - FR28 : Visibilité restreinte par périmètre via RBAC
    - FR35 : Gestion de l'organigramme (Directions, Services, Agences)
    - FR36 : Délégation admin Directeur Audit (ADR-10)
    - FR37 : Compte en attente d'activation (ADR-10)

Architecture : HackSoft Styleguide — couche Model uniquement.
Les requêtes complexes sont dans selectors.py, la logique d'écriture dans services.py.
"""
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# Organigramme Institutionnel
# =============================================================================


class OrgUnitType(models.Model):
    """
    Type d'unité organisationnelle (paramétrable par l'Audit Admin).

    Remplace l'enum statique ``Department.Type`` par un catalogue dynamique
    permettant à l'Audit Admin de créer, renommer et désactiver les types
    sans déploiement (Story 3.7.b / Phase B).

    Le champ ``level`` est purement indicatif (aide au tri UI) — il ne
    constitue pas une contrainte de profondeur imposée à l'organigramme.

    Ref. Architecture : §7.2 — table ``users_orgunittype``
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        _("Libellé"),
        max_length=60,
        help_text=_("Nom affiché dans l'interface (ex : Direction Générale)."),
    )
    code = models.CharField(
        _("Code"),
        max_length=20,
        unique=True,
        help_text=_(
            "Code technique court unique (ex : DG). "
            "Verrouillé après création."
        ),
    )
    level = models.PositiveSmallIntegerField(
        _("Niveau indicatif"),
        default=0,
        help_text=_(
            "Indication de profondeur dans l'organigramme (0 = sommet). "
            "Valeur indicative uniquement — ne constitue pas une contrainte."
        ),
    )
    is_active = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_(
            "Désactiver plutôt que supprimer pour préserver "
            "l'intégrité des données existantes."
        ),
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("Type d'unité organisationnelle")
        verbose_name_plural = _("Types d'unités organisationnelles")
        ordering = ["level", "name"]
        indexes = [
            models.Index(fields=["code"], name="idx_orgunit_type_code"),
        ]

    def __str__(self) -> str:
        return self.name


class Department(models.Model):
    """
    Entité organisationnelle de la BICEC.

    Structure hiérarchique auto-référencée modélisant l'arborescence
    complète de l'institution (DG → Direction → Sous-Direction →
    Département → Service / Région → Agence). Condition sine qua non
    du RBAC : chaque utilisateur est rattaché à un département,
    et ne voit que les données de son périmètre (FR28).

    Ref. Architecture : §7.2 ERD — table ``users_department``
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        _("Nom"),
        max_length=100,
        help_text=_("Nom complet du département (ex: Direction des Opérations)."),
    )
    code = models.CharField(
        _("Code"),
        max_length=10,
        unique=True,
        help_text=_(
            "Code court unique (ex: DOP). Utilisé dans les filtres "
            "et les exports pour identifier rapidement le département."
        ),
    )
    type = models.ForeignKey(
        OrgUnitType,
        on_delete=models.PROTECT,
        related_name="departments",
        verbose_name=_("Type"),
        help_text=_("Catégorie structurelle dans l'organigramme BICEC."),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Département parent"),
        help_text=_(
            "Département hiérarchiquement supérieur. "
            "NULL pour les entités racines (Directions principales)."
        ),
    )
    is_active = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_(
            "Désactiver plutôt que supprimer pour préserver "
            "l'intégrité des données historiques."
        ),
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("Département")
        verbose_name_plural = _("Départements")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["parent"], name="idx_dept_parent"),
            models.Index(fields=["code"], name="idx_dept_code"),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    def get_children(self):
        """Retourne les départements enfants directs (actifs uniquement)."""
        return type(self).objects.filter(parent=self, is_active=True)


# =============================================================================
# Utilisateur Sentinel
# =============================================================================


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé pour Sentinel.

    Clé primaire UUID, rôle métier contraint par TextChoices,
    rattachement à un département pour le RBAC, et flag
    d'administration Audit (ADR-10).

    Un utilisateur dont le champ ``role`` est vide est un compte
    « coquille vide » créé par le Support IT. Il ne peut accéder
    à aucune fonctionnalité métier tant que le Directeur de l'Audit
    Interne ne lui a pas attribué un rôle via l'interface dédiée (FR37).

    Ref. Architecture : §7.2 ERD — table ``users_user``
    """

    class Role(models.TextChoices):
        AUDIT = "AUDIT", _("Audit Interne")
        DM = "DM", _("Directeur Métier")
        ETP = "ETP", _("Employé Traitant")
        DG = "DG", _("Direction Générale")
        EXT = "EXT", _("Auditeur Externe")
        ADMIN = "ADMIN", _("Admin")

    id = models.UUIDField(  
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    role = models.CharField(
        _("Rôle"),
        max_length=10,
        choices=Role.choices,
        blank=True,
        default="",
        help_text=_(
            "Rôle métier Sentinel. Vide = compte « coquille vide » en attente "
            "d'activation par l'Audit Interne (ADR-10, FR37)."
        ),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("Département"),
        help_text=_(
            "Département de rattachement. Détermine le périmètre RBAC "
            "de visibilité des données (FR28)."
        ),
    )
    is_external = models.BooleanField(
        _("Compte externe"),
        default=False,
        help_text=_(
            "Réservé aux auditeurs externes (COBAC/BEAC/CAC). "
            "Limite l'accès au périmètre de mission uniquement (Story 1.3)."
        ),
    )
    is_audit_admin = models.BooleanField(
        _("Administrateur Audit"),
        default=False,
        help_text=_(
            "Flag du Directeur de l'Audit Interne ou de ses délégués (ADR-10). "
            "Permet d'attribuer les rôles métiers et les habilitations "
            "aux comptes « coquilles vides » via l'interface dédiée (FR36)."
        ),
    )

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        indexes = [
            models.Index(fields=["role"], name="idx_user_role"),
            models.Index(fields=["department"], name="idx_user_dept"),
        ]

    def __str__(self):
        return self.username

    # ── Propriétés de domaine ──────────────────────────────────────

    @property
    def has_role(self) -> bool:
        """
        Indique si le compte a un rôle métier attribué.

        Un compte sans rôle est une « coquille vide » créée par le
        Support IT, en attente d'activation par l'Audit Interne (FR37).
        """
        return bool(self.role)

    @property
    def can_manage_users(self) -> bool:
        """
        Indique si l'utilisateur peut gérer les habilitations (ADR-10).

        Seuls les Auditeurs Internes ayant le flag ``is_audit_admin``
        activé (Directeur Audit ou délégué) peuvent attribuer des rôles
        et des périmètres aux comptes « coquilles vides » (FR3, FR36).
        """
        return self.role == self.Role.AUDIT and self.is_audit_admin

    @property
    def is_shell_account(self) -> bool:
        """
        Indique si le compte est une « coquille vide » (sans rôle métier).

        Utilisé par le middleware ``RoleRequiredMiddleware`` pour
        rediriger vers la page d'attente d'activation (FR37).
        """
        return not self.has_role


# =============================================================================
# Provisioning Maker/Checker (Story 6.2.0)
# =============================================================================

# Rôles provisionnables par l'Admin IT (tous les rôles, EXT inclus)
PROVISIONABLE_ROLE_CHOICES = User.Role.choices


class UserProvisioningRequest(models.Model):
    """
    Demande de création de compte (pattern Maker/Checker — Story 6.2.0).

    L'Admin IT (maker) soumet une demande complète (identité + rôle +
    département + mot de passe haché). Un membre du groupe
    « Administrateurs Sentinel » (checker) valide ou rejette.

    Aucun ``User`` n'est créé avant l'approbation. En cas de rejet, la
    demande meurt (re-soumission = nouvelle demande). Le mot de passe
    est stocké haché (``make_password``) dès la soumission — jamais en
    clair.

    Pour les comptes EXT, les champs ``mission_*`` sont conditionnellement
    requis (validés en ``.clean()``) et donnent lieu à la création
    atomique d'une ``ExternalMission`` lors de l'approbation.

    Ref. Architecture : §7.2 — table ``users_userprovisioningrequest``
    """

    class Status(models.TextChoices):
        PENDING   = "PENDING",   _("En attente")
        APPROVED  = "APPROVED",  _("Approuvée")
        REJECTED  = "REJECTED",  _("Rejetée")
        CANCELLED = "CANCELLED", _("Annulée")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    # ── Identité demandée ─────────────────────────────────────────────
    requested_username = models.CharField(
        _("Identifiant"),
        max_length=150,
        help_text=_("Login de connexion du futur compte."),
    )
    requested_first_name = models.CharField(
        _("Prénom"),
        max_length=150,
        blank=True,
        default="",
    )
    requested_last_name = models.CharField(
        _("Nom"),
        max_length=150,
        blank=True,
        default="",
    )
    requested_email = models.EmailField(
        _("E-mail"),
        help_text=_("Adresse e-mail professionnelle du futur compte."),
    )
    # Mot de passe haché via make_password avant persistance (jamais clair)
    hashed_initial_password = models.CharField(
        _("Mot de passe initial (haché)"),
        max_length=128,
        help_text=_(
            "Hash Django du mot de passe initial saisi par l'Admin IT. "
            "Transféré tel quel au User lors de l'approbation."
        ),
    )
    # ── Habilitation demandée ─────────────────────────────────────────
    requested_role = models.CharField(
        _("Rôle"),
        max_length=10,
        choices=PROVISIONABLE_ROLE_CHOICES,
        help_text=_("Rôle métier à attribuer au compte lors de l'approbation."),
    )
    requested_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provisioning_requests",
        verbose_name=_("Département"),
        help_text=_(
            "Département de rattachement. Optionnel pour AUDIT, ADMIN et EXT."
        ),
    )
    # ── Mission externe (conditionnel si rôle == EXT) ─────────────────
    mission_organization = models.CharField(
        _("Organisation (auditeur externe)"),
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "Organisation d'origine de l'auditeur externe (ex. COBAC, BEAC). "
            "Requis si le rôle est EXT."
        ),
    )
    mission_scope = models.TextField(
        _("Périmètre de la mission"),
        blank=True,
        default="",
        help_text=_("Description libre du périmètre d'intervention de la mission."),
    )
    mission_start_date = models.DateField(
        _("Date de début de mission"),
        null=True,
        blank=True,
        help_text=_("Requis si le rôle est EXT."),
    )
    mission_end_date = models.DateField(
        _("Date de fin de mission"),
        null=True,
        blank=True,
        help_text=_("Optionnel — peut être laissé vide si la durée est indéterminée."),
    )
    # ── État de la demande ────────────────────────────────────────────
    status = models.CharField(
        _("Statut"),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField(
        _("Motif du rejet"),
        blank=True,
        default="",
        help_text=_("Obligatoire en cas de rejet. Laissé vide sinon."),
    )
    # ── Acteurs ───────────────────────────────────────────────────────
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="provisioning_requests_made",
        verbose_name=_("Demandé par"),
        help_text=_("Admin IT (maker) qui a soumis la demande."),
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provisioning_requests_reviewed",
        verbose_name=_("Traité par"),
        help_text=_("Membre du groupe « Administrateurs Sentinel » (checker)."),
    )
    reviewed_at = models.DateTimeField(
        _("Traité le"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("Demande de provisioning")
        verbose_name_plural = _("Demandes de provisioning")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_provreq_status"),
            models.Index(fields=["requested_by"], name="idx_provreq_maker"),
        ]

    def __str__(self):
        return (
            f"[{self.status}] {self.requested_username} "
            f"({self.get_requested_role_display()}) — {self.requested_by}"
        )

    def clean(self):
        super().clean()
        # Unicité username contre TOUS les User (actifs ou non — contrainte DB globale)
        if self.requested_username:
            qs = User.objects.filter(username__iexact=self.requested_username)
            if qs.exists():
                raise ValidationError(
                    {"requested_username": _(
                        "Un compte avec cet identifiant existe déjà."
                    )}
                )
        # Unicité email contre tous les User (règle métier)
        if self.requested_email:
            qs = User.objects.filter(email__iexact=self.requested_email)
            if qs.exists():
                raise ValidationError(
                    {"requested_email": _(
                        "Un compte avec cet e-mail existe déjà."
                    )}
                )
        # Cohérence rôle/département : EXT, AUDIT et ADMIN peuvent avoir dept=None
        roles_no_dept_required = {User.Role.AUDIT, User.Role.ADMIN, User.Role.EXT}
        if (
            self.requested_role
            and self.requested_role not in roles_no_dept_required
            and not self.requested_department_id
        ):
            raise ValidationError(
                {"requested_department": _(
                    "Le département est obligatoire pour ce rôle."
                )}
            )
        # Champs mission obligatoires si EXT
        if self.requested_role == User.Role.EXT:
            if not self.mission_organization:
                raise ValidationError(
                    {"mission_organization": _(
                        "L'organisation est obligatoire pour un auditeur externe."
                    )}
                )
            if not self.mission_start_date:
                raise ValidationError(
                    {"mission_start_date": _(
                        "La date de début de mission est obligatoire pour un auditeur externe."
                    )}
                )
            if (
                self.mission_start_date
                and self.mission_end_date
                and self.mission_start_date > self.mission_end_date
            ):
                raise ValidationError(
                    {"mission_end_date": _(
                        "La date de fin ne peut pas être antérieure à la date de début."
                    )}
                )


# =============================================================================
# Mission Externe (Story 1.3 — AC4)
# =============================================================================


class ExternalMission(models.Model):
    """
    Mission d'audit externe rattachée à un auditeur (COBAC, BEAC, CAC…).

    Définit l'organisation d'origine, le périmètre d'intervention et
    les dates de la mission. Permet de tracer quel auditeur externe
    intervient, quand, et sur quel scope.

    Note : La relation M2M avec les recommandations (``external_mission_recommendations``)
    sera implémentée dans l'Epic 2 lorsque l'application ``workflow`` sera créée.

    Ref. Architecture : §7.2 ERD — table ``users_external_mission``
    Ref. PRD : FR2 (Opening Scene COBAC)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    auditor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        limit_choices_to={"is_external": True, "role": User.Role.EXT},
        related_name="external_missions",
        verbose_name=_("Auditeur externe"),
        help_text=_(
            "Utilisateur externe (is_external=True) rattaché à cette mission."
        ),
    )
    organization = models.CharField(
        _("Organisation"),
        max_length=100,
        help_text=_(
            "Institution d'origine de l'auditeur (ex: COBAC, BEAC, CAC)."
        ),
    )
    scope_description = models.TextField(
        _("Périmètre de la mission"),
        blank=True,
        default="",
        help_text=_(
            "Description libre du périmètre d'intervention "
            "(ex: Audit des procédures de crédit)."
        ),
    )
    start_date = models.DateField(
        _("Date de début"),
        help_text=_("Date de début de la mission d'audit externe."),
    )
    end_date = models.DateField(
        _("Date de fin"),
        null=True,
        blank=True,
        help_text=_(
            "Date de fin prévue. Peut être NULL si la durée n'est pas "
            "encore définie."
        ),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Indique si la mission est en cours. Désactiver en fin "
            "de mission plutôt que supprimer."
        ),
    )
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("Mission externe")
        verbose_name_plural = _("Missions externes")
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["auditor"], name="idx_extmission_auditor"),
            models.Index(fields=["organization"], name="idx_extmission_org"),
            models.Index(fields=["is_active"], name="idx_extmission_active"),
        ]

    def __str__(self):
        auditor_name = self.auditor.username if hasattr(self, "auditor") and self.auditor else "N/A"
        return f"{self.organization} — {auditor_name}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                {"end_date": _("La date de fin ne peut pas être antérieure à la date de début.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
