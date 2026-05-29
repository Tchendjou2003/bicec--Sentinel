# Story 3.9: Bascule Automatique OVERDUE (Cron)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Système (Background Job)**,
I want **passer automatiquement `is_overdue = True` à minuit pour les recommandations échues non clôturées (et retirer le flag si elles ne sont plus en retard)**,
so that **l'information « en retard » soit exacte dans les tableaux de bord et les listes le lendemain matin (FR21)**.

## Acceptance Criteria

1. **AC1 — Bascule des recos échues actives → `is_overdue = True`**
   - **Given** une recommandation dans un état **éligible** (`ASSIGNED`, `IN_PROGRESS`, `PENDING_DM_REVIEW`, `PENDING_AUDIT_REVIEW`)
   - **And** `due_date < aujourd'hui` (date locale Africa/Douala) **et** `is_overdue = False`
   - **When** le job nocturne `flag_overdue_recommendations()` s'exécute
   - **Then** `is_overdue` passe à `True`

2. **AC2 — États non éligibles jamais marqués**
   - **Given** une recommandation en `DRAFT` ou `CLOSED_RESOLVED`, **ou** dont `due_date >= aujourd'hui`
   - **When** le job s'exécute
   - **Then** `is_overdue` reste/devient `False` (jamais marqué en retard)

3. **AC3 — Réconciliation bidirectionnelle (retrait du flag)**
   - **Given** une recommandation avec `is_overdue = True` qui n'est plus en retard — soit parce qu'un **report a été approuvé** (Story 3.6) repoussant `due_date` au futur, soit parce qu'elle est passée en `CLOSED_RESOLVED`
   - **When** le job s'exécute
   - **Then** `is_overdue` repasse à `False`

4. **AC4 — Audit trail : un `AuditLog` SYSTEM par reco basculée**
   - **Given** une recommandation dont `is_overdue` change (True↔False) pendant le run
   - **Then** un `AuditLog` est créé : `action=SYSTEM`, `user=None`, `content_type="Recommendation"`, `object_id=rec.pk`, `changes={"is_overdue": [ancien, nouveau]}`, `description` explicite (ex. `f"Bascule automatique OVERDUE {rec.reference} : en retard"`)
   - **And** aucune entrée n'est créée pour les recos dont le flag ne change pas

5. **AC5 — Idempotence**
   - **Given** un état stable (aucune échéance franchie, aucun report, aucune clôture depuis le dernier run)
   - **When** le job s'exécute une 2ᵉ fois
   - **Then** aucune bascule n'a lieu et **aucun** `AuditLog` n'est créé

