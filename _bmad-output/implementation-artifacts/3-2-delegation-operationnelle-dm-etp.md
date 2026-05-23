# Story 3.2: Délégation Opérationnelle (DM -> ETP)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier (DM)**,
I want **soit désigner un de mes ETP pour préparer la preuve, soit m'assigner moi-même (DM Porteur)**,
so that **la personne compétente ait la responsabilité concrète du dossier.**

## Acceptance Criteria

1. **AC1 — Délégation à un ETP**
   - **Given** une recommandation en état `ASSIGNED` dans mon département,
   - **When** je sélectionne un ETP dans la liste déroulante des ETP de mon département,
   - **Then** le champ `assigned_etp` est mis à jour avec cet utilisateur.
   - **And** le statut passe à `IN_PROGRESS` (transition FSM unifiée).
   - **And** l'action est tracée dans l'Audit Log.

2. **AC2 — DM Porteur (auto-assignation)**
   - **Given** une recommandation en état `ASSIGNED` dans mon département,
   - **When** je choisis l'option "Devenir DM Porteur",
   - **Then** le champ `assigned_etp` reste vide (null).
   - **And** le statut passe à `IN_PROGRESS`.
   - **And** l'action est tracée dans l'Audit Log.

3. **AC3 — UI de délégation**
   - **Given** la page de détail d'une recommandation en état `ASSIGNED`,
   - **Then** un bouton "Déléguer" est visible pour le DM de la recommandation.
   - **And** une modale HTMX affiche la liste des ETP du département + option "DM Porteur".
   - **And** le bouton est masqué si le statut n'est pas `ASSIGNED`.
   - **And** le bouton est masqué si l'utilisateur n'est pas le DM assigné.

4. **AC4 — Sécurité RBAC**
   - **Given** un utilisateur qui n'est pas le DM assigné de la recommandation,
   - **When** il tente d'accéder à la vue de délégation,
   - **Then** il reçoit une erreur 403 Forbidden.
   - **And** un ETP ne peut pas se déléguer lui-même une recommandation.

5. **AC5 — Notification (placeholder)**
   - **Given** une délégation réussie à un ETP,
   - **Then** le système prépare le hook de notification (deferred to Epic 4).
   - **And** un message de confirmation est affiché à l'utilisateur.

## Tasks / Subtasks

- [x] Task 1 : Backend — Logique de délégation (selectors, services & views)
  - [x] Subtask 1.1 : Créer `get_available_etps_for_department(department)` dans `apps/workflow/selectors.py` pour lister les ETP actifs d'un département.
  - [x] Subtask 1.2 : Ajouter la transition FSM `@transition` pour passer à l'état `IN_PROGRESS` (`start_processing`) dans le modèle `Recommendation` (apps/workflow/models.py).
  - [x] Subtask 1.3 : Créer `delegate_recommendation_to_etp(recommendation, etp, performed_by, ip_address)` dans `apps/workflow/services.py` :
    - Verrouiller l'objet via `select_for_update()` pour prévenir les race conditions (ADR-07 §5.4).
    - Vérifier que la reco est en `ASSIGNED`.
    - Vérifier que l'ETP appartient au même département que la reco.
    - Mettre à jour `assigned_etp`.
    - Transition FSM `ASSIGNED` → `IN_PROGRESS` (appeler `start_processing()`).
    - Tracer dans l'Audit Log (action=TRANSITION).
  - [x] Subtask 1.4 : Créer `become_dm_porteur(recommendation, performed_by, ip_address)` dans `apps/workflow/services.py` :
    - Verrouiller l'objet via `select_for_update()` pour prévenir les race conditions (ADR-07 §5.4).
    - Vérifier que la reco est en `ASSIGNED`.
    - Transition FSM `ASSIGNED` → `IN_PROGRESS` (appeler `start_processing()`).
    - Laisser `assigned_etp` à null.
    - Tracer dans l'Audit Log.
  - [x] Subtask 1.5 : Créer `RecommendationDelegateView` dans `apps/workflow/views.py` :
    - GET : Retourne la modale HTMX avec formulaire de délégation.
    - POST : Exécute la délégation ou l'auto-assignation DM Porteur.
    - Sécurité : Vérifier que `request.user == recommendation.assigned_dm`.
    - Gérer `TransitionNotAllowed` et `ValidationError` dans le POST pour éviter les 500 (pattern identique à `RecommendationAssignView`).
    - Renvoyer `HX-Refresh: true` après succès pour rafraîchir badge statut, métadonnées et timeline (pattern Story 2.5).
  - [x] Subtask 1.6 : Ajouter l'URL `recommandations/<uuid:pk>/delegate/` dans `apps/workflow/urls.py`.

