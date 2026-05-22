"""
Workflow App — Forms (Convention HackSoft)

Formulaires Django pour la création et modification des recommandations.

Spécifications couvertes :
    - FR5  : Création manuelle unitaire
    - AC1  : Stepper 4 étapes avec champs structurés
    - AC10 : Validation stricte (due_date, reference unique)
"""
from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.users.models import User
from .models import Deliverable, EvidenceFile, Recommendation
from .validators import validate_file_size, validate_magic_bytes


# ── Style Tailwind partagé ────────────────────────────────────────────

_INPUT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 placeholder-gray-400 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200"
)

_SELECT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200 appearance-none"
)

_TEXTAREA_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
    "text-sm text-gray-900 placeholder-gray-400 "
    "focus:border-sentinel-orange focus:ring-2 focus:ring-sentinel-orange/20 "
    "transition-all duration-200 resize-y"
)


class RecommendationForm(forms.ModelForm):
    """
    Formulaire de création/modification d'une recommandation.

    Expose les 11 champs métier visibles dans le Stepper.
    Les champs internes (status, created_by, assigned_dm, etc.)
    sont exclus et gérés côté service.
    """

    class Meta:
        model = Recommendation
        fields = [
            "reference",
            "mission_date",
            "mission_label",
            "controlled_department",
            "observations",
            "anomalous_dossiers",
            "description",
            "source",
            "priority",
            "department",
            "due_date",
        ]
        widgets = {
            "reference": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "REC-2026-...",
            }),
            "mission_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": _INPUT_CLASS,
                    "type": "date",
                }
            ),
            "mission_label": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "Ex: Contrôle KYC Q3 2025",
            }),
            "controlled_department": forms.Select(attrs={
                "class": _SELECT_CLASS,
            }),
            "observations": forms.Textarea(attrs={
                "class": _TEXTAREA_CLASS,
                "rows": 5,
                "placeholder": "Constats issus de la mission d'audit...",
            }),
            "anomalous_dossiers": forms.Textarea(attrs={
                "class": _TEXTAREA_CLASS,
                "rows": 3,
                "placeholder": "Description des dossiers en anomalies (optionnel)...",
            }),
            "description": forms.Textarea(attrs={
                "class": _TEXTAREA_CLASS,
                "rows": 5,
                "placeholder": "Il est recommandé de...",
            }),
            "source": forms.Select(attrs={
                "class": _SELECT_CLASS,
            }),
            "priority": forms.Select(attrs={
                "class": _SELECT_CLASS,
            }),
            "department": forms.Select(attrs={
                "class": _SELECT_CLASS,
            }),
            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": _INPUT_CLASS,
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        from typing import cast
        super().__init__(*args, **kwargs)
        # Restreindre les départements aux actifs uniquement
        from apps.users.models import Department
        active_depts = Department.objects.filter(is_active=True)
        
        controlled_dept = cast(forms.ModelChoiceField, self.fields["controlled_department"])
        dept = cast(forms.ModelChoiceField, self.fields["department"])
        
        controlled_dept.queryset = active_depts
        dept.queryset = active_depts

        # Labels en français
        self.fields["reference"].label = _("Référence de la recommandation")
        self.fields["mission_date"].label = _("Date de la mission")
        self.fields["mission_label"].label = _("Libellé de la mission")
        self.fields["controlled_department"].label = _("Direction contrôlée")
        self.fields["observations"].label = _("Observations")
        self.fields["anomalous_dossiers"].label = _("Dossiers en anomalies")
        self.fields["description"].label = _("Texte de la recommandation")
        self.fields["source"].label = _("Source")
        self.fields["priority"].label = _("Criticité")
        self.fields["department"].label = _("Direction concernée")
        self.fields["due_date"].label = _("Date de mise en œuvre")

        # Placeholder vide pour les selects
        controlled_dept.empty_label = _("— Sélectionner —")
        dept.empty_label = _("— Sélectionner —")

        source_field = cast(forms.ChoiceField, self.fields["source"])
        source_choices = list(source_field.choices)
        if source_choices and source_choices[0][0] in ('', None):
            source_choices[0] = ('', _("— Sélectionner une source —"))
        source_field.choices = source_choices

        priority_field = cast(forms.ChoiceField, self.fields["priority"])
        priority_choices = list(priority_field.choices)
        if priority_choices and priority_choices[0][0] in ('', None):
            priority_choices[0] = ('', _("— Sélectionner la criticité —"))
        priority_field.choices = priority_choices

    def clean_due_date(self):
        """Interdit les dates de mise en œuvre dans le passé (AC10)."""
        due_date = self.cleaned_data.get("due_date")
        if due_date and due_date < timezone.now().date():
            # Ne valider que si on crée ou qu'on modifie spécifiquement cette date
            if not self.instance.pk or due_date != self.instance.due_date:
                raise forms.ValidationError(
                    _("La date de mise en œuvre ne peut pas être dans le passé.")
                )
        return due_date


