# Story 5.1: Journal d'Audit Global (Admin IT — Audit Trail)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **Administrateur IT (ADMIN)**,
I want **consulter un journal d'audit global de toutes les actions tracées dans l'application, filtrable par action, module, utilisateur et plage de dates**,
so that **je peux retracer tout événement système ou métier à des fins de conformité, surveillance et diagnostic (NFR-SEC-05 / Epic 5)**.

## Acceptance Criteria

1. **AC1 — RBAC : accès réservé ADMIN**
   - **Given** un utilisateur non-ADMIN (DM, ETP, AUDIT, DG, EXT)
   - **When** il accède à `/admin/audit-trail/`
   - **Then** il est redirigé vers la page de connexion (403 ou redirect login via `AdminRequiredMixin`)
   - **And** seul le rôle `ADMIN` peut consulter le journal complet

2. **AC2 — Affichage paginé du journal (50 entrées/page)**
   - **Given** l'admin accède à `/admin/audit-trail/`
   - **When** aucun filtre n'est actif
   - **Then** toutes les entrées `AuditLog` s'affichent, triées `created_at DESC`, 50 par page
   - **And** chaque ligne affiche : horodatage (date + heure séparés), acteur (nom + rôle, « Système » si `user=null`), badge action coloré, libellé module FR, description (tronquée avec title), adresse IP

3. **AC3 — Filtres GET combinables**
   - **Given** l'admin saisit/sélectionne un ou plusieurs critères dans le bandeau de filtres
   - **When** il clique « Filtrer »
   - **Then** le tableau affiche uniquement les entrées correspondantes (filtres cumulatifs) sans recharger la pagination à la mauvaise page
   - **And** les filtres disponibles sont : Action (`AuditLog.Action.choices`), Module (3 groupes métier : « Recommandations & preuves », « Utilisateurs & accès », « Organisation »), Utilisateur (liste déroulante des 50 acteurs les plus récents), Date du / Au
   - **And** un bouton « Réinitialiser » apparaît dès qu'un filtre est actif et remet à zéro via un GET sur `/admin/audit-trail/`

4. **AC4 — Pagination conserve les filtres actifs**
   - **Given** un filtre est actif et le résultat est paginé
   - **When** l'admin navigue entre les pages
   - **Then** les paramètres de filtre sont propagés dans les liens de pagination (`?page=N&action=X&…`)

5. **AC5 — Badges d'action colorés**
   - **Given** une entrée `AuditLog` dans le tableau
   - **When** on consulte la colonne « Action »
   - **Then** le badge est coloré selon l'action :
     - `CREATE` → vert (`bg-success-tint / text-success-strong`)
     - `UPDATE` / `TRANSITION` → teal (`bg-sentinel-teal-tint`)
     - `DELETE` / `LOGIN_FAILED` → rouge (`bg-danger-tint`)
     - `IMPORT` → orange Sentinel
     - `LOGIN` / `LOGOUT` / `SYSTEM` / `EXPORT` → gris neutre

6. **AC6 — Empty state**
   - **Given** aucune entrée ne correspond aux filtres
   - **When** le tableau est vide
   - **Then** un écran vide centré s'affiche avec un message contextuel (« Aucun événement ne correspond aux filtres sélectionnés. [Réinitialiser] » si filtre actif, sinon « Aucune entrée dans le journal d'audit pour le moment »)

7. **AC7 — Lien dans la sidebar Admin**
   - **Given** un admin est connecté
   - **When** il consulte la barre de navigation latérale
   - **Then** un lien « Journal d'audit » est visible dans la section Admin (sidebar admin)

## Architecture & fichiers implémentés

### Selector (HackSoft Styleguide)
- [code/apps/audit/selectors.py](../../code/apps/audit/selectors.py)
  - `get_audit_logs(*, action, content_type, user_id, date_from, date_to)` : QuerySet `AuditLog` filtré, trié `-created_at`, avec `select_related("user")`
  - `MODULE_CHOICES` : mapping groupe métier → liste de `content_type` techniques (3 groupes : `workflow`, `utilisateurs`, `organisation`)
  - `MODULE_LABELS` : libellés FR des groupes
  - `CONTENT_TYPE_LABEL` : dictionnaire plat `content_type → libellé FR` (précalculé)
  - Filtrage `date_from`/`date_to` via `datetime.combine(..., time.min/max)` pour préserver l'index btree sur `created_at`

### Vue
- [code/apps/users/views.py:1322](../../code/apps/users/views.py) — `AdminAuditTrailView(AdminRequiredMixin, View)`
  - `PAGINATE_BY = 50`
  - Annote le QuerySet avec `module_label` (via `Case/When`) pour éviter les lookups dict en template
  - Reconstruit le `filter_querystring` (`urllib.parse.urlencode`) pour les liens de pagination
  - Passe `action_choices = AuditLog.Action.choices`, `module_choices = MODULE_LABELS`, `users` (50 acteurs récents)

### URL
- [code/apps/users/urls.py:47](../../code/apps/users/urls.py)
  - Route : `admin/audit-trail/`
  - Name : `auth:admin-audit-trail`

### Templates
- [code/templates/admin_it/audit_trail.html](../../code/templates/admin_it/audit_trail.html) : tableau filtrable, badges colorés, pagination avec propagation des filtres, empty state
- [code/templates/partials/sidebar_admin.html](../../code/templates/partials/sidebar_admin.html) : lien « Journal d'audit » dans la section Administration

## Tasks / Subtasks

- [x] **Task 1 — Selector `get_audit_logs`**
  - [x] Subtask 1.1 : créer `apps/audit/selectors.py` avec `get_audit_logs` + constantes `MODULE_CHOICES` / `MODULE_LABELS` / `CONTENT_TYPE_LABEL`

- [x] **Task 2 — Vue `AdminAuditTrailView`**
  - [x] Subtask 2.1 : implémenter la vue dans `apps/users/views.py`
  - [x] Subtask 2.2 : brancher sur `admin/audit-trail/` dans `apps/users/urls.py` (name `admin-audit-trail`)

- [x] **Task 3 — Template**
  - [x] Subtask 3.1 : créer `templates/admin_it/audit_trail.html` (bandeau filtres, tableau, badges, pagination, empty state)

- [x] **Task 4 — Navigation**
  - [x] Subtask 4.1 : ajouter lien « Journal d'audit » dans `templates/partials/sidebar_admin.html`

## Dev Notes

- La Story 5.1 était référencée dans `sprint-status.yaml` (status `done`) mais son fichier story n'avait pas été créé lors de l'implémentation. Ce fichier documente rétrospectivement le travail réalisé.
- Le fichier `apps/audit/selectors.py` est un **nouveau fichier** (non prévu à l'origine dans `apps/audit/`) — il respecte le Styleguide HackSoft (séparation selector/view).
- La propriété `module_label` est annotée via `Case/When` SQL (et non calculée en Python en template) pour éviter N requêtes dict-lookup par ligne.
- Le journal d'audit est **en lecture seule** (append-only au niveau applicatif) ; aucune action de suppression/modification n'est exposée en UI (NFR-SEC-05 partiel — le trigger DB sera ajouté dans une itération dédiée).
