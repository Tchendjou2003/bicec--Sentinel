# Story 2.1: Création Unitaire — Formulaire Stepper & Livrables

Status: done

## Story

As an **Audit Interne**,
I want **créer unitairement une recommandation via un assistant par étapes (Stepper) et définir ses livrables, tout en la conservant en état « Brouillon (DRAFT) »**,
so that **je puisse structurer clairement ses différents éléments (mission, constats, plan d'action) sans charge cognitive excessive avant de l'assigner officiellement.**

## Acceptance Criteria (BDD)

### AC1 — Création via Stepper (Slide-over)

**Given** un Auditeur Interne connecté (rôle = `AUDIT`),
**When** il clique sur "Nouvelle recommandation" depuis la page liste,
**Then** un tiroir latéral (Slide-over, largeur 55%) s'ouvre depuis la droite avec un formulaire en 4 étapes :

| Étape | Champs | Widgets | Requis ? |
|---|---|---|---|
| **1. Contexte** | Date de mission | `<input type="date">` | Oui |
| | Libellé mission | `<input type="text">` | Oui |
| | Direction contrôlée | `<select>` (Departments actifs) | Oui |
| | Source | `<select>` (7 choix fixes) | Oui |
| **2. Constats** | Observations | `<textarea rows="5">` | Oui |
| | Dossiers en anomalies | `<textarea rows="3">` | Non |
| **3. Recommandation** | Référence (saisie manuelle) | `<input type="text" placeholder="REC-2026-...">` | Oui |
| | Texte de la recommandation | `<textarea rows="5">` | Oui |
| | Criticité | `<select>` (4 choix) | Oui |
| | Direction concernée | `<select>` (Departments) | Non |
| | Date de mise en œuvre | `<input type="date">` | Oui |
| **4. Livrables** | N livrables dynamiques | `<input type="text">` + bouton ✕ | ≥ 1 recommandé |

**And** la soumission finale sauvegarde atomiquement la recommandation + ses livrables avec statut `DRAFT` (FR5, FR6b).
**And** `created_by` = utilisateur connecté, `original_due_date` = `due_date`.
**And** une entrée `AuditLog` (`action=CREATE`, `content_type=Recommendation`) est générée avec l'IP.
**And** le slide-over se ferme et l'utilisateur voit la nouvelle ligne dans le tableau avec un toast de succès.

### AC2 — Tableau épuré (Écran Radar)

**Given** la page `/audit/recommandations/`,
**When** l'auditeur la consulte,
**Then** :
- Des **filtres horizontaux compacts** (Source, Statut, Criticité, Recherche texte) sont alignés au-dessus du tableau, rafraîchis via HTMX sans rechargement de page.
- Le tableau affiche les colonnes : **Réf**, **Mission** (tronqué via CSS `truncate max-w-xs`), **Source**, **Échéance**, **Statut** (badge couleur), **⋯** (menu actions).
- **Pas de colonne Avancement** dans le tableau (inutile au stade DRAFT).
- Toute la ligne est cliquable → page de détail. Le menu ⋯ a un `z-index` supérieur.
- Pagination : 25 éléments par page.
- Si `is_overdue = True`, la date d'échéance s'affiche en rouge avec icône ⚠️.
- Les recommandations `is_deleted=True` sont exclues (Custom Manager).

### AC3 — Empty State

**Given** un Auditeur Interne sans aucune recommandation créée,
**When** il accède à `/audit/recommandations/`,
**Then** un état vide soigné s'affiche avec une illustration, un texte (« Aucune recommandation pour le moment ») et un gros bouton « Créer ma première recommandation ».

### AC4 — Actions contextuelles (Menu ⋯)

**Given** une recommandation en état `DRAFT` dans le tableau,
**When** l'auditeur clique sur le menu ⋯,
**Then** il voit "Modifier" et "Supprimer".
**And** ces options ne sont visibles que pour les recommandations en `DRAFT`.
**And** le clic sur "Supprimer" ouvre une micro-modale de confirmation.

### AC5 — Soft Delete d'un brouillon

**Given** l'auditeur confirme la suppression,
**Then** `is_deleted=True`, `deleted_at=now()`, la reco disparaît du tableau.
**And** les livrables associés restent en base mais sont filtrés via la reco parente (Custom Manager).
**And** une entrée `AuditLog` (`action=DELETE`) est créée.

### AC6 — Soft Delete impossible hors DRAFT

**Given** une recommandation en état `ASSIGNED`, `IN_PROGRESS` ou autre,
**When** un utilisateur tente un soft delete,
**Then** l'opération est refusée avec `ValueError` (FR6).

### AC7 — Isolation RBAC

**Given** un utilisateur non-Audit (DM, ETP, DG, EXT, ADMIN),
**When** il tente d'accéder à `/audit/recommandations/` ou toute URL sous `/audit/`,
**Then** HTTP 403 Forbidden. Les brouillons ne sont visibles que par le pool Audit.

### AC8 — Page "Centre de Contrôle" (Détail)

**Given** une recommandation existante,
**When** l'auditeur clique sur sa ligne,
**Then** il atterrit sur `/audit/recommandations/<uuid>/` avec :
- **Fil d'Ariane** : `Recommandations > REC-xxx`
- **Barre d'actions sticky** : Statut, Assigner (grisé — Story 2.5), Modifier (DRAFT), Supprimer (DRAFT)
- **Layout Split 60/40** :
  - Gauche : Contexte mission, Observations, Texte recommandation, Dossiers anomalies
  - Droite : Barre d'avancement (`progress_percentage`), Checklist livrables, Timeline AuditLog

### AC9 — Modification d'un brouillon

**Given** une recommandation en `DRAFT`,
**When** l'auditeur clique "Modifier" (depuis le menu ⋯ ou la page détail),
**Then** le stepper slide-over se rouvre prérempli avec les données existantes.
**And** les modifications sont sauvegardées avec un delta dans l'AuditLog (`action=UPDATE`, format `{"champ": ["ancien", "nouveau"]}`).

### AC10 — Validation stricte

**Given** un formulaire soumis avec des données invalides,
**Then** :
- `reference` doit être unique en base (sinon erreur).
- `due_date` dans le passé → erreur.
- Champs requis vides → erreur inline sur l'étape concernée.

## Tasks / Subtasks

### Task 1 : Modèle `Recommendation` complet (apps/workflow/models.py)

- [x] 1.1 — Enums `TextChoices` :
  ```python
  class Source(models.TextChoices):
      INTERNE = "INTERNE", _("Audit Interne")
      COBAC = "COBAC", _("COBAC")
      CAC = "CAC", _("CAC")
      ANIF = "ANIF", _("ANIF")
      BEAC = "BEAC", _("BEAC")
      ANTIC = "ANTIC", _("ANTIC")
      CONSULTANT = "CONSULTANT", _("Consultant")

  class Priority(models.TextChoices):
      CRITIQUE = "CRITIQUE", _("Critique")
      HAUTE = "HAUTE", _("Haute")
      MOYENNE = "MOYENNE", _("Moyenne")
      FAIBLE = "FAIBLE", _("Faible")

  class Status(models.TextChoices):
      DRAFT = "DRAFT", _("Brouillon")
      ASSIGNED = "ASSIGNED", _("Assignée")
      IN_PROGRESS = "IN_PROGRESS", _("En cours")
      PENDING_DM_REVIEW = "PENDING_DM_REVIEW", _("Validation DM")
      PENDING_AUDIT_REVIEW = "PENDING_AUDIT_REVIEW", _("Validation Audit")
      CLOSED_RESOLVED = "CLOSED_RESOLVED", _("Clôturée")
  ```

- [x] 1.2 — Champs complets du modèle `Recommendation` :

  | Champ | Type Django | Contrainte | Colonne Métier |
  |---|---|---|---|
  | `id` | UUIDField(PK) | auto | *(interne)* |
  | `reference` | CharField(50) | NOT NULL, **unique** | Référence Recos |
  | `mission_date` | DateField | NULL, blank | Date de la Mission |
  | `mission_label` | CharField(255) | blank=True | Libellé de la Mission |
  | `controlled_department` | FK → Department | NULL, blank, PROTECT | Direction contrôlée |
  | `observations` | TextField | blank=True | Observation(s) |
  | `anomalous_dossiers` | TextField | blank=True | Dossiers en anomalies |
  | `description` | TextField | NOT NULL | Texte de la recommandation |
  | `source` | CharField(20) | NOT NULL, choices | Source |
  | `priority` | CharField(10) | NOT NULL, choices | Criticité |
  | `department` | FK → Department | NULL, blank, PROTECT | Direction concernée |
  | `due_date` | DateField | NOT NULL | Date de mise en œuvre |
  | `original_due_date` | DateField | NOT NULL | *(copie immutable)* |
  | `status` | FSMField(30) | default=DRAFT, protected | *(FSM)* |
  | `is_overdue` | BooleanField | default=False | *(scheduler)* |
  | `created_by` | FK → User | NOT NULL, PROTECT | *(auteur)* |
  | `assigned_dm` | FK → User | NULL, SET_NULL | *(DM — Story 2.5)* |
  | `assigned_etp` | FK → User | NULL, SET_NULL | *(ETP — Story 3.2)* |
  | `import_tag` | CharField(10) | NULL, blank | *(tag IMPORTED)* |
  | `is_deleted` | BooleanField | default=False | *(soft delete)* |
  | `deleted_at` | DateTimeField | NULL, blank | *(horodatage)* |
  | `created_at` | DateTimeField | auto_now_add | *(timestamp)* |
  | `updated_at` | DateTimeField | auto_now | *(timestamp)* |

  > **CRITIQUE** : Tous les 23 champs dans une seule migration propre `0001_initial.py`.

- [x] 1.3 — Indexes de performance :
  ```python
  indexes = [
      models.Index(fields=["status"], name="idx_reco_status"),
      models.Index(fields=["created_by"], name="idx_reco_created_by"),
      models.Index(fields=["assigned_dm"], name="idx_reco_assigned_dm"),
      models.Index(fields=["department"], name="idx_reco_department"),
      models.Index(fields=["is_overdue"], name="idx_reco_overdue"),
      models.Index(fields=["priority"], name="idx_reco_priority"),
  ]
  ```

- [x] 1.4 — Custom Manager :
  ```python
  class ActiveRecommendationManager(models.Manager):
      def get_queryset(self):
          return super().get_queryset().filter(is_deleted=False)

  # Sur le modèle :
  objects = ActiveRecommendationManager()  # défaut
  all_objects = models.Manager()           # admin
  ```

- [x] 1.5 — Validation `clean()` : `due_date` pas dans le passé, `reference` unique.

### Task 2 : Modèle `Deliverable` (apps/workflow/models.py)

- [x] 2.1 — Champs complets :

  | Champ | Type | Contrainte |
  |---|---|---|
  | `id` | UUIDField(PK) | auto |
  | `recommendation` | FK → Recommendation | CASCADE, related_name="deliverables" |
  | `label` | CharField(255) | NOT NULL |
  | `order` | PositiveIntegerField | default=0 |
  | `is_completed` | BooleanField | default=False |
  | `completed_at` | DateTimeField | NULL, blank |
  | `completed_by` | FK → User | NULL, SET_NULL |
  | `created_at` | DateTimeField | auto_now_add |

- [x] 2.2 — Propriété calculée sur `Recommendation` :
  ```python
  @property
  def progress_percentage(self) -> int:
      total = self.deliverables.count()
      if total == 0:
          return 0
      completed = self.deliverables.filter(is_completed=True).count()
      return round((completed / total) * 100)
  ```

### Task 3 : Mixin d'accès (apps/users/mixins.py)

- [x] 3.1 — `AuditRequiredMixin(LoginRequiredMixin)` : Autorise `role=AUDIT` ou `is_superuser`. Sinon `PermissionDenied`.

### Task 4 : Services (apps/workflow/services.py)

- [x] 4.1 — `create_recommendation(*, data, deliverables_data, performed_by, ip_address)` :
  - `@transaction.atomic`, keyword-only args
  - Crée `Recommendation` + N `Deliverable` + `AuditLog(action=CREATE)`
  - Initialise `original_due_date = due_date`

- [x] 4.2 — `update_recommendation(*, recommendation, data, performed_by, ip_address)` :
  - `@transaction.atomic`, `select_for_update()`
  - Calcule le delta avant/après, sauvegarde, `AuditLog(action=UPDATE)`

- [x] 4.3 — `soft_delete_recommendation(*, recommendation, performed_by, ip_address)` :
  - Vérifie `status == DRAFT` sinon `ValueError`
  - `is_deleted=True`, `deleted_at=now()`, `AuditLog(action=DELETE)`

### Task 5 : Selectors (apps/workflow/selectors.py)

- [x] 5.1 — `get_recommendations_for_audit(user)` → QuerySet filtré (non supprimées).
- [x] 5.2 — `get_recommendation_by_id(pk, user)` → avec contrôle RBAC.
- [x] 5.3 — `get_recommendation_detail(pk)` → avec `prefetch_related("deliverables")`.

### Task 6 : Forms & FormSets (apps/workflow/forms.py)

- [x] 6.1 — `RecommendationForm(ModelForm)` :
  - Champs visibles : `reference`, `mission_date`, `mission_label`, `controlled_department`, `observations`, `anomalous_dossiers`, `description`, `source`, `priority`, `department`, `due_date`
  - Exclure : `status`, `created_by`, `assigned_dm`, `assigned_etp`, `is_deleted`, `deleted_at`, `import_tag`, `original_due_date`, `is_overdue`
  - Styling Tailwind (`_INPUT_CLASS` pattern de `apps/users/forms.py`)
  - Widget `date` natif pour `mission_date`, `due_date`
  - `clean_due_date()` : interdit les dates passées

- [x] 6.2 — `DeliverableFormSet` via `inlineformset_factory(Recommendation, Deliverable, fields=["label"], extra=1, can_delete=True)`.

### Task 7 : Views (apps/workflow/views.py)

- [x] 7.1 — `RecommendationListView(AuditRequiredMixin, ListView)` :
  - Template : `workflow/recommendation_list.html`, pagination 25
  - Filtre par query params (`?source=`, `?status=`, `?priority=`, `?q=`)
  - Context : `active_route="recommandations"`, `topbar_title`
  - Support HTMX pour filtres inline

- [x] 7.2 — `RecommendationCreateView(AuditRequiredMixin, View)` :
  - GET : retourne le partial `stepper_slideover.html` (via HTMX `hx-get`)
  - POST : appelle `services.create_recommendation()`, retourne réponse HTMX avec toast

- [x] 7.3 — `RecommendationDetailView(AuditRequiredMixin, DetailView)` :
  - Template : `workflow/recommendation_detail.html`
  - Split layout 60/40, fil d'ariane, barre d'actions sticky
  - Prefetch deliverables

- [x] 7.4 — `RecommendationDeleteView(AuditRequiredMixin, View)` :
  - POST uniquement (HTMX), appelle `services.soft_delete_recommendation()`
  - Retourne `HX-Trigger: {"notify": {"msg": "...", "type": "success"}}`

### Task 8 : URLs (apps/workflow/urls.py + config/urls.py)

- [x] 8.1 — `apps/workflow/urls.py` :
  ```python
  app_name = "workflow"
  urlpatterns = [
      path("recommandations/", views.RecommendationListView.as_view(), name="recommendation-list"),
      path("recommandations/create/", views.RecommendationCreateView.as_view(), name="recommendation-create"),
      path("recommandations/<uuid:pk>/", views.RecommendationDetailView.as_view(), name="recommendation-detail"),
      path("recommandations/<uuid:pk>/delete/", views.RecommendationDeleteView.as_view(), name="recommendation-delete"),
  ]
  ```

- [x] 8.2 — `config/urls.py` : Ajouter `path("audit/", include("apps.workflow.urls"))`.

### Task 9 : Templates (Tailwind + Alpine + HTMX)

- [x] 9.1 — `templates/workflow/recommendation_list.html` :
  - Extends `layouts/app_shell.html`
  - Filtres horizontaux compacts (HTMX)
  - Bouton "+ Nouvelle recommandation"
  - Tableau avec colonnes : Réf, Mission (tronqué), Source, Échéance (rouge si overdue), Statut (badge), ⋯
  - Ligne cliquable vers détail (lien absolu positionné, menu ⋯ en `z-index` supérieur)
  - Empty state soigné si 0 résultat

- [x] 9.2 — `templates/workflow/partials/stepper_slideover.html` :
  - Tiroir latéral droit, 55% largeur, 100vh hauteur
  - Alpine.js : `x-data="{ step: 1 }"`, navigation entre étapes
  - Formulaire aéré (`gap-6`, `bg-gray-50`, couleurs douces)
  - Étape 4 : FormSet livrables + bouton "+ Ajouter un livrable" (Alpine.js clone)
  - Bouton final : `hx-post` soumission totale

- [x] 9.3 — `templates/workflow/recommendation_detail.html` :
  - Fil d'ariane, barre d'actions sticky
  - Split 60/40 : gauche (métadonnées, textes) / droite (avancement, livrables checklist, timeline)
  - Bouton "Assigner" grisé (Story 2.5)

- [x] 9.4 — `templates/workflow/partials/recommendation_row.html` : Ligne HTMX swappable.
- [x] 9.5 — `templates/workflow/partials/recommendation_filters.html` : Filtres HTMX.
- [x] 9.6 — `templates/workflow/partials/delete_confirm.html` : Micro-modale confirmation.

### Task 10 : Tests

- [x] 10.1 — `apps/workflow/tests/test_models.py` :
  - Champs et valeurs par défaut
  - Custom Manager (soft-deleted exclues de `objects`, présentes dans `all_objects`)
  - `progress_percentage` (0/0=0%, 2/4=50%, 3/3=100%)
  - Validation `clean()` (date passée, reference unique)

- [x] 10.2 — `apps/workflow/tests/test_services.py` :
  - `create_recommendation()` → reco + livrables créés + AuditLog
  - `soft_delete_recommendation()` sur DRAFT → `is_deleted=True`
  - `soft_delete_recommendation()` sur ASSIGNED → `ValueError`
  - `update_recommendation()` → delta AuditLog
  - `@transaction.atomic` fonctionne (rollback si erreur)

- [x] 10.3 — `apps/workflow/tests/test_views.py` :
  - 200 pour AUDIT sur `/audit/recommandations/`
  - 403 pour DM/ETP/ADMIN sur `/audit/recommandations/`
  - POST création valide → reco + livrables en base
  - POST soft-delete via HTMX
  - Empty state rendering

- [x] 10.4 — `apps/workflow/tests/test_forms.py` :
  - Champs requis validés
  - `clean_due_date()` rejette dates passées
  - DeliverableFormSet accepte 0..N livrables

### Task 11 : Migration

- [x] 11.1 — Vérifier qu'aucune migration stale n'existe : `apps/workflow/migrations/` doit contenir uniquement `__init__.py`.
- [x] 11.2 — `python manage.py makemigrations workflow` → génère `0001_initial.py` propre.
- [x] 11.3 — `docker compose exec web python manage.py migrate`
- [x] 11.4 — `docker compose exec web python manage.py test apps.workflow -v2`

## Dev Notes

### Architecture & Contraintes

- **FSM (ADR-07)** : `django-fsm` obligatoire. `FSMField` posé avec 6 états. Pas de `@transition` dans cette story (Stories 2.5+).
- **HackSoft** : Mutations dans `services.py`, lectures dans `selectors.py`, zéro logique métier dans les vues.
- **`@transaction.atomic`** : Obligatoire sur chaque service de mutation.
- **`select_for_update()`** : Pour la concurrence FSM (ADR-07 §5.4).
- **Soft Delete** : Custom Manager par défaut. Ne PAS surcharger `Model.delete()`.

### Learnings Epic 1

- **Styling Tailwind** : Réutiliser `_INPUT_CLASS` de `apps/users/forms.py`.
- **Notifications HTMX** : Pattern `HX-Trigger: {"notify": {"msg": "...", "type": "success"}}` + Alpine `$store.sentinel.notify()`.
- **Layout** : `layouts/app_shell.html` + `context_processors.sidebar_context` → `partials/sidebar_audit.html` injecté automatiquement pour le rôle AUDIT.
- **Context** : Passer `active_route`, `topbar_title`, `topbar_subtitle`.

### Fichiers à créer/modifier

| Action | Fichier | Description |
|---|---|---|
| ✏️ | `apps/workflow/models.py` | Modèles `Recommendation` + `Deliverable` |
| ✏️ | `apps/users/mixins.py` | Ajouter `AuditRequiredMixin` |
| ✏️ | `config/urls.py` | Ajouter `path("audit/", include(...))` |
| 🆕 | `apps/workflow/urls.py` | 4 routes |
| 🆕 | `apps/workflow/forms.py` | `RecommendationForm` + `DeliverableFormSet` |
| 🆕 | `apps/workflow/views.py` | 4 vues |
| 🆕 | `apps/workflow/services.py` | 3 services |
| 🆕 | `apps/workflow/selectors.py` | 3 selectors |
| 🆕 | `templates/workflow/recommendation_list.html` | Page liste |
| 🆕 | `templates/workflow/recommendation_detail.html` | Centre de Contrôle |
| 🆕 | `templates/workflow/partials/stepper_slideover.html` | Stepper 4 étapes |
| 🆕 | `templates/workflow/partials/recommendation_row.html` | Ligne HTMX |
| 🆕 | `templates/workflow/partials/recommendation_filters.html` | Filtres HTMX |
| 🆕 | `templates/workflow/partials/delete_confirm.html` | Modale confirmation |
| 🆕 | `apps/workflow/tests/test_models.py` | Tests modèle + progress |
| 🆕 | `apps/workflow/tests/test_services.py` | Tests services |
| 🆕 | `apps/workflow/tests/test_views.py` | Tests vues + RBAC |
| 🆕 | `apps/workflow/tests/test_forms.py` | Tests forms + formset |

### References

| Source | Sections |
|---|---|
| **PRD v2** | FR5, FR6, FR6b, FR9 |
| **Architecture v2 §5.1** | FSM — 6 états |
| **Architecture v2 §7.2** | ERD — tables `workflow_recommendation` + `workflow_deliverable` |
| **Architecture v2 §8** | Classes |
| **ADR-07** | `django-fsm`, `select_for_update()` |
| **ADR-08** | Tailwind CSS |
| **Épic 1 code** | Patterns `services.py`, `selectors.py`, `mixins.py`, `forms.py` |
| **sidebar_audit.html** | Navigation `/audit/recommandations/` pré-configurée |
