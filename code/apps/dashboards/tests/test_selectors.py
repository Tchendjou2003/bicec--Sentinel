"""
Dashboards App — Tests Sélecteurs (Story 6.1a)

Vérifie :
    - Scoping RBAC pour DM (département + descendants uniquement)
    - Scoping RBAC pour ETP (assigned_etp uniquement)
    - Calcul correct des KPIs (zéro N+1, pas de division par zéro)
    - Bandes aging correctes (overdue / warning / ok)
    - Exclusion des recos CLOSED_RESOLVED du tableau urgence
    - Limite de 50 lignes dans get_dm_urgency_rows
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import Recommendation, RecommendationSource

from apps.dashboards.selectors import (
    get_dm_kpis,
    get_dm_urgency_rows,
    get_etp_kpis,
)


class DashboardSelectorsTestMixin:
    """Fixtures partagées pour les tests dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.type_dir, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION",
            defaults={"name": "Direction", "level": 1},
        )
        cls.dept_a = Department.objects.create(name="Direction A", code="DA", type=cls.type_dir)
        cls.dept_b = Department.objects.create(name="Direction B", code="DB", type=cls.type_dir)

        cls.audit_user = User.objects.create_user(
            username="audit_dash", password="TestPass123!", role=User.Role.AUDIT,
        )
        cls.dm_a = User.objects.create_user(
            username="dm_dash_a", password="TestPass123!", role=User.Role.DM, department=cls.dept_a,
        )
        cls.dm_b = User.objects.create_user(
            username="dm_dash_b", password="TestPass123!", role=User.Role.DM, department=cls.dept_b,
        )
        cls.etp_a = User.objects.create_user(
            username="etp_dash_a", password="TestPass123!", role=User.Role.ETP, department=cls.dept_a,
        )

        cls.source, _ = RecommendationSource.objects.get_or_create(
            code="INTERNE",
            defaults={"label": "Audit Interne", "is_external": False},
        )

    def _create_reco(self, dept, priority=None, days_until_due=30, is_overdue=False):
        """Crée une reco en état ASSIGNED dans le département donné."""
        import uuid
        from apps.workflow.services import create_recommendation, assign_recommendation_to_dm

        priority = priority or Recommendation.Priority.MOYENNE
        due = timezone.now().date() + timedelta(days=days_until_due)

        reco = create_recommendation(
            data={
                "reference": f"TST-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission test",
                "controlled_department": dept,
                "observations": "Obs test",
                "anomalous_dossiers": "",
                "description": "Desc test",
                "source": self.source,
                "priority": priority,
                "department": dept,
                "due_date": due,
            },
            deliverables_data=["Livrable test"],
            performed_by=self.audit_user,
        )

        # Assigner au DM du département pour le rendre visible (statut != DRAFT)
        dm = User.objects.filter(role=User.Role.DM, department=dept).first()
        if dm:
            assign_recommendation_to_dm(recommendation=reco, dm=dm, performed_by=self.audit_user)

        if is_overdue:
            Recommendation.objects.filter(pk=reco.pk).update(is_overdue=True)
            # NE PAS appeler refresh_from_db() — le FSMField protected lève
            # AttributeError sur tout set direct. On recharge via .get() à la place.
            reco = Recommendation.objects.get(pk=reco.pk)

        return reco


class GetDmKpisTest(DashboardSelectorsTestMixin, TestCase):
    """Tests pour get_dm_kpis()."""

    def test_dm_kpis_zero_state(self):
        """Aucune reco → tous les KPIs à 0, pas de division par zéro."""
        kpis = get_dm_kpis(user=self.dm_a)
        self.assertEqual(kpis["total_actives"], 0)
        self.assertEqual(kpis["overdue"], 0)
        self.assertEqual(kpis["pending_dm_review"], 0)
        self.assertEqual(kpis["critique_open"], 0)
        self.assertEqual(kpis["taux_cloture"], 0.0)

    def test_dm_kpis_scoped_to_own_dept(self):
        """Le DM A ne voit que ses recos, pas celles du département B."""
        self._create_reco(self.dept_a)
        self._create_reco(self.dept_a)
        self._create_reco(self.dept_b)  # ne doit PAS apparaître pour dm_a

        kpis_a = get_dm_kpis(user=self.dm_a)
        kpis_b = get_dm_kpis(user=self.dm_b)

        self.assertEqual(kpis_a["total_actives"], 2)
        self.assertEqual(kpis_b["total_actives"], 1)

    def test_dm_kpis_overdue_count(self):
        """1 reco overdue → kpis['overdue'] == 1."""
        self._create_reco(self.dept_a, is_overdue=True)
        self._create_reco(self.dept_a, is_overdue=False)

        kpis = get_dm_kpis(user=self.dm_a)
        self.assertEqual(kpis["overdue"], 1)

    def test_dm_kpis_critique_open(self):
        """1 reco CRITIQUE non clôturée → critique_open == 1."""
        self._create_reco(self.dept_a, priority=Recommendation.Priority.CRITIQUE)
        self._create_reco(self.dept_a, priority=Recommendation.Priority.FAIBLE)

        kpis = get_dm_kpis(user=self.dm_a)
        self.assertEqual(kpis["critique_open"], 1)

    def test_dm_kpis_taux_cloture(self):
        """2 recos total dont 1 clôturée → taux_cloture == 50.0."""
        reco = self._create_reco(self.dept_a)
        self._create_reco(self.dept_a)

        # Fermer une reco directement en base pour le test
        Recommendation.objects.filter(pk=reco.pk).update(
            status=Recommendation.Status.CLOSED_RESOLVED
        )

        kpis = get_dm_kpis(user=self.dm_a)
        self.assertEqual(kpis["taux_cloture"], 50.0)


