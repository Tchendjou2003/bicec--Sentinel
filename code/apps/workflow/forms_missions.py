from django import forms
from django.utils.translation import gettext_lazy as _

from apps.users.models import ExternalMission, User
from apps.workflow.models import Recommendation, RecommendationSource

# Style Tailwind partagé avec apps/workflow/forms.py
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


class ExternalMissionForm(forms.ModelForm):
    """
    Formulaire HTMX de création/édition d'une mission d'audit externe.
    
    Affiche les informations générales de la mission (nom, type, organisation)
    ainsi que les relations (auditeurs et recommandations).
    """

    class Meta:
        model = ExternalMission
        fields = [
            "name",
            "organisation",
            "scope_description",
            "start_date",
            "end_date",
            "auditors",
            "recommendations",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": _INPUT_CLASS,
                "placeholder": "Ex: Contrôle COBAC 2026",
            }),
            "organisation": forms.Select(attrs={
                "class": _SELECT_CLASS,
            }),
            "scope_description": forms.Textarea(attrs={
                "class": _TEXTAREA_CLASS,
                "rows": 3,
                "placeholder": "Description du périmètre d'intervention...",
            }),
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": _INPUT_CLASS,
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": _INPUT_CLASS,
                    "type": "date",
                }
            ),
            "auditors": forms.SelectMultiple(attrs={
                "class": _SELECT_CLASS + " js-tomselect",
                "data-placeholder": "Rechercher des auditeurs externes...",
            }),
            "recommendations": forms.SelectMultiple(attrs={
                "class": _SELECT_CLASS + " js-tomselect",
                "data-placeholder": "Rechercher des recommandations clôturées...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organisation"].queryset = RecommendationSource.objects.filter(
            is_external=True, is_active=True
        ).order_by("label")
        self.fields["auditors"].queryset = User.objects.filter(
            role=User.Role.EXT,
            is_active=True
        ).order_by("username")
        self.fields["recommendations"].queryset = Recommendation.objects.filter(
            status=Recommendation.Status.CLOSED_RESOLVED
        ).order_by("-reference")

        for f in ["organisation", "end_date", "scope_description", "auditors", "recommendations"]:
            self.fields[f].required = True
