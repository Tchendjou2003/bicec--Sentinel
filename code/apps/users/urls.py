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
    # ── Types d'unités organisationnelles (Story 3.7.b / Phase B) ──
    path(
        "admin/types-unites/",
        views.OrgUnitTypeListView.as_view(),
        name="org-unit-type-list",
    ),
    path(
        "admin/types-unites/create/",
        views.OrgUnitTypeCreateView.as_view(),
        name="org-unit-type-create",
    ),
    path(
        "admin/types-unites/<uuid:pk>/edit/",
        views.OrgUnitTypeEditView.as_view(),
        name="org-unit-type-edit",
    ),
    path(
        "admin/types-unites/<uuid:pk>/toggle/",
        views.OrgUnitTypeToggleView.as_view(),
        name="org-unit-type-toggle",
    ),
]

