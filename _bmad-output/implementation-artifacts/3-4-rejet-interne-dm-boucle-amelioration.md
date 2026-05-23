# Story 3.4: Rejet Interne par le DM (Boucle d'amélioration)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier**,
I want **rejeter une preuve insuffisante déposée par mon ETP, avec motif obligatoire**,
so that **le statut revienne à `IN_PROGRESS` pour correction, sans déclencher de fausses alertes à l'Audit.**

## Acceptance Criteria

1. **AC1 — Transition FSM Rejet Interne**
   - **Given** une recommandation en état `PENDING_DM_REVIEW`,
   - **When** je clique sur "Rejeter" et saisis le motif,
   - **Then** l'état repasse en `IN_PROGRESS` (conformément au PRD, parcours Edge Case).
   - **And** l'Audit ne reçoit aucune notification de rejet interne.

2. **AC2 — Enregistrement du Rejet sur la Soumission**
   - **Given** le rejet d'une preuve,
   - **When** le formulaire est validé,
   - **Then** la soumission (`EvidenceSubmission`) concernée passe au statut `REJECTED`.
   - **And** le motif de rejet saisi par le DM est enregistré au niveau de cette soumission.
   - **And** l'action est tracée dans l'Audit Log (action=TRANSITION, description="Rejet de preuves par [DM] pour [Référence]").

3. **AC3 — UI et Accès (RBAC)**
   - **Given** un utilisateur connecté,
   - **When** il consulte une recommandation en `PENDING_DM_REVIEW`,
   - **Then** seul le Directeur Métier assigné voit le bouton "Rejeter" et peut l'utiliser via une modale HTMX.
   - **And** le bouton "Rejeter" est **masqué si `assigned_etp` est `None`** (cas DM Porteur — le DM ne peut pas rejeter sa propre soumission).
   - **And** l'ETP assigné voit, lorsque le statut repasse à `IN_PROGRESS`, un bandeau de rejet `bg-red-50 border-red-200` affichant le motif (`review_comment`), la date du rejet (`reviewed_at`) et le nom du DM (`reviewed_by.get_full_name()`), afin de corriger son travail.

## Tasks / Subtasks

- [ ] Task 1 : Backend — Modèles et FSM (AC1, AC2)
  - [ ] Subtask 1.1 : Modifier `EvidenceSubmission` dans `apps/workflow/models.py` pour ajouter les champs :
    - `review_comment` (TextField, blank=True) — motif de rejet saisi par le DM
    - `reviewed_at` (DateTimeField, null=True, blank=True) — horodatage du rejet
    - `reviewed_by` (ForeignKey to `settings.AUTH_USER_MODEL`, null=True, blank=True, on_delete=SET_NULL, related_name='reviewed_submissions') — qui a rejeté (dénormalisé pour requêtes analytiques rapides sans JOIN sur AuditLog)
  - [ ] Subtask 1.2 : Ajouter la transition FSM `reject_evidence()` dans le modèle `Recommendation` (Source: `PENDING_DM_REVIEW`, Target: `IN_PROGRESS`).
  - [ ] Subtask 1.3 : Générer et valider la migration — `python manage.py makemigrations workflow` puis vérifier `python manage.py migrate --check` (requis pour que le pipeline CI ne crashe pas).

- [ ] Task 2 : Backend — Service Layer (AC1, AC2)
  - [ ] Subtask 2.1 : Créer `reject_evidence_submission(*, recommendation, submission_id, reason, performed_by)` dans `apps/workflow/services.py` avec la logique suivante dans `transaction.atomic()` :
    1. **Guard DM Porteur** : si `recommendation.assigned_etp is None`, lever `ValueError("Un DM Porteur ne peut pas rejeter sa propre soumission.")` avant tout traitement.
    2. Verrouiller la reco avec `select_for_update()`.
    3. Valider que `recommendation.status == PENDING_DM_REVIEW` et que `performed_by == recommendation.assigned_dm`.
    4. Mettre à jour `EvidenceSubmission` : `status = REJECTED`, `review_comment = reason`, `reviewed_at = timezone.now()`, `reviewed_by = performed_by`.
    5. Appliquer la transition FSM `recommendation.reject_evidence()` + `recommendation.save()`.
    6. Créer `AuditLog(action=TRANSITION, description="Rejet de preuves par [DM] pour [Référence]", changes={"status": ["PENDING_DM_REVIEW", "IN_PROGRESS"], "review_comment": reason})`.

