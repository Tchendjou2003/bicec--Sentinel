# Story 1.3: Plateforme des Auditeurs Externes

Status: done

## Story

As a **Auditeur Externe (COBAC)**,
I want **disposer d'un canal d'authentification dédié**,
so that **je puisse vérifier les données en totale isolation de l'environnement interne.**

## Acceptance Criteria

1. **Given** un auditeur externe,
   **When** il se connecte,
   **Then** son profil est strictement limité à `is_external=True` et ne peut effectuer aucune action d'écriture.

2. **Given** un auditeur externe tentant d'accéder à l'application,
   **When** il utilise la page de login,
   **Then** il doit exister un canal de connexion spécifique (par exemple `/auth/external/login/`) ou le système détecte son rôle `EXT` et le redirige vers un espace isolé (tableau de bord externe).

3. **Given** un profil externe connecté,
   **When** il tente d'accéder aux vues internes (ex: `/admin/` ou vues de gestion),
   **Then** l'accès lui est refusé (403 Forbidden).

4. **Given** le modèle de données,
   **Then** le système prévoit la structure `ExternalMission` pour définir l'organisation de l'auditeur (COBAC, BEAC, etc.), ses dates d'intervention et son périmètre.

## Tasks / Subtasks

- [x] Task 1: Modélisation de la Mission Externe (AC: 4)
  - [x] Créer le modèle `ExternalMission` dans `apps/users/models.py` (auditor_id, organization, scope_description, start_date, end_date, is_active).
  - [x] Ajouter l'interface d'administration pour ce modèle.
- [x] Task 2: Canal de Connexion Isolé (AC: 2)
  - [x] Créer une vue de login dédiée `ExternalLoginView` ou ajuster la logique de redirection post-login existante pour isoler les utilisateurs ayant `role="EXT"`.
  - [x] Créer un template spécifique pour l'espace externe (ex: `layouts/external_shell.html`) pour garantir l'isolation visuelle et fonctionnelle.
- [x] Task 3: Middleware et Protection Read-Only (AC: 1, 3)
  - [x] Mettre à jour `RoleRequiredMiddleware` ou créer un middleware spécifique pour bloquer toute requête de modification (POST, PUT, DELETE) venant d'un utilisateur `is_external=True`, sauf potentiellement pour la déconnexion.
  - [x] Bloquer l'accès aux URLs internes et d'administration pour les utilisateurs externes.

## Dev Notes

- **Architecture:** Le système repose sur Django SSR + HTMX. L'isolation des auditeurs externes est une exigence forte (ADR-10, PRD FR2). 
- **Sécurité:** Les auditeurs externes ne doivent **jamais** pouvoir modifier de données. Toute requête en écriture (sauf logout) doit être rejetée avec une erreur 403.
- **Base de données:** Le diagramme ERD demande la table `users_external_mission`. Notez que la relation M2M avec les recommandations (`external_mission_recommendations`) sera implémentée ultérieurement lorsque l'application `workflow` sera créée (Epic 2). Pour l'instant, concentrez-vous sur les informations descriptives de la mission.

### Project Structure Notes

- Le modèle `ExternalMission` va dans `apps/users/models.py`.
- Le canal d'authentification externe peut réutiliser les composants UI Tailwind, mais doit utiliser un shell distinct (`layouts/external_shell.html`) pour prouver l'isolation.

### References

- [Source: _bmad-output/planning-artifacts/prd-v2.md#138] (Opening Scene de la Mission COBAC).
- [Source: _bmad-output/planning-artifacts/system-diagrams.md] (ERD pour `users_external_mission`).
- [Source: _bmad-output/planning-artifacts/epics.md#178] (Story 1.3 Acceptance Criteria).

## Dev Agent Record

### Agent Model Used
Claude Opus 4 (Thinking)

### Completion Notes List
- **Task 1 — ExternalMission Model:** Créé le modèle `ExternalMission` avec UUID PK, FK PROTECT vers User, champs organization/scope_description/start_date/end_date/is_active, timestamps, et 3 index DB. Migration `0003_external_mission` appliquée. Admin enregistré avec list_display, filtres, recherche, et date_hierarchy.
- **Task 2 — Canal de Connexion Isolé:** Ajouté la redirection post-login EXT→`/auth/external/dashboard/` dans `SentinelLoginView`. Créé `ExternalDashboardView` avec accès restreint aux EXT uniquement (403 pour les internes). Créé `external_shell.html` (layout dédié sans sidebar) et `external/dashboard.html` (tableau de bord avec badge "Lecture seule"). Corrigé le context_processor sidebar_context (clé AUDIT_EXT → EXT).
- **Task 3 — Middleware Read-Only + Isolation:** Créé `ExternalIsolationMiddleware` avec double protection : (1) blocage POST/PUT/PATCH/DELETE sauf /auth/logout/ (AC1), (2) restriction de navigation aux seules routes /auth/login/|/auth/logout/|/auth/external/ (AC3). Enregistré dans MIDDLEWARE après RoleRequiredMiddleware.
- **Tests:** 34 nouveaux tests ajoutés. 83/83 tests passent, 0 régressions.
- **[Code Review Fixes]:** 
  - Ajout de `limit_choices_to={"is_external": True, "role": "EXT"}` sur la FK `auditor` pour empêcher d'assigner un interne (HIGH).
  - Implémentation de `clean()` et surcharge de `save()` pour valider que `end_date >= start_date` (MEDIUM).
  - Utilisation de `raise PermissionDenied` au lieu d'un simple `HttpResponseForbidden` brut dans le middleware pour s'intégrer au gabarit 403 de Django (MEDIUM).
  - Filtrage strict (`==` au lieu de `startswith`) pour les exceptions de méthodes HTTP dans le middleware (LOW).

### Change Log
- 2026-05-03: Story 1.3 implémentée — Modèle ExternalMission, canal de connexion isolé, middleware read-only et isolation des vues internes.

### File List
- `apps/users/models.py` — Ajout du modèle ExternalMission
- `apps/users/admin.py` — Ajout de ExternalMissionAdmin
- `apps/users/views.py` — Ajout de ExternalDashboardView, modification de SentinelLoginView
- `apps/users/urls.py` — Ajout de la route /auth/external/dashboard/
- `apps/users/middleware.py` — Ajout de ExternalIsolationMiddleware
- `apps/users/context_processors.py` — Correction clé sidebar AUDIT_EXT → EXT
- `apps/users/migrations/0003_external_mission.py` — Migration nouveau modèle
- `apps/users/tests/test_external_mission.py` — 14 tests modèle + admin
- `apps/users/tests/test_external_channel.py` — 6 tests canal de connexion
- `apps/users/tests/test_external_readonly.py` — 12 tests middleware read-only
- `config/settings/base.py` — Ajout ExternalIsolationMiddleware au MIDDLEWARE
- `templates/layouts/external_shell.html` — Shell dédié espace externe
- `templates/external/dashboard.html` — Tableau de bord auditeur externe
