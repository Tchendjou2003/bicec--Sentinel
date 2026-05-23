"""
Workflow App — URLs

Routes pour la gestion des recommandations d'audit.
Préfixe : /audit/ (défini dans config/urls.py)

Spécifications couvertes :
    - AC1 : /audit/recommandations/create/
    - AC2 : /audit/recommandations/
    - AC8 : /audit/recommandations/<uuid>/
    - AC5 : /audit/recommandations/<uuid>/delete/
    - AC3 : /audit/recommandations/<uuid>/assign/ (Story 2.5)
"""
from django.urls import path

from . import views

app_name = "workflow"

urlpatterns = [
    path(
        "recommandations/",
        views.RecommendationListView.as_view(),
        name="recommendation-list",
    ),
    path(
        "recommandations/create/",
        views.RecommendationCreateView.as_view(),
        name="recommendation-create",
    ),
    path(
        "recommandations/<uuid:pk>/update/",
        views.RecommendationUpdateView.as_view(),
        name="recommendation-update",
    ),
    path(
        "recommandations/<uuid:pk>/",
        views.RecommendationDetailView.as_view(),
        name="recommendation-detail",
    ),
    path(
        "recommandations/<uuid:pk>/delete/",
        views.RecommendationDeleteView.as_view(),
        name="recommendation-delete",
    ),
    path(
        "recommandations/<uuid:pk>/assign/",
        views.RecommendationAssignView.as_view(),
        name="recommendation-assign",
    ),
]
