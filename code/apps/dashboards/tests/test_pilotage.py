"""
Dashboards App — Tests Sprint A : socle métriques KPI/KRI (Story 6.9)

Vérifie :
    - Helpers analytiques (_aging_buckets, _on_time_rates, _first_pass_rates,
      _regulatory_stock_weighted/_aging_index, _lead_time_stats)
    - Idempotence de capture_daily_snapshot (update_or_create)
    - Cohérence des snapshots banque + direction
"""

import uuid
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import (
    EvidenceSubmission,
    Recommendation,
    RecommendationSource,
)
from apps.workflow.services import assign_recommendation_to_dm, create_recommendation

from apps.dashboards import selectors
from apps.dashboards.models import MetricsSnapshot
from apps.dashboards.services import capture_daily_snapshot


# ---------------------------------------------------------------------------
# Fixtures partagées
# ---------------------------------------------------------------------------


class PilotageTestMixin:
    """
    Arbre organique minimal pour les tests de pilotage :
        DG (apex, type DG)
        └─ Dir Opérations  (groupe 1)
        └─ Dir Risques     (groupe 2)
    + source externe (COBAC) et interne
    """

    @classmethod
    def setUpTestData(cls):
        cls.type_dg, _ = OrgUnitType.objects.get_or_create(
            code="DG", defaults={"name": "Direction Générale", "level": 0}
        )
        cls.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIR", defaults={"name": "Direction", "level": 1}
        )

        cls.dg_dept = Department.objects.create(
            name="Direction Générale", code="DG", type=cls.type_dg
        )
        cls.dir_ops = Department.objects.create(
            name="Dir Opérations", code="OPS", type=cls.type_dir, parent=cls.dg_dept
        )
        cls.dir_risk = Department.objects.create(
            name="Dir Risques", code="RISK", type=cls.type_dir, parent=cls.dg_dept
        )

        cls.audit_user = User.objects.create_user(
            username="audit_pil", password="TestPass123!", role=User.Role.AUDIT
        )
        cls.dm_ops = User.objects.create_user(
            username="dm_ops_pil",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.dir_ops,
        )
        cls.dm_risk = User.objects.create_user(
            username="dm_risk_pil",
            password="TestPass123!",
            role=User.Role.DM,
            department=cls.dir_risk,
        )

        cls.src_external, _ = RecommendationSource.objects.get_or_create(
            code="COBAC", defaults={"label": "COBAC", "is_external": True}
        )
        cls.src_internal, _ = RecommendationSource.objects.get_or_create(
            code="INT_PIL",
            defaults={"label": "Audit interne PIL", "is_external": False},
        )

    def _create_reco(
        self,
        dept,
        *,
        source=None,
        priority=Recommendation.Priority.MOYENNE,
        due_date_offset=30,
        original_due_date=None,
        assign_dm=None,
        status=None,
        overdue=False,
        closed_at=None,
    ):
        today = timezone.now().date()
        dd = today + timedelta(days=due_date_offset)
        reco = create_recommendation(
            data={
                "reference": f"PIL-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": today,
                "mission_label": "Mission PIL",
                "controlled_department": dept,
                "observations": "Obs",
                "anomalous_dossiers": "",
                "description": "Desc",
                "source": source or self.src_internal,
                "priority": priority,
                "department": dept,
                "due_date": dd,
            },
            deliverables_data=["Livrable"],
            performed_by=self.audit_user,
        )
        updates = {}
        if original_due_date:
            updates["original_due_date"] = original_due_date
        if overdue:
            updates["is_overdue"] = True
        if status:
            updates["status"] = status
        if closed_at:
            updates["closed_at"] = closed_at
            updates.setdefault("status", Recommendation.Status.CLOSED_RESOLVED)
        # assign_dm d'abord (transition FSM), puis on-écrase avec updates
        # (y compris is_overdue / status forcés pour les tests)
        if assign_dm:
            assign_recommendation_to_dm(
                recommendation=reco, dm=assign_dm, performed_by=self.audit_user
            )
            reco = Recommendation.objects.get(pk=reco.pk)
        if updates:
            Recommendation.objects.filter(pk=reco.pk).update(**updates)
            reco = Recommendation.objects.get(pk=reco.pk)
        return reco


# ---------------------------------------------------------------------------
# Helper : _aging_buckets
# ---------------------------------------------------------------------------


