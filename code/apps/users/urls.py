"""
Users App — URL Configuration (Auth)
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
]
