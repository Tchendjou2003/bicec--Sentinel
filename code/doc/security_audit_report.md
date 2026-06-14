# Rapport d'Audit Sécurité & Fonctionnel — Sentinel

**Date** : 2026-05-30 16:45:29 (WAT)  
**Résultat global** : 70/70 PASS — **0 FAIL**

> Audit généré par `manage.py audit_sentinel_security` (transaction annulée, BDD de dev inchangée).

## Résumé exécutif

| Chapitre | PASS | FAIL |
|----------|------|------|
| 1 — Authentification & Session | 5/5 | 0 |
| 2 — RBAC — Accès aux pages par rôle | 22/22 | 0 |
| 3 — Isolation cross-département / cross-user | 4/4 | 0 |
| 4 — Transitions FSM invalides | 4/4 | 0 |
| 5 — Règles métier (guards de service) | 6/6 | 0 |
| 6 — Auditeur Externe (EXT) — Isolation | 4/4 | 0 |
| 7 — Immutabilité post-soumission | 3/3 | 0 |
| 8 — Sceau HMAC & Intégrité | 3/3 | 0 |
| 9 — Notifications | 4/4 | 0 |
| 10 — Pages Admin & IT | 15/15 | 0 |

## ✅ Aucune faille détectée

Toutes les règles métier, transitions et permissions sont respectées.

## Détail complet

### Chapitre 1 — Authentification & Session

- ✅ Page de login accessible sans authentification (`GET /auth/login/` [anonyme] → attendu 200, reçu 200)
- ✅ Accès workflow sans session → redirection login (`GET /audit/recommandations/` [anonyme] → attendu 302, reçu 302)
- ✅ Compte shell (sans rôle) → redirection /auth/pending/ (`GET /audit/recommandations/` [shell] → attendu 302, reçu 302)
- ✅ Brute-force : lockout Axes après 5 échecs (`POST /auth/login/` [anonyme] → attendu lockout (403), reçu lockout)
- ✅ Session idle > 30 min → déconnexion automatique (`GET /audit/recommandations/` [AUDIT] → attendu 302, reçu 302)

### Chapitre 2 — RBAC — Accès aux pages par rôle

