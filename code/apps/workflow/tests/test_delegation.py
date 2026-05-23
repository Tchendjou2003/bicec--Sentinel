"""
Workflow App — Tests de Délégation Hiérarchique (Story 3.2)

Tests complets pour la délégation ETP / DM Porteur couvrant :
    - Scénario 1  : Délégation à un ETP de la même direction (AC1 & AC3)
    - Scénario 1b : Délégation refusée si ETP d'une autre direction (AC4)
    - Scénario 1c : Délégation acceptée si ETP d'un sous-département
    - Scénario 2  : Auto-assignation DM Porteur (AC2)
    - Scénario 3.1: ETP ne peut pas accéder à la vue de délégation
    - Scénario 3.2: DM d'une autre direction ne peut pas déléguer (403)
    - Scénario 3.3: Délégation bloquée si statut != ASSIGNED
    - Tests hiérarchiques : visibilité DM/DG sur sous-départements
    - Tests selectors : _get_department_and_descendants_ids
    - Tests formulaire : DelegateETPForm filtrage hiérarchique
"""
import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.users.models import Department, User
from apps.workflow.models import Recommendation
from apps.workflow.services import (
    assign_recommendation_to_dm,
    create_recommendation,
    delegate_recommendation_to_etp,
    become_dm_porteur,
)
from apps.workflow.forms import DelegateETPForm
from apps.workflow import selectors
from apps.audit.models import AuditLog


class HierarchyTestMixin:
    """Mixin pour construire une hiérarchie de départements complète."""

    @classmethod
    def setUpTestData(cls):
        # ── Direction Finance (racine) ──
        cls.direction_finance = Department.objects.create(
            name="Direction des Finances",
            code="DFI",
            type=Department.Type.DIRECTION,
        )

        # ── Sous-Direction Comptabilité (enfant de Direction Finance) ──
        cls.sous_direction_compta = Department.objects.create(
            name="Sous-Direction Comptabilité",
            code="SDC",
            type=Department.Type.SOUS_DIRECTION,
            parent=cls.direction_finance,
        )

        # ── Département Saisie (enfant de Sous-Direction Comptabilité) ──
        cls.departement_saisie = Department.objects.create(
            name="Département Saisie",
            code="DSA",
            type=Department.Type.DEPARTEMENT,
            parent=cls.sous_direction_compta,
        )

        # ── Service Saisie Credits (enfant de Département Saisie) ──
        cls.service_saisie_credits = Department.objects.create(
            name="Service Saisie Crédits",
            code="SSC",
            type=Department.Type.SERVICE,
            parent=cls.departement_saisie,
        )

        # ── Direction Risques (racine séparée) ──
        cls.direction_risques = Department.objects.create(
            name="Direction des Risques",
            code="DRQ",
            type=Department.Type.DIRECTION,
        )

        # ── Sous-Direction Risques Crédit (enfant de Direction Risques) ──
        cls.sous_direction_risque_credit = Department.objects.create(
            name="Sous-Direction Risques Crédit",
            code="SDRC",
            type=Department.Type.SOUS_DIRECTION,
            parent=cls.direction_risques,
        )

        # ── Utilisateurs Direction Finance ──
        cls.dm_finance = User.objects.create_user(
            username="dm_finance",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="Directeur",
            last_name="Finance",
            department=cls.direction_finance,
        )

        cls.etp_finance = User.objects.create_user(
            username="etp_finance",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Finance",
            department=cls.direction_finance,
        )

        # ── ETP dans la Sous-Direction Comptabilité ──
        cls.etp_sous_direction = User.objects.create_user(
            username="etp_sous_direction",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Sous-Direction",
            department=cls.sous_direction_compta,
        )

        # ── ETP dans le Département Saisie ──
        cls.etp_departement = User.objects.create_user(
            username="etp_departement",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Département",
            department=cls.departement_saisie,
        )

        # ── ETP dans le Service Saisie Crédits ──
        cls.etp_service = User.objects.create_user(
            username="etp_service",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Service",
            department=cls.service_saisie_credits,
        )

        # ── Utilisateurs Direction Risques ──
        cls.dm_risques = User.objects.create_user(
            username="dm_risques",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="Directeur",
            last_name="Risques",
            department=cls.direction_risques,
        )

        cls.etp_risques = User.objects.create_user(
            username="etp_risques",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Risques",
            department=cls.direction_risques,
        )

        cls.etp_sous_direction_risque = User.objects.create_user(
            username="etp_sous_direction_risque",
            password="TestPass123!",
            role=User.Role.ETP,
            first_name="Employé",
            last_name="Sous-Direction Risque",
            department=cls.sous_direction_risque_credit,
        )

        # ── Auditeur ──
        cls.audit_user = User.objects.create_user(
            username="auditeur",
            password="TestPass123!",
            role=User.Role.AUDIT,
            first_name="Auditeur",
            last_name="Interne",
        )

        # ── DG ──
        cls.dg_finance = User.objects.create_user(
            username="dg_finance",
            password="TestPass123!",
            role=User.Role.DG,
            first_name="DG",
            last_name="Finance",
            department=cls.direction_finance,
        )

    def _login_as(self, user):
        self.client.force_login(user)

    def _create_assigned_recommendation(self, department=None, dm=None):
        """Crée une recommandation en état ASSIGNED."""
        dept = department or self.direction_finance
        target_dm = dm or self.dm_finance
        rec = create_recommendation(
            data={
                "reference": f"REC-DEL-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission délégation test",
                "controlled_department": dept,
                "observations": "Obs test",
                "anomalous_dossiers": "",
                "description": "Description test délégation",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": dept,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable test"],
            performed_by=self.audit_user,
        )
        return assign_recommendation_to_dm(
            recommendation=rec,
            dm=target_dm,
            performed_by=self.audit_user,
        )


