"""
Users App — URL Configuration (Auth & Habilitation)
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "auth"

urlpatterns = [
    path(
        "login/",
        views.SentinelLoginView.as_view(),
        name="login",
    ),
    path(
        "pending/",
        views.PendingActivationView.as_view(),
        name="pending",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    # ── Habilitation Audit (Story 1.5 + 1.7) ──
    path(
        "habilitation/",
        views.HabilitationListView.as_view(),
        name="habilitation-list",
    ),
    path(
        "habilitation/<uuid:pk>/edit/",
        views.HabilitationEditView.as_view(),
        name="habilitation-edit",
    ),
    path(
        "habilitation/<uuid:pk>/toggle-admin/",
        views.HabilitationToggleAdminView.as_view(),
        name="habilitation-toggle-admin",
    ),
]

