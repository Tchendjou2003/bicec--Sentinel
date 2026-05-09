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
from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# Organigramme Institutionnel
# =============================================================================


class Department(models.Model):
    """
    Entité organisationnelle de la BICEC (Direction, Agence, Filiale).

    Structure hiérarchique auto-référencée permettant de modéliser
    l'arborescence complète de l'institution. Condition sine qua non
    du RBAC : chaque utilisateur est rattaché à un département,
    et ne voit que les données de son périmètre (FR28).

    Ref. Architecture : §7.2 ERD — table ``users_department``
    """

    class Type(models.TextChoices):
        DIRECTION = "DIRECTION", _("Direction")
        AGENCE = "AGENCE", _("Agence")
        FILIALE = "FILIALE", _("Filiale")

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
    type = models.CharField(
        _("Type"),
        max_length=20,
        choices=Type.choices,
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
            models.Index(fields=["type"], name="idx_dept_type"),
            models.Index(fields=["code"], name="idx_dept_code"),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    def get_children(self):
        """Retourne les départements enfants directs (actifs uniquement)."""
        return self.children.filter(is_active=True)


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
        RSSI = "RSSI", _("RSSI / Support IT")

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
