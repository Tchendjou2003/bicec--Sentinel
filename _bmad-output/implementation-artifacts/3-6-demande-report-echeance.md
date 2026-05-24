# Story 3.6: Demande de Report d'Échéance

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Directeur Métier (ou Direction Générale personnellement assigné(e))**,
I want **demander un allongement du délai de résolution en fournissant une justification et une nouvelle date cible**,
so that **l'Audit Interne puisse évaluer, approuver ou rejeter formellement ma demande — sans passer par email ou téléphone — et que chaque décision soit tracée dans l'audit trail.**

## Status des FR couverts

| FR | Description | Couverture |
|----|-------------|------------|
| **FR13** | Le DM peut demander un report d'échéance justifié | ✅ Story 3.6 |
| **FR14** | L'Audit approuve ou rejette les demandes de report | ✅ Story 3.6 |
| **FR34** | La DG peut demander un report d'échéance | ✅ Story 3.6 |

## Acceptance Criteria

1. **AC1 — Demande de report par un demandeur autorisé (DM ou DG)**
   - **Given** une recommandation en état `ASSIGNED`, `IN_PROGRESS`, ou `PENDING_DM_REVIEW` (non clôturée),
   - **When** un demandeur autorisé (DM assigné OU DG personnellement assigné(e) comme directeur de mission de la recommandation) clique sur "Demander un report" et soumet le formulaire avec une nouvelle date et un motif,
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
   - **Then** la demande est autorisée si : `recommendation.assigned_dm == request.user` — couvre le DM assigné ET le DG personnellement assigné comme directeur de mission (le champ `assigned_dm` peut contenir un utilisateur de rôle DM ou DG).
   - **And** toute tentative POST par un utilisateur autre que `recommendation.assigned_dm` (ETP, AUDIT, EXT, ADMIN_IT, DG non personnellement assigné) renvoie HTTP 403.
   - **And** le bouton "Demander un report" est visible uniquement pour `request.user == recommendation.assigned_dm`.

4. **AC4 — Approbation de la demande par l'Audit**
   - **Given** une `ExtensionRequest` en état `PENDING`,
   - **When** un Auditeur clique sur "Approuver" dans l'interface de détail de la recommandation,
   - **Then** `ExtensionRequest.status` passe à `APPROVED`.
   - **And** `Recommendation.due_date` est mis à jour avec `ExtensionRequest.requested_date`.
   - **And** `Recommendation.original_due_date` est **inchangé** (préservation pour les rapports de vieillissement COBAC — invariant formalisé en AC8 et testé par Subtask 7.9).
   - **And** le champ `audit_comment` est **optionnel** lors de l'approbation (différence-clé vs AC5 — rejet).
   - **And** s'il est fourni, il est enregistré dans `ExtensionRequest.audit_comment`.
   - **And** l'action est tracée dans l'Audit Log (`action=EXTENSION_APPROVED`, `changes={"due_date": [old, new]}`).
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

7. **AC7 — Permissions Audit : tous les auditeurs peuvent statuer**
   - **Given** une `ExtensionRequest` en état `PENDING`,
   - **When** un utilisateur avec `role == User.Role.AUDIT` consulte la recommandation,
   - **Then** il voit les boutons "Approuver" et "Rejeter" et peut les actionner avec succès (200).
   - **And** le flag `is_audit_admin` **n'est PAS requis** pour cette action (contrairement à la gestion des comptes — ADR-10).
   - **And** une tentative POST par un rôle non-AUDIT (DM, ETP, DG, EXT, ADMIN_IT) renvoie HTTP 403.

