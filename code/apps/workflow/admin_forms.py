"""
Workflow App — Formulaires d'administration (Convention HackSoft)

Formulaires dédiés à la gestion des référentiels paramétrables par l'Audit Admin.
Séparés de forms.py (formulaires métier workflow) pour une séparation claire
des préoccupations.

Spécifications couvertes :
    - Story 3.7.b : Paramétrage sources de recommandations et types d'unité
    - AC5 : Code immuable après création
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import RecommendationSource


# ── Style Tailwind partagé (identique à forms.py) ──────────────────────
_INPUT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 placeholder-gray-400 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)

_INPUT_DISABLED_CLASS = (
    "w-full rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 "
    "text-sm text-gray-500 cursor-not-allowed"
)

_SELECT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)


class RecommendationSourceForm(forms.ModelForm):
    """
    Formulaire de création/modification d'une source de recommandation.

    Piège 1 (Story 3.7.b Dev Notes) : UUIDField génère un UUID dès
    l'instanciation Python → self.instance.pk est TOUJOURS non-None,
    même pour une nouvelle instance. Utiliser self.instance._state.adding
    pour distinguer création vs édition.

    AC5 : le champ `code` est rendu en lecture seule (disabled) en édition.
    """

    class Meta:
        model = RecommendationSource
        fields = ["code", "label", "is_external"]
        widgets = {
            "code": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "Ex: MINFI",
            }),
            "label": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "Ex: Ministère des Finances",
            }),
            "is_external": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 rounded border-gray-300 text-sentinel-orange",
            }),
        }
        labels = {
            "code": _("Code (immuable)"),
            "label": _("Libellé"),
            "is_external": _("Source externe (COBAC, ANIF…)"),
        }
        help_texts = {
            "code": _("Identifiant technique unique. Ne peut plus être modifié après création."),
            "label": _("Libellé affiché dans l'UI et les exports."),
            "is_external": _("Décocher pour les sources internes (Audit Interne)."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Piège 1 : utiliser _state.adding (pas .pk) avec UUIDField
        if not self.instance._state.adding:
            self.fields["code"].disabled = True
            self.fields["code"].widget.attrs["class"] = _INPUT_DISABLED_CLASS
            self.fields["code"].widget.attrs["title"] = _(
                "Le code ne peut pas être modifié après création."
            )

    def clean_code(self):
        """
        Normalise le code en majuscules et vérifie qu'il n'est pas vide.
        Ne pas dupliquer le check d'unicité — Django _post_clean le fait automatiquement.
        """
        code = self.cleaned_data.get("code", "").strip().upper()
        if not code:
            raise forms.ValidationError(_("Le code ne peut pas être vide."))
        return code

    def clean_label(self):
        """Normalise le libellé (strip whitespace)."""
        label = self.cleaned_data.get("label", "").strip()
        if not label:
            raise forms.ValidationError(_("Le libellé ne peut pas être vide."))
        return label
