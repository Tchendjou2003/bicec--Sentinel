# Code Review — Issues & Findings

**Date :** 2026-05-15
**Reviewer :** AI (BMAD code-review workflow)
**Stories reviewées :** 2-1, 2-5
**Fichiers analysés :** models, services, selectors, forms, views, urls, mixins, templates, tests, migrations

---

## Story 2-1 : Création Unitaire — Formulaire Stepper & Livrables

**Statut déclaré :** `done`
**Statut réel :** ⚠️ Toutes les tâches sont `[ ]` (non cochées)

---

### 🔴 CRITICAL

#### Issue #1 — Tâches non cochées malgré le statut `done`

**Fichier :** `_bmad-output/implementation-artifacts/2-1-creation-unitaire-formulaire-standard.md`
**Lignes :** 113–353

Toutes les tâches et sous-tâches de la story sont marquées `[ ]` (unchecked), mais le statut est `done`. Soit les tâches ont été réalisées sans être cochées, soit le statut est incorrect.

**Impact :** Impossible de vérifier la complétion réelle de chaque tâche. Risque de livrer du code incomplet.

**Action requise :** Cocher toutes les tâches `[ ]` → `[x]` si elles sont effectivement terminées, OU repasser le statut à `in-progress`.

---

#### Issue #2 — Fichier `recommendation_row.html` manquant

**Fichier attendu :** `templates/workflow/partials/recommendation_row.html`
**Référence :** Story 2-1, Task 9.4

La story spécifie la création d'un partiel `recommendation_row.html` pour les lignes HTMX swappables. Ce fichier n'existe pas. Le tableau est rendu directement dans `recommendation_table.html` sans partiel réutilisable pour chaque ligne.