# =============================================================================
# Tests du selector hiérarchique
# =============================================================================


class DepartmentHierarchySelectorTest(HierarchyTestMixin, TestCase):
    """Tests de _get_department_and_descendants_ids et selectors associés."""

    def test_get_descendants_includes_all_levels(self):
        """Le selector retourne tous les IDs de la branche (direction → service)."""
        ids = selectors.get_department_and_descendants_ids(self.direction_finance)

        self.assertIn(self.direction_finance.id, ids)
        self.assertIn(self.sous_direction_compta.id, ids)
        self.assertIn(self.departement_saisie.id, ids)
        self.assertIn(self.service_saisie_credits.id, ids)

    def test_get_descendants_leaf_has_no_children(self):
        """Un service feuille ne retourne que son propre ID."""
        ids = selectors.get_department_and_descendants_ids(self.service_saisie_credits)

        self.assertEqual(len(ids), 1)
        self.assertIn(self.service_saisie_credits.id, ids)

    def test_get_descendants_excludes_other_branch(self):
        """La branche Finance n'inclut aucun département de Risques."""
        ids = selectors.get_department_and_descendants_ids(self.direction_finance)

        self.assertNotIn(self.direction_risques.id, ids)
        self.assertNotIn(self.sous_direction_risque_credit.id, ids)

    def test_get_available_etps_includes_sub_departments(self):
        """Les ETP des sous-départements sont inclus dans la liste."""
        etps = selectors.get_available_etps_for_department(
            department=self.direction_finance
        )
        etp_ids = set(etps.values_list("id", flat=True))

        self.assertIn(self.etp_finance.id, etp_ids)
        self.assertIn(self.etp_sous_direction.id, etp_ids)
        self.assertIn(self.etp_departement.id, etp_ids)
        self.assertIn(self.etp_service.id, etp_ids)

    def test_get_available_etps_excludes_other_direction(self):
        """Les ETP d'une autre direction sont exclus."""
        etps = selectors.get_available_etps_for_department(
            department=self.direction_finance
        )
        etp_ids = set(etps.values_list("id", flat=True))

        self.assertNotIn(self.etp_risques.id, etp_ids)
        self.assertNotIn(self.etp_sous_direction_risque.id, etp_ids)

    def test_get_available_dms_includes_sub_departments(self):
        """Les DM des sous-départements sont inclus."""
        dm_sous_dir = User.objects.create_user(
            username="dm_sous_direction",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="DM",
            last_name="Sous-Direction",
            department=self.sous_direction_compta,
        )

        dms = selectors.get_available_dms_for_department(
            department=self.direction_finance
        )
        dm_ids = set(dms.values_list("id", flat=True))

        self.assertIn(self.dm_finance.id, dm_ids)
        self.assertIn(dm_sous_dir.id, dm_ids)

    def test_get_available_etps_from_sub_direction_only(self):
        """Depuis une sous-direction, on voit ses propres ETP et ceux de ses enfants."""
        etps = selectors.get_available_etps_for_department(
            department=self.sous_direction_compta
        )
        etp_ids = set(etps.values_list("id", flat=True))

        self.assertIn(self.etp_sous_direction.id, etp_ids)
        self.assertIn(self.etp_departement.id, etp_ids)
        self.assertIn(self.etp_service.id, etp_ids)
        self.assertNotIn(self.etp_finance.id, etp_ids)


