# Story 3.8: Clôture Définitive par l'Audit Interne

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **Audit Interne**,
I want **vérifier les preuves soumises et clôturer définitivement la recommandation, ou les rejeter vers le DM avec motif si insuffisantes**,
so that **le statut devienne `CLOSED_RESOLVED` (dossier scellé, FR20) ou retourne en `IN_PROGRESS` pour correction**.

## Acceptance Criteria

1. **AC1 — Boutons Audit visibles uniquement en `PENDING_AUDIT_REVIEW`**
   - **Given** une recommandation en `PENDING_AUDIT_REVIEW`
   - **And** l'utilisateur a `role == AUDIT`
   - **When** il consulte la page de détail
   - **Then** deux boutons sont visibles : "Clôturer définitivement" (vert) et "Rejeter vers DM" (rouge)
   - **And** ces boutons ne sont visibles ni pour DM, ni ETP, ni DG, ni EXT
   - **And** ces boutons disparaissent pour les autres statuts (DRAFT, ASSIGNED, IN_PROGRESS, PENDING_DM_REVIEW, CLOSED_RESOLVED)

2. **AC2 — Clôture définitive : transition FSM + métadonnées + AuditLog (FR20)**
   - **Given** l'Audit clique "Clôturer définitivement"
   - **And** confirme l'action via modale de confirmation
   - **When** le service `close_recommendation_by_audit()` est appelé
   - **Then** la recommandation passe en `CLOSED_RESOLVED` via `close_by_audit()` FSM
   - **And** les champs `closed_at = now()` et `closed_by = audit_user` sont enregistrés
   - **And** un `AuditLog` est créé : `action=TRANSITION`, `content_type="Recommendation"`, `object_id=rec.pk`, `changes={"status": ["PENDING_AUDIT_REVIEW", "CLOSED_RESOLVED"], "closed_by_audit": True}`, `description=f"Clôture définitive {rec.reference} par {performed_by.get_full_name()}"`
   - **And** un toast "Recommandation clôturée définitivement" est affiché

