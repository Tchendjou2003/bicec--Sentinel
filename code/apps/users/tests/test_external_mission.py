"""
Users App — Tests du modèle ExternalMission (Story 6.7)

Vérifie la conformité du modèle ExternalMission redéfini en Story 6.7 :
    - name : nom humain de la campagne
    - organisation : FK vers RecommendationSource (is_external=True)
    - status : TextChoices PREPARATION / ACTIVE / CLOSED
    - auditors : M2M vers User (role=EXT)
    - recommendations : M2M vers Recommendation
    - created_by / approved_by : traçabilité
    - start_date / end_date : période d'intervention
"""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.users.models import ExternalMission, User
from apps.workflow.models import RecommendationSource


class ExternalMissionModelTest(TestCase):
    """Tests du modèle ExternalMission (Story 6.7)."""

    def setUp(self):
        """Crée un auditeur externe et une source externe pour les tests."""
        self.auditor = User.objects.create_user(
            username="cobac_inspector",
            password="testpass123",
            email="inspector@cobac.org",
            role=User.Role.EXT,
            is_external=True,
        )
        # created_by est null=True mais blank=False → full_clean() l'exige.
        self.creator = User.objects.create_user(
            username="audit_creator",
            password="testpass123",
            email="creator@bicec.cm",
            role=User.Role.AUDIT,
        )
        # Code de test isolé : une source COBAC peut déjà exister (seed migration),
        # ce qui violerait la contrainte unique sur `code`.
        self.source = RecommendationSource.objects.create(
            code="TEST_EXTMISSION",
            label="COBAC (test)",
            is_external=True,
            is_active=True,
        )
        self.today = date.today()
        self.mission = ExternalMission.objects.create(
            name="Contrôle COBAC 2026",
            organisation=self.source,
            scope_description="Audit des procédures de crédit",
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            status=ExternalMission.Status.ACTIVE,
            created_by=self.creator,
        )
        self.mission.auditors.add(self.auditor)

    def test_external_mission_creation(self):
        """Une mission externe est créée avec tous ses champs."""
        self.assertEqual(self.mission.name, "Contrôle COBAC 2026")
        self.assertEqual(self.mission.organisation, self.source)
        self.assertEqual(
            self.mission.scope_description,
            "Audit des procédures de crédit",
        )
        self.assertEqual(self.mission.start_date, self.today)
        self.assertEqual(self.mission.end_date, self.today + timedelta(days=30))
        self.assertEqual(self.mission.status, ExternalMission.Status.ACTIVE)

    def test_external_mission_has_uuid_pk(self):
        """La clé primaire est un UUID (cohérence avec les autres modèles)."""
        import uuid

        self.assertIsInstance(self.mission.pk, uuid.UUID)

    def test_external_mission_str(self):
        """__str__ affiche le nom et le libellé du statut."""
        expected = "Contrôle COBAC 2026 (Active)"
        self.assertEqual(str(self.mission), expected)

    def test_external_mission_auditors_m2m(self):
        """La relation M2M vers User fonctionne correctement."""
        missions = ExternalMission.objects.filter(auditors=self.auditor)
        self.assertEqual(missions.count(), 1)
        self.assertEqual(missions.first(), self.mission)

    def test_external_mission_auditor_related_name(self):
        """L'accès inverse via related_name 'external_missions' fonctionne."""
        self.assertIn(self.mission, self.auditor.external_missions.all())

    def test_external_mission_status_default_preparation(self):
        """Le champ status est PREPARATION par défaut."""
        mission = ExternalMission.objects.create(
            name="Mission sans statut explicite",
            organisation=self.source,
            scope_description="Audit réserves obligatoires",
            start_date=self.today,
            end_date=self.today + timedelta(days=15),
            created_by=self.creator,
        )
        self.assertEqual(mission.status, ExternalMission.Status.PREPARATION)

    def test_external_mission_timestamps(self):
        """Les champs created_at et updated_at sont renseignés automatiquement."""
        self.assertIsNotNone(self.mission.created_at)
        self.assertIsNotNone(self.mission.updated_at)

    def test_external_mission_ordering(self):
        """Les missions sont ordonnées par date de début décroissante."""
        older_mission = ExternalMission.objects.create(
            name="Mission ancienne",
            organisation=self.source,
            scope_description="Audit ancien",
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=30),
            status=ExternalMission.Status.CLOSED,
            created_by=self.creator,
        )
        missions = list(ExternalMission.objects.all())
        # La plus récente (self.mission) devrait être en premier
        self.assertEqual(missions[0], self.mission)
        self.assertEqual(missions[1], older_mission)

    def test_external_mission_organisation_protect_on_delete(self):
        """Supprimer une source rattachée à une mission lève ProtectedError."""
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.source.delete()

    def test_external_mission_scope_can_be_blank(self):
        """Le champ scope_description peut être vide (mission pas encore cadrée)."""
        mission = ExternalMission.objects.create(
            name="Mission non cadrée",
            organisation=self.source,
            scope_description="",
            start_date=self.today,
            end_date=self.today + timedelta(days=10),
            created_by=self.creator,
        )
        self.assertEqual(mission.scope_description, "")

    def test_external_mission_end_date_nullable(self):
        """Le champ end_date peut être null (mission sans date de fin prévue)."""
        mission = ExternalMission.objects.create(
            name="Mission longue durée",
            organisation=self.source,
            scope_description="Mission longue durée",
            start_date=self.today,
            end_date=None,
            created_by=self.creator,
        )
        self.assertIsNone(mission.end_date)

    def test_multiple_missions_per_auditor(self):
        """Un auditeur peut être rattaché à plusieurs missions."""
        second = ExternalMission.objects.create(
            name="Deuxième mission",
            organisation=self.source,
            scope_description="Deuxième mission",
            start_date=self.today + timedelta(days=31),
            end_date=self.today + timedelta(days=60),
            created_by=self.creator,
        )
        second.auditors.add(self.auditor)
        self.assertEqual(self.auditor.external_missions.count(), 2)

    def test_external_mission_invalid_dates(self):
        """Une mission ne peut pas avoir une date de fin antérieure au début."""
        mission = ExternalMission(
            name="Dates incohérentes",
            organisation=self.source,
            start_date=self.today,
            end_date=self.today - timedelta(days=5),
            created_by=self.creator,
        )
        with self.assertRaises(ValidationError) as context:
            mission.full_clean()
        self.assertIn("end_date", context.exception.message_dict)

    def test_external_mission_auditors_limit_choices(self):
        """Le champ auditors restreint le choix aux utilisateurs externes (role=EXT)."""
        limit_choices = ExternalMission._meta.get_field("auditors").get_limit_choices_to()
        self.assertEqual(limit_choices, {"role": User.Role.EXT})

    def test_external_mission_organisation_limit_choices(self):
        """Le champ organisation restreint le choix aux sources externes actives."""
        limit_choices = ExternalMission._meta.get_field("organisation").get_limit_choices_to()
        self.assertEqual(limit_choices, {"is_external": True, "is_active": True})


class ExternalMissionAdminTest(TestCase):
    """Tests de l'interface d'administration pour ExternalMission."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@bicec.cm",
        )
        self.auditor = User.objects.create_user(
            username="ext_auditor",
            password="testpass123",
            role=User.Role.EXT,
            is_external=True,
        )

    def test_external_mission_admin_accessible(self):
        """L'admin ExternalMission est accessible par un superuser."""
        from django.test import Client

        client = Client()
        client.force_login(self.superuser)
        response = client.get("/admin/users/externalmission/")
        self.assertEqual(response.status_code, 200)

    def test_external_mission_admin_add(self):
        """Un superuser peut ajouter une mission via le Django Admin."""
        from django.test import Client

        client = Client()
        client.force_login(self.superuser)
        response = client.get("/admin/users/externalmission/add/")
        self.assertEqual(response.status_code, 200)
