# Story 6.2.0: Gouvernance IT Maker/Checker + TomSelect

Status: ready-for-dev

<!-- Refonte des stories 1.4, 1.5 et 1.7. L'Audit Interne perd la gestion de l'organigramme et des comptes au profit du Support IT, via un flux Maker/Checker validé par le groupe « Administrateurs Sentinel ». Le flag is_audit_admin reste sous auto-gouvernance Audit exclusive. -->

## Story

As a **Responsable Sécurité / Gouvernance (BICEC)**,
I want **que la création des comptes et la gestion de l'organigramme soient centralisées par le Support IT via un flux Maker/Checker (l'IT saisit, un Administrateur valide), et que la sélection des unités organisationnelles devienne ergonomique**,
so that **l'Audit Interne soit déchargé de la gestion des identités, avec un contrôle à quatre yeux strict, une traçabilité parfaite (AuditLog append-only), et une expérience utilisateur fluide lors du choix d'une direction.**

**Contexte produit** — Aujourd'hui le Support IT crée des comptes « coquilles vides » (Story 1.4) et l'Audit Interne attribue ensuite les rôles et périmètres (Stories 1.5 / 1.7, via `is_audit_admin`). La direction veut **inverser cette responsabilité** : c'est désormais l'IT qui gère le cycle de vie des identités et de l'organigramme, sous un contrôle Maker/Checker. L'Audit Interne conserve **uniquement** ce qui relève de son métier : ses référentiels (sources de recommandation) et l'auto-gouvernance de ses propres administrateurs (`is_audit_admin`).

En parallèle, le sélecteur de département actuel (un `<select>` plat mélangeant directions, services, agences) est remplacé par **TomSelect** (recherche live + regroupement `<optgroup>`), vendorisé localement (contrainte bancaire : aucun CDN).

## Acceptance Criteria

### Phase A — Maker/Checker provisioning IT

1. **AC1 — Création de requête (Maker)**
   - **Given** un Admin IT (`role == ADMIN`, ou staff/superuser)
   - **When** il soumet le formulaire de provisioning (identité + rôle + département + mot de passe initial)
   - **Then** une `UserProvisioningRequest` est créée à l'état `PENDING`
   - **And** **aucun `User` réel** n'est créé en base
   - **And** le mot de passe initial est haché via `make_password` **avant** persistance dans `hashed_initial_password` (jamais stocké en clair)
   - **And** une entrée `AuditLog` est émise (`action=CREATE`, `content_type="UserProvisioningRequest"`)
   - **And** **tous** les membres du groupe « Administrateurs Sentinel » reçoivent une notification in-app `PROVISIONING_REQUESTED` (idempotente par destinataire).

2. **AC2 — Validation et création du compte (Checker)**
   - **Given** un membre du groupe « Administrateurs Sentinel » (checker)
   - **When** il approuve une demande `PENDING`
   - **Then** sous `transaction.atomic()`, le `User` est créé avec le rôle et le département demandés
   - **And** le mot de passe du `User` reçoit **directement** la valeur déjà hachée `hashed_initial_password` (PAS via `create_user(password=…)`, pour éviter le double-hachage — voir Dev Notes)
   - **And** l'unicité de `requested_username` (et `requested_email`) est **revalidée contre tous les `User`** juste avant création
   - **And** le statut de la demande passe à `APPROVED`, avec `reviewed_by` et `reviewed_at` renseignés
   - **And** **deux** entrées `AuditLog` sont émises : `content_type="User"` (`CREATE`) **et** `content_type="UserProvisioningRequest"` (`UPDATE` → APPROVED)
   - **And** l'Admin IT (maker) est notifié `PROVISIONING_APPROVED`.

