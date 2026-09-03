# Story 6.1a : Socle Dashboard + Dashboard Directeur Métier (DM)

Status: done

<!-- Prérequis : Epics 1–5 entièrement terminées. App dashboards/ est un stub vide (models.py vide, pas de views/urls/templates). -->
<!-- Décision architecturale : vue adaptative unique /tableau-de-bord/ → DashboardView → template par rôle. -->
<!-- Chart.js 4.x en fichier statique local (code/static/js/chart.umd.min.js) — BICEC on-premise, pas de CDN. -->
<!-- Stories dépendantes : 6.1b (DG) et 6.1c (Audit) réutiliseront tous les composants créés ici. -->

## Story

As a **Directeur Métier (DM)**,
I want **un tableau de bord 360° de ma direction — KPIs, file d'attente, répartition par statut, aging**,
so that **je vois immédiatement l'état de conformité de mon périmètre et les actions que j'ai à mener (FR29, FR30)**.

As a **ETP (Entité)**,
I want **une vue légère de mes recommandations déléguées**,
so that **je gère mes échéances sans me noyer dans les recos hors périmètre**.

## Acceptance Criteria

1. **AC1 — Socle infrastructure**
   - **Given** un utilisateur connecté avec rôle DM, ETP, DG ou AUDIT
   - **When** il accède à `/tableau-de-bord/`
   - **Then** `DashboardView` retourne le template correspondant à son rôle (200 OK)
   - **And** un utilisateur non connecté est redirigé vers `/auth/login/`
   - **And** un utilisateur ADMIN_IT ou EXT reçoit 403 (WorkflowAccessMixin)

2. **AC2 — Redirection home**
   - **Given** l'URL `/` (home actuelle — placeholder TemplateView)
   - **When** un utilisateur connecté y accède
   - **Then** il est redirigé (302) vers `/tableau-de-bord/`

3. **AC3 — KPIs DM (bande supérieure, 5 cartes)**
   - **Given** un DM connecté
   - **When** il affiche son dashboard
   - **Then** 5 cartes KPI sont visibles : Total actives / En retard OVERDUE / En attente de ma validation (PENDING_DM_REVIEW) / Taux de clôture (%) / Critiques non clôturées
   - **And** les KPIs sont scoped à la direction du DM + ses sous-directions (RBAC via `get_recommendations_for_user`)
   - **And** le taux de clôture est 0% si aucune reco (pas de division par zéro)

