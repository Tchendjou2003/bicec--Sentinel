# Story 4.2: Anticipation In-App des Échéances (J-7 / J-3)

Status: ready-for-dev

<!-- Prérequis : Story 4.0 (socle Notification) + 4.1 (hooks + job ruptures) — done. -->

## Story

As a **porteur (ETP, DM Porteur ou DG)**,
I want **être prévenu in-app quand l'échéance d'une de mes recommandations approche (J-7 puis J-3), sans e-mail**,
so that **je pilote mes échéances de manière proactive sans être spammé (FR23)**.

## Acceptance Criteria

1. **AC1 — Palier J-7**
   - **Given** une recommandation **active** (`ASSIGNED` ou `IN_PROGRESS` — le porteur a encore à agir), non en retard, dont `due_date` tombe dans **≤ 7 jours** (`today < due_date ≤ today+7`)
   - **When** le job quotidien s'exécute et que le palier J-7 n'a pas encore été notifié
   - **Then** une `Notification` **non urgente** (`is_urgent=False`) de type `DUE_SOON_J7` est émise au **porteur** (`assigned_etp or assigned_dm`), clé `DUE_SOON_J7:{rec_pk}`

2. **AC2 — Palier J-3**
   - **Given** une recommandation active dont `due_date` tombe dans **≤ 3 jours** (`today < due_date ≤ today+3`)
   - **When** le job s'exécute et que le palier J-3 n'a pas encore été notifié
   - **Then** une `Notification` `DUE_SOON_J3` (non urgente) est émise au porteur, clé `DUE_SOON_J3:{rec_pk}`