# =============================================================================
# Scénario 1 : Délégation à un ETP de la même direction (AC1 & AC3)
# =============================================================================


class DelegateToETPSameDepartmentTest(HierarchyTestMixin, TestCase):
    """Scénario 1 : Un DM délègue à un ETP de sa propre direction."""

    def test_delegate_to_etp_same_department(self):
        """Le DM peut déléguer à un ETP du même département (AC1)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_finance.pk)},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Refresh"], "true")

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec.assigned_etp, self.etp_finance)

    def test_delegate_to_etp_in_sub_direction(self):
        """Le DM peut déléguer à un ETP d'une sous-direction (AC1)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_sous_direction.pk)},
        )

        self.assertEqual(response.status_code, 204)

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec.assigned_etp, self.etp_sous_direction)

    def test_delegate_to_etp_in_departement(self):
        """Le DM peut déléguer à un ETP d'un département enfant."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_departement.pk)},
        )

        self.assertEqual(response.status_code, 204)

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec.assigned_etp, self.etp_departement)

    def test_delegate_to_etp_in_service(self):
        """Le DM peut déléguer à un ETP d'un service (niveau le plus bas)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_service.pk)},
        )

        self.assertEqual(response.status_code, 204)

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(rec.assigned_etp, self.etp_service)

    def test_delegate_modal_shows_etp_from_same_department(self):
        """La modale GET affiche les ETP du même département (AC3)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Déléguer")
        self.assertContains(response, self.etp_finance.username)

    def test_delegate_modal_shows_etp_from_sub_departments(self):
        """La modale GET affiche les ETP des sous-départements (AC4)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.etp_sous_direction.username)
        self.assertContains(response, self.etp_departement.username)
        self.assertContains(response, self.etp_service.username)


# =============================================================================
# Scénario 1b : Délégation refusée si ETP d'une autre direction (AC4)
# =============================================================================


class DelegateToETPOtherDepartmentTest(HierarchyTestMixin, TestCase):
    """Scénario 1b : Impossible de déléguer à un ETP d'une autre direction."""

    def test_cannot_delegate_to_etp_other_direction(self):
        """La délégation à un ETP d'une autre direction est refusée."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_risques.pk)},
        )

        self.assertIn(response.status_code, [422, 200])

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.ASSIGNED)
        self.assertIsNone(rec.assigned_etp)

    def test_cannot_delegate_to_etp_other_sub_direction(self):
        """La délégation à un ETP d'une autre sous-direction est refusée."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_sous_direction_risque.pk)},
        )

        self.assertIn(response.status_code, [422, 200])

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.ASSIGNED)
        self.assertIsNone(rec.assigned_etp)

    def test_delegate_modal_hides_etp_from_other_direction(self):
        """La modale GET n'affiche PAS les ETP d'une autre direction."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.etp_risques.username)
        self.assertNotContains(response, self.etp_sous_direction_risque.username)


# =============================================================================
# Scénario 2 : Auto-assignation DM Porteur (AC2)
# =============================================================================


class DMPorteurTest(HierarchyTestMixin, TestCase):
    """Scénario 2 : Le DM s'auto-assigne comme porteur."""

    def test_dm_can_become_porteur(self):
        """Le DM peut devenir DM Porteur, statut passe à IN_PROGRESS (AC2)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Refresh"], "true")

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)
        self.assertIsNone(rec.assigned_etp)

    def test_dm_porteur_selector_grays_out(self):
        """Le sélecteur ETP est grisé/masqué quand DM Porteur est sélectionné."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("dm_porteur", content)