- ✅ Liste recommandations — AUDIT (`GET /audit/recommandations/` [AUDIT] → attendu 200, reçu 200)
- ✅ Liste recommandations — DM (`GET /audit/recommandations/` [DM] → attendu 200, reçu 200)
- ✅ Liste recommandations — ETP (`GET /audit/recommandations/` [ETP] → attendu 200, reçu 200)
- ✅ Liste recommandations — DG (`GET /audit/recommandations/` [DG] → attendu 200, reçu 200)
- ✅ Liste recommandations — EXT (`GET /audit/recommandations/` [EXT] → attendu 403, reçu 403)
- ✅ Liste recommandations — ADMIN (`GET /audit/recommandations/` [ADMIN] → attendu 403, reçu 403)
- ✅ Liste recommandations — shell (`GET /audit/recommandations/` [shell] → attendu 302, reçu 302)
- ✅ Page création reco — AUDIT (`GET /audit/recommandations/create/` [AUDIT] → attendu 200, reçu 200)
- ✅ Page création reco — DM (`GET /audit/recommandations/create/` [DM] → attendu 403, reçu 403)
- ✅ Page création reco — ETP (`GET /audit/recommandations/create/` [ETP] → attendu 403, reçu 403)
- ✅ Page création reco — DG (`GET /audit/recommandations/create/` [DG] → attendu 403, reçu 403)
- ✅ Page création reco — EXT (`GET /audit/recommandations/create/` [EXT] → attendu 403, reçu 403)
- ✅ Page création reco — ADMIN (`GET /audit/recommandations/create/` [ADMIN] → attendu 403, reçu 403)
- ✅ Page création reco — shell (`GET /audit/recommandations/create/` [shell] → attendu 302, reçu 302)
- ✅ POST assign DM — DM (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/assign/` [DM] → attendu 403, reçu 403)
- ✅ POST assign DM — ETP (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/assign/` [ETP] → attendu 403, reçu 403)
- ✅ POST assign DM — DG (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/assign/` [DG] → attendu 403, reçu 403)
- ✅ POST assign DM — EXT (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/assign/` [EXT] → attendu 403, reçu 403)
- ✅ POST assign DM — ADMIN (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/assign/` [ADMIN] → attendu 403, reçu 403)
- ✅ POST close-audit — DM (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/close-audit/` [DM] → attendu 403, reçu 403)
- ✅ POST close-audit — DG (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/close-audit/` [DG] → attendu 403, reçu 403)
- ✅ POST close-audit — ETP (doit être refusé) (`POST /audit/recommandations/59e22670-d91b-4e13-9dd4-dad1736b410d/close-audit/` [ETP] → attendu 403, reçu 403)

### Chapitre 3 — Isolation cross-département / cross-user

- ✅ DM d'un autre département → reco invisible (404) (`GET /audit/recommandations/be8924ea-ef8c-4982-a39c-c2e674c58590/` [DM] → attendu 404, reçu 404)
- ✅ DM assigné (même dept) → accès reco (200) (`GET /audit/recommandations/be8924ea-ef8c-4982-a39c-c2e674c58590/` [DM] → attendu 200, reçu 200)
- ✅ ETP non assigné → reco invisible (404) (`GET /audit/recommandations/be8924ea-ef8c-4982-a39c-c2e674c58590/` [ETP] → attendu 404, reçu 404)
- ✅ DG non assigné → reco invisible (404) (`GET /audit/recommandations/be8924ea-ef8c-4982-a39c-c2e674c58590/` [DG] → attendu 404, reçu 404)

### Chapitre 4 — Transitions FSM invalides

- ✅ submit-evidence sur DRAFT (ETP) → 404 (reco invisible, non révélée) (`POST /audit/recommandations/fd5cd2d0-e173-4433-a93a-9b5d39169d61/submit-evidence/` [ETP] → attendu 404, reçu 404)
- ✅ close-audit sur IN_PROGRESS → 422 (état invalide) (`POST /audit/recommandations/a30ed74b-38a8-419c-be40-ab3d24111476/close-audit/` [AUDIT] → attendu 422, reçu 422)
- ✅ reject-audit sur IN_PROGRESS → 422 (état invalide) (`POST /audit/recommandations/a30ed74b-38a8-419c-be40-ab3d24111476/reject-audit/` [AUDIT] → attendu 422, reçu 422)
- ✅ Double soumission DG (déjà PENDING_AUDIT_REVIEW) → 422 (`POST /audit/recommandations/4ebfa48b-0b54-4c68-b2c4-01a722cd7a62/submit-dg/` [DG] → attendu 422, reçu 422)

### Chapitre 5 — Règles métier (guards de service)

- ✅ F1 — DG soumet sans fichier → refusé (`SERVICE -` [-] → attendu exception ValueError, reçu ValueError: La soumission DG doit contenir au moins un fichier probatoir)
- ✅ DG soumet sans commentaire → refusé (`SERVICE -` [-] → attendu exception ValueError, reçu ValueError: Le commentaire de résolution est obligatoire pour soumettre.)
- ✅ DG soumet fichier + commentaire → succès (`SERVICE -` [-] → attendu succès, reçu OK (aucune exception))
- ✅ Rejet Audit motif < 10 chars → refusé (`SERVICE -` [-] → attendu exception ValueError, reçu ValueError: Le motif doit comporter au moins 10 caractères.)
- ✅ F2 — clôture sans preuve fichier → refusé (`SERVICE -` [-] → attendu exception ValueError, reçu ValueError: Clôture impossible : le dossier ne contient aucune preuve do)
- ✅ Report avec date antérieure → refusé (`SERVICE -` [-] → attendu exception Exception, reçu ValueError: La nouvelle date doit être postérieure à l'échéance actuelle)

### Chapitre 6 — Auditeur Externe (EXT) — Isolation

- ✅ EXT → liste workflow refusée (403) (`GET /audit/recommandations/` [EXT] → attendu 403, reçu 403)
- ✅ EXT → détail reco refusé (403) (`GET /audit/recommandations/fe3b7a9c-6bd6-4a83-898b-a7d0c4d105a8/` [EXT] → attendu 403, reçu 403)
- ✅ EXT → écriture (POST) refusée (403) (`POST /audit/recommandations/create/` [EXT] → attendu 403, reçu 403)
- ✅ EXT → dashboard externe autorisé (200) (`GET /auth/external/dashboard/` [EXT] → attendu 200, reçu 200)

### Chapitre 7 — Immutabilité post-soumission

- ✅ Mutation sur reco CLOSED : re-clôture → 422 (`POST /audit/recommandations/0896ba45-7ff0-4876-b71a-af1d198b61be/close-audit/` [AUDIT] → attendu 422, reçu 422)
- ✅ Mutation sur reco CLOSED : submit-dg → 422 (`POST /audit/recommandations/0896ba45-7ff0-4876-b71a-af1d198b61be/submit-dg/` [DG] → attendu 422, reçu 422)
- ✅ Lecture d'une reco CLOSED → 200 (toujours consultable) (`GET /audit/recommandations/0896ba45-7ff0-4876-b71a-af1d198b61be/` [AUDIT] → attendu 200, reçu 200)

### Chapitre 8 — Sceau HMAC & Intégrité

- ✅ Clôture avec preuves → sceau généré + verify=True (`SERVICE -` [-] → attendu succès, reçu OK (aucune exception))
- ✅ Altération post-clôture → verify=False (détectée) (`SERVICE -` [-] → attendu succès, reçu OK (aucune exception))
- ✅ F3 — scellement sans fichier probatoire → refusé (`SERVICE -` [-] → attendu exception ValueError, reçu ValueError: Scellement impossible : le dossier ne contient aucun fichier)

### Chapitre 9 — Notifications

- ✅ Dropdown notifications sans auth → 302 (`GET /notifications/dropdown/` [anonyme] → attendu 302, reçu 302)
- ✅ Dropdown notifications avec auth → 200 (`GET /notifications/dropdown/` [DM] → attendu 200, reçu 200)
- ✅ mark-read sur notif d'un autre user → 404 (`POST /notifications/510404ee-4ef6-43b6-b89c-1cff596101c3/mark-read/` [DM] → attendu 404, reçu 404)
- ✅ emit_notification idempotent (même clé → pas de doublon) (`SERVICE -` [-] → attendu succès, reçu OK (aucune exception))

### Chapitre 10 — Pages Admin & IT

- ✅ Gestion utilisateurs IT — AUDIT (`GET /auth/admin/utilisateurs/` [AUDIT] → attendu 403, reçu 403)
- ✅ Gestion utilisateurs IT — DM (`GET /auth/admin/utilisateurs/` [DM] → attendu 403, reçu 403)
- ✅ Gestion utilisateurs IT — ETP (`GET /auth/admin/utilisateurs/` [ETP] → attendu 403, reçu 403)
- ✅ Gestion utilisateurs IT — DG (`GET /auth/admin/utilisateurs/` [DG] → attendu 403, reçu 403)
- ✅ Gestion utilisateurs IT — EXT (`GET /auth/admin/utilisateurs/` [EXT] → attendu 403, reçu 403)
- ✅ Gestion utilisateurs IT — ADMIN (`GET /auth/admin/utilisateurs/` [ADMIN] → attendu 200, reçu 200)
- ✅ Gestion utilisateurs IT — shell (`GET /auth/admin/utilisateurs/` [shell] → attendu 302, reçu 302)
- ✅ Habilitation — AUDIT simple (sans is_audit_admin) → 403 (`GET /audit/habilitation/` [AUDIT] → attendu 403, reçu 403)
- ✅ Habilitation — Audit Admin → 200 (`GET /audit/habilitation/` [AUDIT] → attendu 200, reçu 200)
- ✅ Habilitation — DM → 403 (`GET /audit/habilitation/` [DM] → attendu 403, reçu 403)
- ✅ Sources admin — Audit Admin → 200 (`GET /audit/sources-admin/` [AUDIT] → attendu 200, reçu 200)
- ✅ Sources admin — DM → 403 (`GET /audit/sources-admin/` [DM] → attendu 403, reçu 403)
- ✅ Organigramme — Audit Admin → 200 (`GET /auth/admin/organigramme/` [AUDIT] → attendu 200, reçu 200)
- ✅ Organigramme — ETP → 403 (`GET /auth/admin/organigramme/` [ETP] → attendu 403, reçu 403)
- ✅ Dashboard externe — DM (non-EXT) → 403/redirect (`GET /auth/external/dashboard/` [DM] → attendu 403, reçu 403)