3. **AC3 — Toutes les priorités**
   - L'anticipation concerne **toutes** les priorités actives (CRITIQUE, HAUTE, MOYENNE, FAIBLE) — contrairement aux ruptures 4.1 (CRITIQUE only). L'in-app porte le routinier sans risque de spam (pas d'e-mail).

4. **AC4 — Idempotence & réconciliation (+ handoff Jour J)**
   - **Given** un run répété sans changement → aucune notification dupliquée (clé `idempotency_key` unique)
   - **And** si `due_date` est **repoussée** au-delà du palier (report approuvé Story 3.6), ou si la reco **sort de l'état actif** (passée en `PENDING_*`, `CLOSED_RESOLVED`), ou est **formellement en retard** (`due_date < today` → basculée OVERDUE par le job 3.9 dès le lendemain), les `DUE_SOON_J7:{rec}` / `DUE_SOON_J3:{rec}` correspondantes sont **supprimées** → un futur ré-approche re-notifie correctement
   - **And [Jour J — invariant clé]** le **jour exact de l'échéance** (`due_date == today`), la reco n'est **pas encore** OVERDUE (le job 3.9 bascule sur `due_date < today`, strict) : les notifs d'anticipation doivent donc **survivre** ce jour-là. La réconciliation conserve le `DUE_SOON` tant que `due_date >= today` (relais à OVERDUE seulement à J+1). **Sinon : trou noir** — le rappel disparaît le jour où l'action est due, sans alerte de remplacement.

5. **AC5 — Non urgent**
   - Les anticipations sont `is_urgent=False` (le rouge « urgent » reste réservé aux ruptures 4.1). Affichage in-app normal (orange/neutre).

6. **AC6 — Aucun e-mail**
   - Tout est in-app. Le **digest e-mail hebdomadaire** et l'**e-mail alarme incendie** restent **reportés post-MVP** (réutiliseront le socle `Notification`).

7. **AC7 — Résumé de portefeuille → reporté à Epic 6**
   - Le « résumé de portefeuille » (compteurs en cours / en retard / échéances proches, + reports à valider pour l'Audit) de l'epic est **reporté aux dashboards Epic 6** (décision validée). Hors scope 4.2.

## Tasks / Subtasks

- [ ] **Task 1 — `notify_upcoming_deadlines()`** (AC1-AC5) dans [services.py](../../code/apps/workflow/services.py)
  - [ ] Signature `() -> dict` (`{"j7": n, "j3": m, "cleared": k}`), dans `transaction.atomic()`.
  - [ ] `today = timezone.localdate()` ; `ACTIVE = [ASSIGNED, IN_PROGRESS]`.
  - [ ] **J-7** : `Recommendation.objects.filter(status__in=ACTIVE, due_date__gt=today, due_date__lte=today+7)` → pour chaque, `notify_porteur(type=DUE_SOON_J7, is_urgent=False, actor=None, key=f"DUE_SOON_J7:{pk}")`.
  - [ ] **J-3** : idem avec `due_date__lte=today+3` → `DUE_SOON_J3`. (Une reco ≤3 j satisfait aussi ≤7 j : J7 aura déjà été émise un run précédent ; sur le run d'entrée, les deux peuvent partir — acceptable.)
  - [ ] **Réconciliation** : supprimer les `DUE_SOON_J7`/`DUE_SOON_J3` des recos **hors fenêtre**.
    ⚠ **Utiliser `__gte=today`** (pas `__gt`) pour que la notif **survive le Jour J** (cf. AC4 — le job
    OVERDUE ne bascule qu'à `due_date < today`) :
    ```python
    Notification.objects.filter(notification_type=Notification.Type.DUE_SOON_J7).exclude(
        recommendation__status__in=ACTIVE,
        recommendation__due_date__gte=today,                       # ← Jour J inclus
        recommendation__due_date__lte=today + timedelta(days=7),
    ).delete()   # idem J3 avec +3
    ```
    (cible les notifs dont la reco n'est plus « active ET dans `[today, today+N]` » → report, sortie d'état,
    ou **formellement** en retard `due_date < today`). Les fenêtres d'**émission** ci-dessus gardent `__gt=today`
    (on anticipe le futur ; le J-3 déjà émis porte le rappel jusqu'au Jour J).
  - [ ] Réutilise `notify_porteur` ([notifications/services.py](../../code/apps/notifications/services.py)) — déjà gère le skip si pas de porteur.

- [ ] **Task 2 — Wrapper `run_nightly_notifications()`** (D6)
  - [ ] Nouvelle fonction qui appelle `flag_overdue_recommendations()` **puis** `notify_upcoming_deadlines()` et agrège les compteurs. C'est le point d'entrée unique du cron nocturne.

- [ ] **Task 3 — Migration : repointer le Schedule** (D6)
  - [ ] `code/apps/workflow/migrations/0016_repoint_nightly_schedule.py` (`RunPython`) : mettre à jour le `Schedule` existant (`name="Bascule quotidienne OVERDUE"`) → `func="apps.workflow.services.run_nightly_notifications"` (et renommer en `name="Notifications nocturnes (OVERDUE + anticipation)"`). `reverse_code` : restaurer `flag_overdue_recommendations`.

- [ ] **Task 4 — Tests** (`apps/notifications/tests/test_anticipation_notifications.py`)
  - [ ] `test_j7_notifies_porteur_not_urgent` ; `test_j3_notifies_porteur`.
  - [ ] `test_all_priorities_covered` (MOYENNE/FAIBLE reçoivent aussi J-7).
  - [ ] `test_not_in_window_no_notification` (due_date à +10 j → rien).
  - [ ] `test_idempotent` (2ᵉ run = pas de doublon).
  - [ ] `test_reconcile_after_extension` (report repousse due_date → DUE_SOON supprimées → ré-approche re-notifie).
  - [ ] `test_no_anticipation_when_overdue` (due_date passée → pas de DUE_SOON, c'est le domaine des ruptures).
  - [ ] **`test_due_soon_survives_day_j`** — reco active avec `due_date == today` ayant déjà une `DUE_SOON_J3` :
    après le run, la notif **existe toujours** (pas de trou noir), et la reco n'est **pas** OVERDUE.
  - [ ] `test_due_soon_cleared_day_after` — `due_date == today-1` → DUE_SOON supprimée + reco OVERDUE (relais).
  - [ ] `test_run_nightly_runs_both` (wrapper appelle overdue + anticipation).

- [ ] **Task 5 — Validation**
  - [ ] `makemigrations --check` (seule 0016 attendue, data-migration Schedule).
  - [ ] `migrate` + vérifier `Schedule.func == run_nightly_notifications`.
  - [ ] `test apps.workflow apps.audit apps.notifications` (372 + nouveaux).

## Dev Notes

### Décisions validées (2026-05-30)

- **Toutes priorités** pour J-7/J-3 (in-app routinier, pas de spam email). Distinct des ruptures 4.1 (CRITIQUE only).
- **Résumé de portefeuille reporté à Epic 6** (dashboards). 4.2 = uniquement les notifications d'anticipation.
- **Cron étendu** : un seul passage nocturne via `run_nightly_notifications()` (overdue + anticipation). Évite un 2ᵉ cron.
- **Destinataire** = porteur (`assigned_etp or assigned_dm`) ; `is_urgent=False` ; états ciblés = `ASSIGNED`/`IN_PROGRESS` (le porteur a encore à agir ; une reco en `PENDING_*` a déjà été soumise → pas de rappel).

### Patterns réutilisés
- `notify_porteur` (4.1) ; `Notification.Type.DUE_SOON_J7/J3` (déjà dans le modèle 4.0).
- `flag_overdue_recommendations` (3.9/4.1) — même cadence, mêmes `Recommendation.objects` (soft-deleted exclus).
- Pattern réconciliation identique aux ruptures 4.1 (suppression des notifs hors-fenêtre).
- Migration Schedule : pattern [0015](../../code/apps/workflow/migrations/0015_configure_overdue_cron.py) / [0005](../../code/apps/workflow/migrations/0005_configure_cleanup_cron.py).

### Cas spéciaux & invariants
- **⚠ Handoff Jour J (bug de borne — revue 2026-05-31)** : le job OVERDUE bascule sur `due_date < today` (strict)
  et n'émet d'alerte OVERDUE qu'à J+1. Si la réconciliation supprimait le `DUE_SOON` dès `due_date <= today`,
  le **jour exact** de l'échéance le porteur n'aurait **plus aucune notification** (ni anticipation, ni retard).
  → La réconciliation conserve donc le `DUE_SOON` tant que `due_date >= today` ; le relais à OVERDUE se fait à J+1.
- **Anticipation vs rupture** : `DUE_SOON_*` = `due_date` **≥ aujourd'hui** (≤7/≤3 j, Jour J inclus) ;
  `OVERDUE*` = `due_date` **strictement passée**. Frontière nette à `today` ; la réconciliation supprime les
  DUE_SOON dès que la reco passe `due_date < today` (devient OVERDUE).
- **Chevauchement J7/J3** : une reco créée à ≤3 j reçoit J7 + J3 sur le même run (deux heads-up) — acceptable.
- **`due_date` NOT NULL** → pas de cas NULL.

### References
- `epics.md` Story 4.2 (anticipation + résumé) ; doctrine « alarme incendie » (mémoire) ; Story 4.1 (job + helpers).

## Dev Agent Record

### Agent Model Used
claude-opus-4-8 (planification create-story, exécution manuelle)

### Completion Notes List
- **2026-05-30** : Artifact créé. Décisions : toutes priorités, résumé reporté Epic 6, cron étendu (wrapper). États ciblés ASSIGNED/IN_PROGRESS. Réconciliation des DUE_SOON sur sortie de fenêtre.
- **2026-05-31 — Revue d'artifact (bug de borne « Jour J »)** : correction validée. La réconciliation passe
  de `due_date__gt=today` à `__gte=today` pour que le rappel d'anticipation **survive le jour exact de l'échéance**
  (le job OVERDUE ne bascule qu'à `due_date < today`). Sans ce fix, trou noir le Jour J. Tests `test_due_soon_survives_day_j`
  + `test_due_soon_cleared_day_after` ajoutés. Émission inchangée (`> today`).

### File List
*(À compléter pendant l'implémentation dev-story)*
