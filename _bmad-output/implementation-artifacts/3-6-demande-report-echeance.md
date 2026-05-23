# Story 3.6: Demande de Report d'Échéance

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier**,
I want **demander un allongement du délai de résolution en fournissant une justification et une nouvelle date cible**,
so that **l'Audit Interne puisse évaluer, approuver ou rejeter formellement ma demande — sans passer par email ou téléphone — et que chaque décision soit tracée dans l'audit trail.**

## Status des FR couverts

| FR | Description | Couverture |
|----|-------------|------------|
| **FR13** | Le DM peut demander un report d'échéance justifié | ✅ Story 3.6 |
| **FR14** | L'Audit approuve ou rejette les demandes de report | ✅ Story 3.6 |

## Acceptance Criteria

1. **AC1 — Demande de report par le DM**
   - **Given** une recommandation en état `ASSIGNED`, `IN_PROGRESS`, ou `PENDING_DM_REVIEW` (non clôturée),
   - **When** le DM assigné clique sur "Demander un report" et soumet le formulaire avec une nouvelle date et un motif,
   - **Then** une instance `ExtensionRequest` est créée avec `status=PENDING`, `requested_date=<nouvelle date>`, `reason=<motif>`, `requested_by=request.user`.
   - **And** la recommandation reste dans son état FSM courant (pas de transition FSM — la demande est un objet satellite).
   - **And** l'action est tracée dans l'Audit Log (`action=EXTENSION_REQUESTED`).
   - **And** la modale se ferme et un toast de succès est affiché.

2. **AC2 — Règles de validation de la demande**
   - **Given** le formulaire de demande de report,
   - **When** la nouvelle date soumise est antérieure ou égale à `due_date` actuelle,
   - **Then** le formulaire est invalide (erreur : "La nouvelle date doit être postérieure à l'échéance actuelle.").
   - **When** le motif est vide,
   - **Then** le formulaire est invalide (erreur : "Le motif est obligatoire.").
   - **When** une demande PENDING existe déjà pour cette recommandation,
   - **Then** le service lève `ValueError` (erreur : "Une demande de report est déjà en attente pour cette recommandation.") → HTTP 422.

3. **AC3 — RBAC : qui peut demander un report**
   - **Given** un utilisateur connecté,
   - **Then** seul le DM assigné (`recommendation.assigned_dm == request.user`) peut soumettre une demande de report.
   - **And** une tentative POST par un autre rôle (ETP, AUDIT, DG, EXT) renvoie HTTP 403.
   - **And** le bouton "Demander un report" est uniquement visible pour le DM assigné.

4. **AC4 — Approbation de la demande par l'Audit**
   - **Given** une `ExtensionRequest` en état `PENDING`,
   - **When** un Auditeur clique sur "Approuver" dans l'interface de détail de la recommandation,
   - **Then** `ExtensionRequest.status` passe à `APPROVED`.
   - **And** `Recommendation.due_date` est mis à jour avec `ExtensionRequest.requested_date`.
   - **And** `Recommendation.original_due_date` est **inchangé** (préservation pour les rapports de vieillissement COBAC).
   - **And** un commentaire optionnel de l'Audit est enregistré dans `ExtensionRequest.audit_comment`.
   - **And** l'action est tracée dans l'Audit Log (`action=EXTENSION_APPROVED`).
   - **And** un toast de succès est affiché + rafraîchissement de la page (`HX-Refresh: true`).

