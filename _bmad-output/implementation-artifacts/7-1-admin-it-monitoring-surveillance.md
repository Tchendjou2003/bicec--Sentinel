# Story 7.1 : Admin IT — Monitoring & Surveillance Opérationnelle

Status: draft

<!-- Nouvelle story issue de la discussion du 2026-06-08. Constat : le rôle Admin IT dans
Sentinel est trop minimaliste pour un contexte bancaire (BICEC). Cette story ajoute des
outils de surveillance opérationnelle : déblocage de comptes verrouillés (onglet sur la
page Gestion utilisateurs), sessions actives, comptes inactifs, dashboard de santé
applicative. Journal d'activité (AuditLog viewer) = story ultérieure.
Hors scope : CPU/RAM/disque, Sentry, métriques infrastructure (outils dédiés). -->

## Story

As a **Admin IT BICEC**,
I want **disposer d'interfaces de surveillance opérationnelle dans Sentinel (comptes
verrouillés, sessions actives, comptes inactifs, santé worker)**,
so that **je puisse résoudre les incidents de sécurité sans intervention manuelle en base,
détecter les comptes orphelins pour la conformité bancaire, et m'assurer que le moteur
de notifications est opérationnel.**

**Contexte produit** — Actuellement, un compte bloqué par django-axes (5 tentatives
échouées) ne peut être débloqué que via l'admin Django, inaccessible aux Admin IT.
Les comptes inactifs (collaborateurs partis) restent actifs indéfiniment faute de
tableau de bord de détection. Le dashboard IT actuel (`AdminDashboardView`) n'affiche
que des compteurs statiques sans action possible. Cette story comble ces manques en
restant dans le périmètre applicatif Sentinel.

## Acceptance Criteria

### AC1 — Onglet "Comptes verrouillés" sur la page Gestion des utilisateurs

