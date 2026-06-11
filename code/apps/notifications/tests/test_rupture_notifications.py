"""
Tests des notifications de rupture (job 3.9 étendu) et des hooks de service
critiques — Story 4.1 (corrections post-revue F1/F2/F3).
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.users.models import Department, OrgUnitType, User
from apps.workflow.models import Recommendation, RecommendationSource
from apps.workflow.services import (
    add_file_to_draft,
    close_recommendation_by_audit,
    flag_overdue_recommendations,
    get_or_create_draft_submission,
    reject_recommendation_by_audit,
    save_draft_comment,
    submit_evidence_by_dg,
    submit_evidence_for_recommendation,
)


def _pdf(name="p.pdf"):
    return SimpleUploadedFile(
        name, b"%PDF-1.4 1 0 obj<</Type /Catalog>> endobj", content_type="application/pdf"
    )


class NotificationRuptureTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        otype, _ = OrgUnitType.objects.get_or_create(
            code="DIR", defaults={"name": "Direction", "level": 1})
        cls.dept = Department.objects.create(name="Dept", code="DPT", type=otype)
        cls.audit = User.objects.create_user("audit_r", role=User.Role.AUDIT, department=cls.dept)
        cls.dm = User.objects.create_user("dm_r", role=User.Role.DM, department=cls.dept)
        cls.etp = User.objects.create_user("etp_r", role=User.Role.ETP, department=cls.dept)
        cls.dg = User.objects.create_user("dg_r", role=User.Role.DG, department=cls.dept)
        cls.source = RecommendationSource.objects.create(code="SRCR", label="Src")

    def _reco(self, *, priority, status, is_overdue, days_overdue, assigned_dm=None,
              assigned_etp=None):
        """Crée une reco dans l'état voulu (ORM direct pour contrôler le FSM)."""
        due = timezone.localdate() - timedelta(days=days_overdue)
        rec = Recommendation.objects.create(
            reference=f"REC-{priority}-{timezone.now().timestamp()}",
            description="desc", source=self.source, priority=priority,
            due_date=due, original_due_date=due, created_by=self.audit,
            controlled_department=self.dept, department=self.dept,
        )
        Recommendation.all_objects.filter(pk=rec.pk).update(
            status=status, is_overdue=is_overdue,
            assigned_dm=assigned_dm, assigned_etp=assigned_etp,
        )
        return Recommendation.all_objects.get(pk=rec.pk)


class RuptureNotificationTest(NotificationRuptureTestBase):

    def test_overdue_critique_notifies_porteur_urgent(self):
        self._reco(priority=Recommendation.Priority.CRITIQUE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=False, days_overdue=5, assigned_dm=self.dm)
        flag_overdue_recommendations()
        notif = Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.OVERDUE).first()
        self.assertIsNotNone(notif)
        self.assertTrue(notif.is_urgent)

    def test_overdue_non_critique_no_notification(self):
        rec = self._reco(priority=Recommendation.Priority.MOYENNE,
                         status=Recommendation.Status.IN_PROGRESS,
                         is_overdue=False, days_overdue=5, assigned_dm=self.dm)
        flag_overdue_recommendations()
        # Le flag bascule bien, mais AUCUNE notification (F1).
        self.assertTrue(Recommendation.all_objects.get(pk=rec.pk).is_overdue)
        self.assertEqual(
            Notification.objects.filter(notification_type=Notification.Type.OVERDUE).count(), 0)

    def test_overdue_porteur_is_etp_when_assigned(self):
        self._reco(priority=Recommendation.Priority.CRITIQUE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=False, days_overdue=3,
                   assigned_dm=self.dm, assigned_etp=self.etp)
        flag_overdue_recommendations()
        self.assertTrue(Notification.objects.filter(
            recipient=self.etp, notification_type=Notification.Type.OVERDUE).exists())

    def test_j30_critique_notifies_dm(self):
        self._reco(priority=Recommendation.Priority.CRITIQUE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=True, days_overdue=35, assigned_dm=self.dm,
                   assigned_etp=self.etp)
        flag_overdue_recommendations()
        self.assertTrue(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.OVERDUE_J30).exists())

    def test_j30_non_critique_no_notification(self):
        self._reco(priority=Recommendation.Priority.HAUTE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=True, days_overdue=40, assigned_dm=self.dm)
        flag_overdue_recommendations()
        self.assertEqual(
            Notification.objects.filter(notification_type=Notification.Type.OVERDUE_J30).count(), 0)

    def test_no_j60_notification(self):
        """F5 — le jalon J60 a été retiré : aucune notif d'escalade 60j."""
        self._reco(priority=Recommendation.Priority.CRITIQUE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=True, days_overdue=70, assigned_dm=self.dm)
        flag_overdue_recommendations()
        self.assertEqual(Notification.objects.filter(
            notification_type=Notification.Type.OVERDUE_J60_ESCALATION).count(), 0)

    def test_idempotent_second_run_no_duplicate(self):
        self._reco(priority=Recommendation.Priority.CRITIQUE,
                   status=Recommendation.Status.IN_PROGRESS,
                   is_overdue=False, days_overdue=5, assigned_dm=self.dm)
        flag_overdue_recommendations()
        flag_overdue_recommendations()
        self.assertEqual(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.OVERDUE).count(), 1)

    def test_reconciliation_deletes_then_renotifies(self):
        """F2/AC4 — report (due_date repoussée) → notif supprimée → re-dépassement re-notifie."""
        rec = self._reco(priority=Recommendation.Priority.CRITIQUE,
                         status=Recommendation.Status.IN_PROGRESS,
                         is_overdue=False, days_overdue=5, assigned_dm=self.dm)
        flag_overdue_recommendations()
        self.assertEqual(Notification.objects.filter(
            idempotency_key=f"OVERDUE:{rec.pk}").count(), 1)

        # Report approuvé : due_date repoussée au futur → réconciliation supprime la notif.
        Recommendation.all_objects.filter(pk=rec.pk).update(
            due_date=timezone.localdate() + timedelta(days=10))
        flag_overdue_recommendations()
        self.assertEqual(Notification.objects.filter(
            idempotency_key=f"OVERDUE:{rec.pk}").count(), 0)
        self.assertFalse(Recommendation.all_objects.get(pk=rec.pk).is_overdue)

        # Nouveau dépassement → re-notification possible (clé réutilisable).
        Recommendation.all_objects.filter(pk=rec.pk).update(
            due_date=timezone.localdate() - timedelta(days=2), is_overdue=False)
        flag_overdue_recommendations()
        self.assertEqual(Notification.objects.filter(
            idempotency_key=f"OVERDUE:{rec.pk}").count(), 1)


