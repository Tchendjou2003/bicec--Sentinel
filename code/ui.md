# Rapport d'Audit UI/UX — Sentinel v2.1.0

> **Date** : 16 mai 2026
> **Périmètre** : Templates Django, composants, layouts, design system Tailwind
> **Méthodologie** : Analyse statique du code source contre 10 critères UX professionnels

---

## Synthèse exécutive

| Critère | Score | État |
|---------|-------|------|
| 1. Hiérarchie visuelle | 5/10 | À améliorer |
| 2. Charge cognitive | 4/10 | Problématique |
| 3. Navigation rapide | 6/10 | Correct |
| 4. Feedback immédiat | 5/10 | Partiel |
| 5. Accessibilité | 3/10 | Critique |
| 6. Gestion des états | 5/10 | Partiel |
| 7. Performance perçue | 3/10 | Insuffisant |
| 8. Action > Décoration | 4/10 | Problématique |
| 9. Cohérence visuelle | 4/10 | Fragmentée |
| 10. Centralisation design tokens | 2/10 | Critique |
| 11. Organisation layout détail | 3/10 | À refondre |
| **GLOBAL** | **4.0/10** | **Refonte nécessaire** |

---

## 1. Hiérarchie Visuelle — Montrer ce qui est important

### Problèmes identifiés

**1.1. Prolifération de tailles de titre**
- `home.html` : `text-4xl` pour une page de test
- `login.html` : `text-4xl sm:text-5xl` — excessif pour un formulaire
- `admin_it/dashboard.html` : `text-2xl`
- `workflow/recommendation_list.html` : `text-2xl`
- **Aucune échelle typographique cohérente** entre les pages

**1.2. Couleurs de texte incohérentes**
- Certains templates utilisent `text-gray-900`, d'autres `text-sentinel-brown`, d'autres `text-on-surface`, d'autres `text-foreground`
- **4 systèmes de couleurs coexistent** dans le même projet :
  - Tailwind natif (`gray-500`, `gray-900`...)
  - Sentinel custom (`sentinel-brown`, `sentinel-orange`)
  - Material Design tokens (`on-surface`, `on-surface-variant`...)
  - shadcn-like tokens (`foreground`, `muted-foreground`...)

**1.3. KPI cards vs dashboard admin — deux designs différents**
- `components/kpi_card.html` : utilise le design system tokens (`bg-card`, `text-foreground`, `border`)
- `admin_it/dashboard.html` : utilise des classes ad-hoc (`bg-white`, `text-gray-900`, `border-gray-100`)
- **Le composant KPI réutilisable n'est pas utilisé dans le dashboard admin**

### Recommandations

```
[ ] Définir une échelle typographique unique :
    - Page title : text-2xl font-bold (partout)
    - Section title : text-lg font-semibold
    - Card title : text-sm font-semibold
    - Body : text-sm
    - Caption : text-xs

[ ] Unifier le système de couleurs — supprimer les tokens Material Design
    inutilisés et ne garder que :
    - Sentinel brand (sentinel-orange, sentinel-brown)
    - Semantic tokens (success, warning, destructive, info)
    - Surface tokens (background, card, muted)

[ ] Remplacer les KPI cards du dashboard admin par le composant
    components/kpi_card.html existant
```

---

## 2. Réduire la Charge Cognitive

### Problèmes identifiés

**2.1. 7 sidebars différentes avec des designs inconsistants**

| Sidebar | Largeur | Style | État actif |
|---------|---------|-------|------------|
| `sidebar_base.html` | w-64 | bg-sidebar, tokens | border-l-2 |
| `sidebar_default.html` | w-72 | bg-white, gray-100 | N/A |
| `sidebar_audit.html` | w-64 | bg-white, gray-100 | gradient + shadow |
| `sidebar_audit_ext.html` | w-72 | bg-white, gray-100 | gradient + shadow-lg |
| `sidebar_admin.html` | w-72 | bg-white, gray-100 | gradient + shadow-lg |
| `sidebar_dg.html` | w-72 | bg-white, gray-100 | gradient + shadow-lg |
| `sidebar_dm.html` | w-72 | bg-white, gray-100 | gradient + shadow-lg |
| `sidebar_etp.html` | w-72 | bg-white, gray-100 | gradient + shadow-lg |

**Problème majeur** : `sidebar_base.html` utilise un design system (tokens semantic) tandis que **toutes les autres** utilisent un design ad-hoc (bg-white, gray-100, gradients). Deux systèmes parallèles.

