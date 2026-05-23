# Story 1.4: Gestion de l'Organigramme et Création des Comptes (Admin)

Status: done

## Story

As a **Admin (anciennement RSSI/Support IT)**,
I want **créer et structurer l'organigramme (DG, Directions, Sous-Directions, Départements, Services, Directions Régionales, Agences) et créer les comptes utilisateurs comme des « coquilles vides » (identité technique sans rôle métier)**,
so that **le système reflète fidèlement la structure hiérarchique de la BICEC et que le Directeur de l'Audit Interne puisse attribuer les rôles métiers aux comptes créés (ADR-10).**

## Acceptance Criteria

1. **Given** un profil Admin connecté,
   **When** il atterrit sur le système,
   **Then** il est redirigé vers un tableau de bord dédié dans l'interface principale (ex: `/auth/admin/dashboard/`) et non obligatoirement vers le Django Admin.
   
2. **Given** l'interface dédiée de gestion de l'organigramme dans Sentinel,
   **When** l'Admin crée une arborescence multi-niveaux (DG → DIRECTION → SOUS_DIRECTION → DEPARTEMENT → SERVICE),
   **Then** l'arborescence est sauvegardée dans le modèle `Department` (FR35) et la liste se met à jour via HTMX.
   **And** les types `DG`, `DIRECTION`, `SOUS_DIRECTION`, `DEPARTEMENT`, `SERVICE`, `REGION`, `AGENCE` sont disponibles.

3. **Given** l'interface de gestion de l'organigramme,
   **When** l'Admin crée une Direction Régionale (type `REGION`) avec des Agences rattachées,
   **Then** la hiérarchie REGION → AGENCE est correctement persistée.
   
4. **Given** l'interface dédiée de création d'utilisateurs dans Sentinel,
   **When** l'Admin crée un compte utilisateur avec nom, prénom, email et mot de passe,
   **Then** le compte créé n'a **aucun rôle métier** et ne peut accéder à aucune fonctionnalité métier (FR37).
   **And** le formulaire ne propose **aucun champ** permettant d'attribuer un rôle métier (`role`, `is_external`, `is_audit_admin` sont physiquement absents du formulaire).

## Tasks / Subtasks

- [x] Task 0: Alignement du modèle de données sur l'organigramme réel
  - [x] Enrichir `Department.Type` : DG, DIRECTION, SOUS_DIRECTION, DEPARTEMENT, SERVICE, REGION, AGENCE (supprimer FILIALE).
  - [x] Renommer `User.Role.RSSI` → `User.Role.ADMIN` (code interne + label).
  - [x] Générer et appliquer la migration `0004_enrich_organigramme` (avec data migration RSSI→ADMIN).
  - [x] Mettre à jour tous les fichiers source (views, admin, services, context_processors, tests, sidebar).

- [x] Task 1: Tableau de bord Admin et Navigation
  - [x] Mettre à jour `SentinelLoginView` pour rediriger le rôle `ADMIN` vers son dashboard applicatif.
  - [x] Créer la vue `AdminDashboardView` et le template associé.

- [x] Task 2: Interface de Gestion de l'Organigramme (UI Sentinel)
  - [x] Créer les vues (Lister, Ajouter, Modifier) pour gérer les `Department`.
  - [x] Créer les templates associés en utilisant HTMX et Tailwind CSS.
  - [x] Permettre la saisie hiérarchique (choix du parent et du type).

- [x] Task 3: Interface de Création de Comptes (UI Sentinel)
  - [x] Créer un formulaire Django `ITUserCreationForm` (nom, prénom, username, email, mot de passe).
  - [x] Créer la vue et le template pour lister et créer les "coquilles vides".

- [x] Task 4: Redirection des comptes sans rôle
  - [x] Valider que le compte "coquille vide" créé par l'Admin est capté par le middleware et renvoyé vers `/auth/pending/` (FR37).

## Dev Notes

- **Architecture Frontend:** L'Admin utilise la stack SSR + HTMX + Tailwind. Le Django Admin reste accessible en backup.
- **Sécurité (ADR-10):** L'interface de création d'utilisateurs de l'Admin garantit qu'il ne peut pas manipuler les droits (champs absents du formulaire).
- **Hiérarchie:** Le modèle `Department` supporte 7 types hiérarchiques avec auto-référence (champ `parent`).
- **Audit Interne:** La Direction de l'Audit Interne (DAI) est une `DIRECTION` dans l'organigramme mais ses membres ont le rôle applicatif `AUDIT` (pas `DM`). Ils ne peuvent pas recevoir de recommandations.

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (Thinking)

