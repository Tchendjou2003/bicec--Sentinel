# Story 3.6: Demande de Report d'Ã‰chÃ©ance

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur MÃ©tier (ou Direction GÃ©nÃ©rale personnellement assignÃ©(e))**,
I want **demander un allongement du dÃ©lai de rÃ©solution en fournissant une justification et une nouvelle date cible**,
so that **l'Audit Interne puisse Ã©valuer, approuver ou rejeter formellement ma demande â€” sans passer par email ou tÃ©lÃ©phone â€” et que chaque dÃ©cision soit tracÃ©e dans l'audit trail.**

## Status des FR couverts

| FR | Description | Couverture |
|----|-------------|------------|
| **FR13** | Le DM peut demander un report d'Ã©chÃ©ance justifiÃ© | âœ… Story 3.6 |
| **FR14** | L'Audit approuve ou rejette les demandes de report | âœ… Story 3.6 |
| **FR34** | La DG peut demander un report d'Ã©chÃ©ance | âœ… Story 3.6 |

## Acceptance Criteria

1. **AC1 â€” Demande de report par un demandeur autorisÃ© (DM ou DG)**
   - **Given** une recommandation en Ã©tat `ASSIGNED`, `IN_PROGRESS`, ou `PENDING_DM_REVIEW` (non clÃ´turÃ©e),
   - **When** un demandeur autorisÃ© (DM assignÃ© OU DG personnellement assignÃ©(e) comme directeur de mission de la recommandation) clique sur "Demander un report" et soumet le formulaire avec une nouvelle date et un motif,
   - **Then** une instance `ExtensionRequest` est crÃ©Ã©e avec `status=PENDING`, `requested_date=<nouvelle date>`, `reason=<motif>`, `requested_by=request.user`.
   - **And** la recommandation reste dans son Ã©tat FSM courant (pas de transition FSM â€” la demande est un objet satellite).
   - **And** l'action est tracÃ©e dans l'Audit Log (`action=EXTENSION_REQUESTED`).
   - **And** la modale se ferme et un toast de succÃ¨s est affichÃ©.

2. **AC2 â€” RÃ¨gles de validation de la demande**
   - **Given** le formulaire de demande de report,
   - **When** la nouvelle date soumise est antÃ©rieure ou Ã©gale Ã  `due_date` actuelle,
   - **Then** le formulaire est invalide (erreur : "La nouvelle date doit Ãªtre postÃ©rieure Ã  l'Ã©chÃ©ance actuelle.").
   - **When** le motif est vide,
   - **Then** le formulaire est invalide (erreur : "Le motif est obligatoire.").
   - **When** une demande PENDING existe dÃ©jÃ  pour cette recommandation,
   - **Then** le service lÃ¨ve `ValueError` (erreur : "Une demande de report est dÃ©jÃ  en attente pour cette recommandation.") â†’ HTTP 422.

3. **AC3 â€” RBAC : qui peut demander un report**
   - **Given** un utilisateur connectÃ©,
   - **Then** la demande est autorisÃ©e si : `recommendation.assigned_dm == request.user` â€” couvre le DM assignÃ© ET le DG personnellement assignÃ© comme directeur de mission (le champ `assigned_dm` peut contenir un utilisateur de rÃ´le DM ou DG).
   - **And** toute tentative POST par un utilisateur autre que `recommendation.assigned_dm` (ETP, AUDIT, EXT, ADMIN_IT, DG non personnellement assignÃ©) renvoie HTTP 403.
   - **And** le bouton "Demander un report" est visible uniquement pour `request.user == recommendation.assigned_dm`.

