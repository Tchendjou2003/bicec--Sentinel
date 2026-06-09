# Story 3.5: Validation DM et Envoi à l'Audit (Exemption PV)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier**,
I want **approuver les preuves soumises (par mon ETP ou par moi-même en DM Porteur) et les envoyer à l'Audit**,
so that **le statut passe à `PENDING_AUDIT_REVIEW` et l'Audit Interne peut procéder à sa validation définitive.**

## Acceptance Criteria

1. **AC1 — Transition FSM Validation DM → Audit**
   - **Given** une recommandation en état `PENDING_DM_REVIEW`,
   - **When** le DM assigné clique sur "Valider vers l'Audit" et soumet le formulaire,
   - **Then** l'état passe à `PENDING_AUDIT_REVIEW`.
   - **And** la soumission (`EvidenceSubmission`) PENDING concernée passe au statut `ACCEPTED`.
   - **And** le commentaire DM (si fourni) est enregistré dans `review_comment`, `reviewed_at`, `reviewed_by` (champs déjà présents en DB depuis Story 3.4).
   - **And** l'action est tracée dans l'Audit Log (action=TRANSITION, description="Validation DM [nom] → Audit pour [Référence]", changes={"status": ["PENDING_DM_REVIEW", "PENDING_AUDIT_REVIEW"]}).

2. **AC2 — Exemption du commentaire si PV de Recette détecté (FR19)**
   - **Given** la validation du dossier par le DM,
   - **When** au moins un fichier tagué `PV_RECETTE` est présent dans la soumission PENDING,
   - **Then** le commentaire DM est **optionnel** (formulaire valide même si vide).
   - **When** aucun fichier `PV_RECETTE` n'est présent dans la soumission,
   - **Then** le commentaire DM est **requis** — le service lève `ValueError` et la vue renvoie HTTP 422.

3. **AC3 — RBAC et contrôle d'accès**
   - **Given** un utilisateur connecté,
   - **When** il consulte une recommandation en `PENDING_DM_REVIEW`,
   - **Then** seul le Directeur Métier assigné (`recommendation.assigned_dm == request.user`) voit et peut utiliser le bouton "Valider vers l'Audit".
   - **And** tout autre rôle (ETP, AUDIT, DG, EXT, ADMIN_IT) ne voit pas ce bouton.
   - **And** une tentative POST non autorisée renvoie HTTP 403.

