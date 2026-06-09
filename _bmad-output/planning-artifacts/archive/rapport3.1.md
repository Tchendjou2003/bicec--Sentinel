# Rapport Code Review — Story 3.1

**Date :** 2026-05-17
**Reviewer :** BMad Dev Agent (Amelia) — Adversarial Review
**Story :** `3-1-todo-list-filter-historique-recent.md`
**Statut Story :** ready-for-dev
**Méthode :** BMAD Code Review Workflow

---

## Résumé Exécutif

| Catégorie | Nombre |
|-----------|--------|
| CRITICAL  | 0      |
| HIGH      | 3      |
| MEDIUM    | 3      |
| LOW       | 2      |

**Verdict :** Changes Requested — 3 issues HIGH doivent être corrigés avant validation.

---

## Contexte Git

### Fichiers modifiés (liés à la story)
| Fichier | Story File List |
|---------|----------------|
| `code/apps/users/mixins.py` | ✅ Attendu |
| `code/apps/workflow/selectors.py` | ✅ Attendu |
| `code/apps/workflow/views.py` | ✅ Attendu |
| `code/templates/workflow/recommendation_list.html` | ✅ Attendu |
| `code/templates/workflow/partials/recommendation_table.html` | ✅ Attendu |
| `code/apps/workflow/tests/test_views.py` | ✅ Attendu |

### Fichiers modifiés NON documentés dans la story (15 fichiers)
| Fichier | Source probable |
|---------|---------------|
| `code/apps/users/urls.py` | Story précédente |
| `code/apps/users/views.py` | Story précédente |
| `code/apps/workflow/urls.py` | Story précédente |
| `code/templates/habilitation/partials/toggle_admin.html` | Story précédente |
| `code/templates/habilitation/user_edit.html` | Story précédente |
| `code/templates/habilitation/user_list.html` | Story précédente |
| `code/templates/partials/sidebar_audit.html` | Story précédente |
| `code/templates/workflow/partials/stepper_slideover.html` | Story précédente |
| `code/apps/users/tests/test_external_readonly.py` | Story précédente |
| `code/apps/users/tests/test_habilitation.py` | Story précédente |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | BMAD |
| `_bmad-output/planning-artifacts/architecture-v2.md` | BMAD |
| `_bmad-output/planning-artifacts/epics.md` | BMAD |
| `_bmad-output/planning-artifacts/prd-v2.md` | BMAD |
| `_bmad-output/planning-artifacts/system-diagrams.md` | BMAD |

---

## Validation des Acceptance Criteria

### AC1 — Affichage par défaut (Nouvelles Recos) — ⚠️ PARTIAL

**Exigence :** L'interface affiche par défaut uniquement les recommandations dont `import_tag` est vide ou nul.

**Implémentation :**
- `views.py:61` — Default `"recent"` ✅
- `selectors.py:72-73` — Filtre `import_tag__isnull=True` ✅

**Problème :**
```python
# selectors.py:72-73
elif import_status == "recent":
    qs = qs.filter(import_tag__isnull=True)  # ← manque import_tag=""
```
L'AC spécifie "vide OU nul". Le code ne vérifie que `isnull=True`, pas `import_tag=""`.
Les recommandations avec `import_tag=""` (chaîne vide) seront exclues à tort.

**Fix requis :**
```python
elif import_status == "recent":
    from django.db.models import Q
    qs = qs.filter(Q(import_tag__isnull=True) | Q(import_tag=""))
```

---

### AC2 — Bascule vers le Backlog Historique — ⚠️ PARTIAL

**Exigence :** Le tableau affiche les recommandations issues de l'import (où `import_tag` n'est pas vide).

**Implémentation :**
- `recommendation_list.html:34-59` — Pills/Tabs avec Alpine.js ✅
- HTMX refresh sans rechargement ✅
- `selectors.py:70-71` — Filtre `import_tag="IMPORTED"` ⚠️