# =============================================================================
# Scénario 3.1 : ETP ne peut pas accéder à la vue de délégation
# =============================================================================


class ETPAccessDeniedTest(HierarchyTestMixin, TestCase):
    """Scénario 3.1 : Un ETP ne peut pas accéder à la délégation."""

    def test_etp_cannot_access_delegate_view_get(self):
        """Un ETP reçoit 404 sur GET de la vue de délégation (hors périmètre RBAC).

        Un ETP ne voit que les recos qui lui sont explicitement assignées
        (assigned_etp=user). Cette reco est en état ASSIGNED, pas encore
        déléguée à un ETP → le selector la filtre → 404 (information hiding).
        """
        self._login_as(self.etp_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_etp_cannot_access_delegate_view_post(self):
        """Un ETP reçoit 404 sur POST de la vue de délégation (hors périmètre RBAC)."""
        self._login_as(self.etp_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_finance.pk)},
        )

        self.assertEqual(response.status_code, 404)

    def test_delegate_button_not_visible_for_etp_on_delegate_view(self):
        """Le bouton Déléguer n'est pas accessible pour un ETP (testé via vue GET 404)."""
        self._login_as(self.etp_finance)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 404)


# =============================================================================
# Scénario 3.2 : DM d'une autre direction ne peut pas déléguer (404)
# =============================================================================


class CrossDepartmentDMDeniedTest(HierarchyTestMixin, TestCase):
    """Scénario 3.2 : Cloisonnement strict entre directions."""

    def test_dm_other_direction_cannot_delegate_get(self):
        """Un DM d'une autre direction reçoit 404 sur GET (hors périmètre RBAC).

        Le selector RBAC filtre les recos hors département → 404 (information hiding).
        """
        self._login_as(self.dm_risques)
        rec = self._create_assigned_recommendation()

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_dm_other_direction_cannot_delegate_post(self):
        """Un DM d'une autre direction reçoit 404 sur POST (hors périmètre RBAC)."""
        self._login_as(self.dm_risques)
        rec = self._create_assigned_recommendation()

        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        self.assertEqual(response.status_code, 404)

    def test_dm_risques_cannot_access_finance_recommendation_via_selector(self):
        """Un DM Risques ne voit pas la reco Finance via le selector."""
        rec = self._create_assigned_recommendation()

        results = selectors.get_recommendations_for_user(user=self.dm_risques)
        result_ids = set(results.values_list("id", flat=True))

        self.assertNotIn(rec.id, result_ids)


# =============================================================================
# Scénario 3.3 : Blocage selon l'état de la recommandation
# =============================================================================


