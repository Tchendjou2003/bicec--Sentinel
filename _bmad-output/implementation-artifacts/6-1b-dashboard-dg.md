# Story 6.1b : Dashboard Direction Générale (DG)

Status: done

<!-- Prérequis : Story 6.1a terminée (DashboardView opérationnelle, selectors.py DM/ETP done). -->
<!-- Décision RBAC Option B (validée session 2026-06-04) : dashboard = vue globale banque,
     liste recos = seulement recos assignées (get_recommendations_for_user DG inchangé). -->
<!-- Chart.js 4.x déjà en code/static/js/chart.umd.min.js (6.1a). -->
<!-- Leçons 6.1a : {% comment %}...{% endcomment %} pour multi-lignes, pas de SVG inline
     dans include, list() sur QuerySets avant contexte, variables JS callbacks = item. -->

## Story

As a **Direction Générale (DG)**,
I want **un tableau de bord consolidé de toute la banque — KPIs macro, heatmap par direction, mes recos directes**,
so that **je peux identifier immédiatement quelles directions sont en souffrance et superviser mon exposition réglementaire globale (FR29, FR30)**.

## Acceptance Criteria

1. **AC1 — KPIs macro-banque (5 cartes)** : Total actives (banque) / En retard / Critiques ouvertes / Taux clôture global / En validation Audit. Inclut TOUTES les directions.
2. **AC2 — Heatmap par Direction (tableau HTML pur)** : une ligne par direction racine, colonnes Direction / Actives / OVERDUE / Critiques / Taux clôture / Risque coloré (CRITIQUE=rouge, MODERE=orange, FAIBLE=vert), lien drill-down.
3. **AC3 — Barres empilées par Direction (Chart.js)** : segments par statut, JSON injecté côté serveur.
4. **AC4 — Mes recos directes (scope normal DG)** : max 10 recos `assigned_dm=user` non-clôturées avec bandes aging.
5. **AC5 — Tests** : KPIs DG voient toutes les directions, my_recos scopé, breakdown structuré, vue 200 avec contexte complet.

## Tasks / Subtasks

- [x] **Task 1 — Sélecteurs** (`selectors.py`) : `_get_dg_dashboard_qs`, `_get_department_breakdown` (partagé), `_get_stacked_bar_json` (partagé), `_enrich_with_aging` (partagé), `get_dg_kpis`, `get_dg_department_breakdown`, `get_dg_my_recos_with_aging`.
- [x] **Task 2 — Composant** `code/templates/components/bar_chart.html` (Chart.js stacked bar, `{% comment %}`, `item` callback).
- [x] **Task 3 — `_dg_context()`** : breakdown calculé une fois, `_get_stacked_bar_json(breakdown)` depuis mémoire.
- [x] **Task 4 — Template** `dg_dashboard.html` : 4 sections, extend `app_shell.html`, pas de `icon_svg` dans include.
- [x] **Task 5 — Tests** `test_selectors_6b6c.py` + `test_views.py`.
- [x] **Task 6 — sprint-status.yaml** : `6-1b-dashboard-dg: done`.

## Dev Notes

### RBAC Option B
`_get_dg_dashboard_qs()` retourne toute la banque (exclut DRAFT). `get_dg_my_recos_with_aging(*, user)` utilise `get_recommendations_for_user(user=user)` — scope DG normal. `get_recommendations_for_user` non modifié.

### Réutilisation
`get_department_and_descendants_ids`, `kpi_card.html` (sans icon_svg), `urgency_table.html`, helper `_enrich_with_aging`.

### Helpers partagés créés (réutilisés par 6.1c)
- `_get_department_breakdown(base_qs)` — agrégation par direction racine + risk_level.
- `_get_stacked_bar_json(dept_breakdown)` — JSON Chart.js depuis breakdown en mémoire.
- `_enrich_with_aging(qs)` — bande aging (overdue/warning/ok), refactor des 3 boucles dupliquées de 6.1a.

## Dev Agent Record
### Agent Model Used
claude-sonnet-4-6 / claude-opus-4-8
### Completion Notes List
- Helper `_enrich_with_aging` extrait et réutilisé par get_dm_urgency_rows, get_etp_rows, get_dg_my_recos_with_aging.
- Composant `bar_chart.html` partagé entre DG et Audit (6.1c).
- 44 tests dashboards passent (27 de 6.1a + 17 de 6.1b/6.1c). ruff clean.
### File List
- code/apps/dashboards/selectors.py (modifié)
- code/apps/dashboards/views.py (modifié — _dg_context)
- code/templates/dashboards/dg_dashboard.html (créé)
- code/templates/components/bar_chart.html (créé)
- code/apps/dashboards/tests/test_selectors_6b6c.py (créé)
- code/apps/dashboards/tests/test_views.py (modifié)
