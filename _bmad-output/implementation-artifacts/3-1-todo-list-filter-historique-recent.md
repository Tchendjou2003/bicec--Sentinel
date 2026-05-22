# Story 3.1: To-Do List Filter (Historique vs Récent)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier (DM) ou ETP**,
I want **séparer mon tableau de bord entre le "Backlog Historique" et les "Nouvelles Recos"**,
so that **je ne sois pas paralysé par le volume initial de 2000 recommandations.**

## Acceptance Criteria

1. **AC1 - Affichage par défaut (Nouvelles Recos)**
   - **Given** un utilisateur connecté (DM/ETP),
   - **When** il accède à sa liste de recommandations (`/audit/recommandations/`),
   - **Then** l'interface affiche par défaut uniquement les recommandations créées manuellement (non issues de l'import historique).
   - **And** cela correspond techniquement aux recommandations dont `import_tag` est vide ou nul.

2. **AC2 - Bascule vers le Backlog Historique**
   - **Given** la page de liste des recommandations,
   - **When** l'utilisateur clique sur le filtre/onglet "Backlog Historique",
   - **Then** le tableau se rafraîchit via HTMX sans rechargement complet de la page.
   - **And** le tableau affiche désormais uniquement les recommandations issues de l'import (où `import_tag` n'est pas vide).

3. **AC3 - UX du composant de filtrage**
   - **Given** la barre de filtres au-dessus du tableau,
   - **Then** l'option de filtrage "Historique / Récent" prend la forme d'un composant de type "Pills" ou "Tabs" très visible.
   - **And** l'état actif du filtre doit être clairement indiqué visuellement (Tailwind classes).

## Tasks / Subtasks

- [x] Task 1 : Backend - Logique de filtrage et RBAC (selectors & views)
  - [x] Subtask 1.1 : Modifier `apps/workflow/selectors.py` pour créer un sélecteur universel `get_recommendations_for_user(user, filters)` remplaçant `get_recommendations_for_audit`.
  - [x] Subtask 1.2 : **Application RBAC (FR28/FR32) dans le sélecteur** :
    - Audit : Accès à tout.
    - DG : Filtre sur `department=user.department` ET `exclude(status='DRAFT')`.
    - DM : Filtre sur `department=user.department` ET `exclude(status='DRAFT')`.
    - ETP : Filtre sur `assigned_etp=user` ET `exclude(status='DRAFT')`.
  - [x] Subtask 1.3 : **Optimisation N+1 (NFR-PERF-02)** : Intégrer obligatoirement `select_related("created_by", "department", "assigned_dm", "assigned_etp")`.
  - [x] Subtask 1.4 : Gérer le paramètre de requête `import_status` (recent/historique) dans le sélecteur et dans la vue `RecommendationListView`. (Vérifier `import_tag__isnull=True` ou `import_tag=""` pour récent).
  - [x] Subtask 1.5 : **Sécurité d'Accès** : Créer le mixin `WorkflowAccessMixin` autorisant `AUDIT`, `DM`, `ETP` et `DG` (redirection 403 sinon). L'appliquer sur `RecommendationListView` ET `RecommendationDetailView`.

- [x] Task 2 : Frontend - Composant de bascule UI & Sécurité Vue
  - [x] Subtask 2.1 : **Sécurité UI (FR5/FR6)** : Dans `recommendation_list.html`, masquer le bouton "Créer une recommandation" pour les DMs/ETPs en utilisant `{% if user.role == 'AUDIT' or user.is_superuser %}`.
  - [x] Subtask 2.2 : **Sécurité UI** : Dans `recommendation_table.html`, masquer les actions du menu contextuel (Modifier, Supprimer) si la recommandation n'est pas en DRAFT ou si l'utilisateur n'est pas auditeur.
  - [x] Subtask 2.3 : **Intégration HTMX Robuste** : Dans `recommendation_list.html`, envelopper les filtres existants dans un `<form id="filter-form">`. Ajouter obligatoirement `,[name='import_status']` à tous les attributs `hx-include` des `<select>` existants. Ajouter un `<input type="hidden" name="import_status" id="id_import_status" value="{{ current_import_status }}">`.
  - [x] Subtask 2.4 : Ajouter le composant Pills/Tabs directement dans `recommendation_list.html` et utiliser Alpine.js pour mettre à jour la valeur de l'input caché et soumettre le formulaire (ex: `$dispatch('submit')`).
  - [x] Subtask 2.5 : **Pagination** : Dans `recommendation_table.html`, modifier les liens de pagination (`?page=...`) pour inclure `&import_status={{ current_import_status|urlencode }}` afin de préserver le filtre en changeant de page.