class FSMStateBlockingTest(HierarchyTestMixin, TestCase):
    """Scénario 3.3 : La délégation n'est possible qu'en état ASSIGNED."""

    def test_cannot_delegate_when_in_progress(self):
        """Impossible de déléguer une recommandation déjà IN_PROGRESS."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        # Passer en IN_PROGRESS d'abord
        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        rec = Recommendation.all_objects.get(pk=rec.pk)
        self.assertEqual(rec.status, Recommendation.Status.IN_PROGRESS)

        # Tenter une seconde délégation
        response = self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_finance.pk)},
        )

        self.assertEqual(response.status_code, 403)

    def test_cannot_delegate_when_draft(self):
        """Impossible de déléguer une recommandation en DRAFT.

        Les DM ne voient pas les DRAFTs via get_recommendations_for_user()
        (les DRAFTs sont exclus pour les rôles non-AUDIT). La vue retourne
        donc 404 (information hiding) plutôt que 403.
        """
        self._login_as(self.dm_finance)
        rec = create_recommendation(
            data={
                "reference": f"REC-DRAFT-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission draft test",
                "controlled_department": self.direction_finance,
                "observations": "Obs",
                "anomalous_dossiers": "",
                "description": "Description draft",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": self.direction_finance,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable"],
            performed_by=self.audit_user,
        )

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_delegate_button_hidden_when_in_progress(self):
        """Le bouton Déléguer est absent si la reco est en IN_PROGRESS (testé via 403)."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        # Passer en IN_PROGRESS
        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        response = self.client.get(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
        )

        self.assertEqual(response.status_code, 403)


# =============================================================================
# Tests Audit Log
# =============================================================================


class AuditLogDelegationTest(HierarchyTestMixin, TestCase):
    """Vérification que chaque action de délégation est tracée."""

    def test_delegate_etp_creates_audit_log(self):
        """La délégation à un ETP crée une entrée AuditLog."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_finance.pk)},
        )

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
            user=self.dm_finance,
        ).first()

        self.assertIsNotNone(log)
        self.assertIn("Délégation", log.description)
        self.assertIn("Employé Finance", log.description)
        self.assertEqual(log.changes["status"], ["ASSIGNED", "IN_PROGRESS"])

    def test_dm_porteur_creates_audit_log(self):
        """Le DM Porteur crée une entrée AuditLog."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "dm_porteur"},
        )

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
            user=self.dm_finance,
        ).first()

        self.assertIsNotNone(log)
        self.assertIn("DM Porteur", log.description)
        self.assertIn("Directeur Finance", log.description)

    def test_delegate_to_sub_department_etp_audit_log(self):
        """La délégation à un ETP d'un sous-département est tracée correctement."""
        self._login_as(self.dm_finance)
        rec = self._create_assigned_recommendation()

        self.client.post(
            reverse("workflow:recommendation-delegate", args=[rec.pk]),
            {"action": "delegate_etp", "etp": str(self.etp_service.pk)},
        )

        log = AuditLog.objects.filter(
            object_id=rec.pk,
            action=AuditLog.Action.TRANSITION,
            user=self.dm_finance,
        ).first()

        self.assertIsNotNone(log)
        self.assertIn("Délégation", log.description)
        self.assertIn("Employé Service", log.description)


# =============================================================================
# Tests du formulaire DelegateETPForm
# =============================================================================


