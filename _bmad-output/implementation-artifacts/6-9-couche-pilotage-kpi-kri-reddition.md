# Story 6.9: Couche Pilotage Décisionnel — Socle Métriques + KPI / KRI / Reddition

Status: draft

<!-- Étend Epic 6 (Executive Supervision Dashboards) au-delà des FR29-FR32 : transforme les dashboards photographiques (6.1a/b/c) en outil de pilotage et d'aide à la décision pour la DG et le comité d'audit. -->
<!-- Décisions utilisateur verrouillées : (1) Comité = section Reddition + export, PAS de nouveau rôle ; (2) on-time strict ET tolérant côte à côte ; (3) exposition réglementaire = stock pondéré ET indice de vieillissement séparés ; (4) first-pass = reprise DM ET reprise Audit séparées. -->
<!-- 4 pièges techniques vérifiés dans le code : médiane en Python (SQLite en test), progress_percentage = @property non-SQL, AuditLog sans index (0003), export XLSX/ZIP déjà présents (PDF différé). -->

## Story

As a **décideur de l'audit interne et de la direction générale (rôles AUDIT et DG)**,
I want **des indicateurs décisionnels précis et leur évolution dans le temps — efficacité du dispositif de remédiation (KPI), émergence et aggravation des risques (KRI), et une section de reddition exportable pour le comité d'audit**,
so that **je pilote la performance du dispositif, j'anticipe les risques avant qu'ils ne deviennent des retards, et je présente au comité d'audit / à la COBAC une vision fiable et auditable de l'état de conformité de la banque.**

**Contexte produit** — Les dashboards actuels (Stories 6.1a DM/ETP, 6.1b DG, 6.1c Audit) sont **photographiques** : ils comptent les recommandations par statut à l'instant T (cartes KPI, donut, barres empilées par direction, heatmap `risk_level`, files d'inbox). Un comité d'audit et une DG ont besoin de **tendance** (le dispositif s'améliore-t-il ?), de **délai** (combien de temps pour corriger ?), de **qualité** (corrige-t-on bien du premier coup ?) et d'**anticipation** (où le risque monte-t-il ?). La matière première existe déjà dans le modèle ; il manque l'**axe temps** (séries chronologiques) et quelques **ratios d'efficacité**.

**Point d'ancrage architectural clé** — Cette story n'invente aucun cycle de vie métier : elle **lit** l'existant. (1) Le cron nocturne `run_nightly_notifications` (`services.py:1536`) est déjà un orchestrateur à phases isolées → on y greffe une 3e phase de capture de snapshot, exactement comme `flag_overdue_recommendations` (3.9) et `notify_upcoming_deadlines` (4.2). (2) Tous les sélecteurs partent de `get_recommendations_for_user` (RBAC fail-closed) et réutilisent `_get_department_breakdown` / `_enrich_with_aging` (`dashboards/selectors.py`). (3) `closed_at`, `original_due_date`, `due_date`, `priority`, `source.is_external`, les statuts `EvidenceSubmission` et `ExtensionRequest`, et `HmacSeal` portent **déjà** toute l'information nécessaire. Aucune modification du workflow, du FSM, ni du RBAC.

## Acceptance Criteria

1. **AC1 — Socle temporel : snapshot nocturne idempotent**
   - **Given** le cron nocturne `run_nightly_notifications`
   - **When** il s'exécute
   - **Then** une 3e phase isolée (try/except propre, sans bloquer les deux autres) appelle `capture_daily_snapshot()` qui écrit, pour la date du jour, **une** ligne `MetricsSnapshot` banque-entière (`department=NULL`) **et** une ligne par direction racine active
   - **And** rejouer la capture le même jour ne crée **aucun** doublon (`update_or_create` sur `(snapshot_date, department)`)
   - **And** la capture n'écrit **que** dans `MetricsSnapshot` — **aucune** écriture sur `Recommendation` ni transition FSM.