class WorkflowHookNotificationTest(NotificationRuptureTestBase):

    def _ip_reco_with_draft(self, *, owner, assigned_dm, assigned_etp=None):
        rec = self._reco(priority=Recommendation.Priority.HAUTE,
                         status=Recommendation.Status.IN_PROGRESS,
                         is_overdue=False, days_overdue=-30,
                         assigned_dm=assigned_dm, assigned_etp=assigned_etp)
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=owner)
        add_file_to_draft(submission=draft, file=_pdf(), user=owner)
        save_draft_comment(submission=draft, comment="Travaux réalisés.", user=owner)
        return rec

    def test_d4_dm_porteur_submission_notifies_audit(self):
        """D4 — DM porteur (sans ETP) soumet → l'Audit créateur est notifié."""
        rec = self._ip_reco_with_draft(owner=self.dm, assigned_dm=self.dm)
        submit_evidence_for_recommendation(recommendation=rec, performed_by=self.dm)
        self.assertTrue(Notification.objects.filter(
            recipient=self.audit, notification_type=Notification.Type.EVIDENCE_SUBMITTED).exists())
        # Le DM (acteur) n'est pas notifié.
        self.assertFalse(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.EVIDENCE_SUBMITTED).exists())

    def test_etp_submission_notifies_dm(self):
        rec = self._ip_reco_with_draft(owner=self.etp, assigned_dm=self.dm, assigned_etp=self.etp)
        submit_evidence_for_recommendation(recommendation=rec, performed_by=self.etp)
        self.assertTrue(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.EVIDENCE_SUBMITTED).exists())

    def test_close_notifies_porteur(self):
        # Reco amenée en PENDING_AUDIT_REVIEW via DG (avec fichier).
        rec = self._reco(priority=Recommendation.Priority.HAUTE,
                         status=Recommendation.Status.IN_PROGRESS,
                         is_overdue=False, days_overdue=-30, assigned_dm=self.dg)
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=self.dg)
        add_file_to_draft(submission=draft, file=_pdf(), user=self.dg)
        save_draft_comment(submission=draft, comment="ok", user=self.dg)
        rec = submit_evidence_by_dg(recommendation=rec, performed_by=self.dg)
        close_recommendation_by_audit(recommendation=rec, performed_by=self.audit)
        self.assertTrue(Notification.objects.filter(
            recipient=self.dg, notification_type=Notification.Type.CLOSED).exists())

    def test_reject_by_audit_notifies_porteur_and_dm(self):
        """D5 — rejet Audit notifie le porteur (ETP) ET le DM."""
        rec = self._reco(priority=Recommendation.Priority.HAUTE,
                         status=Recommendation.Status.IN_PROGRESS,
                         is_overdue=False, days_overdue=-30,
                         assigned_dm=self.dm, assigned_etp=self.etp)
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=self.dg)
        # Forcer PENDING_AUDIT_REVIEW + soumission ACCEPTED (avec fichier) via DG ?
        # Plus simple : ETP soumet → DM valide. Mais ici on teste le rejet Audit :
        # on amène en PENDING_AUDIT_REVIEW via DG porteur n'est pas applicable (ETP assigné).
        # On construit l'état directement.
        from apps.workflow.models import EvidenceSubmission, EvidenceFile
        sub = EvidenceSubmission.objects.create(
            recommendation=rec, submitted_by=self.etp,
            status=EvidenceSubmission.SubmissionStatus.ACCEPTED, comment="c")
        EvidenceFile.objects.create(
            submission=sub, file="evidence/x.pdf", original_filename="x.pdf",
            file_size=10, mime_type="application/pdf", sha256_hash="a" * 64,
            uploaded_by=self.etp)
        Recommendation.all_objects.filter(pk=rec.pk).update(status="PENDING_AUDIT_REVIEW")
        rec = Recommendation.all_objects.get(pk=rec.pk)
        reject_recommendation_by_audit(
            recommendation=rec, reason="Motif suffisant de rejet.", performed_by=self.audit)
        self.assertTrue(Notification.objects.filter(
            recipient=self.etp, notification_type=Notification.Type.EVIDENCE_REJECTED).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.dm, notification_type=Notification.Type.EVIDENCE_REJECTED).exists())