3. **AC3 — Rejet et annulation**
   - **Given** une demande `PENDING`
   - **When** un checker la rejette **avec un motif obligatoire**
   - **Then** le statut passe à `REJECTED`, `rejection_reason` est persisté, **aucun `User` n'est créé**, un `AuditLog` est émis, et le maker est notifié `PROVISIONING_REJECTED`
   - **And** une demande `REJECTED` ne peut pas être recyclée (la re-soumission impose une nouvelle requête)
   - **When** l'Admin IT auteur annule lui-même sa propre demande `PENDING`
   - **Then** le statut passe à `CANCELLED` (seul le maker de la demande peut l'annuler ; un autre utilisateur → 403/refus), avec `AuditLog`.

4. **AC4 — Coupure Audit + re-gating IT + édition directe (A2)**
   - **Given** les vues de gestion des habilitations, des départements et de l'organigramme
   - **When** un auditeur `is_audit_admin=True` (mais non membre du groupe IT) tente d'y accéder
   - **Then** il reçoit un **403** : l'accès est désormais réservé aux membres du groupe « Administrateurs Sentinel » (ou superuser)
   - **And** les **modifications ultérieures** sur un compte existant (rôle/département) se font en **édition directe** par un membre du groupe via `HabilitationEditView` (pas de second Maker/Checker — décision A2)
   - **And** appeler `assign_role()` en tant que membre du groupe non-auditeur **ne lève plus** `PermissionDenied` (le garde interne du service est basé sur l'appartenance au groupe, pas sur `can_manage_users`).

5. **AC5 — Auto-gouvernance Audit exclusive (`is_audit_admin`)**
   - **Given** la vue `HabilitationToggleAdminView` (attribution/révocation du flag `is_audit_admin`)
   - **When** un membre du groupe IT (non-auditeur) tente d'y accéder
   - **Then** il reçoit un **403** : cette vue **reste** sous `AuditAdminRequiredMixin` (`can_manage_users`), non re-gatée vers l'IT
   - **And** l'Audit Interne dispose d'un **point d'entrée dédié minimal** dans sa sidebar (liste des auditeurs internes + toggle du flag), découplé de la liste d'habilitation passée à l'IT
   - **And** les référentiels métier Audit (`RecommendationSource`, app `workflow`) restent gouvernés par `is_audit_admin` (inchangés).

### Phase B — UX sélecteurs organisationnels (TomSelect)

6. **AC6 — TomSelect vendorisé sur les sélecteurs organisationnels**
   - **Given** un formulaire contenant un sélecteur organisationnel (`RecommendationForm`, `DepartmentForm`, `UserProvisioningRequestForm`)
   - **When** la page est rendue **ou** mise à jour via un swap HTMX
   - **Then** TomSelect est activé, chargé **localement** depuis `static/vendor/tom-select/` (aucun appel CDN)
   - **And** les options sont regroupées en `<optgroup>` par direction mère (libellé hiérarchique / breadcrumb)
   - **And** la recherche en texte libre (nom **ou** code, ex. « DOP ») filtre instantanément la liste
   - **And** après un `htmx:afterSwap`, les sélecteurs nouvellement injectés sont ré-initialisés (pas de widget « mort »).

### Phase C — Interfaces sobres & modale de création

7. **AC7 — Modale de création + design institutionnel sobre**
   - **Given** la file de validation (`ProvisioningRequestListView`)
   - **When** l'Admin IT clique sur « Nouvelle demande »
   - **Then** le formulaire de création s'ouvre dans une **modale** (overlay + panneau centré), accessible (`role="dialog"`, `aria-modal="true"`, focus-trap, fermeture Échap + clic overlay), animée via `animate-slide-up`
   - **And** la soumission HTMX réussie ferme la modale, rafraîchit la liste (OOB swap) et affiche un toast `sentinel.notify` — sans rechargement de page
   - **And** les écrans de gouvernance (modale, file, liste) respectent les **directives design sobres** (voir Dev Notes › Directives Design) : neutres dominants, `sentinel-orange` réservé à **une seule** action primaire par vue, **aucun** effet décoratif (orbs, gradients héros, glow, glass tape-à-l'œil), badges de statut pâles, densité administrative stricte
   - **And** les composants existants (`components/status_badge`, `components/alert`, `components/form`) sont réutilisés plutôt que recréés.

## Tasks / Subtasks

> ⚠️ **Ordre d'exécution** : voir la section dédiée plus bas. La numérotation des tasks suit la cohérence logique, pas l'ordre d'implémentation.

- [ ] **Task 1 — Settings & groupe approbateurs** (AC1, AC4)
  - [ ] Subtask 1.1 : Ajouter `PROVISIONING_APPROVER_GROUP_NAME = "Administrateurs Sentinel"` dans `code/config/settings/base.py`.
  - [ ] Subtask 1.2 : Créer la data migration `code/apps/users/migrations/0009_create_approvers_group.py` :
    - Utiliser `apps.get_model("auth", "Group")` (couplage modèle vivant interdit en migration).
    - `Group.objects.get_or_create(name="Administrateurs Sentinel")` (idempotent).
    - `dependencies = [("users", "0008_create_user_provisioning_request"), ("auth", "__first__")]` — la table `auth_group` doit exister.
    - `reverse_code` : suppression du groupe par nom.

- [ ] **Task 2 — Modèle `UserProvisioningRequest`** (AC1, AC2, AC3)
  - [ ] Subtask 2.1 : Créer le modèle dans `code/apps/users/models.py` (après `User`, avant `ExternalMission`) :
    - `id` (UUIDField pk, default=uuid.uuid4, editable=False)
    - `requested_username` (CharField 150), `requested_first_name` (CharField 150, blank), `requested_last_name` (CharField 150, blank), `requested_email` (EmailField)
    - `requested_role` (CharField max_length=10, `choices=` = **tous** les `User.Role.choices` incluant `EXT` — constante `PROVISIONABLE_ROLE_CHOICES = User.Role.choices`)
    - `requested_department` (FK `Department`, `on_delete=PROTECT`, `null=True, blank=True`)
    - `hashed_initial_password` (CharField max_length=128) — stocke le hash Django, **jamais le clair**
    - `status` (CharField, `TextChoices` : `PENDING`/`APPROVED`/`REJECTED`/`CANCELLED`, défaut `PENDING`)
    - `rejection_reason` (TextField, blank, default="")
    - `requested_by` (FK User, `on_delete=PROTECT`, related_name="provisioning_requests_made")
    - `reviewed_by` (FK User, `on_delete=PROTECT`, null=True, blank=True, related_name="provisioning_requests_reviewed")
    - `reviewed_at` (DateTimeField, null=True, blank=True)
    - `created_at` (DateTimeField, auto_now_add=True)
    - **Champs mission externe (optionnels en base, conditionnellement requis)** :
      - `mission_organization` (CharField max_length=100, blank=True, default="")
      - `mission_scope` (TextField, blank=True, default="")
      - `mission_start_date` (DateField, null=True, blank=True)
      - `mission_end_date` (DateField, null=True, blank=True)
    - `Meta` : `ordering = ["-created_at"]`, index sur `status`.
  - [ ] Subtask 2.2 : Méthode `.clean()` :
    - Unicité `requested_username` **contre TOUS les `User`** (`User.objects.filter(username__iexact=...).exists()`) — pas seulement les actifs (contrainte d'unicité globale `AbstractUser` → sinon `IntegrityError` à l'approbation).
    - Unicité `requested_email` contre tous les `User` (règle métier).
    - Cohérence rôle/département : `AUDIT`, `ADMIN` et `EXT` peuvent avoir `requested_department=None` ; les autres rôles exigent un département (aligné sur la sémantique du modèle `User`).
    - Si `requested_role == EXT` : `mission_organization` et `mission_start_date` deviennent **requis** (`ValidationError` sinon) ; `mission_end_date` reste optionnel.
    - Si `requested_role == EXT` et `mission_start_date` et `mission_end_date` renseignées : valider `start_date <= end_date` (calqué sur `ExternalMission.clean()`).
    - ⚠️ **Dette technique documentée** : la liste d'organisations EXT est chargée depuis `RecommendationSource.objects.filter(is_external=True, is_active=True)`. Si l'Audit Admin désactive une source, elle disparaît du formulaire EXT. Acceptable MVP — à isoler dans une future story.
  - [ ] Subtask 2.3 : Générer `code/apps/users/migrations/0008_create_user_provisioning_request.py` via `makemigrations users`.
  - [ ] **Aucune contrainte d'unicité DB** sur `requested_username` / `requested_email` (plusieurs requêtes peuvent coexister ; l'unicité est applicative, vérifiée en `clean()` + à l'approbation).

- [ ] **Task 3 — Notifications provisioning** (AC1, AC2, AC3)
  - [ ] Subtask 3.1 : Ajouter à `Notification.Type` (`code/apps/notifications/models.py`) :
    - `PROVISIONING_REQUESTED = "PROVISIONING_REQUESTED", _("Demande de compte à valider")`
    - `PROVISIONING_APPROVED = "PROVISIONING_APPROVED", _("Compte validé")`
    - `PROVISIONING_REJECTED = "PROVISIONING_REJECTED", _("Demande de compte rejetée")`
    - (tous ≤ 30 caractères, OK avec `max_length=30`)
  - [ ] Subtask 3.2 : `makemigrations notifications` (migration de changement de `choices` — état Django, no-op SQL).
  - [ ] Subtask 3.3 : Ajouter un helper `notify_group(*, group_name, notification_type, title, key_prefix, url="", body="", is_urgent=False)` dans `code/apps/notifications/services.py` :
    - Boucle sur `User.objects.filter(groups__name=group_name)`, appelle `emit_notification(recipient=member, idempotency_key=f"{key_prefix}:{member.pk}", ...)`.

- [ ] **Task 4 — Services Maker/Checker + AuditLog** (AC1, AC2, AC3)
  - [ ] Dans `code/apps/users/services.py`, ajouter (gabarit : `assign_role`, `create_shell_account_with_audit`) :
    - `create_provisioning_request(*, maker, cleaned_data, ip_address=None) -> UserProvisioningRequest`
      - Hache le mot de passe initial via `make_password` (choix : **dans le service**, voir Dev Notes), crée la requête `PENDING`.
      - `AuditLog(action=CREATE, content_type="UserProvisioningRequest", object_id=req.pk, ...)`.
      - `notify_group(group_name=settings.PROVISIONING_APPROVER_GROUP_NAME, notification_type=PROVISIONING_REQUESTED, key_prefix=f"PROVISIONING_REQUESTED:{req.pk}", url=<detail url>)`.
    - `approve_provisioning_request(*, request, checker, ip_address=None) -> User`
      - **`with transaction.atomic()`** :
        - Re-valider l'unicité username/email contre tous les `User` (lever `ValidationError` si collision apparue entre-temps).
        - `user = User(username=..., email=..., first_name=..., last_name=..., role=request.requested_role, department=request.requested_department, is_external=(request.requested_role == User.Role.EXT))` ; `user.password = request.hashed_initial_password` ; `user.save()`.
        - Si `requested_role == EXT` : créer aussi `ExternalMission(auditor=user, organization=request.mission_organization, scope_description=request.mission_scope, start_date=request.mission_start_date, end_date=request.mission_end_date)` dans la même `transaction.atomic()`. ⚠️ Créer **après** le `User.save()` car `ExternalMission.auditor` a `limit_choices_to={"is_external": True, "role": EXT}` — la contrainte est vérifiée au moment du `save()` de la mission.
        - AuditLog supplémentaire si EXT : `content_type="ExternalMission"` (CREATE).
        - `request.status = APPROVED ; request.reviewed_by = checker ; request.reviewed_at = now() ; request.save(...)`.
        - **Deux** `AuditLog` : `content_type="User"` (CREATE) + `content_type="UserProvisioningRequest"` (UPDATE).
      - `emit_notification(recipient=request.requested_by, notification_type=PROVISIONING_APPROVED, idempotency_key=f"PROVISIONING_APPROVED:{request.pk}", ...)`.
    - `reject_provisioning_request(*, request, checker, reason, ip_address=None) -> UserProvisioningRequest`
      - `reason` obligatoire (lever `ValueError`/`ValidationError` si vide) ; `status=REJECTED`, `reviewed_by/at` ; `AuditLog` ; notifie le maker `PROVISIONING_REJECTED`.
    - `cancel_provisioning_request(*, request, maker, ip_address=None) -> UserProvisioningRequest`
      - Vérifier `request.requested_by_id == maker.pk` **et** `request.status == PENDING` (sinon `PermissionDenied`/`ValueError`) ; `status=CANCELLED` ; `AuditLog`.

- [ ] **Task 5 — Mixins, permissions & garde interne `assign_role`** (AC4, AC5)
  - [ ] Subtask 5.1 : Ajouter un helper `user_is_provisioning_approver(user) -> bool` (`code/apps/users/mixins.py` ou `selectors.py`) : `user.is_superuser or user.groups.filter(name=settings.PROVISIONING_APPROVER_GROUP_NAME).exists()`.
  - [ ] Subtask 5.2 : Créer `ProvisioningApproverRequiredMixin` dans `code/apps/users/mixins.py` (calqué sur `AuditAdminRequiredMixin` ligne 15) → 403 si `not user_is_provisioning_approver(request.user)`.
  - [ ] Subtask 5.3 : **Garde interne — uniquement `assign_role`** : remplacer dans `assign_role()` (`services.py:40`) le test `if not (performed_by.can_manage_users or performed_by.is_superuser)` par `if not user_is_provisioning_approver(performed_by)`.
    - ⚠️ **NE PAS** modifier `create/update/soft_delete_department_with_audit` ni `create/update/toggle_org_unit_type` : ces services **n'ont aucun garde interne** (ils s'appuient sur le mixin de la vue). NE PAS toucher `toggle_audit_admin` (ligne 97, reste `can_manage_users`).
  - [ ] Subtask 5.4 : **Re-gater vers `ProvisioningApproverRequiredMixin`** (remplacer `AuditAdminRequiredMixin`) les vues de `code/apps/users/views.py` :
    - `HabilitationListView`, `HabilitationEditView`, `OrganigrammeListView`, `DepartmentCreateView`, `DepartmentEditView`, `DepartmentDeleteView`, `DepartmentSearchView`, `OrgUnitTypeListView`, `OrgUnitTypeCreateView`, `OrgUnitTypeEditView`, `OrgUnitTypeToggleView`.
    - **Exclure** (restent `AuditAdminRequiredMixin`) : `HabilitationToggleAdminView` + toutes les vues `RecommendationSource*` (app `workflow`).

- [ ] **Task 6 — Vues, formulaire & templates Maker/Checker** (AC1, AC2, AC3)
  - [ ] Subtask 6.1 : `UserProvisioningRequestForm` (`code/apps/users/forms.py`, ModelForm sur `UserProvisioningRequest`) :
    - Fields : `requested_username`, `requested_first_name`, `requested_last_name`, `requested_email`, `requested_role`, `requested_department`, + un champ `password` **non-modèle** (`forms.CharField(widget=PasswordInput)`).
    - `requested_role` : choices `PROVISIONABLE_ROLE_CHOICES` = **tous les rôles** (AUDIT, DM, ETP, DG, ADMIN, EXT).
    - Le clair n'est **pas** stocké tel quel : le service appelle `make_password`. Le form expose le clair dans `cleaned_data["password"]` ; **ne pas** remplir `hashed_initial_password` côté form (séparation form=validation / service=hash).
    - Widget `requested_department` : classe `js-tomselect` (Task 8).
    - **Champs EXT conditionnels** (affichés via Alpine.js `x-show="$refs.roleSelect.value === 'EXT'"`) :
      - `mission_organization` : `ChoiceField` dont les choix = `[(src.label, src.label) for src in RecommendationSource.objects.filter(is_external=True, is_active=True)]` — on stocke le **label** (string) dans le modèle CharField, pas une FK.
      - `mission_scope` : `Textarea`, optionnel côté form (rendu obligatoire par `.clean()` du modèle si EXT).
      - `mission_start_date` : `DateInput`, optionnel côté form.
      - `mission_end_date` : `DateInput`, optionnel.
    - Le form expose ces champs mais **ne les inclut pas dans les `fields` du ModelForm** standard — les ajouter comme champs non-modèle (`forms.CharField/DateField`) et les passer au service dans `cleaned_data`.
  - [ ] Subtask 6.2 : `ProvisioningRequestCreateView` (maker = `AdminRequiredMixin`, `mixins.py:36`) — **remplace** `ITUserCreateView` (`views.py:491`). Appelle `services.create_provisioning_request`.
  - [ ] Subtask 6.3 : `ProvisioningRequestListView` (checker = `ProvisioningApproverRequiredMixin`) — file `PENDING` + historique (filtres status).
  - [ ] Subtask 6.4 : `ProvisioningRequestApproveView` / `RejectView` / `CancelView` (POST, partials HTMX, `HX-Trigger` notify). Approve/Reject = `ProvisioningApproverRequiredMixin` ; Cancel = maker auteur (vérif dans le service).
  - [ ] Subtask 6.5 : URLs dans `code/apps/users/urls.py` (namespace `auth:`) :
    - `path("admin/provisioning/", ProvisioningRequestListView.as_view(), name="provisioning-list")`
    - `path("admin/provisioning/create/", ProvisioningRequestCreateView.as_view(), name="provisioning-create")`
    - `path("admin/provisioning/<uuid:pk>/approve/", ...)` / `reject/` / `cancel/`
    - (retirer/rediriger l'ancienne route `ITUserCreateView` selon Subtask 6.2).
  - [ ] Subtask 6.6 : Templates sous `code/templates/admin_it/` : `provisioning_list.html` (file + bouton « Nouvelle demande »), `partials/provisioning_create_modal.html` (form **en modale** Alpine.js + HTMX, focus-trap `x-trap`, `x-cloak`, `animate-slide-up`), `partials/provisioning_row.html`, `partials/provisioning_reject_modal.html` (sous-modale exigeant le motif). Réutiliser `components/alert`, `components/status_badge`, `components/form`. Respecter les **Directives Design** (Dev Notes). Succès POST → `HX-Trigger` ferme la modale + OOB swap de la ligne/liste + `sentinel.notify`.
  - [ ] Subtask 6.7 : Marquer `ITUserCreationForm` + `create_shell_account_with_audit` **obsolètes** (docstring + conserver pour bootstrap superuser, ou retirer + nettoyer `test_admin_it.py`). `RoleRequiredMiddleware` + page `auth:pending` **restent** (legacy/EXT) : le chemin IT ne crée plus de coquilles, mais le concept reste pour les comptes EXT et l'existant.

- [ ] **Task 7 — Point d'entrée Audit dédié (toggle is_audit_admin)** (AC5)
  - [ ] Subtask 7.1 : Ajouter (si absente) une vue liste minimale `AuditAdminMembersView` (`AuditAdminRequiredMixin`) listant les `User` `role=AUDIT` avec le toggle `HabilitationToggleAdminView`. Sinon, exposer directement le toggle dans une page Audit dédiée.
  - [ ] Subtask 7.2 : `code/templates/partials/sidebar_audit.html` : retirer les entrées habilitation/organigramme (parties chez l'IT) ; ajouter l'entrée « Administrateurs Audit » (toggle flag). Conserver la section « Configuration » (Sources) inchangée.
  - [ ] Subtask 7.3 : `code/templates/partials/sidebar_admin.html` : ajouter les entrées « Provisioning » (liste + création) et « Organigramme » / « Types d'unité » (déplacées de l'Audit vers l'IT).

- [ ] **Task 8 — TomSelect vendorisé** (AC6)
  - [ ] Subtask 8.1 : Déposer `tom-select.complete.min.js` + `tom-select.min.css` dans `code/static/vendor/tom-select/` (aucun CDN).
  - [ ] Subtask 8.2 : `code/templates/base.html` : `<link>` CSS dans `<head>` ; `<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}" defer></script>` après Alpine (ligne ~42).
  - [ ] Subtask 8.3 : `code/static/js/sentinel.js` : fonction `initTomSelect(root=document)` → `root.querySelectorAll('.js-tomselect:not(.tomselected)')` → `new TomSelect(el, { … })`. Appeler sur `DOMContentLoaded` **et** sur `document.body.addEventListener('htmx:afterSwap', e => initTomSelect(e.target))`.
  - [ ] Subtask 8.4 : Appliquer la classe `js-tomselect` et le rendu `<optgroup>` (par direction mère) sur :
    - `RecommendationForm` : `department` + `controlled_department` (`workflow/forms.py:128-129`).
    - `DepartmentForm` : `parent` (`users/forms.py:111`) — conserver `_parent_label` (fil d'Ariane).
    - `UserProvisioningRequestForm` : `requested_department`.
  - [ ] Subtask 8.5 : Construire les `<optgroup>` via un libellé hiérarchique. Réutiliser `get_department_breadcrumb()` (`selectors.py:86`) / `_parent_label` (`users/forms.py:137`) pour grouper par racine.

- [ ] **Task 9 — Tests** (AC1-AC6)
  - [ ] Subtask 9.1 : Créer `code/apps/users/tests/test_provisioning.py` :
    - `test_create_request_creates_no_user` — POST maker → `UserProvisioningRequest` PENDING, `User.objects.count()` inchangé, password **haché** (pas en clair).
    - `test_create_request_notifies_group` — chaque membre du groupe reçoit `PROVISIONING_REQUESTED`.
    - `test_approve_creates_user_atomically` — approbation → `User` créé, `status=APPROVED`, **2 AuditLog**, maker notifié.
    - `test_approve_password_is_usable` — `user.check_password(<clair saisi>)` est **True** (valide le non-double-hachage).
    - `test_reject_requires_reason` — rejet sans motif → erreur ; avec motif → REJECTED + notif maker.
    - `test_cancel_only_by_maker` — un autre user ne peut pas annuler ; le maker oui (PENDING uniquement).
    - `test_approve_duplicate_username_fails` — collision username à l'approbation → `ValidationError`, pas de `User` créé.
    - `test_approver_required_403` — non-membre du groupe sur la liste/approbation → 403.
    - `test_ext_provisioning_creates_user_and_mission` — approbation EXT → `User` (`is_external=True`, `role=EXT`) + `ExternalMission` créés atomiquement ; 3 AuditLog (User CREATE + Request APPROVED + Mission CREATE).
    - `test_ext_requires_mission_fields` — `clean()` rejette si `role=EXT` sans `mission_organization` ou `mission_start_date`.
    - `test_ext_mission_dates_coherence` — `start_date > end_date` → `ValidationError`.
  - [ ] Subtask 9.2 : Adapter les tests existants à la coupure :
    - `test_habilitation.py` : l'accès passe du contexte « audit admin » au contexte « membre du groupe » ; `HabilitationToggleAdminView` reste Audit.
    - `test_services.py` : `assign_role` autorisé pour membre du groupe non-auditeur ; refusé sinon. `toggle_audit_admin` inchangé.
    - `test_admin_it.py` : `ITUserCreateView` → `ProvisioningRequestCreateView` (plus de shell account direct).
    - `test_middleware.py` : `RoleRequiredMiddleware` inchangé.
  - [ ] Subtask 9.3 : Vérifier/adapter `code/apps/users/management/commands/audit_sentinel_security.py` (lit `can_manage_users`/`is_audit_admin`) — s'assurer que l'audit sécurité tient compte du groupe approbateur.

- [ ] **Task 10 — Validation**
  - [ ] `python manage.py migrate --check` puis `migrate` ; confirmer la création du groupe « Administrateurs Sentinel ».
  - [ ] `python manage.py test apps.users apps.notifications apps.workflow --verbosity=2`.
  - [ ] `ruff check .` / `ruff format .`.
  - [ ] Manuel : maker crée une demande → **aucun `User`** + notifs groupe ; checker approuve → `User` créé + login OK avec le mot de passe initial + notif maker ; rejet sans motif → erreur ; Audit ne voit plus habilitation/organigramme mais garde le toggle admin ; TomSelect actif (recherche 3 lettres + optgroups) y compris après swap HTMX.

## Ordre d'exécution recommandé

1. **Task 2 + Task 1** — modèle `UserProvisioningRequest` + migration `0008`, puis data migration groupe `0009` (dépend de 0008).
2. **Task 3 + Task 4** — types de notif + migration notifications, puis services Maker/Checker (AuditLog + notif).
3. **Task 5** — helper + `ProvisioningApproverRequiredMixin` + garde interne `assign_role` + re-gating des vues.
4. **Task 6 + Task 7** — vues/forms/templates provisioning (remplace `ITUserCreateView`) + point d'entrée Audit dédié + sidebars.
5. **Task 9** — tests provisioning + adaptation de l'existant.
6. **Task 8** — TomSelect (vendor + init HTMX + widgets + optgroups).
7. **Task 10** — validation complète.

## Dev Notes

### Architecture technique (vérifiée dans le code)

- **AuditLog = modèle maison** (`code/apps/audit/models.py:17`), append-only, alimenté **manuellement** : `AuditLog.objects.create(action=..., user=..., content_type="<str>", object_id=<uuid>, changes={...JSON-safe...}, description=..., ip_address=...)`. **Aucun `django-auditlog`**. `content_type` est un **CharField** (pas un FK `ContentType`) → utiliser les littéraux `"UserProvisioningRequest"` et `"User"`.
- **Notifications** (`code/apps/notifications/services.py:12`) : `emit_notification(*, recipient, notification_type, title, idempotency_key, recommendation=None, body="", url="", is_urgent=False)` — idempotent via `get_or_create(idempotency_key=...)`, retourne `None` si déjà émise. `notification_type` : CharField `max_length=30`. Pas de helper « groupe » existant → on en crée un (`notify_group`) qui boucle.
- **`is_audit_admin` — coupure chirurgicale** : le flag perd la gestion users/organigramme (vues re-gatées vers le groupe IT), mais **conserve** (1) l'auto-gouvernance des admins Audit (`HabilitationToggleAdminView`, service `toggle_audit_admin`) et (2) les référentiels métier (`RecommendationSource`, `workflow/models.py:82`). La propriété `can_manage_users` (`models.py:273`) **reste** utilisée par ces deux usages — ne pas la supprimer.

### 🚨 Pièges techniques

#### Piège 1 — Double-hachage du mot de passe à l'approbation (bloquant login)
Le mot de passe est **déjà haché** (`make_password`) et stocké dans `hashed_initial_password`. À l'approbation, **NE PAS** faire `User.objects.create_user(..., password=request.hashed_initial_password)` : `create_user` re-hacherait le hash → login impossible. Pattern correct :
```python
user = User(
    username=request.requested_username,
    email=request.requested_email,
    first_name=request.requested_first_name,
    last_name=request.requested_last_name,
    role=request.requested_role,
    department=request.requested_department,
)
user.password = request.hashed_initial_password  # hash déjà calculé → affectation directe
user.save()
```
Test de garde : `test_approve_password_is_usable` (`user.check_password(<clair>)` doit être `True`).

#### Piège 2 — Garde interne `can_manage_users` UNIQUEMENT dans `assign_role`
Après vérification de `services.py`, **seul `assign_role()` (ligne 40)** contient un garde interne `can_manage_users` parmi les services de gestion. Les services département (127-194) et orgtype (197-283) **n'ont aucun garde interne**. → Modifier **uniquement** `assign_role`. Modifier les autres serait un no-op trompeur. Le re-gating des opérations département/orgtype passe **exclusivement** par le mixin des vues (Task 5.4).

#### Piège 3 — Unicité username contre TOUS les `User` (pas seulement actifs)
`AbstractUser.username` porte une contrainte d'unicité **globale** en base. Le `clean()` du modèle **et** la revalidation à l'approbation doivent vérifier contre **tous** les `User` (`User.objects.filter(username__iexact=...)`), sinon un username tenu par un compte inactif passe la validation mais lève `IntegrityError` au `save()`.

#### Piège 4 — `AuditLog.changes` est un JSONField → jamais d'instance modèle
Ne jamais stocker une instance (`User`, `Department`) dans `changes`. Utiliser `str(pk)` ou un champ scalaire. Ex. : `changes={"role": [None, request.requested_role], "department": [None, str(request.requested_department_id) if request.requested_department_id else None]}`.

#### Piège 5 — Ré-init TomSelect après swap HTMX
Un sélecteur injecté par HTMX (modale, partial) n'est pas initialisé au `DOMContentLoaded`. Écouter `htmx:afterSwap` et appeler `initTomSelect(e.target)` ; garder une garde anti-double-init (`.tomselected` / `:not(.ts-wrapper)`).

### Directives Design (UI/UX) — sobriété institutionnelle

**Principe** : ces écrans sont des outils de **gouvernance bancaire**, pas des pages marketing. Objectif : austérité maîtrisée, densité administrative, lisibilité, zéro effet « waouh ». **Réutiliser les tokens existants** (`code/tailwind.config.js`) — ne **jamais** introduire de nouvelle couleur ni de police.

**Palette (neutres dominants)**
- Fond : `bg-surface-base` (#FAF7F4) ; cartes/tableaux : `bg-surface-card` (#FFFFFF) ; séparateurs **fins 1px** `border-subtle` (#E8DFD6) — sur ces écrans administratifs, les filets discrets sont **autorisés** (contrairement au login « no-line »).
- Texte : `text-text-primary` (titres), `text-text-secondary` (libellés), `text-text-muted` (métadonnées/dates).
- **Accent** : `sentinel-orange` (#E87722) réservé à **une seule** action primaire par vue (« Soumettre la demande », « Approuver »). Tout le reste en neutres ou ghost.
- Statuts (badges **pâles**, jamais saturés) : fond clair + texte/point coloré — `PENDING` → `bg-sentinel-orange-light` + `text-status-pending` ; `APPROVED` → vert pâle + `text-status-approved` ; `REJECTED` → rouge pâle + `text-status-rejected` ; `CANCELLED` → gris neutre. S'appuyer sur `components/status_badge` existant.

**Interdits sur ces écrans** (sinon effet « généré par IA ») : `login-orb`/blobs, `bg-gradient-hero`, `bg-gradient-primary` décoratif, `shadow-glow`, `text-gradient-primary`, glassmorphism (`.glass`) ostentatoire, dégradés violets, emojis, ombres noires lourdes, symétrie carte-centrée générique.

**Typographie** : titres `font-heading` (Manrope, tracking -0.02em déjà global) ; corps `font-body` (Inter) ; libellés de formulaire Inter 500 `text-sm text-text-secondary` ; colonnes dates/compteurs en `tabular-nums`.

**Élévation & rayons** : `shadow-premium-sm` pour cartes/tableaux ; `shadow-premium-lg` **uniquement** pour la modale ; rayons `rounded-md`/`rounded-lg` (éviter `rounded-xl` généralisé).

**Modale de création** (Alpine.js + HTMX) :
- Overlay `bg-on-surface/40` (pas de noir pur), léger `backdrop-blur-sm` ; panneau `bg-surface-card max-w-lg rounded-lg shadow-premium-lg`, entrée `animate-slide-up`.
- A11y : `role="dialog" aria-modal="true"`, `x-trap`, `x-cloak`, fermeture **Échap** + clic overlay, focus sur le 1er champ à l'ouverture.
- Form : grille **1 colonne**, groupes `space-y-4` ; `requested_department` en TomSelect ; champ mot de passe avec hint « transmis hors-bande à l'utilisateur ».
- Boutons : « Annuler » **ghost** (`text-text-secondary`, bordure au survol) + « Soumettre la demande » **plein** `bg-sentinel-orange` (le seul bouton plein de la modale).

**File de validation (tableau)** : lignes aérées (`py-3`), séparateurs `border-subtle`, zébrage très léger ou nul. Colonnes : Demandeur · Identité · Rôle · Département · Statut (badge) · Date · Actions. Empty state sobre (icône fine + phrase `text-text-muted`, **aucune** illustration colorée). Approuver = bouton plein discret ; Rejeter = ouvre la sous-modale « motif obligatoire ».

### Décisions verrouillées (arbitrage utilisateur)

| Réf | Décision |
|-----|----------|
| **A2** | Création = Maker/Checker ; modifications ultérieures d'un compte actif = **édition directe** par un membre du groupe (pas de second contrôle). |
| **B** | Le **maker** (Admin IT auteur) peut annuler **sa propre** requête `PENDING` (`CANCELLED`). |
| **C** | TomSelect **vendorisé local** (`static/vendor/`), zéro CDN, sur **tous** les sélecteurs organisationnels. |
| **Password** | Saisi par le maker → haché `make_password` avant stockage (`hashed_initial_password`) → affecté directement au `User` à l'approbation → transmis **hors-bande** par l'IT → modifiable ensuite par l'utilisateur. |
| **is_audit_admin** | **Auto-gouvernance Audit exclusive** : `HabilitationToggleAdminView` reste sous `AuditAdminRequiredMixin`, l'IT n'y a pas accès. |

### Patterns existants à réutiliser

- `AuditAdminRequiredMixin` (`code/apps/users/mixins.py:15`) — gabarit pour `ProvisioningApproverRequiredMixin`.
- `AdminRequiredMixin` (`code/apps/users/mixins.py:36`) — garde du maker (`ProvisioningRequestCreateView`).
- `assign_role`, `create_shell_account_with_audit` (`code/apps/users/services.py:19,286`) — gabarit service + AuditLog.
- `emit_notification` (`code/apps/notifications/services.py:12`) — idempotence ; conventions de clés (cf. Story 4.0).
- `get_department_breadcrumb` (`code/apps/users/selectors.py:86`), `DepartmentForm._parent_label` (`code/apps/users/forms.py:137`) — libellés hiérarchiques pour les `<optgroup>`.
- Chargement JS local (`code/templates/base.html:40-42`) — modèle pour vendoriser TomSelect.

### NFR couverts

- **NFR-SEC-05 — AuditLog append-only** : toute étape provisioning (create/approve/reject/cancel) tracée ; double trace à l'approbation.
- **NFR-SEC (SoD / ADR-10 inversé)** : séparation Maker (IT) / Checker (groupe) ; mot de passe jamais en clair ; auto-gouvernance Audit préservée.
- **NFR-PERF-02 — UI < 200 ms** : TomSelect côté client, recherche locale ; partials HTMX conservés.

### Project Structure Notes

**Fichiers à créer :**
- `code/apps/users/migrations/0008_create_user_provisioning_request.py`, `0009_create_approvers_group.py`
- `code/apps/notifications/migrations/000X_provisioning_types.py`
- `code/templates/admin_it/provisioning_list.html`, `partials/provisioning_create_modal.html`, `partials/provisioning_row.html`, `partials/provisioning_reject_modal.html` (design sobre — voir Dev Notes › Directives Design)
- `code/static/vendor/tom-select/tom-select.complete.min.js`, `tom-select.min.css`
- `code/apps/users/tests/test_provisioning.py`

**Fichiers à modifier :**
- `code/config/settings/base.py` (constante groupe)
- `code/apps/users/models.py` (`UserProvisioningRequest` + `PROVISIONABLE_ROLE_CHOICES`)
- `code/apps/users/services.py` (4 services provisioning + garde `assign_role`)
- `code/apps/users/mixins.py` (helper + `ProvisioningApproverRequiredMixin`)
- `code/apps/users/views.py` (vues provisioning + re-gating + point d'entrée Audit)
- `code/apps/users/forms.py` (`UserProvisioningRequestForm` + classe `js-tomselect` sur `DepartmentForm.parent`)
- `code/apps/users/urls.py` (routes provisioning)
- `code/apps/notifications/models.py` (3 `Type`), `code/apps/notifications/services.py` (`notify_group`)
- `code/apps/workflow/forms.py` (classe `js-tomselect` + optgroups sur `department`/`controlled_department`)
- `code/templates/base.html` (assets TomSelect), `code/static/js/sentinel.js` (init + HTMX)
- `code/templates/partials/sidebar_audit.html`, `sidebar_admin.html`
- Tests : `test_habilitation.py`, `test_services.py`, `test_admin_it.py`, `test_middleware.py`, commande `audit_sentinel_security.py`

### References

- `_bmad-output/planning-artifacts/epics.md` — Stories **1.4** (création comptes Admin), **1.5** (assignation profils Audit), **1.7** (délégation `is_audit_admin`) → **supersédées / inversées** par cette story.
- `_bmad-output/implementation-artifacts/4-0-socle-notifications-in-app.md` — pattern `emit_notification` + conventions de clés d'idempotence.
- `_bmad-output/implementation-artifacts/3-7-b-parametrage-metier-sources-organigramme.md` — pattern AuditLog (`content_type` littéral), pièges CRUD, refactor sidebar admin/audit.
- `code/apps/users/mixins.py` — mixins RBAC existants.
- `_bmad-output/implementation-artifacts/6-4-configuration-interim-delegation.md` (backlog) — la **délégation temporelle** du flag admin y est traitée (hors périmètre de 6.2.0).

## Dev Agent Record

### Agent Model Used
*(À compléter pendant l'implémentation dev-story)*

### Debug Log References
*(À compléter — référencer les pièges Dev Notes en cas de régression)*

### Completion Notes List
- **2026-06-06** : Artefact créé (rédaction manuelle, `/create-story` BMAD non disponible dans la session). Story unique combinée (décision user) : Phase A provisioning Maker/Checker + Phase B TomSelect + Phase C UI. Décisions verrouillées A2/B/C + password haché côté maker + `is_audit_admin` auto-gouvernance Audit exclusive. Corrections post-revue intégrées : garde interne ciblé sur `assign_role` seul, unicité username globale, périmètre de re-gating exhaustif (11 vues), 2 AuditLog à l'approbation, EXT hors périmètre.
- **2026-06-06 (EXT)** : Amendement — EXT inclus dans `PROVISIONABLE_ROLE_CHOICES`. Formulaire unique avec champs mission conditionnels (Alpine.js `x-show`). Organisation chargée depuis `RecommendationSource(is_external=True, is_active=True)` — label stocké en CharField. `approve_provisioning_request` crée `ExternalMission` atomiquement si EXT. 3 tests EXT ajoutés. Dette technique documentée (couplage RecommendationSource/organisations EXT).
- **2026-06-06 (UI)** : Phase C ajoutée (AC7) — formulaire de création en **modale** accessible + section « Directives Design » (sobriété institutionnelle, neutres dominants, `sentinel-orange` parcimonieux, zéro effet décoratif), ancrée sur les tokens réels de `tailwind.config.js`. Objectif explicite : interfaces professionnelles, non « générées par IA ».

### File List
*(À compléter pendant l'implémentation dev-story)*
