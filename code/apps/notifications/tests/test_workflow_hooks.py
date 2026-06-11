from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.notifications.services import notify_porteur, notify_dm, notify_audit_owner, _reco_url
from apps.notifications.models import Notification
from apps.workflow.models import Recommendation, RecommendationSource

User = get_user_model()

class TestWorkflowHooks(TestCase):
    def setUp(self):
        self.audit = User.objects.create_user(username="audit", role=User.Role.AUDIT)
        self.dm = User.objects.create_user(username="dm", role=User.Role.DM)
        self.etp = User.objects.create_user(username="etp", role=User.Role.ETP)
        self.other = User.objects.create_user(username="other", role=User.Role.DM)

        self.source = RecommendationSource.objects.create(code="SRC-1", label="Test Source")

        self.recommendation = Recommendation.objects.create(
            reference="REC-TEST-1",
            description="Rec Test",
            source=self.source,
            priority=Recommendation.Priority.MOYENNE,
            due_date=date(2026, 12, 31),
            original_due_date=date(2026, 12, 31),
            created_by=self.audit,
            assigned_dm=self.dm,
            assigned_etp=self.etp,
        )

    def test_reco_url(self):
        self.assertEqual(_reco_url(self.recommendation), f"/audit/recommandations/{self.recommendation.pk}/")

    def test_notify_porteur_with_etp(self):
        # When ETP is assigned, porteur is ETP
        notif = notify_porteur(
            self.recommendation,
            type=Notification.Type.EVIDENCE_REJECTED,
            title="Rejet",
            actor=self.other,
            key="KEY-1"
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.etp)
        self.assertEqual(notif.notification_type, Notification.Type.EVIDENCE_REJECTED)

    def test_notify_porteur_without_etp(self):
        self.recommendation.assigned_etp = None
        self.recommendation.save()
        
        # When no ETP, porteur is DM
        notif = notify_porteur(
            self.recommendation,
            type=Notification.Type.EVIDENCE_REJECTED,
            title="Rejet",
            actor=self.other,
            key="KEY-2"
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.dm)

    def test_notify_porteur_skips_actor(self):
        # Actor is ETP, recipient would be ETP -> skip (returns None)
        notif = notify_porteur(
            self.recommendation,
            type=Notification.Type.EVIDENCE_REJECTED,
            title="Rejet",
            actor=self.etp,
            key="KEY-3"
        )
        self.assertIsNone(notif)

    def test_notify_dm(self):
        notif = notify_dm(
            self.recommendation,
            type=Notification.Type.EVIDENCE_REJECTED,
            title="Rejet",
            actor=self.other,
            key="KEY-4"
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.dm)

    def test_notify_dm_skips_actor(self):
        # Actor is DM -> skip
        notif = notify_dm(
            self.recommendation,
            type=Notification.Type.EVIDENCE_REJECTED,
            title="Rejet",
            actor=self.dm,
            key="KEY-5"
        )
        self.assertIsNone(notif)

    def test_notify_audit_owner(self):
        notif = notify_audit_owner(
            self.recommendation,
            type=Notification.Type.EVIDENCE_SUBMITTED,
            title="Soumission",
            actor=self.other,
            key="KEY-6"
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.audit)

    def test_notify_audit_owner_skips_actor(self):
        notif = notify_audit_owner(
            self.recommendation,
            type=Notification.Type.EVIDENCE_VALIDATED,
            title="Validation",
            actor=self.audit,
            key="KEY-7"
        )
        self.assertIsNone(notif)
