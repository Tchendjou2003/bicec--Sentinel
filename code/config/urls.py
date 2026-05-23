"""
Sentinel — URL Configuration
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.users.urls")),
    path("audit/", include("apps.workflow.urls")),
    path(
        "",
        login_required(TemplateView.as_view(template_name="home.html")),
        name="home",
    ),
    path(
        "htmx-test/",
        TemplateView.as_view(template_name="partials/htmx_test.html"),
        name="htmx-test",
    ),
]

