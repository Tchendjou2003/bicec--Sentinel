# Audit Design System & Frontend — Sentinel (document canonique)

> **Statut** : audit consolidé et **vérifié contre le code source**.
> **Méthode** : fusion de deux audits indépendants, dont chaque affirmation factuelle a été recoupée par lecture directe des templates, des tokens (`tailwind.config.js`, `static/css/input.css`) et `grep` quantitatif. Les affirmations non vérifiées ou fausses ont été écartées (voir §Annexe).
> **Portée** : `code/templates/**`, `code/static/css/**`, `code/static/js/sentinel.js`, `code/tailwind.config.js`.
> **Score global réconcilié : 5 / 10** — base architecturale saine, minée par la fragmentation des design tokens.

---

## Synthèse exécutive — scores par axe (réconciliés)

| # | Axe | Score | État |
|---|-----|-------|------|
| 1 | Hiérarchie visuelle | 5/10 | À améliorer |
| 2 | Charge cognitive | 4/10 | Problématique |
| 3 | Navigation rapide | 6/10 | Correct |
| 4 | Feedback immédiat | 4/10 | Partiel |
| 5 | Accessibilité | 3/10 | **Critique** |
| 6 | Gestion des états | 5/10 | Partiel |
| 7 | Performance perçue | 4/10 | Insuffisant |
| 8 | Action > Décoration | 5/10 | À discipliner |
| 9 | Cohérence visuelle | 4/10 | Fragmentée |
| 10 | Centralisation des tokens | **2/10** | **Critique (cause racine)** |
| 11 | Organisation layout / détail | 4/10 | À refondre |

> Note méthodologique : un audit tiers notait 4,0/10, un autre 6,2/10. L'écart venait du **double-comptage du problème de tokens sur tous les axes**. Le présent document fixe la note à **5/10** : tokens réellement critiques (2/10 mérité), mais navigation et layout ne sont pas catastrophiques.

---

## 0. Cause racine — 4 systèmes de couleurs en collision (axe 10)

`tailwind.config.js` empile **quatre familles de couleurs concurrentes** :

| # | Système | Exemples | Source |
|---|---------|----------|--------|
| A | Brand Sentinel | `sentinel-orange #E87722`, `sentinel-brown`, `status-*` | `tailwind.config.js:12-26` |
| B | Surface / Neutrals sémantiques | `surface-card`, `text-primary #2D1F1E`, `text-secondary`, `border-subtle` | `tailwind.config.js:28-35` |
| C | Material Design / « Stitch » (~48 tokens) | `on-surface`, `surface-container-*`, `primary #a23f00`, `error #ba1a1a` | `tailwind.config.js:37-84` |
| D | HSL Shadcn | `--primary 25 80% 53%`, `--card`, `--sidebar-*` via `hsl(var(--*))` | `static/css/input.css:13-55` |

### Collision critique sur `primary` (vérifiée)
Trois valeurs différentes selon le chemin d'écriture :
- `sentinel-orange` = `#E87722` (orange marque)
- `primary` (Material) = `#a23f00` (brun-rouge)
- `--primary` (HSL) = `hsl(25 80% 53%)` (orange)

**Piège** : `text-primary` rend **#a23f00** (Material), PAS le texte foncé attendu — celui-ci exige `text-text-primary` (#2D1F1E). Source de bugs visuels silencieux.

### Tokens fantômes (vérifié)
`layouts/external_shell.html` référence `brand-500/600/700` qui **n'existent dans aucun système** → ne rendent pas (fuite de conventions Shadcn).

### Mesures quantitatives (vérifiées par grep)
- **786 occurrences** de classes `gray-*` réparties sur **52 fichiers** de templates.
- Adoption de tokens sémantiques : **~2–5 %** dans le workflow et les dashboards ; **~40 %** (mais mélangé) dans habilitation/admin.
- **4** directives `@apply` dans `input.css` — toutes pour des éléments décoratifs (`login-orb`), **aucune** pour les patterns récurrents (card, bouton, input).

→ **Conclusion** : aucune propagation de design n'est possible tant que ces 4 systèmes coexistent. C'est la cause première de la plupart des incohérences ci-dessous.

---

## Axes 1 → 11 (constats vérifiés)

