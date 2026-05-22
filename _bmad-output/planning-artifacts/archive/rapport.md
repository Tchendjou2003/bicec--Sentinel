# Rapport de Vérification — Code Review Post-Correction

**Date :** 2026-05-15
**Vérificateur :** AI (BMAD code-review workflow)
**Source :** Corrections appliquées par Gemini 3.1 Pro
**Fichier référence :** `issue.md` (18 issues)

---

## Méthodologie

Chaque issue du fichier `issue.md` a été vérifiée en :
1. Relisant le code source corrigé
2. Vérifiant la présence/absence du fix
3. Évaluant la qualité de la correction
4. Identifiant les restes à faire

---

## Résultats par issue

### 🔴 CRITICAL

| # | Issue | Verdict | Détail |
|---|-------|---------|--------|
| 1 | Tâches non cochées, statut `done` | ⚠️ **PARTIEL** | Story 2-1 repassée à `in-progress` ✅ mais `sprint-status.yaml` dit toujours `done` ❌ — INCOHÉRENCE |
| 2 | `recommendation_row.html` manquant | ❌ **NON CORRIGÉ** | Fichier toujours absent. Non bloquant mais non documenté. |
| 12 | Zéro test pour Story 2.5 | ✅ **CORRIGÉ** | 4 classes de test ajoutées (models, services, views, forms) |

### 🟠 HIGH

| # | Issue | Verdict | Détail |
|---|-------|---------|--------|
| 3 | Double filtrage vue/selector | ✅ **CORRIGÉ** | `views.py:56-62` passe `filters` au selector |
| 4 | `models_Q_reference_mission` mal placée | ✅ **CORRIGÉ** | Fonction supprimée de `views.py` |
| 13 | Validation Alpine.js fragile | ✅ **CORRIGÉ** | `[data-has-error]` utilisé partout (11 occurrences) |

### 🟡 MEDIUM

| # | Issue | Verdict | Détail |
|---|-------|---------|--------|
| 5 | Pas de test `assign_recommendation_to_dm` | ✅ **CORRIGÉ** | `AssignRecommendationToDMTest` (3 tests) |
| 6 | Pas de test `RecommendationAssignView` | ✅ **CORRIGÉ** | `RecommendationAssignViewTest` (6 tests) |
| 7 | Pas de test `AssignDMForm` | ✅ **CORRIGÉ** | `AssignDMFormTest` (4 tests) |
| 8 | Pas de test `get_available_dms_for_department` | ✅ **CORRIGÉ** | `GetAvailableDMsForDepartmentTest` (4 tests) |
| 9 | `except Exception` trop large | ✅ **CORRIGÉ** | `except (TransitionNotAllowed, ValidationError)` |
| 14 | Delta AuditLog incohérent | ✅ **CORRIGÉ** | `str(dm.pk)` dans `changes`, nom dans `description` |
| 15 | Guard `department` manquant | ✅ **CORRIGÉ** | Vérification dans GET et POST |
| 16 | `ValueError` non typée | ⚠️ **PARTIEL** | Service utilise toujours `ValueError`, vue catch les bonnes exceptions |

### 🟢 LOW

| # | Issue | Verdict | Détail |
|---|-------|---------|--------|
| 10 | Script HTMX inline | ❌ **NON CORRIGÉ** | Script toujours inline dans `recommendation_list.html` |
| 11 | `recommendation_filters.html` non utilisé | ❌ **NON CORRIGÉ** | Fichier toujours présent |
| 17 | Bonus non documenté dans File List | ❌ **NON CORRIGÉ** | Non traité |
| 18 | `queryset=None` au lieu de `.none()` | ❌ **NON CORRIGÉ** | `forms.py:216` inchangé |

---

## 📊 Bilan global

| Statut | Nombre | Issues |
|--------|--------|--------|
| ✅ Corrigé | **11** | #3, #4, #5, #6, #7, #8, #9, #12, #13, #14, #15 |
| ⚠️ Partiel | **2** | #1, #16 |
| ❌ Non corrigé | **5** | #2, #10, #11, #17, #18 |