**Problème :**
```python
# selectors.py:70-71
if import_status == "historical":
    qs = qs.filter(import_tag="IMPORTED")  # ← hardcoded "IMPORTED"
```
L'AC dit "où `import_tag` n'est pas vide" — cela devrait inclure TOUT import_tag non-vide,
pas uniquement `"IMPORTED"`. Si le système d'import utilise d'autres valeurs (ex: `"COBAC_IMPORT"`,
`"LEGACY"`), elles seront exclues.

**Fix requis :**
```python
if import_status == "historical":
    from django.db.models import Q
    qs = qs.filter(Q(import_tag__isnull=False) & ~Q(import_tag=""))
```

---

### AC3 — UX du composant de filtrage — ✅ IMPLÉMENTÉ

**Exigence :** Composant "Pills" ou "Tabs" très visible, état actif indiqué visuellement.

**Implémentation :**
- `recommendation_list.html:34-59` — 3 onglets : "Nouvelles Recos", "Backlog Historique", "Toutes"
- Classes Tailwind actives : `border-sentinel-orange text-sentinel-orange`
- Classes Tailwind inactives : `border-transparent text-gray-500`
- Transitions CSS : `transition-colors`

**Verdict :** Conforme ✅

---

## Validation des Tasks / Subtasks

### Task 1 : Backend — Logique de filtrage et RBAC

| Subtask | Status | Notes |
|---------|--------|-------|
| 1.1 — `get_recommendations_for_user(user, filters)` | ✅ | Fonction créée dans `selectors.py:16` |
| 1.2 — Application RBAC | ⚠️ | Voir Finding #3 (RBAC Gap) |
| 1.3 — Optimisation N+1 | ✅ | `select_related("created_by", "department", "controlled_department", "assigned_dm", "assigned_etp")` |
| 1.4 — Paramètre `import_status` | ⚠️ | Voir Finding #1 et #2 |
| 1.5 — `WorkflowAccessMixin` | ✅ | Créé dans `mixins.py:72-87`, appliqué sur ListView et DetailView |

### Task 2 : Frontend — Composant de bascule UI & Sécurité Vue

| Subtask | Status | Notes |
|---------|--------|-------|
| 2.1 — Masquer bouton Créer pour DM/ETP | ✅ | `{% if user.role == 'AUDIT' or user.is_superuser %}` |
| 2.2 — Masquer actions si non-DRAFT | ✅ | `{% if rec.status == 'DRAFT' %}` + check rôle AUDIT |
| 2.3 — Intégration HTMX robuste | ✅ | `<form id="filter-form">`, `hx-include` complet |
| 2.4 — Pills/Tabs avec Alpine.js | ✅ | 3 onglets, dispatch HTMX trigger |
| 2.5 — Pagination préserve import_status | ✅ | `&import_status={{ current_import_status\|urlencode }}` |

### Task 3 : Tests

| Subtask | Status | Notes |
|---------|--------|-------|
| 3.1 — Test RBAC DM/DG | ✅ | `test_dm_excludes_draft`, `test_dm_only_sees_own_department`, `test_dg_can_access_list` |
| 3.2 — Test RBAC ETP | ✅ | `test_etp_only_sees_assigned` |
| 3.3 — Test Audit Filtrage | ✅ | `test_audit_sees_all_with_import_filter` |
| 3.4 — Test Filtres Croisés et Pagination | ⚠️ | `test_cross_filters_preserved` ✅, `test_pagination_preserves` ✅, `test_invalid_import_status_shows_all` ❌ MANQUANT |
| 3.5 — Test UI et HTMX | ✅ | `test_create_button_hidden_for_dm_and_etp`, `test_htmx_request_returns_partial` |

---

## Issues Détaillées

### 🔴 HIGH #1 — AC1 : `import_tag` vide non géré
- **Fichier :** `code/apps/workflow/selectors.py:72-73`
- **Impact :** Les recommandations avec `import_tag=""` ne sont pas affichées dans "Nouvelles Recos"
- **Sévérité :** HIGH — Critère d'acceptation non respecté
- **Fix :** `Q(import_tag__isnull=True) | Q(import_tag="")`

