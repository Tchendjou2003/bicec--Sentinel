"""
Dashboards App — Views

Vue adaptative unique :
    /tableau-de-bord/  →  DashboardView  →  template selon request.user.role

Dispatche le template et le contexte selon le rôle sans duplicer la logique RBAC
(celle-ci est encapsulée dans les sélecteurs du module selectors.py).

Stories couvertes : 6.1a (DM + ETP), 6.1b (DG — TODO), 6.1c (Audit — TODO)
"""
import json

from django.views.generic import TemplateView

from apps.users.mixins import WorkflowAccessMixin

from . import selectors


class DashboardView(WorkflowAccessMixin, TemplateView):
    """
    Vue tableau de bord adaptative — un seul URL, un template par rôle.

    Chaque rôle obtient une vue taillée à ses besoins :
        DM    → 360° direction (KPIs + donut + file d'attente + aging)
        ETP   → vue légère (KPIs + mes recos)
        DG    → supervision banque entière (TODO Story 6.1b)
        AUDIT → contrôle global + files d'action (TODO Story 6.1c)

    RBAC : WorkflowAccessMixin bloque ADMIN_IT et EXT (403).
    """

    def get_template_names(self) -> list[str]:
        from apps.users.models import User

        role = self.request.user.role
        mapping = {
            User.Role.DM: "dashboards/dm_dashboard.html",
            User.Role.ETP: "dashboards/etp_dashboard.html",
            User.Role.DG: "dashboards/dg_dashboard.html",
            User.Role.AUDIT: "dashboards/audit_dashboard.html",
        }
        # Fallback sécurisé — WorkflowAccessMixin garantit qu'on n'arrive pas
        # ici avec un rôle ADMIN/EXT, mais le superuser peut passer
        return [mapping.get(role, "dashboards/audit_dashboard.html")]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        from apps.users.models import User

        ctx.update(self._common_context(user))

        role = user.role
        if role == User.Role.DM:
            ctx.update(self._dm_context(user))
        elif role == User.Role.ETP:
            ctx.update(self._etp_context(user))
        elif role == User.Role.DG:
            ctx.update(self._dg_context(user))
        elif role == User.Role.AUDIT or user.is_superuser:
            ctx.update(self._audit_context(user))

        return ctx

    # ──────────────────────────────────────────────────────────────────────
    # Contextes partagés
    # ──────────────────────────────────────────────────────────────────────

    def _common_context(self, user) -> dict:
        """Variables communes à tous les templates (topbar, sidebar active_route)."""
        from apps.users.models import User

        subtitles = {
            User.Role.DM: (
                f"Périmètre — {user.department.name}" if user.department else "Vue département"
            ),
            User.Role.ETP: "Mes recommandations déléguées",
            User.Role.DG: "Vision consolidée — toute la banque",
            User.Role.AUDIT: "Vue consolidée — périmètre complet",
        }
        return {
            "topbar_title": "Tableau de Bord",
            "topbar_subtitle": subtitles.get(user.role, "Supervision"),
            "active_route": "dashboard",
        }

    # ──────────────────────────────────────────────────────────────────────
    # Contexte DM — Story 6.1a
    # ──────────────────────────────────────────────────────────────────────

    def _dm_context(self, user) -> dict:
        """Contexte complet pour le dashboard DM (Story 6.1a)."""
        kpis = selectors.get_dm_kpis(user=user)
        donut_data = selectors.get_dm_donut_data(user=user)
        # Évaluation en list : évite la récursion du test client Django lors du
        # shallow-copy du contexte (QuerySet lazy → BaseContext.__copy__ récursif).
        pending_validation = list(selectors.get_dm_pending_validation(user=user))
        urgency_rows = selectors.get_dm_urgency_rows(user=user)

        return {
            "kpis": kpis,
            "donut_data_json": json.dumps(donut_data),
            "pending_validation": pending_validation,
            "urgency_rows": urgency_rows,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Contexte ETP — Story 6.1a
    # ──────────────────────────────────────────────────────────────────────

    def _etp_context(self, user) -> dict:
        """Contexte pour le dashboard ETP (vue légère — Story 6.1a)."""
        return {
            "kpis": selectors.get_etp_kpis(user=user),
            "etp_rows": selectors.get_etp_rows(user=user),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Contexte DG — Story 6.1b (vision toute la banque)
    # ──────────────────────────────────────────────────────────────────────

    def _dg_context(self, user) -> dict:
        """Contexte du dashboard DG — KPIs macro, heatmap, barres, mes recos."""
        # breakdown calculé une seule fois, réutilisé pour heatmap ET barres
        dept_breakdown = selectors.get_dg_department_breakdown()
        return {
            "kpis": selectors.get_dg_kpis(),
            "dept_breakdown": dept_breakdown,
            "stacked_bar_json": selectors._get_stacked_bar_json(dept_breakdown),
            "my_recos": selectors.get_dg_my_recos_with_aging(user=user),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Contexte Audit — Story 6.1c (contrôle global + files d'action)
    # ──────────────────────────────────────────────────────────────────────

    def _audit_context(self, user) -> dict:
        """Contexte du dashboard Audit — KPIs, 3 files d'action, heatmap, barres."""
        # breakdown calculé une seule fois, réutilisé pour heatmap ET barres
        dept_breakdown = selectors.get_audit_department_breakdown(user=user)
        return {
            "kpis": selectors.get_audit_kpis(user=user),
            # File 1 — preuves à examiner
            "pending_review": selectors.get_audit_pending_review(user=user),
            "pending_review_count": selectors.get_audit_pending_review_count(user=user),
            # File 2 — reports à décider (sans user)
            "pending_extensions": selectors.get_audit_pending_extensions(),
            "pending_extensions_count": selectors.get_audit_pending_extensions_count(),
            # File 3 — brouillons à assigner
            "draft_unassigned": selectors.get_audit_draft_unassigned(user=user),
            "draft_unassigned_count": selectors.get_audit_draft_unassigned_count(user=user),
            # Graphiques
            "dept_breakdown": dept_breakdown,
            "stacked_bar_json": selectors._get_stacked_bar_json(dept_breakdown),
        }
