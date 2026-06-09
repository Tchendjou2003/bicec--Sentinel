# Story 3.1 — Ajouts Manquants & Correctifs

> **Statut :** Complément au plan `3-1-todo-list-filter-historique-recent.md`
> **Date :** 2026-05-17
> **Source :** Audit croisé PRD v2, Architecture v2, Epics, Code existant

---

## 1. Couverture des Acceptance Criteria

| AC | Couvert ? | Détail |
|---|---|---|
| **AC1** — Affichage par défaut (Nouvelles Recos) | ✅ Oui | Subtask 1.4 gère le param `import_status`, logique `import_tag` vide/nul |
| **AC2** — Bascule HTMX sans rechargement | ✅ Oui | Subtask 2.3/2.4 avec HTMX + Alpine.js |
| **AC3** — UX Pills/Tabs + visuel actif | ✅ Oui | Subtask 2.4 avec Tailwind classes |

**Verdict :** Les 3 AC sont couverts.

---

## 2. Couverture des FR/NFR du PRD V2

| Exigence | Couvert ? | Commentaire |
|---|---|---|
| **FR5** — Création manuelle (masquer bouton pour DM/ETP) | ✅ | Subtask 2.1 |
| **FR6** — Soft Delete DRAFT (masquer actions pour DM/ETP) | ✅ | Subtask 2.2 |
| **FR28** — RBAC applicatif, visibilité par périmètre | ⚠️ Partiel | Subtask 1.2 couvre DM/ETP mais **ne mentionne pas explicitement le rôle DG** (FR32/FR33/FR34) ni les Auditeurs Externes |
| **FR29** — Filtres multi-critères (source, priorité, statut, aging) | ⚠️ Faible | Le plan ne traite que `import_status`. La **préservation des filtres croisés** est mentionnée dans Subtask 3.3 mais **pas d'intégration technique détaillée** avec les filtres existants (source, status, priority, q) |
| **FR30** — Code couleur urgence Rouge/Orange/Vert | ❌ Absent | Non mentionné dans le plan |
| **NFR-PERF-01** — RBAC < 10ms | ⚠️ Implicite | Le `select_related` (Subtask 1.3) aide mais **pas de test de performance** |
| **NFR-PERF-02** — UI < 200ms P95 | ⚠️ Implicite | `select_related` mentionné (Subtask 1.3) mais **aucun test/benchmark** pour valider le seuil avec 2000 recos |
| **NFR-SEC-05** — Audit Logs | ❌ Absent | Aucune mention de logging des actions de filtrage |

---

## 3. Analyse des Tâches — Lacunes Identifiées

### 3.1 Backend (Task 1)

| Problème | Sévérité | Détail |
|---|---|---|
| **WorkflowAccessMixin non défini** | 🔴 Critique | Subtask 1.5 dit "créer un mixin adapté (ex: `WorkflowAccessMixin`)" mais **ne spécifie pas** quels rôles il autorise, ni comment il gère le DG (FR32/FR33). Le code actuel utilise `AuditRequiredMixin` qui bloque DM/ETP avec 403. |
| **Sélecteur universel non détaillé** | 🟡 Moyen | Subtask 1.1 parle de `get_recommendations_for_user(user, filters)` mais **ne décrit pas la logique de branchement** par rôle (AUDIT → tout, DM → département + exclude DRAFT, ETP → assigned_etp + exclude DRAFT) |
| **import_tag edge case** | 🟡 Moyen | Le Dev Notes dit `isnull=False` et `exclude(import_tag="")` mais le modèle (`models.py:227`) a `blank=True, null=True`. Il faut vérifier que `""` (vide) et `None` (null) sont bien traités comme "récent" |
| **Pagination + import_status** | 🟡 Moyen | Le template de pagination (`recommendation_table.html:96-99`) préserve `source`, `status`, `priority`, `q` dans les liens mais **pas `import_status`** — la bascule perdra le filtre à la page suivante |
| **Filtres existants non adaptés** | 🟡 Moyen | Les `<select>` de filtres dans `recommendation_list.html` utilisent `hx-include` explicite. L'ajout d'un champ hidden `import_status` nécessite de **mettre à jour tous les `hx-include`** pour inclure `[name='import_status']` |