**2.2. URLs en dur vs `url` template tag**
- `sidebar_audit.html` : URLs en dur (`/audit/`, `/audit/recommandations/`)
- `sidebar_admin.html` : utilise `{% url 'auth:admin-dashboard' %}`
- **Mélange de patterns** — maintenance impossible

**2.3. Filtres avec 3 approches différentes**
- `admin_it/user_list.html` : liens `<a>` avec rechargement page
- `habilitation/user_list.html` : liens `<a>` avec rechargement page (design différent)
- `workflow/recommendation_list.html` : selects + search avec HTMX (le seul avec filtrage dynamique)

**2.4. Statuts affichés de 3 manières différentes**
- `components/status_badge.html` : composant réutilisable avec dot indicator
- `workflow/recommendation_detail.html` : classes inline dupliquées
- `workflow/partials/recommendation_table.html` : classes inline dupliquées (encore différentes)

### Recommandations

```
[ ] Unifier TOUTES les sidebars sur un seul composant paramétrable
    (sidebar_base.html est le bon modèle mais incomplet)

[ ] Remplacer toutes les URLs en dur par {% url %}

[ ] Standardiser les filtres : adopter le pattern HTMX du workflow
    pour toutes les listes

[ ] Utiliser components/status_badge.html PARTOUT au lieu de
    dupliquer les classes de statut
```

---

## 3. Navigation Rapide — Peu d'étapes pour atteindre l'objectif

### Points positifs
- Sidebars avec navigation directe par profil
- Breadcrumbs présents sur les pages de détail (`recommendation_detail.html`, `user_create.html`)
- Actions rapides sur le dashboard admin

### Problèmes identifiés

**3.1. Pas de navigation clavier**
- Aucun shortcut clavier implémenté (le `Ctrl+K` dans la topbar est visuel uniquement — pas de fonctionnalité)
- Pas de focus trap dans les modales
- Pas de `tabindex` stratégique

**3.2. Recherche non fonctionnelle**
- La barre de recherche dans `topbar.html` n'a pas de `hx-get` ni de `form` — c'est un input orphelin

**3.3. Pas de "recent items" ou "favoris"**
- L'utilisateur doit toujours repasser par la sidebar pour naviguer

**3.4. Pagination basique**
- Pas de pagination numérotée, juste "Précédent / Suivant"
- Pas de "items per page" selector

### Recommandations

```
[ ] Implémenter la recherche globale (Ctrl+K) avec HTMX
[ ] Ajouter des breadcrumbs sur TOUTES les pages (pas seulement détail)
[ ] Ajouter une pagination numérotée avec selector "par page"
[ ] Implémenter les keyboard shortcuts dans Alpine.js store
```

---

## 4. Feedback Immédiat

### Points positifs
- Système de toasts Alpine.js fonctionnel dans `base.html`
- Transitions HTMX avec `hx-swap`
- États hover sur les boutons et liens

### Problèmes identifiés

**4.1. Pas d'indicateur de loading HTMX**
- Aucun `htmx:indicator` configuré — l'utilisateur ne voit pas quand une requête est en cours
- Pas de spinner, pas de skeleton, pas de disabled state pendant les requêtes

**4.2. Pas de feedback visuel sur les selects de filtre HTMX**
- Quand un filtre change dans `recommendation_list.html`, rien n'indique que le chargement est en cours

**4.3. Modales sans état de chargement**
- Les slide-overs HTMX (`stepper-container`) affichent un contenu vide pendant le chargement

**4.4. Boutons de suppression sans confirmation visuelle du résultat**
- Le bouton delete envoie une requête mais ne montre pas de toast de confirmation

### Recommandations

```
[ ] Ajouter htmx:indicator global avec spinner dans la topbar
[ ] Ajouter un état "loading" sur les selects de filtre
[ ] Ajouter un skeleton loader dans les conteneurs HTMX vides
[ ] Dispatch un toast après chaque action HTMX (create, update, delete)
```

---

## 5. Accessibilité — Critique

### Problèmes identifiés

**5.1. `x-cloak` non appliqué systématiquement**
- Les éléments Alpine.js sont visibles avant l'initialisation (flash de contenu)
- `sidebar_base.html`, `sidebar_default.html`, etc. utilisent `style="display:none"` mais sans `x-cloak`

**5.2. Contraste insuffisant**
- `text-gray-400` sur fond blanc : ratio ~2.8:1 (minimum requis : 4.5:1)
- `text-muted-foreground` sur fond card : probablement sous le seuil WCAG AA
- Les placeholders `text-gray-400` sont quasi illisibles

