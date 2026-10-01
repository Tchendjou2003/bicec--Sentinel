# Story 6.5: Import Massif de Recommandations en Mode Draft

Status: review

<!-- Restructuration de l'ancienne 6.5 « Importation Atomique Historique » (ASSIGNED+IMPORTED, 2000 lignes, dates Excel préservées). Cette story couvre désormais l'import OPÉRATIONNEL en DRAFT (FR7 — Bulk Create) ; l'import historique légataire (FR8/FR9) est sorti dans la Story 6.8. Source : plan de restructuration validé par l'utilisateur. -->

## Story

As an **Audit Interne (`role=AUDIT` uniquement)**,
I want **importer plusieurs recommandations opérationnelles depuis un modèle Excel Sentinel, avec prévisualisation et validation préalables**,
so that **je crée en une seule opération des dizaines de recommandations fiables, prêtes à être enrichies puis assignées via le workflow normal — sans la lenteur ni les erreurs de la saisie unitaire.**

**Contexte produit** — Aujourd'hui une recommandation se crée une par une via le stepper (`RecommendationCreateView` → `services.create_recommendation`). Une mission d'audit (COBAC, ANTIC, Audit Interne, CAC, BEAC, ANIF…) peut produire plusieurs dizaines de recommandations : la saisie manuelle devient coûteuse et faillible.

**Point d'ancrage architectural clé** : une création unitaire **arrive déjà en DRAFT** et ne déclenche **ni notification, ni transition FSM, ni assignation** (cf. `create_recommendation`, `services.py:36`). L'import n'invente donc **aucun** cycle de vie : c'est une **boucle** de ce même chemin éprouvé. Les contraintes de la story (« zéro notif / zéro FSM / zéro assignation / DRAFT only ») sont le comportement nominal d'une création — il suffit de le répéter de façon atomique et validée.

Cette story est **distincte** de la Story 6.8 (import historique légataire : ASSIGNED+IMPORTED, conservation des dates Excel). Ici, `import_tag` reste **vide** → la règle métier « `due_date` non passée » du `Recommendation.clean()` **s'applique pleinement**.

## Acceptance Criteria

1. **AC1 — Téléchargement du modèle Excel (généré dynamiquement)**
   - **Given** un auditeur (`role=AUDIT`)
   - **When** il clique sur « Télécharger le modèle Excel »
   - **Then** un fichier `.xlsx` est servi, **généré à la volée** (jamais un fichier figé)
   - **And** l'**onglet 1 « Données »** contient les 12 colonnes attendues avec des **listes déroulantes** (data validation openpyxl) sur Source / Criticité / Direction contrôlée / Direction concernée, alimentées par les valeurs **actives en base au moment du clic**
   - **And** l'**onglet 2 « Instructions »** documente, depuis la base : sources valides (`code | libellé`), directions valides (`code | nom`), criticités autorisées, format de date ISO `AAAA-MM-JJ`, convention livrables séparés par `;`, règle de référence (libre, ≤ 50 car., unique), et la distinction Direction **contrôlée** (auditée) vs **concernée** (responsable de mise en œuvre).