5. **AC5 — Rejet de la demande par l'Audit**
   - **Given** une `ExtensionRequest` en état `PENDING`,
   - **When** un Auditeur clique sur "Rejeter" en fournissant un motif obligatoire,
   - **Then** `ExtensionRequest.status` passe à `REJECTED`.
   - **And** `Recommendation.due_date` est **inchangé** (l'échéance initiale est maintenue).
   - **And** le motif de rejet de l'Audit est enregistré dans `ExtensionRequest.audit_comment`.
   - **And** l'action est tracée dans l'Audit Log (`action=EXTENSION_REJECTED`).
   - **And** un toast informatif est affiché au DM lors de sa prochaine visite.

6. **AC6 — UI — Visibilité de la demande en cours**
   - **Given** une recommandation avec une `ExtensionRequest` en état `PENDING`,
   - **When** la page de détail est affichée,
   - **Then** un bandeau ambre/orange est affiché : "⏳ Demande de report en attente — nouvelle date : <date> | Motif : <motif>".
   - **And** le bouton "Demander un report" est désactivé tant qu'une demande est en PENDING.
   - **Given** une `ExtensionRequest` en état `APPROVED`,
   - **Then** un bandeau vert indique "✅ Report approuvé le <date> — Nouvelle échéance : <due_date>".
   - **Given** une `ExtensionRequest` en état `REJECTED`,
   - **Then** un bandeau rouge indique "❌ Report refusé — Motif Audit : <audit_comment>".

## Model : `ExtensionRequest`

**Nouveau modèle** à créer dans `apps/workflow/models.py` (migration requise).

```python
class ExtensionRequest(models.Model):
    """
    Demande de report d'échéance formelle (FR13, FR14).
    
    Modèle satellite de Recommendation — ne modifie pas le FSM.
    Une seule demande PENDING autorisée par recommandation à la fois.
    """
    
    class Status(models.TextChoices):
        PENDING  = "PENDING",  _("En attente")
        APPROVED = "APPROVED", _("Approuvée")
        REJECTED = "REJECTED", _("Rejetée")
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name="extension_requests",
    )
    
    # Demande DM
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="extension_requests_made",
    )
    requested_date = models.DateField(_("Nouvelle date souhaitée"))
    reason = models.TextField(_("Motif de la demande"), max_length=2000)
    
    # Réponse Audit
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="extension_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    audit_comment = models.TextField(_("Commentaire Audit"), max_length=2000, blank=True, default="")
    
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Demande de report")
        verbose_name_plural = _("Demandes de report")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recommendation", "status"], name="idx_ext_req_reco_status"),
        ]
```

## Tasks / Subtasks

- [ ] Task 1 : Backend — Modèle & Migration (AC1, AC2)
  - [ ] Subtask 1.1 : Créer `ExtensionRequest` dans `apps/workflow/models.py` avec les champs définis ci-dessus.
  - [ ] Subtask 1.2 : Créer la migration `0009_add_extension_request.py` via `python manage.py makemigrations workflow`.
  - [ ] Subtask 1.3 : Vérifier `python manage.py migrate --check` après création.

- [ ] Task 2 : Backend — Formulaires (AC2)
  - [ ] Subtask 2.1 : Créer `ExtensionRequestForm(forms.Form)` dans `apps/workflow/forms.py` :
    - `requested_date` : `DateInput(type=date)`, requis, validation > `recommendation.due_date` actuelle.
    - `reason` : `Textarea`, requis, max_length=2000.
    - `__init__` accepte `due_date=None` pour la validation croisée.
  - [ ] Subtask 2.2 : Créer `ExtensionReviewForm(forms.Form)` pour la réponse Audit :
    - `audit_comment` : `Textarea`, requis (motif obligatoire pour l'approbation ET le rejet).
    - Ce formulaire est partagé pour les 2 actions (approve/reject distingué par le nom du bouton submit).

- [ ] Task 3 : Backend — Services (AC1, AC2, AC4, AC5)
  - [ ] Subtask 3.1 : Créer `request_extension(*, recommendation, requested_date, reason, performed_by, ip_address=None)` dans `services.py` :
    1. Guard RBAC : `performed_by != recommendation.assigned_dm` → `PermissionDenied`.
    2. Guard état : `recommendation.status` in (`CLOSED_RESOLVED`, `DRAFT`) → `ValueError`.
    3. Guard doublon : `ExtensionRequest.objects.filter(recommendation=rec, status=PENDING).exists()` → `ValueError("Une demande de report est déjà en attente.")`.
    4. Guard date : `requested_date <= recommendation.due_date` → `ValueError("La nouvelle date doit être postérieure à l'échéance actuelle.")`.
    5. Créer `ExtensionRequest(recommendation=rec, requested_by=performed_by, requested_date=requested_date, reason=reason, status=PENDING)`.
    6. Créer `AuditLog(action=EXTENSION_REQUESTED, ...)`.
    7. Tout dans `transaction.atomic()`.
  - [ ] Subtask 3.2 : Créer `approve_extension(*, extension_request, audit_comment="", performed_by, ip_address=None)` dans `services.py` :
    1. Guard RBAC : `performed_by.role != AUDIT` → `PermissionDenied`.
    2. Guard état : `extension_request.status != PENDING` → `ValueError`.
    3. Dans `transaction.atomic()` avec `select_for_update()` sur la recommandation :
       - `extension_request.status = APPROVED`
       - `extension_request.reviewed_by = performed_by`
       - `extension_request.reviewed_at = now()`
       - `extension_request.audit_comment = audit_comment`
       - `extension_request.save()`
       - `recommendation.due_date = extension_request.requested_date`
       - `recommendation.save(update_fields=["due_date", "updated_at"])`
    4. Créer `AuditLog(action=EXTENSION_APPROVED, changes={"due_date": [old, new]})`.
  - [ ] Subtask 3.3 : Créer `reject_extension(*, extension_request, audit_comment, performed_by, ip_address=None)` dans `services.py` :
    1. Guard RBAC : `performed_by.role != AUDIT` → `PermissionDenied`.
    2. Guard état : `extension_request.status != PENDING` → `ValueError`.
    3. Guard motif : `not audit_comment.strip()` → `ValueError`.
    4. Dans `transaction.atomic()` :
       - `extension_request.status = REJECTED`
       - Mettre à jour `reviewed_by`, `reviewed_at`, `audit_comment`.
       - `extension_request.save()`
    5. Créer `AuditLog(action=EXTENSION_REJECTED, ...)`.

- [ ] Task 4 : Backend — Vues & URLs (AC3, AC4, AC5)
  - [ ] Subtask 4.1 : Créer `ExtensionRequestView(WorkflowAccessMixin, View)` dans `views.py` :
    - `GET` → rendre `partials/extension_request_modal.html` (formulaire DM).
    - `POST` → appeler `request_extension()`, retourner 200 + toast ou 422 + erreur.
  - [ ] Subtask 4.2 : Créer `ExtensionApproveView(AuditRequiredMixin, View)` dans `views.py` :
    - `POST` → appeler `approve_extension()`, retourner `HX-Refresh: true`.
  - [ ] Subtask 4.3 : Créer `ExtensionRejectView(AuditRequiredMixin, View)` dans `views.py` :
    - `POST` → appeler `reject_extension()`, retourner `HX-Refresh: true`.
  - [ ] Subtask 4.4 : Ajouter 3 routes dans `apps/workflow/urls.py` :
    ```python
    path("recommandations/<uuid:pk>/extension/request/",
         views.ExtensionRequestView.as_view(), name="extension-request"),
    path("recommandations/<uuid:pk>/extension/<uuid:ext_id>/approve/",
         views.ExtensionApproveView.as_view(), name="extension-approve"),
    path("recommandations/<uuid:pk>/extension/<uuid:ext_id>/reject/",
         views.ExtensionRejectView.as_view(), name="extension-reject"),
    ```
  - [ ] Subtask 4.5 : Mettre à jour `RecommendationDetailView.get_context_data()` :
    - `pending_extension` : instance `ExtensionRequest` PENDING ou `None`.
    - `extension_history` : toutes les demandes APPROVED/REJECTED (pour historique).
    - `can_request_extension` : booléen (DM assigné + aucune demande PENDING + statut ≠ CLOSED/DRAFT).

- [ ] Task 5 : Frontend — Templates (AC6)
  - [ ] Subtask 5.1 : Créer `templates/workflow/partials/extension_request_modal.html` :
    - En-tête ambre + icône calendrier.
    - Affichage de la `due_date` actuelle.
    - Champs : `requested_date` (date picker, min=due_date+1) + `reason` (textarea).
    - Boutons : "Annuler" (ferme modale Alpine) + "Envoyer la demande" (submit HTMX).
    - `hx-post="{% url 'workflow:extension-request' recommendation.pk %}"`.
    - `hx-target="#extension-modal-container"` + `hx-swap="innerHTML"`.
  - [ ] Subtask 5.2 : Créer `templates/workflow/partials/extension_review_modal.html` :
    - Vue Audit pour approuver ou rejeter.
    - Affiche le motif DM, la date demandée.
    - Champ `audit_comment` (requis dans les 2 cas).
    - Deux boutons : "Approuver" (vert, hx-post vers approve) et "Rejeter" (rouge, hx-post vers reject).
  - [ ] Subtask 5.3 : Mettre à jour `recommendation_detail.html` :
    - Ajouter le bouton "Demander un report" (DM uniquement, désactivé si PENDING).
    - Ajouter le bandeau de statut de la demande (ambre PENDING / vert APPROVED / rouge REJECTED).
    - Ajouter conteneur `#extension-modal-container` + logique Alpine.
    - Ajouter boutons Approuver/Rejeter (Audit uniquement, visible si PENDING).

- [ ] Task 6 : AuditLog — Nouvelles actions (AC1, AC4, AC5)
  - [ ] Subtask 6.1 : Ajouter dans `apps/audit/models.py` (ou équivalent) les nouvelles actions :
    - `EXTENSION_REQUESTED = "EXTENSION_REQUESTED", _("Demande de report soumise")`
    - `EXTENSION_APPROVED = "EXTENSION_APPROVED", _("Demande de report approuvée")`
    - `EXTENSION_REJECTED = "EXTENSION_REJECTED", _("Demande de report rejetée")`
  - [ ] Subtask 6.2 : Créer la migration correspondante (`0004_add_extension_audit_actions.py` ou similaire).

- [ ] Task 7 : Tests (AC1–AC6)
  - [ ] Subtask 7.1 : `test_dm_can_request_extension()` — POST valide → 200, `ExtensionRequest` créé, AuditLog créé.
  - [ ] Subtask 7.2 : `test_duplicate_pending_request_returns_422()` — 2ème demande PENDING → 422.
  - [ ] Subtask 7.3 : `test_extension_date_must_be_future_returns_422()` — date ≤ due_date → 422.
  - [ ] Subtask 7.4 : `test_non_dm_cannot_request_extension()` — ETP/AUDIT POST → 403.
  - [ ] Subtask 7.5 : `test_audit_can_approve_extension()` — approve → `due_date` mise à jour, `original_due_date` inchangé.
  - [ ] Subtask 7.6 : `test_audit_can_reject_extension()` — reject → `due_date` inchangé, `status=REJECTED`.
  - [ ] Subtask 7.7 : `test_reject_without_comment_returns_422()` — motif vide → 422.
  - [ ] Subtask 7.8 : `test_dm_cannot_approve_or_reject()` — DM POST vers approve/reject → 403.

## Dev Notes

### Architecture & Patterns

- **Pas de FSM** : `ExtensionRequest` n'est pas piloté par `django-fsm`. C'est un modèle satellite avec un champ `status` ordinaire (CharField+choices). La recommandation elle-même ne change pas de statut FSM lors d'une demande de report.
- **Pattern service layer** : Selector → Service → View strictement (HackSoft convention).
- **Réutiliser `WorkflowAccessMixin`** pour les vues DM et `AuditRequiredMixin` pour les vues Audit.
- **`select_for_update()`** dans `approve_extension` pour éviter les race conditions lors de la mise à jour de `due_date`.
- **Soft safety** : Si le DM soumet une 2ème demande avant que l'Audit réponde, le service lève une `ValueError` (guard doublon en AC2).

### Modèle de données

- `original_due_date` (déjà en DB) est **immuable** — jamais mis à jour par ce service.
- `due_date` est mis à jour **uniquement** dans `approve_extension()`.
- `ExtensionRequest` a une relation `ManyToOne` vers `Recommendation` — plusieurs demandes peuvent exister par reco (une PENDING à la fois, mais historique APPROVED/REJECTED conservé).

### Sélecteur à ajouter dans `selectors.py`

```python
def get_pending_extension_for_recommendation(*, recommendation) -> ExtensionRequest | None:
    """Retourne la demande de report PENDING pour une recommandation, ou None."""
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation, status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by")
        .first()
    )
```

### AuditLog

- Réutiliser le pattern des stories précédentes pour `AuditLog.create()`.
- `changes` pour EXTENSION_APPROVED : `{"due_date": [str(old_due_date), str(new_due_date)]}`.
- `changes` pour EXTENSION_REQUESTED : `{"requested_date": str(requested_date), "reason": reason[:100]}`.

### Ordre de livraison suggéré

1. Migration (`ExtensionRequest`) + mise à jour `AuditLog` actions
2. Services (`request_extension`, `approve_extension`, `reject_extension`)
3. Formulaires (`ExtensionRequestForm`, `ExtensionReviewForm`)
4. Vues + URLs
5. Templates (modales + mise à jour `recommendation_detail.html`)
6. Tests

### Project Structure Notes

- Nouveau modèle : `apps/workflow/models.py`
- Nouvelles migrations : `apps/workflow/migrations/0009_add_extension_request.py`
- Nouveaux services : `apps/workflow/services.py` (3 nouvelles fonctions)
- Nouvelles vues : `apps/workflow/views.py` (3 nouvelles classes)
- Nouveaux templates :
  - `templates/workflow/partials/extension_request_modal.html` (nouveau)
  - `templates/workflow/partials/extension_review_modal.html` (nouveau)
  - `templates/workflow/recommendation_detail.html` (mise à jour)
- Tests : `apps/workflow/tests/test_views.py` (classe `ExtensionRequestViewTest`)

### References

- [Source: epics.md#Story 3.6] — FR13, FR14
- [Source: prd-v2.md#FR13-FR14] — Demande de report et workflow d'approbation
- [PRD User Journey 3] — Scénario "Claire demande un report à J-10"
- [Pattern: EvidenceRejectView in views.py] — Architecture HTMX modale à reproduire
- [Pattern: validate_evidence_for_audit in services.py] — Pattern guard + transaction.atomic()
- [[security_issues]] — Vuln 2 à corriger en parallèle (selectors RBAC)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