**5.3. Éléments interactifs sans labels**
- Bouton de recherche dans topbar : pas de `aria-label`
- Bouton de notification : pas de `aria-label` (seulement le toggle sidebar)
- Les liens de pagination n'ont pas de `aria-label`

**5.4. Modales sans gestion ARIA**
- Pas de `role="dialog"` sur les modales
- Pas de `aria-modal="true"`
- Pas de `aria-labelledby` pour les titres de modales
- Pas de focus trap — le focus peut sortir de la modale

**5.5. Formulaires sans association label/field**
- `admin_it/user_create.html` : les labels utilisent `for` mais les champs Django ne rendent pas toujours l'id correspondant
- Pas de `aria-describedby` pour les messages d'erreur
- Pas de `aria-invalid` sur les champs en erreur

**5.6. Police externe chargée via HTTP**
- `login.html` et `lockout.html` chargent Google Fonts via `<link>` dans `extra_css` — bloquant pour le rendu
- Material Symbols chargé uniquement sur certaines pages (incohérent)

**5.7. Pas de skip link**
- Aucun "skip to main content" link pour les utilisateurs de screen reader

### Recommandations

```
[ ] Ajouter x-cloak sur TOUS les éléments Alpine.js
[ ] Remplacer text-gray-400 par text-gray-500 minimum
[ ] Ajouter aria-label sur tous les boutons icon-only
[ ] Ajouter role="dialog" aria-modal="true" aria-labelledby
    sur toutes les modales
[ ] Implémenter un focus trap dans les modales (Alpine.js)
[ ] Ajouter un skip-to-content link dans base.html
[ ] Charger les polices de manière cohérente (input.css ou partout)
[ ] Ajouter aria-invalid et aria-describedby sur les champs en erreur
```

---

## 6. Gestion des États

### Problèmes identifiés

**6.1. Pas de skeleton loading**
- Aucune page n'implémente de skeleton screens
- Les tableaux HTMX passent de "contenu" à "vide" à "nouveau contenu" sans transition

**6.2. Empty states inconsistants**
- `recommendation_table.html` : empty state élaboré avec icône + CTA
- `admin_it/user_list.html` : simple texte "Aucun utilisateur trouvé"
- `habilitation/user_list.html` : simple texte "Aucun utilisateur trouvé"

**6.3. Pas d'état d'erreur réseau**
- Si HTMX échoue (500, timeout), l'utilisateur voit un conteneur vide
- Pas de gestion `htmx:responseError` ou `htmx:timeout`

**6.4. États de formulaire incomplets**
- `admin_it/user_create.html` : pas de disabled state sur le bouton submit pendant le POST
- Pas de validation côté client visible

**6.5. Alpine.js store non initialisé dans base.html**
- Le code `$store.sentinel.notifications` suppose un store initialisé mais
  l'initialisation n'est pas visible dans les templates lus

### Recommandations

```
[ ] Créer un composant skeleton_table.html et skeleton_card.html
[ ] Unifier les empty states avec un composant components/empty_state.html
[ ] Ajouter un gestionnaire global htmx:responseError pour afficher
    un toast d'erreur
[ ] Ajouter un état loading/disabled sur les boutons de submit
[ ] Vérifier l'initialisation du store Alpine.js sentinel
```

---

## 7. Performance Perçue

### Problèmes identifiés

**7.1. Pas de lazy loading**
- Toutes les images (`logo.jpeg`) sont chargées immédiatement
- Pas de `loading="lazy"` sur les images hors viewport

**7.2. Pas de pagination côté serveur visible**
- Les listes utilisent la pagination Django mais sans indication de chargement progressif

**7.3. CSS potentiellement lourd**
- `output.css` : Tailwind compile TOUTES les classes — pas de purge visible
- `input.css` importe 3 Google Fonts (Inter, Manrope, JetBrains Mono) + login importe Inter + Jakarta Sans en double

**7.4. Fonts chargées de manière incohérente**
- `input.css` : Inter, Manrope, JetBrains Mono
- `login.html` : Material Symbols + Inter + Jakarta Sans (en double !)
- `lockout.html` : Material Symbols seul
- **Inter est chargé 2 fois**, Jakarta Sans uniquement sur login

**7.5. Pas de cache-busting cohérent**
- `base.html` : `output.css?v=2` — version hardcodée
- Les fichiers JS n'ont pas de cache-busting

### Recommandations

```
[ ] Ajouter loading="lazy" sur toutes les images non-critiques
[ ] Supprimer les doublons de font imports (login.html)
[ ] Charger Material Symbols dans input.css ou dans base.html,
    pas dans des templates individuels
[ ] Implémenter un système de cache-busting automatique
[ ] Vérifier que Tailwind purge correctement les classes inutilisées
```