### 1. Hiérarchie visuelle — 5/10
- Titres de page en **3 couleurs différentes** selon le profil : `text-gray-900` (admin), `text-sentinel-brown` (habilitation, `home.html:7`), `text-foreground` (notifications).
- Dashboards **sans `<h1>`** : titre de page en `<h2>`, sous-sections en `<h3>` → outline sémantique cassé.
- Modales : `text-lg` partout sauf `submit_evidence_modal.html:16` en `text-base`.

### 2. Charge cognitive — 4/10
- `workflow/recommendation_detail.html` : `x-data` déclare **11 états modaux** (ligne 7) ; jusqu'à **13 boutons d'action** en sticky bar ; 8–9 cartes ; aucune divulgation progressive.
- Classe card `bg-white rounded-xl border border-gray-100 shadow-sm p-5` répétée **9×** dans ce seul fichier.
- `provisioning_list.html` : table 7 colonnes sans priorisation ni lignes repliables.

### 3. Navigation rapide — 6/10
- **Recherche topbar non fonctionnelle** : `topbar.html:15` est un `<input type="search">` orphelin (ni `form`, ni `hx-get`) ; le « Ctrl+K » du placeholder est décoratif (aucun handler clavier).
- Breadcrumbs présents sur certaines pages (habilitation, user_create) mais absents sur `admin_it` (dashboard, listes, organigramme, provisioning).
- Pagination « Précédent / Suivant » uniquement (pas de pagination numérotée ni « par page »).
- **Note** : les sidebars utilisent correctement `{% url %}` (pas d'URL métier en dur — l'audit tiers se trompait sur ce point). Seuls 2 liens non implémentés sont des `href="#"` (Import, Validation).