**Taux de correction complète : 61% (11/18)**
**Taux de correction (complète + partielle) : 72% (13/18)**

---

## 🧪 Évaluation de la qualité des tests

### Points positifs

1. **Couverture fonctionnelle correcte** — Les 4 classes de test ajoutées couvrent les 4 composants critiques de la Story 2.5 (model FSM, service, vue, form/selector).

2. **Tests de bon sens** — Les scénarios principaux sont couverts :
   - Assignation réussie DRAFT → ASSIGNED
   - AuditLog TRANSITION créé avec le bon delta
   - Blocage sur non-DRAFT (TransitionNotAllowed)
   - RBAC (403 pour non-AUDIT)
   - Formulaire invalide (422)

3. **Pattern de test cohérent** — Les nouveaux tests respectent les mixins et helpers existants (`ServiceTestMixin`, `ViewTestMixin`).

4. **Vérification du delta AuditLog** — Le test `test_assign_creates_audit_log_transition` vérifie explicitement `str(dm.pk)` dans le delta, ce qui valide la correction de l'Issue #14.

### Faiblesses identifiées

1. **`test_assign_to_dm_null_user_raises_error`** (test_models.py:315-328) — **TEST FAIBLE**
   ```python
   with self.assertRaises(Exception):
       try:
           rec.assign_to_dm(None)
       except Exception as e:
           if isinstance(e, (ValueError, AttributeError)):
               raise
           pass  # ← MASQUE les erreurs non-ValueError/AttributeError
   ```
   Ce test est un `assertRaises(Exception)` avec un `try/except` interne qui `pass` silencieusement pour certaines exceptions. Si `assign_to_dm(None)` lève un `TypeError` (ex: `None.role`), le test passe quand même. **Devrait être :** `self.assertRaises(ValidationError)` directement.

2. **Pas de test pour DM d'un autre département** (test_services.py) — Le service `assign_recommendation_to_dm` ne teste pas le cas où le DM appartient à un département différent de la recommandation. La validation est dans `assign_to_dm()` (models.py:334-337) mais le service ne la teste pas.

3. **Pas de test pour `department=NULL`** (test_views.py) — La vue retourne 403 si `department` est NULL (views.py:325-326, 348-349), mais aucun test ne vérifie ce comportement.

4. **Pas de test "Département Fantôme"** (test_views.py) — Le cas où aucun DM actif n'est rattaché au département (alerte amber dans la modale) n'est pas testé.

5. **Pas de test pour `is_deleted` sur assignation** (test_services.py) — Le service vérifie `if recommendation.is_deleted:` (services.py:263-264) mais aucun test ne couvre ce cas.

6. **`test_soft_delete_403_for_non_audit`** (test_views.py:322-326) — **BUG DANS LE TEST**
   ```python
   def test_soft_delete_403_for_non_audit(self):
       self._login_as(self.dm_user)
       rec = self._create_draft_recommendation()
       self.assertEqual(response.status_code, 403)  # ← 'response' non défini !
   ```
   La variable `response` n'est pas définie. Le test va lever un `NameError` à l'exécution. C'est un **bug existant** (pré-correction) mais qui n'a pas été détecté.

### Note globale qualité des tests : **6/10**

Les tests ajoutés sont fonctionnels et couvrent les cas principaux, mais ils manquent de profondeur sur les cas limites et contiennent un test cassé pré-existant.

---

## 🔍 Détail des corrections vérifiées

### Issue #3 — Refactor selector/views ✅

**Avant :**
```python
# views.py — filtres manuels + fonction orpheline
def get_queryset(self):
    qs = selectors.get_recommendations_for_audit(user=self.request.user)
    source = self.request.GET.get("source")
    if source:
        qs = qs.filter(source=source)
    # ...
```

**Après :**
```python
# views.py — délègue au selector
def get_queryset(self):
    filters = {
        "source": self.request.GET.get("source"),
        "status": self.request.GET.get("status"),
        "priority": self.request.GET.get("priority"),
        "q": self.request.GET.get("q"),
    }
    return selectors.get_recommendations_for_audit(user=self.request.user, filters=filters)
```