8. **AC8 — Invariant `original_due_date` (COBAC)**
   - **Given** une approbation `approve_extension()` qui met à jour `due_date`,
   - **Then** `Recommendation.original_due_date` reste **strictement identique** avant et après l'opération.
   - **And** cet invariant est garanti par l'absence de modification explicite dans le service (vérifié par `Subtask 7.9`).

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
  - [ ] Subtask 2.2 : Créer **deux** formulaires distincts dans `apps/workflow/forms.py` (clarification AC4 vs AC5) :
    - `ExtensionApproveForm(forms.Form)` :
      - `audit_comment` : `Textarea`, **optionnel** (`required=False`, `max_length=2000`).
      - Utilisé par `ExtensionApproveView`.
    - `ExtensionRejectForm(forms.Form)` :
      - `audit_comment` : `Textarea`, **obligatoire** (`required=True`, `max_length=2000`).
      - `error_messages={"required": _("Le motif de rejet est obligatoire.")}`
      - Utilisé par `ExtensionRejectView`.
    - Justification : éviter le pattern "form partagé avec règle conditionnelle" qui obscurcit l'intention métier.

- [ ] Task 3 : Backend — Services (AC1, AC2, AC4, AC5)
  - [ ] Subtask 3.1 : Créer `request_extension(*, recommendation, requested_date, reason, performed_by, ip_address=None)` dans `services.py` :
    1. Guard RBAC (FR13 + FR34) :
       ```python
       # assigned_dm peut être un DM ou un DG — l'assignation personnelle est le seul critère
       if performed_by != recommendation.assigned_dm:
           raise PermissionDenied
       ```
    2. Guard état : `recommendation.status` in (`CLOSED_RESOLVED`, `DRAFT`) → `ValueError`.
    3. Guard doublon : `ExtensionRequest.objects.filter(recommendation=rec, status=PENDING).exists()` → `ValueError("Une demande de report est déjà en attente.")`.
    4. Guard date : `requested_date <= recommendation.due_date` → `ValueError("La nouvelle date doit être postérieure à l'échéance actuelle.")`.
    5. Créer `ExtensionRequest(recommendation=rec, requested_by=performed_by, requested_date=requested_date, reason=reason, status=PENDING)`.
    6. Créer `AuditLog(action=EXTENSION_REQUESTED, ...)`.
    7. Tout dans `transaction.atomic()`.
  - [ ] Subtask 3.2 : Créer `approve_extension(*, extension_request, performed_by, audit_comment="", ip_address=None)` dans `services.py` :
    1. Guard RBAC : `performed_by.role != User.Role.AUDIT` → `PermissionDenied` (AC7 : `is_audit_admin` n'est PAS requis).
    2. Guard état : `extension_request.status != PENDING` → `ValueError`.
    3. Dans `transaction.atomic()` avec `select_for_update()` sur la recommandation :
       - `old_due_date = recommendation.due_date` (pour AuditLog)
       - `extension_request.status = APPROVED`
       - `extension_request.reviewed_by = performed_by`
       - `extension_request.reviewed_at = timezone.now()`
       - `extension_request.audit_comment = audit_comment` (peut être vide — AC4)
       - `extension_request.save()`
       - `recommendation.due_date = extension_request.requested_date`
       - `recommendation.save(update_fields=["due_date", "updated_at"])`
       - **NE PAS toucher** `original_due_date` (invariant AC8 / Subtask 7.9).
    4. Créer `AuditLog(action=EXTENSION_APPROVED, changes={"due_date": [str(old_due_date), str(new_due_date)]})`.
  - [ ] Subtask 3.3 : Créer `reject_extension(*, extension_request, performed_by, audit_comment, ip_address=None)` dans `services.py` (note : `audit_comment` **sans défaut** = obligatoire à l'appel) :
    1. Guard RBAC : `performed_by.role != User.Role.AUDIT` → `PermissionDenied` (AC7).
    2. Guard état : `extension_request.status != PENDING` → `ValueError`.
    3. Guard motif : `not audit_comment.strip()` → `ValueError("Le motif de rejet est obligatoire.")`.
    4. Dans `transaction.atomic()` :
       - `extension_request.status = REJECTED`
       - Mettre à jour `reviewed_by`, `reviewed_at`, `audit_comment`.
       - `extension_request.save()`
       - **NE PAS modifier** `recommendation.due_date` (l'échéance initiale est maintenue).
    5. Créer `AuditLog(action=EXTENSION_REJECTED, changes={"audit_comment": audit_comment[:100]})`.

- [ ] Task 4 : Backend — Sélecteur, Vues & URLs (AC3, AC4, AC5, AC7)
  - [ ] Subtask 4.0 : Ajouter `get_pending_extension_for_recommendation(*, recommendation) -> ExtensionRequest | None` dans `apps/workflow/selectors.py` :
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
  - [ ] Subtask 4.5 : Mettre à jour `RecommendationDetailView.get_context_data()` (importer les 2 sélecteurs de la Subtask 4.0) :
    - `pending_extension` : appel à `selectors.get_pending_extension_for_recommendation(recommendation=self.object)` (None ou instance).
    - `extension_history` : appel à `selectors.get_extension_history_for_recommendation(recommendation=self.object)`.
    - `can_request_extension` : booléen — `user == recommendation.assigned_dm` (couvre DM ET DG personnellement assignés), **ET** `pending_extension is None`, **ET** `status not in (CLOSED_RESOLVED, DRAFT)`.
    - `can_review_extension` : booléen — `user.role == User.Role.AUDIT` (AC7).

- [ ] Task 5 : Frontend — Templates (AC6)
  - [ ] Subtask 5.1 : Créer `templates/workflow/partials/extension_request_modal.html` :
    - En-tête ambre + icône calendrier.
    - Affichage de la `due_date` actuelle.
    - Champs : `requested_date` (date picker, min=due_date+1) + `reason` (textarea).
    - Boutons : "Annuler" (ferme modale Alpine) + "Envoyer la demande" (submit HTMX).
    - `hx-post="{% url 'workflow:extension-request' recommendation.pk %}"`.
    - `hx-target="#extension-modal-container"` + `hx-swap="innerHTML"`.
  - [ ] Subtask 5.2 : Créer `templates/workflow/partials/extension_review_modal.html` :
    - Vue Audit pour statuer sur la demande PENDING.
    - Affiche : `requested_by` (nom + rôle DM/DG), `requested_date`, `reason`, `due_date` actuelle.
    - **Deux modes** (rendu conditionnel `{% if action == 'approve' %}...{% else %}...`) :
      - **Approve** : utilise `ExtensionApproveForm` (`audit_comment` optionnel). Bouton "Approuver" vert (hx-post vers `extension-approve`).
      - **Reject** : utilise `ExtensionRejectForm` (`audit_comment` obligatoire avec label "Motif du rejet"). Bouton "Rejeter" rouge (hx-post vers `extension-reject`).
  - [ ] Subtask 5.3 : Mettre à jour `recommendation_detail.html` :
    - Ajouter au `x-data` initial : `extensionRequestModalOpen: false, extensionReviewModalOpen: false` (cohérent avec le pattern existant `assignModalOpen`, `approveModalOpen`, etc.).
    - Ajouter les conteneurs HTMX : `#extension-request-modal-container` et `#extension-review-modal-container`.
    - Ajouter le bouton "Demander un report" (visible si `can_request_extension`, désactivé si `pending_extension`).
    - Ajouter le bandeau de statut (ambre PENDING / vert APPROVED / rouge REJECTED selon `pending_extension` ou dernière entrée de `extension_history`).
    - Ajouter les boutons "Approuver"/"Rejeter" (visibles si `can_review_extension` AND `pending_extension`), chacun ouvrant la modale review en mode approprié via `hx-get?action=approve|reject`.

- [ ] Task 6 : AuditLog — Nouvelles actions (AC1, AC4, AC5)
  - [ ] Subtask 6.1 : Ajouter dans `apps/audit/models.py` (ou équivalent) les nouvelles actions :
    - `EXTENSION_REQUESTED = "EXTENSION_REQUESTED", _("Demande de report soumise")`
    - `EXTENSION_APPROVED = "EXTENSION_APPROVED", _("Demande de report approuvée")`
    - `EXTENSION_REJECTED = "EXTENSION_REJECTED", _("Demande de report rejetée")`
  - [ ] Subtask 6.2 : Créer la migration correspondante (`0004_add_extension_audit_actions.py` ou similaire).

- [ ] Task 7 : Tests (AC1–AC8)
  - [ ] Subtask 7.1 : `test_dm_can_request_extension()` — POST valide par le DM assigné → 200, `ExtensionRequest` créé, AuditLog créé.
  - [ ] Subtask 7.2 : `test_duplicate_pending_request_returns_422()` — 2ème demande PENDING → 422.
  - [ ] Subtask 7.3 : `test_extension_date_must_be_future_returns_422()` — date ≤ due_date → 422.
  - [ ] Subtask 7.4 : `test_non_authorized_role_cannot_request_extension()` — ETP/AUDIT/EXT/ADMIN_IT POST → 403.
  - [ ] Subtask 7.5 : `test_audit_can_approve_extension()` — approve → `due_date` mise à jour, `status=APPROVED`, `reviewed_by` et `reviewed_at` renseignés.
  - [ ] Subtask 7.6 : `test_audit_can_reject_extension()` — reject avec motif → `due_date` inchangé, `status=REJECTED`, `audit_comment` enregistré.
  - [ ] Subtask 7.7 : `test_reject_without_comment_returns_422()` — motif vide ou whitespace seul → 422.
  - [ ] Subtask 7.8 : `test_dm_cannot_approve_or_reject()` — DM/ETP/DG POST vers approve/reject → 403.
  - [ ] Subtask 7.9 : `test_original_due_date_immutable_after_approval()` — Snapshot `original_due_date` avant `approve_extension()`, vérifier après que `Recommendation.all_objects.get(pk=rec.pk).original_due_date` est strictement identique. **Invariant COBAC (AC8).**
  - [ ] Subtask 7.10 : `test_dg_assigned_as_dm_can_request_extension()` — Un DG personnellement assigné (`recommendation.assigned_dm == dg_user`) peut POST avec succès (200, ExtensionRequest créée). **Couvre FR34.**
  - [ ] Subtask 7.11 : `test_dg_not_assigned_cannot_request_extension()` — Un DG dont l'UUID n'est PAS dans `recommendation.assigned_dm` → 403.
  - [ ] Subtask 7.12 : `test_audit_without_is_audit_admin_can_approve()` — Un AUDIT avec `is_audit_admin=False` peut approuver/rejeter (200). **Couvre AC7.**
  - [ ] Subtask 7.13 : `test_audit_can_approve_without_comment()` — approve sans `audit_comment` → 200, `extension_request.audit_comment == ""`. **Couvre AC4 (optionnel).**

## Dev Notes

### Profil DG dans Sentinel (contexte RBAC)

Le DG est traité exactement comme un DM pour les recommandations qui lui sont **personnellement assignées** (`assigned_dm`). Différences importantes vs DM :

- **Vue globale** : le DG dispose d'indicateurs agrégés sur toutes les directions (Epic 6 — hors scope 3.6) ; ici on ne traite que son espace de travail personnel.
- **Pas de délégation à ETP** : le DG est le seul porteur de ses recommandations assignées — il ne peut pas déléguer leur traitement à un ETP (contrairement au DM). Le service `delegate_to_etp()` (Story 3.2) doit inclure un guard `if recommendation.assigned_dm.role == User.Role.DG: raise PermissionDenied`. Ce guard est à vérifier dans l'implémentation Story 3.2 existante — hors scope de Story 3.6.
- **Extension request** : pour Story 3.6, le DG suit le même chemin que le DM — condition unique : `assigned_dm == request.user`.

### Architecture & Patterns

- **Pas de FSM** : `ExtensionRequest` n'est pas piloté par `django-fsm`. C'est un modèle satellite avec un champ `status` ordinaire (CharField+choices). La recommandation elle-même ne change pas de statut FSM lors d'une demande de report. **Note** : le PRD v2 §225 mentionne « 5 états + statut transitoire d'extension » — cette interprétation reste correcte car le « statut transitoire » est porté par l'instance `ExtensionRequest`, pas par le FSM de Recommendation.
- **Pattern service layer** : Selector → Service → View strictement (HackSoft convention).
- **Réutiliser `WorkflowAccessMixin`** pour les vues du demandeur (DM/DG) et `AuditRequiredMixin` pour les vues Audit (statuer sur la demande).
- **`select_for_update()`** dans `approve_extension` pour éviter les race conditions lors de la mise à jour de `due_date`.
- **Soft safety** : Si un 2ème demandeur soumet une demande avant que l'Audit réponde, le service lève une `ValueError` (guard doublon en AC2).

### Notifications (HORS scope Story 3.6)

L'envoi de notification au demandeur (DM/DG) après décision Audit (approbation ou rejet) est **explicitement délégué à Epic 4** (Notifications & Alertes). Story 3.6 ne crée :

- **aucun signal Django** (`post_save` sur `ExtensionRequest`),
- **aucune tâche django-q2 dédiée** (`notify_extension_decision`),
- **aucun envoi email/in-app**.

À la place, Story 3.6 garantit que les **AuditLog entries** (`EXTENSION_REQUESTED`, `EXTENSION_APPROVED`, `EXTENSION_REJECTED`) sont créées avec toutes les métadonnées nécessaires (`user`, `content_type`, `object_id`, `changes`, `ip_address`). L'Epic 4 implémentera ensuite :

1. Un consommateur (signal ou cron) sur ces actions AuditLog,
2. La résolution du destinataire (`extension_request.requested_by`),
3. L'envoi du message contextuel (email + in-app) avec le verdict Audit et `audit_comment`.

### Modèle de données

- `original_due_date` (déjà en DB) est **immuable** — jamais mis à jour par ce service.
- `due_date` est mis à jour **uniquement** dans `approve_extension()`.
- `ExtensionRequest` a une relation `ManyToOne` vers `Recommendation` — plusieurs demandes peuvent exister par reco (une PENDING à la fois, mais historique APPROVED/REJECTED conservé).

### Sélecteurs à ajouter dans `selectors.py` (Subtask 4.0)

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
    """Retourne l'historique APPROVED/REJECTED (exclut PENDING) trié du plus récent au plus ancien."""
    return (
        ExtensionRequest.objects
        .filter(recommendation=recommendation)
        .exclude(status=ExtensionRequest.Status.PENDING)
        .select_related("requested_by", "reviewed_by")
        .order_by("-reviewed_at")
    )
```

### AuditLog

- Réutiliser le pattern des stories précédentes pour `AuditLog.create()`.
- `changes` pour EXTENSION_APPROVED : `{"due_date": [str(old_due_date), str(new_due_date)]}`.
- `changes` pour EXTENSION_REQUESTED : `{"requested_date": str(requested_date), "reason": reason[:100]}`.

### Ordre de livraison suggéré

1. Migration (`ExtensionRequest`) + mise à jour `AuditLog` actions
2. Sélecteurs (`get_pending_extension_for_recommendation`, `get_extension_history_for_recommendation`)
3. Services (`request_extension`, `approve_extension`, `reject_extension`)
4. Formulaires (`ExtensionRequestForm`, `ExtensionApproveForm`, `ExtensionRejectForm`)
5. Vues + URLs
6. Templates (modales + mise à jour `recommendation_detail.html`)
7. Tests

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
- [Source: epics.md ligne 50] — FR34 (DG peut demander un report)
- [Source: prd-v2.md#FR13-FR14-FR34] — Demande de report et workflow d'approbation
- [PRD User Journey 3] — Scénario "Claire demande un report à J-10"
- [PRD §225-226] — "Workflow FSM strict (5 états + statut transitoire d'extension)" — interprété comme objet satellite, pas comme état FSM additionnel.
- [Pattern: EvidenceRejectView in views.py] — Architecture HTMX modale à reproduire
- [Pattern: validate_evidence_for_audit in services.py] — Pattern guard + transaction.atomic()
- [[security_issues]] — Vuln 2 à corriger en parallèle (selectors RBAC)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
