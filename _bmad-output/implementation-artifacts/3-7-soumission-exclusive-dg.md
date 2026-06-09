# Story 3.7: Soumission Exclusive par la DG

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DG (Direction Générale)**,
I want **soumettre moi-même des preuves directement à l'Audit Interne sur des recommandations critiques de mon périmètre**,
so that **je contourne les niveaux intermédiaires (ETP, circuit DM Review) lorsque cela s'avère stratégiquement nécessaire** (FR33).

## Acceptance Criteria

1. **AC1 — Bouton "Soumettre à l'Audit" visible uniquement pour le DG assigné (FR33)**
   - **Given** une recommandation dont `assigned_dm == request.user` et `request.user.role == "DG"`
   - **And** le statut est `ASSIGNED` ou `IN_PROGRESS`
   - **When** le DG consulte la page de détail de la recommandation
   - **Then** un bouton "Soumettre directement à l'Audit" est visible dans la section actions
   - **And** ce bouton n'est pas visible pour DM, ETP, AUDIT, EXT, ni pour un DG non-assigné à cette recommandation

2. **AC2 — La soumission DG bypass le circuit DM Review (FR33)**
   - **Given** le DG ouvre le panneau "Soumission directe à l'Audit"
   - **When** le DG a uploadé au moins un fichier ou saisi un commentaire et clique "Valider"
   - **Then** un `EvidenceSubmission` est créé/mis à jour avec `status=ACCEPTED`, `submitted_by=DG`, `reviewed_by=DG`, `reviewed_at=now()`
   - **And** le statut de la recommandation passe à `PENDING_AUDIT_REVIEW` via la transition FSM `submit_directly_to_audit()`
   - **And** l'état `PENDING_DM_REVIEW` n'est jamais visité (bypass complet)
   - **And** un toast de confirmation est affiché ("Preuves soumises directement à l'Audit.")

3. **AC3 — Au moins un fichier OU un commentaire est requis**
   - **Given** le panneau DG est ouvert
   - **When** le DG clique "Valider" sans aucun fichier uploadé ET sans commentaire saisi (ou whitespace seul via `comment.strip()`)
   - **Then** le service lève une `ValueError` et la vue retourne HTTP 422
   - **And** un message d'erreur explicite est affiché dans la modale

4. **AC4 — AuditLog : traçabilité de la soumission directe DG**
   - **Given** la soumission directe DG est validée avec succès
   - **When** la transaction est committée
   - **Then** un `AuditLog` est créé avec :
     - `action=AuditLog.Action.TRANSITION`
     - `content_type="Recommendation"`, `object_id=rec.pk`
     - `changes={"status": [source_status, "PENDING_AUDIT_REVIEW"], "submitted_by_dg": True}`
     - `description` mentionnant le DG et la référence de la recommandation
   - **And** l'entrée est visible dans l'historique (drawer + timeline preview) de la fiche