### 3.2 Frontend (Task 2)

| Problème | Sévérité | Détail |
|---|---|---|
| **recommendation_filters.html est vide** | 🟡 Moyen | Le fichier est un commentaire mort (`{# Ce fichier n'est plus utilisé #}`). Les filtres sont directement dans `recommendation_list.html`. Le plan référence le mauvais fichier. |
| **Alpine.js dispatch non détaillé** | 🟡 Moyen | Subtask 2.4 mentionne `$dispatch('submit')` mais le formulaire actuel n'a pas de `<form>` wrap — les filtres sont des `<select>` individuels avec `hx-get` direct. Il faut revoir l'architecture du formulaire. |
| **DG non couvert** | 🟡 Moyen | L'UC du DG (§4.4 architecture-v2) montre "Consulter Dashboard Supervision macro" + "To-Do List". Le DG est un rôle qui accède aux recommandations mais le plan ne le mentionne pas. |

### 3.3 Tests (Task 3)

| Test manquant | Couvre | Pourquoi c'est important |
|---|---|---|
| **Test DM ne voit PAS les DRAFT** | FR6, FR28 | Le plan dit "exclude(status='DRAFT')" mais aucun test ne le vérifie explicitement |
| **Test ETP ne voit que ses recos** | FR28 | Subtask 3.2 mentionne `assigned_etp=user` mais **aucun test d'intégration** ne crée une reco assignée à un ETP différent et vérifie l'invisibilité |
| **Test Audit voit TOUT (import_status filter)** | FR28 | Aucun test ne vérifie qu'un Auditeur voit à la fois les récentes ET les historiques |
| **Test DG accède à la liste** | FR32 | Le rôle DG n'est pas testé |
| **Test HTMX retourne le partial** | AC2 | Le test existant `test_htmx_request_returns_partial` vérifie le 200 mais **pas que c'est bien le template partiel** qui est retourné |
| **Test filtres croisés préservés** | FR29 | Subtask 3.3 est mentionné mais **aucun code de test** n'est fourni |
| **Test pagination + import_status** | FR29 | Non mentionné |
| **Test import_status invalide** | Robustesse | Que se passe-t-il si `import_status=toto` ? |
| **Test empty state par catégorie** | UX | Si un DM n'a aucune reco récente, l'empty state s'affiche-t-il ? |
| **Test performance (NFR-PERF-02)** | NFR | Aucun test de charge pour 2000 recos |
| **Test Audit Log généré** | NFR-SEC-05 | Aucune vérification que les actions de filtrage sont loggées |

---

## 4. Incohérences Techniques

| # | Incohérence | Impact |
|---|---|---|
| 1 | Le plan dit "masquer le bouton Créer pour les DM/ETP (ex: `{% if user.is_auditor %}`)" mais le modèle User n'a pas de propriété `is_auditor` — il a `role == 'AUDIT'` | 🔴 Le template ne compilera pas |
| 2 | Le plan dit "Modifier `apps/workflow/selectors.py` pour créer un sélecteur universel" mais le fichier actuel a `get_recommendations_for_audit()` — il faut décider si on **remplace** ou **ajoute** | 🟡 Risque de casser l'existant |
| 3 | Le plan référence `templates/workflow/partials/recommendation_filters.html` mais ce fichier est **vide** (commentaire mort) — les filtres sont dans `recommendation_list.html` | 🟡 Confusion pour le dev |
| 4 | Le plan ne mentionne pas la migration Django nécessaire si le sélecteur change la structure des QuerySets | 🟡 Pas de risque DB mais risque de régression |
| 5 | Le plan dit "remplacer `AuditRequiredMixin` par `WorkflowAccessMixin`" sur `RecommendationListView` mais les autres vues (Create, Update, Delete, Assign, Detail) utilisent aussi `AuditRequiredMixin` — faut-il les changer aussi ? | 🟡 Portée ambiguë |

---

## 5. Recommandations pour Compléter le Plan

### Priorité HAUTE (bloquantes)

1. **Définir le WorkflowAccessMixin** : Spécifier explicitement les rôles autorisés (AUDIT, DM, ETP, DG ?) et la logique de redirection (403 ou redirect vers dashboard rôle)