4. **AC4 — Donut Chart répartition par statut (DM)**
   - **Given** un DM connecté
   - **When** il affiche son dashboard
   - **Then** un donut Chart.js affiche la répartition ASSIGNED / IN_PROGRESS / PENDING_DM_REVIEW / PENDING_AUDIT_REVIEW / OVERDUE / CLOSED_RESOLVED
   - **And** le chart est rendu client-side depuis des données JSON injectées dans le template (`escapejs`, pas d'appel AJAX)

5. **AC5 — File d'attente DM (`PENDING_DM_REVIEW`)**
   - **Given** des preuves soumises par des ETPs dans la direction du DM
   - **When** il affiche son dashboard
   - **Then** un tableau cliquable affiche ces recos (Référence, ETP soumetteur, Priorité, Échéance)
   - **And** chaque ligne est un lien vers la page de détail
   - **And** si aucune preuve en attente, un état vide friendly est affiché

6. **AC6 — Tableau aging / urgence (DM)**
   - **Given** des recommandations actives dans la direction du DM
   - **When** il affiche le tableau
   - **Then** les recos actives non-clôturées sont triées par urgence (overdue d'abord, puis due_date ASC)
   - **And** chaque ligne a une bande couleur gauche : rouge (OVERDUE), orange (due_date ≤ J+30), vert (J+30)
   - **And** colonne "Aging" : "J+N retard" (rouge), "Dans N jours" (orange), "OK" (vert)
   - **And** aging calculé sur `original_due_date` pour les retards, `due_date` pour les warnings
   - **And** limité à 50 lignes

7. **AC7 — Dashboard ETP (vue légère)**
   - **Given** un utilisateur ETP connecté
   - **When** il affiche `/tableau-de-bord/`
   - **Then** 4 KPI cards : Mes actives / En retard / En cours (IN_PROGRESS) / Clôturées
   - **And** tableau des recos déléguées trié par échéance
   - **And** pas de graphique Chart.js

8. **AC8 — Sidebar : lien dashboard actif**
   - **Given** n'importe quel rôle workflow
   - **When** il est sur `/tableau-de-bord/`
   - **Then** le lien "Tableau de Bord" dans la sidebar est mis en surbrillance

9. **AC9 — Tests**
   - Sélecteurs : zéro N+1, scoping RBAC correct pour DM et ETP
   - Vue : 200 pour DM/ETP/DG/AUDIT, 403 pour ADMIN, 302 pour anonyme
   - Isolation RBAC : DM dept A ne voit pas les recos de dept B

## Tasks / Subtasks

- [ ] **Task 1 — Sélecteurs** (`code/apps/dashboards/selectors.py`)
  - [ ] 1.1 : `get_dm_kpis(*, user) -> dict` — une seule requête `aggregate()` multi-`Count(filter=Q(...))`. Champs : `total_actives`, `overdue`, `pending_dm_review`, `closed_resolved`, `total_all`, `critique_open`. `taux_cloture` calculé en Python (0 si total=0).
  - [ ] 1.2 : `get_dm_donut_data(*, user) -> dict` — retourne `{labels, values, colors}` pour Chart.js. Segments : ASSIGNED, IN_PROGRESS, PENDING_DM_REVIEW, PENDING_AUDIT_REVIEW, OVERDUE (is_overdue=True parmi actives), CLOSED_RESOLVED.
  - [ ] 1.3 : `get_dm_pending_validation(*, user) -> QuerySet` — `.filter(status=PENDING_DM_REVIEW)` sur la base RBAC. `select_related("assigned_etp", "department")`. Ordonné `due_date`.
  - [ ] 1.4 : `get_dm_urgency_rows(*, user, limit=50) -> list[dict]` — recos actives non-clôturées et non-DRAFT. Enrichies `aging_band` + `days_delta`. Ordonné `-is_overdue, due_date`. Slicé à `limit`.
  - [ ] 1.5 : `get_etp_kpis(*, user) -> dict` — `total_actives`, `overdue`, `in_progress`, `closed_resolved`.
  - [ ] 1.6 : `get_etp_rows(*, user) -> QuerySet` — recos `assigned_etp=user`, non clôturées. `select_related("department")`. Ordonné `due_date`.
  - [ ] **IMPÉRATIF** : tous les sélecteurs partent de `get_recommendations_for_user(user=user)` (RBAC fail-closed).

- [ ] **Task 2 — Vue et URLs**
  - [ ] 2.1 : Créer `code/apps/dashboards/views.py` — `DashboardView(WorkflowAccessMixin, TemplateView)` avec `get_template_names()` (dispatch par `user.role`) et `get_context_data()` (helpers `_common_context`, `_dm_context`, `_etp_context`, stubs vides `_dg_context`/`_audit_context` avec commentaire TODO 6.1b/6.1c).
  - [ ] 2.2 : Créer `code/apps/dashboards/urls.py` — `app_name = "dashboards"`, `path("", DashboardView.as_view(), name="home")`.
  - [ ] 2.3 : Modifier `code/config/urls.py` : ajouter `path("tableau-de-bord/", include("apps.dashboards.urls", namespace="dashboards"))` + remplacer la home `TemplateView` par `RedirectView.as_view(pattern_name="dashboards:home", permanent=False)` (garder `name="home"`).

- [ ] **Task 3 — Templates partagés**
  - [ ] 3.1 : Créer `code/templates/dashboards/_base_dashboard.html` — extend `layouts/app_shell.html`. Définit sous-blocs `dashboard_kpis`, `dashboard_charts`, `dashboard_tables` à l'intérieur de `{% block content %}`.
  - [ ] 3.2 : Créer `code/templates/components/donut_chart.html` — accepte `chart_id` (unique obligatoire) et `chart_data_json`. Canvas + `<script>` Chart.js inline avec `JSON.parse('{{ chart_data_json|escapejs }}')`.
  - [ ] 3.3 : Vérifier que `code/static/js/chart.umd.min.js` existe. L'inclure dans `_base_dashboard.html` via `{% load static %}<script src="{% static 'js/chart.umd.min.js' %}"></script>`.

- [ ] **Task 4 — Dashboard DM**
  - [ ] 4.1 : Créer `code/templates/dashboards/dm_dashboard.html` — extend `_base_dashboard.html`. KPIs (5 kpi_card.html), donut_chart, file d'attente PENDING_DM_REVIEW, urgency_table partial.
  - [ ] 4.2 : Créer `code/templates/dashboards/partials/urgency_table.html` — tableau avec bandes couleur, colonnes Référence/Statut/Priorité/Échéance/Aging/ETP assigné.
  - [ ] 4.3 : Créer `code/templates/dashboards/dg_dashboard.html` — stub minimal (extend `_base_dashboard.html`, message "À implémenter Story 6.1b").
  - [ ] 4.4 : Créer `code/templates/dashboards/audit_dashboard.html` — idem stub.

- [ ] **Task 5 — Dashboard ETP**
  - [ ] 5.1 : Créer `code/templates/dashboards/etp_dashboard.html` — extend `_base_dashboard.html`. 4 KPI cards. Tableau recos déléguées. Pas de Chart.js.

- [ ] **Task 6 — Sidebars**
  - [ ] Vérifier pattern `active_route` dans les sidebars existantes (comment la surbrillance est gérée).
  - [ ] Modifier `sidebar_dm.html` : lien vers `{% url 'dashboards:home' %}`.
  - [ ] Modifier `sidebar_etp.html` : idem.
  - [ ] Modifier `sidebar_dg.html` : idem.
  - [ ] Modifier `sidebar_audit.html` : idem.

- [ ] **Task 7 — Tests**
  - [ ] Créer `code/apps/dashboards/tests/__init__.py` + `test_selectors.py` + `test_views.py`.
  - [ ] Sélecteurs : scoping DM, counts corrects, zero state, aging bands, capped 50, ETP scoped.
  - [ ] Vues : 200/403/302 par rôle, redirection home, isolation RBAC inter-dept.

- [ ] **Task 8 — sprint-status.yaml**
  - [ ] Remplacer `6-1-dashboard-supervision-indicateurs-urgence: backlog` par les 3 sous-stories.
  - [ ] Marquer `epic-5: done`.

## Dev Notes

### Architecture Pattern

```
DashboardView(WorkflowAccessMixin, TemplateView)
├── get_template_names()    → dispatch user.role → template différent
└── get_context_data()
    ├── _common_context()   → topbar_title, topbar_subtitle, active_route="dashboard"
    ├── _dm_context()       → kpis, donut_data_json, pending_validation, urgency_rows
    ├── _etp_context()      → kpis, etp_rows
    ├── _dg_context()       → {} + TODO 6.1b
    └── _audit_context()    → {} + TODO 6.1c
```

### Réutilisation — NE PAS recréer

- `code/templates/components/kpi_card.html` — variables : `title`, `value`, `accent` (primary|destructive|success|warning|info), `icon_svg` (optionnel), `delta`, `delta_label`.
- `code/templates/components/status_badge.html` — badge couleur par statut FSM.
- `code/apps/workflow/selectors.py::get_recommendations_for_user(*, user)` — base RBAC obligatoire.
- `code/apps/users/mixins.py::WorkflowAccessMixin` — 403 pour ADMIN_IT et EXT.
- `code/templates/layouts/app_shell.html` — layout avec sidebar/topbar.

### active_route — vérifier avant Task 6

Avant de modifier les sidebars, chercher comment `active_route` (ou équivalent) est déjà utilisé pour la surbrillance du lien "Recommandations" dans `sidebar_dm.html`. Reproduire exactement le même pattern pour le lien dashboard. Si le context processor gère ça, ne pas dupliquer dans la vue.

### Chart.js — flux données (views.py → template)

```python
import json
ctx["donut_data_json"] = json.dumps({
    "labels": ["Assignée", "En cours", "Revue DM", "Revue Audit", "En retard", "Clôturée"],
    "values": [agg["assigned"], agg["in_progress"], agg["pending_dm_review"],
               agg["pending_audit_review"], agg["overdue_active"], agg["closed_resolved"]],
    "colors": ["#3B82F6", "#F59E0B", "#F97316", "#6366F1", "#EF4444", "#10B981"],
})
```

```html
{# donut_chart.html — utiliser escapejs, PAS safe (XSS) #}
<canvas id="{{ chart_id }}" height="220"></canvas>
<script>
(function() {
  var d = JSON.parse('{{ chart_data_json|escapejs }}');
  new Chart(document.getElementById("{{ chart_id }}"), {
    type: "doughnut",
    data: { labels: d.labels, datasets: [{ data: d.values, backgroundColor: d.colors, borderWidth: 2 }] },
    options: { cutout: "65%", plugins: { legend: { position: "right" } } }
  });
})();
</script>
```

### Aging — logique sélecteur

```python
from datetime import timedelta
from django.utils import timezone

today = timezone.localdate()
warning_threshold = today + timedelta(days=30)

for rec in qs:
    if rec.is_overdue:
        aging_band = "overdue"
        days_delta = (today - rec.original_due_date).days  # positif = nb jours de retard
    elif rec.due_date <= warning_threshold:
        aging_band = "warning"
        days_delta = (rec.due_date - today).days            # positif = jours restants
    else:
        aging_band = "ok"
        days_delta = None
```

### Aging — template bandes couleur

```html
<tr class="{% if row.aging_band == 'overdue' %}border-l-4 border-l-red-500 bg-red-50/30
           {% elif row.aging_band == 'warning' %}border-l-4 border-l-orange-400 bg-orange-50/20
           {% else %}border-l-4 border-l-green-400{% endif %}">
  ...
  <td>
    {% if row.aging_band == 'overdue' %}
      <span class="text-red-600 font-semibold">J+{{ row.days_delta }} retard</span>
    {% elif row.aging_band == 'warning' %}
      <span class="text-orange-500">Dans {{ row.days_delta }}j</span>
    {% else %}
      <span class="text-green-600">OK</span>
    {% endif %}
  </td>
```

### Branche Git

`feat/story-6.1a-socle-dashboard-dm`

### Fichiers nouveaux

- `code/apps/dashboards/selectors.py`
- `code/apps/dashboards/views.py`
- `code/apps/dashboards/urls.py`
- `code/apps/dashboards/tests/__init__.py`
- `code/apps/dashboards/tests/test_selectors.py`
- `code/apps/dashboards/tests/test_views.py`
- `code/templates/dashboards/_base_dashboard.html`
- `code/templates/dashboards/dm_dashboard.html`
- `code/templates/dashboards/dg_dashboard.html`
- `code/templates/dashboards/audit_dashboard.html`
- `code/templates/dashboards/etp_dashboard.html`
- `code/templates/dashboards/partials/urgency_table.html`
- `code/templates/components/donut_chart.html`

### Fichiers modifiés

- `code/config/urls.py`
- `code/templates/partials/sidebar_audit.html`
- `code/templates/partials/sidebar_dm.html`
- `code/templates/partials/sidebar_etp.html`
- `code/templates/partials/sidebar_dg.html`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6]
- [Source: code/apps/workflow/selectors.py — get_recommendations_for_user]
- [Source: code/apps/workflow/models.py — Recommendation.Status, Priority, is_overdue, original_due_date]
- [Source: code/templates/components/kpi_card.html]
- [Source: code/apps/users/mixins.py — WorkflowAccessMixin]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