- [x] Task 2 : Frontend — Modale de délégation & UI
  - [x] Subtask 2.1 : Créer `DelegateETPForm` dans `apps/workflow/forms.py` :
    - Champ `etp` : ModelChoiceField filtré par département.
    - Champ `action` : ChoiceField avec options `delegate_etp` et `dm_porteur`.
  - [x] Subtask 2.2 : Créer `templates/workflow/partials/delegate_etp_modal.html` :
    - Liste déroulante des ETP du département.
    - Radio buttons ou boutons pour choisir "Déléguer à un ETP" ou "Devenir DM Porteur".
    - Bouton de confirmation.
    - Style cohérent avec la modale d'assignation existante.
  - [x] Subtask 2.3 : Modifier `templates/workflow/recommendation_detail.html` :
    - Ajouter un bouton "Déléguer" dans la barre d'actions (visible uniquement si `status == 'ASSIGNED'` et `user == recommendation.assigned_dm`).
    - Ajouter le conteneur Alpine.js pour la modale de délégation (`x-data="{ delegateModalOpen: false }"`).
    - Ajouter le template x-teleport pour la modale.
  - [x] Subtask 2.4 : Afficher l'ETP assigné dans la section "Informations" de la page détail :
    - Si `recommendation.assigned_etp` est renseigné, afficher "ETP délégué : {nom}".
    - Si `recommendation.assigned_etp` est null et `status == 'IN_PROGRESS'`, afficher "DM Porteur".

- [x] Task 3 : Tests (Délégation, RBAC et UI)
  - [x] Subtask 3.1 : **Test RBAC Délégation** : `test_dm_can_delegate_to_etp` (DM assigné peut déléguer à un ETP de son département).
  - [x] Subtask 3.2 : **Test RBAC Interdiction** : `test_non_assigned_dm_cannot_delegate` (un DM non assigné reçoit 403) et `test_etp_cannot_delegate` (un ETP ne peut pas déléguer).
  - [x] Subtask 3.3 : **Test DM Porteur** : `test_dm_can_become_porteur` (DM peut s'auto-assigner comme porteur, statut passe à IN_PROGRESS).
  - [x] Subtask 3.4 : **Test ETP cross-department** : `test_cannot_delegate_to_etp_from_other_department` (impossible de déléguer à un ETP d'un autre département).
  - [x] Subtask 3.5 : **Test Audit Log** : `test_delegation_traces_in_audit_log` et `test_dm_porteur_traces_in_audit_log`.
  - [x] Subtask 3.6 : **Test UI** : `test_delegate_button_visible_for_assigned_dm` et `test_delegate_button_hidden_for_non_assigned_dm`.
  - [x] Subtask 3.7 : **Test FSM négatif** : `test_cannot_delegate_when_not_assigned` (vérifie le rejet si status != ASSIGNED, ex: IN_PROGRESS ou CLOSED_RESOLVED).

## Dev Notes

- **Architecture & Constraints:**
  - Conserver le pattern HackSoft : selector → service → view.
  - **Correction PRD:** La délégation (ETP et DM Porteur) fait passer le statut de `ASSIGNED` à `IN_PROGRESS` via une transition FSM centralisée `start_processing`.
  - Le champ `assigned_etp` existe déjà dans le modèle (`models.py:218-226`).
  - Le selector `get_recommendations_for_user` filtre déjà par `assigned_etp=user` pour les ETP (`selectors.py:46-47`).
  - Utiliser le même pattern HTMX que la modale d'assignation existante (`recommendation_detail.html:314-321`).
  - La notification est deferred à Epic 4 — prévoir un hook placeholder dans le service.

- **Source tree components to touch:**
  - `code/apps/workflow/models.py` (ajouter transition FSM `start_processing`)
  - `code/apps/workflow/selectors.py` (ajouter `get_available_etps_for_department`)
  - `code/apps/workflow/services.py` (ajouter `delegate_recommendation_to_etp` et `become_dm_porteur`)
  - `code/apps/workflow/forms.py` (ajouter `DelegateETPForm`)
  - `code/apps/workflow/views.py` (ajouter `RecommendationDelegateView`)
  - `code/apps/workflow/urls.py` (ajouter URL de délégation)
  - `code/templates/workflow/partials/delegate_etp_modal.html` (nouveau fichier)
  - `code/templates/workflow/recommendation_detail.html` (ajouter bouton + modale)
  - `code/apps/workflow/tests/test_views.py` (ajouter tests de délégation)

### References

- [Source: epics.md#Story 3.2]
- [Architecture v2] django-fsm pour les transitions d'état, HTMX pour les interactions UI.
- [PRD v2] FR12 : Le DM peut déléguer à un ETP ou traiter personnellement (DM Porteur).
- [Story 3.1] Le filtre Historique/Récent et le RBAC sont déjà implémentés.
- [Story 2.5] L'assignation au DM est déjà implémentée — la délégation ETP est le prochain pas.

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References
- Tests passés avec succès: 103 tests passés pour `apps.workflow`.

### Completion Notes List
- Sécurité RBAC forte avec des gardes en place pour interdire les accès aux non-assignés.
- Utilisation de `select_for_update()` dans les services pour éviter les conditions de concurrence.
- Formulaire `DelegateETPForm` créé pour distinguer la délégation ETP du portage DM.
- Les actions HTMX sont sécurisées et incluent `HX-Refresh` pour une mise à jour fluide de l'interface et du Timeline.
- L'ensemble de la suite de tests FSM, HTMX et Backend (7 nouveaux cas de tests) est validé.

### File List
- `code/apps/workflow/models.py`
- `code/apps/workflow/selectors.py`
- `code/apps/workflow/services.py`
- `code/apps/workflow/forms.py`
- `code/apps/workflow/views.py`
- `code/apps/workflow/urls.py`
- `code/templates/workflow/partials/delegate_etp_modal.html`
- `code/templates/workflow/recommendation_detail.html`
- `code/apps/workflow/tests/test_views.py`