- [x] Task 3 : Tests (Sécurité, Filtrage et UI)
  - [x] Subtask 3.1 : **Test RBAC DM/DG** : `test_dm_excludes_draft` et `test_dm_only_sees_own_department` (Ne voit pas les brouillons, voit uniquement les recos de son département). Ajouter `test_dg_can_access_list`.
  - [x] Subtask 3.2 : **Test RBAC ETP** : `test_etp_only_sees_assigned` (Ne voit que les recos qui lui sont formellement assignées).
  - [x] Subtask 3.3 : **Test Audit Filtrage** : `test_audit_sees_all_with_import_filter` (Audit voit tout avec changement récent/historique).
  - [x] Subtask 3.4 : **Test Filtres Croisés et Pagination** : `test_cross_filters_preserved_with_import_status`, `test_pagination_preserves_import_status`, et `test_invalid_import_status_shows_all`.
  - [x] Subtask 3.5 : **Test UI et HTMX** : `test_create_button_hidden_for_dm`, `test_create_button_hidden_for_etp`, et `test_htmx_request_returns_partial`.

## Dev Notes

- **Architecture & Constraints:**
  - Conserver le pattern de requêtes HTMX défini dans Epic 1 et 2 (le rendu partiel est déjà géré par `django-htmx` si présent ou vérification de `HTTP_HX_REQUEST`).
  - Le tri par défaut des récentes doit rester "plus récent d'abord" ou basé sur `is_overdue`.
  - **Performance Critique** : L'utilisation de `select_related()` est non-négociable pour garantir un temps de réponse < 200ms sur des volumes de 2000 recos (NFR-PERF-02).
  - **RBAC Strict** : Les DM et ETPs ne doivent en aucun cas interagir avec les brouillons (DRAFT), c'est une règle métier forte (FR6). Le mixin `WorkflowAccessMixin` doit explicitement lister les rôles autorisés (`User.Role.AUDIT`, `User.Role.DM`, `User.Role.ETP`, `User.Role.DG`).

- **Source tree components to touch:**
  - `apps/users/mixins.py` (création du mixin `WorkflowAccessMixin` pour autorisation DM/ETP/DG)
  - `apps/workflow/selectors.py` (logique RBAC `get_recommendations_for_user` et filtres consolidés)
  - `apps/workflow/views.py` (remplacement d'AuditRequiredMixin et passage de `import_status`)
  - `templates/workflow/recommendation_list.html` (masquer bouton créer via `user.role == 'AUDIT'`, wrapper form `<form id="filter-form">`, MAJ `hx-include`, ajout Tabs/Pills)
  - `templates/workflow/partials/recommendation_table.html` (masquer boutons d'actions, MAJ des liens de pagination)
  - `apps/workflow/tests/test_views.py` (couverture exhaustive avec les nouveaux tests RBAC et filtres)

### References

- [Source: epics.md#Story 3.1]
- [Architecture v2] Tailwind CSS et HTMX pour le filtrage (NFR-PERF-02).
- [PRD v2] Séparation des tâches (FR5, FR6, FR28, FR32).
- [Audit 3-1-ajouts-manquants.md] Sécurité RBAC stricte (WorkflowAccessMixin, tests associés), correctifs pagination et UI.

## Dev Agent Record

### Agent Model Used

Gemini 3 Flash

### Debug Log References

- Code Review conducted on 2026-05-17.
- Identified: 3 HIGH issues (AC1 blank tag, AC2 restrictive IMPORTED tag, RBAC fallback gap), 2 MEDIUM (missing test, hardcoded values), 2 LOW (implicit 'all', status update).
- All items successfully fixed and validated in tests.

### Completion Notes List

- Added `WorkflowAccessMixin` and protected list/detail views.
- Overhauled `get_recommendations_for_user` to prevent leaks (fail-closed fallback).
- Expanded tests with `test_invalid_import_status_shows_all`.
- Reworked filters UI to horizontal premium toolbar.
- Realigned login redirect rules in `SentinelLoginView` for direct workflow access.

### File List

- `code/apps/users/mixins.py`
- `code/apps/workflow/selectors.py`
- `code/apps/workflow/views.py`
- `code/templates/workflow/recommendation_list.html`
- `code/templates/workflow/partials/recommendation_table.html`
- `code/apps/workflow/tests/test_views.py`
- `code/apps/users/views.py`
- `code/templates/workflow/partials/stepper_slideover.html`