**Impact :** Pas de réutilisation possible du template de ligne (ex: pour un rafraîchissement ciblé d'une seule ligne via HTMX).

**Action requise :** Créer le partiel `recommendation_row.html` OU supprimer la tâche 9.4 de la story si le pattern actuel est jugé suffisant.

---

### 🟠 HIGH

#### Issue #3 — Double filtrage dans `RecommendationListView`

**Fichiers :**
- `code/apps/workflow/views.py` (lignes 55–75)
- `code/apps/workflow/selectors.py` (lignes 16–54)

La vue `RecommendationListView.get_queryset()` applique les filtres (source, status, priority, q) manuellement via `qs.filter(...)`. Or le selector `get_recommendations_for_audit()` accepte déjà un paramètre `filters: dict` qui fait exactement la même chose. La logique de filtrage du selector (lignes 36–53) n'est jamais appelée.

**Impact :** Code dupliqué. Si le selector évolue, la vue ne bénéficiera pas des changements. Risque d'incohérence.

**Action requise :** Soit passer les filtres au selector, soit supprimer la logique de filtrage du selector.

---

#### Issue #4 — Fonction `models_Q_reference_mission` mal placée

**Fichier :** `code/apps/workflow/views.py` (lignes 99–102)

```python
def models_Q_reference_mission(search: str):
    from django.db.models import Q
    return Q(reference__icontains=search) | Q(mission_label__icontains=search)
```

Cette fonction helper de lecture/recherche est définie dans `views.py`. Selon le pattern HackSoft, toute logique de filtrage/lecture doit être dans `selectors.py`.

**Impact :** Violation de l'architecture. Non réutilisable par d'autres consommateurs.

**Action requise :** Déplacer la fonction dans `selectors.py` et l'importer dans la vue.

---

### 🟡 MEDIUM

#### Issue #5 — Aucun test pour `assign_recommendation_to_dm`

**Fichier manquant :** `code/apps/workflow/tests/test_services.py`

Le service `assign_recommendation_to_dm()` (Story 2.5) n'a aucun test. Les services `create_recommendation`, `update_recommendation`, `soft_delete_recommendation` sont testés, mais pas celui-ci.

**Impact :** Code non vérifié. Risque de régression silencieuse.

**Action requise :** Ajouter au minimum :
- Test assignation réussie DRAFT → ASSIGNED
- Test AuditLog TRANSITION créé
- Test erreur si DM invalide (mauvais rôle)
- Test erreur si DM n'appartient pas au département
- Test erreur si department est NULL

---

#### Issue #6 — Aucun test pour `RecommendationAssignView`

**Fichier manquant :** `code/apps/workflow/tests/test_views.py`

La vue `RecommendationAssignView` (GET + POST) n'a aucun test.

**Impact :** Le endpoint `/audit/recommandations/<uuid>/assign/` n'est pas vérifié.

**Action requise :** Ajouter au minimum :
- GET 200 pour AUDIT avec modale affichée
- GET 403 pour non-AUDIT
- POST assignation réussie → 204 + HX-Trigger
- POST status != DRAFT → 403
- POST formulaire invalide → 422

---

#### Issue #7 — Aucun test pour `AssignDMForm`

**Fichier manquant :** `code/apps/workflow/tests/test_forms.py`

Le formulaire `AssignDMForm` n'a aucun test.

**Impact :** Validation du formulaire non vérifiée.

**Action requise :** Ajouter au minimum :
- Test queryset filtré par département
- Test queryset vide si pas de département
- Test validation avec DM valide
- Test rejet si DM vide

---

#### Issue #8 — Aucun test pour `get_available_dms_for_department`

**Fichier manquant :** `code/apps/workflow/tests/test_forms.py` ou `test_services.py`

Le selector `get_available_dms_for_department()` n'a aucun test.

**Impact :** Logique de filtrage DM par département non vérifiée.

**Action requise :** Ajouter au minimum :
- Test retourne DMs actifs du département
- Test exclut DMs inactifs
- Test exclut DMs d'un autre département
- Test exclut utilisateurs avec un autre rôle

---

#### Issue #9 — `except Exception` trop large dans `RecommendationAssignView.post`

**Fichier :** `code/apps/workflow/views.py` (ligne 378)

```python
except Exception as e:
    # Race condition : TransitionNotAllowed ou ValidationError
```

Le bloc catch est trop générique. Il capture `TransitionNotAllowed`, `ValidationError`, mais aussi toute autre exception imprvue (ex: `IntegrityError`, `DatabaseError`).

**Impact :** Les erreurs de base de données sont masquées et retournées comme des erreurs métier (422 au lieu de 500).

**Action requise :** Remplacer par :
```python
from django_fsm import TransitionNotAllowed
from django.core.exceptions import ValidationError

except (TransitionNotAllowed, ValidationError) as e:
    ...
```

---

### 🟢 LOW

#### Issue #10 — Script HTMX inline dans `recommendation_list.html`

**Fichier :** `code/templates/workflow/recommendation_list.html` (lignes 132–142)

Les listeners `closeSlideOver` et `refreshTable` sont en JavaScript inline dans le template.

**Impact :** Non testable, non réutilisable, mélange logique/présentation.

**Action requise :** Optionnel — externaliser dans un fichier JS dédié.

---

#### Issue #11 — `recommendation_filters.html` existe mais n'est pas utilisé

**Fichier :** `code/templates/workflow/partials/recommendation_filters.html`

Ce fichier partiel existe mais les filtres sont directement intégrés dans `recommendation_list.html` (lignes 29–84).

**Impact :** Fichier mort (dead code). Peut induire en erreur lors de futures modifications.

**Action requise :** Supprimer `recommendation_filters.html` OU refactorer pour l'utiliser.

---

## Story 2-5 : Assignation Définitive au DM (Lancement du Chrono)

**Statut déclaré :** `review`
**Statut réel :** ⚠️ Aucun test écrit

---

### 🔴 CRITICAL

#### Issue #12 — Zéro test pour l'intégralité de la Story 2.5

**Fichiers concernés :**
- `code/apps/workflow/tests/test_services.py` — pas de test pour `assign_recommendation_to_dm()`
- `code/apps/workflow/tests/test_views.py` — pas de test pour `RecommendationAssignView`
- `code/apps/workflow/tests/test_forms.py` — pas de test pour `AssignDMForm`
- `code/apps/workflow/tests/test_models.py` — pas de test pour `assign_to_dm()` FSM

La story 2.5 ajoute 7 fichiers modifiés/créés avec de la logique métier critique (FSM, service, vue, formulaire, selector) mais aucun test n'a été écrit.

**Impact :** Code non vérifié. Impossible de valider que les ACs sont réellement implémentés. Risque de régression élevé.

**Action requise :** Écrire les tests AVANT de passer le statut à `done`. Voir Issues #5, #6, #7, #8 pour la liste détaillée.

---

### 🟠 HIGH

#### Issue #13 — Validation Alpine.js fragile dans `stepper_slideover.html`

**Fichier :** `code/templates/workflow/partials/stepper_slideover.html` (lignes 9–14)

```javascript
init() {
    this.$nextTick(() => {
        if (this.$refs.step1 && this.$refs.step1.querySelector('p.text-red-500')) { this.step = 1; }
        else if (this.$refs.step2 && this.$refs.step2.querySelector('p.text-red-500')) { this.step = 2; }
        ...
    });
}
```

La détection des erreurs de validation repose sur la classe CSS `p.text-red-500`. Si le style des messages d'erreur change, la détection casse silencieusement.

**Impact :** L'auto-jump vers l'étape avec erreurs peut ne plus fonctionner après un changement de style.

**Action requise :** Utiliser un data attribute (`data-has-error`) au lieu d'une classe CSS pour la détection.

---

### 🟡 MEDIUM

#### Issue #14 — Delta AuditLog incohérent pour `assigned_dm`

**Fichier :** `code/apps/workflow/services.py` (lignes 255–266)

```python
dm_display = dm.get_full_name() or dm.username
# ...
changes={
    "status": ["DRAFT", "ASSIGNED"],
    "assigned_dm": [None, dm_display],  # ← nom lisible
}
```

Le delta pour `assigned_dm` stocke le nom lisible (`dm_display`) au lieu du UUID. Or `update_recommendation()` stocke les PKs des FK (lignes 134–135). Incohérence dans le format de l'audit trail.

**Impact :** L'audit trail n'est pas exploitable de manière programmatique pour `assigned_dm`. Impossible de faire un lien direct vers l'utilisateur depuis le log.

**Action requise :** Uniformiser — stocker `str(dm.pk)` dans le delta, et le nom dans la `description`.

---

#### Issue #15 — `RecommendationAssignView.get` ne vérifie pas `department` explicitement

**Fichier :** `code/apps/workflow/views.py` (lignes 333–351)

La vue crée le formulaire `AssignDMForm(department=recommendation.department)` sans vérifier si `recommendation.department` est NULL. Le formulaire gère le cas (queryset vide), mais la vérification explicite dans la vue serait plus claire et plus sécurisée.

**Impact :** Faible — le comportement est correct mais le code est moins lisible.

**Action requise :** Ajouter un guard explicite :
```python
if not recommendation.department:
    return HttpResponseForbidden("La Direction concernée doit être renseignée.")
```

---

#### Issue #16 — `update_recommendation` ne vérifie pas le statut DRAFT pour les modifications non-assignation

**Fichier :** `code/apps/workflow/services.py` (lignes 119–124)

Le service `update_recommendation` lève un `ValueError` si le statut n'est pas DRAFT. Cependant, la vue `RecommendationUpdateView` vérifie aussi le statut (lignes 174, 185). Double protection OK, mais le service utilise `ValueError` au lieu d'une exception métier typée.

**Impact :** Faible — fonctionnel mais non standard.

**Action requise :** Optionnel — créer une exception métier `WorkflowError` pour plus de clarté.

---

### 🟢 LOW

#### Issue #17 — Story 2.5 inclut `stepper_slideover.html` dans le File List sans tâche explicite

**Fichier :** `_bmad-output/implementation-artifacts/2-5-assignation-definitive-dm.md` (ligne 234)

Le File List mentionne `templates/workflow/partials/stepper_slideover.html` avec la note "+init() auto-jump erreurs". Cette modification n'est pas dans les tâches de la story (Tasks 1–7). C'est un bonus non documenté dans les ACs.

**Impact :** Traçabilité incomplète. Le changement est utile mais hors scope de la story.

**Action requise :** Documenter le changement dans le Change Log avec une note "Bonus" ou le déplacer dans une story séparée.

---

#### Issue #18 — `AssignDMForm.dm.queryset` initialisé à `None`

**Fichier :** `code/apps/workflow/forms.py` (ligne 216)

```python
dm = forms.ModelChoiceField(
    queryset=None,  # Surchargé dans __init__
    ...
)
```

Le queryset est initialisé à `None` au lieu de `User.objects.none()`. Django gère les deux, mais `None` peut provoquer des warnings dans certains outils d'analyse.

**Impact :** Très faible — fonctionnel mais non standard.

**Action requise :** Remplacer par `queryset=User.objects.none()` ou laisser tel quel.

---

## 📊 Tableau récapitulatif

| # | Story | Severity | Issue | Fichier |
|---|-------|----------|-------|---------|
| 1 | 2-1 | 🔴 CRITICAL | Tâches non cochées, statut `done` | `2-1-...md` |
| 2 | 2-1 | 🔴 CRITICAL | `recommendation_row.html` manquant | `templates/` |
| 3 | 2-1 | 🟠 HIGH | Double filtrage vue/selector | `views.py`, `selectors.py` |
| 4 | 2-1 | 🟠 HIGH | `models_Q_reference_mission` mal placée | `views.py` |
| 5 | 2-1 | 🟡 MEDIUM | Pas de test `assign_recommendation_to_dm` | `test_services.py` |
| 6 | 2-1 | 🟡 MEDIUM | Pas de test `RecommendationAssignView` | `test_views.py` |
| 7 | 2-1 | 🟡 MEDIUM | Pas de test `AssignDMForm` | `test_forms.py` |
| 8 | 2-1 | 🟡 MEDIUM | Pas de test `get_available_dms_for_department` | `test_forms.py` |
| 9 | 2-1 | 🟡 MEDIUM | `except Exception` trop large | `views.py` |
| 10 | 2-1 | 🟢 LOW | Script HTMX inline | `recommendation_list.html` |
| 11 | 2-1 | 🟢 LOW | `recommendation_filters.html` non utilisé | `partials/` |
| 12 | 2-5 | 🔴 CRITICAL | Zéro test pour Story 2.5 complète | `tests/` |
| 13 | 2-5 | 🟠 HIGH | Validation Alpine.js fragile (CSS selector) | `stepper_slideover.html` |
| 14 | 2-5 | 🟡 MEDIUM | Delta AuditLog incohérent (nom vs PK) | `services.py` |
| 15 | 2-5 | 🟡 MEDIUM | Guard `department` manquant dans la vue | `views.py` |
| 16 | 2-5 | 🟡 MEDIUM | `ValueError` non typée | `services.py` |
| 17 | 2-5 | 🟢 LOW | Bonus non documenté dans File List | `2-5-...md` |
| 18 | 2-5 | 🟢 LOW | `queryset=None` au lieu de `.none()` | `forms.py` |

---

## 🎯 Plan d'action prioritaire

| Priorité | Action | Effort estimé |
|----------|--------|---------------|
| **P0** | Corriger les checkboxes de la Story 2-1 (`[ ]` → `[x]` ou statut → `in-progress`) | 5 min |
| **P0** | Écrire les tests pour Story 2.5 (Issues #5, #6, #7, #8, #12) | 2–3h |
| **P1** | Refactorer `RecommendationListView` pour utiliser le selector (Issue #3) | 30 min |
| **P1** | Déplacer `models_Q_reference_mission` dans `selectors.py` (Issue #4) | 10 min |
| **P1** | Uniformiser le delta AuditLog (Issue #14) | 15 min |
| **P2** | Remplacer `except Exception` par des exceptions spécifiques (Issue #9) | 10 min |
| **P2** | Améliorer la détection d'erreurs Alpine.js (Issue #13) | 20 min |
| **P3** | Supprimer ou utiliser `recommendation_filters.html` (Issue #11) | 10 min |
| **P3** | Nettoyer le script inline HTMX (Issue #10) | 15 min |
