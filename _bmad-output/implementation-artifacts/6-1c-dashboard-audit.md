# Story 6.1c : Dashboard Audit Interne

Status: done

<!-- Prérequis : Stories 6.1a ET 6.1b terminées (_get_department_breakdown, _get_stacked_bar_json, bar_chart.html disponibles). -->
<!-- L'Audit voit TOUT (get_recommendations_for_user AUDIT = no filter). -->
<!-- Même règles 6.1a : {% comment %} multi-ligne, pas SVG inline, list() dans sélecteurs, item JS callback. -->

## Story

As a **Auditeur Interne (AUDIT)**,
I want **un dashboard de contrôle global — KPIs macro, inbox des 3 files d'action, heatmap santé, et auto-évaluation de performance**,
so that **je supervise l'état de conformité de toute la banque, j'agis immédiatement sur les dossiers qui attendent ma décision, et j'évalue la performance de l'équipe d'audit (FR25, FR29, FR30)**.

## Acceptance Criteria

1. **AC1 — KPIs globaux (6 cartes)** : Total actives / En retard / À valider (PENDING_AUDIT_REVIEW, accent warning) / Critiques ouvertes / Taux clôture / Créées ce mois.
2. **AC2 — Inbox Audit (3 files)** : Preuves à examiner (PENDING_AUDIT_REVIEW) / Reports à décider (ExtensionRequest.PENDING) / Brouillons à assigner (DRAFT). Chaque file : max 10 + badge count total + état vide friendly.
3. **AC3 — Barres empilées + Heatmap Santé** : réutilise `bar_chart.html` + tableau santé par direction (risk_level coloré).
4. **AC4 — Performance Audit (Section 5)** : Recos créées ce mois / clôturées ce mois / taux clôture global / taux retard global — lus depuis `kpis`, sans appel AuditLog.
5. **AC5 — Tests** : counts des 3 files corrects, vue 200 avec contexte complet.

## Tasks / Subtasks

- [x] **Task 1 — Sélecteurs Audit** : `get_audit_kpis` (+ taux_overdue, recos_crees/closes_ce_mois), `get_audit_pending_review` + count, `get_audit_pending_extensions` (SANS user) + count, `get_audit_draft_unassigned` + count, `get_audit_department_breakdown`.
- [x] **Task 2 — `_audit_context()`** : breakdown une fois, `_get_stacked_bar_json(breakdown)` depuis mémoire, `pending_extensions` sans user, PAS de `perf_metrics`.
- [x] **Task 3 — Template** `audit_dashboard.html` : 5 sections, extend `app_shell.html`, 3 files SSR (pas de tabs JS), Section 5 lit `kpis`.
- [x] **Task 4 — Tests** `test_selectors_6b6c.py` + `test_views.py`.
- [x] **Task 5 — sprint-status.yaml** : `6-1c-dashboard-audit: done`. epic-6 reste `in-progress` (6.2–6.7 backlog).

## Dev Notes

### Inbox — 3 files SSR (pas de tabs JS)
3 cartes séquentielles. Ordre : Preuves (bloquant ETPs) > Reports > Brouillons.

### Réutilisation 6.1b
`_get_department_breakdown`, `_get_stacked_bar_json`, `bar_chart.html` (chart_id="audit-stacked"), markup heatmap (copié de DG), `kpi_card.html` (sans icon_svg).

### ExtensionRequest
`ExtensionRequest.Status.PENDING` (models.py:935). Champs : `recommendation`, `requested_by`, `created_at` (date demande), `requested_date` (= nouvelle date souhaitée). ⚠ PAS de `new_due_date`.

### Section 5 Performance
Pas de sélecteur `get_audit_performance_metrics` — le template lit `kpis.recos_crees_ce_mois`, `kpis.recos_closes_ce_mois`, `kpis.taux_cloture`, `kpis.taux_overdue`. Évite la double requête.

## Dev Agent Record
### Agent Model Used
claude-sonnet-4-6 / claude-opus-4-8
### Completion Notes List
- `get_audit_pending_extensions()` sans `user` (seul l'Audit appelle, voit tout).
- Section 5 alimentée par `get_audit_kpis` (taux_overdue + compteurs mensuels ajoutés au dict).
- 44 tests dashboards passent. ruff clean.
### File List
- code/apps/dashboards/selectors.py (modifié — sélecteurs Audit)
- code/apps/dashboards/views.py (modifié — _audit_context)
- code/templates/dashboards/audit_dashboard.html (créé)
- code/apps/dashboards/tests/test_selectors_6b6c.py (créé, partagé avec 6.1b)
- code/apps/dashboards/tests/test_views.py (modifié)
