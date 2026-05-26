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

from apps.users import views as user_views
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
    path(
        "recommandations/<uuid:pk>/delegate/",
        views.RecommendationDelegateView.as_view(),
        name="recommendation-delegate",
    ),
    path(
        "recommandations/<uuid:pk>/submit-evidence/",
        views.RecommendationSubmitEvidenceView.as_view(),
        name="recommendation-submit-evidence",
    ),
    # ── Historique complet — slide-over HTMX ──
    path(
        "recommandations/<uuid:pk>/audit-log/",
        views.RecommendationAuditLogView.as_view(),
        name="recommendation-audit-log",
    ),
    # ── Rejet de preuves par le DM (Story 3.4) ──
    path(
        "recommandations/<uuid:pk>/submissions/<uuid:submission_id>/reject/",
        views.EvidenceRejectView.as_view(),
        name="evidence-reject",
    ),
    # ── Validation DM → Audit (Story 3.5) ──
    path(
        "recommandations/<uuid:pk>/submissions/<uuid:submission_id>/approve/",
        views.EvidenceDMApprovalView.as_view(),
        name="evidence-approve",
    ),
    # ── Endpoints HTMX pour brouillons (Story 3.3 v2) ──
    path(
        "recommandations/<uuid:pk>/draft/upload/",
        views.DraftUploadFileView.as_view(),
        name="draft-upload",
    ),
    path(
        "recommandations/<uuid:pk>/draft/file/<uuid:file_id>/delete/",
        views.DraftDeleteFileView.as_view(),
        name="draft-delete-file",
    ),
    path(
        "recommandations/<uuid:pk>/draft/comment/",
        views.DraftSaveCommentView.as_view(),
        name="draft-save-comment",
    ),
    path(
        "recommandations/<uuid:pk>/draft/deliverable/<uuid:del_id>/toggle/",
        views.DraftToggleDeliverableView.as_view(),
        name="draft-toggle-deliverable",
    ),
    path(
        "recommandations/<uuid:pk>/evidence/<uuid:file_id>/download/",
        views.EvidenceFileDownloadView.as_view(),
        name="evidence-download",
    ),
    # ── Demandes de Report d'Échéance (Story 3.6 — FR13, FR14, FR34) ──
    path(
        "recommandations/<uuid:pk>/extension/request/",
        views.ExtensionRequestView.as_view(),
        name="extension-request",
    ),
    path(
        "recommandations/<uuid:pk>/extension/<uuid:ext_id>/approve/",
        views.ExtensionApproveView.as_view(),
        name="extension-approve",
    ),
    path(
        "recommandations/<uuid:pk>/extension/<uuid:ext_id>/reject/",
        views.ExtensionRejectView.as_view(),
        name="extension-reject",
    ),
    # ── Habilitation Audit (Story 1.5 + 1.7) ──
    path(
        "habilitation/",
        user_views.HabilitationListView.as_view(),
        name="habilitation-list",
    ),
    path(
        "habilitation/<uuid:pk>/edit/",
        user_views.HabilitationEditView.as_view(),
        name="habilitation-edit",
    ),
    path(
        "habilitation/<uuid:pk>/toggle-admin/",
        user_views.HabilitationToggleAdminView.as_view(),
        name="habilitation-toggle-admin",
    ),
]