4. **AC4 — UI Modale HTMX (DM Review Panel)**
   - **Given** le DM clique sur "Valider vers l'Audit",
   - **When** la modale s'ouvre (chargée via HTMX),
   - **Then** elle affiche :
     - Un bandeau info vert si un PV de Recette est détecté : "Commentaire optionnel — PV de Recette détecté".
     - Le nombre de fichiers de la soumission et le commentaire ETP.
     - Un champ textarea "Commentaire DM" (label indique s'il est requis ou optionnel).
     - Un bouton "Valider vers l'Audit" (vert) et un bouton "Annuler" (gris).
   - **When** la validation réussit,
   - **Then** la page se recharge (`HX-Refresh: true`) affichant le statut `PENDING_AUDIT_REVIEW`.
   - **When** validation échoue (commentaire manquant sans PV_RECETTE),
   - **Then** HX-Trigger envoie un toast d'erreur et la modale reste ouverte (422).

## Tasks / Subtasks

- [ ] Task 1 : Backend — FSM (AC1)
  - [ ] Subtask 1.1 : Ajouter la transition `approve_for_audit()` dans `Recommendation` (`apps/workflow/models.py`) :
    - `source=Status.PENDING_DM_REVIEW`, `target=Status.PENDING_AUDIT_REVIEW`
    - Docstring : "Transition PENDING_DM_REVIEW → PENDING_AUDIT_REVIEW (Story 3.5 — AC1)."
  - [ ] Subtask 1.2 : Vérifier `python manage.py migrate --check` (aucune nouvelle colonne — pas de migration attendue).

- [ ] Task 2 : Backend — Service Layer (AC1, AC2)
  - [ ] Subtask 2.1 : Créer `validate_evidence_for_audit(*, recommendation, performed_by, comment="")` dans `apps/workflow/services.py` :
    1. Guard RBAC : `performed_by != recommendation.assigned_dm` → `PermissionDenied`.
    2. Verrouiller + recharger : `Recommendation.all_objects.select_for_update().get(pk=recommendation.pk)`.
    3. Guard FSM : `status != PENDING_DM_REVIEW` → `ValueError`.
    4. Récupérer soumission PENDING (absente → `ValueError`).
    5. PV Exemption : `has_pv = submission.files.filter(tag=PV_RECETTE).exists()`. Si `not has_pv and not comment.strip()` → `ValueError`.
    6. Mettre à jour `EvidenceSubmission` : `status=ACCEPTED`, `review_comment`, `reviewed_at`, `reviewed_by`.
    7. FSM : `rec.approve_for_audit()` + `rec.save()`.
    8. Créer `AuditLog(action=TRANSITION, ...)`.
    - Tout dans `transaction.atomic()`.

- [ ] Task 3 : Backend — Formulaire (AC2, AC4)
  - [ ] Subtask 3.1 : Créer `EvidenceDMApprovalForm` dans `apps/workflow/forms.py` avec `comment` (Textarea, `required=False`).

- [ ] Task 4 : Backend — Vue et URL (AC3, AC4)
  - [ ] Subtask 4.1 : Créer `EvidenceDMApprovalView(WorkflowAccessMixin, View)` dans `apps/workflow/views.py`.
  - [ ] Subtask 4.2 : Mettre à jour `RecommendationDetailView.get_context_data()` : `can_approve_evidence` + `has_pv_recette_in_submission`.
  - [ ] Subtask 4.3 : Route `recommandations/<uuid:pk>/submissions/<uuid:submission_id>/approve/` (name=`evidence-approve`).

- [ ] Task 5 : Frontend — Templates (AC4)
  - [ ] Subtask 5.1 : Créer `templates/workflow/partials/approve_evidence_modal.html`.
  - [ ] Subtask 5.2 : Mettre à jour `recommendation_detail.html` (bouton + modale Alpine).

- [ ] Task 6 : Tests (AC1–AC4)
  - [ ] Subtask 6.1–6.7 : 7 tests dans `EvidenceDMApprovalViewTest` (`test_views.py`).

## Dev Notes

- **Architecture** : Selector → Service → View strictement.
- **Réutiliser** `EvidenceSubmission.SubmissionStatus.ACCEPTED` et `EvidenceFile.Tag.PV_RECETTE` (déjà définis).
- **Réutiliser** champs `review_comment`, `reviewed_at`, `reviewed_by` sur `EvidenceSubmission` (Story 3.4 — déjà en DB, pas de migration).
- **Réutiliser** pattern `select_for_update()` + `Recommendation.all_objects.get(pk=...)` (guard FSM incompatible avec `refresh_from_db()`).
- **Notifications (hors scope)** : Notification async à l'Audit Interne reportée à Epic 4.
- **DM Porteur** : Quand `assigned_etp is None`, le DM a soumis lui-même → statut = `PENDING_DM_REVIEW`. Il peut valider ses propres preuves (pas de guard contrairement au rejet Story 3.4).

### Project Structure Notes

- Nouveaux tests dans `apps/workflow/tests/test_views.py` (classe `EvidenceDMApprovalViewTest`).
- Template partiel dans `templates/workflow/partials/`.

### References

- [Source: epics.md#Story 3.5] — FR17, FR19
- [Source: prd-v2.md#FR17-FR19] — Exemption PV de Recette
- [Pattern: EvidenceRejectView in views.py] — Même architecture à reproduire

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
