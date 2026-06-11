# Story 4.1: Notifications In-App sur Événements (Workflow + Ruptures)

Status: done

<!-- Prérequis : Story 4.0 (socle Notification + emit_notification) — done. -->
<!-- Implémenté + revue de code (2026-05-30). Échelle de rupture PROGRESSIVE retenue
     (OVERDUE→porteur, J30→DM) ; J60 retiré du MVP. Voir Completion Notes. -->

## Story

As a **Utilisateur concerné (porteur, DM, DG, Audit)**,
I want **recevoir une notification in-app quand un événement me concernant survient — assignation, délégation, soumission, rejet, validation, clôture, report — et surtout les ruptures (passage en retard d'une Critique, jalon 30 j)**,
so that **je voie immédiatement ce qui exige mon action, sans e-mail (FR22)**.

## Acceptance Criteria

1. **AC1 — Notifications sur événements workflow (service layer)**
   - **Given** un événement workflow (assignation, délégation, soumission de preuves, rejet DM, validation DM→Audit, rejet Audit, clôture, demande/décision de report)
   - **When** le service correspondant s'exécute (dans sa transaction)
   - **Then** une `Notification` in-app est émise (`emit_notification`, Story 4.0) au **bon destinataire** (cf. tableau Dev Notes)
   - **And** on **ne notifie jamais l'auteur de l'action** (pas d'auto-notification)
   - **And** les événements « côté Audit » (soumission prête, demande de report) sont notifiés à **`created_by`** (décision D1)
   - **And** [D4] si le DM est **porteur direct** (pas d'ETP assigné) et soumet lui-même les preuves, c'est **l'Audit (`created_by`)** qui est notifié (et non le DM auto-notifié)
   - **And** [D5] un rejet de l'Audit notifie **simultanément le DM ET l'ETP** (si assigné) car les deux doivent reprendre le travail

2. **AC2 — Rupture : passage en retard d'une Critique → porteur** *(échelle progressive D6)*
   - **Given** une recommandation de priorité **CRITIQUE** qui bascule `is_overdue=False → True`
   - **When** le job nocturne `flag_overdue_recommendations()` (Story 3.9, étendu) s'exécute
   - **Then** une `Notification` **urgente** (`is_urgent=True`) est émise au **porteur** (ETP assigné, ou DM/DG porteur), clé `OVERDUE:{rec_pk}`
   - **And** les recos **non-CRITIQUE** basculent bien `is_overdue` mais **ne déclenchent aucune notification** (relèvent du digest 4.2)

3. **AC3 — Rupture : jalon ≥ 30 jours (Critique) → escalade au DM** *(échelle progressive D6)*
   - **Given** une recommandation CRITIQUE en retard avec `aujourd'hui − due_date ≥ 30 jours`
   - **When** le job s'exécute
   - **Then** une `Notification` **urgente** est émise au **DM** (escalade hiérarchique), clé `OVERDUE_J30:{rec_pk}` (seuil, **pas** « exactement 30 j » ; idempotent)

4. **AC4 — Idempotence & réconciliation**
   - **Given** un run répété sans changement → aucune notification dupliquée (contrainte `idempotency_key` unique, Story 4.0)
   - **And** quand le job **retire** le flag (`is_overdue True → False`, ex. report approuvé Story 3.6), les notifications `OVERDUE:{rec_pk}` et `OVERDUE_J30:{rec_pk}` de cette reco sont **supprimées** → un futur re-dépassement re-notifie correctement

5. **AC5 — Escalade J60 reportée (v2)**
   - L'escalade hiérarchique au « supérieur » à 60 jours est **hors scope MVP** (décision D3) — le modèle n'a pas de chef de département. Documenté en backlog v2.

6. **AC6 — Aucun e-mail**
   - Aucune notification e-mail n'est émise (canal reporté post-MVP). Tout est in-app via le socle 4.0.

## Tasks / Subtasks

- [ ] **Task 1 — Helpers de notification** (AC1)
  - [ ] Subtask 1.1 : `apps/notifications/services.py` — ajouter helpers réutilisables :
    - `notify_porteur(rec, *, type, title, actor, is_urgent=False, body="", key)` → destinataire = `rec.assigned_etp or rec.assigned_dm` ; **skip si destinataire == actor**.
    - `notify_dm(rec, *, type, title, actor, is_urgent=False, body="", key)` → destinataire = `rec.assigned_dm` ; skip si == actor. (nouveau helper [D5, D6])
    - `notify_audit_owner(rec, *, type, title, actor, key, body="")` → destinataire = `rec.created_by` ; skip si == actor.
    - `_reco_url(rec)` → `f"/audit/recommandations/{rec.pk}/"`.
  - [ ] Règle universelle : **ne jamais notifier l'acteur** (`recipient == performed_by` → no-op).

- [ ] **Task 2 — Câblage dans les services workflow** ([services.py](../../code/apps/workflow/services.py)) (AC1)
  Ajouter un `emit_notification` à la fin de chaque service (dans la transaction), selon le tableau Dev Notes :
  - [ ] `assign_recommendation_to_dm` → notifie le DM (`ASSIGNED`)
  - [ ] `assign_recommendation_to_dg` → notifie le DG (`ASSIGNED`)
  - [ ] `delegate_recommendation_to_etp` → notifie l'ETP (`DELEGATED`)
  - [ ] `submit_evidence_for_recommendation` → **[D4]** si acteur = ETP : notifie `assigned_dm` (`EVIDENCE_SUBMITTED`) ; si acteur = DM Porteur (no ETP) : notifie `created_by` Audit (`EVIDENCE_SUBMITTED`)
  - [ ] `submit_evidence_by_dg` → notifie `created_by` (`EVIDENCE_SUBMITTED`)
  - [ ] `validate_evidence_for_audit` → notifie `created_by` (`EVIDENCE_VALIDATED`)
  - [ ] `reject_evidence_submission` (DM) → notifie le porteur (ETP), **urgent** (`EVIDENCE_REJECTED`) — note : ce service lève une erreur si `assigned_etp is None`, donc pas de risque d’auto-notification
  - [ ] `reject_recommendation_by_audit` → **[D5]** notifie le porteur (`assigned_etp or assigned_dm`) **ET** le DM (`assigned_dm`) si un ETP est assigné, **urgent** (`EVIDENCE_REJECTED`) — clés distinctes
  - [ ] `close_recommendation_by_audit` → notifie le porteur (`CLOSED`)
  Ajouter un `emit_notification` à la fin de chaque service :
  - [ ] `assign_recommendation_to_dm` → notifie le DM
  - [ ] `assign_recommendation_to_dg` → notifie le DG
  - [ ] `delegate_recommendation_to_etp` → notifie l'ETP
  - [ ] `submit_evidence_for_recommendation` → **[D4]** si acteur = ETP : notifie `assigned_dm` ; si acteur = DM Porteur : notifie `created_by` (Audit)
  - [ ] `submit_evidence_by_dg` → notifie `created_by`
  - [ ] `validate_evidence_for_audit` → notifie `created_by`
  - [ ] `reject_evidence_submission` (DM) → notifie le porteur (ETP), **urgent**
  - [ ] `reject_recommendation_by_audit` → **[D5]** notifie le porteur ET le DM si ETP distinct, **urgent**, clés `...:{recipient_pk}`
  - [ ] `close_recommendation_by_audit` → notifie le porteur
  - [ ] `request_extension` → notifie `created_by`
  - [ ] `approve_extension` → notifie le demandeur `assigned_dm`
  - [ ] `reject_extension` → notifie le demandeur, **urgent**

- [ ] **Task 3 — Ruptures dans le job 3.9** (AC2, AC3, AC4)
  - [ ] Étendre `flag_overdue_recommendations()` ([services.py](../../code/apps/workflow/services.py)) :
    - Après le `update(is_overdue=True)` des `to_flag` : pour chaque reco **CRITIQUE** nouvellement flagguée :
      - → `emit_notification(OVERDUE, is_urgent=True, key=f"OVERDUE:{pk}:{porteur_pk}")` au porteur (`assigned_etp or assigned_dm`).
      - → **[D6]** Si un ETP est assigné : `emit_notification(OVERDUE, is_urgent=True, key=f"OVERDUE:{pk}:{dm_pk}")` au DM également (clé distincte par destinataire).
    - **Jalon J30** : parcourir les recos CRITIQUE actuellement `is_overdue=True` avec `today − due_date ≥ 30` :
      - → `emit_notification(OVERDUE_J30, is_urgent=True, key=f"OVERDUE_J30:{pk}:{porteur_pk}")` (idempotent).
      - → **[D6]** Si un ETP est assigné : `emit_notification(OVERDUE_J30, is_urgent=True, key=f"OVERDUE_J30:{pk}:{dm_pk}")` au DM.
    - Pour les `to_clear` (flag retiré) : `Notification.objects.filter(idempotency_key__startswith=f"OVERDUE:{pk}:").delete()` + même pour `OVERDUE_J30:{pk}:` → réinitialisation (AC4).
  - [ ] Garder la signature `() → dict` ; enrichir le retour : `{"flagged", "cleared", "notified"}`.

- [ ] **Task 4 — Tests** (AC1-AC4)
  - [ ] `apps/notifications/tests/test_workflow_hooks.py` : vérifier destinataire, non-auto-notification, clés multi-destinataires.
  - [ ] `test_overdue_critique_emits_urgent_notification` ; `test_overdue_non_critique_no_notification`.
  - [ ] Non-régression : `apps.workflow` + `apps.audit` + `apps.notifications` restent verts.

- [ ] **Task 5 — Validation**
  - [ ] `makemigrations --check` (aucune migration attendue — pas de changement de schéma)
  - [ ] `test apps.workflow apps.audit apps.notifications`
  - [ ] Manuel : rejouer `demo_dg_workflow` **sans** les `emit_notification` manuels de la démo (les vraies notifs viennent désormais des services) → vérifier les badges DG/Audit.

## Dev Notes

### Décisions validées (2026-05-30)

- **D1 — Destinataire « Audit »** = `created_by` (auditeur créateur de la reco). Ciblé, pas de bruit de pool.
- **D2 — Ruptures** : détectées dans le job nocturne **3.9 étendu** (`flag_overdue_recommendations`), qui connaît déjà les bascules. Un seul cron.
- **D3 — Escalade J60** : **reportée v2** (pas de « chef de département » dans le modèle). 4.1 couvre OVERDUE + J30 vers le porteur.
- **D4 — DM Porteur direct** : quand `assigned_etp is None` et que le DM soumet lui-même (`is_dm_porteur=True` dans le service), l’acteur est le DM. La règle anti-auto-notification éliminerait la notif au DM. Le service doit donc notifier l’**Audit (`created_by`)** à la place (soumission prête pour revue). Cela évite l’angle mort où l’Audit ignore qu’une soumission est prête.
- **D5 — Rejet Audit → double destinataire** : `reject_recommendation_by_audit` renvoie la reco en IN_PROGRESS. Le DM doit coordonner la reprise avec son ETP. Notifier uniquement l’ETP (porteur) laisse le DM dans l’ignorance. → La notif urgente est envoyée au porteur (`assigned_etp or assigned_dm`) **ET** au DM si distinct du porteur. Clés idempotentes distinctes : `EVIDENCE_REJECTED_AUDIT:{rec}:{sub}:{etp}` et `EVIDENCE_REJECTED_AUDIT:{rec}:{sub}:{dm}`.
- **D6 — Ruptures : échelle PROGRESSIVE** *(révisé post-revue 2026-05-30)* : au lieu de notifier porteur + DM simultanément, l'escalade est **graduelle** — `OVERDUE` (jour J du dépassement) → **porteur** ; `OVERDUE_J30` (≥ 30 j) → **escalade au DM**. Moins de bruit, escalade réelle. Clés mono-destinataire `OVERDUE:{rec}` / `OVERDUE_J30:{rec}`. **CRITIQUE uniquement** (les autres priorités → digest 4.2). Le jalon **J60 est retiré du MVP** (reviendra en v2 avec une vraie hiérarchie de département).
- **Règle anti-auto-notification** : on ne notifie jamais l'utilisateur qui a déclenché l'action (gère le cas DM porteur qui soumet et se reverrait notifié, et l'Audit qui clôt sa propre reco).

### Tableau destinataires / clés

| Service (événement) | Destinataire | urgent | Type | Clé idempotence |
|---|---|---|---|---|
| `assign_recommendation_to_dm` | `assigned_dm` (DM) | non | ASSIGNED | `ASSIGNED:{rec}:{dm}` |
| `assign_recommendation_to_dg` | `assigned_dm` (DG) | non | ASSIGNED | `ASSIGNED:{rec}:{dg}` |
| `delegate_recommendation_to_etp` | `assigned_etp` | non | DELEGATED | `DELEGATED:{rec}:{etp}` |
| `submit_evidence_for_recommendation` (acteur=ETP) | `assigned_dm` | non | EVIDENCE_SUBMITTED | `EVIDENCE_SUBMITTED:{rec}:{sub}` |
| `submit_evidence_for_recommendation` (acteur=DM Porteur, no ETP) | `created_by` Audit [D4] | non | EVIDENCE_SUBMITTED | `EVIDENCE_SUBMITTED:{rec}:{sub}` |
| `submit_evidence_by_dg` | `created_by` | non | EVIDENCE_SUBMITTED | `EVIDENCE_SUBMITTED:{rec}:{sub}` |
| `validate_evidence_for_audit` | `created_by` | non | EVIDENCE_VALIDATED | `EVIDENCE_VALIDATED:{rec}:{sub}` |
| `reject_evidence_submission` (DM) | porteur (ETP) | **oui** | EVIDENCE_REJECTED | `EVIDENCE_REJECTED:{rec}:{sub}` |
| `reject_recommendation_by_audit` | porteur [D5] | **oui** | EVIDENCE_REJECTED | `EVIDENCE_REJECTED_AUDIT:{rec}:{sub}:{porteur}` |
| `reject_recommendation_by_audit` | `assigned_dm` (si ETP distinct) [D5] | **oui** | EVIDENCE_REJECTED | `EVIDENCE_REJECTED_AUDIT:{rec}:{sub}:{dm}` |
| `close_recommendation_by_audit` | porteur | non | CLOSED | `CLOSED:{rec}` |
| `request_extension` | `created_by` | non | EXTENSION_REQUESTED | `EXTENSION_REQUESTED:{rec}:{ext}` |
| `approve_extension` | `assigned_dm` (demandeur) | non | EXTENSION_APPROVED | `EXTENSION_APPROVED:{rec}:{ext}` |
| `reject_extension` | `assigned_dm` (demandeur) | **oui** | EXTENSION_REJECTED | `EXTENSION_REJECTED:{rec}:{ext}` |
| **Rupture** OVERDUE (Critique) | porteur (`assigned_etp or assigned_dm`) | **oui** | OVERDUE | `OVERDUE:{rec}` |
| **Rupture** Jalon ≥30 j (Critique) | `assigned_dm` (escalade) | **oui** | OVERDUE_J30 | `OVERDUE_J30:{rec}` |
| ~~Rupture Jalon 60 j~~ | *(retiré du MVP — v2)* | — | — | — |

`porteur` = `assigned_etp or assigned_dm`.

### Patterns réutilisés

- `emit_notification()` ([notifications/services.py](../../code/apps/notifications/services.py)) — idempotent (Story 4.0).
- `Notification.Type` ([notifications/models.py](../../code/apps/notifications/models.py)) — inclut déjà tous les types + `EVIDENCE_SUBMITTED` (ajouté pour la démo) et `is_urgent`.
- `flag_overdue_recommendations()` ([services.py](../../code/apps/workflow/services.py)) — Story 3.9, point d'extension pour les ruptures.
- `created_by`, `assigned_dm`, `assigned_etp` sur `Recommendation`.

### Cas spéciaux & invariants

- **Anti-auto-notification** : guard `if recipient_id == actor_id: return` dans chaque hook.
- **[D4] DM Porteur direct** : dans `submit_evidence_for_recommendation`, la branche `is_dm_porteur=True` (pas d'ETP) doit notifier `created_by` (Audit) et non `assigned_dm` (qui est l'acteur). Le helper `notify_porteur` ne suffira pas ici : utiliser `notify_audit_owner` dans cette branche.
- **[D5] Rejet Audit double destinataire** : appeler le helper `notify_porteur` (ETP ou DM) ET `notify_dm` si ETP distinct. Les deux notifs ont des clés idempotentes distinctes (suffixe `:{recipient_pk}`).
- **[D6] Escalade OVERDUE vers DM** : dans `flag_overdue_recommendations`, après la notif porteur, vérifier `if rec.assigned_etp_id:` et émettre une 2e notif au DM avec clé distincte. La suppression sur `to_clear` doit utiliser `idempotency_key__startswith=f"OVERDUE:{pk}:"` pour couvrir les deux destinataires.
- **Réconciliation** : la suppression des notifs OVERDUE/J30 sur `to_clear` est ce qui permet de **re-notifier** après un report puis un nouveau dépassement (sinon la clé unique bloquerait à vie).
- **Priorité** : ruptures = **CRITIQUE uniquement** (les autres priorités relèvent du résumé de portefeuille, Story 4.2).
- **Transaction** : les `emit_notification` workflow sont dans la même transaction que la mutation métier (cohérence : si le service rollback, pas de notif fantôme).
- **Démo** : `demo_dg_workflow` émet aujourd'hui les notifs manuellement ; après 4.1 elles proviendront des services → retirer les emit manuels de la démo (ou les garder pour un mode hors-service). À traiter en fin de story.

### Couverture NFR

- **FR22** (alertes événements critiques) : AC1-AC3 (in-app). **NFR-PERF-02** : `emit_notification` = 1 INSERT léger dans la transaction existante.
- Doctrine « alarme incendie » (mémoire) : in-app d'abord ; e-mail réutilisera ce socle post-MVP.

### Project Structure Notes

**Fichiers à modifier** :
- `code/apps/notifications/services.py` — helpers `notify_porteur` / `notify_dm` (nouveau) / `notify_audit_owner`.
- `code/apps/workflow/services.py` — `emit_notification` dans ~12 services + ruptures dans `flag_overdue_recommendations`.

**Fichiers à créer** :
- `code/apps/notifications/tests/test_workflow_hooks.py`.

**Aucun changement** : modèle Notification (déjà complet en 4.0), migrations, templates (badge/dropdown 4.0).

### References

- `epics.md` Story 4.1 (Notifications In-App Workflow + Ruptures)
- Story 4.0 artifact (socle `Notification` + `emit_notification` + conventions de clés)
- Story 3.9 (`flag_overdue_recommendations`) ; Story 3.6 (report → `due_date`)
- Mémoire : doctrine « alarme incendie » (e-mail reporté post-MVP)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (planification create-story, exécution manuelle)

### Completion Notes List

- **2026-05-30** : Artifact créé. Décisions : (D1) destinataire Audit = `created_by`, (D2) ruptures dans le job 3.9 étendu, (D3) escalade J60 reportée v2. Règle anti-auto-notification ajoutée. E-mail hors scope (in-app only).
- **2026-05-30** : Analyse critique intégrée. Décisions : (D4) DM Porteur direct → notifie l’Audit, (D5) rejet Audit → double destinataire ETP + DM, (D6) ruptures → escalade vers DM.
- **2026-05-30 — Revue de code post-implémentation** (3 bugs corrigés + 2 divergences tranchées) :
  - **F1** : ajout du filtre `priorité == CRITIQUE` sur OVERDUE **et** J30 (les ruptures ne ciblaient aucune priorité → spam).
  - **F2** : la réconciliation (`to_clear`) **supprime** désormais les notifs `OVERDUE:{pk}` / `OVERDUE_J30:{pk}` → re-notification possible après report + re-dépassement (AC4 réparé).
  - **F3 / D4** : `submit_evidence_for_recommendation` notifie l’**Audit** quand le DM porteur soumet (sans ETP) — auparavant `notify_dm` skippait l’acteur → personne notifié.
  - **F4 (révisé)** : échelle **progressive** retenue (OVERDUE→porteur, J30→DM) au lieu de porteur+DM simultanés ; clés mono-destinataire.
  - **F5** : jalon **J60 retiré** du MVP (conforme à la doctrine de scope ; revient en v2).
  - Tests ajoutés : `apps/notifications/tests/test_rupture_notifications.py` (ruptures CRITIQUE/non-CRITIQUE, J30, réconciliation, idempotence, D4, D5, clôture). **372 tests verts**, `makemigrations --check` propre.
  - Backlog noté : future story « notifications/rappels **paramétrables par l’Audit** » (seuils, priorités, destinataires, canal).

### File List

- `code/apps/workflow/services.py` — hooks `emit_notification` (11 services) + ruptures CRITIQUE dans `flag_overdue_recommendations` + réconciliation.
- `code/apps/notifications/services.py` — helpers `notify_porteur` / `notify_dm` / `notify_audit_owner` / `_reco_url`.
- `code/apps/notifications/tests/test_workflow_hooks.py`, `test_rupture_notifications.py`.
