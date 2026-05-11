"""
Users App — Forms (Convention HackSoft)

Formulaires Django pour la gestion Admin des comptes et de l'organigramme.

Spécifications couvertes :
    - FR35 : Gestion de l'organigramme (Directions, Services, Agences)
    - FR37 : Création de comptes « coquilles vides » (ADR-10)
    - ADR-10 : Séparation — l'Admin ne peut PAS attribuer de rôle
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Department, User


# ── Style Tailwind partagé ────────────────────────────────────────────

_INPUT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 placeholder-gray-400 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)

_CHECKBOX_CLASS = (
    "h-5 w-5 rounded border-gray-300 text-sentinel-orange "
    "focus:ring-sentinel-orange/50"
)


class ITUserCreationForm(UserCreationForm):
    """
    Formulaire de création de compte par l'Admin (Support IT).

    Volontairement limité à l'identité technique (nom, prénom, email,
    mot de passe). Les champs `role`, `is_external`, `is_audit_admin`
    sont physiquement absents du formulaire pour garantir la séparation
    des fonctions (ADR-10). Le compte créé est une « coquille vide »
    (FR37) en attente d'habilitation par le Directeur de l'Audit Interne.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True

        for field in self.fields.values():
            field.widget.attrs.update({"class": _INPUT_CLASS})


class DepartmentForm(forms.ModelForm):
    """
    Formulaire de création/modification d'un département.

    Permet de saisir le nom, le code, le type hiérarchique et le parent.
    Le champ `parent` affiche le chemin hiérarchique complet pour chaque
    option (ex: « DG › Dir. Réseau › Rég. Littoral ») et est filtré
    pour ne proposer que les départements actifs (FR35).

    Valide qu'un département ne peut pas être son propre parent ni
    créer de référence circulaire (Code Review — HIGH #7).
    """

    class Meta:
        model = Department
        fields = ("name", "code", "type", "parent", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer le queryset parent : actifs uniquement, exclure soi-même
        qs = Department.objects.filter(is_active=True).select_related(
            "parent", "parent__parent", "parent__parent__parent"
        ).order_by("name")
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = qs  # type: ignore
        self.fields["parent"].required = False

        # Labels hiérarchiques pour le champ parent
        self.fields["parent"].label_from_instance = self._parent_label  # type: ignore

        self.fields["is_active"].initial = True
        self.fields["is_active"].required = False

        # Placeholders
        self.fields["name"].widget.attrs["placeholder"] = "Ex: Direction des Opérations"
        self.fields["code"].widget.attrs["placeholder"] = "Ex: DOP"

        # Styling Tailwind
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": _CHECKBOX_CLASS})
            else:
                field.widget.attrs.update({"class": _INPUT_CLASS})

    @staticmethod
    def _parent_label(obj: Department) -> str:
        """
        Génère un label hiérarchique pour le select du parent.

        Ex: « Direction Générale › Direction du Réseau › Rég. Littoral »
        au lieu de juste « Rég. Littoral ».
        """
        parts = [obj.name]
        current = obj.parent
        depth = 0
        while current and depth < 5:  # Sécurité anti-boucle
            parts.append(current.name)
            current = current.parent
            depth += 1
        parts.reverse()
        return " › ".join(parts)

    def clean_parent(self):
        """
        Empêche les références circulaires dans l'organigramme.

        Vérifie que :
        1. Un département ne peut pas être son propre parent.
        2. Le parent choisi n'est pas un descendant du département
           en cours d'édition (ce qui créerait une boucle).
        """
        parent = self.cleaned_data.get("parent")
        if parent is None:
            return parent

        # Interdire d'être son propre parent
        if self.instance and self.instance.pk and parent.pk == self.instance.pk:
            raise ValidationError(
                "Une structure ne peut pas être son propre parent."
            )

        # Interdire les cycles : vérifier que le parent choisi
        # n'est pas un descendant de l'instance actuelle
        if self.instance and self.instance.pk:
            current = parent
            depth = 0
            while current is not None and depth < 10:
                if current.pk == self.instance.pk:
                    raise ValidationError(
                        "Référence circulaire détectée : "
                        f"« {parent.name} » est déjà un descendant "
                        f"de « {self.instance.name} »."
                    )
                current = current.parent
                depth += 1

        return parent