---

## 8. Prioriser l'Action plutôt que la Décoration

### Problèmes identifiés

**8.1. Gradients excessifs**
- **Tous les boutons actifs de sidebar** utilisent `bg-gradient-to-r from-sentinel-orange to-[#C9631A]`
- Les boutons primaires utilisent aussi ce gradient
- `login.html` : bouton avec `bg-gradient-to-br from-primary-container to-primary`
- **Le gradient est utilisé partout** — il perd son impact visuel

**8.2. Shadows excessives**
- `shadow-lg shadow-orange-500/30` sur les boutons de sidebar actifs
- `shadow-2xl` sur les modales
- `shadow-[0_4px_20px_...]` custom sur login
- `shadow-premium-sm`, `shadow-premium-md`, `shadow-premium-lg`, `shadow-glow` — 4 niveaux de shadow custom

**8.3. Login page surchargée**
- 3 orbs animés avec blur-3xl
- Watermark logo en background
- 2 grilles de points décoratifs
- Ambient background lighting
- **C'est la page la plus décorative** alors que c'est une application métier bancaire

**8.4. Animations inutiles**
- `hover:-translate-y-0.5` sur presque tous les boutons
- `group-hover:translate-x-0.5` sur btn_primary
- `animate-shake` sur les alertes error
- `animate-pulse-slow` sur le badge de notification
- `animate-fade-in` sur le main content de chaque page
- `animate-card-in` disponible mais pas utilisé

**8.5. Rounded-xl / rounded-2xl / rounded-3xl mélangés**
- Pas de cohérence sur les border-radius
- Certains éléments utilisent `rounded-lg`, d'autres `rounded-xl`, d'autres `rounded-2xl`

### Recommandations

```
[ ] Réserver le gradient orange UNIQUEMENT au CTA principal de chaque page
[ ] Utiliser un flat color pour l'état actif des sidebars
[ ] Simplifier la page login : supprimer les orbs, watermark, dots
[ ] Réduire les animations à : fade-in sur les pages, rien sur les boutons
[ ] Standardiser les border-radius :
    - Cards : rounded-lg
    - Buttons : rounded-lg
    - Modals : rounded-xl
    - Badges : rounded-full
```

---

## 9. Cohérence Visuelle — Le problème central

### 9.1. Trois systèmes de design coexistent

| Système | Où utilisé | Tokens |
|---------|-----------|--------|
| **Material Design** | login.html, lockout.html | on-surface, surface-container, error-container... |
| **shadcn-like** | topbar, footer, kpi_card, sidebar_base, external_shell | foreground, muted, card, border... |
| **Ad-hoc gray** | TOUTES les autres pages | gray-50, gray-100, gray-900, white... |

### 9.2. Incohérences spécifiques

**Cards** :
- `bg-white border-gray-100 shadow-sm` (majorité des pages)
- `bg-card border-border/50 shadow-sm` (external, kpi_card)
- `bg-surface-container-lowest` (login)

**Boutons primaires** :
- `bg-gradient-to-r from-sentinel-orange to-[#C9631A]` (workflow, admin)
- `bg-sentinel-orange hover:bg-sentinel-orange-dark` (btn_primary component, home)
- `bg-gradient-to-br from-primary-container to-primary` (login)

**Inputs** :
- `border-gray-200 focus:border-sentinel-orange` (workflow filters)
- `border-outline-variant/50 focus:ring-primary` (login)
- `border-border-subtle focus:ring-sentinel-orange` (form components)

**Typography** :
- `font-heading` utilisé irrégulièrement
- `font-headline` uniquement sur login/lockout
- `font-bold`, `font-semibold`, `font-extrabold` mélangés sans règle

### 9.3. Espacement incohérent

| Élément | Padding utilisé |
|---------|----------------|
| Cards workflow | p-5 |
| Cards admin dashboard | p-6 |
| Cards habilitation | pas de card wrapper |
| Modales | p-6 |
| Login card | p-8 sm:p-10 |

---

## 10. Architecture des Templates

### Points positifs
- Bonne séparation `components/`, `layouts/`, `partials/`
- Utilisation de HTMX pour les interactions dynamiques
- Alpine.js pour la réactivité côté client
- Composants réutilisables bien documentés (comments)

### Problèmes structurels

**10.1. `base.html` trop minimal**
- Ne définit pas de navbar, footer, sidebar blocks
- Les pages auth utilisent `{% block navbar %}{% endblock %}` qui n'existe pas dans base.html

