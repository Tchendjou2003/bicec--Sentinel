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
    # ── Espace Externe (Story 1.3) ──
    path(
        "external/dashboard/",
        views.ExternalDashboardView.as_view(),
        name="external-dashboard",
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
    # ── Administration IT (Story 1.4) ──
    path(
        "admin/dashboard/",
        views.AdminDashboardView.as_view(),
        name="admin-dashboard",
    ),
    path(
        "admin/organigramme/",
        views.OrganigrammeListView.as_view(),
        name="organigramme-list",
    ),
    path(
        "admin/organigramme/search/",
        views.DepartmentSearchView.as_view(),
        name="department-search",
    ),
    path(
        "admin/organigramme/create/",
        views.DepartmentCreateView.as_view(),
        name="department-create",
    ),
    path(
        "admin/organigramme/<uuid:pk>/edit/",
        views.DepartmentEditView.as_view(),
        name="department-edit",
    ),
    path(
        "admin/organigramme/<uuid:pk>/delete/",
        views.DepartmentDeleteView.as_view(),
        name="department-delete",
    ),
    path(
        "admin/utilisateurs/",
        views.ITUserListView.as_view(),
        name="admin-user-list",
    ),
    path(
        "admin/utilisateurs/create/",
        views.ITUserCreateView.as_view(),
        name="admin-user-create",
    ),
]