**Verdict :** Correction propre. Le selector fait maintenant tout le travail de filtrage.

---

### Issue #9 — Exceptions spécifiques ✅

**Avant :**
```python
except Exception as e:
```

**Après :**
```python
from django_fsm import TransitionNotAllowed
from django.core.exceptions import ValidationError
# ...
except (TransitionNotAllowed, ValidationError) as e:
```

**Verdict :** Correction correcte. Les imports sont dans le bloc `post()` (pas en haut du fichier), ce qui est acceptable pour éviter les imports circulaires.

---

### Issue #13 — Alpine.js data-has-error ✅

**Avant :**
```javascript
if (this.$refs.step1 && this.$refs.step1.querySelector('p.text-red-500')) { this.step = 1; }
```

**Après :**
```javascript
if (this.$refs.step1 && this.$refs.step1.querySelector('[data-has-error]')) { this.step = 1; }
```

Et tous les messages d'erreur ont maintenant `data-has-error` :
```html
<p data-has-error class="text-xs text-red-500 mt-1">{{ form.mission_date.errors.0 }}</p>
```

**Verdict :** Correction exemplaire. 11 occurrences de `data-has-error` ajoutées sur tous les messages d'erreur du stepper.

---

### Issue #14 — Delta AuditLog ✅

**Avant :**
```python
"assigned_dm": [None, dm_display],  # nom lisible
```

**Après :**
```python
"assigned_dm": [None, str(dm.pk)],  # UUID technique
# ...
dm_display = dm.get_full_name() or dm.username  # → description
```

**Verdict :** Correction propre. Le delta est maintenant exploitable par la machine, le nom reste dans la description humaine.

---

### Issue #15 — Guard department ✅

**Ajouté dans GET et POST :**
```python
if not recommendation.department:
    return HttpResponseForbidden("La Direction concernée doit être renseignée.")
```

**Verdict :** Correction correcte. Protection explicite dans les deux méthodes HTTP.

---

## 🎯 Reste à faire (priorisé)

| Priorité | Issue | Action | Effort |
|----------|-------|--------|--------|
| **P1** | #1 | Synchroniser `sprint-status.yaml` : `2-1-creation-unitaire-formulaire-standard: in-progress` | 1 min |
| **P1** | — | Corriger le bug `test_soft_delete_403_for_non_audit` (response non défini) | 2 min |
| **P1** | — | Renforcer `test_assign_to_dm_null_user_raises_error` | 5 min |
| **P2** | — | Ajouter test DM autre département dans `test_services.py` | 10 min |
| **P2** | — | Ajouter test `department=NULL` dans `test_views.py` | 5 min |
| **P2** | — | Ajouter test "Département Fantôme" dans `test_views.py` | 5 min |
| **P2** | — | Ajouter test `is_deleted` sur assignation | 5 min |
| **P3** | #2 | Créer `recommendation_row.html` ou supprimer la tâche 9.4 | 15 min |
| **P3** | #10 | Externaliser le script HTMX inline | 15 min |
| **P3** | #11 | Supprimer `recommendation_filters.html` | 2 min |
| **P3** | #18 | Remplacer `queryset=None` par `User.objects.none()` | 1 min |

---

## 📝 Conclusion

Les corrections P0 et P1 sont **globalement bien faites**. L'architecture HackSoft est respectée, les tests couvrent les cas principaux, et les corrections sont propres.

**Points forts :**
- Refactor vue/selector exemplaire
- Tests structurés et cohérents
- Alpine.js corrigé de manière robuste

**Points faibles :**
- Sprint-status non synchronisé avec le story file
- Un test cassé pré-existant non détecté
- Tests manquants sur les cas limites (department NULL, DM autre dept, is_deleted)
- Issues LOW non traitées (scripts inline, fichiers morts)

**Verdict global : Les corrections sont ACCEPTABLES pour passer la Story 2.5 en `done`, après synchronisation du sprint-status et correction du test cassé.**
