# Story 3.7.b : Paramétrage métier (Sources des recommandations & Types d'unité organisationnelle)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Audit Admin (Direction de l'Audit Interne, flag `is_audit_admin=True`)**,
I want **paramétrer dynamiquement les sources des recommandations et les types d'unité organisationnelle depuis l'UI**,
so that **Sentinel s'adapte aux évolutions internes de BICEC (nouvelles autorités, restructurations) ET reste utilisable par d'autres structures sans modification de code** (agnosticisme produit).

**Contexte produit** — Aujourd'hui deux référentiels métier sont codés en dur en Python :
- `Recommendation.Source` : 7 valeurs (`INTERNE`, `COBAC`, `CAC`, `ANIF`, `BEAC`, `ANTIC`, `CONSULTANT`) spécifiques au secteur bancaire camerounais
- `Department.Type` : 7 valeurs (`DG`, `DIRECTION`, `SOUS_DIRECTION`, `DEPARTEMENT`, `SERVICE`, `REGION`, `AGENCE`) spécifiques à la structure BICEC

Ces deux énumérations doivent devenir des **tables paramétrables** gérées par l'Audit Admin via l'UI. Aucune logique métier critique du workflow ne dépend de ces valeurs (le RBAC repose sur la hiérarchie parent-enfant `Department`, pas sur le type ; le workflow FSM est indépendant de la source).

## Acceptance Criteria

### Phase A — Sources des recommandations

1. **AC1 — Modèle `RecommendationSource` paramétrable**
   - **Given** le code Sentinel à l'état pré-3.7.b (385 tests verts, `Recommendation.source` = `CharField(choices=Source.choices)`)
   - **When** on applique les migrations workflow 0010 → 0012
   - **Then** la table `workflow_recommendation_source` existe avec 7 enregistrements pré-remplis : `INTERNE` (is_external=False) + `COBAC/CAC/ANIF/BEAC/ANTIC/CONSULTANT` (is_external=True)
   - **And** `Recommendation.source` est désormais un `ForeignKey(RecommendationSource, on_delete=PROTECT, related_name="recommendations")`
   - **And** toutes les recommandations existantes ont leur FK correctement remplie (aucune source NULL)

2. **AC2 — Accès UI CRUD restreint à l'Audit Admin (RBAC)**
   - **Given** un utilisateur `user.role == AUDIT` avec `is_audit_admin=True`
   - **When** il accède à `/audit/sources-admin/`
   - **Then** il voit la liste des sources (actives + inactives) avec actions Créer / Éditer / Toggle is_active
   - **Given** tout autre rôle (`AUDIT` sans flag, `DM`, `ETP`, `DG`, `ADMIN_IT`, `EXT`) ou anonyme
   - **When** il tente d'accéder à ce même endpoint (GET ou POST)
   - **Then** HTTP 403 (ou 302 vers login si anonyme)

3. **AC3 — Désactivation : filtrage du select de création recommandation**
   - **Given** une source active (ex: `ANTIC`) utilisée par 5 recommandations historiques
   - **When** Audit Admin la désactive via le toggle
   - **Then** `is_active=False` est persisté en base
   - **And** `ANTIC` n'apparaît plus dans le `<select>` source du formulaire `RecommendationCreateView`
   - **And** les 5 recommandations historiques continuent d'afficher `ANTIC` dans la liste / détail

4. **AC4 — Rename : impact global, pas de snapshot historique**
   - **Given** une source `code="COBAC", label="COBAC"` utilisée par 10 recommandations
   - **When** Audit Admin modifie le label en `"COBAC Cameroun"` et sauvegarde
   - **Then** toutes les 10 recommandations historiques affichent désormais `"COBAC Cameroun"` dans la colonne source
   - **And** aucun snapshot de l'ancien label n'est conservé (décision verrouillée : pas de versioning)

5. **AC5 — Code immuable après création**
   - **Given** une source existante (`code="MINFI"`)
   - **When** Audit Admin ouvre la modale d'édition
   - **Then** le champ `code` est rendu en lecture seule (`disabled` HTML)
   - **And** seuls `label` et `is_external` sont éditables
   - **And** une tentative de modification du `code` via POST direct (manipulation URL) est ignorée (champ ignoré côté formulaire)

