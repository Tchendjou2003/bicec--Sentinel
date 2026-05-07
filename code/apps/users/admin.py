"""
Users App — Admin Configuration

Configuration du Django Admin pour les modèles Department et User.
Le RSSI utilise cette interface pour gérer l'organigramme et créer
les comptes « coquilles vides » (ADR-10, FR35).

Sécurité (ADR-10) :
    - Le champ ``role`` est en lecture seule dans le Django Admin
      pour empêcher le RSSI d'attribuer des rôles métiers.
    - Le champ ``is_audit_admin`` est masqué du Django Admin
      (géré uniquement par l'interface dédiée Audit).
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Department, User


# =============================================================================
# Department Admin — Organigramme (Story 1.4)
# =============================================================================


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin pour la gestion de l'organigramme institutionnel (FR35)."""

    list_display = ("name", "code", "type", "parent", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("name", "code")
    list_select_related = ("parent",)
    ordering = ("name",)


# =============================================================================
# User Admin — Comptes « Coquilles Vides » (Story 1.4, ADR-10)
# =============================================================================


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin Sentinel aligné sur le modèle User personnalisé.

    Protection ADR-10 : le champ ``role`` est en lecture seule
    pour les utilisateurs non-superuser (le RSSI ne peut pas
    attribuer de rôles métiers via le Django Admin).
    """

    list_display = (
        "username",
        "email",
        "role",
        "department",
        "is_active",
        "is_external",
    )
    list_filter = ("role", "is_active", "is_external", "department")
    search_fields = ("username", "email", "first_name", "last_name")
    list_select_related = ("department",)

    # Formulaire d'édition — champs Sentinel ajoutés
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            _("Profil Sentinel"),
            {
                "fields": ("role", "department", "is_external"),
                "description": _(
                    "Le rôle métier est attribué par l'Audit Interne "
                    "via l'interface dédiée d'habilitation (ADR-10)."
                ),
            },
        ),
    )

    # Formulaire de création — le RSSI crée les comptes sans rôle
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            _("Rattachement"),
            {
                "fields": ("first_name", "last_name", "email", "department"),
                "description": _(
                    "Créez le compte avec l'identité technique. "
                    "Le rôle sera attribué par l'Audit Interne."
                ),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """
        Rend les champs ``role`` et ``is_audit_admin`` en lecture seule
        pour les utilisateurs non-superuser (ADR-10).

        Seul un superuser (script initial) peut modifier ces champs
        via le Django Admin. En production, l'interface dédiée Audit
        gère les habilitations.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.extend(["role", "is_audit_admin"])
        return readonly

    def get_exclude(self, request, obj=None):
        """
        Masque ``is_audit_admin`` du Django Admin pour tous les
        utilisateurs (géré uniquement par l'interface Audit dédiée).
        """
        exclude = list(super().get_exclude(request, obj) or [])
        if not request.user.is_superuser:
            exclude.append("is_audit_admin")
        return exclude
