from django.apps import AppConfig


class UiConfig(AppConfig):
    """App utilitaire UI / Design System — pas de modèle, uniquement des templatetags."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ui"
    verbose_name = "UI / Design System"