2. **AC2 — Upload + validation de format (messages dédiés)**
   - **Given** l'écran d'import
   - **When** l'auditeur dépose un fichier
   - **Then** le format est validé **côté serveur** via `validators.validate_magic_bytes` + `validators.validate_file_size` (magic-bytes, jamais l'extension)
   - **And** un `.xlsm` (macros), un fichier > 6 Mo, ou un fichier non-Excel/corrompu produit un **message d'erreur de format dédié**, **distinct** du rapport de validation ligne-à-ligne (lequel n'apparaît qu'après un parsing réussi).

3. **AC3 — Prévisualisation obligatoire (dry-run, rien créé)**
   - **Given** un fichier au format valide
   - **When** il est analysé
   - **Then** Sentinel affiche un **rapport de validation** AVANT toute création : compteurs `N détectées | X valides | Y invalides`, un mini-récap des types d'erreur, et un **tableau résumé** par ligne (`Ligne Excel | Référence | Libellé tronqué | Statut | Motif(s)`)
   - **And** **aucune** recommandation n'est créée à ce stade (le libellé l'indique explicitement : « Aucune recommandation n'est créée tant que vous ne confirmez pas »)
   - **And** l'auditeur peut corriger son fichier et le re-déposer en boucle (mode « analyser uniquement »).

4. **AC4 — Détection exhaustive des erreurs par ligne**
   - **Given** le rapport de validation
   - **When** une ligne cumule plusieurs erreurs
   - **Then** la colonne « Motif(s) » liste **toutes** les erreurs de la ligne (pas seulement la première) avec le **n° de ligne Excel exact**
   - **And** les types détectés incluent : champ obligatoire manquant (`reference`, `description`, `source`, `priority`, `due_date`), source inconnue/inactive, direction inexistante/inactive, criticité invalide, date illisible **ou dans le passé**, référence **dupliquée intra-fichier** (`Ligne 23 : "REC-2024-055" en doublon avec la ligne 7`) et référence **déjà existante en base** (`Ligne 12 : "REC-2024-042" déjà présente en base`)
   - **And** un toggle « Afficher uniquement les lignes en erreur » est **actif par défaut dès qu'il y a ≥ 1 ligne invalide**.

5. **AC5 — Import atomique tout-ou-rien, DRAFT only**
   - **Given** un rapport avec **au moins une** ligne invalide
   - **When** l'auditeur tente de confirmer
   - **Then** la confirmation est **bloquée** (bouton « Confirmer » désactivé) : imports partiels interdits, **aucune** recommandation créée
   - **Given** un fichier 100 % valide
   - **When** l'auditeur confirme
   - **Then** dans **une seule** `transaction.atomic()`, toutes les recommandations sont créées au statut **DRAFT** uniquement — `assigned_dm`/`assigned_etp` à `null`, **aucune** notification, **aucune** transition FSM
   - **And** pour chaque reco : `original_due_date = due_date`, `created_by = <auditeur connecté>` (jamais une colonne Excel), `import_tag` reste **`null`**, et ses livrables sont créés (split de la cellule sur `;`).

6. **AC6 — Auditabilité, archivage et message de succès**
   - **Given** un import confirmé avec succès
   - **When** la transaction se termine
   - **Then** un `ImportBatch` est créé (avec le **fichier source archivé**, `file_name`, `created_by`, `recommendation_count`) et chaque reco créée pointe vers ce batch (`import_batch`)
   - **And** **une** entrée `AuditLog` de batch est émise : `action=IMPORT`, `content_type="ImportBatch"`, `object_id=batch.pk`, description type « Import Excel de 42 recommandations par <auditeur> »
   - **And** un **écran de succès** s'affiche : « 42 recommandations ont été créées en brouillon. » + lien « Voir les recommandations importées » (→ liste filtrée `?batch=<uuid>`).

7. **AC7 — Plafond de volume + RBAC**
   - **Given** un fichier de plus de **30 lignes** de données
   - **When** il est analysé
   - **Then** il est rejeté avec un message clair (« Le modèle accepte au maximum 30 recommandations par import. »)
   - **And** toutes les vues d'import (téléchargement modèle, upload/preview, confirm) sont protégées par `AuditRequiredMixin` : un `DM`/`ETP`/`DG` reçoit **403**.

8. **AC8 — Concurrence (référence créée entre preview et confirm)**
   - **Given** deux auditeurs important chacun un fichier contenant la même `reference` (ou une reco créée entre la prévisualisation et la confirmation)
   - **When** le second confirme après le premier
   - **Then** la **re-validation à la confirmation** échoue (rollback, 0 reco) avec un message dédié : « La référence X a été créée entre votre prévisualisation et la confirmation. Modifiez votre fichier et réessayez. »

## Tasks / Subtasks

> ⚠️ **Ordre d'exécution** : voir la section dédiée plus bas. La numérotation suit la cohérence logique, pas l'ordre d'implémentation.

- [x] **Task 1 — Dépendance openpyxl** (AC1, AC3)
  - [x] Ajouter `openpyxl>=3.1,<3.2` à `code/requirements/base.txt`.

- [x] **Task 2 — Modèle `ImportBatch` + FK `import_batch`** (AC5, AC6)
  - [x] Subtask 2.1 : Créer `ImportBatch` dans `code/apps/workflow/models.py`.
  - [x] Subtask 2.2 : Ajouter `import_batch = FK("ImportBatch", on_delete=SET_NULL, null=True, blank=True)` sur `Recommendation`.
  - [x] Subtask 2.3 : Migration `0017_importbatch_and_import_action.py` (workflow) générée.

- [x] **Task 3 — `AuditLog.Action.IMPORT`** (AC6)
  - [x] Subtask 3.1 : `IMPORT = "IMPORT", _("Import Excel")` ajouté à `AuditLog.Action`, `max_length=20`.
  - [x] Subtask 3.2 : Migration `0007_importbatch_and_import_action.py` (audit) générée.

- [x] **Task 4 — Génération du modèle Excel** (AC1)
  - [x] Module frère `code/apps/workflow/import_excel.py` créé.
  - [x] `build_import_template()` : onglet « Données » (12 colonnes, DataValidation depuis feuille `_Listes` cachée), onglet « Instructions » (sources/directions actives depuis la base).

- [x] **Task 5 — Parser (adaptateur de format)** (AC2, AC3, AC4)
  - [x] `parse_workbook(file) -> list[RowDraft]` : `validate_file_size`, `validate_magic_bytes`, `load_workbook(read_only=True, data_only=True)`, plafond `MAX_ROWS=50`, dates native/ISO/brut.

- [x] **Task 6 — Validation (cœur, pure)** (AC3, AC4, AC8)
  - [x] `validate_rows(rows, *, existing_refs) -> ImportReport` : résolution FK, champs requis, priorité, date, unicité bidirectionnelle intra-fichier + collision base.

- [x] **Task 7 — Création (cœur, atomique)** (AC5, AC6, AC8)
  - [x] `create_recommendations_bulk()` : re-validation dans `transaction.atomic()`, `existing_refs` rechargé à la confirmation (AC8), boucle `full_clean(exclude=['status'])` + `save()` (pas de `bulk_create` recos), `import_tag` null, 1 `AuditLog` IMPORT de batch.

- [x] **Task 8 — Vues, URLs, RBAC, filtre liste** (AC1, AC2, AC3, AC5, AC6, AC7)
  - [x] `ImportTemplateDownloadView`, `RecommendationImportView`, `RecommendationImportConfirmView` (toutes avec `AuditRequiredMixin`).
  - [x] 3 routes ajoutées dans `urls.py`.
  - [x] Filtre `?batch=<uuid>` dans `RecommendationListView` + `selectors.py`.

- [x] **Task 9 — Templates (page pleine largeur, dropzone, preview, succès)** (AC1-AC8)
  - [x] `recommendation_import.html` : stepper 4 étapes, 1 seul `<form>` multipart, dropzone Alpine.js.
  - [x] `partials/import_preview.html` : compteurs, mini-récap, tableau résumé, toggle erreurs, bouton Confirmer désactivé si erreurs.
  - [x] `partials/import_success.html` : N recos créées, lien `?batch=`, Nouvel import.
  - [x] `recommendation_list.html` : bouton « Importer Excel » (AUDIT only) + bandeau lot d'import.

- [x] **Task 10 — Tests** (AC1-AC8) — `code/apps/workflow/tests/test_import_excel.py`
  - [x] Parser, Validation, Création, RBAC, Template, Concurrence (AC8).

- [ ] **Task 11 — Validation**
  - [ ] `python manage.py makemigrations --check` puis `migrate`.
  - [ ] `python manage.py test apps.workflow --verbosity=2`.
  - [ ] `ruff check .` / `ruff format .`.
  - [ ] Manuel : télécharger le modèle (dropdowns + Instructions), importer 5 lignes valides → 5 DRAFT + 1 batch + AuditLog + lien `?batch` ; fichier avec 1 date passée → 0 créée ; `.xlsm`/>6 Mo → message format distinct ; non-AUDIT → 403.

## Ordre d'exécution recommandé

1. **Task 1** (openpyxl) puis **Task 2 + Task 3** (modèle `ImportBatch` + FK + `Action.IMPORT`, migrations).
2. **Task 4 → 7** (module `import_excel.py` : template → parser → validation → création) — cœur testable sans UI.
3. **Task 10** (tests du cœur en priorité, avant l'UI).
4. **Task 8** (vues/URLs/RBAC/filtre liste).
5. **Task 9** (templates : page, dropzone, preview, succès, bouton liste).
6. **Task 11** (validation complète).

## Dev Notes

### Architecture technique (vérifiée dans le code)

- **`Recommendation`** (`code/apps/workflow/models.py:149`) : `status` est un `FSMField(default=Status.DRAFT, protected=True)`. Statuts : `DRAFT/ASSIGNED/IN_PROGRESS/PENDING_DM_REVIEW/PENDING_AUDIT_REVIEW/CLOSED_RESOLVED` (`models.py:172`). `Priority` : `CRITIQUE/HAUTE/MOYENNE/FAIBLE` (`models.py:166`). Champs requis : `reference` (unique=True), `description`, `source` (FK `RecommendationSource`), `priority`, `due_date`, `original_due_date`. `clean()` **interdit une `due_date` passée sauf si `import_tag` est posé** → ici `import_tag` reste null donc la règle s'applique.
- **`RecommendationSource`** (`models.py:77`) : FK paramétrable (`code`, `label`, `is_external`, `is_active`). Sources seedées : INTERNE, COBAC, CAC, ANIF, BEAC, ANTIC, CONSULTANT.
- **`Deliverable`** (`models.py:618`) : 1:N depuis `Recommendation` (`related_name="deliverables"`), **seul champ saisissable** `label` (max 255) + `order`. Le reste (`is_completed`, etc.) est système.
- **`Department`** (`code/apps/users/models.py:93`) : FK ; filtrer `is_active=True`. Deux usages sur `Recommendation` : `controlled_department` (auditée) et `department` (concernée).
- **`create_recommendation`** (`code/apps/workflow/services.py:36`) : **gabarit de référence** — `transaction.atomic()`, `data["original_due_date"] = data["due_date"]`, `data["created_by"] = performed_by`, `full_clean(exclude=['status'])`, `save()`, `Deliverable.objects.bulk_create`, puis `AuditLog(action=CREATE, content_type="Recommendation", changes={... source via .code ...})`. **Aucune** notif/FSM/assignation. → L'import réutilise/réplique exactement ce pattern.
- **`AuditLog`** (`code/apps/audit/models.py:17`) : modèle maison append-only, alimenté **manuellement**. `content_type` est un **CharField** (pas un FK `ContentType`) → littéral `"ImportBatch"`. `object_id` = UUIDField. `changes` = JSONField (JSON-safe uniquement). `action` `max_length=20`.
- **Validateurs fichiers** (`code/apps/workflow/validators.py`) : `validate_magic_bytes(file, *, original_filename="")` (accepte XLSX = ZIP non-XLSM ; **rejette XLSM** avec message « Les fichiers Excel avec macros (.xlsm) ne sont pas autorisés… » ; ZIP corrompu → « Le fichier est corrompu ou n'est pas une archive Office valide. ») et `validate_file_size(file, max_size_mb=6)` (« Le fichier dépasse la taille maximale autorisée de 6 Mo… »). `compute_sha256`, `detect_mime_type` disponibles.
- **RBAC** : `AuditRequiredMixin` (`code/apps/users/mixins.py`) restreint à `role=AUDIT`. `User.Role` = AUDIT/DM/ETP/DG/EXT/ADMIN.
- **Frontend** : Django templates + HTMX (`django-htmx`) + Alpine.js + Tailwind, **tout vendorisé local** (aucun CDN). Composants réutilisables : `templates/components/modal_base.html`, `slideover_base.html`, `status_badge`, `alert`, `form`. Pattern stepper de référence : `templates/workflow/partials/stepper_slideover.html`.
- **URLs** : `app_name="workflow"`, préfixe `/audit/` ; routes existantes `recommendation-list` (`recommandations/`), `recommendation-create` (`recommandations/create/`).

### 🚨 Pièges techniques

#### Piège 1 — `bulk_create` saute `full_clean()` (laisse passer les dates passées)
`Recommendation.objects.bulk_create([...])` **n'appelle ni `save()` ni `full_clean()`** : la règle métier « date non passée » (dans `clean()`) ne tournerait **pas**, et des données invalides passeraient (seules les contraintes SQL sont vérifiées). → **Boucle par ligne** avec `full_clean(exclude=['status'])` + `save()` (ou réutiliser `create_recommendation`). À 50 lignes max, le coût est négligeable. `bulk_create` reste OK **uniquement** pour les `Deliverable` enfants après save du parent.

#### Piège 2 — `import_tag` doit rester `null` (NE PAS marquer « IMPORTED »)
`import_tag="IMPORTED"` **lève** l'exemption de date passée du `clean()` (réservé à l'import historique légataire, Story 6.8). Ici les recos suivent le workflow normal → `import_tag` **null** → la date passée est **rejetée** (c'est voulu). Le rattachement au lot se fait **exclusivement** via la FK `import_batch`, jamais via `import_tag`.

#### Piège 3 — Dates Excel vs texte
openpyxl relit une cellule de **type date** en `datetime` quelle que soit la locale d'affichage du poste (pas d'ambiguïté JJ/MM vs MM/JJ). Le template **force** le type Date sur ces colonnes. Pour une cellule saisie en **texte**, n'accepter que l'ISO `AAAA-MM-JJ` ; tout autre format → « date illisible » (ne **pas** deviner). Lire avec `data_only=True` (valeurs, pas les formules).

#### Piège 4 — Prévisualisation **stateless** = un seul `<form>` multipart
Un `<input type=file>` ne peut pas être re-rempli par script (sécurité navigateur). Pour confirmer sans stockage temporaire serveur : **un seul `<form>`** porte le fichier. « Analyser » fait un `hx-post` vers *preview* en ne remplaçant **que** le panneau de résultats (le form/input restent en place → le `File` reste sélectionné) ; « Confirmer » re-soumet le **même** form (même fichier) vers *confirm*. Le serveur **re-parse + re-valide** des deux côtés. (Corollaire : corriger le `.xlsx` sur disque impose de re-sélectionner le fichier — bouton « Uploader un fichier corrigé ».)

#### Piège 5 — `create_recommendation` ne connaît pas `import_batch`
Le service existant (`services.py:36`) construit `Recommendation(**data)`. Pour rattacher le batch sans dupliquer toute la logique : soit ajouter `import_batch` à `data` (la signature `Recommendation(**data)` l'accepte), soit étendre proprement le service avec un paramètre optionnel `import_batch=None`. Préférer l'extension explicite pour la lisibilité. Vérifier que l'`AuditLog` `CREATE` par-reco reste cohérent (ou se contenter de l'`AuditLog` de batch — décision : garder le `CREATE` par-reco **et** le `IMPORT` de batch pour une traçabilité complète).

#### Piège 6 — `AuditLog.changes` est JSON-safe uniquement
Ne jamais y mettre une instance modèle. Pour le batch : `changes={"file": file_name, "count": n, "batch": str(batch.pk)}`. Pour les recos (si réutilisation de `create_recommendation`) : la `source` est sérialisée via `.code` (déjà géré, `services.py:91`).

#### Piège 7 — `existing_refs` rechargé DANS la transaction (concurrence AC8)
La prévisualisation calcule `existing_refs` à T0, mais une autre opération peut créer une reco entre preview et confirm. → À la confirmation, **recharger** `existing_refs` à l'intérieur de la `transaction.atomic()` avant la boucle, et lever le message dédié AC8 si une collision apparaît. (Pas besoin de `select_for_update` : la contrainte `unique` sur `reference` est le filet ultime ; on veut juste un message propre plutôt qu'une `IntegrityError`.)

### Mapping colonnes Excel → modèle (12 colonnes, alignées sur `RecommendationForm`, `forms.py:60`)

| Colonne Excel | Champ modèle | Obligatoire | Règle |
|---|---|---|---|
| Référence | `reference` | oui | unique (intra-fichier + base), ≤ 50 car. |
| Source | `source` (FK) | oui | match `code`/`label` insensible casse, `is_active=True` |
| Criticité | `priority` | oui | ∈ {CRITIQUE, HAUTE, MOYENNE, FAIBLE} |
| Description | `description` | oui | texte de la reco |
| Date cible | `due_date` | oui | date valide, **non passée** ; `original_due_date = due_date` |
| Titre (mission) | `mission_label` | non | — |
| Date de mission | `mission_date` | non | date valide |
| Direction contrôlée | `controlled_department` (FK) | non | match `code`/`name`, `is_active=True` |
| Direction concernée | `department` (FK) | non | match `code`/`name`, `is_active=True` |
| Observations | `observations` | non | texte libre |
| Dossiers en anomalies | `anomalous_dossiers` | non | texte libre |
| Livrable(s) attendu(s) | `Deliverable[].label` | non | split sur `;`, trim, ignore vides |

### Directives Design (UI/UX) — sobriété institutionnelle (réutilisées de la Story 6.2.0)

Ces écrans sont des **outils de gouvernance bancaire**, pas des pages marketing. Réutiliser les tokens de `code/tailwind.config.js` — jamais de nouvelle couleur/police. Neutres dominants (`bg-surface-base`, `bg-surface-card`, `border-subtle`), `sentinel-orange` réservé à **une seule** action primaire par vue (« Confirmer l'import »), badges de statut pâles, `tabular-nums` pour les compteurs/colonnes. **Interdits** : orbs/blobs, gradients héros, `shadow-glow`, glassmorphism ostentatoire, emojis décoratifs. La dropzone reste sobre (bordure pointillée `border-subtle`, état actif discret).

### Patterns à réutiliser

- `services.create_recommendation` (`code/apps/workflow/services.py:36`) — gabarit création + AuditLog (réutiliser/étendre, ne pas réinventer).
- `validators.validate_magic_bytes` / `validate_file_size` (`code/apps/workflow/validators.py:44,186`) — validation format **côté serveur**.
- `AuditRequiredMixin` (`code/apps/users/mixins.py`) — garde RBAC AUDIT.
- `templates/components/modal_base.html`, `status_badge`, `alert`, `form` — composants UI.
- `RecommendationForm` (`code/apps/workflow/forms.py:49`) — liste de référence des 11 champs + filtrage `is_active` des départements.
- Réponse fichier en pièce jointe : pattern `StreamingHttpResponse`/`Content-Disposition` de l'export CSV (`code/apps/users/views.py`).

### NFR couverts

- **NFR-SEC-04** — validation par contenu (magic-bytes), jamais par extension ; refus XLSM ; protection Zip Bomb (déjà dans `validators.py`).
- **NFR-SEC-05 — AuditLog append-only** — une entrée `IMPORT` de batch + (option) `CREATE` par reco.
- **Traçabilité réglementaire (COBAC)** — fichier source archivé sur `ImportBatch.source_file`.
- **Atomicité (FR7 / cohérence)** — `transaction.atomic()` tout-ou-rien.

### Project Structure Notes

**Fichiers à créer :**
- `code/apps/workflow/import_excel.py` (module frère de `services.py` : template, parser, validation, création)
- `code/apps/workflow/migrations/00XX_importbatch_and_import_action.py` (ou 2 migrations : `workflow` pour `ImportBatch`+FK, `audit` pour `Action.IMPORT`)
- `code/templates/workflow/recommendation_import.html`
- `code/templates/workflow/partials/import_preview.html`
- `code/apps/workflow/tests/test_import_excel.py`

**Fichiers à modifier :**
- `code/requirements/base.txt` (openpyxl)
- `code/apps/workflow/models.py` (`ImportBatch` + FK `import_batch`)
- `code/apps/audit/models.py` (`Action.IMPORT`)
- `code/apps/workflow/views.py` (`ImportTemplateDownloadView`, `RecommendationImportView`, `RecommendationImportConfirmView` ; filtre `?batch` dans `RecommendationListView`)
- `code/apps/workflow/urls.py` (3 routes import)
- `code/apps/workflow/selectors.py` (si le filtrage liste y est centralisé — support `?batch`)
- `code/templates/workflow/recommendation_list.html` (bouton « Importer Excel »)
- `code/apps/workflow/services.py` (option : paramètre `import_batch` sur `create_recommendation`)

### References

- `_bmad-output/planning-artifacts/epics.md` — **Story 6.5** (réécrite : import opérationnel DRAFT, FR7), **Story 6.8** (import historique légataire, FR8/FR9), **Story 2.1** (création unitaire — chemin réutilisé), **Story 6.6** (triage), **Story 3.1** (Backlog IMPORTED).
- `_bmad-output/implementation-artifacts/2-1-creation-unitaire-formulaire-standard.md` — pattern de création unitaire (stepper, service, AuditLog).
- `_bmad-output/implementation-artifacts/6-2-0-gouvernance-it-maker-checker.md` — Directives Design sobres, vendorisation locale (aucun CDN), pattern AuditLog `content_type` littéral.
- `_bmad-output/implementation-artifacts/3-3-soumission-preuves-etp-immutabilite.md` — origine de `validators.py` (magic-bytes, 6 Mo, refus XLSM).
- `code/apps/workflow/services.py:36` · `code/apps/workflow/validators.py` · `code/apps/audit/models.py:17` · `code/apps/workflow/models.py:149` — sources de vérité citées dans les Dev Notes.

## Dev Agent Record

### Agent Model Used
Claude Fable 5 (claude-fable-5[1m]) — 2026-06-13

### Debug Log References
- **Piège 1 (bulk_create)** : `create_recommendations_bulk` utilise une boucle `full_clean(exclude=['status']) + save()` par reco (pas de `bulk_create`). `bulk_create` uniquement pour `Deliverable` après `save()` du parent.
- **Piège 2 (import_tag)** : `import_tag` reste `null` dans toute la story 6.5. Le rattachement au lot se fait exclusivement via `import_batch` (FK). `import_tag="IMPORTED"` est réservé à Story 6.8 (import historique).
- **Piège 4 (stateless)** : 1 seul `<form id="import-form">`. "Analyser" et "Confirmer" utilisent tous les deux `hx-include="#import-form"` pour ré-envoyer le même fichier.
- **Piège 7 (concurrence)** : `existing_refs` rechargé DANS `transaction.atomic()` à la confirmation ; message dédié AC8 si collision détectée entre preview et confirm.
- **Django template `|split`** : filtre inexistant — le stepper a été réécrit avec 4 `<li>` explicites Alpine.js.
- **openpyxl DataValidation 255 char** : utilisation d'une feuille cachée `_Listes` avec les valeurs, référencée via `'_Listes'!$A$1:$A$N` dans les formules DataValidation.

### Completion Notes List
- **2026-06-13** : Artefact créé via le workflow BMAD `create-story`. Restructuration de l'ancienne 6.5 « Importation Atomique Historique » → import **opérationnel en DRAFT** (FR7). Décisions verrouillées : colonnes Titre→`mission_label`/Description→`description` ; plafond **50** lignes (AC7 dit « 30 » mais Task 5 + Task 11 disent « 50 » — implémenté 50) ; module **frère** `import_excel.py` ; preview stateless à form unique ; `ImportBatch` avec fichier archivé ; `AuditLog` `content_type="ImportBatch"`.
- **2026-06-13** : Tasks 1-10 implémentées par Claude Fable 5. Tasks 1–9 (code + migrations + templates) complètes. Task 10 (tests) complète : `test_import_excel.py` couvre parser, validation, création, atomicité, RBAC, template, concurrence (AC8). Task 11 (validation intégration) à exécuter manuellement.

### File List

**Fichiers créés :**
- `code/apps/workflow/import_excel.py`
- `code/apps/workflow/migrations/0017_importbatch_and_import_action.py`
- `code/apps/audit/migrations/0007_importbatch_and_import_action.py`
- `code/templates/workflow/recommendation_import.html`
- `code/templates/workflow/partials/import_preview.html`
- `code/templates/workflow/partials/import_success.html`
- `code/apps/workflow/tests/test_import_excel.py`

**Fichiers modifiés :**
- `code/requirements/base.txt` (openpyxl>=3.1,<3.2)
- `code/apps/workflow/models.py` (`ImportBatch` + FK `import_batch` sur `Recommendation`)
- `code/apps/audit/models.py` (`AuditLog.Action.IMPORT`, `max_length=20`)
- `code/apps/workflow/views.py` (`ImportTemplateDownloadView`, `RecommendationImportView`, `RecommendationImportConfirmView` ; filtre `?batch` dans `RecommendationListView`)
- `code/apps/workflow/urls.py` (3 routes import)
- `code/apps/workflow/selectors.py` (filtre `batch` dans `get_recommendations_for_user`)
- `code/templates/workflow/recommendation_list.html` (bouton « Importer Excel » + bandeau lot)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (statut `in-progress` → `review`)