4. **AC4 â€” Approbation de la demande par l'Audit**
   - **Given** une `ExtensionRequest` en Ã©tat `PENDING`,
   - **When** un Auditeur clique sur "Approuver" dans l'interface de dÃ©tail de la recommandation,
   - **Then** `ExtensionRequest.status` passe Ã  `APPROVED`.
   - **And** `Recommendation.due_date` est mis Ã  jour avec `ExtensionRequest.requested_date`.
   - **And** `Recommendation.original_due_date` est **inchangÃ©** (prÃ©servation pour les rapports de vieillissement COBAC â€” invariant formalisÃ© en AC8 et testÃ© par Subtask 7.9).
   - **And** le champ `audit_comment` est **optionnel** lors de l'approbation (diffÃ©rence-clÃ© vs AC5 â€” rejet).
   - **And** s'il est fourni, il est enregistrÃ© dans `ExtensionRequest.audit_comment`.
   - **And** l'action est tracÃ©e dans l'Audit Log (`action=EXTENSION_APPROVED`, `changes={"due_date": [old, new]}`).
   - **And** un toast de succÃ¨s est affichÃ© + rafraÃ®chissement de la page (`HX-Refresh: true`).

5. **AC5 â€” Rejet de la demande par l'Audit**
   - **Given** une `ExtensionRequest` en Ã©tat `PENDING`,
   - **When** un Auditeur clique sur "Rejeter" en fournissant un motif obligatoire,
   - **Then** `ExtensionRequest.status` passe Ã  `REJECTED`.
   - **And** `Recommendation.due_date` est **inchangÃ©** (l'Ã©chÃ©ance initiale est maintenue).
   - **And** le motif de rejet de l'Audit est enregistrÃ© dans `ExtensionRequest.audit_comment`.
   - **And** l'action est tracÃ©e dans l'Audit Log (`action=EXTENSION_REJECTED`).
   - **And** un toast informatif est affichÃ© au DM lors de sa prochaine visite.

6. **AC6 â€” UI â€” VisibilitÃ© de la demande en cours**
   - **Given** une recommandation avec une `ExtensionRequest` en Ã©tat `PENDING`,
   - **When** la page de dÃ©tail est affichÃ©e,
   - **Then** un bandeau ambre/orange est affichÃ© : "â³ Demande de report en attente â€” nouvelle date : <date> | Motif : <motif>".
   - **And** le bouton "Demander un report" est dÃ©sactivÃ© tant qu'une demande est en PENDING.
   - **Given** une `ExtensionRequest` en Ã©tat `APPROVED`,
   - **Then** un bandeau vert indique "âœ… Report approuvÃ© le <date> â€” Nouvelle Ã©chÃ©ance : <due_date>".
   - **Given** une `ExtensionRequest` en Ã©tat `REJECTED`,
   - **Then** un bandeau rouge indique "âŒ Report refusÃ© â€” Motif Audit : <audit_comment>".

7. **AC7 â€” Permissions Audit : tous les auditeurs peuvent statuer**
   - **Given** une `ExtensionRequest` en Ã©tat `PENDING`,
   - **When** un utilisateur avec `role == User.Role.AUDIT` consulte la recommandation,
   - **Then** il voit les boutons "Approuver" et "Rejeter" et peut les actionner avec succÃ¨s (200).
   - **And** le flag `is_audit_admin` **n'est PAS requis** pour cette action (contrairement Ã  la gestion des comptes â€” ADR-10).
   - **And** une tentative POST par un rÃ´le non-AUDIT (DM, ETP, DG, EXT, ADMIN_IT) renvoie HTTP 403.

8. **AC8 â€” Invariant `original_due_date` (COBAC)**
   - **Given** une approbation `approve_extension()` qui met Ã  jour `due_date`,
   - **Then** `Recommendation.original_due_date` reste **strictement identique** avant et aprÃ¨s l'opÃ©ration.
   - **And** cet invariant est garanti par l'absence de modification explicite dans le service (vÃ©rifiÃ© par `Subtask 7.9`).

## Model : `ExtensionRequest`

**Nouveau modÃ¨le** Ã  crÃ©er dans `apps/workflow/models.py` (migration requise).

```python
class ExtensionRequest(models.Model):
    """
    Demande de report d'Ã©chÃ©ance formelle (FR13, FR14).
    
    ModÃ¨le satellite de Recommendation â€” ne modifie pas le FSM.
    Une seule demande PENDING autorisÃ©e par recommandation Ã  la fois.
    """
    
    class Status(models.TextChoices):
        PENDING  = "PENDING",  _("En attente")
        APPROVED = "APPROVED", _("ApprouvÃ©e")
        REJECTED = "REJECTED", _("RejetÃ©e")
    
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
    requested_date = models.DateField(_("Nouvelle date souhaitÃ©e"))
    reason = models.TextField(_("Motif de la demande"), max_length=2000)
    
    # RÃ©ponse Audit
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

- [x] Task 1 : Backend â€” ModÃ¨le & Migration (AC1, AC2)
  - [x] Subtask 1.1 : CrÃ©er `ExtensionRequest` dans `apps/workflow/models.py` avec les champs dÃ©finis ci-dessus.
  - [x] Subtask 1.2 : CrÃ©er la migration `0009_add_extension_request.py` via `python manage.py makemigrations workflow`.
  - [x] Subtask 1.3 : VÃ©rifier `python manage.py migrate --check` aprÃ¨s crÃ©ation.

- [x] Task 2 : Backend â€” Formulaires (AC2)
  - [x] Subtask 2.1 : CrÃ©er `ExtensionRequestForm(forms.Form)` dans `apps/workflow/forms.py` :
    - `requested_date` : `DateInput(type=date)`, requis, validation > `recommendation.due_date` actuelle.
    - `reason` : `Textarea`, requis, max_length=2000.
    - `__init__` accepte `due_date=None` pour la validation croisÃ©e.
  - [x] Subtask 2.2 : CrÃ©er **deux** formulaires distincts dans `apps/workflow/forms.py` (clarification AC4 vs AC5) :
    - `ExtensionApproveForm(forms.Form)` :
      - `audit_comment` : `Textarea`, **optionnel** (`required=False`, `max_length=2000`).
      - UtilisÃ© par `ExtensionApproveView`.
    - `ExtensionRejectForm(forms.Form)` :
      - `audit_comment` : `Textarea`, **obligatoire** (`required=True`, `max_length=2000`).
      - `error_messages={"required": _("Le motif de rejet est obligatoire.")}`
      - UtilisÃ© par `ExtensionRejectView`.
    - Justification : Ã©viter le pattern "form partagÃ© avec rÃ¨gle conditionnelle" qui obscurcit l'intention mÃ©tier.

- [x] Task 3 : Backend â€” Services (AC1, AC2, AC4, AC5)
  - [x] Subtask 3.1 : CrÃ©er `request_extension(*, recommendation, requested_date, reason, performed_by, ip_address=None)` dans `services.py` :
    1. Guard RBAC (FR13 + FR34) :
       ```python
       # assigned_dm peut Ãªtre un DM ou un DG â€” l'assignation personnelle est le seul critÃ¨re
       if performed_by != recommendation.assigned_dm:
           raise PermissionDenied
       ```
    2. Guard Ã©tat : `recommendation.status` in (`CLOSED_RESOLVED`, `DRAFT`) â†’ `ValueError`.
    3. Guard doublon : `ExtensionRequest.objects.filter(recommendation=rec, status=PENDING).exists()` â†’ `ValueError("Une demande de report est dÃ©jÃ  en attente.")`.
    4. Guard date : `requested_date <= recommendation.due_date` â†’ `ValueError("La nouvelle date doit Ãªtre postÃ©rieure Ã  l'Ã©chÃ©ance actuelle.")`.
    5. CrÃ©er `ExtensionRequest(recommendation=rec, requested_by=performed_by, requested_date=requested_date, reason=reason, status=PENDING)`.
    6. CrÃ©er `AuditLog(action=EXTENSION_REQUESTED, ...)`.
    7. Tout dans `transaction.atomic()`.
  - [x] Subtask 3.2 : CrÃ©er `approve_extension(*, extension_request, performed_by, audit_comment="", ip_address=None)` dans `services.py` :
    1. Guard RBAC : `performed_by.role != User.Role.AUDIT` â†’ `PermissionDenied` (AC7 : `is_audit_admin` n'est PAS requis).
    2. Guard Ã©tat : `extension_request.status != PENDING` â†’ `ValueError`.
    3. Dans `transaction.atomic()` avec `select_for_update()` sur la recommandation :
       - `old_due_date = recommendation.due_date` (pour AuditLog)
       - `extension_request.status = APPROVED`
       - `extension_request.reviewed_by = performed_by`
       - `extension_request.reviewed_at = timezone.now()`
       - `extension_request.audit_comment = audit_comment` (peut Ãªtre vide â€” AC4)
       - `extension_request.save()`
       - `recommendation.due_date = extension_request.requested_date`
       - `recommendation.save(update_fields=["due_date", "updated_at"])`
       - **NE PAS toucher** `original_due_date` (invariant AC8 / Subtask 7.9).
    4. CrÃ©er `AuditLog(action=EXTENSION_APPROVED, changes={"due_date": [str(old_due_date), str(new_due_date)]})`.
  - [x] Subtask 3.3 : CrÃ©er `reject_extension(*, extension_request, performed_by, audit_comment, ip_address=None)` dans `services.py` (note : `audit_comment` **sans dÃ©faut** = obligatoire Ã  l'appel) :
    1. Guard RBAC : `performed_by.role != User.Role.AUDIT` â†’ `PermissionDenied` (AC7).
    2. Guard Ã©tat : `extension_request.status != PENDING` â†’ `ValueError`.
    3. Guard motif : `not audit_comment.strip()` â†’ `ValueError("Le motif de rejet est obligatoire.")`.
    4. Dans `transaction.atomic()` :
       - `extension_request.status = REJECTED`
       - Mettre Ã  jour `reviewed_by`, `reviewed_at`, `audit_comment`.
       - `extension_request.save()`
       - **NE PAS modifier** `recommendation.due_date` (l'Ã©chÃ©ance initiale est maintenue).
    5. CrÃ©er `AuditLog(action=EXTENSION_REJECTED, changes={"audit_comment": audit_comment[:100]})`.

- [x] Task 4 : Backend â€” SÃ©lecteur, Vues & URLs (AC3, AC4, AC5, AC7)
  - [x] Subtask 4.0 : Ajouter `get_pending_extension_for_recommendation(*, recommendation) -> ExtensionRequest | None` dans `apps/workflow/selectors.py` :
    ```python
    def get_pending_extension_for_recommendation(*, recommendation):
        return (
            ExtensionRequest.objects
            .filter(recommendation=recommendation, status=ExtensionRequest.Status.PENDING)
            .select_related("requested_by")
            .first()
        )
    ```
    Et `get_extension_history_for_recommendation(*, recommendation)` pour l'historique APPROVED/REJECTED.
  - [x] Subtask 4.1 : CrÃ©er `ExtensionRequestView(WorkflowAccessMixin, View)` dans `views.py` :
    - `GET` â†’ rendre `partials/extension_request_modal.html` (formulaire DM).
    - `POST` â†’ appeler `request_extension()`, retourner 200 + toast ou 422 + erreur.
  - [x] Subtask 4.2 : CrÃ©er `ExtensionApproveView(AuditRequiredMixin, View)` dans `views.py` :
    - `POST` â†’ appeler `approve_extension()`, retourner `HX-Refresh: true`.
  - [x] Subtask 4.3 : CrÃ©er `ExtensionRejectView(AuditRequiredMixin, View)` dans `views.py` :
    - `POST` â†’ appeler `reject_extension()`, retourner `HX-Refresh: true`.
  - [x] Subtask 4.4 : Ajouter 3 routes dans `apps/workflow/urls.py` :
    ```python
    path("recommandations/<uuid:pk>/extension/request/",
         views.ExtensionRequestView.as_view(), name="extension-request"),
    path("recommandations/<uuid:pk>/extension/<uuid:ext_id>/approve/",
         views.ExtensionApproveView.as_view(), name="extension-approve"),
    path("recommandations/<uuid:pk>/extension/<uuid:ext_id>/reject/",
         views.ExtensionRejectView.as_view(), name="extension-reject"),
    ```
  - [x] Subtask 4.5 : Mettre Ã  jour `RecommendationDetailView.get_context_data()` (importer les 2 sÃ©lecteurs de la Subtask 4.0) :
    - `pending_extension` : appel Ã  `selectors.get_pending_extension_for_recommendation(recommendation=self.object)` (None ou instance).
    - `extension_history` : appel Ã  `selectors.get_extension_history_for_recommendation(recommendation=self.object)`.
    - `can_request_extension` : boolÃ©en â€” `user == recommendation.assigned_dm` (couvre DM ET DG personnellement assignÃ©s), **ET** `pending_extension is None`, **ET** `status not in (CLOSED_RESOLVED, DRAFT)`.
    - `can_review_extension` : boolÃ©en â€” `user.role == User.Role.AUDIT` (AC7).

- [x] Task 5 : Frontend â€” Templates (AC6)
  - [x] Subtask 5.1 : CrÃ©er `templates/workflow/partials/extension_request_modal.html` :
    - En-tÃªte ambre + icÃ´ne calendrier.
    - Affichage de la `due_date` actuelle.
    - Champs : `requested_date` (date picker, min=due_date+1) + `reason` (textarea).
    - Boutons : "Annuler" (ferme modale Alpine) + "Envoyer la demande" (submit HTMX).
    - `hx-post="{% url 'workflow:extension-request' recommendation.pk %}"`.
    - `hx-target="#extension-modal-container"` + `hx-swap="innerHTML"`.
  - [x] Subtask 5.2 : CrÃ©er `templates/workflow/partials/extension_review_modal.html` :
    - Vue Audit pour statuer sur la demande PENDING.
    - Affiche : `requested_by` (nom + rÃ´le DM/DG), `requested_date`, `reason`, `due_date` actuelle.
    - **Deux modes** (rendu conditionnel `{% if action == 'approve' %}...{% else %}...`) :
      - **Approve** : utilise `ExtensionApproveForm` (`audit_comment` optionnel). Bouton "Approuver" vert (hx-post vers `extension-approve`).
      - **Reject** : utilise `ExtensionRejectForm` (`audit_comment` obligatoire avec label "Motif du rejet"). Bouton "Rejeter" rouge (hx-post vers `extension-reject`).
  - [x] Subtask 5.3 : Mettre Ã  jour `recommendation_detail.html` :
    - Ajouter au `x-data` initial : `extensionRequestModalOpen: false, extensionReviewModalOpen: false` (cohÃ©rent avec le pattern existant `assignModalOpen`, `approveModalOpen`, etc.).
    - Ajouter les conteneurs HTMX : `#extension-request-modal-container` et `#extension-review-modal-container`.
    - Ajouter le bouton "Demander un report" (visible si `can_request_extension`, dÃ©sactivÃ© si `pending_extension`).
    - Ajouter le bandeau de statut (ambre PENDING / vert APPROVED / rouge REJECTED selon `pending_extension` ou derniÃ¨re entrÃ©e de `extension_history`).
    - Ajouter les boutons "Approuver"/"Rejeter" (visibles si `can_review_extension` AND `pending_extension`), chacun ouvrant la modale review en mode appropriÃ© via `hx-get?action=approve|reject`.

- [x] Task 6 : AuditLog â€” Nouvelles actions (AC1, AC4, AC5)
  - [x] Subtask 6.1 : Ajouter dans `apps/audit/models.py` (ou Ã©quivalent) les nouvelles actions :
    - `EXTENSION_REQUESTED = "EXTENSION_REQUESTED", _("Demande de report soumise")`
    - `EXTENSION_APPROVED = "EXTENSION_APPROVED", _("Demande de report approuvÃ©e")`
    - `EXTENSION_REJECTED = "EXTENSION_REJECTED", _("Demande de report rejetÃ©e")`
  - [x] Subtask 6.2 : CrÃ©er la migration correspondante (`0004_add_extension_audit_actions.py` ou similaire).

- [x] Task 7 : Tests (AC1â€“AC8)
  - [x] Subtask 7.1 : `test_dm_can_request_extension()` â€” POST valide par le DM assignÃ© â†’ 200, `ExtensionRequest` crÃ©Ã©, AuditLog crÃ©Ã©.
  - [x] Subtask 7.2 : `test_duplicate_pending_request_returns_422()` â€” 2Ã¨me demande PENDING â†’ 422.
  - [x] Subtask 7.3 : `test_extension_date_must_be_future_returns_422()` â€” date â‰¤ due_date â†’ 422.
  - [x] Subtask 7.4 : `test_non_authorized_role_cannot_request_extension()` â€” ETP/AUDIT/EXT/ADMIN_IT POST â†’ 403.
  - [x] Subtask 7.5 : `test_audit_can_approve_extension()` â€” approve â†’ `due_date` mise Ã  jour, `status=APPROVED`, `reviewed_by` et `reviewed_at` renseignÃ©s.
  - [x] Subtask 7.6 : `test_audit_can_reject_extension()` â€” reject avec motif â†’ `due_date` inchangÃ©, `status=REJECTED`, `audit_comment` enregistrÃ©.
  - [x] Subtask 7.7 : `test_reject_without_comment_returns_422()` â€” motif vide ou whitespace seul â†’ 422.
  - [x] Subtask 7.8 : `test_dm_cannot_approve_or_reject()` â€” DM/ETP/DG POST vers approve/reject â†’ 403.
  - [x] Subtask 7.9 : `test_original_due_date_immutable_after_approval()` â€” Snapshot `original_due_date` avant `approve_extension()`, vÃ©rifier aprÃ¨s que `Recommendation.all_objects.get(pk=rec.pk).original_due_date` est strictement identique. **Invariant COBAC (AC8).**
  - [x] Subtask 7.10 : `test_dg_assigned_as_dm_can_request_extension()` â€” Un DG personnellement assignÃ© (`recommendation.assigned_dm == dg_user`) peut POST avec succÃ¨s (200, ExtensionRequest crÃ©Ã©e). **Couvre FR34.**
  - [x] Subtask 7.11 : `test_dg_not_assigned_cannot_request_extension()` â€” Un DG dont l'UUID n'est PAS dans `recommendation.assigned_dm` â†’ 403.
  - [x] Subtask 7.12 : `test_audit_without_is_audit_admin_can_approve()` â€” Un AUDIT avec `is_audit_admin=False` peut approuver/rejeter (200). **Couvre AC7.**
  - [x] Subtask 7.13 : `test_audit_can_approve_without_comment()` â€” approve sans `audit_comment` â†’ 200, `extension_request.audit_comment == ""`. **Couvre AC4 (optionnel).**

## Dev Notes

### Profil DG dans Sentinel (contexte RBAC)

Le DG est traitÃ© exactement comme un DM pour les recommandations qui lui sont **personnellement assignÃ©es** (`assigned_dm`). DiffÃ©rences importantes vs DM :

- **Vue globale** : le DG dispose d'indicateurs agrÃ©gÃ©s sur toutes les directions (Epic 6 â€” hors scope 3.6) ; ici on ne traite que son espace de travail personnel.
- **Pas de dÃ©lÃ©gation Ã  ETP** : le DG est le seul porteur de ses recommandations assignÃ©es â€” il ne peut pas dÃ©lÃ©guer leur traitement Ã  un ETP (contrairement au DM). Le service `delegate_to_etp()` (Story 3.2) doit inclure un guard `if recommendation.assigned_dm.role == User.Role.DG: raise PermissionDenied`. Ce guard est Ã  vÃ©rifier dans l'implÃ©mentation Story 3.2 existante â€” hors scope de Story 3.6.
- **Extension request** : pour Story 3.6, le DG suit le mÃªme chemin que le DM â€” condition unique : `assigned_dm == request.user`.

### Architecture & Patterns

- **Pas de FSM** : `ExtensionRequest` n'est pas pilotÃ© par `django-fsm`. C'est un modÃ¨le satellite avec un champ `status` ordinaire (CharField+choices). La recommandation elle-mÃªme ne change pas de statut FSM lors d'une demande de report. **Note** : le PRD v2 Â§225 mentionne Â« 5 Ã©tats + statut transitoire d'extension Â» â€” cette interprÃ©tation reste correcte car le Â« statut transitoire Â» est portÃ© par l'instance `ExtensionRequest`, pas par le FSM de Recommendation.
- **Pattern service layer** : Selector â†’ Service â†’ View strictement (HackSoft convention).
- **RÃ©utiliser `WorkflowAccessMixin`** pour les vues du demandeur (DM/DG) et `AuditRequiredMixin` pour les vues Audit (statuer sur la demande).
- **`select_for_update()`** dans `approve_extension` pour Ã©viter les race conditions lors de la mise Ã  jour de `due_date`.
- **Soft safety** : Si un 2Ã¨me demandeur soumet une demande avant que l'Audit rÃ©ponde, le service lÃ¨ve une `ValueError` (guard doublon en AC2).

### Notifications (HORS scope Story 3.6)

L'envoi de notification au demandeur (DM/DG) aprÃ¨s dÃ©cision Audit (approbation ou rejet) est **explicitement dÃ©lÃ©guÃ© Ã  Epic 4** (Notifications & Alertes). Story 3.6 ne crÃ©e :

- **aucun signal Django** (`post_save` sur `ExtensionRequest`),
- **aucune tÃ¢che django-q2 dÃ©diÃ©e** (`notify_extension_decision`),
- **aucun envoi email/in-app**.

Ã€ la place, Story 3.6 garantit que les **AuditLog entries** (`EXTENSION_REQUESTED`, `EXTENSION_APPROVED`, `EXTENSION_REJECTED`) sont crÃ©Ã©es avec toutes les mÃ©tadonnÃ©es nÃ©cessaires (`user`, `content_type`, `object_id`, `changes`, `ip_address`). L'Epic 4 implÃ©mentera ensuite :

1. Un consommateur (signal ou cron) sur ces actions AuditLog,
2. La rÃ©solution du destinataire (`extension_request.requested_by`),
3. L'envoi du message contextuel (email + in-app) avec le verdict Audit et `audit_comment`.

### ModÃ¨le de donnÃ©es

- `original_due_date` (dÃ©jÃ  en DB) est **immuable** â€” jamais mis Ã  jour par ce service.
- `due_date` est mis Ã  jour **uniquement** dans `approve_extension()`.
- `ExtensionRequest` a une relation `ManyToOne` vers `Recommendation` â€” plusieurs demandes peuvent exister par reco (une PENDING Ã  la fois, mais historique APPROVED/REJECTED conservÃ©).

### SÃ©lecteurs Ã  ajouter dans `selectors.py` (Subtask 4.0)

```python
def get_pending_extension_for_recommendation(*, recommendation) -> ExtensionRequest | None:
    """Retourne la demande de report PENDING pour une recommandation, ou None."""
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation, status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by")
        .first()
    )


def get_extension_history_for_recommendation(*, recommendation) -> QuerySet[ExtensionRequest]:
    """Retourne l'historique APPROVED/REJECTED (exclut PENDING) triÃ© du plus rÃ©cent au plus ancien."""
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation)
        .exclude(status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by", "reviewed_by")
        .order_by("-reviewed_at")
    )
```

### AuditLog

- RÃ©utiliser le pattern des stories prÃ©cÃ©dentes pour `AuditLog.create()`.
- `changes` pour EXTENSION_APPROVED : `{"due_date": [str(old_due_date), str(new_due_date)]}`.
- `changes` pour EXTENSION_REQUESTED : `{"requested_date": str(requested_date), "reason": reason[:100]}`.

### Ordre de livraison suggÃ©rÃ©

1. Migration (`ExtensionRequest`) + mise Ã  jour `AuditLog` actions
2. SÃ©lecteurs (`get_pending_extension_for_recommendation`, `get_extension_history_for_recommendation`)
3. Services (`request_extension`, `approve_extension`, `reject_extension`)
4. Formulaires (`ExtensionRequestForm`, `ExtensionApproveForm`, `ExtensionRejectForm`)
5. Vues + URLs
6. Templates (modales + mise Ã  jour `recommendation_detail.html`)
7. Tests

### Project Structure Notes

- Nouveau modÃ¨le : `apps/workflow/models.py`
- Nouvelles migrations : `apps/workflow/migrations/0009_add_extension_request.py`
- Nouveaux services : `apps/workflow/services.py` (3 nouvelles fonctions)
- Nouvelles vues : `apps/workflow/views.py` (3 nouvelles classes)
- Nouveaux templates :
  - `templates/workflow/partials/extension_request_modal.html` (nouveau)
  - `templates/workflow/partials/extension_review_modal.html` (nouveau)
  - `templates/workflow/recommendation_detail.html` (mise Ã  jour)
- Tests : `apps/workflow/tests/test_views.py` (classe `ExtensionRequestViewTest`)

### References

- [Source: epics.md#Story 3.6] â€” FR13, FR14
- [Source: epics.md ligne 50] â€” FR34 (DG peut demander un report)
- [Source: prd-v2.md#FR13-FR14-FR34] â€” Demande de report et workflow d'approbation
- [PRD User Journey 3] â€” ScÃ©nario "Claire demande un report Ã  J-10"
- [PRD Â§225-226] â€” "Workflow FSM strict (5 Ã©tats + statut transitoire d'extension)" â€” interprÃ©tÃ© comme objet satellite, pas comme Ã©tat FSM additionnel.
- [Pattern: EvidenceRejectView in views.py] â€” Architecture HTMX modale Ã  reproduire
- [Pattern: validate_evidence_for_audit in services.py] â€” Pattern guard + transaction.atomic()
- [[security_issues]] â€” Vuln 2 Ã  corriger en parallÃ¨le (selectors RBAC)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
- [NEW] code/apps/workflow/migrations/0009_add_extension_request.py
- [NEW] code/templates/workflow/partials/extension_request_modal.html
- [NEW] code/templates/workflow/partials/extension_review_modal.html
- [MODIFY] code/apps/audit/migrations/0004_add_extension_audit_actions.py
- [MODIFY] code/apps/audit/models.py
- [MODIFY] code/apps/workflow/models.py
- [MODIFY] code/apps/workflow/forms.py
- [MODIFY] code/apps/workflow/services.py
- [MODIFY] code/apps/workflow/selectors.py
- [MODIFY] code/apps/workflow/views.py
- [MODIFY] code/apps/workflow/urls.py
- [MODIFY] code/apps/workflow/tests/test_views.py
- [MODIFY] code/templates/workflow/recommendation_detail.html
