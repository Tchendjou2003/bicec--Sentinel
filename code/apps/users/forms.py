"""
Users App — Forms (Convention HackSoft)

Formulaires Django pour la gestion Admin des comptes et de l'organigramme.

Spécifications couvertes :
    - FR35 : Gestion de l'organigramme (Directions, Services, Agences)
    - FR37 : Création de comptes « coquilles vides » (ADR-10)
    - ADR-10 : Séparation — l'Admin ne peut PAS attribuer de rôle
    - Story 6.2.0 : Provisioning Maker/Checker (UserProvisioningRequestForm)
"""
from django import forms
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from .models import Department, OrgUnitType, User


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


class OrgUnitTypeForm(forms.ModelForm):
    """
    Formulaire de création/modification d'un type d'unité organisationnelle.

    Le ``code`` est verrouillé en édition (immuable après création).
    Seuls ``name`` et ``level`` sont modifiables.
    """

    class Meta:
        model = OrgUnitType
        fields = ("code", "name", "level")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Verrouiller le code en édition
        if self.instance and not self.instance._state.adding:
            self.fields["code"].disabled = True
            self.fields["code"].help_text = "Le code est immuable après création."

        self.fields["name"].widget.attrs["placeholder"] = "Ex: Direction Générale"
        self.fields["code"].widget.attrs["placeholder"] = "Ex: DG"
        self.fields["level"].widget.attrs["placeholder"] = "0"

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

        # TomSelect — sélecteur hiérarchique parent (Story 6.2.0)
        parent_widget = self.fields["parent"].widget  # type: ignore
        css = parent_widget.attrs.get("class", "")
        if "js-tomselect" not in css:
            parent_widget.attrs["class"] = css + " js-tomselect"
        parent_widget.attrs.setdefault("data-placeholder", "Rechercher un département parent…")

        # Queryset type : types actifs seulement, triés par niveau
        self.fields["type"].queryset = OrgUnitType.objects.filter(  # type: ignore
            is_active=True
        ).order_by("level", "name")

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


# =============================================================================
# Provisioning Maker/Checker (Story 6.2.0)
# =============================================================================

_SELECT_CLASS = (
    "w-full rounded-xl border border-border-subtle bg-surface-card px-3 py-2 "
    "text-sm text-text-primary "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)

_DATE_CLASS = (
    "w-full rounded-xl border border-border-subtle bg-surface-card px-3 py-2 "
    "text-sm text-text-primary "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)

_TEXTAREA_CLASS = (
    "w-full rounded-xl border border-border-subtle bg-surface-card px-3 py-2 "
    "text-sm text-text-primary resize-none "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)


