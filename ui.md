# Audit UI/UX — Sentinel (BICEC)

> **Date :** 10 juin 2026 | **Périmètre :** 81 templates, 3 CSS, 4 JS, tailwind.config.js
> **Méthode :** Analyse ligne par ligne, fichier par fichier — 11 critères.

---

## Table des matières

1. [Résumé Exécutif](#1-résumé-exécutif)
2. [Hiérarchie visuelle](#2-hiérarchie-visuelle)
3. [Charge cognitive](#3-charge-cognitive)
4. [Navigation rapide](#4-navigation-rapide)
5. [Feedback immédiat](#5-feedback-immédiat)
6. [Accessibilité](#6-accessibilité)
7. [Gestion des états](#7-gestion-des-états)
8. [Performance perçue](#8-performance-perçue)
9. [Action > Décoration](#9-action--décoration)
10. [Cohérence visuelle](#10-cohérence-visuelle)
11. [Centralisation des tokens](#11-centralisation-des-tokens)
12. [Organisation layout/détail](#12-organisation-layoutdétail)
13. [Annexe : Problèmes par fichier](#13-annexe--problèmes-par-fichier)

---

## 1. Résumé Exécutif

| Niveau | Nombre | Description |
|--------|--------|-------------|
| 🔴 Critique | 12 | Bugs UI fonctionnels, incohérences de blocs, doublons |
| 🟠 Majeur | 26 | Violations de design system, tokens en dur, accessibilité |
| 🟡 Mineur | 31 | Typos, conventions, détails d'harmonisation |
| 🔵 Info | 15 | Suggestions d'amélioration |

### Top 5 problèmes bloquants

1. **430+ styles inline** avec des hexadécimaux en dur — aucun respect du design system tokenisé
2. **2 implémentations différentes de la modale de suppression** (code dupliqué) dans `delete_confirm.html` et `recommendation_list.html:154-176`
3. **Police « Plus Jakarta Sans » déclarée mais jamais chargée** — fallback silencieux vers system-ui
4. **Boutons « Annuler »/« Confirmer » stylisés manuellement** dans 4 fichiers différents au lieu d'utiliser `btn btn-secondary` / `btn btn-primary`
5. **`close_confirm_modal.html` n'est pas une vraie modale** — pas d'overlay, pas de backdrop, apparaît en inline

---

## 2. Hiérarchie visuelle

### Ce qui est bien
- Les cartes (`.card`) avec border-left-top accent `h-1 bg-gradient` dans `kpi_card.html`
- Les badges de statut avec pastilles colorées + libellé
- La grille 4 colonnes dans `recommendation_detail.html` pour les métadonnées (Direction, Porteur, Échéance, Source)
- Les sections de la page détail bien distinctes (C1, C4, C5, C6, C7, C8)

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| H1 | `recommendation_detail.html` | 40-63 | Badges de statut dupliquent `status_badge.html` avec du inline style — 2 rendus possibles différents | 🟠 |
| H2 | `recommendation_detail.html` | 347 | Layout en `display:grid;grid-template-columns:1fr 320px` avec inline style plutôt que classes Tailwind | 🟡 |
| H3 | `stepper_slideover.html` | 55-63 | Labels du stepper (Contexte, Constats, Recommandation, Livrables) en `text-[10px]` — peu lisibles | 🟡 |
| H4 | `login.html` | 54-57 | Titre "Bienvenue sur Sentinel" en `font-size:40px` inline — cohérent mais devrait être un token | 🟢 |
| H5 | `home.html` | 7 | Page d'accueil minimaliste avec un seul bouton HTMX de test — pas de hiérarchie réelle | 🟢 |

---

## 3. Charge cognitive

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| C1 | `recommendation_detail.html` | 7-10 | **15 variables Alpine** dans le `x-data` — `slideOverOpen, assignModalOpen, delegateModalOpen, submitEvidenceModalOpen, rejectModalOpen, approveModalOpen, historyDrawerOpen, extensionRequestModalOpen, extensionReviewModalOpen, dgSubmitPanelOpen, closeConfirmModalOpen, rejectAuditModalOpen` — charge cognitive énorme | 🔴 |
| C2 | `assign_dm_modal.html` | 7-19 | Toggle DM/DG en deux onglets — bonne idée mais l'utilisateur doit comprendre la différence entre les deux circuits | 🟡 |
| C3 | `stepper_slideover.html` | 5-15 | 4 étapes avec validation uniquement serveur — pas d'indicateur de champs requis par étape | 🟠 |
| C4 | `extension_review_modal.html` | 6-28 | Composant conditionnel (approve/reject) avec 2 formulaires distincts dans le même template — beaucoup de logique | 🟡 |
| C5 | Global | — | **6 rôles** (AUDIT, DM, ETP, DG, EXT, ADMIN_IT) avec des sidebar différentes — l'utilisateur voit son périmètre mais ne sait pas ce que les autres voient | 🔵 |

---

## 4. Navigation rapide

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| N1 | `sidebar_audit.html` | 13-14, 19 | Liens morts : "Import" (#), "Validation" (#), "Piste d'audit" (#) | 🟡 |
| N2 | `sidebar_dm.html` | 13-15 | Liens morts : "Rapports" (#), "Audit Trail" (#), "Paramètres" (#) | 🟡 |
| N3 | `sidebar_etp.html` | 13-14 | Liens morts : "Soumettre Preuves" (#), "Historique" (#) | 🟡 |
| N4 | `sidebar_dg.html` | 17-18 | Liens morts : "Vue par Direction" (#), "Rapports & Exports" (#) | 🟡 |
| N5 | `sidebar_audit_ext.html` | 9-11 | URLs en dur (`/audit-ext/...`) au lieu de `{% url %}` | 🟠 |
| N6 | `recommendation_list.html` | 31-126 | Les filtres HTMX ré-incluent tous les paramètres à chaque changement — pas de navigation par URL propre | 🟡 |
| N7 | Global | — | Pas de menu de navigation mobile fonctionnel (sidebar masquée en lg) | 🔵 |

---

## 5. Feedback immédiat

### Ce qui est bien
- Toasts Alpine via `$store.sentinel.notify()` + écoute `HX-Trigger:notify` dans `sentinel.js`
- Skeleton loader dans `recommendation_table_skeleton.html`
- `htmx-indicator` avec transition d'opacité dans `input.css:231-240`
- Autosave du commentaire dans `submit_evidence_modal.html` avec délai 800ms

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| F1 | `stepper_slideover.html` | 230-233 | **Bouton submit final sans état de chargement** — l'utilisateur peut cliquer plusieurs fois | 🟠 |
| F2 | `stepper_slideover.html` | 225-228 | Bouton "Suivant" sans validation client — pas de feedback si champs requis vides | 🟠 |
| F3 | `submit_evidence_modal.html` | 168-169 | `:disabled="submitting"` bien géré, mais pas de message si l'upload échoue (catch console.error seulement) | 🟡 |
| F4 | `delete_confirm.html` | 19 | `htmx.ajax('POST', ...)` sans handler d'erreur — pas de toast si la suppression échoue | 🟠 |
| F5 | `base.html` | 75-92 | Bridge Django Messages → Alpine : la conversion `tags` ne gère que 4 types. Les tags customs sont ignorés | 🟡 |
| F6 | `assign_dm_modal.html` | 105 | Bouton submit avec `bg-gradient-to-r from-blue-600 to-blue-700` — **casse le pattern btn-primary**, pas de hover/active states | 🟠 |

---

## 6. Accessibilité

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| A1 | `login.html` | 133-134 | `onfocus`/`onblur` JS inline pour le focus — pas accessible via CSS `:focus` | 🟠 |
| A2 | `login.html` | 126-134 | Input username sans `aria-describedby` — pas de lien avec le label | 🟡 |
| A3 | Global | partout | De nombreux SVG décoratifs sans `aria-hidden="true"` | 🟠 |
| A4 | `status_badge.html` | 3-35 | Badges avec `color:#968A80` sur `background-color:#F0ECE7` — ratio de contraste ~2.8:1 (échec WCAG AA) | 🔴 |
| A5 | `recommendation_detail.html` | 40-63 | Mêmes couleurs de badges en inline — problème de contraste identique | 🔴 |
| A6 | `delete_confirm.html` | 4-5 | Modale sans `role="dialog"` ou `aria-modal` | 🟠 |
| A7 | `close_confirm_modal.html` | 4 | Pas de `role="dialog"` — ce n'est même pas une modale, c'est une div inline | 🟠 |
| A8 | `provisioning_reject_modal.html` | 15 | ✅ Bon exemple avec `role="dialog" aria-modal="true" aria-labelledby` | 🔵 |
| A9 | `recommendation_table.html` | 20 | Lignes cliquables via `onclick` — pas accessible au clavier (ni Enter, ni focus visible) | 🔴 |
| A10 | `input.css` | 75-78 | Scrollbar custom WebKit uniquement — pas de fallback Firefox | 🟡 |
| A11 | `base.html` | 44 | `hx-headers` exposé dans le HTML — pas un problème d'accessibilité stricto sensu mais de sécurité | 🟢 |

---

## 7. Gestion des états

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| E1 | `submit_evidence_modal.html` | 22-23 | `x-init="$el.style.width = '{{ progress }}%'"` — exécuté 1 fois, ne réagit pas aux changements de quota | 🟠 |
| E2 | `recommendation_detail.html` | 587 | `x-init` sur la barre de progression — idem, 1 fois à l'init | 🟠 |
| E3 | `recommendation_table_skeleton.html` | — | Skeleton visible mais pas de message "Chargement..." pour les lecteurs d'écran | 🟡 |
| E4 | `recommendation_list.html` | 131-134 | L'overlay du skeleton utilise `background:rgba(255,255,255,0.85)` — pas de backdrop-filter, lourd sur mobiles | 🟢 |
| E5 | `submit_evidence_modal.html` | 112-115 | Indicateur d'upload en cours bien présent (`x-show="uploading"`) | ✅ |
| E6 | `recommendation_table.html` | 96-119 | Empty state complet avec illustration + CTA | ✅ |

---

## 8. Performance perçue

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| P1 | `input.css` | 1 | Google Fonts import bloquant — `display=swap` atténue mais `@import` dans CSS est plus lent que `<link>` dans `<head>` | 🟡 |
| P2 | `lockout.html` | 10 | Charge Material Symbols depuis CDN Google — 2e police externe en plus d'Inter/Manrope/JetBrains | 🟡 |
| P3 | `base.html` | 70-71 | Alpine.js en `defer` — bien, mais sentinel.js aussi en `defer`, l'ordre d'exécution est garanti | ✅ |
| P4 | `base.html` | 12 | `output.css?v=17` — cache-busting manuel, bonne pratique | ✅ |
| P5 | `submit_evidence_modal.html` | 201-258 | Upload en séquentiel (for loop) au lieu de parallèle (Promise.all) | 🟡 |
| P6 | Global | — | 72 KB de CSS compilé (`output.css`) — correct pour une app Tailwind | ✅ |

---

## 9. Action > Décoration

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| ACT1 | `login.html` | 19-47 | **Orbes décoratifs floues + points** — 40 lignes de pure décoration, 2 requêtes réseau implicites (logo en watermark 800px) | 🟠 |
| ACT2 | `login.html` | 65-67 | `border-top:3px solid #E87722` — belle signature, mais devrait être une classe | 🟢 |
| ACT3 | `close_confirm_modal.html` | 8-25 | L'icône + message d'avertissement prend 50% du contenu — bon ratio action/info | ✅ |
| ACT4 | `assign_dm_modal.html` | 35-47 | Bandeau "Aucun DM" utile mais prend beaucoup de place | 🟢 |
| ACT5 | `stepper_slideover.html` | 78-79, 115-116, 138-139, 182-183 | Bandeaux d'info par étape avec émojis (📋🔍📝📦) — bonne pratique pédagogique | ✅ |

---

## 10. Cohérence visuelle

### Problèmes majeurs

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| V1 | `delete_confirm.html` | 18-19 | Boutons en classes manuelles `rounded-xl px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200` au lieu de `btn btn-secondary` | 🟠 |
| V2 | `delete_confirm.html` | 19 | Bouton "Confirmer la suppression" en `bg-red-600 hover:bg-red-700` au lieu de `btn btn-danger` | 🟠 |
| V3 | `recommendation_list.html` | 21-22 | Bouton "Nouvelle recommandation" en `bg-[#E87722] hover:bg-[#C9631A]` au lieu de `btn btn-primary` | 🟠 |
| V4 | `recommendation_list.html` | 112-113 | Bouton "Créer ma première recommandation" idem — hex en dur | 🟠 |
| V5 | `assign_dm_modal.html` | 105 | Bouton "Confirmer l'assignation" en gradient bleu custom — casse l'unité design | 🟠 |
| V6 | `assign_dm_modal.html` | 96-97 | Bouton "Annuler" en classes manuelles au lieu de `btn btn-secondary` | 🟠 |
| V7 | `provisioning_reject_modal.html` | 56-58 | Bouton "Annuler" en `rounded-lg px-4 py-2 text-sm font-medium text-text-secondary border border-border-subtle` — **encore un style différent** | 🟠 |
| V8 | `provisioning_reject_modal.html` | 62-63 | Bouton "Confirmer" en `bg-status-rejected` — utilise un token différent des autres modales (`btn btn-danger`) | 🟠 |
| V9 | `delegate_etp_modal.html` | 73-109 | Cartes de sélection radio avec icônes — design unique dans l'app, aucune autre modale ne fait ça | 🟢 |
| V10 | Global | — | 3 modèles de modales différents : overlay + backdrop (standard), inline sans overlay (`close_confirm_modal.html`), et auto-fermeture (`provisioning_reject_modal.html`) | 🔴 |

### Modèles de modales (comparaison)

| Fichier | Structure | Backdrop | Fermeture | Boutons |
|---------|-----------|----------|-----------|---------|
| `delete_confirm.html` | `fixed inset-0 z-[60]` | ✅ `bg-gray-900/50 backdrop-blur-sm` | `@click="deleteOpen=false"` | Classes manuelles |
| `close_confirm_modal.html` | Div inline seulement | ❌ **Aucun** | N/A (pas une modale) | `btn btn-secondary` / `btn btn-primary` |
| `assign_dm_modal.html` | Div dans slot parent | Géré par parent | `@click="assignModalOpen=false"` | Mix (manuels + gradient) |
| `reject_audit_modal.html` | Div dans slot parent | Géré par parent | `@click="rejectAuditModalOpen=false"` | `btn btn-secondary` / `btn btn-danger` |
| `approve_evidence_modal.html` | Div dans slot parent | Géré par parent | `@click="approveModalOpen=false"` | `btn btn-secondary` / `btn btn-primary` |
| `extension_review_modal.html` | Div dans slot parent | Géré par parent | `@click="extensionReviewModalOpen=false"` | `btn btn-secondary` / `btn btn-primary` ou `btn btn-danger` |
| `provisioning_reject_modal.html` | Auto-portée `fixed inset-0 z-50` | ✅ `bg-on-surface/40 backdrop-blur-sm` | `$el.remove()` / Escape | Classes manuelles |
| `recommendation_list.html:154-176` | **Duplication** de `delete_confirm.html` | ✅ | `deleteOpen = false` | `btn btn-secondary` / `btn btn-danger` ✅ |

---

## 11. Centralisation des tokens

### Constat critique

Le design system Sentinel est **bien défini** dans `tailwind.config.js` (197 lignes, ~40 couleurs nommées, 7 font stacks, animations, ombres) et `input.css` (~50 variables HSL + classes custom). **Mais il n'est pas respecté.**

### Chiffres

| Métrique | Valeur |
|----------|--------|
| Styles inline | 430+ occurrences |
| Couleurs hexadécimales en dur | ~60 valeurs uniques |
| Fichiers avec inline styles | 22 templates sur 81 |
| `btn btn-primary` utilisé | 7 occurrences |
| Classes `bg-[#...]` en dur | 15+ occurrences |

### Pire contrevenants

| # | Fichier | Extrait |
|---|---------|---------|
| T1 | `login.html` (fichier entier) | 100% en inline styles — aucun token utilisé |
| T2 | `recommendation_detail.html` | 50+ styles inline : couleurs, bordures, polices |
| T3 | `recommendation_list.html` | Filtres et boutons en `bg-[#E87722]`, `border-[#D8CBBE]`, etc. |
| T4 | `recommendation_table.html` | Tableau entier en couleurs inline |
| T5 | `status_badge.html` | Composant central des statuts — 100% inline styles |
| T6 | `close_confirm_modal.html` | Couleurs inline + classes Tailwind mélangées |
| T7 | `closure_banner.html` | 100% inline styles |

### Exemple de code non tokenisé vs tokenisé

```html
<!-- Actuel (recommendation_list.html:21) -->
class="inline-flex items-center gap-2 rounded-xl bg-[#E87722] hover:bg-[#C9631A] active:bg-[#A8500F] px-5 py-2.5 text-sm font-semibold text-white"

<!-- Devrait être -->
class="btn btn-primary px-5 py-2.5"
```

---

## 12. Organisation layout/détail

### Problèmes

| # | Fichier | Ligne | Problème | Gravité |
|---|---------|-------|----------|---------|
| L1 | `recommendation_detail.html` | 347 | Grid en `display:grid;grid-template-columns:1fr 320px;` — 320px fixe, casse sur écran <900px | 🟠 |
| L2 | `recommendation_detail.html` | 314-343 | Grille 4 colonnes en `grid-cols-4` — bien mais pas de responsive (devient illisible sur tablette) | 🟡 |
| L3 | `stepper_slideover.html` | 146 | Slide-over stepper avec `top: 10%` — sur mobile, 10% du viewport = pas de différence visible | 🟡 |
| L4 | `external_shell.html` | 9-37 | Header externe différent de l'app shell — pas de sidebar, cohérent avec son usage | ✅ |
| L5 | `layouts/app_shell.html` | 5-17 | Layout sain : sidebar fixe + contenu scrollable + footer | ✅ |
| L6 | `topbar.html` | 51-58 | Dropdown notification avec `position: absolute` inline — pas de classe Tailwind pour ça | 🟡 |

---

## 13. Annexe : Problèmes par fichier

### `code/templates/base.html`
- **L76-77** : `data-message="{{ message }}"` dangereux si contient des guillemets → utiliser `{{ message|escapejs }}`
- **L44** : `hx-headers` exposé en HTML (CSRF token visible dans le source)

### `code/templates/auth/login.html`
- **100% inline styles** — page la moins tokenisée du projet
- **L19-47** : Orbes décoratives en `blur-[80px]` et `blur-[100px]` — lourd sur mobiles
- **L133-134** : Handlers JS inline `onfocus`/`onblur` — pas de `:focus-visible`
- **L55** : `font-display font-extrabold` — `font-display` est un token Tailwind, mais la taille `font-size:40px` est en inline

### `code/templates/layouts/app_shell.html`
- ✅ Propre, léger, bien structuré

### `code/templates/layouts/external_shell.html`
- **L15** : `text-muted-foreground` — ce token HSL existe-t-il ? OK, défini dans tailwind.config.js ligne 25

### `code/templates/partials/topbar.html`
- **L51-58** : Style inline pour le panel dropdown — devrait aller dans input.css
- **L96** : "Mon profil" / "Paramètres" désactivés avec `opacity-60 cursor-not-allowed` + "(Bientôt)" — bonne transparence UX

### `code/templates/partials/sidebar_*.html` (tous)
- ✅ Structure cohérente, même pattern graphique graphite, nommage homogène
- Liens morts (#) : voir section [Navigation rapide](#4-navigation-rapide)

### `code/templates/components/status_badge.html`
- **🔴 100% inline styles** — ce composant est utilisé dans `recommendation_table.html`, donc les couleurs statut sont dupliquées partout

### `code/templates/components/alert.html`
- ✅ Propre, utilise des classes Tailwind

### `code/templates/components/btn_primary.html`
- **L18** : `class="{% if full_width %}w-full{% endif %} btn btn-primary"` — bien conçu, mais inclut une flèche intérieure qui ne correspond pas à tous les usages

### `code/templates/components/kpi_card.html`
- ✅ Excellent composant — bien tokenisé avec accents, transitions, ombres

### `code/templates/components/forms/input_text.html`
- **L49** : `bg-surface-base` — peut poser problème si le fond général est `bg-background`

### `code/templates/workflow/recommendation_detail.html`
- **L7-10** : 15 variables Alpine — refactor possible en store dédié `$store.recoModals`
- **L40-80** : Badges de statut dupliquent `status_badge.html` en inline — à remplacer par `{% include "components/status_badge.html" with status=recommendation.status %}`
- **L347** : Grid inline non-responsive
- **L587** : `x-init` sur la progress bar

### `code/templates/workflow/recommendation_list.html`
- **L21-22, 112-113** : Boutons en hex inline
- **L154-176** : Modale de suppression dupliquée (copie de `delete_confirm.html`)
- **L178-191** : Scripts HTMX listeners bien placés

### `code/templates/workflow/partials/delete_confirm.html`
- **L18-19** : Boutons en classes manuelles
- **L3** : `@open-delete.window` — bien conçu pour Event Driven

### `code/templates/workflow/partials/close_confirm_modal.html`
- **🔴 Ce n'est pas une modale** — pas d'overlay, pas de backdrop, apparition inline
- **L22** : Utilise `⚠️` émoji dans le texte — fragile, dépend de la police système

### `code/templates/workflow/partials/assign_dm_modal.html`
- **L105** : Bouton submit en gradient bleu — **casse le design system**

### `code/templates/workflow/partials/submit_evidence_modal.html`
- **L327** : Fonction `evidenceDraft()` en script embarqué — 145 lignes de JS dans un template Django

### `code/templates/workflow/partials/provisioning_reject_modal.html`
- **L12** : `bg-on-surface/40` — token Material Design qui n'existe pas dans le projet (tailwind.config.js ligne 92 `on-surface`)
- Style de boutons complètement différent des autres modales

### `code/templates/admin_it/org_unit_types/_form_modal.html`
- ✅ Propre, bien structuré, utilise `btn btn-secondary` / `btn btn-primary`

### `code/templates/axes/lockout.html`
- **L10** : Charge Material Symbols depuis CDN Google — 2e police externe
- **L11-16** : Style block avec variables de fonte non standard
- Utilise `bg-error`, `text-error`, `bg-surface`, `font-headline` — tokens Material Design mélangés aux tokens Sentinel

### `code/static/js/sentinel.js`
- ✅ Propre, bien commenté, bien géré
- **L8** : `setTimeout` 4000ms pour les notifications — court pour les messages longs
- MutationObserver pour TomSelect ✅

### `code/static/css/input.css`
- **L1** : `@import` Google Fonts — préférer `<link>` dans `<head>` pour le caching
- **L56-66** : Dark mode minimal (6 vars seulement) — beaucoup de couleurs ne sont pas couvertes
- ✅ Excellent système de tokens HSL et classes utilitaires

### `code/tailwind.config.js`
- **L160** : `headline: ["Plus Jakarta Sans", "sans-serif"]` — **cette police n'est JAMAIS chargée**
- **L85-132** : ~50 tokens Material Design/Stitch mélangés aux tokens Sentinel — dead code ou legacy ?

---

## Bugs & Anomalies techniques

| # | Fichier | Ligne | Description | Gravité |
|---|---------|-------|-------------|---------|
| B1 | `audit_log_drawer.html` | 63 | `bg-gray-150` — classe Tailwind invalide | 🔴 |
| B2 | `provisioning_reject_modal.html` | 12 | `bg-on-surface/40` — token inexistant | 🔴 |
| B3 | `tailwind.config.js` | 160 | `Plus Jakarta Sans` jamais chargée — police orpheline | 🟠 |
| B4 | `close_confirm_modal.html` | 4 | Modale sans overlay — l'utilisateur ne peut pas cliquer à côté pour fermer | 🟠 |
| B5 | `recommendation_list.html` | 154-176 | Code de modale de suppression dupliqué depuis `delete_confirm.html` | 🟠 |
| B6 | `recommendation_detail.html` | 40-80 | Badges statut dupliquent `status_badge.html` — 2 sources de vérité | 🟠 |
| B7 | `login.html` | 90-105 | Bloc d'erreur avec `animate-shake` mais pas d'`aria-live="assertive"` — invisible pour lecteurs d'écran | 🟠 |
| B8 | `dashboard/audit_dashboard.html` | 23, 241-246 | Typos : "Creees" → "Créées", "cloture" → "clôture", "cloturees" → "clôturées" | 🟡 |
| B9 | `submit_evidence_modal.html` | 22-23, 66-70 | `x-init` pour les progress bars — non réactif | 🟡 |

---

## Recommandations prioritaires

### 🔴 Immédiat (1-2 jours)

1. **Unifier les modèles de modales** — créer un composant `modal_base.html` avec overlay/backdrop/fermeture Escape, et l'utiliser partout
2. **Supprimer la duplication de modale de suppression** — `recommendation_list.html:154-176` doit utiliser `delete_confirm.html` via include
3. **Corriger `close_confirm_modal.html`** — ajouter un overlay avec backdrop
4. **Harmoniser les boutons** — remplacer tous les `bg-[#...]` et boutons manuels par `btn btn-primary`, `btn btn-secondary`, `btn btn-danger`
5. **Remplacer les badges inline de `recommendation_detail.html`** par `{% include "components/status_badge.html" %}`

### 🟠 Court terme (1 semaine)

6. **Supprimer les 430+ styles inline** — migrer vers les tokens Tailwind/classes custom
7. **Charger Plus Jakarta Sans** depuis Google Fonts ou la retirer du config
8. **Rendre les lignes du tableau accessibles au clavier** (`tabindex`, `@keydown.enter`)
9. **Corriger `bg-gray-150` et `bg-on-surface/40`** — classes invalides
10. **Ajouter `aria-hidden="true"` sur les SVG décoratifs**
11. **Remplacer `x-init` sur les progress bars par `x-effect` ou `:style`**

### 🟡 Moyen terme (2 semaines)

12. **Nettoyer les tokens Material Design legacy** de `tailwind.config.js`
13. **Refactorer les 15 variables Alpine** de `recommendation_detail.html` en un store dédié
14. **Ajouter la validation client** au stepper avant chaque étape
15. **Paralleliser les uploads** dans `submit_evidence_modal.html` avec `Promise.all`
16. **Corriger les typos françaises** dans les dashboards

---

## Fichiers modèles (bonnes pratiques à suivre)

Ces fichiers respectent le mieux le design system :

| Fichier | Pourquoi |
|---------|----------|
| `components/kpi_card.html` | Tokenisé, transitions, responsive |
| `components/alert.html` | Classes Tailwind uniquement, rôles ARIA |
| `admin_it/org_unit_types/_form_modal.html` | Structure modale propre, boutons tokenisés |
| `workflow/partials/extension_review_modal.html` | Gère 2 états (approve/reject) proprement |
| `workflow/partials/delegate_etp_modal.html` | Radio cards bien conçues, Alpine intégré |
| `static/js/sentinel.js` | Code JS propre, bien commenté, robuste |

---

*Rapport généré par audit statique ligne par ligne — 81 templates, 4 JS, 3 CSS, 1 config Tailwind.*