# ── Deliverable FormSet ───────────────────────────────────────────────


class DeliverableForm(forms.ModelForm):
    """Formulaire unitaire pour un livrable dans le formset."""

    class Meta:
        model = Deliverable
        fields = ["label"]
        widgets = {
            "label": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "Ex: Procédure KYC mise à jour",
            }),
        }


DeliverableFormSet = inlineformset_factory(
    Recommendation,
    Deliverable,
    form=DeliverableForm,
    fields=["label"],
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ── Formulaire d'Assignation (Story 2.5) ─────────────────────────────


class AssignDMForm(forms.Form):
    """
    Formulaire léger pour l'assignation d'une recommandation à un DM.

    Utilise forms.Form (pas ModelForm) car on ne modifie qu'un seul
    champ FK via le service layer, pas via un form.save().

    Le queryset est filtré dynamiquement par département dans __init__.
    """

    dm = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Surchargé dans __init__
        label=_("Directeur Métier"),
        widget=forms.Select(attrs={"class": _SELECT_CLASS}),
        empty_label=_("— Sélectionner un DM —"),
    )

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            from . import selectors

            self.fields["dm"].queryset = (
                selectors.get_available_dms_for_department(department=department)
            )
        else:
            self.fields["dm"].queryset = User.objects.none()


# ── Formulaire de Délégation (Story 3.2) ─────────────────────────────


class DelegateETPForm(forms.Form):
    """
    Formulaire pour la délégation d'une recommandation à un ETP
    ou la prise en charge DM Porteur (Story 3.2 / AC1, AC2).

    Utilise forms.Form (pas ModelForm) car la logique métier
    est orchestrée par le service layer.

    Le queryset ETP est filtré dynamiquement par département dans __init__.
    """

    ACTION_DELEGATE_ETP = "delegate_etp"
    ACTION_DM_PORTEUR = "dm_porteur"

    ACTION_CHOICES = [
        (ACTION_DELEGATE_ETP, _("Déléguer à un ETP")),
        (ACTION_DM_PORTEUR, _("Devenir DM Porteur")),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "sr-only peer"}),
        initial=ACTION_DELEGATE_ETP,
        label=_("Action"),
    )

    etp = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Surchargé dans __init__
        label=_("Employé Traitant"),
        widget=forms.Select(attrs={"class": _SELECT_CLASS}),
        empty_label=_("— Sélectionner un ETP —"),
        required=False,  # Non requis si action = dm_porteur
    )

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            from . import selectors

            self.fields["etp"].queryset = (
                selectors.get_available_etps_for_department(department=department)
            )
        else:
            self.fields["etp"].queryset = User.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        etp = cleaned_data.get("etp")

        if action == self.ACTION_DELEGATE_ETP and not etp:
            self.add_error(
                "etp",
                _("Veuillez sélectionner un ETP pour la délégation."),
            )

        return cleaned_data


# ── Formulaires de Soumission de Preuves (Story 3.3) ─────────────────


class EvidenceDraftCommentForm(forms.Form):
    """
    Validation du commentaire de résolution lors de la soumission finale.

    Le commentaire est sauvegardé en continu par autosave (HTMX debounce)
    via DraftSaveCommentView. Ce formulaire n'est utilisé que pour valider
    la présence du commentaire avant la transition FSM.

    Note : Les fichiers sont uploadés individuellement via DraftUploadFileView
    (Story 3.3 v2 — brouillons persistants) — pas de champ fichier ici.
    """

    comment = forms.CharField(
        label=_("Commentaire de résolution"),
        widget=forms.Textarea(attrs={
            "class": _TEXTAREA_CLASS,
            "rows": 4,
            "placeholder": _(
                "Décrivez les actions menées pour résoudre cette recommandation..."
            ),
        }),
        help_text=_("Expliquez les mesures prises pour remédier aux observations."),
    )