### 🔴 HIGH #2 — AC2 : Filtre historique trop restrictif
- **Fichier :** `code/apps/workflow/selectors.py:70-71`
- **Impact :** Seules les recos avec `import_tag="IMPORTED"` apparaissent dans "Backlog Historique"
- **Sévérité :** HIGH — Critère d'acceptation non respecté
- **Fix :** `Q(import_tag__isnull=False) & ~Q(import_tag="")`

### 🔴 HIGH #3 — RBAC Gap dans le sélecteur
- **Fichier :** `code/apps/workflow/selectors.py:40-47`
- **Impact :** Un utilisateur avec rôle `ADMIN`, `EXT` ou vide peut voir TOUTES les recommandations non-DRAFT de TOUS les départements
- **Sévérité :** HIGH — Faille de sécurité RBAC
- **Code problématique :**
```python
if not (user.role == User.Role.AUDIT or user.is_superuser):
    qs = qs.exclude(status=Recommendation.Status.DRAFT)
    if user.role in [User.Role.DM, User.Role.DG]:
        qs = qs.filter(department=user.department)
    elif user.role == User.Role.ETP:
        qs = qs.filter(assigned_etp=user)
    # ← ADMIN, EXT, rôle vide : tombent ici sans filtre !
```
- **Fix :** Ajouter un `else` qui lève `PermissionDenied` ou retourne un queryset vide

### 🟡 MEDIUM #4 — Test manquant `test_invalid_import_status_shows_all`
- **Fichier :** `code/apps/workflow/tests/test_views.py`
- **Impact :** Couverture de test incomplète (Subtask 3.4)
- **Fix :** Ajouter :
```python
def test_invalid_import_status_shows_all(self):
    """Un import_status invalide affiche toutes les recommandations."""
    self._login_as(self.audit_user)
    rec_recent = self._create_draft_recommendation()
    rec_hist = self._create_draft_recommendation()
    Recommendation.all_objects.filter(pk=rec_hist.pk).update(import_tag="IMPORTED")
    response = self.client.get(
        reverse("workflow:recommendation-list"),
        {"import_status": "invalid_value"}
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, rec_recent.reference)
    self.assertContains(response, rec_hist.reference)
```

### 🟡 MEDIUM #5 — Valeur `import_tag` hardcodée
- **Fichier :** `code/apps/workflow/selectors.py:71`
- **Impact :** Si le système d'import utilise des valeurs autres que `"IMPORTED"`, elles seront exclues
- **Fix :** Utiliser une constante `IMPORT_TAG_VALUE = "IMPORTED"` dans les settings ou models, ou filtrer par non-vide

### 🟡 MEDIUM #6 — File List vide dans la story
- **Fichier :** `_bmad-output/implementation-artifacts/3-1-todo-list-filter-historique-recent.md:92`
- **Impact :** Traçabilité incomplète, le reviewer ne sait pas quels fichiers ont été modifiés
- **Fix :** Documenter les 6 fichiers dans le Dev Agent Record → File List

### 🟢 LOW #7 — Gestion implicite du filtre "all"
- **Fichier :** `code/apps/workflow/selectors.py:70-73`
- **Impact :** Fonctionnel mais pas explicite — le code tombe dans le vide du if/elif
- **Fix :** Ajouter `elif import_status == "all": pass` pour la clarté

### 🟢 LOW #8 — Statut story non mis à jour
- **Fichier :** `_bmad-output/implementation-artifacts/3-1-todo-list-filter-historique-recent.md:3`
- **Impact :** Le statut est `ready-for-dev` alors que le code est implémenté
- **Fix :** Mettre à jour vers `review`

---

## Recommandation

**Verdict : CHANGES REQUESTED**

Les 3 issues HIGH doivent être corrigés avant validation :
1. AC1 : Gérer `import_tag=""` dans le filtre "recent"
2. AC2 : Filtrer par non-vide au lieu de `"IMPORTED"` exact
3. RBAC : Ajouter un fallback sécurisé pour les rôles non gérés

Les issues MEDIUM et LOW peuvent être traités dans un second temps.

---

_Rapport généré par BMad Code Review Workflow — Story 3.1_
_Reviewer: Dave Lahe — 2026-05-17_