6. **AC6 — Pas de suppression dure : toggle uniquement**
   - **Given** une source utilisée par 0 recommandation
   - **When** on inspecte les URLs `/audit/sources-admin/...`
   - **Then** aucun endpoint `DELETE` n'existe
   - **And** la seule façon de retirer une source du formulaire est `is_active=False` (préserve l'historique)

7. **AC7 — AuditLog sur toute mutation source**
   - **Given** Audit Admin crée, modifie ou toggle une source
   - **When** la transaction est committée
   - **Then** un `AuditLog` est créé avec :
     - `action` = `CREATE` (création) ou `UPDATE` (modification ou toggle)
     - `content_type` = `"RecommendationSource"` (string littéral, pas FK ContentType)
     - `object_id` = `source.pk` (UUID)
     - `changes` = dict JSON-safe : ex `{"label": ["COBAC", "COBAC Cameroun"]}` ou `{"is_active": [True, False]}` (jamais d'instance modèle dans le JSON)
     - `user` = `performed_by` (Audit Admin)
     - `description` mentionne le code et le label de la source

### Phase B — Types d'unité organisationnelle

8. **AC8 — Modèle `OrgUnitType` paramétrable + Department.type = FK**
   - **Given** le code Sentinel à l'état post-Phase A
   - **When** on applique les migrations users 0005 → 0007
   - **Then** la table `users_org_unit_type` existe avec 7 enregistrements pré-remplis :
     - `DG` (level=1), `DIRECTION` (level=2), `SOUS_DIRECTION` (level=3), `REGION` (level=3), `DEPARTEMENT` (level=4), `AGENCE` (level=4), `SERVICE` (level=5)
   - **And** `Department.type` est désormais un `ForeignKey(OrgUnitType, on_delete=PROTECT, related_name="departments")`
   - **And** tous les `Department` existants ont leur FK correctement remplie

9. **AC9 — Garde-fou anti-cycle uniquement (`level` = hint advisory)**
   - **Given** un `Department A` et un `Department B` avec `A.parent = B`
   - **When** on tente de modifier `B.parent = A` (cycle direct)
   - **Then** `Department.clean()` lève `ValidationError({"parent": "Cycle détecté : un département ne peut pas être son propre ancêtre."})`
   - **Given** types `REGION (level=3)` et `AGENCE (level=4)`
   - **When** on crée `Department(type=REGION, parent=<Department AGENCE>)` (level 3 sous level 4 — incohérent mais possible)
   - **Then** la création réussit : `level` est un **hint de tri/suggestion UI**, pas une contrainte dure
   - **Given** un type racine (parent=NULL)
   - **When** on crée n'importe quel Department sans parent
   - **Then** la validation anti-cycle est skippée (pas de parent = pas de cycle possible)
   - **Note** : le `level` reste utile pour ordonner les types dans les selects et suggérer les types pertinents, mais il ne **bloque jamais** la création/édition. L'Audit Admin est responsable de la cohérence de son arbre.

10. **AC10 — UI CRUD OrgUnitType (Audit Admin)**
    - **Given** `user.is_audit_admin=True`
    - **When** il accède à `/auth/orgtypes-admin/`
    - **Then** il voit la liste avec colonnes `code | name | level | is_active | actions`
    - **And** il peut créer (modale HTMX), éditer (modale), toggle is_active
    - **And** le code est immuable après création (idem AC5)
    - **Given** tout autre rôle → HTTP 403

11. **AC11 — Refactor UI organigramme : `admin_it` → `audit-admin`**
    - **Given** Audit Admin se connecte
    - **When** il consulte sa sidebar
    - **Then** il voit une section "Configuration" contenant : "Sources" + "Types d'unité" + "Organigramme"
    - **And** les liens pointent vers `/audit/sources-admin/`, `/auth/orgtypes-admin/`, `/auth/admin/organigramme/`
    - **Given** ADMIN_IT (sans is_audit_admin) se connecte
    - **When** il consulte sa sidebar
    - **Then** la section "Organigramme" a disparu (déplacée chez Audit Admin)
    - **And** l'URL `/auth/admin/organigramme/` est conservée mais désormais protégée par `AuditAdminRequiredMixin` au lieu de `AdminRequiredMixin` → un ADMIN_IT pur (sans `is_audit_admin=True`) reçoit 403. Pas de redirection mise en place (Sentinel est pré-prod, aucune compatibilité requise pour les bookmarks).
    - **Note URL** : le préfixe réel dans `config/urls.py` est `/auth/admin/...` (pas `/admin-it/`). Les templates vivent dans `admin_it/` mais les URLs sont sous `auth:`. Seule la sémantique métier (RBAC) change, pas le chemin.

12. **AC12 — `DepartmentForm` utilise OrgUnitType actif uniquement**
    - **Given** `OrgUnitType` en base : `DG (active)`, `DIRECTION (active)`, `POLE (inactive)`
    - **When** Audit Admin ouvre le formulaire de création / édition de Department
    - **Then** le `<select name="type">` propose uniquement DG et DIRECTION (pas POLE)
    - **And** la création d'un Department avec `type=POLE` via POST direct (manipulation) échoue à la validation form

13. **AC13 — AuditLog sur mutations OrgUnitType (idem AC7 pour sources)**
    - Action=CREATE|UPDATE, content_type="OrgUnitType", changes JSON-safe (jamais d'instance)

### Phase C — Cohérence + non-régression

14. **AC14 — Tests existants `Recommendation.Source.X` et `Department.Type.X` adaptés**
    - **Given** la suite Docker pré-3.7.b (385 tests verts) avec usages directs `source=Recommendation.Source.INTERNE` et `type=Department.Type.DG`
    - **When** on bascule en FK (Phase A + Phase B appliquées)
    - **Then** les ~15 tests sources sont adaptés (`source=RecommendationSource.objects.get(code="INTERNE")` pour appels de service, ou `str(...).pk` pour `client.post`)
    - **And** les ~35 tests types sont adaptés (`type=OrgUnitType.objects.get(code="DG")`)
    - **And** la suite Docker complète passe : **cible ~415 verts** (385 existants + ~30 nouveaux Phase A/B/C)

15. **AC15 — Aucune régression sur Stories 3.7 et 3.8 préservées**
    - **Given** Story 3.7 (Soumission Exclusive DG) et Story 3.8 (DG dashboard restriction + todo) sont fonctionnelles avant 3.7.b
    - **When** Phase A + Phase B appliquées
    - **Then** les tests `DGDirectSubmitViewTest`, `DGTodoListViewTest`, `DGGlobalListRestrictionTest`, `PostLoginRedirectTest` restent verts

## Tasks / Subtasks

### Phase A — Sources des recommandations (~6-8h)

- [ ] **Task 1** : Modèle `RecommendationSource` (AC1, AC5, AC6, AC7)
  - [ ] Subtask 1.1 : Ajouter classe `RecommendationSource` dans `code/apps/workflow/models.py` AVANT `class Recommendation`
    - Champs : `id` (UUIDField pk, default=uuid.uuid4), `code` (CharField unique, max_length=30), `label` (CharField, max_length=120), `is_external` (BooleanField default=True), `is_active` (BooleanField default=True), `created_at` (auto_now_add), `created_by` (FK User SET_NULL nullable)
    - `Meta` : verbose_name "Source de recommandation", `db_table = "workflow_recommendation_source"`, ordering `["is_external", "label"]`
    - `__str__` : retourne `self.label`
  - [ ] Subtask 1.2 : Conserver l'enum `Recommendation.Source` temporairement (réutilisé par la migration 0011) — sera supprimé en migration 0012

- [ ] **Task 2** : Migration de schéma 0010 (AC1)
  - [ ] Créer `code/apps/workflow/migrations/0010_create_recommendation_source.py`
    - `CreateModel(RecommendationSource, ...)`
    - `AddField(Recommendation, "source_new", ForeignKey(RecommendationSource, null=True, blank=True, on_delete=PROTECT, related_name="recommendations"))` — champ temporaire nullable

- [ ] **Task 3** : Data migration 0011 — seed + bascule (AC1)
  - [ ] Créer `code/apps/workflow/migrations/0011_seed_sources_and_populate_fk.py`
  - [ ] **Pattern obligatoire** : utiliser `apps.get_model()` pour accéder aux modèles historiques (couplage avec le modèle vivant interdit dans les data migrations) :
    ```python
    from django.db import migrations

    DEFAULT_SOURCES = [
        # (code, label, is_external)
        ("INTERNE",    "Audit Interne", False),
        ("COBAC",      "COBAC",         True),
        ("CAC",        "CAC",           True),
        ("ANIF",       "ANIF",          True),
        ("BEAC",       "BEAC",          True),
        ("ANTIC",      "ANTIC",         True),
        ("CONSULTANT", "Consultant",    True),
    ]

    def seed_and_populate(apps, schema_editor):
        Source = apps.get_model('workflow', 'RecommendationSource')
        Recommendation = apps.get_model('workflow', 'Recommendation')

        for code, label, is_external in DEFAULT_SOURCES:
            Source.objects.get_or_create(
                code=code,
                defaults={"label": label, "is_external": is_external, "is_active": True},
            )

        for rec in Recommendation.objects.all():
            rec.source_new = Source.objects.get(code=rec.source)
            rec.save(update_fields=["source_new"])

    def reverse(apps, schema_editor):
        Source = apps.get_model('workflow', 'RecommendationSource')
        Recommendation = apps.get_model('workflow', 'Recommendation')
        Recommendation.objects.update(source_new=None)
        Source.objects.filter(code__in=[c for c, _, _ in DEFAULT_SOURCES]).delete()

    class Migration(migrations.Migration):
        dependencies = [("workflow", "0010_create_recommendation_source")]
        operations = [migrations.RunPython(seed_and_populate, reverse_code=reverse)]
    ```

- [ ] **Task 4** : Migration de finalisation 0012 (AC1)
  - [ ] Créer `code/apps/workflow/migrations/0012_finalize_source_fk.py`
    - `RemoveField(Recommendation, "source")` — retire l'ancien CharField
    - `RenameField(Recommendation, "source_new", "source")` — bascule le FK
    - `AlterField(Recommendation, "source", ForeignKey(RecommendationSource, on_delete=PROTECT, related_name="recommendations"))` — non-null

- [ ] **Task 5** : Bascule du modèle Python (AC1)
  - [ ] Dans `code/apps/workflow/models.py` :
    - Retirer la classe `Recommendation.Source` (l'enum)
    - Remplacer le champ `source = CharField(choices=Source.choices, ...)` par `source = ForeignKey(RecommendationSource, on_delete=PROTECT, related_name="recommendations")`

- [ ] **Task 6** : Services CRUD sources (AC7)
  - [ ] Ajouter dans `code/apps/workflow/services.py` (à la fin du fichier) :
    - `create_recommendation_source(*, code, label, is_external, performed_by, ip_address=None) -> RecommendationSource` : crée la source + AuditLog `CREATE`
    - `update_recommendation_source(*, source, label, is_external, performed_by, ip_address=None) -> RecommendationSource` : **recharge `fresh = RecommendationSource.objects.select_for_update().get(pk=source.pk)` AVANT comparaison** (piège ModelForm `_post_clean` — voir Dev Notes), calcule delta, save + AuditLog `UPDATE`
    - `toggle_recommendation_source(*, source, performed_by, ip_address=None) -> RecommendationSource` : bascule `is_active` + AuditLog `UPDATE`

- [ ] **Task 7** : Sélecteurs sources (AC3)
  - [ ] Ajouter dans `code/apps/workflow/selectors.py` (avant `get_recommendations_for_user`) :
    - `get_active_sources() -> QuerySet[RecommendationSource]` : `filter(is_active=True).order_by("is_external", "label")`
    - `get_all_sources() -> QuerySet[RecommendationSource]` : `all().order_by("is_external", "label")`
    - `get_source_by_code(code: str) -> RecommendationSource | None` : utilitaire pour les **tests et les services** uniquement. **Pas pour les data migrations** : celles-ci utilisent `apps.get_model('workflow', 'RecommendationSource').objects.get(code=...)` directement (couplage avec le modèle vivant interdit)
  - [ ] Adapter le filtre source dans `get_recommendations_for_user` : coupe nette, UUID uniquement (Sentinel est pré-prod, aucun bookmark `?source=COBAC` à préserver) :
    ```python
    if source:
        qs = qs.filter(source_id=source)
    ```
  - [ ] Ajouter `"source"` au `select_related()` dans **les 3 sélecteurs** pour éviter N+1 queries :
    - `get_recommendations_for_user` (ligne ~37) — sélecteur liste
    - `get_recommendation_by_id` (lignes ~113-116) — sélecteur accès unitaire
    - `get_recommendation_detail_for_user` (lignes ~140-143) — sélecteur détail
    ```python
    .select_related(
        "created_by", "department", "controlled_department", "assigned_dm", "assigned_etp", "source"
    )
    ```

- [ ] **Task 8** : Adapter `RecommendationForm` (AC3)
  - [ ] Dans `code/apps/workflow/forms.py` :
    - Importer `RecommendationSource`
    - Dans `__init__` : `source_field.queryset = RecommendationSource.objects.filter(is_active=True)` (ModelChoiceField auto-généré depuis FK)
    - Définir `source_field.empty_label = "— Sélectionner une source —"`
    - **Supprimer les lignes ~151-155** (ancien bloc `ChoiceField` incompatible avec `ModelChoiceField`) :
      ```python
      # À SUPPRIMER — ces lignes crasheront avec ModelChoiceField :
      source_field = cast(forms.ChoiceField, self.fields["source"])
      source_choices = list(source_field.choices)
      if source_choices and source_choices[0][0] in ('', None):
          source_choices[0] = ('', _("— Sélectionner une source —"))
      source_field.choices = source_choices
      ```

- [ ] **Task 9** : Adapter `RecommendationListView` (AC3)
  - [ ] Dans `code/apps/workflow/views.py`, `get_context_data` :
    - Remplacer `context["sources"] = Recommendation.Source.choices` par `context["sources"] = selectors.get_active_sources()`

- [ ] **Task 10** : Adapter le template liste recommandations (AC3)
  - [ ] Dans `code/templates/workflow/recommendation_list.html` :
    - Remplacer `{% for value, label in sources %}<option value="{{ value }}" ...>{{ label }}</option>{% endfor %}`
    - Par `{% for src in sources %}<option value="{{ src.pk }}" {% if src.pk|stringformat:'s' == current_source %}selected{% endif %}>{{ src.label }}</option>{% endfor %}`

- [ ] **Task 10b** : Fix `get_source_display` → `.source.label` dans les templates détail/table (bug silencieux)
  - [ ] **Contexte** : quand `source` passe de CharField à ForeignKey, la méthode auto-générée `get_source_display()` **disparaît**. Django template engine avale silencieusement l'AttributeError → affichage **vide** (pas d'erreur Python, pas de crash, juste une colonne vide en prod)
  - [ ] `code/templates/workflow/recommendation_detail.html:229` : remplacer `{{ recommendation.get_source_display }}` par `{{ recommendation.source.label }}`
  - [ ] `code/templates/workflow/partials/recommendation_table.html:30` : remplacer `{{ rec.get_source_display }}` par `{{ rec.source.label }}`

- [ ] **Task 11** : URLs + Vues CRUD sources (AC2)
  - [ ] Dans `code/apps/workflow/urls.py`, ajouter sous-section "Administration Sources (Audit Admin)" :
    - `path("sources-admin/", views.RecommendationSourceListView.as_view(), name="source-list")`
    - `path("sources-admin/create/", views.RecommendationSourceCreateView.as_view(), name="source-create")`
    - `path("sources-admin/<uuid:pk>/edit/", views.RecommendationSourceEditView.as_view(), name="source-edit")`
    - `path("sources-admin/<uuid:pk>/toggle/", views.RecommendationSourceToggleView.as_view(), name="source-toggle")`
  - [ ] Dans `code/apps/workflow/views.py`, ajouter 4 vues (héritant `AuditAdminRequiredMixin` de `apps.users.mixins`) :
    - `RecommendationSourceListView` (ListView) : queryset = `selectors.get_all_sources()`, template `workflow/admin/sources/list.html`
    - `RecommendationSourceCreateView` (View) : GET retourne `_form_modal.html` (form vide), POST crée via `services.create_recommendation_source` (204 + HX-Refresh) ou 422 + form re-rendu
    - `RecommendationSourceEditView` : GET form pré-rempli (instance), POST `services.update_recommendation_source` (204 + HX-Refresh ou 422)
    - `RecommendationSourceToggleView` : POST uniquement, appelle `services.toggle_recommendation_source` (204 + HX-Refresh)

- [ ] **Task 12** : Form `RecommendationSourceForm` (AC5)
  - [ ] Créer **nouveau fichier `code/apps/workflow/admin_forms.py`** (recommandé — le `forms.py` existant fait déjà ~544 lignes et contient uniquement les formulaires workflow ; les formulaires admin config sont sémantiquement différents) :
    - `class RecommendationSourceForm(ModelForm)` avec fields `["code", "label", "is_external"]`
    - **Pattern critique** (voir Dev Notes) : `__init__` utilise `if not self.instance._state.adding: self.fields["code"].disabled = True` (PAS `self.instance.pk` qui est toujours non-None à cause de `UUIDField(default=uuid.uuid4)`)
    - `clean_code` : normalise upper + check non vide. NE PAS dupliquer le check d'unicité (Django `_post_clean` le fait automatiquement)
    - `clean_label` : strip + check non vide

- [ ] **Task 13** : Templates sources (AC2)
  - [ ] Créer `code/templates/workflow/admin/sources/list.html` : étend `app_shell.html`, affiche tableau avec colonnes Code / Label / Type (interne/externe via badge) / Statut (toggle is_active) / Actions (éditer)
  - [ ] Créer `code/templates/workflow/admin/sources/_form_modal.html` : modale HTMX avec form code/label/is_external, bouton "Enregistrer" (POST hx-post), pattern identique à `admin_it/user_create.html`

- [ ] **Task 14** : Sidebar Audit Admin — section Configuration > Sources (AC11)
  - [ ] Dans `code/templates/partials/sidebar_audit.html`, ajouter sous condition `{% if user.is_audit_admin %}` une section "Configuration" avec lien vers `{% url 'workflow:source-list' %}` (Sources)
  - [ ] Note : la section sera complétée Phase B avec "Types d'unité" et "Organigramme"

- [ ] **Task 15** : Adapter les ~15 tests utilisant `Recommendation.Source.X` (AC14)
  - [ ] Pour chaque fichier listé ci-dessous, remplacer `source=Recommendation.Source.INTERNE` :
    - Si l'usage est dans un dict passé au service `create_recommendation` ou à `Model.objects.create(...)` → remplacer par `source=RecommendationSource.objects.get(code="INTERNE")` (instance)
    - Si l'usage est dans `client.post({...})` (HTTP) → remplacer par `source=str(RecommendationSource.objects.get(code="INTERNE").pk)` (UUID string)
  - [ ] Fichiers concernés (16 occurrences vérifiées par grep) :
    - `code/apps/workflow/tests/test_models.py` (×2 : 1 fixture + 1 assertion `test_source_choices` → `assertEqual(RecommendationSource.objects.count(), 7)`)
    - `code/apps/workflow/tests/test_forms.py` (×1 : pk string pour `client.post`)
    - `code/apps/workflow/tests/test_services.py` (×1 : instance pour service)
    - `code/apps/workflow/tests/test_delegation.py` (×4 : instances)
    - `code/apps/workflow/tests/test_views.py` (×8 : mix instance/pk string selon contexte ; voir piège AC7 du fichier — POST = pk string)
    - ~~`code/apps/dashboards/tests/test_views.py`~~ — **faux positif retiré** : grep confirme 0 occurrence de `Recommendation.Source` dans ce fichier

- [ ] **Task 16** : Fix régression `create_recommendation` AuditLog (AC7 sur création reco standard)
  - [ ] Dans `code/apps/workflow/services.py:83`, remplacer `"source": recommendation.source,` par :
    ```python
    "source": recommendation.source.code if recommendation.source_id else None,
    ```
  - [ ] Note : sans ce fix, **171 erreurs `TypeError: Object of type RecommendationSource is not JSON serializable`** apparaissent dans la suite (voir piège Dev Notes)

- [ ] **Task 17** : Validation intermédiaire Phase A
  - [ ] Lancer `docker compose run --rm web python manage.py test --verbosity=1`
  - [ ] Cible : **~395 verts** (385 existants + 8-10 nouveaux Phase A)
  - [ ] Si rouge → fixer avant de passer Phase B

### Phase B — Types d'unité organisationnelle (~10-12h)

- [ ] **Task 18** : Modèle `OrgUnitType` (AC8)
  - [ ] Ajouter dans `code/apps/users/models.py` AVANT `class Department` :
    - Champs : `id` UUIDField, `code` (unique max 30), `name` (max 80), `level` (PositiveIntegerField default=1), `is_active` (default=True), `created_at`, `created_by` (FK User SET_NULL nullable)
    - **Pas de champ `icon`** (YAGNI — aucun usage UI décrit, ajout trivial plus tard si besoin)
    - `Meta` : `db_table = "users_org_unit_type"`, ordering `["level", "name"]`, indexes sur `level` et `is_active`

- [ ] **Task 19** : Migration schéma users 0005 (AC8)
  - [ ] Créer `code/apps/users/migrations/0005_create_org_unit_type.py` :
    - `CreateModel(OrgUnitType, ...)`
    - `AddField(Department, "type_new", ForeignKey(OrgUnitType, null=True, blank=True, on_delete=PROTECT, related_name="departments"))`

- [ ] **Task 20** : Data migration users 0006 — seed + bascule (AC8)
  - [ ] Créer `code/apps/users/migrations/0006_seed_org_unit_types_and_populate_fk.py`
  - [ ] **Pattern obligatoire** : `apps.get_model()` pour les modèles historiques (idem Task 3) :
    ```python
    from django.db import migrations

    DEFAULT_TYPES = [
        # (code, name, level)
        ("DG",             "Direction Générale",  1),
        ("DIRECTION",      "Direction",            2),
        ("SOUS_DIRECTION", "Sous-Direction",       3),
        ("REGION",         "Direction Régionale",  3),
        ("DEPARTEMENT",    "Département",          4),
        ("AGENCE",         "Agence",               4),
        ("SERVICE",        "Service",              5),
    ]

    def seed_and_populate(apps, schema_editor):
        OrgUnitType = apps.get_model('users', 'OrgUnitType')
        Department = apps.get_model('users', 'Department')

        for code, name, level in DEFAULT_TYPES:
            OrgUnitType.objects.get_or_create(
                code=code,
                defaults={"name": name, "level": level, "is_active": True},
            )

        for dept in Department.objects.all():
            dept.type_new = OrgUnitType.objects.get(code=dept.type)
            dept.save(update_fields=["type_new"])

    def reverse(apps, schema_editor):
        OrgUnitType = apps.get_model('users', 'OrgUnitType')
        Department = apps.get_model('users', 'Department')
        Department.objects.update(type_new=None)
        OrgUnitType.objects.filter(code__in=[c for c, _, _ in DEFAULT_TYPES]).delete()

    class Migration(migrations.Migration):
        dependencies = [("users", "0005_create_org_unit_type")]
        operations = [migrations.RunPython(seed_and_populate, reverse_code=reverse)]
    ```

- [ ] **Task 21** : Migration finalisation users 0007 (AC8)
  - [ ] Créer `code/apps/users/migrations/0007_finalize_department_type_fk.py` :
    - `RemoveField(Department, "type")`
    - `RenameField(Department, "type_new", "type")`
    - `AlterField` non-null FK PROTECT

- [ ] **Task 22** : Bascule modèle Python `Department` + garde-fou anti-cycle (AC8, AC9)
  - [ ] Dans `code/apps/users/models.py` :
    - Retirer la classe `Department.Type`
    - Remplacer `type = CharField(choices=Type.choices, ...)` par `type = ForeignKey(OrgUnitType, on_delete=PROTECT, related_name="departments")`
    - Ajouter la méthode `clean()` — **anti-cycle uniquement**, pas de validation `level` stricte :
      ```python
      def clean(self):
          super().clean()
          if self.parent_id:
              # Garde-fou anti-cycle : un département ne peut pas être son propre ancêtre
              ancestor = self.parent
              visited = set()
              while ancestor is not None:
                  if ancestor.pk == self.pk:
                      raise ValidationError({
                          "parent": "Cycle détecté : un département ne peut pas être "
                                    "son propre ancêtre."
                      })
                  if ancestor.pk in visited:
                      break  # Cycle pré-existant (ne devrait pas arriver)
                  visited.add(ancestor.pk)
                  ancestor = ancestor.parent
      ```
    - **Note** : `level` reste un **hint de tri/suggestion UI** dans les selects, jamais une contrainte bloquante
    - Retirer l'index `Meta.indexes` sur `type` (devient `type_id` automatique via FK)

- [ ] **Task 23** : Services CRUD OrgUnitType (AC13)
  - [ ] Ajouter dans `code/apps/users/services.py` :
    - `create_org_unit_type(*, code, name, level, performed_by, ip_address=None)` + AuditLog `CREATE`
    - `update_org_unit_type(*, org_type, name, level, performed_by, ip_address=None)` : pattern `select_for_update().get(pk=...)` + delta + AuditLog. **Pas de validation hiérarchique** : `level` est advisory (AC9 révisé)
    - `toggle_org_unit_type(*, org_type, performed_by, ip_address=None)` : bascule is_active + AuditLog. Warning si des `Department` actifs utilisent ce type (loggé, pas bloquant)

- [ ] **Task 24** : Sélecteurs OrgUnitType (AC12)
  - [ ] Ajouter dans `code/apps/users/selectors.py` :
    - `get_active_org_unit_types()` : `filter(is_active=True).order_by("level", "name")`
    - `get_all_org_unit_types()` : `all().order_by("level", "name")`
    - **Pas de `get_allowed_child_types()`** : `level` est advisory, tous les types actifs sont proposés dans le select

- [ ] **Task 25** : URLs + Vues CRUD OrgUnitType (AC10)
  - [ ] Dans `code/apps/users/urls.py`, ajouter sous-section "Audit Admin — Types d'unité" :
    - `path("orgtypes-admin/", views.OrgUnitTypeListView.as_view(), name="orgtype-list")`
    - `path("orgtypes-admin/create/", views.OrgUnitTypeCreateView.as_view(), name="orgtype-create")`
    - `path("orgtypes-admin/<uuid:pk>/edit/", views.OrgUnitTypeEditView.as_view(), name="orgtype-edit")`
    - `path("orgtypes-admin/<uuid:pk>/toggle/", views.OrgUnitTypeToggleView.as_view(), name="orgtype-toggle")`
  - [ ] Dans `code/apps/users/views.py`, 4 vues avec `AuditAdminRequiredMixin` — patterns identiques aux vues sources Phase A

- [ ] **Task 26** : Form `OrgUnitTypeForm` (AC10)
  - [ ] Champs `["code", "name", "level"]` (is_active géré par toggle séparé, **pas d'`icon`** — YAGNI)
  - [ ] **Pattern critique** : `if not self.instance._state.adding: self.fields["code"].disabled = True`
  - [ ] `clean_code` : upper + non vide
  - [ ] `clean_level` : `value >= 1`

- [ ] **Task 27** : Templates OrgUnitType (AC10)
  - [ ] Créer `code/templates/users/admin/orgtypes/list.html` et `_form_modal.html` (patterns identiques aux sources Phase A)

- [ ] **Task 28** : Refactor UI organigramme — admin_it → audit_admin space (AC11)
  - [ ] Vues organigramme identifiées dans `code/apps/users/views.py` — **5 vues** à migrer (pas 4) :
    - `OrganigrammeListView` (L280)
    - `DepartmentCreateView` (L320)
    - `DepartmentEditView` (L365)
    - `DepartmentDeleteView` (L412)
    - **`DepartmentSearchView` (L450)** — ne pas oublier cette vue de recherche HTMX !
  - [ ] Changer leur mixin de `AdminRequiredMixin` → `AuditAdminRequiredMixin`. Garder les URLs `admin/organigramme/*` mais déplacer la sémantique métier vers Audit Admin. UI sidebar : retirer le lien de `sidebar_admin.html`, ajouter dans `sidebar_audit.html` sous "Configuration"
  - [ ] Coupe nette : pas de redirection 302 (Sentinel est pré-prod, aucune mémoire musculaire d'URL à préserver). L'ancienne URL retourne simplement 403 pour les non-Audit Admin.

- [ ] **Task 29** : Adapter `DepartmentForm` (AC12)
  - [ ] Dans `code/apps/users/forms.py` (ou équivalent) :
    - `type` devient `ModelChoiceField(queryset=selectors.get_active_org_unit_types())`
    - Tous les types actifs sont proposés (pas de filtrage par level — advisory seulement)

- [ ] **Task 29b** : Fix `get_type_display` + comparaisons `dept.type == 'DG'` dans les templates organigramme (bug silencieux)
  - [ ] **Contexte** : quand `type` passe de CharField à ForeignKey, `get_type_display()` **disparaît** et `dept.type == 'DG'` compare une instance `OrgUnitType` avec un string → toujours `False` → les couleurs CSS de l'arbre disparaissent silencieusement
  - [ ] `code/templates/admin_it/partials/organigramme_drilldown.html:25-31` : remplacer `{% if dept.type == 'DG' %}` par `{% if dept.type.code == 'DG' %}` etc.
    > [!WARNING]
    > **Bug existant pré-3.7.b** : la ligne 27 compare `dept.type == 'S_DIRECTION'` mais l'enum réel utilise `'SOUS_DIRECTION'`. Cette branche CSS **n'a jamais matché**. Corriger vers `dept.type.code == 'SOUS_DIRECTION'` (pas `'S_DIRECTION'`) :
    > ```diff
    > -{% elif dept.type == 'S_DIRECTION' %}bg-indigo-100 text-indigo-700
    > +{% elif dept.type.code == 'SOUS_DIRECTION' %}bg-indigo-100 text-indigo-700
    > ```
  - [ ] `code/templates/admin_it/partials/organigramme_drilldown.html:32` : remplacer `{{ dept.get_type_display }}` par `{{ dept.type.name }}`
  - [ ] `code/templates/admin_it/partials/organigramme_node.html:8` : remplacer `{{ node.get_type_display|truncatechars:3 }}` par `{{ node.type.name|truncatechars:3 }}`
  - [ ] `code/templates/admin_it/partials/organigramme_node.html:12` : remplacer `{{ node.get_type_display }}` par `{{ node.type.name }}`

- [ ] **Task 30** : Adapter les ~35 tests utilisant `Department.Type.X` (AC14)
  - [ ] Pattern : `type=Department.Type.DG` → `type=OrgUnitType.objects.get(code="DG")` dans les calls à `Department.objects.create(...)`
  - [ ] **Pas de risque AC9** : `level` est advisory, le `clean()` ne vérifie que les cycles → les tests qui créaient des hiérarchies arbitraires continuent de fonctionner sans adaptation
  - [ ] Fichiers principaux à inspecter :
    - `code/apps/users/tests/test_models.py` (~12 occurrences), `test_admin_it.py` (~20 occurrences), `test_habilitation.py` (~1 occurrence)
    - `code/apps/workflow/tests/*.py` (créations Department dans fixtures — `test_views.py` ×4, `test_delegation.py` ×6, `test_forms.py` ×6, `test_services.py` ×2)
    - ~~`code/apps/dashboards/tests/test_views.py`~~ — **faux positif retiré** : grep confirme 0 occurrence de `Department.Type` dans ce fichier

- [ ] **Task 31** : Mettre à jour `sidebar_audit.html` complètement (AC11)
  - [ ] Section "Configuration" (visible si `user.is_audit_admin`) contient désormais 3 entrées :
    - Sources → `{% url 'workflow:source-list' %}`
    - Types d'unité → `{% url 'auth:orgtype-list' %}`
    - Organigramme → URL choisie en Task 28 (admin_it/organigramme/ ou auth/organigramme/)

- [ ] **Task 32** : Retirer "Organigramme" de la sidebar admin (AC11)
  - [ ] Dans `code/templates/partials/sidebar_admin.html` : retirer/masquer l'entrée "Organigramme" (devient redondante avec Audit Admin)

### Phase C — Tests dédiés + validation finale (~3-4h)

- [ ] **Task 33** : Tests dédiés Phase A — `code/apps/workflow/tests/test_recommendation_source.py`
  - [ ] `RecommendationSourceModelTest` : création, str, ordering, seed auto en data migration (vérifier les 7 sources existent après `setUpTestData`)
  - [ ] `RecommendationSourceServicesTest` : `create_recommendation_source` + AuditLog, `update_recommendation_source` (rename impact global, AuditLog UPDATE), `toggle_recommendation_source` (bascule + AuditLog)
  - [ ] `RecommendationSourceCRUDTest` : RBAC (Audit Admin only 200/204, AUDIT sans flag 403, DM/ETP/DG 403, anonyme redirect login), `test_create_returns_204_and_hx_refresh` (POST valide → 204 + HX-Refresh: true), `test_create_duplicate_code_returns_422`, `test_edit_label_persists`, `test_toggle_inverts_state`

- [ ] **Task 34** : Tests dédiés Phase B — `code/apps/users/tests/test_org_unit_type.py`
  - [ ] `OrgUnitTypeModelTest` : création, seed auto (7 types existent)
  - [ ] `DepartmentAntiCycleTest` : `clean()` lève ValidationError si cycle détecté (AC9) — tester cycle direct (A→B→A), cycle indirect (A→B→C→A), et auto-référence (A→A)
  - [ ] `OrgUnitTypeServicesTest` : CRUD + AuditLog
  - [ ] `OrgUnitTypeCRUDTest` : RBAC + 204/422

- [ ] **Task 35** : Suite Docker complète
  - [ ] Lancer `docker compose run --rm web python manage.py test --verbosity=1`
  - [ ] **Cible : ~415/415 verts** (385 baseline + ~30 nouveaux Phase A/B/C)
  - [ ] Si fail : fixer les régressions selon les patterns Dev Notes

## Ordre d'exécution recommandé

⚠️ **Les tâches sont numérotées par cohérence logique de description, pas par ordre d'exécution.** Suivre la numérotation 1→17 (Phase A) puis 18→32 (Phase B) à la lettre **casse les imports en cours de route** : la bascule Python du modèle (Tasks 5 et 22, qui retirent l'enum et changent le champ en FK) doit venir **après** l'adaptation des tests, forms, selectors et templates qui référencent encore l'enum.

### Phase A — séquence safe

1. **Tasks 1.1 + 2 + 3** — ajouter la classe `RecommendationSource` au modèle Python + migration 0010 (FK nullable `source_new`) + migration 0011 (data migration : seed des 7 sources + populate `source_new`). À cette étape, les deux colonnes (`source` CharField + `source_new` FK) coexistent en base et dans l'ORM. **Ne pas encore retirer l'enum `Recommendation.Source`** (cf. Task 1.2).
2. **Tasks 6 → 14** — passage applicatif au FK : services CRUD sources, sélecteurs, form, vues, templates, sidebar. Le code applicatif lit/écrit déjà via le FK `source_new`. Le champ `source` (CharField historique) n'est plus écrit mais existe encore.
3. **Tasks 15 + 16** — adapter les ~15 tests existants au pattern instance vs `str(pk)` + fix piège 3 dans `create_recommendation` (`.code` au lieu d'instance dans `AuditLog.changes`). Lancer la suite pour confirmer ~395 verts.
4. **Tasks 4 + 5** — migration 0012 finale (drop `source` CharField, rename `source_new` → `source`, alter not-null) + bascule Python (retirer l'enum `Recommendation.Source`, remplacer le champ par FK direct). Cette étape supprime définitivement le double champ.
5. **Task 17** — relance Docker complète. Cible : ~395 verts confirmés.

### Phase B — séquence safe (même logique)

1. **Tasks 18 + 19 + 20** — modèle `OrgUnitType` + migration users 0005 (FK nullable `type_new`) + migration users 0006 (seed + populate).
2. **Tasks 23 → 29 + 29b + 31 + 32** — services, sélecteurs, vues CRUD, form, refactor UI organigramme, fix templates `get_type_display`, sidebar.
3. **Task 30** — adapter les ~35 tests `Department.Type.X`.
4. **Tasks 21 + 22** — migration users 0007 finale + bascule Python (retirer enum `Department.Type`, basculer FK, ajouter `clean()` anti-cycle).
5. **Tasks 33 + 34 + 35** — tests dédiés + suite Docker complète (~415 verts).

### Variante simplifiée acceptable

Regrouper les étapes 1→3 de chaque phase en un seul commit atomique (la bascule finale 4-5 reste séparée pour bien isoler le point de non-retour de la migration finale). Acceptable car les FK sont déjà fonctionnelles via `source_new` / `type_new` avant la finalisation.

---

## Dev Notes

### 🚨 Pièges techniques critiques (issus de la tentative précédente revertée)

Ces 4 pièges ont été identifiés lors d'une tentative d'implémentation précédente (385 → 398 tests rouges → revert complet). Ils DOIVENT être respectés dans cette nouvelle implémentation :

#### Piège 1 — `instance.pk` vs `instance._state.adding` avec UUIDField

**Problème** : `UUIDField(default=uuid.uuid4)` génère un UUID dès l'instanciation Python. Donc `RecommendationSource().pk` est **non-None** même pour une instance non-sauvegardée. Le pattern habituel `if self.instance.pk:` (pour distinguer create vs edit dans `ModelForm.__init__`) est **toujours True** et casse la création.

**Symptôme observé** : `{'code': ['Ce champ est obligatoire.']}` au POST valide → 422 au lieu de 204. Cause : `code.disabled=True` (forcé par "edit mode" faussement détecté) → field récupère `initial=""` au lieu du POST.

**Fix obligatoire** :
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if not self.instance._state.adding:  # ✅ pas self.instance.pk
        self.fields["code"].disabled = True
```

#### Piège 2 — `ModelForm._post_clean()` mute l'instance avant le service

**Problème** : Quand on fait `form = RecommendationSourceForm(POST, instance=source)` puis `form.is_valid()`, Django mute `source.label = "New Label"` PENDANT `_post_clean()`. Si le service compare ensuite `if source.label != new_label:`, les valeurs sont **déjà égales** → delta vide → `if delta: save()` ne s'exécute pas → rien n'est persisté.

**Symptôme observé** : test `test_edit_label_persists` → response 204 (succès apparent) mais `source.refresh_from_db().label == "Old Label"` (pas de save réel).

**Fix obligatoire** dans `update_recommendation_source` et `update_org_unit_type` :
```python
def update_recommendation_source(*, source, label, is_external, performed_by, ...):
    with transaction.atomic():
        # Recharger depuis DB pour capturer le vrai état pré-form
        fresh = RecommendationSource.objects.select_for_update().get(pk=source.pk)
        delta = {}
        if fresh.label != label.strip():
            delta["label"] = [fresh.label, label.strip()]
            fresh.label = label.strip()
        # ... etc, utiliser `fresh` partout, pas `source`
        if delta:
            fresh.save(update_fields=["label", "is_external"])
            AuditLog.objects.create(...)
    return fresh
```

#### Piège 3 — `AuditLog.changes` est un JSONField → jamais d'instance modèle

**Problème** : `changes = {"source": recommendation.source}` stocke une instance `RecommendationSource` dans un JSONField. PostgreSQL psycopg lève `TypeError: Object of type RecommendationSource is not JSON serializable`. **171 erreurs** observées dans la tentative précédente.

**Fix obligatoire** dans `create_recommendation` et tout service qui logue un FK :
```python
changes={
    "source": recommendation.source.code if recommendation.source_id else None,
    # ou str(recommendation.source.pk) selon le besoin
    ...
}
```

#### Piège 4 — Tests POST `client.post({"source": instance})` → form invalide

**Problème** : `self.client.post(url, {"source": RecommendationSource.objects.get(code="INTERNE")})`. Django sérialise l'instance via `__str__()` → la valeur envoyée en POST est le label, pas l'UUID. Le ModelChoiceField rejette → form `not_a_valid_choice` → 422.

**Fix** : distinguer le contexte d'usage dans les tests :
- **Appel direct au service** (ex: `create_recommendation(data={...})` qui fait `Recommendation(**data)`) : passer une instance OK
- **`client.post()` HTTP** : passer `str(instance.pk)` (UUID string)

### Décisions verrouillées (brainstorming utilisateur)

#### Sources

| Décision | Choix |
|---|---|
| Modèle | `RecommendationSource` dans `apps.workflow.models` |
| Champs | `code` (unique), `label`, `is_external` (bool), `is_active` (bool), `created_at`, `created_by` (FK User nullable) |
| FK | `Recommendation.source = ForeignKey(RecommendationSource, on_delete=PROTECT)` |
| Permissions | Audit Admin uniquement (`is_audit_admin=True`) — directeur + délégués |
| CRUD | Add + Edit (label/is_external) + Toggle. **Pas de delete dure** |
| Rename | Impact global (pas de snapshot) |
| Distinction interne/externe | Simple flag bool, pas de règle métier |
| Seed | 7 sources auto via data migration |

#### Types d'unité

| Décision | Choix |
|---|---|
| Modèle | `OrgUnitType` dans `apps.users.models` |
| Champs | `code` (unique), `name`, `level` (PositiveInt, **1=sommet**, advisory), `is_active`, `created_at`, `created_by`. **Pas d'`icon`** (YAGNI) |
| FK | `Department.type = ForeignKey(OrgUnitType, on_delete=PROTECT)` |
| Permissions | Audit Admin |
| CRUD | Add + Edit + Toggle. Pas de delete |
| Validation | **Anti-cycle uniquement** : `Department.clean()` vérifie qu'un nœud ne peut pas être son propre ancêtre. `level` = hint de tri/suggestion UI, pas de contrainte bloquante |
| Mapping levels | DG=1, DIRECTION=2, SOUS_DIRECTION=3, REGION=3, DEPARTEMENT=4, AGENCE=4, SERVICE=5 (advisory) |
| UI Organigramme | Déplacé `admin_it` → Audit Admin (Task 28) |

### Architecture : PAS d'app séparée `audit_admin`

**Leçon apprise** — la tentative précédente avait créé `apps.audit_admin` pour héberger les vues CRUD sources. Confusion avec `apps.audit` (qui contient `AuditLog`) → 2 apps "audit" coexistent, sidebar confuse, imports ambigus.

**Décision** :
- CRUD Sources → vit dans `apps.workflow` (à côté du modèle `RecommendationSource`)
- CRUD OrgUnitType + Organigramme → vit dans `apps.users` (à côté du modèle `Department`)
- URLs publiques : préfixes existants (`/audit/sources-admin/`, `/auth/orgtypes-admin/`, `/auth/organigramme/`)
- Templates : `code/templates/workflow/admin/sources/` et `code/templates/users/admin/orgtypes/`

### Patterns existants à réutiliser

- **`AuditAdminRequiredMixin`** dans [`code/apps/users/mixins.py:15`](code/apps/users/mixins.py#L15) — déjà existant, à utiliser pour toutes les vues CRUD Phase A et B
- **Pattern HTMX modale CRUD** : [`code/templates/admin_it/user_create.html`](code/templates/admin_it/user_create.html) — modèle à suivre pour `_form_modal.html`
- **Pattern service `create_*` + AuditLog** : [`code/apps/workflow/services.py:create_recommendation`](code/apps/workflow/services.py#L31) — structure transaction.atomic + AuditLog.objects.create
- **Pattern data migration RunPython** : [`code/apps/users/migrations/0004_enrich_organigramme.py`](code/apps/users/migrations/0004_enrich_organigramme.py) — exemple de seed data
- **Pattern `select_for_update()` + django-fsm-safe** : [`code/apps/workflow/services.py:submit_evidence_by_dg`](code/apps/workflow/services.py) — pattern Story 3.7
- **HX-Refresh + HX-Trigger notify** : [`code/static/js/sentinel.js`](code/static/js/sentinel.js) — clé JSON `"msg"` (pas `"message"`)

### NFR couverts

- **NFR-AGN-01 — Agnosticisme produit** : Sentinel utilisable hors BICEC sans modification code (sources + types configurables)
- **NFR-SEC-05 — AuditLog append-only** : toute mutation source/type tracée (AC7, AC13)
- **NFR-PERF-02 — UI < 200ms P95** : pattern HTMX hx-post conservé pour les CRUD

### Cas spéciaux & invariants

- **`code` immuable** : choix produit. Si l'audit veut "renommer" un code, doit créer une nouvelle source/type + désactiver l'ancienne
- **`level` advisory** : l'audit peut ajuster le niveau d'un type existant. Aucune validation stricte sur les hiérarchies existantes — `level` est un hint de tri/affichage, pas une contrainte métier
- **Anti-cycle seul garde-fou dur** : `Department.clean()` empêche un nœud d'être son propre ancêtre (protection contre boucle infinie dans `__str__()` et `get_children()` récursif)
- **Pas de `parent_types` M2M sur OrgUnitType** : pas de validation hiérarchique par type, `level` suffit comme hint (simplicité)
- **Recommendation.Source enum** : conservé Task 1.2 → retiré Task 5 (après que la data migration 0011 a fini d'en avoir besoin)
- **`get_source_display` / `get_type_display`** : disparaissent quand CharField→FK. Remplacer par `.source.label` et `.type.name` dans tous les templates (Tasks 10b, 29b)

### Project Structure Notes

Fichiers à **modifier** :
- `code/apps/workflow/models.py` — ajouter `RecommendationSource`, retirer enum `Source`, basculer champ FK
- `code/apps/workflow/services.py` — ajouter 3 services CRUD + fix piège 3 (changes JSON-safe)
- `code/apps/workflow/selectors.py` — ajouter `get_active_sources()` etc. + adapter filtre source UUID uniquement + ajouter `"source"` au `select_related()`
- `code/apps/workflow/forms.py` — adapter `RecommendationForm` (ModelChoiceField)
- `code/apps/workflow/views.py` — ajouter 4 vues CRUD sources + adapter `RecommendationListView`
- `code/apps/workflow/urls.py` — ajouter 4 routes `sources-admin/`
- `code/apps/workflow/tests/test_views.py` — adapter ~7 usages Source.X (mix instance/pk string)
- `code/apps/workflow/tests/test_delegation.py, test_forms.py, test_models.py, test_services.py` — adapter ~8 usages
- `code/templates/workflow/recommendation_list.html` — adapter boucle source dropdown
- `code/templates/workflow/recommendation_detail.html` — fix `get_source_display` → `.source.label` (Task 10b)
- `code/templates/workflow/partials/recommendation_table.html` — fix `get_source_display` → `.source.label` (Task 10b)
- `code/templates/admin_it/partials/organigramme_drilldown.html` — fix `get_type_display` → `.type.name` + comparaisons `dept.type.code` (Task 29b)
- `code/templates/admin_it/partials/organigramme_node.html` — fix `get_type_display` → `.type.name` (Task 29b)
- `code/templates/partials/sidebar_audit.html` — ajouter section Configuration > Sources/Types/Organigramme
- `code/templates/partials/sidebar_admin.html` — retirer Organigramme (déplacé)
- `code/apps/users/models.py` — ajouter `OrgUnitType`, retirer enum `Type`, basculer FK + `clean()`
- `code/apps/users/services.py` — ajouter 3 services CRUD OrgUnitType
- `code/apps/users/selectors.py` — ajouter 3 sélecteurs OrgUnitType
- `code/apps/users/views.py` — ajouter 4 vues CRUD OrgUnitType + reclasser vues organigramme sous AuditAdminRequiredMixin
- `code/apps/users/urls.py` — ajouter 4 routes `orgtypes-admin/`
- `code/apps/users/forms.py` — adapter `DepartmentForm` (ModelChoiceField type)
- `code/apps/users/tests/test_*.py` — adapter ~35 usages Department.Type.X
- ~~`code/apps/dashboards/tests/test_views.py`~~ — **retiré** (0 occurrence confirmée par grep)
- `code/apps/workflow/migrations/0010, 0011, 0012` (créer)
- `code/apps/users/migrations/0005, 0006, 0007` (créer)

Fichiers à **créer** :
- `code/apps/workflow/forms.py` (ou nouveau `admin_forms.py`) — `RecommendationSourceForm`
- `code/apps/users/forms.py` — `OrgUnitTypeForm`
- `code/templates/workflow/admin/sources/list.html`
- `code/templates/workflow/admin/sources/_form_modal.html`
- `code/templates/users/admin/orgtypes/list.html`
- `code/templates/users/admin/orgtypes/_form_modal.html`
- `code/apps/workflow/tests/test_recommendation_source.py` (Task 33)
- `code/apps/users/tests/test_org_unit_type.py` (Task 34)

### References

- `_bmad-output/planning-artifacts/architecture-v2.md` §4-5 (référentiels paramétrables + agnosticisme)
- `_bmad-output/planning-artifacts/prd-v2.md` (NFR-AGN-01 si présent, sinon à acter)
- Story 3.7 artifact : `_bmad-output/implementation-artifacts/3-7-soumission-exclusive-dg.md` (pattern `select_for_update` + AuditLog `content_type` string)
- Story 1.4 artifact : `_bmad-output/implementation-artifacts/1-4-gestion-organigramme-institutionnel.md` (pattern CRUD organigramme actuel à refactorer)
- **Brainstorming utilisateur (2026-05-28)** : 6 AskUserQuestion → décisions verrouillées (Audit Admin permissions, seed auto data migration, etc.)
- **Revue technique (2026-05-28)** : 6 corrections intégrées — AC9 strict→advisory (anti-cycle only), retrait shim UUID/code, retrait champ `icon`, ajout Tasks 10b/29b (fix `get_*_display` templates), ajout `select_related("source")`
- **Tentative précédente revertée** : 4 pièges techniques documentés ci-dessus (sections Pièges 1-4 Dev Notes)
- **Revue croisée code (2026-05-28, post-plan)** : 7 corrections intégrées après vérification exhaustive par grep/view sur le code réel :
  1. Retrait faux positif `dashboards/tests/test_views.py` (Tasks 15, 30 — 0 occurrence confirmée)
  2. Bug existant `S_DIRECTION` → `SOUS_DIRECTION` dans `organigramme_drilldown.html:27` (Task 29b)
  3. Harmonisation préfixe URL `admin/` vs `admin-it/` dans AC11
  4. `select_related("source")` étendu aux 3 sélecteurs (pas seulement le sélecteur liste)
  5. `DepartmentSearchView` ajouté à la migration de mixin (Task 28 — 5 vues, pas 4)
  6. Lignes exactes à supprimer dans `forms.py` (L151-155) référencées dans Task 8
  7. Fichier `admin_forms.py` recommandé pour Task 12 (séparation sémantique)

## Dev Agent Record

### Agent Model Used
(à remplir lors de l'implémentation)

### Debug Log References
(à remplir lors de l'implémentation — référencer pièges Dev Notes en cas de régression)

### Completion Notes List
(à remplir lors de l'implémentation)

### File List
(à remplir lors de l'implémentation)