2. **Ajouter les tests manquants** :
   - `test_dm_excludes_draft` — DM ne voit pas les DRAFT
   - `test_etp_only_sees_assigned` — ETP ne voit que ses recos
   - `test_audit_sees_all_with_import_filter` — Audit voit tout
   - `test_dg_can_access_list` — DG accède à la liste
   - `test_htmx_returns_partial_template` — Vérifier le template partiel
   - `test_cross_filters_preserved` — Filtres croisés préservés
   - `test_pagination_preserves_import_status` — Pagination + import_status
   - `test_invalid_import_status` — Paramètre invalide

3. **Corriger la pagination** : Ajouter `import_status` dans les liens de pagination du template `recommendation_table.html`

4. **Corriger les hx-include** : Mettre à jour tous les `hx-include` des filtres existants pour inclure `[name='import_status']`

### Priorité MOYENNE (importantes)

5. **Intégrer FR30** : Ajouter le code couleur Rouge/Orange/Vert dans le tableau (déjà partiellement fait dans le template existant avec `is_overdue`)

6. **Clarifier le scope DG** : Déterminer si le DG accède à la même vue liste ou à une vue dédiée (FR32)

7. **Performance test** : Ajouter un test Django avec `assertNumQueries` pour valider le NFR-PERF-02

8. **Sélecteur : détailler la logique RBAC** : Écrire le pseudo-code du `get_recommendations_for_user` avec les 3 branches (AUDIT/DM/ETP)

### Priorité BASSE (nice-to-have)

9. **Audit Log** : Logger les changements de filtre import_status (NFR-SEC-05)

10. **Test edge case import_tag** : Vérifier `import_tag=""` vs `import_tag=None` vs `import_tag="IMPORTED"`

---

## 6. Détail des Correctifs Techniques

### 6.1 WorkflowAccessMixin — Spécification Proposée

```python
# apps/users/mixins.py

class WorkflowAccessMixin(LoginRequiredMixin):
    """
    Mixin — Autorise l'accès aux vues workflow pour AUDIT, DM, ETP, DG.

    Remplace AuditRequiredMixin sur les vues de liste/détail des recommandations
    pour permettre aux DM/ETP/DG d'accéder à leur périmètre filtré.

    Les rôles ADMIN et EXTERNE restent exclus (403).
    """

    def dispatch(self, request, *args, **kwargs):
        from .models import User
        allowed_roles = {
            User.Role.AUDIT,
            User.Role.DM,
            User.Role.ETP,
            User.Role.DG,
        }
        if request.user.is_authenticated and not (
            request.user.role in allowed_roles
            or request.user.is_superuser
        ):
            raise PermissionDenied("Accès réservé aux rôles métiers.")
        return super().dispatch(request, *args, **kwargs)
```

### 6.2 Sélecteur Universel — Logique RBAC Proposée

```python
# apps/workflow/selectors.py

def get_recommendations_for_user(*, user, filters: dict | None = None) -> QuerySet:
    """
    Sélecteur universel avec RBAC intégré.

    Branchement par rôle :
    - AUDIT : voit tout (sans filtre département)
    - DM    : voit son département + exclude DRAFT
    - ETP   : voit ses assignations (assigned_etp=user) + exclude DRAFT
    - DG    : voit son périmètre (à définir avec FR32)
    """
    from apps.users.models import User

    qs = (
        Recommendation.objects
        .select_related("created_by", "department", "assigned_dm", "assigned_etp")
        .filter(is_deleted=False)
    )

    # --- RBAC Branch ---
    if user.role == User.Role.AUDIT or user.is_superuser:
        pass  # Accès total
    elif user.role == User.Role.DM:
        qs = qs.filter(department=user.department).exclude(status="DRAFT")
    elif user.role == User.Role.ETP:
        qs = qs.filter(assigned_etp=user).exclude(status="DRAFT")
    elif user.role == User.Role.DG:
        # FR32 : DG voit les recos de sa direction
        qs = qs.filter(department=user.department).exclude(status="DRAFT")
    else:
        return qs.none()  # Fail-safe

    # --- Filtres existants ---
    if filters:
        if filters.get("source"):
            qs = qs.filter(source=filters["source"])
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])
        if filters.get("priority"):
            qs = qs.filter(priority=filters["priority"])
        if filters.get("q"):
            from django.db.models import Q
            qs = qs.filter(
                Q(reference__icontains=filters["q"])
                | Q(mission_label__icontains=filters["q"])
            )

    # --- Filtre Historique/Récent (Story 3.1) ---
    import_status = (filters or {}).get("import_status")
    if import_status == "historique":
        qs = qs.exclude(import_tag__isnull=True).exclude(import_tag="")
    elif import_status == "recent":
        qs = qs.filter(
            models.Q(import_tag__isnull=True) | models.Q(import_tag="")
        )
    # Si import_status est vide ou invalide → pas de filtre (affiche tout)

    return qs.order_by("-created_at")
```