1. **Given** l'Admin IT consulte `/auth/provisioning/`
   **Then** la page affiche deux onglets : "Demandes" (comportement actuel) et
   "Comptes verrouillés" (nouveau)
   **And** le pattern d'onglets est identique à celui de l'organigramme
   (boutons `:style` Alpine.js avec `border-bottom:2px solid #E87722` sur l'actif)

2. **Given** l'Admin IT clique sur l'onglet "Comptes verrouillés"
   **Then** il voit le tableau DS des `AccessAttempt` actifs :
   username | IP | nombre de tentatives | horodatage du dernier échec | bouton "Débloquer"

3. **Given** l'Admin IT clique "Débloquer"
   **When** la requête HTMX POST est traitée
   **Then** l'`AccessAttempt` correspondant est supprimé (`AccessAttempt.objects.filter(pk=...).delete()`)
   **And** une entrée `AuditLog` est émise (`action=UPDATE, content_type="AccessAttempt",
   extra_data={"action": "unlock", "username": ...}`)
   **And** un toast `sentinel.notify('Compte débloqué', 'success')` est affiché
   **And** la ligne disparaît du tableau (HTMX OOB swap ou `hx-target` sur la ligne)

4. **Given** aucun compte verrouillé
   **Then** un état vide DS est affiché ("Aucun compte verrouillé")

### AC2 — Sessions actives + déconnexion forcée

1. **Given** l'Admin IT consulte `/auth/admin/sessions/`
   **Then** il voit la liste des sessions Django non expirées :
   username résolu (via `session.get_decoded()["_auth_user_id"]`) | rôle | dernière activité
   **And** les sessions expirées (`expire_date <= now()`) sont exclues

2. **Given** l'Admin IT clique "Déconnecter" sur une session
   **When** HTMX POST traité
   **Then** `Session.objects.filter(session_key=...).delete()`
   **And** une entrée `AuditLog` est émise (`action=UPDATE, content_type="Session",
   extra_data={"action": "force_logout", "target_user": username}`)
   **And** l'utilisateur concerné sera redirigé vers `/auth/login/` à sa prochaine requête

3. **Sécurité** : un Admin IT ne peut pas déconnecter un superuser — guard dans la vue
   (`if target_user.is_superuser: return 403`)

### AC3 — Comptes inactifs / dernier login

1. **Given** l'Admin IT consulte `/auth/admin/inactive-users/`
   **Then** il voit les comptes n'ayant pas eu d'activité depuis ≥ 30 jours
   (filtre : `last_login__lt=now()-timedelta(days=seuil)` OU `last_login__isnull=True`)
   **And** un sélecteur permet de choisir le seuil : 30 / 60 / 90 jours (filtre HTMX)
   **And** les superusers sont exclus de la liste

2. **Given** l'Admin IT clique "Exporter CSV"
   **Then** `GET ?export=csv` retourne un fichier CSV :
   username, prénom, nom, email, rôle, département, dernier login (ou "Jamais")
   **And** nom du fichier : `comptes-inactifs-AAAA-MM-JJ.csv`
   **And** implémenté via `StreamingHttpResponse` + `csv.writer`

### AC4 — Dashboard de surveillance

1. **Given** l'Admin IT accède à `/auth/admin/monitoring/`
   **Then** il voit 5 KPI cards DS (style `components/kpi_card`) :
   — Comptes verrouillés en cours → lien vers onglet lockouts dans `/auth/provisioning/`
   — Sessions actives → `/auth/admin/sessions/`
   — Comptes inactifs >30j → `/auth/admin/inactive-users/`
   — Demandes de provisioning en attente (`UserProvisioningRequest.status=PENDING`) → `/auth/provisioning/`
   — Santé worker : statut OK/ALERTE (ALERTE si taux d'échec >5% sur 24h)

2. **Given** le bloc "Santé Worker"
   **Then** il affiche :
   — Tâches en file d'attente (`OrmQ.objects.count()`)
   — Succès dans les dernières 24h (`Success.objects.filter(stopped__gte=now()-24h).count()`)
   — Échecs dans les dernières 24h (`Failure.objects.filter(stopped__gte=now()-24h).count()`)
   — Horodatage du dernier succès

3. **Given** le bloc "Statistiques d'utilisation"
   **Then** il affiche :
   — Utilisateurs actifs dans les 30 derniers jours (`last_login__gte=now()-30j`, non superuser)
   — Répartition par rôle (compteurs par valeur `User.role`)

### AC5 — Sidebar Admin IT

1. **Given** l'Admin IT est connecté
   **Then** la sidebar Admin IT affiche une nouvelle section "Surveillance" avec :
   — Lien "Monitoring" pointant vers `auth:admin-monitoring`
   **And** ce lien est visible uniquement pour les utilisateurs satisfaisant `AdminRequiredMixin`

## Tasks / Subtasks

- [ ] **Task 1 — Selectors** (`code/apps/users/selectors.py`)
  - [ ] 1.1 : `get_active_lockouts()` → `AccessAttempt.objects.order_by("-attempt_time")`
  - [ ] 1.2 : `get_active_sessions()` → `Session.objects.filter(expire_date__gt=now())`
    avec résolution du `user_id` depuis `session.get_decoded()`
  - [ ] 1.3 : `get_inactive_users(days=30)` → `User.objects.filter(is_superuser=False).filter(
    Q(last_login__lt=now()-timedelta(days=days)) | Q(last_login__isnull=True))`
  - [ ] 1.4 : `get_worker_health()` → dict avec stats OrmQ, Success, Failure (24h)
  - [ ] 1.5 : `get_usage_stats()` → dict : actifs 30j, répartition par `role`
  - [ ] 1.6 : `get_pending_provisioning_count()` →
    `UserProvisioningRequest.objects.filter(status='PENDING').count()`

- [ ] **Task 2 — Services** (`code/apps/users/services.py`)
  - [ ] 2.1 : `unlock_account(*, access_attempt_pk, performed_by) -> None`
    — `AccessAttempt.objects.filter(pk=access_attempt_pk).delete()`
    — `AuditLog(action="UPDATE", content_type="AccessAttempt", extra_data={...})`
  - [ ] 2.2 : `force_logout_session(*, session_key, target_username, performed_by) -> None`
    — `Session.objects.filter(session_key=session_key).delete()`
    — `AuditLog(action="UPDATE", content_type="Session", extra_data={...})`

- [ ] **Task 3 — Vues** (dans `code/apps/users/views.py` ou `monitoring_views.py`)
  Toutes protégées par `AdminRequiredMixin`.
  - [ ] 3.1 : `AdminMonitoringDashboardView` (TemplateView) — agrège les 5 KPI via selectors
  - [ ] 3.2 : `AdminActiveSessionsView` (TemplateView) — GET liste + POST HTMX déconnexion
  - [ ] 3.3 : `AdminInactiveUsersView` (ListView) — filtre `days` via GET param + export CSV
  - [ ] 3.4 : Modifier `ProvisioningRequestListView.get_context_data` pour injecter
    `lockouts = selectors.get_active_lockouts()` (onglet 2)
  - [ ] 3.5 : `AdminUnlockAccountView` (View POST HTMX) — appelle `services.unlock_account`,
    retourne partial `admin_it/partials/lockouts_panel.html` (refresh tableau)

- [ ] **Task 4 — URLs** (`code/apps/users/urls.py`, namespace `auth:`)
  ```python
  path("admin/monitoring/",           AdminMonitoringDashboardView.as_view(), name="admin-monitoring"),
  path("admin/sessions/",             AdminActiveSessionsView.as_view(),      name="admin-sessions"),
  path("admin/inactive-users/",       AdminInactiveUsersView.as_view(),       name="admin-inactive-users"),
  path("admin/lockouts/<uuid:pk>/unlock/", AdminUnlockAccountView.as_view(), name="admin-unlock"),
  ```

- [ ] **Task 5 — Templates**
  - [ ] 5.1 : `code/templates/admin_it/monitoring/dashboard.html`
    — 5 KPI cards (réutiliser `components/kpi_card`)
    — Bloc "Santé Worker" (tâches, succès 24h, échecs 24h, dernier succès)
    — Bloc "Statistiques d'utilisation" (actifs 30j, répartition rôle)
  - [ ] 5.2 : `code/templates/admin_it/monitoring/sessions.html`
    — Tableau DS : username | rôle | dernière activité | bouton "Déconnecter" (HTMX POST)
    — Bouton désactivé si superuser
  - [ ] 5.3 : `code/templates/admin_it/monitoring/inactive_users.html`
    — Sélecteur seuil HTMX (30/60/90j)
    — Tableau DS : username | nom | rôle | département | dernier login
    — Bouton "Exporter CSV"
  - [ ] 5.4 : Modifier `code/templates/admin_it/provisioning_list.html`
    — Ajouter onglet "Comptes verrouillés" (Alpine.js `pane` + `:style` border-bottom,
    identique au pattern `organigramme_list.html`)
    — Contenu de l'onglet = `{% include "admin_it/partials/lockouts_panel.html" %}`
  - [ ] 5.5 : `code/templates/admin_it/partials/lockouts_panel.html`
    — `<div id="lockouts-panel">` + tableau DS + boutons "Débloquer" (HTMX POST)
    — État vide si aucun lockout

- [ ] **Task 6 — Sidebar** (`code/templates/partials/sidebar_admin.html`)
  Ajouter une section "Surveillance" (séparateur DS + lien) pointant vers `auth:admin-monitoring`

## Dev Notes

- `AccessAttempt` : `from axes.models import AccessAttempt` (déjà dans `INSTALLED_APPS`)
- `Session` : `from django.contrib.sessions.models import Session`
  — `session.get_decoded()` peut lever `SuspiciousOperation` si la session est corrompue
  — Wrapper dans un try/except, ignorer silencieusement ces sessions
  — Clé `_auth_user_id` = UUID string → résoudre avec `User.objects.filter(pk=uid).first()`
- Django-Q : `from django_q.models import OrmQ, Success, Failure`
- Export CSV : `StreamingHttpResponse` + `csv.writer` (évite les timeouts sur gros volumes)
- Guard superuser (AC2.3) : dans `AdminActiveSessionsView.post()`, résoudre l'utilisateur
  cible avant de supprimer ; lever `PermissionDenied` si `target_user.is_superuser`
- `get_pending_provisioning_count()` : importer `UserProvisioningRequest` depuis
  `apps.users.models` (éviter import circulaire si dans `selectors.py`)
- Tests : mocker `AccessAttempt` avec `@patch("axes.models.AccessAttempt")` si le module
  n'est pas disponible dans l'environnement de test isolé

## Verification

- `/auth/provisioning/` onglet "Comptes verrouillés" :
  — Tableau visible ; bouton "Débloquer" supprime l'`AccessAttempt`, AuditLog émis, toast affiché
- `/auth/admin/sessions/` :
  — Sessions non expirées listées avec username résolu
  — Déconnexion forcée fonctionne ; superuser protégé (403)
- `/auth/admin/inactive-users/?seuil=60` :
  — Filtre HTMX fonctionne ; `?export=csv` retourne un CSV téléchargeable
- `/auth/admin/monitoring/` :
  — 5 KPI cards avec valeurs calculées
  — Santé worker affichée (OK si 0 échec sur 24h)
- Sidebar Admin IT : section "Surveillance" et lien "Monitoring" visibles pour Admin IT