5. **AC5 — RBAC : seul le DG `assigned_dm` peut utiliser ce endpoint (FR33)**
   - **Given** un utilisateur DG qui n'est PAS `assigned_dm` de cette recommandation
   - **When** il tente un POST sur `evidence-submit-dg`
   - **Then** la vue retourne HTTP 403
   - **And** aucun `EvidenceSubmission` ni `AuditLog` n'est créé
   - **Given** un utilisateur avec rôle DM ou ETP (même s'il a accès workflow)
   - **When** il tente un POST sur `evidence-submit-dg`
   - **Then** la vue retourne HTTP 403 (endpoint réservé au rôle DG)

6. **AC6 — Idempotence : pas de double soumission**
   - **Given** la recommandation est déjà en `PENDING_AUDIT_REVIEW` ou `CLOSED_RESOLVED`
   - **When** le DG tente de soumettre à nouveau
   - **Then** le service lève une `ValueError` et la vue retourne HTTP 422
   - **And** le bouton "Soumettre directement à l'Audit" n'est pas affiché si le statut est >= `PENDING_AUDIT_REVIEW`

7. **AC7 — Validations fichiers identiques au flux ETP (NFR-SCA-01 / NFR-SEC-04)**
   - **Given** le DG uploade un fichier dans le panneau
   - **When** le fichier ne respecte pas les règles : magic bytes invalides, taille > **6 Mo unitaire**, type MIME non autorisé, ou **> 5 fichiers** au total
   - **Then** une erreur de validation est retournée (HTTP 422)
   - **And** aucun fichier n'est persisté en base
   - **And** XLSM est strictement interdit (NFR-SEC-04)

8. **AC8 — L'Audit voit la soumission DG dans le panneau preuves**
   - **Given** la recommandation est en `PENDING_AUDIT_REVIEW` après soumission DG
   - **When** un utilisateur AUDIT consulte la page de détail
   - **Then** la soumission (fichiers + commentaire DG) est visible dans le panneau preuves
   - **And** les fichiers sont téléchargeables
   - **And** le nom du DG soumettant est affiché (`submitted_by`)

9. **AC9 — Limitation MVP : pas de suppléance entre DG et DGA (BICEC — Option 1)**
   - **Given** BICEC a deux comptes avec rôle `DG` (le DG et le DGA)
   - **When** le DGA consulte une recommandation dont `assigned_dm` est le DG (ou inversement)
   - **Then** le bouton "Soumettre directement à l'Audit" n'est PAS visible
   - **And** un POST direct sur le endpoint retourne HTTP 403 (AC5 s'applique)
   - **Note** : Cette limitation est **volontaire au MVP**. Une évolution future (flag `is_dga` ou modèle de suppléance) pourrait permettre l'héritage de permissions sans casser les ACs actuelles.

## Tasks / Subtasks

- [x] Task 1 : Backend — Modèle FSM (AC2, AC6)
  - [x] Subtask 1.1 : Ajouter FSM transition `submit_directly_to_audit()` dans `Recommendation` (`code/apps/workflow/models.py`)
    - `@transition(field=status, source=[Status.ASSIGNED, Status.IN_PROGRESS], target=Status.PENDING_AUDIT_REVIEW)`
    - Docstring : "Transition directe DG → PENDING_AUDIT_REVIEW (Story 3.7 / FR33). Bypass de PENDING_DM_REVIEW."
    - Corps : `pass` (toute logique dans le service)
  - [x] Subtask 1.2 : Aucune migration DB requise (uniquement une transition FSM Python)

- [x] Task 2 : Backend — Vérification des gardes de statut pour le DG (AC1, AC7)
  - [x] Subtask 2.1 : Dans `code/apps/workflow/views.py`, fonction `_require_evidence_permission` ([views.py:1074](code/apps/workflow/views.py#L1074))
    - Le check existant `is_dm_porteur` (assigned_etp is None AND assigned_dm == user) accepte déjà le DG (qui est assigned_dm sans ETP). **Aucune modification nécessaire.**
  - [x] Subtask 2.2 : Vérifier `DraftUploadFileView.post()`, `DraftSaveCommentView.post()` et `DraftDeleteFileView.post()`
    - **Vérifié** : aucune de ces vues ne contient de garde de statut (`status == IN_PROGRESS`). Le seul garde est `_require_evidence_permission()` qui valide déjà le DG via `is_dm_porteur`. **Aucune modification nécessaire.**
  - [x] Subtask 2.3 : **Aucun nouveau helper à créer** — `services.get_or_create_draft_submission(recommendation=rec, user=performed_by)` (services.py:818-856) couvre exactement ce besoin. Il cherche un DRAFT existant pour le user et en crée un si absent. Retourne `(submission, created)`.
    - **Note** : Ne pas utiliser `selectors.get_draft_submission_for_recommendation()` dans le service de soumission car ce selector retourne `None` si absent, alors que la soumission DG doit créer le draft implicitement si le DG n'a pas encore uploadé.

- [x] Task 3 : Backend — Service `submit_evidence_by_dg()` (AC2, AC3, AC4, AC5, AC6, AC7)
  - [x] Subtask 3.1 : Créer dans `code/apps/workflow/services.py`
    - Signature kwargs-only : `(*, recommendation: Recommendation, performed_by, ip_address: str | None = None) -> Recommendation`
    - Docstring avec Args/Returns/Raises et référence AC2-AC6 / FR33
    - Guard RBAC pré-transaction (AC5) : 
      - `if performed_by.role != User.Role.DG: raise PermissionDenied(...)`
      - `if recommendation.assigned_dm_id != performed_by.pk: raise PermissionDenied(...)`
    - `with transaction.atomic():` + `rec = Recommendation.all_objects.select_for_update().get(pk=recommendation.pk)`
    - Guard FSM (AC6) : `if rec.status not in [Status.ASSIGNED, Status.IN_PROGRESS]: raise ValueError(...)`
    - Récupérer/créer le draft DG : `draft, _ = get_or_create_draft_submission(recommendation=rec, user=performed_by)` (correction Subtask 2.3 : `get_or_create`, pas `get_draft_submission_for_recommendation`)
    - Guard contenu (AC3) : `if not draft.files.exists() and not draft.comment.strip(): raise ValueError("Veuillez joindre au moins un fichier ou saisir un commentaire.")`
    - Mémoriser `source_status = rec.status` avant transition
    - Mettre à jour draft : `status=ACCEPTED, reviewed_by=performed_by, reviewed_at=now()` + `save()`
    - Appeler `rec.submit_directly_to_audit()` + `rec.save()`
    - `AuditLog.objects.create(action=AuditLog.Action.TRANSITION, content_type="Recommendation", object_id=rec.pk, changes={"status": [source_status, "PENDING_AUDIT_REVIEW"], "submitted_by_dg": True}, description=f"Soumission directe DG {performed_by.get_full_name()} pour {rec.reference}", user=performed_by, ip_address=ip_address)`
    - Retourner `rec`

- [x] Task 4 : Backend — Vue + URL pour la validation finale DG (AC1, AC2, AC5, AC6)
  - [x] Subtask 4.1 : Créer `EvidenceDGDirectSubmitView(WorkflowAccessMixin, View)` dans `code/apps/workflow/views.py`
    - `dispatch()` : RBAC précoce — `if request.user.role != "DG" or rec.assigned_dm_id != request.user.pk: raise PermissionDenied` (AC5)
    - GET : renvoie `_render_dg_submission_panel(request, rec)` (partial HTML — pattern panneau, pas modale)
      - Affiche les fichiers déjà uploadés dans le draft DG
      - Zone d'upload (réutilise endpoint `draft-upload` existant)
      - Textarea commentaire (réutilise endpoint `draft-save-comment` existant)
      - Bouton "Valider et soumettre à l'Audit"
    - POST : appelle `submit_evidence_by_dg(...)`
      - Succès : `HttpResponse(status=204, headers={"HX-Refresh": "true", "HX-Trigger": json.dumps({"notify": {"message": "Preuves soumises directement à l'Audit.", "type": "success"}})})`
      - `ValueError` : HTTP 422 + re-render panneau avec erreur + `HX-Trigger notify` (type="error")
      - `PermissionDenied` : HTTP 403
  - [x] Subtask 4.2 : Ajouter URL dans `code/apps/workflow/urls.py`
    - Pattern : `recommandations/<uuid:pk>/submit-dg/`
    - Name : `evidence-submit-dg`
    - Vue : `EvidenceDGDirectSubmitView.as_view()`

- [x] Task 5 : Frontend — Template panneau (AC2, AC3, AC7, AC8)
  - [x] Subtask 5.1 : Créer `code/templates/workflow/partials/dg_submit_evidence_panel.html`
    - Header : icône upload + "Soumission directe à l'Audit Interne"
    - Bandeau bleu info : "En tant que DG, vous soumettez directement à l'Audit Interne. La recommandation passera en PENDING_AUDIT_REVIEW sans passer par le circuit DM Review (FR33)."
    - Section "Fichiers" : réutilise le composant `partials/_draft_file_card.html` existant pour lister les fichiers du draft
    - Zone upload incrémentale : `hx-post="{% url 'workflow:draft-upload' recommendation.pk %}"`, `hx-encoding="multipart/form-data"`, `hx-swap="beforeend"` → cible la liste des cartes fichier
      - Indicateur d'upload + limites visibles : "Max 5 fichiers · 6 Mo unitaire · PDF/DOC/XLSX (XLSM interdit)"
    - Textarea commentaire avec autosave HTMX (réutilise pattern `draft-save-comment` + `_saved_indicator.html`)
    - Bouton Valider : `bg-gradient-to-br from-blue-600 to-blue-700` + icône send + "Valider et soumettre à l'Audit"
      - `hx-post="{% url 'workflow:evidence-submit-dg' recommendation.pk %}"`
      - `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`
      - `hx-confirm="Confirmer la soumission directe à l'Audit ?"`
    - Bouton Annuler : `@click="dgSubmitPanelOpen = false"`

- [x] Task 6 : Frontend — Intégration recommendation_detail.html (AC1, AC6)
  - [x] Subtask 6.1 : Ajouter contexte dans `RecommendationDetailView.get_context_data()` (`code/apps/workflow/views.py`)
    - `can_submit_dg = (user.role == "DG" and rec.assigned_dm_id == user.pk and rec.status in [Recommendation.Status.ASSIGNED, Recommendation.Status.IN_PROGRESS])`
  - [x] Subtask 6.2 : Ajouter dans `code/templates/workflow/recommendation_detail.html`
    - Alpine state `dgSubmitPanelOpen: false` dans l'objet `x-data` existant (ligne 7 du template)
    - Conteneur **side drawer** (pattern `historyDrawerOpen`, **PAS** `extensionRequestModalOpen`) :
      - **Ne pas** utiliser `x-teleport="body"` + `fixed inset-0 flex items-center justify-center` — ce pattern est pour les petites modales sans upload
      - **Utiliser** : `<div x-show="dgSubmitPanelOpen" class="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white shadow-xl overflow-y-auto ..." style="display:none" @keydown.escape.window="dgSubmitPanelOpen = false" id="dg-submit-evidence-panel-container">` — scrollable, pleine hauteur, depuis la droite
      - **Rationale** : Le panneau DG contient upload incrémental HTMX + textarea autosave → trop riche pour une modale centrée 400px. Le side drawer est adapté à ce contenu.
    - Bouton conditionnel `{% if can_submit_dg %}` :
      - `hx-get="{% url 'workflow:evidence-submit-dg' recommendation.pk %}"`
      - `hx-target="#dg-submit-evidence-panel-container"`
      - `hx-swap="innerHTML"`
      - `@click="dgSubmitPanelOpen = true"`
      - Icône upload + texte "Soumettre directement à l'Audit" + couleur `text-blue-600`

- [x] Task 7 : Tests — `DGDirectSubmitViewTest(EvidenceSubmissionTestMixin, TestCase)` dans `test_views.py` (12 tests)
  - **Note héritage (correction)** : Utiliser `EvidenceSubmissionTestMixin` (test_views.py:830) et non `ViewTestMixin` directement. `EvidenceSubmissionTestMixin` hérite de `ViewTestMixin` et fournit `_create_draft_and_upload()` (test_views.py:854) — helper critique pour pré-remplir draft + fichier + commentaire sans réécrire la logique. Pattern identique à `ExtensionRequestViewTest(EvidenceSubmissionTestMixin, TestCase)` (test_views.py:1840).
  - [x] 7.0 *(prérequis)* Ajouter un **second user DG** dans `ViewTestMixin.setUpTestData()` ([test_views.py:24](code/apps/workflow/tests/test_views.py#L24)) :
    - `dg_user` existe déjà → DG principal
    - Ajouter `dga_user = User.objects.create_user(username="dga_view", role="DG", department=cls.direction)` pour simuler le DGA BICEC
    - Garantit que le test 7.12 a une vraie cible et que la logique RBAC est validée avec ≥ 2 users DG
  - [x] 7.1 `test_dg_can_submit_directly_to_audit` — DG avec draft pré-rempli → POST → 204 (AC2)
  - [x] 7.2 `test_recommendation_goes_to_pending_audit_review` — FSM state = PENDING_AUDIT_REVIEW après POST (AC2)
  - [x] 7.3 `test_evidence_submission_status_becomes_accepted` — draft.status DRAFT → ACCEPTED + reviewed_by=DG (AC2)
  - [x] 7.4 `test_empty_draft_returns_422` — DG sans fichier ET sans commentaire → 422 (AC3)
  - [x] 7.5 `test_comment_only_submission_accepted` — DG avec commentaire seul (pas de fichier) → 204 (AC3)
  - [x] 7.6 `test_audit_log_created_with_content_type_recommendation` — AuditLog action=TRANSITION + content_type="Recommendation" (AC4)
  - [x] 7.7 `test_non_assigned_dg_cannot_submit` — DG sur autre reco → 403 (AC5)
  - [x] 7.8 `test_dm_role_cannot_use_dg_endpoint` — user.role=DM même si assigned_dm=lui → 403 (AC5)
  - [x] 7.9 `test_already_pending_audit_review_rejected` — reco déjà PENDING_AUDIT_REVIEW → 422 (AC6)
  - [x] 7.10 `test_audit_sees_dg_submission` — AUDIT GET detail page voit EvidenceSubmission DG (AC8)
  - [x] 7.11 *(bonus)* `test_dg_can_upload_files_in_assigned_state` — vérifie que `DraftUploadFileView` accepte ASSIGNED pour DG (Subtask 2.2)
  - [x] 7.12 `test_second_dg_user_cannot_submit_for_first_dg_recommendation` — Vérifie que 2 utilisateurs avec `role=DG` ne se suppléent pas : un second user DG (simulant le DGA BICEC) ne peut pas soumettre pour une reco dont `assigned_dm` est le premier DG (AC9)

- [x] Task 8 : Backend — Restriction visibilité DG dans le sélecteur (selectors.py)
  - **Contexte** : `get_recommendations_for_user()` (selectors.py:44-49) traite actuellement DG et DM identiquement — le DG voit toutes les recommandations de son département. Exigence métier (validation responsable 2026-05-28) : le DG ne doit voir **que** les recommandations dont il est `assigned_dm`. Il agit comme un DM Porteur sur ses propres recos, pas comme un superviseur de département.
  - [x] Subtask 8.1 : Dans `get_recommendations_for_user()` (`code/apps/workflow/selectors.py`, lignes 44-49), séparer le traitement DG du traitement DM :

    **Code actuel :**
    ```python
    if user.role in [User.Role.DM, User.Role.DG]:
        if user.department:
            dept_ids = get_department_and_descendants_ids(user.department)
            qs = qs.filter(department_id__in=dept_ids)
        else:
            return qs.none()
    ```

    **Code corrigé :**
    ```python
    if user.role == User.Role.DM:
        if user.department:
            dept_ids = get_department_and_descendants_ids(user.department)
            qs = qs.filter(department_id__in=dept_ids)
        else:
            return qs.none()
    elif user.role == User.Role.DG:
        # Le DG ne voit QUE les recommandations qui lui sont personnellement assignées (FR33)
        qs = qs.filter(assigned_dm=user)
    ```

  - [x] Subtask 8.2 : Adapter les tests existants impactés par ce changement
    - Vérifier que les tests utilisant `dg_user` sur des recos de liste supposent `assigned_dm=dg_user` — si non, corriger les assertions (s'assurer que les recos de test ont bien `assigned_dm=dg_user`)
    - En particulier, vérifier les tests RBAC de type "DG voit les recos" dans les classes existantes
  - [x] Subtask 8.3 : `RecommendationDetailView` — 404 automatique si `assigned_dm != request.user` pour DG (découle de Subtask 8.1 car `get_recommendation_detail_for_user()` appelle `get_recommendations_for_user()`)
  - **Note** : Aucune modification supplémentaire dans `WorkflowAccessMixin` — la restriction se fait au niveau du queryset, pas du mixin de rôle.
  - **Note dashboard** : La demande d'un dashboard DG (statistiques globales, recos en retard, ETPs/DMs actifs, graphiques) nécessitera un queryset séparé non filtré par `assigned_dm` — à gérer dans **Story 6.x** (Epic 6 dashboards, stub existant dans `code/apps/dashboards/`).

## Dev Notes

### Décisions architecturales (validées par utilisateur)

- **FSM transition** : nom = `submit_directly_to_audit()`, source = `[Status.ASSIGNED, Status.IN_PROGRESS]`. Choix validé pour respecter strictement l'intention FR33 ("bypass niveaux intermédiaires"), même si l'architecture-v2.md L.939 documente une variante `submit_to_audit()` avec source IN_PROGRESS uniquement (attribuée à DM, pas DG).
- **Upload pattern** : incrémental (un fichier par POST), comme Story 3.3 ETP. Le DG réutilise les endpoints existants (`draft-upload`, `draft-save-comment`) après vérification que les gardes de statut n'empêchent pas ASSIGNED.

### Support DG / DGA (BICEC — décision Option 1)

BICEC dispose d'un Directeur Général **et** d'un Directeur Général Adjoint. Décision validée : les deux utilisent le **même rôle `User.Role.DG`** avec deux comptes distincts. Aucun nouveau rôle, aucun flag spécifique au MVP.

**Implications Story 3.7** :
- Le service `submit_evidence_by_dg()` valide `performed_by.role == "DG"` ET `recommendation.assigned_dm_id == performed_by.pk` — fonctionne nativement avec N utilisateurs DG distincts
- Description AuditLog utilise `performed_by.get_full_name()` (jamais "le DG" en dur)
- Aucune logique ne suppose l'unicité du DG dans la base
- Le contexte `can_submit_dg` (Subtask 6.1) protège déjà la limitation : un DGA ne voit pas le bouton sur les recos du DG (AC9)

**Patterns à éviter dans Task 3 pour garantir la migration future indolore** :

| ❌ À éviter | ✅ À faire |
|---|---|
| `User.objects.get(role="DG")` (singular) | `recommendation.assigned_dm` (FK direct) |
| `User.objects.filter(role="DG").first()` | Récupérer via `performed_by` (paramètre service) |
| Hardcoder `"DG"` dans les descriptions | Utiliser `performed_by.get_role_display()` ou `get_full_name()` |
| Tests qui supposent un seul user DG en DB | `ViewTestMixin` doit fournir 2 users DG (cf. Subtask 7.0) |

**Migration future vers flag `is_dga` (Option 3, si remarque hiérarchique apparaît)** :
- Pré-requis garantis ci-dessus : aucune query qui présume l'unicité du DG
- Toutes les vérifications sont user-scoped (`assigned_dm == request.user`) → l'ajout d'un flag `is_dga` n'invalidera aucun test
- Estimation effort migration : 1 BooleanField + 1 migration + propriété `User.role_display` (~30 minutes)
- Référence pattern : `is_audit_admin` ([users/models.py:184](code/apps/users/models.py#L184))

### Éléments codebase à réutiliser (vérifiés)

- **`validate_magic_bytes(file, *, original_filename="")`** dans [validators.py:44](code/apps/workflow/validators.py#L44) — magic bytes, MIME, taille 6 Mo (NFR-SCA-01), XLSM interdit (NFR-SEC-04)
- **`_get_client_ip(request)`** dans [views.py:42](code/apps/workflow/views.py#L42) — extraction IP pour AuditLog
- **`_require_evidence_permission(recommendation, user)`** dans [views.py:1074](code/apps/workflow/views.py#L1074) — accepte déjà DG via le check `is_dm_porteur` (assigned_etp is None AND assigned_dm == user), **aucune modification nécessaire**
- **`DraftUploadFileView`** ([views.py:1089](code/apps/workflow/views.py#L1089)) + **`DraftSaveCommentView`** ([views.py:1203](code/apps/workflow/views.py#L1203)) + **`DraftDeleteFileView`** ([views.py:1158](code/apps/workflow/views.py#L1158)) — endpoints upload incrémental réutilisables directement (vérifié : **aucune garde de statut** dans ces vues)
- **`selectors.get_draft_submission_for_recommendation`** — retourne le draft du user courant
- **`get_evidence_for_recommendation(*, recommendation, user=None)`** ([selectors.py:185](code/apps/workflow/selectors.py#L185)) — filtre AUDIT déjà OK pour PENDING_AUDIT_REVIEW → soumissions DG visibles automatiquement (AC8 sans modif)
- **`WorkflowAccessMixin`** ([mixins.py:72-87](code/apps/users/mixins.py#L72-L87)) — inclut bien `User.Role.DG`
- **`EvidenceSubmissionTestMixin`** ([test_views.py:830](code/apps/workflow/tests/test_views.py#L830)) — hérite de `ViewTestMixin`, fournit `_create_draft_and_upload()` (test_views.py:854). **Utiliser comme base class pour `DGDirectSubmitViewTest`** (correction Task 7 — remplace `ViewTestMixin` direct)
- **`ViewTestMixin`** ([test_views.py:24](code/apps/workflow/tests/test_views.py#L24)) — fournit `setUpTestData` avec departments + 5 users (audit, dm, etp, admin, dg). Étendre pour y ajouter `dga_user` (Subtask 7.0)
- **Tag fichier** : `EvidenceFile.Tag.JUSTIFICATIF` ([models.py:655-660](code/apps/workflow/models.py#L655-L660)) — tag par défaut pour les fichiers DG (pas de PV_RECETTE requis dans ce flux)

### Couverture NFR (référencées explicitement)

- **NFR-SEC-04** (Magic Bytes strict, XLSM interdit) : couvert par `validate_magic_bytes` (AC7)
- **NFR-SEC-05** (AuditLog append-only, 12 mois) : couvert par `AuditLog.objects.create` (AC4)
- **NFR-SCA-01** (max 5 fichiers / 6 Mo unitaire) : couvert par validators existants + UI label explicite (AC7)
- **NFR-PERF-02** (UI < 200ms P95 via HTMX) : pattern HTMX hx-post conservé

### Cas spéciaux & invariants

- **DG = assigned_dm** : pattern identique à Story 3.6 (FR34 confirmé)
- **EvidenceSubmission.status=ACCEPTED dès création** : auto-validée — pas de circuit PENDING → DM Review
- **django-fsm + select_for_update** : utiliser `Recommendation.all_objects.select_for_update().get(pk=recommendation.pk)` et **non** `rec.refresh_from_db()` qui lève `AttributeError` avec django-fsm (pattern Story 3.6 confirmé)
- **AuditLog action** : utiliser `AuditLog.Action.TRANSITION` existant. Pas de nouvelle action enum à créer (contrairement à Story 3.6)
- **Tailwind** : n'utiliser que les classes présentes dans `output.css` compilé — `from-blue-600 to-blue-700` confirmé
- **Aucune migration DB** : Story 3.7 ne crée aucun nouveau modèle ni champ

### Project Structure Notes

Fichiers à **modifier** :
- `code/apps/workflow/selectors.py` — Task 8 : séparation DG/DM dans `get_recommendations_for_user()` (lignes 44-49)
- `code/apps/workflow/models.py` — FSM transition `submit_directly_to_audit()`
- `code/apps/workflow/services.py` — service `submit_evidence_by_dg()` (sans `_get_or_create_dg_draft()` — correction Subtask 2.3)
- `code/apps/workflow/views.py` — vue `EvidenceDGDirectSubmitView` + helper `_render_dg_submission_panel()` + contexte `can_submit_dg` dans `RecommendationDetailView`
- `code/apps/workflow/urls.py` — URL `evidence-submit-dg`
- `code/templates/workflow/recommendation_detail.html` — bouton DG conditionnel + conteneur side drawer + état `dgSubmitPanelOpen`
- `code/apps/workflow/tests/test_views.py` — `dga_user` dans `ViewTestMixin` + classe `DGDirectSubmitViewTest(EvidenceSubmissionTestMixin)` avec 12 tests

Fichier à **créer** :
- `code/templates/workflow/partials/dg_submit_evidence_panel.html`

### References

- `_bmad-output/planning-artifacts/epics.md` L.377-387 (Story 3.7 requirements) + L.291-294 (Epic 3) + L.116 (FR33 coverage map)
- `_bmad-output/planning-artifacts/prd-v2.md` FR33 L.306-309 + Journey 5 (Supervision Stratégique DG) L.162-173 + NFRs L.55-73
- `_bmad-output/planning-artifacts/architecture-v2.md` §4.4 L.817-847 (UC8 DG "Soumettre directement preuves à l'Audit") + FSM L.939
- Story 3.3 artifact : `_bmad-output/implementation-artifacts/3-3-soumission-preuves-etp-immutabilite.md` (pattern upload incrémental, magic bytes, quota)
- Story 3.5 artifact : `_bmad-output/implementation-artifacts/3-5-validation-dm-envoi-audit-exemption-pv.md` (pattern service validate_evidence_for_audit, FSM approve_for_audit)
- Story 3.6 artifact : `_bmad-output/implementation-artifacts/3-6-demande-report-echeance.md` (pattern AuditLog content_type="Recommendation", django-fsm `all_objects.select_for_update()`)
- **Décision BICEC DG/DGA — Option 1 (2026-05-25)** : 2 comptes utilisateurs distincts partagent le rôle `User.Role.DG`. Migration ultérieure vers flag `is_dga` (Option 3) ou rôle séparé (Option 2) possible sans casser les ACs existants — voir section "Support DG / DGA" dans Dev Notes

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **2026-05-28** : Artifact mis à jour avant implémentation — 3 corrections identifiées lors de la revue codebase + 1 nouvelle exigence :
  - Correction 1 (Subtask 2.3) : `_get_or_create_dg_draft()` supprimé — remplacé par `get_or_create_draft_submission()` existant (services.py:818-856)
  - Correction 2 (Task 7) : Classe de test `DGDirectSubmitViewTest` hérite de `EvidenceSubmissionTestMixin` (pas `ViewTestMixin`) pour accéder à `_create_draft_and_upload()`
  - Correction 3 (Task 6.2) : Pattern UI précisé — side drawer (pattern `historyDrawerOpen`), pas modale centrée
  - Task 8 ajoutée : Restriction visibilité DG dans `selectors.py` — séparer DG/DM dans `get_recommendations_for_user()` (exigence responsable 2026-05-28 : DG voit uniquement ses recos assignées)

- **2026-05-28** : Implémentation Story 3.7 + Story 3.8 (DG direct assignment) terminée — 244 tests verts, 0 migration DB, 0 régression.
  - Story 3.7 : `submit_directly_to_audit()` FSM, `submit_evidence_by_dg()` service, `EvidenceDGDirectSubmitView` view, `dg_submit_evidence_panel.html` template, 12 tests dans `DGDirectSubmitViewTest`. Bug fix : `_render_dg_submission_panel()` utilise `get_or_create_draft_submission()` (pas `get_draft_submission_for_recommendation()`).
  - Story 3.8 (extension) : `assign_to_dg()` FSM (DRAFT → IN_PROGRESS bypass ASSIGNED), `assign_recommendation_to_dg()` service, `get_available_dgs_for_recommendation()` selector, `AssignDGForm`, `RecommendationAssignDGView`, toggle DM ↔ DG dans la modale (`assign_dm_modal.html` modifié + `assign_dg_modal.html` créé), `recommendation-assign-dg` URL, 6 tests dans `RecommendationAssignDGViewTest`.

### File List

**Story 3.7 :**
- `code/apps/workflow/models.py` — `submit_directly_to_audit()` FSM transition
- `code/apps/workflow/services.py` — `submit_evidence_by_dg()` service
- `code/apps/workflow/views.py` — `EvidenceDGDirectSubmitView`, `_render_dg_submission_panel()`, `can_submit_dg` context
- `code/apps/workflow/urls.py` — `evidence-submit-dg` URL
- `code/apps/workflow/selectors.py` — séparation DG/DM dans `get_recommendations_for_user()`
- `code/templates/workflow/recommendation_detail.html` — `dgSubmitPanelOpen` + bouton + side drawer
- `code/templates/workflow/partials/dg_submit_evidence_panel.html` — créé
- `code/apps/workflow/tests/test_views.py` — `dga_user` + `DGDirectSubmitViewTest` (12 tests)
- `code/apps/workflow/tests/test_delegation.py` — `test_dg_selector_sees_own_department_recommendations` adapté

**Story 3.8 (DG direct assignment depuis Audit) :**
- `code/apps/workflow/models.py` — `assign_to_dg()` FSM transition (DRAFT → IN_PROGRESS)
- `code/apps/workflow/services.py` — `assign_recommendation_to_dg()` service
- `code/apps/workflow/selectors.py` — `get_available_dgs_for_recommendation()`
- `code/apps/workflow/forms.py` — `AssignDGForm`
- `code/apps/workflow/views.py` — `RecommendationAssignDGView`, `_render_assign_dg_modal()`, import `AssignDGForm`
- `code/apps/workflow/urls.py` — `recommendation-assign-dg` URL
- `code/templates/workflow/partials/assign_dm_modal.html` — toggle pill DM ↔ DG ajouté
- `code/templates/workflow/partials/assign_dg_modal.html` — créé (toggle inversé + bandeau bleu + form.dg)
- `code/apps/workflow/tests/test_views.py` — `RecommendationAssignDGViewTest` (6 tests) + `_create_recommendation_for_dg()` default mis à jour → IN_PROGRESS + `test_dg_can_access_list` mis à jour → IN_PROGRESS
- `code/apps/workflow/tests/test_delegation.py` — `test_dg_selector_sees_own_department_recommendations` mis à jour → IN_PROGRESS