2. **AC2 — KPI d'efficacité (dashboards DG + Audit)**
   - **Given** un utilisateur DG ou AUDIT sur `/tableau-de-bord/`
   - **When** la page se charge
   - **Then** une section « Efficacité du dispositif » affiche : délai **médian** de remédiation (`closed_at − created_at`) par criticité, taux de clôture dans les délais **strict ET tolérant** (cf. AC5), taux de reprise **DM ET Audit** (cf. AC6)
   - **And** une courbe « flux » (créées vs clôturées par mois + backlog net cumulé) lue depuis `MetricsSnapshot` est rendue via un partial `line_chart.html`
   - **And** le dwell-time par étape **n'est pas** dans cette story (différé — cf. Dev Notes piège AuditLog).

3. **AC3 — KRI de risque (dashboards DG + Audit)**
   - **Given** un utilisateur DG ou AUDIT
   - **When** la page se charge
   - **Then** une section « Risques émergents » affiche : pyramide d'âge du retard (buckets 0-30 / 30-90 / >90 j), exposition réglementaire en **deux mesures séparées** (stock pondéré **et** indice de vieillissement, cf. AC7), taux de glissement (% recos avec ≥1 report approuvé + dérive moyenne)
   - **And** un tableau « À risque de bascule » liste les recos non clôturées dont l'échéance est dans ≤ 30 j **et** la progression < 50 % (calculée par **annotation**, pas via la property — cf. piège)
   - **And** un tableau « Enlisement » liste les recos avec ≥ 2 reports OU (CRITIQUE et `updated_at` > 30 j).

