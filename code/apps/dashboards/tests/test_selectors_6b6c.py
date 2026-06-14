"""
Dashboards App — Tests Sélecteurs DG + Audit (Stories 6.1b / 6.1c)

Vérifie :
    - DG : KPIs banque entière, breakdown par direction, my_recos scopé
    - Audit : KPIs globaux, counts des 3 files d'action, breakdown
"""
import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import ExtensionRequest, Recommendation, RecommendationSource
from apps.workflow.services import assign_recommendation_to_dm, create_recommendation

from apps.dashboards.selectors import (
    _get_stacked_bar_json,
    get_audit_department_breakdown,
    get_audit_draft_unassigned_count,
    get_audit_kpis,
    get_audit_pending_extensions_count,
    get_audit_pending_review_count,
    get_dg_department_breakdown,
    get_dg_kpis,
    get_dg_my_recos_with_aging,
)


class DashboardDgAuditTestMixin:
    """Fixtures partagées — 2 directions racines distinctes."""

    @classmethod
    def setUpTestData(cls):
        cls.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION",
            defaults={"name": "Direction", "level": 1},
        )
        cls.dir_a = Department.objects.create(name="Direction Alpha", code="DALPHA", type=cls.type_dir)
        cls.dir_b = Department.objects.create(name="Direction Beta", code="DBETA", type=cls.type_dir)

        cls.audit_user = User.objects.create_user(
            username="audit_6bc", password="TestPass123!", role=User.Role.AUDIT,
        )
        cls.dm_a = User.objects.create_user(
            username="dm_6bc_a", password="TestPass123!", role=User.Role.DM, department=cls.dir_a,
        )
        cls.dm_b = User.objects.create_user(
            username="dm_6bc_b", password="TestPass123!", role=User.Role.DM, department=cls.dir_b,
        )
        cls.dg_user = User.objects.create_user(
            username="dg_6bc", password="TestPass123!", role=User.Role.DG,
        )
        cls.source, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def _create_reco(self, dept, *, assign_dm=None, status=None, priority=None):
        """Crée une reco. Optionnellement l'assigne à un DM et force un statut."""
        priority = priority or Recommendation.Priority.MOYENNE
        reco = create_recommendation(
            data={
                "reference": f"T6-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission 6bc",
                "controlled_department": dept,
                "observations": "Obs",
                "anomalous_dossiers": "",
                "description": "Desc",
                "source": self.source,
                "priority": priority,
                "department": dept,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable"],
            performed_by=self.audit_user,
        )
        if assign_dm:
            assign_recommendation_to_dm(
                recommendation=reco, dm=assign_dm, performed_by=self.audit_user
            )
        if status:
            Recommendation.objects.filter(pk=reco.pk).update(status=status)
            reco = Recommendation.objects.get(pk=reco.pk)
        return reco


class GetDgSelectorsTest(DashboardDgAuditTestMixin, TestCase):
    """Tests sélecteurs DG (Story 6.1b)."""

    def test_dg_kpis_sees_all_departments(self):
        """Les KPIs DG agrègent les recos de TOUTES les directions."""
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        self._create_reco(self.dir_b, assign_dm=self.dm_b)

        kpis = get_dg_kpis()
        self.assertEqual(kpis["total_actives"], 3)

    def test_dg_kpis_excludes_drafts(self):
        """Les brouillons DRAFT ne comptent pas dans les KPIs DG."""
        self._create_reco(self.dir_a)  # reste DRAFT (pas assigné)
        self._create_reco(self.dir_a, assign_dm=self.dm_a)  # ASSIGNED

        kpis = get_dg_kpis()
        self.assertEqual(kpis["total_actives"], 1)

    def test_dg_department_breakdown_structure(self):
        """Chaque dict du breakdown a les clés attendues."""
        self._create_reco(self.dir_a, assign_dm=self.dm_a)

        breakdown = get_dg_department_breakdown()
        self.assertGreaterEqual(len(breakdown), 1)
        expected_keys = {
            "department", "total", "actives", "overdue", "overdue_pct",
            "closed", "taux_cloture", "critique_open", "risk_level",
            "assigned", "in_progress", "pending_dm", "pending_audit",
        }
        for row in breakdown:
            self.assertTrue(expected_keys.issubset(row.keys()))

    def test_dg_breakdown_rolls_up_subdepartments(self):
        """Une reco d'une sous-direction remonte sous sa direction racine (Fix #2)."""
        # Sous-direction rattachée à dir_a
        sous_dir = Department.objects.create(
            name="Sous-Direction Alpha", code="SDALPHA", type=self.type_dir, parent=self.dir_a,
        )
        dm_sub = User.objects.create_user(
            username="dm_sub_a", password="TestPass123!", role=User.Role.DM, department=sous_dir,
        )
        # 1 reco directement sur dir_a, 1 reco sur la sous-direction
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        self._create_reco(sous_dir, assign_dm=dm_sub)

        breakdown = get_dg_department_breakdown()
        row_a = next(r for r in breakdown if r["department"].pk == self.dir_a.pk)
        # Les 2 recos (racine + descendant) sont agrégées sous la racine
        self.assertEqual(row_a["total"], 2)
        # La sous-direction n'apparaît PAS comme ligne racine séparée
        root_pks = {r["department"].pk for r in breakdown}
        self.assertNotIn(sous_dir.pk, root_pks)

    def test_dg_my_recos_scoped(self):
        """my_recos ne contient QUE les recos assignées à la DG elle-même."""
        # Reco assignée à un DM lambda (pas la DG)
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        # Reco assignée à la DG (DG Porteur) — assignation directe car le service
        # assign_recommendation_to_dm exige le rôle DM ; le champ assigned_dm
        # accepte un DG porteur.
        reco_dg = self._create_reco(self.dir_b, assign_dm=self.dm_b)
        Recommendation.objects.filter(pk=reco_dg.pk).update(assigned_dm=self.dg_user)

        rows = get_dg_my_recos_with_aging(user=self.dg_user)
        pks = [r["rec"].pk for r in rows]
        self.assertIn(reco_dg.pk, pks)
        self.assertEqual(len(rows), 1)

    def test_stacked_bar_json_valid(self):
        """_get_stacked_bar_json retourne un JSON parsable avec labels + datasets."""
        import json
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        breakdown = get_dg_department_breakdown()
        data = json.loads(_get_stacked_bar_json(breakdown))
        self.assertIn("labels", data)
        self.assertIn("datasets", data)
        self.assertEqual(len(data["datasets"]), 6)  # 6 segments de statut


class GetAuditSelectorsTest(DashboardDgAuditTestMixin, TestCase):
    """Tests sélecteurs Audit (Story 6.1c)."""

    def test_audit_kpis_global_scope(self):
        """L'Audit voit toutes les recos (toutes directions)."""
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        self._create_reco(self.dir_b, assign_dm=self.dm_b)

        kpis = get_audit_kpis(user=self.audit_user)
        self.assertEqual(kpis["total_actives"], 2)

    def test_audit_kpis_excludes_drafts(self):
        """Les brouillons DRAFT ne gonflent pas total_actives ni le breakdown Audit."""
        # 1 brouillon (non assigné → reste DRAFT) + 1 reco assignée
        self._create_reco(self.dir_a)  # DRAFT
        self._create_reco(self.dir_a, assign_dm=self.dm_a)  # ASSIGNED

        kpis = get_audit_kpis(user=self.audit_user)
        self.assertEqual(kpis["total_actives"], 1)  # le DRAFT est exclu

        breakdown = get_audit_department_breakdown(user=self.audit_user)
        row_a = next(r for r in breakdown if r["department"].pk == self.dir_a.pk)
        self.assertEqual(row_a["total"], 1)  # le DRAFT n'est pas compté

    def test_audit_kpis_has_perf_fields(self):
        """Le dict KPIs contient les champs Section 5 (perf)."""
        kpis = get_audit_kpis(user=self.audit_user)
        for key in ("taux_overdue", "recos_crees_ce_mois", "recos_closes_ce_mois"):
            self.assertIn(key, kpis)

    def test_audit_pending_review_count(self):
        """Count des recos en PENDING_AUDIT_REVIEW."""
        self._create_reco(
            self.dir_a, assign_dm=self.dm_a,
            status=Recommendation.Status.PENDING_AUDIT_REVIEW,
        )
        self._create_reco(
            self.dir_b, assign_dm=self.dm_b,
            status=Recommendation.Status.PENDING_AUDIT_REVIEW,
        )
        self._create_reco(self.dir_a, assign_dm=self.dm_a)  # ASSIGNED, ne compte pas

        count = get_audit_pending_review_count(user=self.audit_user)
        self.assertEqual(count, 2)

    def test_audit_draft_count(self):
        """Count des brouillons DRAFT non assignés."""
        self._create_reco(self.dir_a)  # DRAFT
        self._create_reco(self.dir_a)  # DRAFT
        self._create_reco(self.dir_b, assign_dm=self.dm_b)  # ASSIGNED

        count = get_audit_draft_unassigned_count(user=self.audit_user)
        self.assertEqual(count, 2)

    def test_audit_pending_extensions_count(self):
        """Count des demandes de report PENDING."""
        reco = self._create_reco(self.dir_a, assign_dm=self.dm_a)
        ExtensionRequest.objects.create(
            recommendation=reco,
            requested_by=self.dm_a,
            requested_date=timezone.now().date() + timedelta(days=60),
            reason="Besoin de délai supplémentaire",
            status=ExtensionRequest.Status.PENDING,
        )

        count = get_audit_pending_extensions_count()
        self.assertEqual(count, 1)

    def test_audit_department_breakdown_structure(self):
        """Le breakdown Audit a la même structure que DG."""
        self._create_reco(self.dir_a, assign_dm=self.dm_a)
        breakdown = get_audit_department_breakdown(user=self.audit_user)
        self.assertGreaterEqual(len(breakdown), 1)
        self.assertIn("risk_level", breakdown[0])
