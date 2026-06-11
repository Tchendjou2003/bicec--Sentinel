# Story 4.0: Socle Notifications In-App (Modèle + Feed)

Status: done

<!-- Prérequis de Stories 4.1 et 4.2. Lancer dev-story avant d'ouvrir 4.1. -->

## Story

As a **Utilisateur (DM, ETP, DG, Audit)**,
I want **voir en temps réel dans la topbar les événements qui me concernent — via un badge de compteur et une liste déroulante — et pouvoir les marquer comme lus**,
so that **je suis informé sans quitter l'application, et que les stories 4.1/4.2 puissent émettre des notifications idempotentes sur ce socle (channel-agnostic, futur e-mail post-MVP)**.

## Acceptance Criteria

1. **AC1 — Badge in-app (compteur de non-lus)**
   - **Given** un utilisateur connecté ayant des notifications non-lues
   - **When** il consulte n'importe quelle page de l'application
   - **Then** la **cloche** de la topbar affiche un **badge rouge** avec le nombre de notifications non-lues
   - **And** si toutes sont lues, le badge disparaît (pas de « 0 »)

2. **AC2 — Dropdown de notifications (HTMX lazy)**
   - **Given** l'utilisateur clique sur la cloche
   - **When** le dropdown s'ouvre (premier clic)
   - **Then** les **10 dernières notifications** de l'utilisateur sont chargées via HTMX (lazy — pas de requête supplémentaire au chargement de page)
   - **And** chaque entrée affiche : icône du type, titre court, date relative, et statut visuel (non-lu = fond distinct)
   - **And** les notifications **urgentes** (`is_urgent=True` — ruptures, escalades) sont visuellement distinctes (couleur + icône prioritaire)

3. **AC3 — Marquer comme lu**
   - **Given** une notification non-lue dans le dropdown
   - **When** l'utilisateur clique dessus
   - **Then** elle est marquée comme lue (POST HTMX) et redirige vers son `url`
   - **And** le badge se met à jour (décrémenté via `HX-Trigger`)
   - **And** un « Tout marquer comme lu » marque toutes les notifs de l'utilisateur en une action

4. **AC4 — Modèle `Notification` + idempotence**
   - Le modèle trace : `recipient` (FK User), `notification_type` (enum), `recommendation` (FK nullable), `title`, `body`, `url`, `is_urgent`, `is_read`, `idempotency_key` (unique), `created_at`
   - **Given** un appel `emit_notification(..., idempotency_key="overdue_j30:rec-uuid")`
   - **When** la même clé est émise une 2ᵉ fois
   - **Then** **aucun doublon** n'est créé (`get_or_create` sur `idempotency_key`) — retourne `None` si déjà existante

5. **AC5 — Channel-agnostic (préparation e-mail post-MVP)**
   - Le modèle ne contient **aucune référence** à un canal e-mail
   - Les Notification sont **queryables** par canal futur sans migration (le canal est un concept externe au modèle)

6. **AC6 — RBAC : uniquement ses propres notifications**
   - **Given** tout endpoint de la `NotificationDropdownView` ou mark-read
   - **Then** l'utilisateur ne peut voir et agir que sur **ses propres** notifications (filtré `recipient=request.user`)

## Tasks / Subtasks