### 4. Feedback immédiat — 4/10
- **Aucun indicateur de chargement HTMX** (`hx-indicator`/skeleton) sur les filtres de liste, refresh de table, recherche organigramme.
- Boutons async sans état `disabled`/spinner (`close_confirm_modal.html:70`, `reject_audit_modal.html:72`, `extension_review_modal.html`) → risque de double-clic.
- **Point fort à préserver** : toasts globaux cohérents via le store Alpine `sentinel.notify` (`base.html` + `sentinel.js`). *(Le store EST initialisé dans `sentinel.js` — l'audit tiers se trompait en le disant absent.)*

### 5. Accessibilité — 3/10 (critique)
- Dashboards sans `<h1>` → outline cassé pour lecteurs d'écran.
- **Indicateurs couleur-seule** (WCAG) : bordures de ligne rouge/orange/vert dans `urgency_table.html` sans alternative textuelle ; badges de statut couleur-seule.
- ARIA manquants : toggle admin sans `aria-pressed` ; badge notif sans `role="status"` ; SVG décoratifs sans `aria-hidden`.
- Modales en `<div>` + overlay au lieu de `<dialog>` ; pas de focus-trap ; focus non rendu au déclencheur. *(Exception : `provisioning_create_modal.html` a déjà `role="dialog"`/`aria-modal`/`aria-labelledby`.)*
- Modales HTMX (`assign_dm`, `delegate_etp`, `submit_evidence`…) rendues **sans overlay** → page derrière interactive.
- Contraste : `text-gray-400` sur blanc ≈ **2,5:1** (< 4,5:1 requis).
- `x-cloak` appliqué de façon inégale (certains éléments utilisent `style="display:none"` sans `x-cloak`).

### 6. Gestion des états — 5/10
- États vides : **5+ implémentations différentes**, pas de composant partagé.
- Pas d'état « en cours d'envoi » sur les actions critiques ; pas d'optimistic UI.
- Sidebar collapse : état en mémoire Alpine uniquement, **pas de persistance localStorage** → reset au reload.
- Aucune gestion d'échec réseau HTMX (`htmx:responseError`).

### 7. Performance perçue — 4/10
- Aucun skeleton loader ; `animate-fade-in` minimal.
- **Fonts fragmentées (vérifié)** : `input.css:1` charge Inter + Manrope + JetBrains Mono ; `login.html:10-11` **recharge Inter** (doublon réseau) + Plus Jakarta Sans (uniquement ici) + Material Symbols ; `lockout.html:10` charge Material Symbols seul. `font-headline` (Plus Jakarta Sans) est déclaré dans Tailwind mais **non chargé** hors login → fallback système.
- 6 familles de polices déclarées, 2 réellement utilisées de façon cohérente (`sans`=Inter, `heading`=Manrope) ; `font-label` redondant avec `font-body`.
- Pas de `loading="lazy"` sur les images.

### 8. Action > Décoration — 5/10
- **Bouton primaire orange dupliqué inline 11+ fois** (`from-sentinel-orange to-[#C9631A]`) ; bouton secondaire 9+ fois ; `#C9631A` codé en dur ~8×. Le composant `btn_primary.html` existe mais est sous-utilisé.
- `recommendation_detail` : 13 boutons au même style `text-xs` → aucune hiérarchie primaire/secondaire/danger.
- Login surchargée : 3 orbs animés + watermark + 2 grilles de points pour une application bancaire métier.
- Gradient orange omniprésent (états actifs sidebar + CTA) → perte d'impact.

### 9. Cohérence visuelle — 4/10
- **Overlays de modale** : `bg-gray-900/40` vs `bg-gray-900/50` (mélangés dans `recommendation_list.html`) vs `bg-on-surface/40` (`provisioning_reject_modal.html`).
- **Panneaux** : `bg-white rounded-2xl` (workflow) vs `bg-surface-card rounded-xl` (provisioning).
- **Mécanismes de fermeture** : `@click` Alpine vs `$dispatch` custom event vs `$el.remove()` DOM — 3 patterns.
- **Ombres** : `shadow-sm/md/lg/2xl` + `shadow-premium-*` + `shadow-[...0.02]` vs `0.04` (sidebars) — pas d'échelle.
- **Rayons** : `rounded-lg`/`xl`/`2xl` mélangés pour des rôles équivalents.
- Tables : entêtes `bg-gray-50/50` vs `/60` vs `/70` vs `/80`.
- Duplication copier-coller : table « Santé par Direction » identique entre `audit_dashboard` et `dg_dashboard`.

### 10. Centralisation des tokens — 2/10
Voir §0. Cause racine. 4 systèmes + collision `primary` + tokens fantômes + 786 `gray-*` + 0 `@apply` métier.

### 11. Organisation layout / détail — 4/10
- **Détail reco** : grid `lg:grid-cols-5` (split 60/40) avec cards sans `min-height` → déséquilibre vertical massif (colonne gauche lourde en texte, colonne droite avec vide ou débordement selon la timeline). Refonte en zones symétriques recommandée.
- Breakpoints incohérents : `sm`/`lg`/`xl` mélangés ; **ETP saute le tablet** (`grid-cols-2 → sm:grid-cols-4`).
- `provisioning` slide-over `min-width:480px` casse sur tablette (35 % de 768 = 270px < 480).
- `notification_dropdown` `width:380px` dépasse la largeur iPhone (390px).
- **z-index non centralisé** : toast 9999, slide-over/modale 100, modale organigramme 60, dropdown notif 50, sidebar mobile 50, topbar 30 → conflits potentiels.

---

## Incohérences transverses — tableaux de synthèse

### Sidebars (6 hand-codées + 1 composant mort)
| | admin | audit | audit_ext | dm | dg | etp | base (inutilisé) |
|--|--|--|--|--|--|--|--|
| Largeur | w-72 | **w-64** | w-72 | w-72 | w-72 | w-72 | w-64 |
| Rayon actif | rounded-xl | **rounded-lg** | xl | xl | xl | xl | rounded-md |
| Ombre | …0.02 | **…0.04** | 0.02 | 0.02 | 0.02 | 0.02 | — |
| Texte items | text-sm | **text-[13px]** | sm | sm | sm | sm | sm |

`components/sidebar_base.html` n'est **inclus nulle part** → code mort. Lien actif (gradient orange) recodé 6×.

### Modales / overlays
| Fichier | Overlay | z-index | Fermeture |
|--|--|--|--|
| recommendation_list (stepper) | gray-900/**40** | 100 | @click + event |
| recommendation_list (delete) | gray-900/**50** | 100 | @click |
| delete_confirm | gray-900/50 | **60** | @click |
| provisioning_reject | **on-surface/40** | 50 | $el.remove() |
| modales HTMX (assign/delegate/submit…) | **aucun** | — | mix |

---

## Points forts à préserver
- Toasts globaux cohérents (store Alpine `sentinel.notify`).
- Composant `kpi_card.html` réutilisable (système d'accent).
- `urgency_table.html` partagé entre DM/DG/ETP (bon réemploi).
- Hiérarchie de polices définie (Manrope titres / Inter corps / JetBrains Mono).
- Couleurs de marque cohérentes là où elles sont appliquées.
- Espacement de section cohérent (`mb-8`).
- Bonne séparation `components/` / `layouts/` / `partials/` ; HTMX + Alpine.

---

## Backlog priorisé

### P0 — Cause racine & accessibilité bloquante
| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | **Unifier les design tokens** : choisir UN système (aligné sur le projet Claude Design), résoudre la collision `primary`, supprimer Material/HSL/`brand-*` morts | Très haut | Moyen |
| 2 | Créer des classes `@apply` pour les patterns récurrents (`.card`, `.btn-primary/secondary/danger`, `.input`) dans `input.css` | Très haut | Faible |
| 3 | Ajouter `<h1>` aux dashboards (outline sémantique) | Haut | Faible |
| 4 | Alternative textuelle aux statuts couleur-seule (`urgency_table`, badges) | Haut | Faible |
| 5 | Overlay + `role="dialog"`/`aria-modal` + focus-trap sur toutes les modales (HTMX incluses) | Très haut | Moyen |

### P1 — Cohérence structurante
| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 6 | Composant **Button** unifié (primary/secondary/danger/ghost × tailles) → supprimer les 20+ duplications inline | Très haut | Moyen |
| 7 | Composant **Modal/Slide-over** unifié (overlay, z-index, structure, fermeture) | Haut | Moyen |
| 8 | Composant **Sidebar** unique paramétré → tuer les 6 copies + le code mort `sidebar_base.html` | Très haut | Moyen |
| 9 | Échelles centralisées : z-index, ombres, rayons | Haut | Faible |
| 10 | Utiliser `status_badge.html` partout au lieu des classes inline | Moyen | Faible |

### P2 — Qualité & quick wins
| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 11 | États de chargement HTMX (`hx-indicator` global + skeletons) ; gestionnaire `htmx:responseError` → toast | Haut | Moyen |
| 12 | Composant **état vide** unique ; persistance localStorage de la sidebar | Moyen | Faible |
| 13 | **Consolider les fonts** : retirer le doublon Inter de `login.html`, charger toutes les fonts au même endroit, charger ou retirer Plus Jakarta Sans | Moyen | Faible |
| 14 | Implémenter la recherche globale Ctrl+K (HTMX) **ou** retirer le leurre | Moyen | Moyen |
| 15 | Harmoniser les breakpoints (tablet partout) ; corriger slide-over/dropdown mobile | Moyen | Faible |
| 16 | `aria-pressed`, `role="status"`, `aria-hidden`, skip-to-content, `x-cloak` systématique | Haut | Moyen |
| 17 | Supprimer le code mort : `home.html` (page de test) et `sidebar_base.html` | Faible | Faible |

---

## Annexe — Affirmations d'audit écartées (fausses / périmées)

Conservées ici pour traçabilité ; **ne pas** les inclure dans les décisions.

| Affirmation écartée | Réalité vérifiée |
|---|---|
| « 341 occurrences `gray-*` » | **786** occurrences (52 fichiers) — sous-estimé |
| « `sidebar_audit` utilise des URLs en dur `/audit/` » | **Faux** : utilise `{% url %}` (`sidebar_audit.html:26,32`) |
| « 0 classe `@apply` » | **Faux** : 4 dans `input.css` (vrai seulement pour cards/boutons) |
| « `output.css?v=2` » | **Faux** : `?v=3` (`base.html:12`) |
| « JS sans cache-busting » | **Périmé** : `sentinel.js?v=6`, `tom-select?v=1` |
| « Store Alpine `sentinel` non initialisé » | **Faux** : initialisé dans `sentinel.js` (`alpine:init`) |
| « 7 sidebars » | Le tableau source en listait **8** (incohérence interne) |
| « base.html sans block navbar → maintenance impossible » | **No-op inoffensif** : `login.html:6` override un block non défini, sans effet |

---

## Prochaine étape recommandée
Attaquer le **P0-1 (unification des tokens)** depuis le projet Claude Design (à déposer dans `code/doc/design-system/`), en **additif** d'abord (sans casser le rendu existant) et en résolvant la collision `primary`. Puis dérouler le backlog par lots, en commençant par les classes `@apply` (P0-2) qui débloquent toutes les migrations de composants suivantes.