3. **AC3 — Rejet vers DM : motif obligatoire + transition FSM + statut soumission**
   - **Given** l'Audit clique "Rejeter vers DM"
   - **When** la modale de rejet s'ouvre avec un champ "Motif" obligatoire (textarea, min 10 caractères)
   - **And** l'Audit saisit le motif et confirme
   - **Then** la recommandation passe en `IN_PROGRESS` via `reject_by_audit()` FSM
   - **And** la dernière `EvidenceSubmission` (status=ACCEPTED) passe à `REJECTED_BY_AUDIT` avec `review_comment=<motif>`, `reviewed_by=audit_user`, `reviewed_at=now()`
   - **And** le draft DM existant est **conservé** (l'ETP/DM repartira de ses fichiers et commentaire pour corriger)
   - **And** un `AuditLog` est créé : `action=TRANSITION`, `changes={"status": ["PENDING_AUDIT_REVIEW", "IN_PROGRESS"], "rejected_by_audit": True, "reason": <motif>}`
   - **And** un toast "Recommandation rejetée et retournée au DM" est affiché

4. **AC4 — Motif vide ou trop court rejeté**
   - **Given** la modale de rejet est ouverte
   - **When** l'Audit soumet avec motif vide OU `motif.strip().length < 10`
   - **Then** le service lève `ValueError` et la vue retourne HTTP 422
   - **And** un message d'erreur explicite est affiché ("Le motif doit comporter au moins 10 caractères")
   - **And** aucune transition FSM, aucun AuditLog créé

5. **AC5 — RBAC : seul un utilisateur `role=AUDIT` peut clôturer ou rejeter (FR20)**
   - **Given** un utilisateur DM, ETP, DG ou EXT
   - **When** il tente un POST sur `recommendation-close-audit` ou `recommendation-reject-audit`
   - **Then** la vue retourne HTTP 403 (via `AuditRequiredMixin`)
   - **And** aucune transition, aucun AuditLog créé

6. **AC6 — Idempotence : statut non éligible rejeté**
   - **Given** une recommandation déjà en `CLOSED_RESOLVED` ou dans un statut < `PENDING_AUDIT_REVIEW`
   - **When** l'Audit tente POST sur `recommendation-close-audit` ou `recommendation-reject-audit`
   - **Then** le service lève `ValueError("La clôture/rejet est impossible depuis l'état « X »")` et la vue retourne HTTP 422
   - **And** aucune transition FSM exécutée

7. **AC7 — Immutabilité après clôture (FR20)**
   - **Given** une recommandation en `CLOSED_RESOLVED`
   - **When** un utilisateur consulte la page de détail
   - **Then** **aucun** bouton d'action métier n'est visible : pas d'upload, pas de soumission, pas de demande de report, pas de validation DM, pas de re-clôture, pas d'assignation, pas de rejet
   - **And** les tentatives POST sur tout endpoint mutant (cf. Subtask 4.2) retournent HTTP 422 avec message "Dossier clôturé, modification impossible"
   - **And** la lecture (GET detail page, list, search, audit log drawer) reste autorisée pour les rôles habilités

8. **AC8 — Bandeau "Clôturée" + métadonnées affichées (FR20)**
   - **Given** une recommandation en `CLOSED_RESOLVED`
   - **When** un utilisateur consulte la page détail
   - **Then** un bandeau vert "✓ Recommandation clôturée définitivement" est affiché en haut
   - **And** les informations suivantes sont visibles : date de clôture (`closed_at` formatée), auditeur responsable (`closed_by.get_full_name()`)
   - **And** un placeholder "🔒 Sceau HMAC : *en attente Story 3.10*" est affiché (emplacement futur du sceau cryptographique)

## Tasks / Subtasks

- [x] **Task 1 — Backend : Transitions FSM** (AC2, AC3, AC6)
  - [x] Subtask 1.1 : Ajouter `close_by_audit()` dans `Recommendation` ([models.py](code/apps/workflow/models.py))
    - `@transition(field=status, source=Status.PENDING_AUDIT_REVIEW, target=Status.CLOSED_RESOLVED)`
    - Docstring : "Clôture définitive Audit Interne (Story 3.8 / FR20). Toute logique métier dans le service layer."
    - Corps : `pass`
  - [x] Subtask 1.2 : Ajouter `reject_by_audit()` dans `Recommendation`
    - `@transition(field=status, source=Status.PENDING_AUDIT_REVIEW, target=Status.IN_PROGRESS)`
    - Docstring : "Rejet Audit Interne avec motif obligatoire (Story 3.8). Symétrique de `reject_by_dm()`."
    - Corps : `pass`

- [x] **Task 2 — Backend : Modèles & Migration** (AC2, AC3, AC8)
  - [x] Subtask 2.1 : Ajouter `REJECTED_BY_AUDIT` dans `EvidenceSubmission.SubmissionStatus` enum ([models.py:656](code/apps/workflow/models.py#L656))
    - `REJECTED_BY_AUDIT = "REJECTED_BY_AUDIT", _("Rejetée par l'Audit")`
    - Mettre à jour le `help_text` du champ `status` pour mentionner le nouveau statut
  - [x] Subtask 2.2 : Ajouter 2 champs sur `Recommendation` ([models.py](code/apps/workflow/models.py)) :
    - `closed_at = models.DateTimeField(_("Clôturée le"), null=True, blank=True, help_text=_("Horodatage exact de la clôture par l'Audit (Story 3.8)."))`
    - `closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, null=True, blank=True, related_name="closed_recommendations", verbose_name=_("Clôturée par"), help_text=_("Auditeur responsable de la clôture définitive."))`
  - [x] Subtask 2.3 : Créer migration `code/apps/workflow/migrations/0014_add_closure_fields_and_audit_rejection.py`
    - `AddField` Recommendation.closed_at, closed_by
    - `AlterField` EvidenceSubmission.status (choices avec REJECTED_BY_AUDIT)
    - Pas de data migration nécessaire (champs nullable, enum additif)

- [x] **Task 3 — Backend : Services** (AC2, AC3, AC4, AC5, AC6)
  - [x] Subtask 3.1 : Créer `close_recommendation_by_audit()` dans [services.py](code/apps/workflow/services.py)
    - Signature kwargs-only : `(*, recommendation, performed_by, ip_address=None) -> Recommendation`
    - Docstring complète avec Args/Returns/Raises et référence AC2, AC5, AC6 / FR20
    - Guard RBAC pré-transaction : `if performed_by.role != User.Role.AUDIT: raise PermissionDenied("Seul l'Audit Interne peut clôturer une recommandation.")`
    - `with transaction.atomic():` + `rec = Recommendation.all_objects.select_for_update().get(pk=recommendation.pk)` (pattern Story 3.5/3.7)
    - Guard FSM : `if rec.status != Recommendation.Status.PENDING_AUDIT_REVIEW: raise ValueError(f"La clôture est impossible depuis l'état « {rec.status} ».")`
    - Mémoriser `source_status = rec.status` avant transition
    - Transition : `rec.close_by_audit()`
    - Renseigner `rec.closed_at = timezone.now()` et `rec.closed_by = performed_by`
    - `rec.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])`
    - AuditLog : `AuditLog.objects.create(action=AuditLog.Action.TRANSITION, content_type="Recommendation", object_id=rec.pk, user=performed_by, changes={"status": [source_status, "CLOSED_RESOLVED"], "closed_by_audit": True}, description=f"Clôture définitive {rec.reference} par {performed_by.get_full_name()}", ip_address=ip_address)`
    - Retourner `rec`
  - [x] Subtask 3.2 : Créer `reject_recommendation_by_audit()` dans services.py
    - Signature : `(*, recommendation, reason: str, performed_by, ip_address=None) -> Recommendation`
    - Docstring avec Args/Returns/Raises, référence AC3, AC4, AC5, AC6
    - Guard RBAC : `if performed_by.role != User.Role.AUDIT: raise PermissionDenied(...)`
    - Guard motif (AC4) : `if not reason or len(reason.strip()) < 10: raise ValueError("Le motif doit comporter au moins 10 caractères.")`
    - `with transaction.atomic():` + `select_for_update()`
    - Guard FSM : status doit être `PENDING_AUDIT_REVIEW`
    - Récupérer la dernière `EvidenceSubmission` avec status=ACCEPTED via :
      ```python
      last_submission = rec.evidence_submissions.filter(
          status=EvidenceSubmission.SubmissionStatus.ACCEPTED
      ).order_by("-created_at").first()
      ```
    - Si `last_submission` existe : mettre à jour `status=REJECTED_BY_AUDIT`, `review_comment=reason.strip()`, `reviewed_by=performed_by`, `reviewed_at=timezone.now()` + `save(update_fields=[...])`
    - Mémoriser `source_status = rec.status`
    - Transition : `rec.reject_by_audit()` + `rec.save(update_fields=["status", "updated_at"])`
    - AuditLog : `changes={"status": [source_status, "IN_PROGRESS"], "rejected_by_audit": True, "reason": reason.strip()}`, `description=f"Rejet Audit {rec.reference} par {performed_by.get_full_name()} — motif: {reason.strip()[:80]}..."`
    - Retourner `rec`

- [x] **Task 4 — Backend : Vues + URLs** (AC1, AC2, AC3, AC4, AC5)
  - [x] Subtask 4.1 : Créer `RecommendationCloseByAuditView(AuditRequiredMixin, View)` dans [views.py](code/apps/workflow/views.py)
    - `_get_recommendation(pk)` : utilise `selectors.get_recommendation_detail_for_user(pk=pk, user=self.request.user)`
    - `GET` : renvoie `_render_close_confirm_modal(request, rec)` (partial HTML)
    - `POST` :
      - try : `close_recommendation_by_audit(recommendation=rec, performed_by=request.user, ip_address=_get_client_ip(request))`
      - except `PermissionDenied` : HTTP 403 (déjà géré par mixin, mais double protection)
      - except `ValueError as exc` : HTTP 422 + `HX-Trigger` notify error
      - succès : `HttpResponse(status=204)` + `HX-Refresh: true` + `HX-Trigger` notify success "Recommandation clôturée définitivement"
  - [x] Subtask 4.2 : Créer `RecommendationRejectByAuditView(AuditRequiredMixin, View)` dans views.py
    - `GET` : renvoie `_render_reject_audit_modal(request, rec, form=None)` avec textarea motif
    - `POST` :
      - Récupérer `reason = request.POST.get("reason", "")`
      - try : `reject_recommendation_by_audit(recommendation=rec, reason=reason, performed_by=request.user, ip_address=...)`
      - except `(ValueError, PermissionDenied) as exc` : HTTP 422 + re-render modale avec erreur via `_render_reject_audit_modal` + `HX-Trigger` notify error
      - succès : `HttpResponse(status=204)` + `HX-Refresh: true` + notify success "Recommandation rejetée et retournée au DM"
  - [x] Subtask 4.3 : Helpers de rendu modale
    - `_render_close_confirm_modal(request, rec)` → `render_to_string("workflow/partials/close_confirm_modal.html", {...})`
    - `_render_reject_audit_modal(request, rec, *, error_message=None, reason="")` → `render_to_string("workflow/partials/reject_audit_modal.html", {...})`
  - [x] Subtask 4.4 : Ajouter URLs dans [urls.py](code/apps/workflow/urls.py) :
    - `path("recommandations/<uuid:pk>/close-audit/", views.RecommendationCloseByAuditView.as_view(), name="recommendation-close-audit"),`
    - `path("recommandations/<uuid:pk>/reject-audit/", views.RecommendationRejectByAuditView.as_view(), name="recommendation-reject-audit"),`

- [x] **Task 5 — Backend : Verrou d'immutabilité après CLOSED_RESOLVED** (AC7)
  - [x] Subtask 5.1 : Créer helper `_ensure_not_closed(recommendation)` dans [views.py](code/apps/workflow/views.py)
    - ```python
      def _ensure_not_closed(recommendation):
          """Garde universel — bloque toute mutation sur une recommandation clôturée (FR20)."""
          if recommendation.status == Recommendation.Status.CLOSED_RESOLVED:
              raise ValueError("Dossier clôturé, modification impossible.")
      ```
    - Le `ValueError` est intercepté par les vues mutantes existantes (pattern actuel) et retourne 422
  - [x] Subtask 5.2 : Appliquer `_ensure_not_closed(rec)` au début de la méthode `post` de toutes les vues mutantes :
    - `RecommendationEditView.post` (si existe)
    - `RecommendationDeleteView.post`
    - `DraftUploadFileView.post`, `DraftDeleteFileView.post`, `DraftSaveCommentView.post`
    - `EvidenceSubmitView.post` (soumission ETP)
    - `EvidenceDGDirectSubmitView.post`
    - `EvidenceValidateForAuditView.post` (validation DM → Audit)
    - `EvidenceRejectByDMView.post` (si existe — rejet interne DM)
    - `ExtensionRequestView.post`, `ExtensionApproveView.post`, `ExtensionRejectView.post`
    - `RecommendationAssignView.post` (DM)
    - `RecommendationAssignDGView.post`
    - `RecommendationCloseByAuditView.post` (auto-protection contre double clôture)
    - `RecommendationRejectByAuditView.post`
  - [x] Subtask 5.3 : Ne PAS appliquer aux vues de lecture seule :
    - `RecommendationDetailView`, `RecommendationListView`
    - `DepartmentSearchView`, `AuditLogDrawerView`
    - Tous les `GET` de modales (le serveur peut servir la modale, mais le POST sera bloqué)

- [x] **Task 6 — Frontend : Templates partials** (AC1, AC2, AC3, AC8)
  - [x] Subtask 6.1 : Créer `code/templates/workflow/partials/close_confirm_modal.html`
    - Header : icône check vert + titre "Clôturer définitivement"
    - Bandeau d'avertissement orange : "⚠️ Cette action est **irréversible**. Le dossier sera scellé et ne pourra plus être modifié (FR20)."
    - Récap visuel : référence, titre court, DM assigné, date dernière soumission
    - Boutons : "Confirmer la clôture" (vert, `hx-post=close-audit`) + "Annuler" (`@click="closeConfirmModalOpen = false"`)
    - `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`
  - [x] Subtask 6.2 : Créer `code/templates/workflow/partials/reject_audit_modal.html`
    - Pattern dupliqué/adapté depuis `reject_evidence_modal.html` (Story 3.4 — DM rejection)
    - Textarea `name="reason"` avec compteur de caractères (min 10) + label "Motif du rejet"
    - Affichage erreur si `error_message` présent dans le contexte
    - Bouton "Rejeter vers DM" (rouge) + "Annuler"
    - `hx-post="{% url 'workflow:recommendation-reject-audit' recommendation.pk %}"` + `hx-target="#reject-audit-modal-container"` + `hx-swap="innerHTML"`
  - [x] Subtask 6.3 : Créer `code/templates/workflow/partials/closure_banner.html` (AC8)
    - Bandeau vert avec icône check (gradient `from-green-50 to-emerald-50` + bordure `border-green-300`)
    - Ligne 1 : "✓ Recommandation clôturée définitivement"
    - Ligne 2 : `Clôturée le {{ recommendation.closed_at|date:"d M Y à H:i" }} par {{ recommendation.closed_by.get_full_name }}`
    - Ligne 3 : badge gris discret : "🔒 Sceau HMAC : en attente Story 3.10"

- [x] **Task 7 — Frontend : Intégration recommendation_detail.html** (AC1, AC7, AC8)
  - [x] Subtask 7.1 : Ajouter au contexte de `RecommendationDetailView.get_context_data()` ([views.py](code/apps/workflow/views.py)) :
    - `context["can_close_by_audit"] = user.role == User.Role.AUDIT and rec.status == Recommendation.Status.PENDING_AUDIT_REVIEW`
    - `context["can_reject_by_audit"] = user.role == User.Role.AUDIT and rec.status == Recommendation.Status.PENDING_AUDIT_REVIEW`
    - `context["is_closed"] = rec.status == Recommendation.Status.CLOSED_RESOLVED`
  - [x] Subtask 7.2 : Dans [recommendation_detail.html](code/templates/workflow/recommendation_detail.html) :
    - Ajouter état Alpine : `closeConfirmModalOpen: false, rejectAuditModalOpen: false`
    - En haut de la page (après le header de reco) : `{% if is_closed %}{% include "workflow/partials/closure_banner.html" %}{% endif %}`
    - Dans la section actions (à côté des autres boutons) :
      ```html
      {% if can_close_by_audit %}
      <button hx-get="{% url 'workflow:recommendation-close-audit' recommendation.pk %}"
              hx-target="#close-confirm-modal-container" hx-swap="innerHTML"
              @click="closeConfirmModalOpen = true"
              class="...green styling...">
        ✓ Clôturer définitivement
      </button>
      {% endif %}
      {% if can_reject_by_audit %}
      <button hx-get="{% url 'workflow:recommendation-reject-audit' recommendation.pk %}"
              hx-target="#reject-audit-modal-container" hx-swap="innerHTML"
              @click="rejectAuditModalOpen = true"
              class="...red styling...">
        ✗ Rejeter vers DM
      </button>
      {% endif %}
      ```
    - Conteneurs modales en fin de page :
      ```html
      <div x-show="closeConfirmModalOpen" x-cloak class="modal-overlay-pattern">
        <div id="close-confirm-modal-container"></div>
      </div>
      <div x-show="rejectAuditModalOpen" x-cloak class="modal-overlay-pattern">
        <div id="reject-audit-modal-container"></div>
      </div>
      ```
  - [x] Subtask 7.3 : Si `is_closed`, masquer **tous** les boutons d'action métier existants (extension, validation DM, soumission, rejet, etc.) via `{% if not is_closed %}` wrapper (UX complement — la protection serveur est faite Task 5)

- [x] **Task 8 — Selector : filtre par statut "clôturée"** (Bonus exploration historique)
  - [x] Subtask 8.1 : Vérifier que `get_recommendations_for_user()` ([selectors.py](code/apps/workflow/selectors.py)) inclut bien les recos `CLOSED_RESOLVED` dans la liste de l'Audit (probablement déjà le cas, à vérifier)
  - [x] Subtask 8.2 : Vérifier que le filtre `?statut=closed` est exposé dans le formulaire de filtre du dashboard (`recommendation_list.html` / `recommendation_filters.html`) — sinon, l'ajouter

- [x] **Task 9 — Tests Services** (AC2, AC3, AC4, AC5, AC6)
  - [x] Subtask 9.1 : `CloseRecommendationByAuditServiceTest(TestCase)` dans [test_services.py](code/apps/workflow/tests/test_services.py)
    - `test_close_success` — Audit clôture une reco PENDING_AUDIT_REVIEW → CLOSED_RESOLVED + closed_at/closed_by renseignés
    - `test_close_creates_audit_log_with_closed_by_audit_flag` — vérifie AuditLog `changes["closed_by_audit"] is True`
    - `test_close_permission_denied_for_dm` — DM tente clôture → `PermissionDenied`
    - `test_close_permission_denied_for_dg` — DG tente clôture → `PermissionDenied`
    - `test_close_invalid_status_in_progress_raises_value_error` — Reco IN_PROGRESS → `ValueError`
    - `test_close_invalid_status_draft_raises_value_error` — Reco DRAFT → `ValueError`
    - `test_close_idempotent_already_closed` — Reco déjà CLOSED_RESOLVED → `ValueError`
  - [x] Subtask 9.2 : `RejectRecommendationByAuditServiceTest(TestCase)`
    - `test_reject_success` — Audit rejette → IN_PROGRESS + submission status REJECTED_BY_AUDIT + review_comment + reviewed_by/at renseignés
    - `test_reject_draft_preserved_for_correction` — vérifie qu'un draft DM existant n'est PAS supprimé après rejet Audit
    - `test_reject_creates_audit_log` — AuditLog `changes["rejected_by_audit"] is True` + `changes["reason"]`
    - `test_reject_empty_reason_raises_value_error`
    - `test_reject_short_reason_raises_value_error` — motif < 10 chars
    - `test_reject_whitespace_only_reason_raises_value_error` — motif "   " → strip().length < 10
    - `test_reject_permission_denied_for_dm`
    - `test_reject_invalid_status_raises_value_error`

- [x] **Task 10 — Tests Views** (AC1, AC2, AC3, AC5, AC6)
  - [x] Subtask 10.1 : `RecommendationCloseByAuditViewTest(EvidenceSubmissionTestMixin, TestCase)` dans [test_views.py](code/apps/workflow/tests/test_views.py)
    - `test_audit_can_get_close_modal` — GET → 200 + template `close_confirm_modal.html`
    - `test_audit_can_close_recommendation` — POST → 204 + HX-Refresh
    - `test_close_modal_unauthorized_for_dm` — GET → 403
    - `test_close_post_unauthorized_for_dm` — POST → 403
    - `test_close_unavailable_for_in_progress_status` — POST sur IN_PROGRESS → 422
    - `test_close_context_can_close_by_audit_true_only_for_audit_in_pending_audit_review` — vérifie le contexte sur `RecommendationDetailView` (AC1)
  - [x] Subtask 10.2 : `RecommendationRejectByAuditViewTest(EvidenceSubmissionTestMixin, TestCase)`
    - `test_audit_can_get_reject_modal` — GET → 200 + template `reject_audit_modal.html`
    - `test_audit_can_reject_with_valid_reason` — POST avec motif ≥ 10 chars → 204
    - `test_reject_short_reason_returns_422` — motif < 10 → 422
    - `test_reject_empty_reason_returns_422`
    - `test_dm_cannot_reject_audit` — 403
    - `test_reject_updates_submission_to_rejected_by_audit` — vérifie EvidenceSubmission.status après rejet

- [x] **Task 11 — Tests Immutabilité après clôture** (AC7)
  - [x] Subtask 11.1 : `ImmutabilityAfterClosureTest(EvidenceSubmissionTestMixin, TestCase)` dans test_views.py
    - Setup commun : créer une reco CLOSED_RESOLVED via update direct DB
    - Tests à exécuter (paramétrer si possible via `subTest`) :
      - `test_close_audit_blocked_after_closure` — POST close-audit → 422
      - `test_reject_audit_blocked_after_closure` — POST reject-audit → 422
      - `test_assign_dm_blocked_after_closure` — POST assign → 422
      - `test_draft_upload_blocked_after_closure` — POST draft-upload → 422
      - `test_draft_delete_blocked_after_closure` — POST draft-delete → 422
      - `test_draft_save_comment_blocked_after_closure` — POST draft-save-comment → 422
      - `test_evidence_submit_blocked_after_closure` — POST evidence-submit → 422
      - `test_dg_direct_submit_blocked_after_closure` — POST evidence-submit-dg → 422
      - `test_dm_validate_blocked_after_closure` — POST dm-validate → 422
      - `test_extension_request_blocked_after_closure`
      - `test_extension_approve_blocked_after_closure`
      - `test_extension_reject_blocked_after_closure`
      - `test_recommendation_delete_blocked_after_closure`
    - `test_detail_view_still_accessible_after_closure` — GET → 200
    - `test_list_view_includes_closed_recommendations` — la reco apparaît bien en lecture

- [x] **Task 12 — Validation Docker + Tests verts**
  - [x] Subtask 12.1 : `docker compose exec web python manage.py makemigrations` — vérifier que seule la migration 0014 est créée
  - [x] Subtask 12.2 : `docker compose exec web python manage.py migrate` — appliquer la migration
  - [x] Subtask 12.3 : `docker compose exec web python manage.py test apps.workflow --verbosity=2` — viser 450+ tests verts (424 actuels + ~30 nouveaux)
  - [x] Subtask 12.4 : Test manuel navigateur :
    - Audit clôture une reco PENDING_AUDIT_REVIEW → vérifier bandeau, métadonnées, boutons disparus
    - Audit rejette avec motif court (< 10) → vérifier erreur 422 + message
    - Audit rejette avec motif valide → vérifier retour IN_PROGRESS et draft conservé
    - DM tente de modifier une reco CLOSED_RESOLVED → vérifier message "Dossier clôturé"

## Dev Notes

### Décisions architecturales (validées 2026-05-28)

- **2 transitions FSM distinctes** : `close_by_audit()` et `reject_by_audit()` — cohérent avec le pattern `approve_for_audit()` / `reject_by_dm()` des Stories 3.4/3.5. Pas de transition paramétrée.
- **Champs `closed_at` / `closed_by`** : ajoutés sur `Recommendation` pour permettre à Story 3.10 (HMAC) de retrouver le moment précis de la clôture et l'identité du responsable sans dépendre du parsing AuditLog.
- **Nouveau statut `REJECTED_BY_AUDIT`** : ajouté à `EvidenceSubmission.SubmissionStatus` (décision validée — option A). Permet de filtrer dans les requêtes analytiques (taux de rejet Audit vs DM, KPI cibles 2-5% du PRD L.80) sans JOIN sur `User.role`.
- **Draft DM conservé après rejet Audit** (décision validée) : la submission rejetée passe en `REJECTED_BY_AUDIT` (lecture historique), mais le draft existant du DM/ETP reste accessible pour qu'ils repartent de leur travail et corrigent. Pas de réinitialisation forcée.
- **Notification au DM hors scope** (décision validée) : reporté à Epic 4 (FR22-FR23). Pas de modèle Notification ni d'email dans Story 3.8. L'AuditLog est la source de vérité historique.
- **Immutabilité côté serveur ET client** : la protection contre les mutations post-clôture est faite côté serveur via `_ensure_not_closed()` (Task 5) — l'absence de boutons côté template (Task 7) est un complément UX, jamais une garantie de sécurité.
- **Pas de Sceau HMAC dans Story 3.8** : Story 3.10 ajoutera le calcul HMAC sur post-save de `close_by_audit()`. Stub visible dans le bandeau (AC8) pour préparer la place.

### Patterns à réutiliser (vérifiés)

- **`AuditRequiredMixin`** ([mixins.py](code/apps/users/mixins.py)) — guard `role=AUDIT`
- **Pattern django-fsm + select_for_update** : `Recommendation.all_objects.select_for_update().get(pk=...)` — Stories 3.5/3.7 (jamais `refresh_from_db()` car django-fsm lève AttributeError)
- **`AuditLog.Action.TRANSITION`** — déjà utilisé pour toutes les transitions FSM
- **`_get_client_ip(request)`** ([views.py](code/apps/workflow/views.py)) — extraction IP pour AuditLog
- **`reject_evidence_modal.html`** (Story 3.4) — pattern modale rejet avec motif et compteur de caractères
- **`approve_evidence_modal.html`** — pattern modale confirmation
- **`EvidenceSubmissionTestMixin`** ([test_views.py:830](code/apps/workflow/tests/test_views.py#L830)) — base class pour tests avec helpers `_create_draft_and_upload()`, `_create_in_progress_recommendation_dm_porteur()`
- **`get_recommendation_detail_for_user(pk, user)`** ([selectors.py](code/apps/workflow/selectors.py)) — récupération RBAC-aware

### Couverture NFR

- **NFR-SEC-05** (AuditLog append-only, 12 mois) : couvert AC2, AC3
- **NFR-PERF-02** (UI < 200ms P95 via HTMX) : pattern `hx-post` + 204 + HX-Refresh conservé
- **NFR-SEC-04** (intégrité) : préparé par les champs `closed_at`/`closed_by` qui alimenteront Story 3.10 (HMAC-SHA256)

### Cas spéciaux & invariants

- **django-fsm + select_for_update** : utiliser `Recommendation.all_objects.select_for_update().get(pk=...)`, **jamais** `refresh_from_db()`
- **`closed_at` timezone** : `django.utils.timezone.now()` (pas `datetime.now()`)
- **Idempotence** : double clic sur "Clôturer" → 422 (pas 500), géré par guard FSM
- **Motif rejet** : `reason.strip()` + check longueur côté serveur (jamais faire confiance au client)
- **`update_fields` explicite** : pour éviter d'écraser des champs concurrents (préserve la cohérence avec les transactions DG/extension en parallèle)
- **Tag enum REJECTED_BY_AUDIT** : doit aussi être ajouté dans le help_text et les éventuels affichages liste/filtre

### Project Structure Notes

**Fichiers à modifier** :
- `code/apps/workflow/models.py` — 2 transitions FSM + 2 champs `closed_at`/`closed_by` + 1 enum value
- `code/apps/workflow/services.py` — 2 services `close_recommendation_by_audit` + `reject_recommendation_by_audit`
- `code/apps/workflow/views.py` — 2 vues + helper `_ensure_not_closed` + 2 helpers `_render_*_modal` + 3 clés contexte
- `code/apps/workflow/urls.py` — 2 routes
- `code/templates/workflow/recommendation_detail.html` — 2 boutons conditionnels + bandeau + conteneurs modales + état Alpine
- `code/apps/workflow/tests/test_services.py` — ~15 tests dans 2 nouvelles classes
- `code/apps/workflow/tests/test_views.py` — ~12 tests dans 3 nouvelles classes (close, reject, immutability)
- Vues existantes mutantes (Task 5.2) — ajout `_ensure_not_closed(rec)` en début de POST

**Fichiers à créer** :
- `code/apps/workflow/migrations/0014_add_closure_fields_and_audit_rejection.py`
- `code/templates/workflow/partials/close_confirm_modal.html`
- `code/templates/workflow/partials/reject_audit_modal.html`
- `code/templates/workflow/partials/closure_banner.html`

### References

- `_bmad-output/planning-artifacts/epics.md` L.389-401 (Story 3.8 ACs) + L.471-484 (Story 3.10 HMAC dépendant)
- `_bmad-output/planning-artifacts/prd-v2.md` FR20 L.287 + FR24 L.295 (HMAC hors scope) + KPI rejet Audit L.80 (cible 2-5%)
- `_bmad-output/planning-artifacts/architecture-v2.md` L.944-945 (FSM `close_by_audit` / `reject_by_audit`) + L.1117-1120 (séquence diagram clôture)
- Story 3.5 artifact : `_bmad-output/implementation-artifacts/3-5-validation-dm-envoi-audit-exemption-pv.md` (pattern `validate_evidence_for_audit`, transition `approve_for_audit`)
- Story 3.7 artifact : `_bmad-output/implementation-artifacts/3-7-soumission-exclusive-dg.md` (pattern AuditLog, select_for_update, error handling)
- Story 3.4 artifact : `_bmad-output/implementation-artifacts/3-4-rejet-interne-dm-boucle-amelioration.md` (pattern modale rejet avec motif, transition `reject_by_dm`)
- **Décisions validées (2026-05-28)** : Option A (REJECTED_BY_AUDIT explicit) + AC9 reporté à Epic 4 + Draft conservé après rejet Audit

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (planification) / claude-opus-4-7 (exécution prévue)

### Debug Log References

### Completion Notes List

- **2026-05-28** : Artifact créé via workflow bmad `create-story` (exécution manuelle dans Claude Code, skill non enregistré).
  - 3 décisions utilisateur validées avant rédaction : (1) `REJECTED_BY_AUDIT` ajouté au enum, (2) Notification DM reportée à Epic 4 (AC9 supprimée), (3) Draft DM conservé après rejet Audit.
  - Architecture FSM alignée sur `architecture-v2.md` L.944-945 : 2 transitions distinctes `close_by_audit` + `reject_by_audit`.
  - Story 3.10 (HMAC-SHA256) prévue en suite immédiate — placeholder visible dans le bandeau de clôture (AC8).

### File List

*(À compléter pendant l'implémentation)*