- [ ] **Task 1 — Modèle `Notification`** (AC4, AC5)
  - [ ] Subtask 1.1 : Compléter `apps/notifications/models.py` (stub vide aujourd'hui)
    ```
    class Notification(models.Model):
        class Type(models.TextChoices):
            # ── Événements workflow ────────────────────────────
            ASSIGNED            = "ASSIGNED",             _("Reco assignée")
            DELEGATED           = "DELEGATED",            _("Délégation ETP")
            EVIDENCE_REJECTED   = "EVIDENCE_REJECTED",    _("Preuves rejetées")
            EVIDENCE_VALIDATED  = "EVIDENCE_VALIDATED",   _("Preuves validées DM→Audit")
            CLOSED              = "CLOSED",               _("Reco clôturée")
            EXTENSION_REQUESTED = "EXTENSION_REQUESTED",  _("Demande de report soumise")
            EXTENSION_APPROVED  = "EXTENSION_APPROVED",   _("Report approuvé")
            EXTENSION_REJECTED  = "EXTENSION_REJECTED",   _("Report rejeté")
            # ── Ruptures / Urgences (is_urgent=True) ───────────
            OVERDUE             = "OVERDUE",              _("Passage en retard")
            OVERDUE_J30         = "OVERDUE_J30",          _("Retard ≥ 30 jours")
            OVERDUE_J60_ESCALATION = "OVERDUE_J60_ESCALATION", _("Escalade retard 60 j")
            # ── Anticipations ──────────────────────────────────
            DUE_SOON_J7         = "DUE_SOON_J7",          _("Échéance dans 7 jours")
            DUE_SOON_J3         = "DUE_SOON_J3",          _("Échéance dans 3 jours")

        id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        recipient         = models.ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT,
                                              related_name="notifications")
        notification_type = models.CharField(max_length=30, choices=Type.choices)
        recommendation    = models.ForeignKey("workflow.Recommendation", on_delete=SET_NULL,
                                              null=True, blank=True, related_name="notifications")
        title             = models.CharField(max_length=200)
        body              = models.TextField(blank=True, default="")
        url               = models.CharField(max_length=500, blank=True, default="")
        is_urgent         = models.BooleanField(default=False, help_text="Rupture/escalade")
        is_read           = models.BooleanField(default=False, db_index=True)
        idempotency_key   = models.CharField(max_length=255, unique=True)
        created_at        = models.DateTimeField(auto_now_add=True, db_index=True)

        class Meta:
            ordering = ["-created_at"]
            indexes = [
                models.Index(fields=["recipient", "is_read"], name="idx_notif_recipient_read"),
            ]
    ```
  - [ ] Subtask 1.2 : Créer `apps/notifications/migrations/0001_initial.py` via `makemigrations notifications`

- [ ] **Task 2 — Service `emit_notification()`** (AC4, AC5)
  - [ ] Créer `apps/notifications/services.py` :
    ```python
    def emit_notification(
        *,
        recipient,
        notification_type: Notification.Type,
        title: str,
        idempotency_key: str,
        recommendation=None,
        body: str = "",
        url: str = "",
        is_urgent: bool = False,
    ) -> "Notification | None":
        """Émet une notification idempotente. Retourne None si déjà existante."""
        notif, created = Notification.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "recipient": recipient,
                "notification_type": notification_type,
                "recommendation": recommendation,
                "title": title,
                "body": body,
                "url": url,
                "is_urgent": is_urgent,
            },
        )
        return notif if created else None
    ```
  - [ ] Format de la clé d'idempotence (convention) : `"{type}:{recommendation_pk}"` pour les events workflow, `"{type}:{recommendation_pk}:{extra}"` pour les ruptures (ex. `"OVERDUE_J30:{rec_pk}"`, `"ASSIGNED:{rec_pk}:{dm_pk}"`).

- [ ] **Task 3 — Context processor `unread_count`** (AC1)
  - [ ] Créer `apps/notifications/context_processors.py` (calqué sur `apps/users/context_processors.sidebar_context`) :
    ```python
    def notifications_context(request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return {"unread_notifications_count": 0}
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {"unread_notifications_count": count}
    ```
  - [ ] Enregistrer dans `TEMPLATES → context_processors` de [base.py](code/config/settings/base.py#L105) : `"apps.notifications.context_processors.notifications_context"`.

- [ ] **Task 4 — Vues + URLs** (AC2, AC3, AC6)
  - [ ] Créer `apps/notifications/views.py` :
    - `NotificationDropdownView(LoginRequiredMixin, View)` — `GET` → rendu HTMX du partial `notification_dropdown.html` (10 dernières de `request.user`, `select_related("recommendation")`).
    - `NotificationMarkReadView(LoginRequiredMixin, View)` — `POST {pk}` → met `is_read=True` si `notification.recipient == request.user` (AC6) ; renvoie `HX-Trigger: {"badge-update": true}` pour rafraîchir le badge.
    - `NotificationMarkAllReadView(LoginRequiredMixin, View)` — `POST` → `Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)` ; `HX-Trigger: {"badge-update": true}`.
  - [ ] Créer `apps/notifications/urls.py` (app_name="notifications") :
    - `path("dropdown/", NotificationDropdownView.as_view(), name="dropdown")`
    - `path("<uuid:pk>/mark-read/", NotificationMarkReadView.as_view(), name="mark-read")`
    - `path("mark-all-read/", NotificationMarkAllReadView.as_view(), name="mark-all-read")`
  - [ ] Câbler dans [config/urls.py](code/config/urls.py) : `path("notifications/", include("apps.notifications.urls", namespace="notifications"))`.

- [ ] **Task 5 — Templates** (AC1, AC2, AC3)
  - [ ] Créer `templates/notifications/partials/notification_dropdown.html` :
    - Header : « Notifications » + lien « Tout marquer comme lu » (HTMX `hx-post mark-all-read`)
    - Liste des 10 dernières avec : icône du type, `title`, date relative (filtre `timesince`), fond distinct si `not is_read`, badge rouge si `is_urgent`
    - Chaque item : `hx-post="mark-read"` + `hx-push-url="{{ notif.url }}"` (clic = marque lu + redirige)
    - Empty state si aucune notification
  - [ ] Modifier `templates/partials/topbar.html` (ligne 20-23) :
    - Remplacer le `<button>` statique par un **dropdown Alpine.js** (`x-data="{ open: false }"`)
    - Badge : `{% if unread_notifications_count %}` → `<span>{{ unread_notifications_count }}</span>` (remplace le point rouge statique) + `hx-swap-oob` sur `#notif-badge` pour les mises à jour push
    - Sur `@click="open = !open"` + `hx-get="{% url 'notifications:dropdown' %}"` + `hx-trigger="click once"` (lazy load au 1er clic)
    - Conteneur HTMX : `<div id="notification-dropdown-container" hx-swap="innerHTML">` dans le dropdown Alpine

- [ ] **Task 6 — Tests** (AC1-AC6)
  - [ ] Créer `apps/notifications/tests/test_services.py` :
    - `test_emit_notification_creates_record` — vérifie création + champs
    - `test_emit_notification_idempotent` — 2ᵉ appel même clé → `None`, pas de doublon
    - `test_emit_notification_urgent_flag` — `is_urgent=True` conservé
  - [ ] Créer `apps/notifications/tests/test_views.py` :
    - `test_dropdown_returns_200_for_authenticated` — GET dropdown → 200
    - `test_dropdown_returns_redirect_for_anonymous` — GET dropdown → 302
    - `test_mark_read_marks_own_notification` — POST mark-read → `is_read=True`
    - `test_mark_read_forbidden_for_other_user` — POST sur notif d'un autre user → 403 ou 404
    - `test_mark_all_read` — POST mark-all-read → toutes is_read=True, badge à 0
    - `test_unread_count_in_context` — context processor injecte `unread_notifications_count`

- [ ] **Task 7 — Validation**
  - [ ] `makemigrations --check` (seule `notifications/0001` attendue)
  - [ ] `test apps.notifications` + `test apps.workflow apps.audit` (non-régression)
  - [ ] Manuel : badge cloche affiche le bon compte → clique → dropdown → clic → marque lu → badge décrémente

## Dev Notes

### Architecture technique (vérifiée)

- **`apps.notifications` dans INSTALLED_APPS** ([base.py:64](code/config/settings/base.py#L64)) — déjà enregistré, stub vide (`models.py` vide, aucune migration).
- **Context processor pattern** : calqué sur `apps.users.context_processors.sidebar_context` ([context_processors.py](code/apps/users/context_processors.py)) — requête COUNT légère par page (pas de queryset complet).
- **Topbar** : cloche hard-codée ligne 20-23 de [topbar.html](code/templates/partials/topbar.html) — point précis d'intégration. Alpine.js `x-data` déjà utilisé sur la topbar (dropdown profil ligne 25).
- **HTMX lazy** : `hx-trigger="click once"` → le dropdown n'est chargé qu'au 1er clic, pas au chargement de page (conforme NFR-PERF-02 < 200ms).
- **Badge update** : `HX-Trigger: {"badge-update": true}` → handler JS lit l'event et déclenche un `htmx.trigger("#notif-badge", "refresh")` pour mettre à jour le compteur sans reload complet.
- **Idempotency via `unique=True`** sur `idempotency_key` : la contrainte DB garantit l'idempotence même en cas de race condition.

### Channel-agnostic (post-MVP e-mail)

Le modèle `Notification` est **sans référence e-mail** (AC5). Quand le canal e-mail sera activé (post-MVP, prérequis : infra SMTP COBAC disponible), un service `send_email_for_notification(notification: Notification)` consommera les instances existantes **sans migration** — juste un nouveau service et une configuration `EMAIL_BACKEND`.

### Conventions d'idempotence (partagée avec 4.1/4.2)

| Événement | Clé d'idempotence |
|---|---|
| Reco assignée à DM `x` | `ASSIGNED:{rec_pk}:{dm_pk}` |
| Preuves rejetées | `EVIDENCE_REJECTED:{rec_pk}:{submission_pk}` |
| Clôture | `CLOSED:{rec_pk}` |
| Passage OVERDUE | `OVERDUE:{rec_pk}` |
| Jalon 30j | `OVERDUE_J30:{rec_pk}` |
| Escalade 60j | `OVERDUE_J60_ESCALATION:{rec_pk}` |
| J-7 | `DUE_SOON_J7:{rec_pk}` |
| J-3 | `DUE_SOON_J3:{rec_pk}` |

> ⚠ La clé `OVERDUE:{rec_pk}` est réinitialisée si la reco repasse de `OVERDUE=False` à `True` (ex. report approuvé puis délai dépassé à nouveau). À implémenter dans 4.1 : supprimer l'ancienne `Notification` OVERDUE quand la 3.9 remet `is_overdue=False`, afin que le prochain passage soit bien notifié.

### Couverture NFR

- **NFR-PERF-02** (UI < 200ms) : dropdown lazy (HTMX `once`) + COUNT léger en context processor.
- **NFR-SEC-05** (AuditLog) : les notifications ne sont PAS dans l'AuditLog (pas une mutation métier).

### Project Structure Notes

**Fichiers à créer** :
- `code/apps/notifications/models.py` (compléter le stub)
- `code/apps/notifications/services.py`
- `code/apps/notifications/views.py`
- `code/apps/notifications/urls.py`
- `code/apps/notifications/context_processors.py`
- `code/apps/notifications/migrations/0001_initial.py` (via `makemigrations`)
- `code/apps/notifications/tests/__init__.py` + `test_services.py` + `test_views.py`
- `code/templates/notifications/partials/notification_dropdown.html`

**Fichiers à modifier** :
- `code/config/settings/base.py` — ajouter context processor
- `code/config/urls.py` — inclure `apps.notifications.urls`
- `code/templates/partials/topbar.html` — câbler la cloche (badge + dropdown HTMX)

### References

- `epics.md` Story 4.0 (in-app socle, prérequis 4.1/4.2)
- `apps/users/context_processors.py` (pattern context processor à répliquer)
- `templates/partials/topbar.html` ligne 20-23 (cloche hard-codée → slot d'intégration)
- Story 3.9 (`flag_overdue_recommendations` → `AuditLog action=SYSTEM` → déclencheur OVERDUE pour 4.1)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (planification create-story, exécution manuelle)

### Debug Log References

### Completion Notes List

- **2026-05-30** : Artifact créé. Story 4.0 = prérequis de 4.1 et 4.2. Décisions validées : (1) in-app d'abord (e-mail post-MVP), (2) tout l'in-app dans Epic 4 (modèle + feed + badge dans cette story), (3) channel-agnostic. Convention d'idempotence documentée et partagée avec 4.1/4.2.

### File List

*(À compléter pendant l'implémentation dev-story)*
