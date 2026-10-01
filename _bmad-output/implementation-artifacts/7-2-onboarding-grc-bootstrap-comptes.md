# Story 7.2: Onboarding GRC — Bootstrap gouverné, entité système & création de comptes par profils

Status: ready-for-dev

<!-- Suite de la Story 6.2.0 (gouvernance IT Maker/Checker) et de 1.4/1.5 (organigramme + RBAC). Cette story résout : (1) l'impossibilité de créer le Directeur de l'Audit Interne via les formulaires (is_audit_admin non exposé) ; (2) la prise en main « page blanche » ; (3) l'absence d'emplacement organigramme pour les admins Sentinel ; (4) le bootstrap non gouverné du premier admin. Décision doctrinale verrouillée : l'Audit reste exclusivement auditeur (jamais audité), donc le DAI = AUDIT + is_audit_admin, sans multi-rôle. -->

## Story

As a **Responsable Sécurité / Gouvernance (BICEC)**,
I want **prendre en main Sentinel sur une base déjà amorcée (entité système seedée + premier administrateur créé sans Django Admin), être guidé pas-à-pas dans la matérialisation de l'organigramme, puis créer tous les comptes — y compris celui du Directeur de l'Audit Interne — via des profils métier prédéfinis dans les formulaires de l'application**,
so that **le déploiement de Sentinel dans n'importe quelle organisation (banque ou autre) soit professionnel, intuitif et gouverné, sans jamais recourir à l'interface Django Admin, et sans figer l'outil sur le contexte BICEC.**

