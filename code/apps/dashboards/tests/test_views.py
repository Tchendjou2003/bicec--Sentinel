"""
Dashboards App — Tests Vues (Story 6.1a)

Vérifie :
    - 200 pour DM / ETP / DG / AUDIT
    - 403 pour ADMIN_IT (WorkflowAccessMixin)
    - 302 pour utilisateur anonyme → login
    - GET / redirige vers /tableau-de-bord/
    - Contexte DM contient les clés attendues (kpis, urgency_rows, etc.)
    - Isolation RBAC : DM dept B ne voit pas les KPIs du dept A
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import Recommendation, RecommendationSource
from apps.workflow.services import create_recommendation, assign_recommendation_to_dm


class DashboardViewTestMixin:
    """Fixtures partagées pour les tests de vues dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION",
            defaults={"name": "Direction", "level": 1},
        )
        cls.dept_a = Department.objects.create(
            name="Direction A View", code="DAV", type=cls.type_dir
        )
        cls.dept_b = Department.objects.create(
            name="Direction B View", code="DBV", type=cls.type_dir
        )

        cls.audit_user = User.objects.create_user(
            username="audit_vtest", password="TestPass123!", role=User.Role.AUDIT,
        )
        cls.dm_a = User.objects.create_user(
            username="dm_vtest_a", password="TestPass123!",
            role=User.Role.DM, department=cls.dept_a,
        )
        cls.dm_b = User.objects.create_user(
            username="dm_vtest_b", password="TestPass123!",
            role=User.Role.DM, department=cls.dept_b,
        )
        cls.etp_user = User.objects.create_user(
            username="etp_vtest", password="TestPass123!",
            role=User.Role.ETP, department=cls.dept_a,
        )
        cls.dg_user = User.objects.create_user(
            username="dg_vtest", password="TestPass123!", role=User.Role.DG,
        )
        cls.admin_user = User.objects.create_user(
            username="admin_vtest", password="TestPass123!", role=User.Role.ADMIN,
        )

        cls.source, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )
        cls.dashboard_url = reverse("dashboards:home")

    def _create_reco_for_dept(self, dept, dm_user=None):
        import uuid
        reco = create_recommendation(
            data={
                "reference": f"VT-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission view test",
                "controlled_department": dept,
                "observations": "Obs",
                "anomalous_dossiers": "",
                "description": "Desc",
                "source": self.source,
                "priority": Recommendation.Priority.MOYENNE,
                "department": dept,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable"],
            performed_by=self.audit_user,
        )
        if dm_user:
            assign_recommendation_to_dm(
                recommendation=reco, dm=dm_user, performed_by=self.audit_user
            )
        return reco


class DashboardViewAccessTest(DashboardViewTestMixin, TestCase):
    """Tests d'accès à la vue dashboard (AC1)."""

    def test_anonymous_redirects_to_login(self):
        """Utilisateur non connecté → 302 vers /auth/login/."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])

    def test_dm_gets_200(self):
        """Un DM connecté obtient 200 sur /tableau-de-bord/."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_etp_gets_200(self):
        """Un ETP connecté obtient 200 sur /tableau-de-bord/."""
        self.client.force_login(self.etp_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_dg_gets_200(self):
        """Un DG connecté obtient 200 sur /tableau-de-bord/."""
        self.client.force_login(self.dg_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_audit_gets_200(self):
        """Un Audit connecté obtient 200 sur /tableau-de-bord/."""
        self.client.force_login(self.audit_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_admin_gets_403(self):
        """Un ADMIN_IT reçoit 403 (WorkflowAccessMixin)."""
        self.client.force_login(self.admin_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 403)


class DashboardHomeRedirectTest(DashboardViewTestMixin, TestCase):
    """Tests de la redirection home (AC2)."""

    def test_home_redirects_to_dashboard(self):
        """GET / → 302 vers /tableau-de-bord/."""
        self.client.force_login(self.dm_a)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("tableau-de-bord", response["Location"])


class DashboardDmContextTest(DashboardViewTestMixin, TestCase):
    """Tests du contexte du dashboard DM (AC3, AC4, AC5, AC6)."""

    def test_dm_context_has_kpis(self):
        """Le contexte DM contient 'kpis'."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertIn("kpis", response.context)

    def test_dm_context_has_urgency_rows(self):
        """Le contexte DM contient 'urgency_rows'."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertIn("urgency_rows", response.context)

    def test_dm_context_has_pending_validation(self):
        """Le contexte DM contient 'pending_validation'."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertIn("pending_validation", response.context)

    def test_dm_context_has_donut_data(self):
        """Le contexte DM contient 'donut_data_json' (string JSON)."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertIn("donut_data_json", response.context)
        import json
        data = json.loads(response.context["donut_data_json"])
        self.assertIn("labels", data)
        self.assertIn("values", data)

    def test_dm_uses_dm_dashboard_template(self):
        """Le DM obtient le template dashboards/dm_dashboard.html."""
        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        self.assertTemplateUsed(response, "dashboards/dm_dashboard.html")

    def test_etp_uses_etp_dashboard_template(self):
        """L'ETP obtient le template dashboards/etp_dashboard.html."""
        self.client.force_login(self.etp_user)
        response = self.client.get(self.dashboard_url)
        self.assertTemplateUsed(response, "dashboards/etp_dashboard.html")


class DashboardRbacIsolationTest(DashboardViewTestMixin, TestCase):
    """Tests d'isolation RBAC inter-département (AC9)."""

    def test_dm_a_cannot_see_dept_b_kpis(self):
        """Le DM A ne voit pas les recos du département B dans ses KPIs."""
        # Créer 2 recos dept B
        self._create_reco_for_dept(self.dept_b, dm_user=self.dm_b)
        self._create_reco_for_dept(self.dept_b, dm_user=self.dm_b)
        # Créer 1 reco dept A
        self._create_reco_for_dept(self.dept_a, dm_user=self.dm_a)

        self.client.force_login(self.dm_a)
        response = self.client.get(self.dashboard_url)
        kpis = response.context["kpis"]
        # dm_a ne doit voir que la 1 reco de dept A
        self.assertEqual(kpis["total_actives"], 1)

    def test_dm_b_cannot_see_dept_a_kpis(self):
        """Le DM B ne voit pas les recos du département A dans ses KPIs."""
        self._create_reco_for_dept(self.dept_a, dm_user=self.dm_a)
        self._create_reco_for_dept(self.dept_b, dm_user=self.dm_b)

        self.client.force_login(self.dm_b)
        response = self.client.get(self.dashboard_url)
        kpis = response.context["kpis"]
        self.assertEqual(kpis["total_actives"], 1)


class DashboardDgContextTest(DashboardViewTestMixin, TestCase):
    """Tests du contexte du dashboard DG (Story 6.1b)."""

    def test_dg_uses_dg_dashboard_template(self):
        """Le DG obtient le template dashboards/dg_dashboard.html."""
        self.client.force_login(self.dg_user)
        response = self.client.get(self.dashboard_url)
        self.assertTemplateUsed(response, "dashboards/dg_dashboard.html")

    def test_dg_context_has_keys(self):
        """Le contexte DG contient kpis, dept_breakdown, stacked_bar_json, my_recos."""
        self.client.force_login(self.dg_user)
        response = self.client.get(self.dashboard_url)
        for key in ("kpis", "dept_breakdown", "stacked_bar_json", "my_recos"):
            self.assertIn(key, response.context)

    def test_dg_sees_all_departments(self):
        """Les KPIs DG agrègent toutes les directions (vue globale banque)."""
        self._create_reco_for_dept(self.dept_a, dm_user=self.dm_a)
        self._create_reco_for_dept(self.dept_b, dm_user=self.dm_b)

        self.client.force_login(self.dg_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.context["kpis"]["total_actives"], 2)


class DashboardAuditContextTest(DashboardViewTestMixin, TestCase):
    """Tests du contexte du dashboard Audit (Story 6.1c)."""

    def test_audit_uses_audit_dashboard_template(self):
        """L'Audit obtient le template dashboards/audit_dashboard.html."""
        self.client.force_login(self.audit_user)
        response = self.client.get(self.dashboard_url)
        self.assertTemplateUsed(response, "dashboards/audit_dashboard.html")

    def test_audit_context_has_queues(self):
        """Le contexte Audit contient les 3 files + breakdown + stacked_bar_json."""
        self.client.force_login(self.audit_user)
        response = self.client.get(self.dashboard_url)
        for key in (
            "kpis", "pending_review", "pending_review_count",
            "pending_extensions", "pending_extensions_count",
            "draft_unassigned", "draft_unassigned_count",
            "dept_breakdown", "stacked_bar_json",
        ):
            self.assertIn(key, response.context)

    def test_audit_context_no_perf_metrics_key(self):
        """La Section 5 lit kpis directement — pas de clé perf_metrics."""
        self.client.force_login(self.audit_user)
        response = self.client.get(self.dashboard_url)
        self.assertNotIn("perf_metrics", response.context)