### Completion Notes List
- Task 0 complétée : modèle aligné, migration appliquée, tests mis à jour (conversation 51f1f0be).
- Task 1 complétée : `AdminDashboardView` créée avec stats KPI (total_users, total_shell, total_departments). `SentinelLoginView` redirige maintenant vers `auth:admin-dashboard` au lieu de `admin:index`.
- Task 2 complétée : `OrganigrammeListView`, `DepartmentCreateView`, `DepartmentEditView` avec modal HTMX et arborescence collapsible. Templates Tailwind créés dans `templates/admin_it/`.
- Task 3 complétée : `ITUserCreationForm` (hérite UserCreationForm, sans champ role/is_external/is_audit_admin), `ITUserCreateView`, `ITUserListView` avec filtres. Template de création avec rappel ADR-10.
- Task 4 validée : `is_shell_account` property testée — le middleware `RoleRequiredMiddleware` capture bien les comptes créés par l'Admin.
- Sidebar Admin mise à jour : liens `/rssi/` remplacés par les URLs `auth:*` correctes.
- `AdminRequiredMixin` créé pour protéger les vues Admin IT (rôle ADMIN ou is_staff).
- Sélecteurs ajoutés : `count_total_users()`, `count_departments()`, `get_department_tree()`.
- 16 tests unitaires créés dans `test_admin_it.py` couvrant les 4 ACs.

### Change Log
- 2026-05-04: Task 0 — Enrichissement Department.Type (7 types), renommage RSSI→ADMIN, data migration, mise à jour 10 fichiers source.
- 2026-05-08: Tasks 1-4 — Dashboard Admin, organigramme CRUD (HTMX), création comptes coquilles vides, tests.
- 2026-05-08: Code Review Fixes — Arborescence récursive HTMX (organigramme_node.html), exclusion du parent courant pour éviter les boucles (DepartmentForm), ajout AuditLog pour la création/édition (services.py, NFR-SEC-05).

### File List
- `apps/users/models.py` — Department.Type + User.Role (inchangé)
- `apps/users/views.py` — AdminDashboardView, OrganigrammeListView, DepartmentCreateView, DepartmentEditView, ITUserListView, ITUserCreateView, AdminRequiredMixin, redirection login ADMIN
- `apps/users/urls.py` — 6 nouvelles routes admin IT
- `apps/users/forms.py` — ITUserCreationForm, DepartmentForm (NOUVEAU)
- `apps/users/selectors.py` — count_total_users, count_departments, get_department_tree
- `apps/users/mixins.py` — AuditAdminRequiredMixin
- `apps/users/admin.py` — commentaires Admin
- `apps/users/services.py` — commentaire ADMIN
- `apps/users/context_processors.py` — clé sidebar ADMIN
- `apps/users/migrations/0004_enrich_organigramme.py` — migration + data migration
- `apps/users/tests/test_admin_it.py` — 16 tests couvrant AC1-AC4 (NOUVEAU)
- `apps/users/tests/test_models.py` — DepartmentFullHierarchyTest + fixtures
- `apps/users/tests/test_views.py` — fixtures + nom test
- `templates/admin_it/dashboard.html` — Dashboard Admin IT (NOUVEAU)
- `templates/admin_it/organigramme_list.html` — Liste organigramme HTMX (NOUVEAU)
- `templates/admin_it/user_list.html` — Liste utilisateurs Admin IT (NOUVEAU)
- `templates/admin_it/user_create.html` — Formulaire création coquille vide (NOUVEAU)
- `templates/admin_it/partials/organigramme_drilldown.html` — Arborescence et navigation drill-down (NOUVEAU)
- `templates/admin_it/partials/organigramme_search_results.html` — Résultats de recherche globale HTMX (NOUVEAU)
- `templates/admin_it/partials/department_form.html` — Modal formulaire département (NOUVEAU)
- `templates/partials/sidebar_admin.html` — Liens mis à jour vers auth:*