**10.2. `app_shell.html` dépend d'un context processor**
- `sidebar_template|default:"partials/sidebar_default.html"` — variable magique
- Pas de fallback si le context processor échoue

**10.3. Pas de macro/template tag custom**
- Tout passe par `{% include %}` avec des variables — pas de validation de type
- Les composants pourraient être des template tags Django pour plus de robustesse

**10.4. Le composant `sidebar_base.html` n'est utilisé nulle part**
- C'est le seul qui utilise le design system tokens
- Toutes les sidebars réelles sont des fichiers séparés avec du code dupliqué

---

---

## 11. Analyse Approfondie — Page Détail Recommandation

### 11.1. Taille et organisation des cards

**Layout actuel** : Grid `lg:grid-cols-5` avec split 60/40 (`lg:col-span-3` / `lg:col-span-2`)

**Colonne gauche (60%) — 4 cards de hauteur variable :**

| Card | Contenu | Hauteur estimée |
|------|---------|-----------------|
| Contexte Mission | 6 champs en grille 2 colonnes | ~200px |
| Observations | Paragraphe texte libre | Variable (30-200px) |
| Texte recommandation | Paragraphe texte libre | Variable (50-300px) |
| Dossiers en anomalies | Paragraphe conditionnel | Variable |

**Colonne droite (40%) — 4 cards empilées :**

| Card | Contenu | Hauteur estimée |
|------|---------|-----------------|
| Avancement | Barre de progression + 2 dates | ~100px |
| Livrables attendus | Liste variable (0-N items) | Variable (60-400px) |
| Historique | Timeline variable (0-N logs) | Variable (60-600px) |
| Informations | 3-4 lignes metadata | ~130px |

**Problèmes identifiés :**

**11.1.1. Déséquilibre vertical massif**
- La colonne gauche contient le contenu textuel lourd (observations + description = potentiellement 500px+)
- La colonne droite contient des widgets courts (avancement = 100px, metadata = 130px)
- **Résultat** : la colonne droite se retrouve avec un vide énorme en bas quand la timeline est courte, ou déborde quand elle est longue
- Les cards n'ont **aucune hauteur minimale ou fixe** — tout est `space-y-5` (gap de 20px) sans contrôle de proportion

**11.1.2. Pas de symétrie visuelle**
- Les 8 cards n'ont aucune relation de taille entre elles
- Aucune card ne s'aligne horizontalement avec une card de l'autre colonne
- L'œil ne trouve pas de rythme vertical — chaque card a un padding `p-5` mais des contenus de tailles radicalement différentes

**11.1.3. Le split 60/40 est arbitraire**
- Sur un écran 1440px : gauche = ~820px, droite = ~520px
- La colonne droite est **trop étroite** pour la timeline qui a besoin de lisibilité
- La colonne gauche est **trop large** pour des champs de formulaire en grille 2 colonnes

**11.1.4. Recommandation de réorganisation**

```
PROPOSITION — Layout en 3 zones au lieu de 2 colonnes :

┌─────────────────────────────────────────────────────────┐
│  Breadcrumb + Barre d'actions sticky (existant)          │
├──────────────────────────┬──────────────────────────────┤
│  ZONE A : Identité (fixe) │  ZONE B : Avancement (fixe)  │
│  Contexte Mission         │  Barre de progression        │
│  + Métadonnées combinées  │  + Livrables                 │
│  [Hauteur fixe ~280px]    │  [Hauteur fixe ~280px]       │
├──────────────────────────┴──────────────────────────────┤
│  ZONE C : Contenu principal (pleine largeur)             │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Observations         │  │ Texte recommandation      │  │
│  │ [min-h-32]           │  │ [min-h-48]               │  │
│  └─────────────────────┘  └──────────────────────────┘  │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Dossiers anomalies   │  │ Historique / Timeline     │  │
│  │ [min-h-24]           │  │ [min-h-48, scrollable]   │  │
│  └─────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

Règles :
- Zone A et B : hauteur égale, alignées horizontalement
- Zone C : grille 2 colonnes égales (grid-cols-2)
- Chaque card a un min-h défini pour garantir l'alignement
- La timeline a un max-h avec overflow-y-auto pour ne pas casser le layout
```

### 11.2. Éléments codés en dur sur la page détail

**Textes hardcoded (non-i18n, non-centralisés) :**

