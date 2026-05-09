"""
Users App — Tests du modèle ExternalMission (Story 1.3, AC4)

Vérifie la conformité du modèle ExternalMission avec les
spécifications : FR2 (isolation des auditeurs externes),
ADR-10 (séparation des rôles).

Le modèle doit représenter une mission d'audit externe avec :
    - Un auditeur rattaché (FK vers User)
    - L'organisation d'origine (COBAC, BEAC, etc.)
    - Le périmètre de la mission (scope_description)
    - Les dates de début et fin
    - Un flag is_active
"""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.users.models import ExternalMission, User


class ExternalMissionModelTest(TestCase):
    """Tests du modèle ExternalMission (Story 1.3 — AC4)."""

    def setUp(self):
        """Crée un auditeur externe pour les tests."""
        self.auditor = User.objects.create_user(
            username="cobac_inspector",
            password="testpass123",
            email="inspector@cobac.org",
            role=User.Role.EXT,
            is_external=True,
        )
        self.today = date.today()
        self.mission = ExternalMission.objects.create(
            auditor=self.auditor,
            organization="COBAC",
            scope_description="Audit des procédures de crédit",
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            is_active=True,
        )

    def test_external_mission_creation(self):
        """Une mission externe est créée avec tous ses champs."""
        self.assertEqual(self.mission.auditor, self.auditor)
        self.assertEqual(self.mission.organization, "COBAC")
        self.assertEqual(
            self.mission.scope_description,
            "Audit des procédures de crédit",
        )
        self.assertEqual(self.mission.start_date, self.today)
        self.assertEqual(self.mission.end_date, self.today + timedelta(days=30))
        self.assertTrue(self.mission.is_active)

    def test_external_mission_has_uuid_pk(self):
        """La clé primaire est un UUID (cohérence avec les autres modèles)."""
        import uuid

        self.assertIsInstance(self.mission.pk, uuid.UUID)

    def test_external_mission_str(self):
        """__str__ affiche l'organisation et l'auditeur."""
        expected = f"COBAC — cobac_inspector"
        self.assertEqual(str(self.mission), expected)

    def test_external_mission_auditor_fk(self):
        """La relation FK vers User fonctionne correctement."""
        missions = ExternalMission.objects.filter(auditor=self.auditor)
        self.assertEqual(missions.count(), 1)
        self.assertEqual(missions.first(), self.mission)

    def test_external_mission_auditor_related_name(self):
        """L'accès inverse via related_name 'external_missions' fonctionne."""
        self.assertIn(self.mission, self.auditor.external_missions.all())

    def test_external_mission_is_active_default_true(self):
        """Le champ is_active est True par défaut."""
        mission = ExternalMission.objects.create(
            auditor=self.auditor,
            organization="BEAC",
            scope_description="Audit réserves obligatoires",
            start_date=self.today,
            end_date=self.today + timedelta(days=15),
        )
        self.assertTrue(mission.is_active)

    def test_external_mission_timestamps(self):
        """Les champs created_at et updated_at sont renseignés automatiquement."""
        self.assertIsNotNone(self.mission.created_at)
        self.assertIsNotNone(self.mission.updated_at)

    def test_external_mission_ordering(self):
        """Les missions sont ordonnées par date de début décroissante."""
        older_mission = ExternalMission.objects.create(
            auditor=self.auditor,
            organization="BEAC",
            scope_description="Audit ancien",
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=30),
            is_active=False,
        )
        missions = list(ExternalMission.objects.all())
        # La plus récente (self.mission) devrait être en premier
        self.assertEqual(missions[0], self.mission)
        self.assertEqual(missions[1], older_mission)

    def test_external_mission_auditor_protect_on_delete(self):
        """Supprimer un utilisateur avec des missions lève ProtectedError."""
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.auditor.delete()

    def test_external_mission_scope_can_be_blank(self):
        """Le champ scope_description peut être vide (mission pas encore cadrée)."""
        mission = ExternalMission.objects.create(
            auditor=self.auditor,
            organization="CAC",
            scope_description="",
            start_date=self.today,
            end_date=self.today + timedelta(days=10),
        )
        self.assertEqual(mission.scope_description, "")

    def test_external_mission_end_date_nullable(self):
        """Le champ end_date peut être null (mission sans date de fin prévue)."""
        mission = ExternalMission.objects.create(
            auditor=self.auditor,
            organization="COBAC",
            scope_description="Mission longue durée",
            start_date=self.today,
            end_date=None,
        )
        self.assertIsNone(mission.end_date)

    def test_multiple_missions_per_auditor(self):
        """Un auditeur peut avoir plusieurs missions."""
        ExternalMission.objects.create(
            auditor=self.auditor,
            organization="BEAC",
            scope_description="Deuxième mission",
            start_date=self.today + timedelta(days=31),
            end_date=self.today + timedelta(days=60),
        )
        self.assertEqual(self.auditor.external_missions.count(), 2)

    def test_external_mission_invalid_dates(self):
        """Une mission ne peut pas avoir une date de fin antérieure au début."""
        mission = ExternalMission(
            auditor=self.auditor,
            organization="CAC",
            start_date=self.today,
            end_date=self.today - timedelta(days=5),
        )
        with self.assertRaises(ValidationError) as context:
            mission.full_clean()
        self.assertIn("end_date", context.exception.message_dict)

    def test_external_mission_auditor_limit_choices(self):
        """Le champ auditor restreint le choix aux utilisateurs externes (is_external=True, role=EXT)."""
        limit_choices = ExternalMission._meta.get_field('auditor').get_limit_choices_to()
        self.assertEqual(limit_choices, {"is_external": True, "role": User.Role.EXT})


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
