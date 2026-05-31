"""
Tests de l'anticipation in-app J-7 / J-3 (Story 4.2) et du wrapper nocturne.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import Recommendation, RecommendationSource
from apps.workflow.services import (
    notify_upcoming_deadlines,
    run_nightly_notifications,
)


class AnticipationTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        otype, _ = OrgUnitType.objects.get_or_create(
            code="DIR", defaults={"name": "Direction", "level": 1})
        cls.dept = Department.objects.create(name="Dept", code="DPT", type=otype)
        cls.audit = User.objects.create_user("audit_a", role=User.Role.AUDIT, department=cls.dept)
        cls.dm = User.objects.create_user("dm_a", role=User.Role.DM, department=cls.dept)
        cls.etp = User.objects.create_user("etp_a", role=User.Role.ETP, department=cls.dept)
        cls.source = RecommendationSource.objects.create(code="SRCA", label="Src")

    def _reco(self, *, priority, days_until, status=Recommendation.Status.IN_PROGRESS,
              assigned_dm=None, assigned_etp=None, is_overdue=False):
        due = timezone.localdate() + timedelta(days=days_until)
        rec = Recommendation.objects.create(
            reference=f"REC-{priority}-{timezone.now().timestamp()}",
            description="d", source=self.source, priority=priority,
            due_date=due, original_due_date=due, created_by=self.audit,
            controlled_department=self.dept, department=self.dept)
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=status, assigned_dm=assigned_dm or self.dm,
            assigned_etp=assigned_etp, is_overdue=is_overdue)
        return Recommendation.all_objects.get(pk=rec.pk)


class UpcomingDeadlineTest(AnticipationTestBase):

    def test_j7_notifies_porteur_not_urgent(self):
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=7)
        notify_upcoming_deadlines()
        notif = Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.DUE_SOON_J7).first()
        self.assertIsNotNone(notif)
        self.assertFalse(notif.is_urgent)

    def test_j3_notifies_porteur(self):
        self._reco(priority=Recommendation.Priority.MOYENNE, days_until=3)
        notify_upcoming_deadlines()
        self.assertTrue(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.DUE_SOON_J3).exists())

    def test_all_priorities_covered(self):
        for prio in [Recommendation.Priority.CRITIQUE, Recommendation.Priority.HAUTE,
                     Recommendation.Priority.MOYENNE, Recommendation.Priority.FAIBLE]:
            self._reco(priority=prio, days_until=6)
        notify_upcoming_deadlines()
        self.assertEqual(Notification.objects.filter(
            notification_type=Notification.Type.DUE_SOON_J7).count(), 4)

    def test_porteur_is_etp_when_assigned(self):
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=5,
                   assigned_etp=self.etp)
        notify_upcoming_deadlines()
        self.assertTrue(Notification.objects.filter(
            recipient=self.etp, notification_type=Notification.Type.DUE_SOON_J7).exists())

    def test_not_in_window_no_notification(self):
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=10)
        notify_upcoming_deadlines()
        self.assertEqual(Notification.objects.filter(
            notification_type=Notification.Type.DUE_SOON_J7).count(), 0)

    def test_pending_state_no_notification(self):
        """Une reco déjà soumise (PENDING_*) ne génère pas de rappel au porteur."""
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=5,
                   status=Recommendation.Status.PENDING_DM_REVIEW)
        notify_upcoming_deadlines()
        self.assertEqual(Notification.objects.filter(
            notification_type=Notification.Type.DUE_SOON_J7).count(), 0)

    def test_idempotent(self):
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=6)
        notify_upcoming_deadlines()
        notify_upcoming_deadlines()
        self.assertEqual(Notification.objects.filter(
            notification_type=Notification.Type.DUE_SOON_J7).count(), 1)

    def test_no_anticipation_when_overdue(self):
        """due_date passée → pas de DUE_SOON (domaine des ruptures)."""
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=-2, is_overdue=True)
        notify_upcoming_deadlines()
        self.assertEqual(Notification.objects.filter(
            notification_type__in=[Notification.Type.DUE_SOON_J7,
                                   Notification.Type.DUE_SOON_J3]).count(), 0)

    def test_due_soon_survives_day_j(self):
        """Jour J (due_date == today) : le rappel J-3 déjà émis SURVIT (pas de trou noir)."""
        rec = self._reco(priority=Recommendation.Priority.HAUTE, days_until=2)
        notify_upcoming_deadlines()  # émet J-3 et J-7
        self.assertTrue(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J3:{rec.pk}").exists())
        # On avance au Jour J : due_date == today
        Recommendation.all_objects.filter(pk=rec.pk).update(due_date=timezone.localdate())
        notify_upcoming_deadlines()
        # La notif d'anticipation existe TOUJOURS le jour exact de l'échéance.
        self.assertTrue(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J3:{rec.pk}").exists())

    def test_due_soon_cleared_day_after(self):
        """J+1 (due_date == today-1) : DUE_SOON nettoyée (relais à OVERDUE)."""
        rec = self._reco(priority=Recommendation.Priority.HAUTE, days_until=2)
        notify_upcoming_deadlines()
        Recommendation.all_objects.filter(pk=rec.pk).update(
            due_date=timezone.localdate() - timedelta(days=1))
        notify_upcoming_deadlines()
        self.assertFalse(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J3:{rec.pk}").exists())

    def test_reconcile_after_extension(self):
        """Report repousse due_date hors fenêtre → DUE_SOON supprimée → ré-approche re-notifie."""
        rec = self._reco(priority=Recommendation.Priority.HAUTE, days_until=5)
        notify_upcoming_deadlines()
        self.assertTrue(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J7:{rec.pk}").exists())
        # Report : due_date repoussée à +30 j (hors fenêtre J-7)
        Recommendation.all_objects.filter(pk=rec.pk).update(
            due_date=timezone.localdate() + timedelta(days=30))
        notify_upcoming_deadlines()
        self.assertFalse(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J7:{rec.pk}").exists())
        # Ré-approche → re-notification possible
        Recommendation.all_objects.filter(pk=rec.pk).update(
            due_date=timezone.localdate() + timedelta(days=6))
        notify_upcoming_deadlines()
        self.assertTrue(Notification.objects.filter(
            idempotency_key=f"DUE_SOON_J7:{rec.pk}").exists())


class NightlyWrapperTest(AnticipationTestBase):

    def test_run_nightly_runs_both(self):
        # Une reco échue CRITIQUE (overdue) + une reco proche (anticipation)
        overdue = self._reco(priority=Recommendation.Priority.CRITIQUE, days_until=-3)
        self._reco(priority=Recommendation.Priority.HAUTE, days_until=5)
        result = run_nightly_notifications()
        self.assertIn("overdue", result)
        self.assertIn("upcoming", result)
        # L'overdue a basculé + notif OVERDUE (CRITIQUE) ; l'anticipation a émis J-7.
        self.assertTrue(Recommendation.all_objects.get(pk=overdue.pk).is_overdue)
        self.assertTrue(Notification.objects.filter(
            notification_type=Notification.Type.DUE_SOON_J7).exists())