6. **AC6 — Périmètre des données**
   - **Given** des recommandations soft-deleted (`is_deleted=True`)
   - **Then** elles sont **exclues** (manager par défaut `ActiveRecommendationManager`)
   - **And** `due_date` étant **NOT NULL** ([models.py:264](../../code/apps/workflow/models.py#L264)), aucun cas NULL n'est à gérer

## Tasks / Subtasks

- [ ] **Task 1 — Service `flag_overdue_recommendations()`** (AC1, AC2, AC3, AC4, AC5, AC6)
  - [ ] Subtask 1.1 : Créer la fonction module-level dans [services.py](../../code/apps/workflow/services.py)
    - Signature : `def flag_overdue_recommendations() -> dict:` (pas de kwargs requis ; appelée par le scheduler)
    - Docstring complète (Args/Returns, réf. AC1-AC6 / FR21). Mentionner : destinée au CRON Django-Q2 quotidien.
    - Réutilise le **squelette** de `cleanup_abandoned_drafts` ([services.py:1196](../../code/apps/workflow/services.py#L1196)) : `transaction.atomic()`, `AuditLog(user=None, …)`, retourne un compteur.
    - ⚠ **Divergence assumée** : `cleanup` crée **un seul** AuditLog agrégé (`object_id=None`) ; ici on crée **un log par reco** (`object_id=rec.pk`) — Décision C.
  - [ ] Subtask 1.2 : Logique
    - `today = timezone.localdate()` (date locale Africa/Douala — `USE_TZ=True`).
    - `ELIGIBLE = [Status.ASSIGNED, Status.IN_PROGRESS, Status.PENDING_DM_REVIEW, Status.PENDING_AUDIT_REVIEW]`
    - **À flaguer** : `to_flag = Recommendation.objects.filter(status__in=ELIGIBLE, due_date__lt=today, is_overdue=True is False).filter(is_overdue=False)` → en pratique : `status__in=ELIGIBLE, due_date__lt=today, is_overdue=False`.
    - **À nettoyer (réconciliation)** : `to_clear = Recommendation.objects.filter(is_overdue=True).exclude(status__in=ELIGIBLE, due_date__lt=today)`
      → retire le flag si statut non-éligible (ex. `CLOSED_RESOLVED`) **ou** `due_date >= today`.
    - Capturer les pks (et `reference`) des deux ensembles **avant** update (pour l'AuditLog).
    - `to_flag.update(is_overdue=True)` et `to_clear.update(is_overdue=False)` (bulk, efficace ; `update()` ne déclenche pas `save()`/FSM — OK, `is_overdue` n'est pas piloté par django-fsm).
    - `AuditLog.objects.bulk_create([...])` : une entrée SYSTEM par reco basculée (changes `[False, True]` pour flag, `[True, False]` pour clear).
    - Retourner `{"flagged": len(flagged_pks), "cleared": len(cleared_pks)}`.
  - [ ] Subtask 1.3 : Le manager par défaut exclut déjà les soft-deleted — ne PAS utiliser `all_objects`.

- [ ] **Task 2 — Migration : enregistrement du Schedule Django-Q2** (AC1)
  - [ ] Subtask 2.1 : Créer `code/apps/workflow/migrations/0015_configure_overdue_cron.py` (calquée sur [0005](../../code/apps/workflow/migrations/0005_configure_cleanup_cron.py))
    - `RunPython(create_overdue_schedule, reverse_code=remove_overdue_schedule)` avec `try/except ImportError` sur `django_q.models.Schedule`.
    - `Schedule.objects.get_or_create(name="Bascule quotidienne OVERDUE", defaults={"func": "apps.workflow.services.flag_overdue_recommendations", "schedule_type": "D", "repeats": -1, "next_run": <minuit Douala +1j>})`
    - **`next_run`** : `timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=1)` (localtime → 00:00 Douala, pas UTC).
    - `dependencies = [("workflow", "0014_add_closure_fields_and_audit_rejection"), ("django_q", "0001_initial")]`

- [ ] **Task 3 — Tests** (AC1-AC6) — classe `FlagOverdueRecommendationsServiceTest(TestCase)` dans [test_services.py](../../code/apps/workflow/tests/test_services.py)
  - [ ] `test_flags_active_overdue` — états actifs échus → `is_overdue=True`
  - [ ] `test_excludes_draft_and_closed` — DRAFT et CLOSED_RESOLVED jamais marqués même si échus
  - [ ] `test_excludes_future_and_today_due_date` — `due_date >= today` → reste `False`
  - [ ] `test_reconcile_clears_after_extension` — reco `is_overdue=True` dont `due_date` repoussée au futur → `False` au run suivant
  - [ ] `test_reconcile_clears_when_closed` — reco `CLOSED_RESOLVED` avec ancien `is_overdue=True` → `False`
  - [ ] `test_idempotent_second_run` — 2ᵉ run sans changement = 0 bascule, 0 AuditLog
  - [ ] `test_audit_log_per_reco_system` — un `AuditLog` action=SYSTEM, `object_id=rec.pk`, `changes={"is_overdue":[…]}` par reco basculée
  - [ ] `test_excludes_soft_deleted` — reco soft-deleted échue → non touchée
  - [ ] `test_returns_counts` — `{"flagged": n, "cleared": m}` corrects

- [ ] **Task 4 — Vérif UI (lecture seule, aucun changement attendu)**
  - [ ] Confirmer que le badge « En retard » s'affiche déjà via `is_overdue` ([recommendation_table.html:33](../../code/templates/workflow/partials/recommendation_table.html#L33), [recommendation_detail.html:37](../../code/templates/workflow/recommendation_detail.html#L37)) et le tri `-is_overdue` ([selectors.py:134](../../code/apps/workflow/selectors.py#L134)) → **aucune modification de template**.

- [ ] **Task 5 — Validation**
  - [ ] `docker compose exec web python manage.py makemigrations --check` (seule 0015 attendue — pas de changement de schéma, juste data-migration Schedule)
  - [ ] `docker compose exec web python manage.py migrate`
  - [ ] `docker compose exec web python manage.py test apps.workflow --verbosity=2` (318 actuels + ~9 nouveaux)
  - [ ] Test manuel shell : forcer une reco active à `due_date` passée → `flag_overdue_recommendations()` → `is_overdue=True` + AuditLog SYSTEM ; approuver un report repoussant l'échéance → relancer → `is_overdue=False`.

## Dev Notes

### Décisions validées (2026-05-29)

- **OVERDUE = flag, pas un état FSM.** `architecture-v2.md` L.184/480 : « FSM strict 5 états + flag OVERDUE ». Le champ `is_overdue` existe déjà ([models.py:286](../../code/apps/workflow/models.py#L286)) ; la 3.9 en est le **premier writer**. La machine FSM (`status`) n'est pas touchée — `update(is_overdue=…)` n'interfère pas avec django-fsm.
- **Décision A — États éligibles** : `ASSIGNED, IN_PROGRESS, PENDING_DM_REVIEW, PENDING_AUDIT_REVIEW`. Exclus : `DRAFT` (brouillon d'audit non engagé ; la validation interdit déjà une échéance passée à la création) et `CLOSED_RESOLVED` (dossier résolu).
- **Décision B — Réconciliation bidirectionnelle** : le job pose ET retire le flag, pour rester cohérent après un report approuvé (Story 3.6 met à jour `due_date`, [services.py:925](../../code/apps/workflow/services.py#L925)) ou une clôture. (La remise à `False` synchrone dans le service de report est une optimisation hors scope — le run nocturne suffit.)
- **Décision C — AuditLog par reco** (`action=SYSTEM`, `object_id=rec.pk`) plutôt qu'un log agrégé : traçabilité par dossier, exploitable par la timeline (Story 5.1). Append-only (NFR-SEC-05).

### Patterns réutilisés (vérifiés)

- **`cleanup_abandoned_drafts`** ([services.py:1196](../../code/apps/workflow/services.py#L1196)) — squelette de tâche CRON Django-Q2. **⚠ Divergence** : log agrégé (`object_id=None`) vs log par-reco ici.
- **Migration Schedule** ([0005_configure_cleanup_cron.py](../../code/apps/workflow/migrations/0005_configure_cleanup_cron.py)) — pattern `get_or_create` + `try/except ImportError` + `reverse_code`. 0005 vise 02:00 via `now().replace(hour=2)` (UTC) ; **ici on utilise `localtime()`** pour viser 00:00 Douala.
- **`AuditLog.Action.SYSTEM`** ([audit/models.py:34](../../code/apps/audit/models.py#L34)) — action dédiée aux jobs système.
- **`Q_CLUSTER`** poll 10s, `TIME_ZONE="Africa/Douala"`, `USE_TZ=True` ([base.py:178,193,195](../../code/config/settings/base.py#L178)).

### Cas spéciaux & invariants

- **Comportement tz Django-Q2** : `next_run` est stocké **aware** (`USE_TZ=True`). Le worker compare à `now()` (UTC) et ré-incrémente de 24h après chaque exécution. L'ancre « minuit Douala » (WAT/UTC+1, sans DST) reste donc correcte dans le temps.
- **Index DB** : `idx_reco_status` + `idx_reco_overdue` existent ([models.py:379,383](../../code/apps/workflow/models.py#L379)) → filtres `status`/`is_overdue` couverts. **`due_date` n'est PAS indexé** → le `due_date__lt` fera un scan ; acceptable pour un batch nocturne (volume modeste, hors heures de pointe). **Pas d'ajout d'index dans cette story.**
- **`due_date` NOT NULL** ([models.py:264](../../code/apps/workflow/models.py#L264)) → aucune gestion de NULL.
- **Imports historiques** (Story 4.3 : statut `ASSIGNED` + `due_date` passée) seront **massivement flagués au 1ᵉʳ run** → comportement attendu (FR21) et générera autant d'`AuditLog` SYSTEM (append-only, OK).
- **`update()` vs `save()`** : `update(is_overdue=…)` est volontaire (bulk, pas de signaux, pas de FSM). `is_overdue` n'est pas un champ protégé django-fsm.

### Couverture NFR

- **NFR-SEC-05** (AuditLog append-only) : AC4.
- **NFR-REL-04** (résilience scheduler Django-Q2) : architecture-v2 L.393-423 (heartbeat indépendant du worker).

### Project Structure Notes

**Fichiers à créer** :
- `code/apps/workflow/migrations/0015_configure_overdue_cron.py`

**Fichiers à modifier** :
- `code/apps/workflow/services.py` — fonction `flag_overdue_recommendations()`
- `code/apps/workflow/tests/test_services.py` — classe `FlagOverdueRecommendationsServiceTest` (~9 tests)

**Aucun changement** : modèles (champ `is_overdue` déjà présent), templates (badge déjà câblé), urls, vues.

### References

- `_bmad-output/planning-artifacts/epics.md` Story 3.9 (L.402-413)
- `_bmad-output/planning-artifacts/prd-v2.md` FR21 (L.290)
- `_bmad-output/planning-artifacts/architecture-v2.md` flag OVERDUE (L.184, 480), scheduler Django-Q2 (L.226, 393-423)
- Story 3.6 artifact (interaction report → `due_date`) ; migration 0005 (pattern Schedule)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (planification create-story, exécution manuelle dans Claude Code)

### Debug Log References

### Completion Notes List

- **2026-05-29** : Artifact créé via workflow bmad `create-story` (exécution manuelle). 3 décisions utilisateur validées avant rédaction : (A) états éligibles = actifs hors DRAFT/CLOSED, (B) réconciliation bidirectionnelle, (C) AuditLog SYSTEM par reco.
  - OVERDUE confirmé comme **flag** `is_overdue` (déjà présent, jamais écrit) et non comme 6ᵉ état FSM (architecture-v2 L.184/480).
  - Revue de plan : corrigé `due_date` NOT NULL (pas de NULL à gérer), explicité la divergence de granularité AuditLog vs `cleanup_abandoned_drafts`, documenté le comportement tz Django-Q2, noté l'absence d'index sur `due_date`.

### File List

**Créés :**
- `code/apps/workflow/migrations/0015_configure_overdue_cron.py` — Schedule django-q2 quotidien (minuit Douala).

**Modifiés :**
- `code/apps/workflow/services.py` — fonction `flag_overdue_recommendations()` (réconciliation bidirectionnelle + AuditLog SYSTEM par reco).
- `code/apps/workflow/tests/test_services.py` — classe `FlagOverdueRecommendationsServiceTest` (9 tests) + import du service.

**Validation :** `makemigrations --check` = « No changes detected » ; `test apps.workflow` = **327 verts** (318 + 9). Migration 0015 appliquée OK.

**Aucun changement** : modèles (`is_overdue` déjà présent), templates (badge déjà câblé), urls, vues — conforme au plan.