| Ligne | Texte | Type |
|-------|-------|------|
| 102 | `Contexte Mission` | Titre de section |
| 106 | `Date de la mission` | Label de champ |
| 110 | `Source` | Label de champ |
| 114 | `Libellé de la mission` | Label de champ |
| 118 | `Direction contrôlée` | Label de champ |
| 122 | `Direction concernée` | Label de champ |
| 126 | `Criticité` | Label de champ |
| 148 | `Observations` | Titre de section |
| 150 | `Aucune observation.` | Texte fallback |
| 159 | `Texte de la recommandation` | Titre de section |
| 171 | `Dossiers en anomalies` | Titre de section |
| 183 | `Avancement` | Titre de section |
| 191 | `Échéance :` | Label inline |
| 192 | `Orig. :` | Label inline |
| 202 | `Livrables attendus` | Titre de section |
| 203 | `élément` + pluralize | Texte dynamique partiel |
| 223 | `Aucun livrable défini.` | Texte fallback |
| 233 | `Historique` | Titre de section |
| 270 | `Aucun historique.` | Texte fallback |
| 276 | `Informations` | Titre de section |
| 279 | `Créé par` | Label de champ |
| 283 | `Créé le` | Label de champ |
| 287 | `Modifié le` | Label de champ |
| 292 | `DM assigné` | Label de champ |
| 35 | `En retard` | Badge texte |
| 54 | `Assigner` | Bouton (x2) |
| 57 | `Veuillez d'abord renseigner la Direction concernée` | Tooltip |
| 74 | `Modifier` | Bouton |
| 84 | `Supprimer` | Bouton |
| 334 | `Supprimer la recommandation` | Titre modale |
| 335 | `Réf. :` | Label modale |
| 338 | `Cette action est réversible...` | Description modale |
| 340 | `Annuler` | Bouton modale |
| 341 | `Confirmer` | Bouton modale |

**Total : ~35 textes codés en dur** — aucun ne passe par un système de traduction ou de constantes.

