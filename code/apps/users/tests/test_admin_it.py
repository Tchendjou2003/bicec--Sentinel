"""
Users App — Tests Story 1.4 : Admin Dashboard, Organigramme & Comptes

Vérifie les vues Admin IT : dashboard, organigramme CRUD, création de comptes
coquilles vides, et redirection login.

Acceptance Criteria couverts :
    - AC1 : Redirection Admin vers /auth/admin/dashboard/
    - AC2 : Gestion organigramme multi-niveaux
    - AC3 : Hiérarchie REGION → AGENCE
    - AC4 : Création coquille vide (sans rôle, sans champ rôle)
"""
from django.test import Client, TestCase
from django.urls import reverse

from apps.users.models import Department, User
from apps.audit.models import AuditLog


class AdminDashboardAccessTest(TestCase):
    """Tests d'accès au tableau de bord Admin (AC1)."""

    def setUp(self):
        self.client = Client()
        self.dashboard_url = reverse("auth:admin-dashboard")
        self.login_url = reverse("auth:login")

        # Admin IT
        self.admin_user = User.objects.create_user(
            username="admin_it",
            password="testpass123",
            email="admin@bicec.cm",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        # Non-admin
        self.dm_user = User.objects.create_user(
            username="dm",
            password="testpass123",
            email="dm@bicec.cm",
            role=User.Role.DM,
        )

    def test_admin_dashboard_requires_login(self):
        """Un utilisateur non connecté est redirigé vers le login."""
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(
            response,
            f"{self.login_url}?next={self.dashboard_url}",
        )

    def test_admin_dashboard_accessible_for_admin(self):
        """L'Admin peut accéder au dashboard."""
        self.client.force_login(self.admin_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/dashboard.html")

    def test_admin_dashboard_forbidden_for_non_admin(self):
        """Un DM reçoit un 403 Forbidden."""
        self.client.force_login(self.dm_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_shows_stats(self):
        """Le dashboard affiche les stats (total_users, total_shell, total_departments)."""
        self.client.force_login(self.admin_user)
        response = self.client.get(self.dashboard_url)
        self.assertIn("total_users", response.context)
        self.assertIn("total_shell", response.context)
        self.assertIn("total_departments", response.context)

    def test_login_redirects_admin_to_dashboard(self):
        """AC1 — L'Admin est redirigé vers /auth/admin/dashboard/ après login."""
        response = self.client.post(self.login_url, {
            "username": "admin_it",
            "password": "testpass123",
        })
        self.assertRedirects(response, self.dashboard_url)


class OrganigrammeTest(TestCase):
    """Tests CRUD organigramme (AC2, AC3)."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_it",
            password="testpass123",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.force_login(self.admin_user)

    def test_organigramme_list_renders(self):
        """La page organigramme s'affiche."""
        response = self.client.get(reverse("auth:organigramme-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/organigramme_list.html")

    def test_create_department_get(self):
        """Le formulaire de création de département s'affiche."""
        response = self.client.get(reverse("auth:department-create"))
        self.assertEqual(response.status_code, 200)

    def test_create_department_post(self):
        """AC2 — Créer un département via POST."""
        response = self.client.post(reverse("auth:department-create"), {
            "name": "Direction Générale",
            "code": "DG",
            "type": Department.Type.DG,
        })
        self.assertEqual(Department.objects.count(), 1)
        dept = Department.objects.first()
        self.assertEqual(dept.name, "Direction Générale")
        self.assertEqual(dept.type, Department.Type.DG)
        self.assertIsNone(dept.parent)
        
        # Test NFR-SEC-05 (AuditLog)
        self.assertEqual(AuditLog.objects.filter(content_type="Department").count(), 1)
        audit = AuditLog.objects.first()
        self.assertEqual(audit.action, AuditLog.Action.CREATE)
        self.assertEqual(audit.user, self.admin_user)

    def test_create_hierarchie_multi_niveaux(self):
        """AC2 — Créer une arborescence DG → DIRECTION → DEPARTEMENT."""
        dg = Department.objects.create(
            name="Direction Générale", code="DG", type=Department.Type.DG,
        )
        direction = Department.objects.create(
            name="Direction des Opérations", code="DOP",
            type=Department.Type.DIRECTION, parent=dg,
        )
        dept = Department.objects.create(
            name="Département Crédit", code="DCRED",
            type=Department.Type.DEPARTEMENT, parent=direction,
        )
        self.assertEqual(dept.parent, direction)
        self.assertEqual(direction.parent, dg)
        self.assertIn(direction, dg.children.all())

    def test_create_region_agence_hierarchy(self):
        """AC3 — La hiérarchie REGION → AGENCE est correctement persistée."""
        region = Department.objects.create(
            name="Direction Régionale Littoral", code="DRL",
            type=Department.Type.REGION,
        )
        agence = Department.objects.create(
            name="Agence Akwa", code="AKW",
            type=Department.Type.AGENCE, parent=region,
        )
        self.assertEqual(agence.parent, region)
        self.assertEqual(agence.type, Department.Type.AGENCE)
        self.assertIn(agence, region.children.all())

    def test_edit_department(self):
        """Modifier un département via POST."""
        dept = Department.objects.create(
            name="Test", code="TST", type=Department.Type.SERVICE,
        )
        response = self.client.post(
            reverse("auth:department-edit", kwargs={"pk": dept.pk}),
            {
                "name": "Test Modifié",
                "code": "TST",
                "type": Department.Type.SERVICE,
                "is_active": True,
            },
        )
        dept.refresh_from_db()
        self.assertEqual(dept.name, "Test Modifié")

        # Test NFR-SEC-05 (AuditLog)
        self.assertTrue(AuditLog.objects.filter(content_type="Department", action=AuditLog.Action.UPDATE).exists())
        
    def test_department_form_excludes_self_from_parent(self):
        """Un département ne peut pas être son propre parent."""
        dept = Department.objects.create(
            name="Test", code="TST", type=Department.Type.SERVICE,
        )
        response = self.client.get(reverse("auth:department-edit", kwargs={"pk": dept.pk}))
        form = response.context["form"]
        self.assertNotIn(dept, form.fields["parent"].queryset)

    def test_organigramme_drilldown_htmx(self):
        """Le drilldown retourne les enfants directs (via HTMX)."""
        dg = Department.objects.create(name="DG", code="DG", type=Department.Type.DG)
        dir1 = Department.objects.create(name="DIR1", code="D1", type=Department.Type.DIRECTION, parent=dg)
        
        # Requête HTMX sur la racine
        response = self.client.get(reverse("auth:organigramme-list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/partials/organigramme_drilldown.html")
        self.assertIn(dg, response.context["departments"])
        self.assertNotIn(dir1, response.context["departments"])
        
        # Requête HTMX sur DG
        response = self.client.get(f"{reverse('auth:organigramme-list')}?parent_id={dg.pk}", HTTP_HX_REQUEST="true")
        self.assertIn(dir1, response.context["departments"])
        self.assertEqual(response.context["breadcrumb"][0], dg)

    def test_organigramme_search(self):
        """La vue de recherche filtre correctement par nom ou code."""
        Department.objects.create(name="Direction Réseau", code="DRES")
        Department.objects.create(name="Service Informatique", code="SIT")
        
        response = self.client.get(f"{reverse('auth:department-search')}?q=rés")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/partials/organigramme_search_results.html")
        results = response.context["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "DRES")

    def test_department_circular_reference(self):
        """Vérifie que la boucle A -> B -> A est interdite dans le formulaire."""
        dept_a = Department.objects.create(name="Dept A", code="A")
        dept_b = Department.objects.create(name="Dept B", code="B", parent=dept_a)
        
        # Essayer de mettre B comme parent de A
        response = self.client.post(
            reverse("auth:department-edit", kwargs={"pk": dept_a.pk}),
            {
                "name": "Dept A",
                "code": "A",
                "type": Department.Type.DIRECTION,
                "is_active": True,
                "parent": dept_b.pk,
            },
        )
        self.assertFormError(response.context["form"], "parent", "Référence circulaire détectée : « Dept B » est déjà un descendant de « Dept A ».")


class ITUserCreationTest(TestCase):
    """Tests création de comptes coquilles vides (AC4)."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_it",
            password="testpass123",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.create_url = reverse("auth:admin-user-create")
        self.list_url = reverse("auth:admin-user-list")

    def test_user_list_renders(self):
        """La page liste utilisateurs s'affiche."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/user_list.html")

    def test_user_create_form_renders(self):
        """Le formulaire de création s'affiche."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/user_create.html")

    def test_user_create_form_has_no_role_field(self):
        """AC4 — Le formulaire ne contient PAS de champ rôle."""
        response = self.client.get(self.create_url)
        form = response.context["form"]
        self.assertNotIn("role", form.fields)
        self.assertNotIn("is_external", form.fields)
        self.assertNotIn("is_audit_admin", form.fields)

    def test_create_shell_account(self):
        """AC4 — Créer un compte coquille vide via POST."""
        response = self.client.post(self.create_url, {
            "username": "new_user",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@bicec.cm",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertRedirects(response, self.list_url)
        new_user = User.objects.get(username="new_user")
        self.assertEqual(new_user.role, "")  # Coquille vide
        self.assertFalse(new_user.is_external)
        self.assertFalse(new_user.is_audit_admin)
        self.assertEqual(new_user.first_name, "Jean")
        self.assertEqual(new_user.email, "jean.dupont@bicec.cm")

        # Test NFR-SEC-05 (AuditLog)
        self.assertTrue(AuditLog.objects.filter(content_type="User", action=AuditLog.Action.CREATE, object_id=new_user.pk).exists())

    def test_shell_account_is_captured_by_middleware(self):
        """AC4/FR37 — Le compte coquille vide est bien détecté comme shell_account."""
        self.client.post(self.create_url, {
            "username": "shell_test",
            "first_name": "Test",
            "last_name": "Shell",
            "email": "test.shell@bicec.cm",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        new_user = User.objects.get(username="shell_test")
        self.assertTrue(new_user.is_shell_account)

    def test_create_user_requires_all_fields(self):
        """Le formulaire refuse un POST sans les champs requis."""
        response = self.client.post(self.create_url, {
            "username": "incomplete",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertEqual(response.status_code, 200)  # Re-renders form
        self.assertFalse(User.objects.filter(username="incomplete").exists())

    def test_user_list_filter_shell(self):
        """Le filtre 'shell' ne montre que les coquilles vides."""
        User.objects.create_user(username="shell1", password="x")
        User.objects.create_user(username="actif1", password="x", role=User.Role.DM)
        response = self.client.get(f"{self.list_url}?filtre=shell")
        users = response.context["users"]
        for u in users:
            self.assertEqual(u.role, "")


class DepartmentDeleteTest(TestCase):
    """Tests de la suppression (soft-delete) de département (H4 — Code Review)."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_it",
            password="testpass123",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.force_login(self.admin_user)

    def test_soft_delete_department_success(self):
        """Un département sans enfants ni utilisateurs est désactivé."""
        dept = Department.objects.create(
            name="À supprimer", code="DEL", type=Department.Type.SERVICE,
        )
        url = reverse("auth:department-delete", kwargs={"pk": dept.pk})
        response = self.client.post(url)
        dept.refresh_from_db()
        self.assertFalse(dept.is_active)

    def test_soft_delete_blocked_by_active_children(self):
        """Un département avec des sous-structures actives ne peut pas être supprimé."""
        parent = Department.objects.create(
            name="Parent", code="PAR", type=Department.Type.DIRECTION,
        )
        Department.objects.create(
            name="Enfant", code="ENF", type=Department.Type.SERVICE, parent=parent,
        )
        url = reverse("auth:department-delete", kwargs={"pk": parent.pk})
        self.client.post(url)
        parent.refresh_from_db()
        self.assertTrue(parent.is_active)  # Toujours actif — suppression refusée

    def test_soft_delete_blocked_by_active_users(self):
        """Un département avec des utilisateurs actifs ne peut pas être supprimé."""
        dept = Department.objects.create(
            name="Peuplé", code="PEU", type=Department.Type.SERVICE,
        )
        User.objects.create_user(
            username="rattaché", password="x", role=User.Role.ETP, department=dept,
        )
        url = reverse("auth:department-delete", kwargs={"pk": dept.pk})
        self.client.post(url)
        dept.refresh_from_db()
        self.assertTrue(dept.is_active)  # Toujours actif

    def test_soft_delete_creates_audit_log(self):
        """La suppression génère une trace dans l'AuditLog (NFR-SEC-05)."""
        dept = Department.objects.create(
            name="Auditable", code="AUD", type=Department.Type.SERVICE,
        )
        url = reverse("auth:department-delete", kwargs={"pk": dept.pk})
        self.client.post(url)
        self.assertTrue(
            AuditLog.objects.filter(
                content_type="Department",
                action=AuditLog.Action.DELETE,
                object_id=dept.pk,
            ).exists()
        )

    def test_soft_delete_htmx_returns_drilldown(self):
        """En requête HTMX, la suppression retourne le partial drilldown."""
        dept = Department.objects.create(
            name="HTMX Delete", code="HXD", type=Department.Type.SERVICE,
        )
        url = reverse("auth:department-delete", kwargs={"pk": dept.pk})
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_it/partials/organigramme_drilldown.html")