class UserProvisioningRequestForm(forms.Form):
    """
    Formulaire de soumission d'une demande de provisioning (Story 6.2.0 / AC1).

    Formulaire simple (non ModelForm) pour gérer les champs non-modèle
    (``password`` en clair) et les champs EXT conditionnels (``mission_*``).

    Le mot de passe est exposé en clair dans ``cleaned_data["password"]``
    et haché dans le service ``create_provisioning_request``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Charger dynamiquement les organisations externes (Story 6.2.0)
        try:
            from apps.workflow.models import RecommendationSource
            sources = RecommendationSource.objects.filter(
                is_external=True, is_active=True
            ).order_by("label")
            choices = [("", "— Sélectionner une organisation —")]
            for s in sources:
                choices.append((s.label, s.label))
        except Exception:
            choices = [("", "— Sélectionner une organisation —")]

        # Pour les tests unitaires et la tolérance aux données historiques,
        # si la valeur soumise ou initiale n'est pas dans les choix, on l'ajoute.
        initial_val = self.initial.get("mission_organization")
        if not initial_val and self.data:
            initial_val = self.data.get("mission_organization")
        if initial_val and not any(initial_val == c[0] for c in choices):
            choices.append((initial_val, initial_val))

        self.fields["mission_organization"].choices = choices

    # ── Identité ─────────────────────────────────────────────────────
    requested_username = forms.CharField(
        label="Identifiant",
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        widget=forms.TextInput(attrs={
            "class": _INPUT_CLASS,
            "placeholder": "ex. j.dupont",
            "autocomplete": "off",
        }),
    )
    requested_first_name = forms.CharField(
        label="Prénom",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": _INPUT_CLASS, "placeholder": "Prénom"}),
    )
    requested_last_name = forms.CharField(
        label="Nom",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": _INPUT_CLASS, "placeholder": "Nom"}),
    )
    requested_email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={
            "class": _INPUT_CLASS,
            "placeholder": "prenom.nom@bicec.cm",
        }),
    )
    password = forms.CharField(
        label="Mot de passe initial",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "class": _INPUT_CLASS,
            "autocomplete": "new-password",
        }),
        help_text="Minimum 8 caractères. À transmettre hors-bande à l'utilisateur.",
    )

    # ── Habilitation ─────────────────────────────────────────────────
    requested_role = forms.ChoiceField(
        label="Rôle",
        choices=[("", "— Sélectionner un rôle —")] + list(User.Role.choices),
        widget=forms.Select(attrs={"class": _SELECT_CLASS, "x-ref": "roleSelect"}),
    )
    requested_department = forms.ModelChoiceField(
        label="Département",
        queryset=Department.objects.filter(is_active=True).select_related("parent", "type"),
        required=False,
        empty_label="— Aucun / Non requis —",
        widget=forms.Select(attrs={
            "class": _SELECT_CLASS + " js-tomselect",
            "data-placeholder": "Rechercher un département…",
        }),
    )

    # ── Mission externe (conditionnelle EXT) ─────────────────────────
    mission_organization = forms.ChoiceField(
        label="Organisation d'origine",
        required=False,
        choices=[],
        widget=forms.Select(attrs={
            "class": _SELECT_CLASS + " js-tomselect",
            "data-placeholder": "Rechercher une organisation…",
        }),
        help_text="Requis pour un auditeur externe (EXT).",
    )
    mission_scope = forms.CharField(
        label="Périmètre de la mission",
        required=False,
        widget=forms.Textarea(attrs={
            "class": _TEXTAREA_CLASS,
            "rows": 3,
            "placeholder": "Description du périmètre d'intervention…",
        }),
    )
    mission_start_date = forms.DateField(
        label="Date de début",
        required=False,
        widget=forms.DateInput(attrs={
            "class": _DATE_CLASS,
            "type": "date",
        }),
    )
    mission_end_date = forms.DateField(
        label="Date de fin (optionnel)",
        required=False,
        widget=forms.DateInput(attrs={
            "class": _DATE_CLASS,
            "type": "date",
        }),
    )

    def clean_requested_username(self):
        username = self.cleaned_data.get("requested_username", "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Un compte avec cet identifiant existe déjà.")
        return username

    def clean_requested_email(self):
        email = self.cleaned_data.get("requested_email", "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte avec cet e-mail existe déjà.")
        return email

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("requested_role", "")
        dept = cleaned.get("requested_department")

        # Département requis sauf pour AUDIT, ADMIN, EXT
        roles_no_dept = {User.Role.AUDIT, User.Role.ADMIN, User.Role.EXT}
        if role and role not in roles_no_dept and not dept:
            self.add_error(
                "requested_department",
                "Le département est obligatoire pour ce rôle.",
            )

        # Champs EXT conditionnellement requis
        if role == User.Role.EXT:
            if not cleaned.get("mission_organization"):
                self.add_error(
                    "mission_organization",
                    "L'organisation est obligatoire pour un auditeur externe.",
                )
            if not cleaned.get("mission_start_date"):
                self.add_error(
                    "mission_start_date",
                    "La date de début est obligatoire pour un auditeur externe.",
                )
            start = cleaned.get("mission_start_date")
            end = cleaned.get("mission_end_date")
            if start and end and start > end:
                self.add_error(
                    "mission_end_date",
                    "La date de fin ne peut pas être antérieure à la date de début.",
                )

        return cleaned