**Contexte produit** — La Story 6.2.0 a centralisé la création de comptes via un flux Maker/Checker (l'IT saisit, un membre du groupe « Administrateurs Sentinel » valide). Mais trois trous subsistent. **(1)** Le formulaire de provisioning n'expose pas le flag `is_audit_admin` : impossible de créer le Directeur de l'Audit Interne (DAI) autrement que par Django Admin. **(2)** La première prise en main démarre « page blanche » : aucun guidage, aucune structure pré-existante, et nulle part où rattacher les administrateurs Sentinel eux-mêmes dans l'organigramme. **(3)** Le tout premier administrateur se crée via `createsuperuser` + Django Admin — non gouverné, hors RBAC Sentinel.

**Décision doctrinale (verrouillée avec la direction).** L'Audit Interne et le DAI **restent exclusivement auditeurs — jamais audités** (cohérent avec la chaîne AUDIT-fermée). Le « double-chapeau » initialement envisagé (cumul AUDIT + DM) est **abandonné** : le DAI = `role=AUDIT` + `is_audit_admin=True`. De même, `ADMIN` est un **rôle purement système** (gère l'outil, n'émet ni ne reçoit de recommandation). Les booléens sur `User` restent réservés à l'identité structurelle ; aucune nouvelle capacité fonctionnelle n'est encodée en booléen.

## Acceptance Criteria

### Phase A — Entité système & organigramme amorcé

1. **AC1 — Seed de l'entité système (idempotent)**
   - **Given** un déploiement neuf après `migrate`
   - **Then** il existe un `OrgUnitType(code="SUPPORT", name="Support Applicatif", level=0, is_active=True)` et un `Department(code="SUPPORT", name="Support Applicatif", type=SUPPORT, is_system=True, parent=None, is_active=True)`
   - **And** rejouer la migration n'a aucun effet de bord (`get_or_create`, `reverse_code` symétrique).

2. **AC2 — Entité système protégée mais renommable**
   - **Given** un département `is_system=True`
   - **When** un membre du groupe tente de le **supprimer** ou de **désactiver** (`is_active=False`) — que ce soit via `soft_delete_department_with_audit` **ou** via l'édition (`DepartmentForm`/`update_department_with_audit`)
   - **Then** l'opération est refusée par une `ValidationError` levée dans `Department.clean()` (garde au niveau modèle, couvrant tous les chemins)
   - **And** le **renommage** (`name`) reste autorisé
   - **And** l'`OrgUnitType` SUPPORT ne peut être désactivé via `toggle_org_unit_type` tant qu'un département `is_system=True` l'utilise
   - **And** dans l'organigramme, l'entité affiche un badge « ⚙️ Système » et ses boutons Supprimer/Désactiver sont grisés (Modifier reste actif).

### Phase B — Bootstrap gouverné (commande)

3. **AC3 — Création du premier administrateur sans Django Admin**
   - **Given** un déploiement neuf (0 administrateur Sentinel actif)
   - **When** l'opérateur exécute `python manage.py bootstrap_admin --username … --email … [--password …]`
   - **Then** un `User(role=ADMIN, department=<entité système>, job_title="Administrateur Sentinel", is_staff=False)` est créé
   - **And** ce **premier** admin est ajouté au groupe « Administrateurs Sentinel » (= Checker / tête de l'entité)
   - **And** un `AuditLog` est émis, tracé `[BOOTSTRAP]` avec `is_checker=True`
   - **And** à la connexion, il atterrit sur `admin-dashboard` **sans aucune modification du flux de login** (`SentinelLoginView` route déjà `role==ADMIN`).

4. **AC4 — Deuxième admin (Maker) puis verrou**
   - **Given** 1 administrateur Sentinel actif existe déjà
   - **When** l'opérateur relance `bootstrap_admin`
   - **Then** le deuxième `User(role=ADMIN, …)` est créé **hors** groupe (= Maker)
   - **When** l'opérateur relance une 3ᵉ fois (≥2 admins actifs)
   - **Then** la commande refuse (`PermissionDenied` / `CommandError`) : le bootstrap est terminé, les comptes suivants passent par le flux Maker/Checker.

### Phase C — Création de comptes par profils (dont le DAI)

5. **AC5 — Catalogue de profils dans le formulaire de provisioning**
   - **Given** le Maker ouvre le slide-over de création de demande
   - **Then** un sélecteur de **profils** groupés par catégorie est proposé (Administration / Audit / Métier / Gouvernance) à partir de `ACCOUNT_TEMPLATES`
   - **When** il sélectionne un profil (ex. « Directeur de l'Audit »)
   - **Then** les champs aval sont pré-remplis (`requested_role`, `requested_is_audit_admin`, `requested_job_title`), la section mission EXT s'affiche pour le profil externe, et la clé du profil est stockée dans `requested_profile`
   - **And** les champs restent éditables (sauf le département pour le profil ADMIN).

6. **AC6 — Création du Directeur de l'Audit Interne via formulaire (cœur)**
   - **Given** le Maker sélectionne le profil « Directeur de l'Audit » et soumet la demande
   - **When** un Checker l'approuve
   - **Then** sous `transaction.atomic()`, un `User(role=AUDIT, is_audit_admin=True, job_title="Directeur de l'Audit Interne")` est créé — **sans passer par Django Admin**
   - **And** `requested_is_audit_admin=True` n'est accepté **que si** `requested_role==AUDIT` (validation croisée du formulaire ; sinon erreur)
   - **And** l'`AuditLog` inclut les deltas `is_audit_admin`, `job_title` et `requested_profile`.

7. **AC7 — Profil Administrateur Sentinel & filtrage du département système**
   - **Given** le profil « Administrateur Sentinel » (role=ADMIN, `auto_department="SYSTEM"`)
   - **When** la demande est créée
   - **Then** le service `create_provisioning_request` affecte automatiquement `requested_department = resolve_system_department()` (le formulaire soumet un département **vide** ; le champ TomSelect est vidé et désactivé côté Alpine)
   - **And** l'entité système est **exclue** du sélecteur de département (`.exclude(is_system=True)`) pour tous les profils métier : « Support Applicatif » n'apparaît jamais pour un DM/ETP/DG.

### Phase D — Onboarding guidé

8. **AC8 — Bandeau de progression sur le dashboard admin**
   - **Given** un administrateur sur un déploiement où l'organigramme **métier** est vide
   - **Then** le dashboard affiche un bandeau d'onboarding en 3 étapes (1. Organigramme → 2. Audit → 3. Comptes métier) avec liens vers l'organigramme et le provisioning
   - **And** chaque étape réalisée passe en ✅ ; le bandeau disparaît quand les trois sont satisfaites
   - **And** le calcul exclut l'entité système (`Department(is_active=True, is_system=False)`).

## Tasks / Subtasks

- [ ] **T1 — Modèles** (AC: 1, 2, 6) — `code/apps/users/models.py`
  - [ ] `Department.is_system = BooleanField(default=False, editable=False)`
  - [ ] `Department.clean()` : `ValidationError` si `is_system and not is_active`
  - [ ] `User.job_title = CharField(max_length=100, blank=True, default="")`
  - [ ] `UserProvisioningRequest` : `requested_is_audit_admin`, `requested_job_title`, `requested_profile`
  - [ ] `UserProvisioningRequest.clean()` : règle croisée `requested_is_audit_admin → requested_role==AUDIT`
- [ ] **T2 — Migrations** (AC: 1) — `0010_admin_entity_fields` (schéma) + `0011_seed_admin_org_unit` (data, idempotente, `reverse_code`)
- [ ] **T3 — Catalogue profils** (AC: 5, 7) — `code/apps/users/account_templates.py` : `ACCOUNT_TEMPLATES`, `get_template`, `get_templates_grouped`, `resolve_system_department`
- [ ] **T4 — Formulaire** (AC: 5, 6, 7) — `forms.py` : champs `requested_*` ; `__init__` `.exclude(is_system=True)` ; `clean()` règle croisée
- [ ] **T5 — Services** (AC: 2, 3, 4, 6, 7) — `services.py`
  - [ ] `create_provisioning_request` : persister les 3 champs ; ADMIN → `resolve_system_department()`
  - [ ] `approve_provisioning_request` : propager `is_audit_admin` + `job_title` ; AuditLog enrichi
  - [ ] garde `is_system` dans `soft_delete_department_with_audit` ; garde SUPPORT dans `toggle_org_unit_type`
  - [ ] `bootstrap_create_admin(*, …)` : verrou ≥2, dept système, 1er=groupe, AuditLog `[BOOTSTRAP]`
- [ ] **T6 — Commande** (AC: 3, 4) — `code/apps/users/management/commands/bootstrap_admin.py`
- [ ] **T7 — Vues & selectors** (AC: 5, 8) — `views.py` (`AdminDashboardView` onboarding, `ProvisioningRequestCreateView` templates) ; `selectors.py` (`count_business_departments`)
- [ ] **T8 — Templates** (AC: 2, 5, 7, 8)
  - [ ] `partials/provisioning_create_modal.html` : sélecteur de profil + synchro **TomSelect via API**
  - [ ] `dashboard.html` : bandeau onboarding
  - [ ] `partials/organigramme_node.html` : badge « Système » + boutons grisés
- [ ] **T9 — Vérification** (AC: tous) — migrations idempotentes, scénario bootstrap, création DAI, `python manage.py test apps.users apps.workflow`

## Dev Notes

### Doctrine (NE PAS violer)
- **L'Audit n'est jamais destinataire d'une recommandation.** Ne pas toucher `get_recommendations_for_user` ni `get_available_dms_for_department` : le DAI n'est **pas** un DM. [Source: plan §"Ce qui NE change PAS"]
- **`ADMIN` = système pur**, déjà *fail-closed* dans `workflow/selectors.py::get_recommendations_for_user` (rôles non pris en charge → `qs.none()`).
- **Pas de nouveau booléen de capacité.** La distinction « tête vs membres » réutilise le groupe Django « Administrateurs Sentinel » (l'existant), pas un champ.

### Pièges & edge cases (détectés en revue)
1. **ModelChoiceField + exclude** : `requested_department` (`forms.py:309`) a un queryset `Department.objects.filter(is_active=True)`. Y ajouter `.exclude(is_system=True)` fait que **soumettre l'ID système → « Select a valid choice »**. Donc le profil ADMIN soumet un département **vide** (`required=False` déjà en place, `forms.py:312`) ; l'entité système est affectée **côté service**.
2. **Garde modèle obligatoire** : `update_department_with_audit` (`services.py:172`) appelle `form.save()` et `DepartmentForm` inclut `is_active` → une garde uniquement dans `soft_delete_department_with_audit` serait **contournable** par l'édition. Mettre la garde dans `Department.clean()`.
3. **TomSelect** : le champ porte la classe `js-tomselect` (`forms.py:315`), initialisée par `static/js/sentinel.js`. Modifier le `<select>` natif via Alpine ne met pas à jour l'affichage → utiliser `el.tomselect.setValue(...)`, `.disable()/.enable()`. [Source: plan §8]
4. **Double-hachage** (rappel 6.2.0) : `approve_provisioning_request` affecte `user.password = hashed_initial_password` **directement** (pas `create_user(password=…)`). Pour `bootstrap_create_admin`, on crée un mot de passe en clair → `create_user(password=…)` est correct (pas de hash préalable).

### Source tree à toucher
- App `users` : `models.py`, `forms.py`, `services.py`, `selectors.py`, `views.py`, `urls.py` (route commande non requise), `account_templates.py` (nouveau), `migrations/0010*`, `migrations/0011*`, `management/commands/bootstrap_admin.py` (nouveau).
- Templates : `admin_it/dashboard.html`, `admin_it/partials/provisioning_create_modal.html`, `admin_it/partials/organigramme_node.html`.
- Réutiliser : `settings.PROVISIONING_APPROVER_GROUP_NAME`, groupe créé par `migrations/0009_create_approvers_group.py`, patterns de seed `migrations/0006_seed_org_unit_types.py`.

### Testing standards
- Tests dans `code/apps/users/tests/` (suivre `test_views.py`, `test_services.py` existants). Couvrir : idempotence du seed, garde `is_system` (delete + edit), verrou bootstrap ≥2, propagation `is_audit_admin`/`job_title` à l'approbation, validation croisée, exclusion du dept système du sélecteur.

### Project Structure Notes
- Convention HackSoft respectée : mutations en `services.py`, lectures en `selectors.py`, validations en `forms.py`/`models.clean()`, HTTP en `views.py`. Le catalogue `account_templates.py` est une **donnée** (pas de modèle BDD) — extensible sans migration, sans éditeur (YAGNI).
- Contexte on-premise : aucun CDN, TomSelect déjà vendorisé (`static/vendor/tom-select/`).

### References
- [Source: _bmad-output/implementation-artifacts/6-2-0-gouvernance-it-maker-checker.md] — flux Maker/Checker, double-hachage, groupe approbateur.
- [Source: code/apps/users/models.py] — `User.Role`, `Department`, `OrgUnitType`, `UserProvisioningRequest`.
- [Source: code/apps/workflow/selectors.py#get_recommendations_for_user] — ADMIN fail-closed, RBAC AUDIT.
- [Source: C:/Users/Davel/.claude/plans/j-ai-un-soucis-et-peaceful-anchor.md] — plan d'implémentation détaillé approuvé.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (Claude Code)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed — comprehensive developer guide created.
- Implémentation réalisée. Doctrine respectée (Audit jamais audité ; ADMIN système pur ; aucun nouveau booléen de capacité).
- 3 edge cases traités : garde `Department.clean()` (couvre l'édition), profil ADMIN soumet un dept vide (rattaché côté service), synchro TomSelect via API.
- Vérif : 196 tests `apps.users` OK (dont 13 nouveaux `test_story_7_2`). `apps.workflow` : seules les 10 erreurs préexistantes `test_import_excel` (feature WIP 6-5, uploads BytesIO) — sans rapport. `check` + `makemigrations --check` OK. Migrations 0010/0011 appliquées sur la base dev, seed vérifié.

### File List

**Nouveaux**
- `code/apps/users/account_templates.py`
- `code/apps/users/migrations/0010_admin_entity_fields.py`
- `code/apps/users/migrations/0011_seed_admin_org_unit.py`
- `code/apps/users/management/__init__.py`
- `code/apps/users/management/commands/__init__.py`
- `code/apps/users/management/commands/bootstrap_admin.py`
- `code/apps/users/tests/test_story_7_2.py`

**Modifiés**
- `code/apps/users/models.py` (Department.is_system + clean ; User.job_title ; UserProvisioningRequest.requested_* + clean)
- `code/apps/users/forms.py` (champs requested_* ; exclude is_system ; validation croisée)
- `code/apps/users/services.py` (propagation approve ; gardes is_system/SUPPORT ; bootstrap_create_admin ; dept système ADMIN)
- `code/apps/users/selectors.py` (count_business_departments)
- `code/apps/users/views.py` (onboarding context ; templates context)
- `code/templates/admin_it/dashboard.html` (bandeau onboarding)
- `code/templates/admin_it/partials/provisioning_create_modal.html` (sélecteur de profil + synchro TomSelect)
- `code/templates/admin_it/partials/organigramme_node.html` (badge Système)
- `code/templates/admin_it/partials/organigramme_drilldown.html` (badge + suppression neutralisée)
- `code/apps/users/tests/test_admin_it.py` + `test_models.py` (baseline ajusté au seed)