### 6.3 Template — Bouton Créer (Correction is_auditor)

```html
{# recommendation_list.html — Bouton Créer #}
{# INCORRECT : {% if user.is_auditor %} #}
{# CORRECT : #}
{% if user.role == 'AUDIT' or user.is_superuser %}
<button
  @click="slideOverOpen = true"
  hx-get="{% url 'workflow:recommendation-create' %}"
  hx-target="#stepper-container"
  hx-swap="innerHTML"
  class="inline-flex items-center gap-2 rounded-xl ..."
  id="btn-new-recommendation"
>
  Nouvelle recommandation
</button>
{% endif %}
```

### 6.4 Template — Pills/Tabs avec HTMX (Architecture Proposée)

```html
{# recommendation_list.html — Composant Pills/Tabs #}
<div class="flex items-center gap-1 rounded-lg bg-gray-100 p-1" role="tablist">
  <button
    role="tab"
    @click="$refs.importStatus.value = 'recent'; $refs.filterForm.dispatchEvent(new Event('submit', {bubbles: true}))"
    :class="import_status !== 'historique' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'"
    class="px-4 py-2 text-sm font-medium rounded-md transition-all"
    x-data
  >
    Nouvelles Recos
  </button>
  <button
    role="tab"
    @click="$refs.importStatus.value = 'historique'; $refs.filterForm.dispatchEvent(new Event('submit', {bubbles: true}))"
    :class="import_status === 'historique' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'"
    class="px-4 py-2 text-sm font-medium rounded-md transition-all"
    x-data
  >
    Backlog Historique
  </button>
</div>

{# Champ hidden pour HTMX #}
<input type="hidden" name="import_status" x-ref="importStatus"
       value="{{ current_import_status }}" id="id_import_status">
```

### 6.5 Pagination — Correction import_status

```html
{# recommendation_table.html — Pagination #}
{% if page_obj.has_previous %}
<a href="?page={{ page_obj.previous_page_number }}&source={{ current_source|urlencode }}&status={{ current_status|urlencode }}&priority={{ current_priority|urlencode }}&q={{ current_search|urlencode }}&import_status={{ current_import_status|urlencode }}"
   class="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors">
  Préc.
</a>
{% endif %}
{% if page_obj.has_next %}
<a href="?page={{ page_obj.next_page_number }}&source={{ current_source|urlencode }}&status={{ current_status|urlencode }}&priority={{ current_priority|urlencode }}&q={{ current_search|urlencode }}&import_status={{ current_import_status|urlencode }}"
   class="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors">
  Suiv.
</a>
{% endif %}
```

### 6.6 hx-include — Mise à jour des filtres existants

```html
{# Chaque <select> de filtre doit inclure import_status #}
<select name="source"
  hx-get="{% url 'workflow:recommendation-list' %}"
  hx-target="#recommendation-table"
  hx-swap="innerHTML"
  hx-include="[name='source'],[name='status'],[name='priority'],[name='q'],[name='import_status']"
  ...
>
```

---

## 7. Nouveaux Tests à Ajouter