**SVG inline hardcodés :**
- **18 SVGs inline** directement dans le template (icônes de sections, boutons, timeline)
- Aucun n'est extrait dans un composant ou un sprite SVG
- Chaque SVG est répété à chaque utilisation (ex: l'icône calendrier apparaît dans le breadcrumb ET dans le header de card)

**Classes CSS dupliquées sur chaque card :**
```
bg-white rounded-xl border border-gray-100 shadow-sm p-5
```
Cette combinaison apparaît **8 fois** sur cette seule page. Aucune classe utilitaire composée (`@apply`) n'est définie.

---

## 12. Analyse Approfondie — Centralisation des Fonts et Couleurs

### 12.1. Fonts : dispersées et chargées en double

**Configuration centrale (`tailwind.config.js` lignes 108-115) :**
```js
fontFamily: {
  sans: ["Inter", "system-ui", "sans-serif"],
  mono: ["JetBrains Mono", "monospace"],
  headline: ["Plus Jakarta Sans", "sans-serif"],
  heading: ["Manrope", "sans-serif"],
  body: ["Inter", "sans-serif"],
  label: ["Inter", "sans-serif"],
}
```

**Chargement effectif des fonts :**

| Source | Fonts chargées | Où |
|--------|---------------|-----|
| `input.css` ligne 1 | Inter (300-700), Manrope (500-800), JetBrains Mono (400-500) | Global |
| `login.html` ligne 10-11 | Material Symbols + Inter (400-800) + Plus Jakarta Sans (500-800) | Login uniquement |
| `lockout.html` ligne 10 | Material Symbols | Lockout uniquement |

**Problèmes :**

1. **Inter chargé 2 fois** — une fois dans `input.css` (300-700), une fois dans `login.html` (400-800). Le navigateur télécharge 2 fichiers WOFF2 différents.
2. **Plus Jakarta Sans** (`font-headline`) n'est chargé que dans `login.html` — sur toutes les autres pages, `font-heading` utilise Manrope (chargé globalement) mais `font-headline` utilise Jakarta Sans **non chargé** → fallback système
3. **Material Symbols** chargé uniquement sur login/lockout — incohérent avec le reste de l'app qui utilise des SVG inline
4. **6 font families déclarées** dans Tailwind mais seulement 2 réellement utilisées de manière cohérente (`sans` = Inter, `heading` = Manrope)

**Verdict : DISPERSÉ** — Les fonts sont définies centralement dans `tailwind.config.js` mais chargées de manière fragmentée dans des templates individuels.

### 12.2. Couleurs : 4 systèmes parallèles, aucun n'est dominant

**Système 1 — Tailwind natif (le plus utilisé)**
- `gray-50`, `gray-100`, `gray-200`, `gray-400`, `gray-500`, `gray-600`, `gray-700`, `gray-900`
- `white`, `blue-50`, `blue-100`, `blue-600`, `blue-700`
- `amber-50`, `amber-100`, `amber-500`, `amber-600`, `amber-700`, `amber-800`
- `green-50`, `green-100`, `green-500`, `green-600`, `green-700`
- `red-50`, `red-100`, `red-500`, `red-600`, `red-700`
- `purple-50`, `purple-100`, `purple-600`, `purple-700`
- `indigo-100`, `indigo-600`, `indigo-700`
- `orange-50`, `orange-500`
- **341 occurrences** dans les templates (grep)
- **Utilisé dans** : workflow, admin_it, habilitation, tous les partials

**Système 2 — shadcn-like HSL tokens (défini dans input.css + tailwind.config.js)**
- `bg-background`, `text-foreground`, `bg-card`, `text-muted-foreground`
- `border-border`, `bg-muted`, `text-destructive`, `bg-success`
- **54 occurrences** dans les templates
- **Utilisé dans** : base.html, topbar, footer, kpi_card, sidebar_base, external_shell, external/dashboard

**Système 3 — Material Design tokens (Stitch)**
- `bg-surface`, `text-on-surface`, `bg-surface-container-lowest`
- `text-on-surface-variant`, `bg-error-container`, `text-on-error-container`
- `border-outline-variant`, `bg-surface-container-low`, `bg-surface-container-high`
- **37 occurrences** dans les templates
- **Utilisé dans** : login.html, lockout.html (uniquement)

**Système 4 — Sentinel custom + Surface palette**
- `bg-sentinel-orange`, `text-sentinel-brown`, `bg-surface-base`
- `text-text-primary`, `text-text-secondary`, `text-text-muted`
- `border-border-subtle`
- **~50 occurrences** estimées
- **Utilisé dans** : habilitation, form components, pending, sidebar par profil

**Cartographie de la dispersion par fichier :**

| Fichier | Système dominant | Systèmes secondaires |
|---------|-----------------|---------------------|
| `base.html` | shadcn | — |
| `topbar.html` | shadcn | — |
| `footer.html` | shadcn | — |
| `kpi_card.html` | shadcn | — |
| `sidebar_base.html` | shadcn | — |
| `external_shell.html` | shadcn | — |
| `external/dashboard.html` | shadcn | — |
| `login.html` | Material | — |
| `lockout.html` | Material | — |
| `auth/pending.html` | Sentinel custom | border-subtle |
| `workflow/recommendation_detail.html` | **gray natif** | — |
| `workflow/recommendation_list.html` | **gray natif** | — |
| `workflow/partials/recommendation_table.html` | **gray natif** | — |
| `workflow/partials/stepper_slideover.html` | **gray natif** | sentinel-orange |
| `workflow/partials/assign_dm_modal.html` | **gray natif** | — |
| `admin_it/dashboard.html` | **gray natif** | sentinel-orange |
| `admin_it/user_list.html` | **gray natif** | sentinel-orange |
| `admin_it/user_create.html` | **gray natif** | sentinel-orange |
| `habilitation/user_list.html` | **Sentinel custom** | border-subtle, gray |
| `habilitation/user_edit.html` | **Mixte** | border-subtle, surface-base, gray |
| `components/forms/input_text.html` | **Sentinel custom** | border-subtle, surface-base |
| `components/forms/input_password.html` | **Sentinel custom** | border-subtle, surface-base |
| `components/status_badge.html` | **shadcn** | — |
| `components/alert.html` | **Tailwind natif** | red-50, green-50... |
| `partials/sidebar_audit.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_admin.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_dg.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_dm.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_etp.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_default.html` | **gray natif** | sentinel-orange |
| `partials/sidebar_audit_ext.html` | **gray natif** | sentinel-orange |

**Verdict : EXTRÊMEMENT DISPERSÉ**

- `tailwind.config.js` définit ~70 couleurs custom (Sentinel brand + Material tokens + shadcn HSL)
- **Aucun template n'utilise exclusivement un seul système** (sauf les 7 fichiers shadcn-only)
- La page `recommendation_detail.html` (la plus importante) utilise **100% gray natif** — aucun token sémantique
- Les form components utilisent `text-primary`, `bg-surface-base`, `border-border-subtle` — un 4ème système
- **0 classes `@apply`** ne sont définies dans `input.css` pour composer des patterns récurrents

### 12.3. Ce qui EST bien centralisé

| Élément | Localisation | État |
|---------|-------------|------|
| CSS custom properties HSL | `input.css` lignes 13-54 | Bien structuré |
| Animations keyframes | `input.css` lignes 130-158 | Centralisé |
| Utility classes custom | `input.css` lignes 76-92 | Centralisé |
| Font families | `tailwind.config.js` lignes 108-115 | Centralisé |
| Border radius scale | `tailwind.config.js` ligne 116 | Centralisé |
| Shadow presets | `input.css` lignes 50-54 | Centralisé |

### 12.4. Ce qui N'EST PAS centralisé

| Élément | Problème |
|---------|----------|
| Couleurs de texte | 341 occurrences de `gray-*` hardcoded |
| Couleurs de fond | `bg-white` utilisé 50+ fois au lieu de `bg-card` |
| Couleurs de bordure | `border-gray-100`, `border-gray-200` au lieu de `border-border` |
| Couleurs sémantiques | `bg-red-100 text-red-700` au lieu de `bg-destructive/10 text-destructive` |
| SVG icons | 100+ SVG inline dupliqués, aucun sprite |
| Textes UI | 0 système i18n, 0 constantes |
| Espacements | `p-5`, `p-6`, `px-4`, `px-5` mélangés sans règle |
| Border radius | `rounded-lg`, `rounded-xl`, `rounded-2xl` mélangés |

---

## Plan d'Action Priorisé

### Phase 1 — Critique (semestre 1)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | Unifier le système de couleurs (supprimer Material + gray natif, garder shadcn-like) | Très haut | Moyen |
| 2 | Ajouter `x-cloak` + ARIA sur toutes les modales | Très haut | Faible |
| 3 | Remplacer les URLs en dur par `{% url %}` | Haut | Faible |
| 4 | Utiliser `status_badge.html` partout | Haut | Faible |
| 5 | Ajouter htmx:indicator global | Haut | Faible |
| 6 | Créer des classes `@apply` pour les patterns récurrents (cards, boutons, inputs) | Très haut | Faible |
| 7 | Refondre le layout détail recommandation en 3 zones symétriques | Haut | Moyen |
| 8 | Centraliser le chargement des fonts (supprimer doublons login.html) | Haut | Faible |

### Phase 2 — Important (semestre 2)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 6 | Unifier toutes les sidebars en un composant paramétrable | Très haut | Moyen |
| 7 | Créer des skeleton loading components | Haut | Moyen |
| 8 | Standardiser les empty states | Moyen | Faible |
| 9 | Simplifier la page login (supprimer décorations) | Moyen | Faible |
| 10 | Corriger les doublons de font loading | Moyen | Faible |

### Phase 3 — Amélioration continue

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 11 | Implémenter recherche globale Ctrl+K | Haut | Moyen |
| 12 | Pagination numérotée avec "per page" | Moyen | Faible |
| 13 | Keyboard shortcuts | Moyen | Moyen |
| 14 | Template tags Django pour les composants | Moyen | Moyen |
| 15 | Skip-to-content link + audit WCAG complet | Haut | Moyen |

---

## Conclusion

Le projet Sentinel possède une **bonne architecture de base** (composants séparés, HTMX, Alpine.js) mais souffre d'une **fragmentation extrême du design system** qui crée une expérience incohérente.

**Les 3 problèmes majeurs :**

1. **4 systèmes de couleurs coexistent** — 341 occurrences de `gray-*` natif hardcoded, 54 de tokens shadcn, 37 de Material Design, ~50 de Sentinel custom. Aucun template métier (workflow, admin, habilitation) n'utilise les tokens sémantiques.

2. **Page détail recommandation désorganée** — 8 cards sans hauteur fixe, split 60/40 arbitraire, 35 textes hardcoded, 18 SVG inline dupliqués, la classe card `bg-white rounded-xl border border-gray-100 shadow-sm p-5` répétée 8 fois sans `@apply`.

3. **Fonts chargées de manière fragmentée** — Inter en double, Plus Jakarta Sans déclaré mais non chargé sur la plupart des pages, Material Symbols uniquement sur login/lockout.

La priorité absolue est **l'unification du système de design** : choisir un seul système de tokens (recommandation : shadcn-like déjà présent dans input.css) et l'appliquer partout via des classes `@apply` dans `input.css`. Ensuite, la refonte du layout détail en 3 zones symétriques et la consolidation des sidebars en un composant paramétrable réduiront la dette technique de ~80%.

Le score global de **4.0/10** reflète une application fonctionnelle mais qui nécessite un effort de cohérence pour atteindre le standard professionnel attendu d'une application bancaire.