4. **AC4 — Section Reddition + pack exportable (comité d'audit, SANS nouveau rôle)**
   - **Given** un utilisateur AUDIT (section résumée aussi visible DG)
   - **When** il consulte la section « Reddition »
   - **Then** elle affiche : tendances trimestrielles (depuis `MetricsSnapshot`), top 10 des risques (score composite criticité × aging × drapeau réglementaire), couverture de scellement (clôturées avec `hmac_seal` / total clôturées)
   - **And** un bouton « Exporter le pack » génère un fichier **Excel (openpyxl) et/ou ZIP** (PDF natif **différé**), et émet **une** entrée `AuditLog` `action=EXPORT`
   - **And** **aucun** nouveau rôle/login n'est créé : la vue réutilise `AuditRequiredMixin` / le contexte DG existant.

5. **AC5 — On-time strict ET tolérant**
   - **Given** une recommandation clôturée
   - **When** le taux de clôture dans les délais est calculé
   - **Then** deux taux distincts sont exposés : **strict** (`closed_at ≤ original_due_date`) et **tolérant** (`closed_at ≤ due_date` courante)
   - **And** l'écart entre les deux est présenté comme indicateur de pression sur les échéances.

6. **AC6 — First-pass : reprise DM ET reprise Audit séparées**
   - **Given** les soumissions de preuves d'une recommandation
   - **When** la qualité « du premier coup » est calculée
   - **Then** deux taux distincts sont exposés : taux de reprise **DM** (présence d'au moins une `EvidenceSubmission` `status=REJECTED`) et taux de reprise **Audit** (`status=REJECTED_BY_AUDIT`)
   - **And** les deux sont calculables sur le périmètre RBAC de l'utilisateur.

7. **AC7 — Exposition réglementaire : stock pondéré ET vieillissement**
   - **Given** les recommandations à source **externe** (`source.is_external=True`) ouvertes
   - **When** l'exposition réglementaire est calculée
   - **Then** deux chiffres séparés : `regulatory_stock_weighted` = Σ poids_criticité (CRITIQUE=4/HAUTE=3/MOYENNE=2/FAIBLE=1) ; `regulatory_aging_index` = Σ (poids_criticité × jours_de_retard) sur les externes en retard
   - **And** les deux sont snapshotés quotidiennement pour permettre la tendance.

8. **AC8 — RBAC, performance, tests**
   - **Given** n'importe quel sélecteur de pilotage
   - **When** il s'exécute
   - **Then** il part de `get_recommendations_for_user` (DG/Audit voient tout ; DRAFT exclus comme dans `get_audit_kpis`)
   - **And** `get_at_risk_recommendations` ne produit **pas** de N+1 (vérifié par `assertNumQueries`)
   - **And** la suite `pytest apps/dashboards` (≥ 44 tests existants) reste verte, `ruff` clean.

## Tasks / Subtasks

> Numérotation = cohérence logique. Ordre d'implémentation : section dédiée plus bas. Tasks groupées par sprint (A→E) pour permettre un découpage ultérieur en sous-stories.

### Sprint A — Socle (Phase 0)

- [ ] **Task 1 — Modèle `MetricsSnapshot`** (AC1, AC5, AC6, AC7)
  - [ ] Créer `MetricsSnapshot` dans `code/apps/dashboards/models.py` (actuellement stub) : `snapshot_date` (indexé), `department` (FK `users.Department`, null=banque), colonnes séries (`total_actives`, `overdue`, `overdue_0_30/30_90/90_plus`, `closed_cumulative`, `closed_total`, `critique_open`, `on_time_closed_strict`, `on_time_closed_tolerant`, `regulatory_stock_weighted`, `regulatory_aging_index`, `submissions_total`, `rejected_by_dm`, `rejected_by_audit`), `created_at`.
  - [ ] Contrainte d'unicité `(snapshot_date, department)`.
  - [ ] Migration `dashboards/migrations/000X_metricssnapshot.py`.

- [ ] **Task 2 — Helpers de calcul réutilisables** (AC2, AC3, AC5, AC6, AC7)
  - [ ] Dans `dashboards/selectors.py`, à côté de `_enrich_with_aging` : `_aging_buckets(qs)`, `_regulatory_stock_weighted(qs)`, `_regulatory_aging_index(qs)`, `_lead_time_stats(qs)` (**`statistics.median` en Python**, pas SQL), `_first_pass_rates(qs)` (reprise DM + Audit), `_on_time_rates(qs)` (strict + tolérant).

- [ ] **Task 3 — Service de capture** (AC1)
  - [ ] **Nouveau** `code/apps/dashboards/services.py` : `capture_daily_snapshot()` (calcul + `update_or_create` snapshot **uniquement**). Réutilise `_get_descendants_map` / `_get_department_breakdown`.

- [ ] **Task 4 — Greffe cron + commandes** (AC1)
  - [ ] Ajouter une 3e phase isolée dans `run_nightly_notifications()` (`workflow/services.py:1536`), import différé de `apps.dashboards.services` (anti-cycle).
  - [ ] `dashboards/management/commands/capture_metrics_snapshot.py` (wrapper testable).
  - [ ] `dashboards/management/commands/backfill_metrics_snapshot.py` (~90 j depuis `created_at`/`closed_at` ; volumes exacts, buckets d'aging approximatifs — documenter la limite).

### Sprint B — KPI efficacité (Phase 1)

- [ ] **Task 5 — Sélecteurs KPI** (AC2, AC5, AC6) : `get_efficiency_kpis(*, user)`, `get_throughput_series(*, periods=12)`.
- [ ] **Task 6 — Partial courbe** (AC2) : `code/templates/dashboards/partials/line_chart.html` (Chart.js line, pendant de `bar_chart.html`).
- [ ] **Task 7 — Contextes + sections** (AC2) : enrichir `_dg_context` / `_audit_context` (`dashboards/views.py:132,147`) + sections « Efficacité » dans `dg_dashboard.html` / `audit_dashboard.html`.

### Sprint C — KRI risque (Phase 2)

- [ ] **Task 8 — Sélecteurs KRI** (AC3, AC7) : `get_risk_kris(*, user)`, `get_at_risk_recommendations(*, user)` (**annotation** `Count('deliverables', filter=Q(deliverables__is_completed=True))` vs total — PAS la property), `get_stuck_recommendations(*, user)`, `get_risk_trend_series()`.
- [ ] **Task 9 — Section « Risques émergents »** dans `dg_dashboard.html` / `audit_dashboard.html` (KRI cards + pyramide d'âge + listes).

### Sprint D — Reddition + export (Phase 3)

- [ ] **Task 10 — Sélecteur gouvernance** (AC4) : `get_governance_summary(*, user)` (tendances trimestrielles, top 10 score composite, couverture scellement via `recommendation.hmac_seal`).
- [ ] **Task 11 — Section Reddition + export Excel/ZIP** (AC4) : section lecture seule dans `audit_dashboard.html` (+ résumé DG) ; vue + URL d'export calquées sur l'export XLSX existant (`workflow/views.py:2389`) et le ZIP (`workflow/views_missions.py`) ; `AuditLog action=EXPORT`.

### Sprint E (futur — hors story)

- [ ] Dwell-time par étape (nécessite index AuditLog ou champ `status_changed_at`).
- [ ] Export PDF natif (après choix d'une lib compatible Docker).

### Tests + validation

- [ ] **Task 12 — Tests** `code/apps/dashboards/tests/test_pilotage.py` : helpers (buckets, lead time médian Python, on-time strict/tolérant, reprise DM/Audit, exposition stock+vieillissement), idempotence `capture_daily_snapshot` (2× → 1 ligne/jour/direction), `get_at_risk_recommendations` (cas dans/hors fenêtre) avec `assertNumQueries` (pas de N+1).
- [ ] **Task 13 — Validation** : `makemigrations --check` + `migrate` ; `pytest apps/dashboards` ; `ruff check/format` ; manuel : capture + backfill, rendu DG/AUDIT, export pack + entrée `AuditLog EXPORT`.

## Ordre d'exécution recommandé

1. **Sprint A** (Task 1 → 4) : socle + helpers + capture + backfill — testable sans UI.
2. **Task 12** (tests du socle/helpers en priorité).
3. **Sprint B** (Task 5 → 7) : KPI efficacité + courbes.
4. **Sprint C** (Task 8 → 9) : KRI.
5. **Sprint D** (Task 10 → 11) : reddition + export.
6. **Task 13** : validation complète.

## Dev Notes

### Architecture technique (vérifiée dans le code)

- **`Recommendation`** (`code/apps/workflow/models.py:149`) : `closed_at` (`models.py:335`, nullable, migration `0014`), `original_due_date` (`models.py:271`, invariant COBAC), `due_date` (`models.py:264`, change après report approuvé), `priority` (`models.py:247`), `source` FK (`models.py:240`), `is_overdue` (`models.py:286`, calculé par le cron 3.9). **`progress_percentage` est une `@property`** (`models.py:416-428`) faisant 2 `COUNT()` → voir piège 2.
- **`EvidenceSubmission.SubmissionStatus`** (`models.py:717-722`) : `REJECTED` (rejet DM, 3.4) et `REJECTED_BY_AUDIT` (rejet Audit, 3.8) → base des deux taux de reprise.
- **`ExtensionRequest`** (`models.py:926`) : `Status.APPROVED` (`models.py:943-946`) → taux de glissement ; `requested_date`/`due_date` pour la dérive.
- **`HmacSeal`** (`code/apps/audit/models.py:101`) : OneToOne `recommendation.hmac_seal` → couverture de scellement.
- **Sélecteurs dashboards existants** (`code/apps/dashboards/selectors.py`) : `get_recommendations_for_user` (RBAC), `_get_department_breakdown`, `_get_descendants_map`, `_enrich_with_aging`, `_get_stacked_bar_json`, `get_audit_kpis` (gabarit aggregate multi-Count + exclusion DRAFT + compteurs mensuels). `_get_dg_dashboard_qs` exclut DRAFT.
- **Vues** (`code/apps/dashboards/views.py`) : `_dg_context` (l.132), `_audit_context` (l.147) — points d'injection des nouveaux contextes.
- **Cron** : `run_nightly_notifications` (`workflow/services.py:1536`, orchestrateur isolé), `flag_overdue_recommendations` (`services.py:1322`). Schedule Django-Q2 via migrations `workflow/0015`, repointé `0016`.
- **Export déjà disponible** : XLSX via openpyxl (`workflow/views.py:2389` et `:2507`, dép. `requirements/base.txt:11`), ZIP `BytesIO` (`workflow/views_missions.py:41-55`). **Aucune lib PDF** installée.
- **Chart.js** : partials `templates/dashboards/partials/bar_chart.html`, `kpi_card.html` ; palette de statuts `_STACKED_SEGMENTS` (`selectors.py`).

### 🚨 Pièges techniques (tous vérifiés)

#### Piège 1 — Médiane : Python obligatoire, jamais SQL
Prod = PostgreSQL (`config/settings/base.py:120`) **mais tests = SQLite** (`config/settings/test.py:9`). Tout `percentile_cont`/raw SQL **casserait la suite de tests**. → `_lead_time_stats` charge les deltas en Python et utilise `statistics.median`. Volume BICEC (≤ quelques milliers de recos clôturées) : coût négligeable.

#### Piège 2 — `progress_percentage` est une `@property`, pas un champ SQL
`models.py:416-428` : 2 `COUNT()` par appel. **Impossible de filtrer dessus en SQL** ; l'utiliser dans une boucle = N+1. → `get_at_risk_recommendations` **annote** le queryset : `Count('deliverables', filter=Q(deliverables__is_completed=True))` et `Count('deliverables')`, puis filtre le ratio < 0.5 en base (ou en Python sur le queryset déjà annoté). Vérifier via `assertNumQueries` (AC8).

#### Piège 3 — AuditLog n'a AUCUN index → dwell-time différé
Les index de `audit/migrations/0002_initial` (dont `(content_type, object_id)` et `(action, -created_at)`) ont **tous été retirés** par `0003_remove_..._idx_and_more.py`. Reconstruire le temps-par-étape depuis `AuditLog action=TRANSITION` ferait donc un **full scan** + parsing JSON `changes`. → **Différé (Sprint E)**. ⚠ Si repris : un champ `status_changed_at` sur `Recommendation` ne donnerait que le *temps depuis le dernier changement* (stagnation), **pas** le temps médian par étape des dossiers clôturés — ne pas confondre.

#### Piège 4 — Reddition = Excel/ZIP, PAS de PDF
Aucune lib PDF dans `requirements/base.txt` ; en introduire une (WeasyPrint→GTK/Cairo, ReportLab) complique l'image Docker on-premise. La doctrine projet (epics.md, Additional Requirements : « pas de librairie backend PDF complexe type ReportLab/WeasyPrint exigée pour le MVP ») confirme. → Export **Excel (openpyxl déjà présent)** + **ZIP** ; le rendu imprimable navigateur (`@media print`, Story 6.3) couvre le besoin PDF. PDF natif = Sprint E.

#### Piège 5 — Snapshot vide au jour 1
`MetricsSnapshot` est vide au démarrage → courbes plates pendant ~30 j. La commande `backfill_metrics_snapshot` reconstitue ~90 j : les **volumes** (créées/clôturées) sont exacts depuis `created_at`/`closed_at`, mais les **buckets d'aging** historiques sont **approximatifs** (l'état `is_overdue` passé n'est pas stocké). Documenter cette limite dans la commande et l'UI (« tendances de volume fiables ; aging historique reconstitué »).

#### Piège 6 — `capture_daily_snapshot` ne fait QUE du calcul + snapshot
Le futur `dashboards/services.py` ne doit contenir **aucune** logique d'écriture métier (pas de mutation de `Recommendation`, pas de FSM, pas de notif). Pur calcul → `update_or_create(MetricsSnapshot)`. Cohérent avec la convention HackSoft (services = écriture, mais ici écriture **analytique** isolée).

### Définitions formelles des indicateurs (à figer — auditables)

| Indicateur | Formule | Source |
|---|---|---|
| Délai de remédiation | `statistics.median(closed_at − created_at)` par `priority` | `closed_at`, `created_at` |
| On-time **strict** | `closed_at ≤ original_due_date` / total clôturées | `closed_at`, `original_due_date` |
| On-time **tolérant** | `closed_at ≤ due_date` / total clôturées | `closed_at`, `due_date` |
| Reprise **DM** | recos avec ≥1 `EvidenceSubmission` `REJECTED` / total | `EvidenceSubmission.status` |
| Reprise **Audit** | recos avec ≥1 `REJECTED_BY_AUDIT` / total | `EvidenceSubmission.status` |
| Exposition **stock** | Σ poids_criticité sur externes ouvertes | `source.is_external`, `priority` |
| Exposition **vieillissement** | Σ (poids_criticité × jours_retard) sur externes en retard | + `is_overdue`, `original_due_date` |
| Glissement | % recos avec ≥1 `ExtensionRequest APPROVED` ; dérive moy. `due_date − original_due_date` | `ExtensionRequest` |
| À risque de bascule | non clôturée ∧ `due_date ∈ [today, +30j]` ∧ progression < 50% | `due_date`, annotation livrables |
| Couverture scellement | clôturées avec `hmac_seal` / total clôturées | `HmacSeal` |

Poids criticité : CRITIQUE=4, HAUTE=3, MOYENNE=2, FAIBLE=1.

### Patterns à réutiliser
- `get_recommendations_for_user` (`workflow/selectors.py`) — base RBAC de **tout** queryset.
- `get_audit_kpis` (`dashboards/selectors.py`) — gabarit `aggregate()` multi-`Count` + exclusion DRAFT + compteurs mensuels.
- `_get_department_breakdown` / `_get_descendants_map` / `_enrich_with_aging` — agrégation par direction + aging.
- `run_nightly_notifications` (`workflow/services.py:1536`) — pattern d'orchestrateur cron à phases isolées.
- Export : `workflow/views.py:2389` (XLSX openpyxl), `workflow/views_missions.py` (ZIP `BytesIO` + `FileResponse`).
- Chart.js : `bar_chart.html`, `kpi_card.html`.

### Project Structure Notes

**Fichiers à créer :**
- `code/apps/dashboards/services.py`
- `code/apps/dashboards/management/commands/capture_metrics_snapshot.py`
- `code/apps/dashboards/management/commands/backfill_metrics_snapshot.py`
- `code/apps/dashboards/migrations/000X_metricssnapshot.py`
- `code/templates/dashboards/partials/line_chart.html`
- `code/apps/dashboards/tests/test_pilotage.py`

**Fichiers à modifier :**
- `code/apps/dashboards/models.py` (`MetricsSnapshot`)
- `code/apps/dashboards/selectors.py` (helpers + sélecteurs KPI/KRI/gouvernance)
- `code/apps/dashboards/views.py` (`_dg_context`, `_audit_context`)
- `code/apps/dashboards/urls.py` (route export reddition)
- `code/apps/workflow/services.py` (3e phase dans `run_nightly_notifications`)
- `code/templates/dashboards/dg_dashboard.html`, `audit_dashboard.html` (sections Efficacité / Risques / Reddition)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (statut story)

### Design (sobriété institutionnelle — réutilisé de 6.2.0 / 6.5)
Outil de gouvernance bancaire, pas de marketing. Tokens `tailwind.config.js` uniquement, `sentinel-orange` réservé à une seule action primaire par vue, `tabular-nums` pour les chiffres/compteurs, badges pâles. Interdits : gradients héros, glow, glassmorphism, emojis décoratifs. Courbes Chart.js sobres, cohérentes avec `_STACKED_SEGMENTS`.

### NFR couverts
- **NFR-PERF-02** (rendu < 200ms P95) — agrégats pré-calculés (snapshot) + `aggregate()` unique, pas de N+1 (AC8).
- **NFR-SEC-05** (AuditLog append-only) — export émet une entrée `EXPORT`.
- **Traçabilité COBAC** — exposition réglementaire séparée (stock + vieillissement) auditable + couverture de scellement.

### References
- `_bmad-output/planning-artifacts/epics.md` — Epic 6 (FR29-FR32), Additional Requirements (« pas de PDF backend complexe MVP »).
- `_bmad-output/implementation-artifacts/6-1c-dashboard-audit.md` — gabarit sélecteurs/inbox Audit, Section 5 Performance.
- `_bmad-output/implementation-artifacts/6-5-import-massif-recommandations-draft.md` — conventions openpyxl, AuditLog `content_type` littéral, design sobre.
- `code/apps/dashboards/selectors.py` · `code/apps/dashboards/views.py` · `code/apps/workflow/services.py:1536` · `code/apps/workflow/models.py:149` · `code/apps/audit/models.py:101` — sources de vérité citées.

## Dev Agent Record

### Agent Model Used
_(à compléter à l'implémentation)_

### Completion Notes List
- _(à compléter)_

### File List
- _(à compléter)_