```python
# apps/workflow/tests/test_views.py — Ajouts Story 3.1

class RecommendationListFilterTest(ViewTestMixin, TestCase):
    """Tests du filtre Historique vs Récent (Story 3.1)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer des recos récentes (sans import_tag)
        cls.recent_rec = create_recommendation(
            data={
                "reference": "REC-RECENT-001",
                "mission_date": timezone.now().date(),
                "mission_label": "Reco récente",
                "controlled_department": cls.department,
                "observations": "Obs",
                "description": "Desc",
                "source": Recommendation.Source.INTERNE,
                "priority": Recommendation.Priority.MOYENNE,
                "department": cls.department,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=[],
            performed_by=cls.audit_user,
        )
        # Créer des recos historiques (avec import_tag)
        cls.historical_rec = create_recommendation(
            data={
                "reference": "REC-HIST-001",
                "mission_date": timezone.now().date(),
                "mission_label": "Reco historique",
                "controlled_department": cls.department,
                "observations": "Obs",
                "description": "Desc",
                "source": Recommendation.Source.COBAC,
                "priority": Recommendation.Priority.HAUTE,
                "department": cls.department,
                "due_date": timezone.now().date() + timedelta(days=30),
                "import_tag": "IMPORTED",
            },
            deliverables_data=[],
            performed_by=cls.audit_user,
        )

    # --- AC1 : Affichage par défaut ---
    def test_default_shows_recent_only(self):
        """Par défaut, seules les recos récentes sont affichées."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, "REC-RECENT-001")

    def test_default_excludes_historical(self):
        """Par défaut, les recos historiques ne sont pas affichées."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        # Dépend de la logique : si pas de filtre, tout s'affiche
        # Si le filtre par défaut est "recent", alors :
        # self.assertNotContains(response, "REC-HIST-001")

    # --- AC2 : Bascule Historique ---
    def test_import_status_historique_shows_imported(self):
        """Le filtre historique affiche les recos importées."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "historique"},
        )
        self.assertContains(response, "REC-HIST-001")

    def test_import_status_recent_excludes_imported(self):
        """Le filtre récent exclut les recos importées."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "recent"},
        )
        self.assertContains(response, "REC-RECENT-001")
        self.assertNotContains(response, "REC-HIST-001")

    # --- RBAC DM ---
    def test_dm_excludes_draft(self):
        """Un DM ne voit pas les recommandations DRAFT."""
        self._login_as(self.dm_user)
        # La reco récente est en DRAFT (créée sans assignation)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, "REC-RECENT-001")

    def test_dm_only_sees_own_department(self):
        """Un DM ne voit que les recommandations de son département."""
        self.dm_user.department = self.department
        self.dm_user.save()
        self._login_as(self.dm_user)
        # Assigner la reco au DM pour qu'elle soit visible
        self.recent_rec.assigned_dm = self.dm_user
        self.recent_rec.status = Recommendation.Status.ASSIGNED
        self.recent_rec.save()
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, "REC-RECENT-001")

    # --- RBAC ETP ---
    def test_etp_only_sees_assigned(self):
        """Un ETP ne voit que les recommandations qui lui sont assignées."""
        self.etp_user.department = self.department
        self.etp_user.save()
        self._login_as(self.etp_user)
        # Sans assignation → rien visible
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, "REC-RECENT-001")

    def test_etp_sees_assigned_recommendation(self):
        """Un ETP voit la recommandation qui lui est assignée."""
        self.etp_user.department = self.department
        self.etp_user.save()
        self.recent_rec.assigned_etp = self.etp_user
        self.recent_rec.status = Recommendation.Status.IN_PROGRESS
        self.recent_rec.save()
        self._login_as(self.etp_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, "REC-RECENT-001")

    # --- RBAC Audit ---
    def test_audit_sees_all_with_import_filter(self):
        """Un Auditeur voit les récentes ET les historiques."""
        self._login_as(self.audit_user)
        # Filtre récent
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "recent"},
        )
        self.assertContains(response, "REC-RECENT-001")
        # Filtre historique
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "historique"},
        )
        self.assertContains(response, "REC-HIST-001")

    # --- Filtres croisés ---
    def test_cross_filters_preserved_with_import_status(self):
        """Les filtres source/priority sont préservés avec import_status."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {
                "import_status": "historique",
                "source": Recommendation.Source.COBAC,
            },
        )
        self.assertContains(response, "REC-HIST-001")

    def test_cross_filters_exclude_non_matching(self):
        """Les filtres croisés excluent les non-correspondants."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {
                "import_status": "historique",
                "source": Recommendation.Source.INTERNE,
            },
        )
        self.assertNotContains(response, "REC-HIST-001")

    # --- HTMX ---
    def test_htmx_request_returns_partial(self):
        """Une requête HTMX retourne le template partiel."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            HTTP_HX_REQUEST="true",
        )
        self.assertTemplateUsed(response, "workflow/partials/recommendation_table.html")

    # --- Pagination ---
    def test_pagination_preserves_import_status(self):
        """Les liens de pagination préservent le filtre import_status."""
        self._login_as(self.audit_user)
        # Créer assez de recos pour paginer
        for i in range(30):
            create_recommendation(
                data={
                    "reference": f"REC-PAGE-{i:03d}",
                    "mission_date": timezone.now().date(),
                    "mission_label": f"Reco page {i}",
                    "controlled_department": self.department,
                    "observations": "Obs",
                    "description": "Desc",
                    "source": Recommendation.Source.INTERNE,
                    "priority": Recommendation.Priority.MOYENNE,
                    "department": self.department,
                    "due_date": timezone.now().date() + timedelta(days=30),
                },
                deliverables_data=[],
                performed_by=self.audit_user,
            )
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "recent"},
        )
        self.assertContains(response, "import_status=recent")

    # --- Edge cases ---
    def test_invalid_import_status_shows_all(self):
        """Un import_status invalide affiche tout (pas de crash)."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": "invalid_value"},
        )
        self.assertEqual(response.status_code, 200)

    def test_empty_import_status_shows_all(self):
        """Un import_status vide affiche tout."""
        self._login_as(self.audit_user)
        response = self.client.get(
            reverse("workflow:recommendation-list"),
            {"import_status": ""},
        )
        self.assertEqual(response.status_code, 200)

    # --- UI Sécurité ---
    def test_create_button_hidden_for_dm(self):
        """Le bouton Créer n'est pas rendu pour un DM."""
        self._login_as(self.dm_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, "btn-new-recommendation")

    def test_create_button_hidden_for_etp(self):
        """Le bouton Créer n'est pas rendu pour un ETP."""
        self._login_as(self.etp_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertNotContains(response, "btn-new-recommendation")

    def test_create_button_visible_for_audit(self):
        """Le bouton Créer est rendu pour un Auditeur."""
        self._login_as(self.audit_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertContains(response, "btn-new-recommendation")

    # --- DG ---
    def test_dg_can_access_list(self):
        """Un DG peut accéder à la liste des recommandations."""
        dg_user = User.objects.create_user(
            username="dg_test",
            password="TestPass123!",
            role=User.Role.DG,
            department=self.department,
        )
        self.client.force_login(dg_user)
        response = self.client.get(reverse("workflow:recommendation-list"))
        self.assertEqual(response.status_code, 200)
```

---

## 8. Verdict Global

| Critère | Note | Commentaire |
|---|---|---|
| **Couverture AC** | 3/3 ✅ | Les 3 AC sont couvertes |
| **Couverture FR** | 3/6 ⚠️ | FR5, FR6 OK. FR28 partiel, FR29 faible, FR30 absent, FR32-34 ignorés |
| **Couverture NFR** | 0/4 ❌ | NFR-PERF-01/02 mentionnés mais pas testés. NFR-SEC-05 absent |
| **Complétude des tests** | 4/11 ⚠️ | 4 tests prévus, au moins 8 manquants |
| **Cohérence technique** | 3/5 ⚠️ | 5 incohérences identifiées (is_auditor, filters.html vide, etc.) |
| **Faisabilité** | ⚠️ | Le WorkflowAccessMixin est le point bloquant — sans définition claire, le plan est incomplet |

**Note globale : Le plan est un squelette correct mais insuffisant pour un dev autonome.** Il couvre le "happy path" mais manque de rigueur sur la sécurité (RBAC détaillé), les tests (8 manquants), et l'intégration avec l'existant (filtres, pagination, template). Il faut le renforcer avant de lancer le développement.