class GetDmUrgencyRowsTest(DashboardSelectorsTestMixin, TestCase):
    """Tests pour get_dm_urgency_rows()."""

    def test_urgency_rows_aging_bands(self):
        """3 recos avec aging différent → bandes correctes."""
        # Overdue
        reco_overdue = self._create_reco(self.dept_a, is_overdue=True)
        # Warning : échéance dans 10 jours
        reco_warning = self._create_reco(self.dept_a, days_until_due=10)
        # OK : échéance dans 60 jours
        reco_ok = self._create_reco(self.dept_a, days_until_due=60)

        rows = get_dm_urgency_rows(user=self.dm_a)
        bands_by_pk = {row["rec"].pk: row["aging_band"] for row in rows}

        self.assertEqual(bands_by_pk[reco_overdue.pk], "overdue")
        self.assertEqual(bands_by_pk[reco_warning.pk], "warning")
        self.assertEqual(bands_by_pk[reco_ok.pk], "ok")

    def test_urgency_rows_excludes_closed(self):
        """Les recos CLOSED_RESOLVED ne doivent PAS apparaître dans le tableau."""
        reco = self._create_reco(self.dept_a)
        Recommendation.objects.filter(pk=reco.pk).update(
            status=Recommendation.Status.CLOSED_RESOLVED
        )

        rows = get_dm_urgency_rows(user=self.dm_a)
        pks = [row["rec"].pk for row in rows]
        self.assertNotIn(reco.pk, pks)

    def test_urgency_rows_capped_at_50(self):
        """55 recos actives → get_dm_urgency_rows retourne exactement 50."""
        for _ in range(55):
            self._create_reco(self.dept_a)

        rows = get_dm_urgency_rows(user=self.dm_a)
        self.assertEqual(len(rows), 50)

    def test_urgency_rows_overdue_days_delta_positive(self):
        """Une reco overdue → days_delta est positif (nombre de jours de retard)."""
        from django.utils import timezone
        # Créer avec due_date future (validation l'exige), puis passer en overdue
        # et remettre original_due_date dans le passé pour simuler le retard
        reco = self._create_reco(self.dept_a, days_until_due=1)
        past_date = timezone.localdate() - timedelta(days=10)
        Recommendation.objects.filter(pk=reco.pk).update(
            is_overdue=True,
            original_due_date=past_date,
        )

        rows = get_dm_urgency_rows(user=self.dm_a)
        overdue_rows = [r for r in rows if r["aging_band"] == "overdue"]
        self.assertTrue(len(overdue_rows) >= 1)
        for row in overdue_rows:
            self.assertIsNotNone(row["days_delta"])
            self.assertGreaterEqual(row["days_delta"], 0)

    def test_urgency_rows_scoped_to_dept(self):
        """Les recos du département B n'apparaissent pas pour le DM A."""
        self._create_reco(self.dept_b)

        rows = get_dm_urgency_rows(user=self.dm_a)
        depts = {row["rec"].department_id for row in rows if row["rec"].department}
        self.assertNotIn(self.dept_b.pk, depts)


class GetEtpKpisTest(DashboardSelectorsTestMixin, TestCase):
    """Tests pour get_etp_kpis()."""

    def test_etp_kpis_zero_state(self):
        """ETP sans recos → tous KPIs à 0."""
        kpis = get_etp_kpis(user=self.etp_a)
        self.assertEqual(kpis["total_actives"], 0)
        self.assertEqual(kpis["overdue"], 0)
        self.assertEqual(kpis["in_progress"], 0)
        self.assertEqual(kpis["closed_resolved"], 0)

    def test_etp_kpis_scoped_to_assigned_etp(self):
        """L'ETP ne voit que les recos où assigned_etp == lui-même."""
        reco = self._create_reco(self.dept_a)

        # Déléguer la reco à etp_a (ASSIGNED → IN_PROGRESS avec assigned_etp)
        from apps.workflow.services import delegate_recommendation_to_etp
        delegate_recommendation_to_etp(recommendation=reco, etp=self.etp_a, performed_by=self.dm_a)

        kpis = get_etp_kpis(user=self.etp_a)
        self.assertEqual(kpis["total_actives"], 1)