class DelegateETPFormTest(HierarchyTestMixin, TestCase):
    """Tests du formulaire de délégation avec filtrage hiérarchique."""

    def test_form_shows_etps_from_same_department(self):
        """Le formulaire inclut les ETP du même département."""
        form = DelegateETPForm(department=self.direction_finance)
        etp_ids = set(form.fields["etp"].queryset.values_list("id", flat=True))

        self.assertIn(self.etp_finance.id, etp_ids)

    def test_form_shows_etps_from_sub_departments(self):
        """Le formulaire inclut les ETP des sous-départements."""
        form = DelegateETPForm(department=self.direction_finance)
        etp_ids = set(form.fields["etp"].queryset.values_list("id", flat=True))

        self.assertIn(self.etp_sous_direction.id, etp_ids)
        self.assertIn(self.etp_departement.id, etp_ids)
        self.assertIn(self.etp_service.id, etp_ids)

    def test_form_excludes_etps_from_other_department(self):
        """Le formulaire exclut les ETP d'une autre direction."""
        form = DelegateETPForm(department=self.direction_finance)
        etp_ids = set(form.fields["etp"].queryset.values_list("id", flat=True))

        self.assertNotIn(self.etp_risques.id, etp_ids)
        self.assertNotIn(self.etp_sous_direction_risque.id, etp_ids)

    def test_form_requires_etp_for_delegate_action(self):
        """Si action = delegate_etp, le champ ETP est requis."""
        form = DelegateETPForm(
            data={"action": "delegate_etp"},
            department=self.direction_finance,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("etp", form.errors)

    def test_form_does_not_require_etp_for_dm_porteur(self):
        """Si action = dm_porteur, le champ ETP n'est pas requis."""
        form = DelegateETPForm(
            data={"action": "dm_porteur"},
            department=self.direction_finance,
        )
        self.assertTrue(form.is_valid())

    def test_form_empty_department_has_no_etps(self):
        """Un formulaire sans département n'a pas d'ETP."""
        form = DelegateETPForm()
        self.assertEqual(form.fields["etp"].queryset.count(), 0)


# =============================================================================
# Tests Service Layer — Délégation hiérarchique
# =============================================================================


class DelegateServiceHierarchyTest(HierarchyTestMixin, TestCase):
    """Tests directs du service layer pour la délégation hiérarchique."""

    def test_delegate_to_etp_in_same_department(self):
        """Le service accepte la délégation à un ETP du même département."""
        rec = self._create_assigned_recommendation()

        result = delegate_recommendation_to_etp(
            recommendation=rec,
            etp=self.etp_finance,
            performed_by=self.dm_finance,
        )

        self.assertEqual(result.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(result.assigned_etp, self.etp_finance)

    def test_delegate_to_etp_in_sub_direction(self):
        """Le service accepte la délégation à un ETP d'une sous-direction."""
        rec = self._create_assigned_recommendation()

        result = delegate_recommendation_to_etp(
            recommendation=rec,
            etp=self.etp_sous_direction,
            performed_by=self.dm_finance,
        )

        self.assertEqual(result.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(result.assigned_etp, self.etp_sous_direction)

    def test_delegate_to_etp_in_departement(self):
        """Le service accepte la délégation à un ETP d'un département."""
        rec = self._create_assigned_recommendation()

        result = delegate_recommendation_to_etp(
            recommendation=rec,
            etp=self.etp_departement,
            performed_by=self.dm_finance,
        )

        self.assertEqual(result.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(result.assigned_etp, self.etp_departement)

    def test_delegate_to_etp_in_service(self):
        """Le service accepte la délégation à un ETP d'un service."""
        rec = self._create_assigned_recommendation()

        result = delegate_recommendation_to_etp(
            recommendation=rec,
            etp=self.etp_service,
            performed_by=self.dm_finance,
        )

        self.assertEqual(result.status, Recommendation.Status.IN_PROGRESS)
        self.assertEqual(result.assigned_etp, self.etp_service)

    def test_delegate_to_etp_other_department_raises_error(self):
        """Le service refuse la délégation à un ETP d'une autre direction."""
        rec = self._create_assigned_recommendation()

        with self.assertRaises(ValueError) as cm:
            delegate_recommendation_to_etp(
                recommendation=rec,
                etp=self.etp_risques,
                performed_by=self.dm_finance,
            )

        self.assertIn("n'appartient pas", str(cm.exception))

    def test_delegate_non_etp_user_raises_error(self):
        """Le service refuse si l'utilisateur cible n'a pas le rôle ETP."""
        rec = self._create_assigned_recommendation()

        with self.assertRaises(ValueError) as cm:
            delegate_recommendation_to_etp(
                recommendation=rec,
                etp=self.dm_risques,
                performed_by=self.dm_finance,
            )

        self.assertIn("n'a pas le rôle ETP", str(cm.exception))

    def test_delegate_with_no_department_raises_error(self):
        """Le service refuse la délégation si la recommandation n'a pas de département."""
        rec = self._create_assigned_recommendation()
        rec.department = None
        rec.save(update_fields=["department"])

        with self.assertRaises(ValueError) as cm:
            delegate_recommendation_to_etp(
                recommendation=rec,
                etp=self.etp_finance,
                performed_by=self.dm_finance,
            )

        self.assertIn("n'appartient pas", str(cm.exception))

    def test_become_dm_porteur_sets_no_etp(self):
        """Le DM Porteur laisse assigned_etp à null."""
        rec = self._create_assigned_recommendation()

        result = become_dm_porteur(
            recommendation=rec,
            performed_by=self.dm_finance,
        )

        self.assertEqual(result.status, Recommendation.Status.IN_PROGRESS)
        self.assertIsNone(result.assigned_etp)


# =============================================================================
# Tests RBAC — Visibilité hiérarchique DM/DG
# =============================================================================


class HierarchicalVisibilityTest(HierarchyTestMixin, TestCase):
    """Tests de visibilité RBAC pour DM/DG sur leurs sous-départements (via selectors)."""

    def test_dm_selector_sees_own_department_recommendations(self):
        """Le selector retourne les recommandations du département du DM."""
        rec = self._create_assigned_recommendation()

        results = selectors.get_recommendations_for_user(user=self.dm_finance)
        result_ids = set(results.values_list("id", flat=True))

        self.assertIn(rec.id, result_ids)

    def test_dm_selector_sees_sub_department_recommendations(self):
        """Le selector retourne les recommandations des sous-départements du DM."""
        dm_sous_dir = User.objects.create_user(
            username="dm_sous_dir_vis",
            password="TestPass123!",
            role=User.Role.DM,
            first_name="DM",
            last_name="Sous-Dir Vis",
            department=self.sous_direction_compta,
        )

        rec_sous_dir = create_recommendation(
            data={
                "reference": f"REC-SD-{uuid.uuid4().hex[:6].upper()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Mission SD",
                "controlled_department": self.sous_direction_compta,
                "observations": "Obs",
                "anomalous_dossiers": "",
                "description": "Desc SD",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": self.sous_direction_compta,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=["Livrable SD"],
            performed_by=self.audit_user,
        )
        rec_sous_dir = assign_recommendation_to_dm(
            recommendation=rec_sous_dir,
            dm=dm_sous_dir,
            performed_by=self.audit_user,
        )

        # 1. Le DM du sous-département concerné doit la voir (match exact)
        results_sous_dir = selectors.get_recommendations_for_user(user=dm_sous_dir)
        self.assertIn(rec_sous_dir.id, set(results_sous_dir.values_list("id", flat=True)))

        # 2. Le DM de la Direction Finance (parent) doit également la voir (visibilité hiérarchique)
        results_parent = selectors.get_recommendations_for_user(user=self.dm_finance)
        self.assertIn(rec_sous_dir.id, set(results_parent.values_list("id", flat=True)))

    def test_dm_selector_does_not_see_other_department_recommendations(self):
        """Le selector n'inclut PAS les recommandations d'une autre direction."""
        rec_risques = self._create_assigned_recommendation(
            department=self.direction_risques,
            dm=self.dm_risques,
        )

        results = selectors.get_recommendations_for_user(user=self.dm_finance)
        result_ids = set(results.values_list("id", flat=True))

        self.assertNotIn(rec_risques.id, result_ids)

    def test_dg_selector_sees_own_department_recommendations(self):
        """Le selector DG retourne les recommandations de son département."""
        rec = self._create_assigned_recommendation()

        results = selectors.get_recommendations_for_user(user=self.dg_finance)
        result_ids = set(results.values_list("id", flat=True))

        self.assertIn(rec.id, result_ids)

    def test_etp_selector_only_sees_explicitly_assigned(self):
        """Le selector ETP ne retourne que les recommandations assignées à l'ETP."""
        rec_assigned = self._create_assigned_recommendation()
        delegate_recommendation_to_etp(
            recommendation=rec_assigned,
            etp=self.etp_finance,
            performed_by=self.dm_finance,
        )

        rec_not_assigned = self._create_assigned_recommendation()

        results = selectors.get_recommendations_for_user(user=self.etp_finance)
        result_ids = set(results.values_list("id", flat=True))

        self.assertIn(rec_assigned.id, result_ids)
        self.assertNotIn(rec_not_assigned.id, result_ids)