class AgingBucketsTest(PilotageTestMixin, TestCase):
    def test_buckets_correctly_distributed(self):
        """Trois recos en retard se répartissent dans les bons buckets."""
        today = timezone.localdate()
        self._create_reco(
            self.dir_ops,
            overdue=True,
            status=Recommendation.Status.IN_PROGRESS,
            original_due_date=today - timedelta(days=10),
        )
        self._create_reco(
            self.dir_ops,
            overdue=True,
            status=Recommendation.Status.IN_PROGRESS,
            original_due_date=today - timedelta(days=60),
        )
        self._create_reco(
            self.dir_ops,
            overdue=True,
            status=Recommendation.Status.IN_PROGRESS,
            original_due_date=today - timedelta(days=120),
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        buckets = selectors._aging_buckets(qs)

        self.assertEqual(buckets["overdue_0_30"], 1)
        self.assertEqual(buckets["overdue_30_90"], 1)
        self.assertEqual(buckets["overdue_90_plus"], 1)

    def test_no_overdue_returns_zeros(self):
        """Sans recos en retard, tous les buckets sont à 0."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        buckets = selectors._aging_buckets(qs)
        self.assertEqual(sum(buckets.values()), 0)


# ---------------------------------------------------------------------------
# Helper : _on_time_rates
# ---------------------------------------------------------------------------


class OnTimeRatesTest(PilotageTestMixin, TestCase):
    def test_strict_and_tolerant_rates(self):
        """
        Une reco clôturée avant original_due_date → compte dans les deux.
        Une reco clôturée après original mais avant due_date → seulement tolérante.
        """
        today = timezone.localdate()
        original = today - timedelta(days=30)
        current_due = today - timedelta(days=5)
        closed_strict = today - timedelta(days=35)  # avant original et current
        closed_tolerant = today - timedelta(days=10)  # après original, avant current

        # Reco on-time stricte ET tolérante
        self._create_reco(
            self.dir_ops,
            original_due_date=original,
            due_date_offset=0,
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at=closed_strict,
        )
        r = Recommendation.objects.order_by("-created_at").first()
        Recommendation.objects.filter(pk=r.pk).update(
            due_date=current_due, original_due_date=original
        )

        # Reco on-time tolérante seulement
        self._create_reco(
            self.dir_ops,
            original_due_date=original,
            due_date_offset=0,
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at=closed_tolerant,
        )
        r2 = Recommendation.objects.order_by("-created_at").first()
        Recommendation.objects.filter(pk=r2.pk).update(
            due_date=current_due, original_due_date=original
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        rates = selectors._on_time_rates(qs)

        self.assertEqual(rates["total_closed"], 2)
        self.assertEqual(rates["on_time_strict"], 1)
        self.assertEqual(rates["on_time_tolerant"], 2)
        self.assertEqual(rates["taux_strict"], 50.0)
        self.assertEqual(rates["taux_tolerant"], 100.0)

    def test_no_closed_returns_zeros(self):
        """Sans clôturées, tous les taux sont à 0."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        rates = selectors._on_time_rates(qs)
        self.assertEqual(rates["total_closed"], 0)
        self.assertEqual(rates["taux_strict"], 0.0)
        self.assertEqual(rates["taux_tolerant"], 0.0)


# ---------------------------------------------------------------------------
# Helper : _first_pass_rates
# ---------------------------------------------------------------------------


class FirstPassRatesTest(PilotageTestMixin, TestCase):
    def test_dm_rejection_counted_separately(self):
        """Une reprise DM compte dans rejected_by_dm mais pas rejected_by_audit."""
        reco = self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        EvidenceSubmission.objects.create(
            recommendation=reco,
            submitted_by=self.dm_ops,
            status=EvidenceSubmission.SubmissionStatus.REJECTED,
            comment="Preuve insuffisante",
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        rates = selectors._first_pass_rates(qs)

        self.assertEqual(rates["rejected_by_dm"], 1)
        self.assertEqual(rates["rejected_by_audit"], 0)
        self.assertEqual(rates["submissions_total"], 1)
        self.assertEqual(rates["taux_reprise_dm"], 100.0)
        self.assertEqual(rates["taux_reprise_audit"], 0.0)

    def test_audit_rejection_counted_separately(self):
        """Une reprise Audit compte dans rejected_by_audit mais pas rejected_by_dm."""
        reco = self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        EvidenceSubmission.objects.create(
            recommendation=reco,
            submitted_by=self.dm_ops,
            status=EvidenceSubmission.SubmissionStatus.REJECTED_BY_AUDIT,
            comment="Non conforme Audit",
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        rates = selectors._first_pass_rates(qs)

        self.assertEqual(rates["rejected_by_audit"], 1)
        self.assertEqual(rates["rejected_by_dm"], 0)

    def test_no_submissions_returns_zeros(self):
        """Sans soumission, taux à 0."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        rates = selectors._first_pass_rates(qs)
        self.assertEqual(rates["submissions_total"], 0)
        self.assertEqual(rates["taux_reprise_dm"], 0.0)


# ---------------------------------------------------------------------------
# Helper : _regulatory_stock_weighted + _regulatory_aging_index
# ---------------------------------------------------------------------------


class RegulatoryExposureTest(PilotageTestMixin, TestCase):
    def test_stock_weighted_only_external(self):
        """Seules les recos externes ouvertes comptent dans le stock pondéré."""
        self._create_reco(
            self.dir_ops,
            source=self.src_external,
            priority=Recommendation.Priority.CRITIQUE,
            assign_dm=self.dm_ops,
        )  # externe CRITIQUE → +4
        self._create_reco(
            self.dir_ops,
            source=self.src_external,
            priority=Recommendation.Priority.HAUTE,
            assign_dm=self.dm_ops,
        )  # externe HAUTE → +3
        self._create_reco(
            self.dir_ops,
            source=self.src_internal,
            priority=Recommendation.Priority.CRITIQUE,
            assign_dm=self.dm_ops,
        )  # interne → +0

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        stock = selectors._regulatory_stock_weighted(qs)
        self.assertEqual(stock, 7)  # 4 + 3

    def test_closed_external_excluded_from_stock(self):
        """Une reco externe clôturée ne compte plus dans le stock."""
        self._create_reco(
            self.dir_ops,
            source=self.src_external,
            priority=Recommendation.Priority.CRITIQUE,
            status=Recommendation.Status.CLOSED_RESOLVED,
            closed_at=timezone.now(),
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        stock = selectors._regulatory_stock_weighted(qs)
        self.assertEqual(stock, 0)

    def test_aging_index_external_overdue_only(self):
        """L'indice de vieillissement agrège poids × jours_retard sur les externes en retard."""
        today = timezone.localdate()
        original = today - timedelta(days=10)

        self._create_reco(
            self.dir_ops,
            source=self.src_external,
            priority=Recommendation.Priority.HAUTE,  # poids=3
            overdue=True,
            status=Recommendation.Status.IN_PROGRESS,
            original_due_date=original,
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        idx = selectors._regulatory_aging_index(qs)
        self.assertEqual(idx, 3 * 10)  # 3 × 10 jours

    def test_aging_index_non_overdue_not_counted(self):
        """Une reco externe non en retard ne contribue pas à l'indice."""
        self._create_reco(
            self.dir_ops,
            source=self.src_external,
            priority=Recommendation.Priority.CRITIQUE,
            assign_dm=self.dm_ops,
        )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        idx = selectors._regulatory_aging_index(qs)
        self.assertEqual(idx, 0)


# ---------------------------------------------------------------------------
# Helper : _lead_time_stats
# ---------------------------------------------------------------------------


class LeadTimeStatsTest(PilotageTestMixin, TestCase):
    def test_median_lead_time_by_priority(self):
        """La médiane est calculée correctement par criticité."""
        today = timezone.now()
        days_ago = lambda n: today - timedelta(days=n)  # noqa: E731

        # 3 recos MOYENNE : deltas 10, 20, 30 → médiane 20
        for delta in (10, 20, 30):
            r = self._create_reco(
                self.dir_ops,
                priority=Recommendation.Priority.MOYENNE,
                status=Recommendation.Status.CLOSED_RESOLVED,
            )
            Recommendation.objects.filter(pk=r.pk).update(
                created_at=days_ago(delta + 1),
                closed_at=days_ago(1),
            )

        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        stats = selectors._lead_time_stats(qs)

        self.assertIn(Recommendation.Priority.MOYENNE, stats)
        self.assertAlmostEqual(stats[Recommendation.Priority.MOYENNE], 20, delta=1)

    def test_no_closed_returns_empty_dict(self):
        """Sans clôturées, le dict est vide."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        qs = Recommendation.objects.exclude(status=Recommendation.Status.DRAFT)
        stats = selectors._lead_time_stats(qs)
        self.assertEqual(stats, {})


# ---------------------------------------------------------------------------
# Service : capture_daily_snapshot (idempotence + cohérence)
# ---------------------------------------------------------------------------


class CaptureSnapshotTest(PilotageTestMixin, TestCase):
    def test_idempotent_two_calls_same_day(self):
        """Appeler capture deux fois le même jour ne crée qu'une ligne par périmètre."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        today = timezone.localdate()

        result1 = capture_daily_snapshot(snapshot_date=today)
        result2 = capture_daily_snapshot(snapshot_date=today)

        self.assertGreater(result1["created"], 0)
        self.assertEqual(result2["created"], 0)
        self.assertGreater(result2["updated"], 0)

        count = MetricsSnapshot.objects.filter(snapshot_date=today).count()
        # banque entière + nb groupes
        from apps.dashboards.selectors import _get_breakdown_groups

        groups, _, _ = _get_breakdown_groups()
        self.assertEqual(count, 1 + len(groups))

    def test_bank_wide_snapshot_has_no_department(self):
        """Le snapshot banque entière a department=NULL."""
        today = timezone.localdate()
        capture_daily_snapshot(snapshot_date=today)

        snap = MetricsSnapshot.objects.get(snapshot_date=today, department__isnull=True)
        self.assertIsNone(snap.department_id)

    def test_totals_match_actual_data(self):
        """Le snapshot banque entière reflète les données actuelles."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        self._create_reco(self.dir_risk, assign_dm=self.dm_risk)
        today = timezone.localdate()

        capture_daily_snapshot(snapshot_date=today)
        snap = MetricsSnapshot.objects.get(snapshot_date=today, department__isnull=True)

        # 2 recos ASSIGNED (non-DRAFT, non-CLOSED) → 2 actives
        self.assertEqual(snap.total_actives, 2)
        self.assertEqual(snap.closed_total, 0)

    def test_direction_snapshot_scoped(self):
        """Le snapshot d'une direction ne comptabilise que ses recos."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        # dir_risk n'a aucune reco → total_actives=0
        today = timezone.localdate()
        capture_daily_snapshot(snapshot_date=today)

        snap_ops = MetricsSnapshot.objects.get(
            snapshot_date=today, department=self.dir_ops
        )
        snap_risk = MetricsSnapshot.objects.get(
            snapshot_date=today, department=self.dir_risk
        )

        self.assertEqual(snap_ops.total_actives, 1)
        self.assertEqual(snap_risk.total_actives, 0)

    def test_different_dates_create_separate_rows(self):
        """Des appels pour deux dates différentes créent deux snapshots distincts."""
        self._create_reco(self.dir_ops, assign_dm=self.dm_ops)
        date_a = date(2026, 1, 15)
        date_b = date(2026, 1, 16)

        capture_daily_snapshot(snapshot_date=date_a)
        capture_daily_snapshot(snapshot_date=date_b)

        self.assertTrue(
            MetricsSnapshot.objects.filter(
                snapshot_date=date_a, department__isnull=True
            ).exists()
        )
        self.assertTrue(
            MetricsSnapshot.objects.filter(
                snapshot_date=date_b, department__isnull=True
            ).exists()
        )


# ---------------------------------------------------------------------------
# AC8 — get_at_risk_recommendations : absence de N+1
# ---------------------------------------------------------------------------


class AtRiskNoN1Test(PilotageTestMixin, TestCase):
    """
    Vérifie que get_at_risk_recommendations ne produit pas de N+1.

    Piège 2 : progress_percentage est une @property faisant 2 COUNT par appel.
    L'implémentation doit annoter le queryset (Count annotés) et filtrer en Python,
    ce qui donne 1 seule requête DB quelle que soit la taille du résultat.
    """

    def setUp(self):
        # 5 recos avec échéance dans 10j et 0 livrables complétés → toutes « à risque »
        for _ in range(5):
            self._create_reco(
                self.dir_ops,
                status=Recommendation.Status.IN_PROGRESS,
                due_date_offset=10,
            )

    def test_single_query_regardless_of_result_size(self):
        """
        Quel que soit le nombre de recos retournées, une seule requête DB est émise.

        Le sélecteur charge tout en mémoire via un queryset annoté + slice,
        puis filtre le ratio en Python → 1 query.
        """
        with self.assertNumQueries(1):
            results = selectors.get_at_risk_recommendations(user=self.audit_user)
        # Les 5 recos sont bien retournées (toutes à risque : 0 livrable complété / 1 total)
        self.assertEqual(len(results), 5)

    def test_recos_outside_window_excluded(self):
        """Recos avec échéance dans +60j ne sont pas à risque de bascule."""
        self._create_reco(
            self.dir_ops,
            status=Recommendation.Status.IN_PROGRESS,
            due_date_offset=60,
        )
        results = selectors.get_at_risk_recommendations(user=self.audit_user)
        # La reco à 60j ne doit pas apparaître
        due_dates = [r.due_date for r in results]
        from django.utils import timezone as tz

        cutoff = tz.localdate() + __import__("datetime").timedelta(days=30)
        for dd in due_dates:
            self.assertLessEqual(dd, cutoff)

    def test_risk_trend_series_returns_valid_json(self):
        """get_risk_trend_series retourne un JSON valide avec labels et datasets."""
        import json as _json

        result = selectors.get_risk_trend_series(periods=3)
        data = _json.loads(result)
        self.assertIn("labels", data)
        self.assertIn("datasets", data)
        self.assertEqual(len(data["labels"]), 3)
        self.assertEqual(len(data["datasets"]), 3)
        # Sans snapshots, toutes les valeurs sont null
        for ds in data["datasets"]:
            self.assertTrue(all(v is None for v in ds["data"]))
