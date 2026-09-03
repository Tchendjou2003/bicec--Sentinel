"""Notifications App — URLs (Story 4.0)"""
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("dropdown/", views.NotificationDropdownView.as_view(), name="dropdown"),
    path("<uuid:pk>/mark-read/", views.NotificationMarkReadView.as_view(), name="mark-read"),
    path("<uuid:pk>/delete/", views.NotificationDeleteView.as_view(), name="delete"),
    path("mark-all-read/", views.NotificationMarkAllReadView.as_view(), name="mark-all-read"),
]