- [ ] Task 3 : Backend — Formulaire et Vue (AC3)
  - [ ] Subtask 3.1 : Créer `EvidenceRejectForm` dans `apps/workflow/forms.py` avec le champ `reason` (Textarea, obligatoire).
  - [ ] Subtask 3.2 : Créer la vue `EvidenceRejectView` dans `apps/workflow/views.py` gérant le GET (retourne la modale) et le POST (appelle le service et renvoie `HX-Refresh: true`). Vérifier les permissions : `performed_by == recommendation.assigned_dm` ET `recommendation.assigned_etp is not None` (guard DM Porteur). En cas d'échec de validation (`ValueError`), renvoyer HTTP 422 avec `HX-Trigger: {"notify": {"msg": "...", "type": "error"}}`.
  - [ ] Subtask 3.3 : Ajouter la route URL `recommandations/<uuid:pk>/submissions/<uuid:submission_id>/reject/`.

- [ ] Task 4 : Frontend — UI (AC3)
  - [ ] Subtask 4.1 : Créer `templates/workflow/partials/reject_evidence_modal.html` avec le formulaire HTMX (textarea + submit).
  - [ ] Subtask 4.2 : Dans `recommendation_detail.html`, ajouter le bouton "Rejeter" (rouge/danger) avec la double condition : `statut == PENDING_DM_REVIEW` **ET** `recommendation.assigned_etp is not None` (masqué pour DM Porteur). Intégrer le composant Alpine pour l'ouverture de la modale (`x-teleport="body"`, même pattern que `delegate_etp_modal.html`).
  - [ ] Subtask 4.3 : Dans la section des preuves de `recommendation_detail.html`, afficher pour l'ETP (quand `statut == IN_PROGRESS` et qu'une soumission `REJECTED` existe) un bandeau de feedback `bg-red-50 border border-red-200 rounded-xl p-4` contenant :
    - Icône ❌ + titre "Votre soumission a été rejetée"
    - Motif : `{{ rejected_submission.review_comment }}`
    - Rejeté par : `{{ rejected_submission.reviewed_by.get_full_name }}` le `{{ rejected_submission.reviewed_at|date:"d/m/Y à H:i" }}`
    - Appel à l'action : "Veuillez corriger et re-soumettre vos preuves."

- [ ] Task 5 : Tests
  - [ ] Subtask 5.1 : Test de la transition `test_dm_can_reject_evidence_submission` (statut passe à IN_PROGRESS, log Audit créé).
  - [ ] Subtask 5.2 : Test de l'enregistrement du motif `test_evidence_submission_marked_as_rejected`.
  - [ ] Subtask 5.3 : Test RBAC `test_etp_cannot_reject_evidence` (ETP ou autre ne peut pas rejeter → 403).
  - [ ] Subtask 5.4 : Test validation `test_reject_evidence_requires_reason` (motif obligatoire → 422).
  - [ ] Subtask 5.5 : Test guard DM Porteur `test_dm_porteur_cannot_reject_own_submission` — si `assigned_etp is None`, le service lève `ValueError` et la vue renvoie 422.

## Dev Notes

- **Architecture Constraints:**
  - Suivre le pattern Selector -> Service -> View existant.
  - La sécurité d'accès doit vérifier explicitement `recommendation.assigned_dm == user` ET `recommendation.assigned_etp is not None`.
  - La gestion HTMX doit continuer à utiliser le pattern `<template x-teleport="body">` pour la modale, avec un trigger Alpine.js (comme pour `delegate_etp_modal.html`).

- **Cas DM Porteur (CRITIQUE) :**
  - Un DM Porteur (`assigned_etp is None`) a soumis ses propres preuves via `submit_to_dm()`. Il ne doit **jamais** pouvoir rejeter sa propre soumission.
  - Double protection : (1) le bouton "Rejeter" est conditionné à `assigned_etp is not None` dans le template, (2) le service lève `ValueError` si ce guard est contourné.

- **Notifications (hors scope) :**
  - La notification async à l'ETP (email Django-Q2) est **hors périmètre** de cette story — traitée globalement en Epic 4. Le feedback visuel (bandeau de rejet dans l'UI) suffit pour le MVP Epic 3.

- **Contexte de vue pour le bandeau ETP :**
  - La vue `RecommendationDetailView` doit passer `rejected_submission` au contexte : `EvidenceSubmission.objects.filter(recommendation=rec, status='REJECTED').order_by('-reviewed_at').first()`.

### Project Structure Notes

- Alignment with unified project structure:
  - Nouveaux tests à placer dans `apps/workflow/tests/test_services.py` ou `test_views.py`.
  - Templates dans `templates/workflow/partials/`.

### References

- [Source: epics.md#Epic 3] — Contexte FSM et dépendance
- [Source: prd-v2.md] — L'Audit ne doit recevoir aucune alerte sur les rejets internes.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
