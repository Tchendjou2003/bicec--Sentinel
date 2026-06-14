"""
Sentinel — URL Configuration
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.users.urls")),
    path("audit/", include("apps.workflow.urls")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    path("tableau-de-bord/", include("apps.dashboards.urls", namespace="dashboards")),
    # / → redirige vers le dashboard (Story 6.1a)
    path(
        "",
        login_required(RedirectView.as_view(pattern_name="dashboards:home", permanent=False)),
        name="home",
    ),
    path(
        "htmx-test/",
        login_required(RedirectView.as_view(pattern_name="dashboards:home", permanent=False)),
        name="htmx-test",
    ),
]

