# Story 3.10: Génération du Sceau HMAC-SHA256 à la Clôture

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Système**,
I want **générer une empreinte cryptographique HMAC-SHA256 unique au moment exact de la clôture d'une recommandation par l'Audit Interne**,
so that **l'intégrité de la recommandation et de ses preuves soit garantie de manière inaltérable et vérifiable (FR24 / NFR-SEC-03)**.

## Acceptance Criteria

1. **AC1 — Sceau généré à la clôture (effet de bord de la transaction FSM finale)**
   - **Given** une recommandation passant en `CLOSED_RESOLVED` via `close_recommendation_by_audit()` (Story 3.8)
   - **When** la clôture est confirmée (dans la même transaction atomique, après `rec.save()`)
   - **Then** un enregistrement `HmacSeal` (1:1) est créé : `hmac_hash` (HMAC-SHA256 hex, 64 car.), `sealed_metadata`, `file_hashes`, `sealed_by = audit_user`, `sealed_at = now()`
   - **And** la clôture et le scellement réussissent ou échouent **ensemble** (atomicité)

2. **AC2 — Contenu du `sealed_metadata` (snapshot figé)**
   - ⚠ **Invariant de sûreté (E2)** : le payload HMAC n'utilise que des **identifiants stables** (UUID, codes) — **jamais** de libellés mutables (`get_full_name()`, label) — car `verify_recommendation_seal` (AC4) **recalcule** depuis l'état courant ; un nom modifié casserait le sceau à tort.
   - Le snapshot scellé contient (champs **immuables** après clôture, Story 3.8) :
     `reference`, `mission_label`, `description`, `source = rec.source.code` (NOT NULL), `priority`, `due_date`, `original_due_date`, `created_at` (str), `closed_at` (str), `closed_by = str(rec.closed_by_id)`, `assigned_dm = str(rec.assigned_dm_id)`, `status`
   - **And** les deux directions (COBAC — A1), **null-safe** car FK nullables : `controlled_department = rec.controlled_department.code if rec.controlled_department else None` (direction auditée) **et** `department = rec.department.code if rec.department else None` (direction qui implémente)
   - **And** une liste `submissions` (triée par `created_at`) : pour chaque soumission ACCEPTED `{"id": str(sub.id), "submitted_by": str(sub.submitted_by_id), "comment": sub.comment}` — identité **par UUID** + commentaire (D2)
   - **And** `file_hashes` contient `{str(evidence_file_id): sha256_hash}` pour chaque fichier des soumissions ACCEPTED (réutilise `EvidenceFile.sha256_hash` déjà stocké — **aucun re-hachage**)
   - **And (M2)** si **aucune** soumission ACCEPTED : `submissions = []` et `file_hashes = {}` → le sceau est **quand même** généré (intégrité des métadonnées seules)

3. **AC3 — Calcul HMAC déterministe avec clé dédiée**
   - **Given** le payload `{"metadata": sealed_metadata, "files": file_hashes}`
   - **When** le sceau est calculé
   - **Then** `hmac_hash = hmac.new(HMAC_SECRET_KEY, canonical_json, sha256).hexdigest()` où `canonical_json = json.dumps(payload, sort_keys=True, separators=(",",":"), default=str)`
   - **And** `HMAC_SECRET_KEY` (settings, distincte de `SECRET_KEY` — ADR-07) est utilisée
   - **And** l'overhead de calcul reste < 500 ms (NFR-PERF-03 — trivialement tenu, pas de re-lecture disque)

4. **AC4 — Vérification d'intégrité (D4)**
   - **Given** une recommandation scellée intacte
   - **When** `verify_recommendation_seal(recommendation)` est appelée
   - **Then** elle recalcule le HMAC depuis l'état courant et retourne `True` si identique au `hmac_hash` stocké, `False` sinon (altération détectée)

5. **AC5 — Backfill des clôtures existantes (D3)**
   - **Given** des recommandations déjà en `CLOSED_RESOLVED` sans sceau (antérieures à 3.10)
   - **When** la data-migration de backfill s'exécute
   - **Then** un `HmacSeal` est généré pour chacune (`sealed_by = closed_by`, `sealed_at = closed_at` si dispo sinon `now()`)

6. **AC6 — Affichage du sceau dans le bandeau de clôture (remplace le placeholder)**
   - **Given** une recommandation `CLOSED_RESOLVED` scellée
   - **When** un utilisateur consulte la page détail
   - **Then** le bandeau (Story 3.8) affiche le `hmac_hash` (tronqué, ex. 16 premiers caractères + « … »), `sealed_at`, et un indicateur « ✓ Intègre » basé sur `verify_recommendation_seal()`
   - **And** le placeholder « 🔒 Sceau HMAC : en attente Story 3.10 » est supprimé

7. **AC7 — Unicité & non-régression**
   - La relation est **1:1** : une 2ᵉ tentative de scellement de la même reco lève (ou `get_or_create` idempotent — pas de doublon)
   - **And** aucune transition FSM existante n'est cassée (les 327 tests restent verts)

## Tasks / Subtasks

- [ ] **Task 1 — Modèle `HmacSeal` + migration** (AC1, AC2)
  - [ ] Subtask 1.1 : Créer `HmacSeal` dans [apps/audit/models.py](../../code/apps/audit/models.py) :
    - `id` UUID PK ; `recommendation = OneToOneField("workflow.Recommendation", on_delete=PROTECT, related_name="hmac_seal")` ; `hmac_hash = CharField(max_length=64)` ; `sealed_metadata = JSONField()` ; `file_hashes = JSONField()` ; `sealed_by = ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT, null=True)` ; `sealed_at = DateTimeField(default=timezone.now)` ; `created_at = auto_now_add`.
    - `Meta.db_table = "audit_hmac_seal"` (conforme architecture).
  - [ ] Subtask 1.2 : Migration `apps/audit/0005_add_hmac_seal.py` (CreateModel). `on_delete=PROTECT` → un dossier scellé ne peut pas être hard-deleted sans retirer le sceau (note dev cleanup).

- [ ] **Task 2 — Service de scellement (`apps/audit/services.py`)** (AC2, AC3)
  - [ ] Subtask 2.1 : Créer `apps/audit/services.py` avec `generate_recommendation_seal(*, recommendation, sealed_by) -> HmacSeal` :
    - **Sérialisation stable + null-safe (E1/E2)** : `rec.source.code` (NOT NULL, direct) ; `str(rec.assigned_dm_id)` / `str(rec.closed_by_id)` (déterministes même à None) ; les FK **nullables** `controlled_department`/`department` → `.code if … else None` ; `submitted_by` → `str(sub.submitted_by_id)`. **Jamais** de `get_full_name()`/label dans le payload.
    - Construire `file_hashes = {str(f.id): f.sha256_hash}` pour les fichiers des soumissions `status=ACCEPTED` (vide si aucune — M2).
    - Construire `sealed_metadata` (snapshot AC2 + liste `submissions` triée par `created_at`).
    - `payload = {"metadata": sealed_metadata, "files": file_hashes}` → `canonical = json.dumps(payload, sort_keys=True, separators=(",",":"), default=str)`.
    - `hmac_hash = hmac.new(settings.HMAC_SECRET_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()`.
    - `HmacSeal.objects.get_or_create(recommendation=..., defaults={...})` (idempotence — AC7) et retour.
    - **Perf (A4)** : charger la reco avec `select_related("source", "controlled_department")` et `prefetch_related` des soumissions ACCEPTED + leurs fichiers pour éviter les N+1 (surtout au backfill itératif).
  - [ ] Subtask 2.2 : Helper interne `_build_seal_payload(recommendation) -> (sealed_metadata, file_hashes, canonical)` réutilisé par génération **et** vérification (source unique de vérité du payload — garantit que `verify` recompose à l'identique).

- [ ] **Task 3 — Vérification (`verify_recommendation_seal`)** (AC4)
  - [ ] `verify_recommendation_seal(recommendation) -> bool` dans `apps/audit/services.py` : recalcule via `_build_seal_payload`, compare avec `recommendation.hmac_seal.hmac_hash` via `hmac.compare_digest`. Retourne `False` si pas de sceau.

- [ ] **Task 4 — Branchement dans la clôture** (AC1, AC7)
  - [ ] Dans [close_recommendation_by_audit](../../code/apps/workflow/services.py) (Story 3.8), après `rec.save(...)` et **dans le même `transaction.atomic()`** : appeler `generate_recommendation_seal(recommendation=rec, sealed_by=performed_by)`.
  - [ ] Ajouter `seal_hash` au `changes` de l'AuditLog TRANSITION de clôture (traçabilité) ; ou log SYSTEM dédié « scellement ». (Choix dev : enrichir le log existant.)
  - [ ] Import : `from apps.audit.services import generate_recommendation_seal` (workflow importe déjà `apps.audit.models.AuditLog`).

- [ ] **Task 5 — Backfill data migration** (AC5)
  - [ ] `apps/audit/0006_backfill_hmac_seals.py` (`RunPython`) : pour chaque `Recommendation` `CLOSED_RESOLVED` sans `hmac_seal`, calculer et créer le sceau. **Logique HMAC répliquée inline** (les migrations n'importent pas les services applicatifs ; utiliser `apps.get_model` + `hmac`/`hashlib` + `settings.HMAC_SECRET_KEY`). `sealed_by = closed_by`, `sealed_at = closed_at or now()`. `reverse_code` : suppression des sceaux backfillés.
  - [ ] Dépendances : `("audit","0005_add_hmac_seal")`, `("workflow","0015_configure_overdue_cron")`.

- [ ] **Task 6 — Affichage bandeau** (AC6)
  - [ ] Dans [RecommendationDetailView.get_context_data](../../code/apps/workflow/views.py) : `context["hmac_seal"] = getattr(rec, "hmac_seal", None)` et `context["seal_valid"] = verify_recommendation_seal(rec) if hmac_seal else None`.
  - [ ] Dans [closure_banner.html](../../code/templates/workflow/partials/closure_banner.html) : remplacer le placeholder par le `hmac_hash` tronqué + `sealed_at` + badge « ✓ Intègre » / « ⚠ Altéré » selon `seal_valid`. Garder un fallback « non scellé » si `hmac_seal is None` (recos non backfillées éventuelles).

- [ ] **Task 7 — Tests** (AC1-AC7) — `apps/audit/tests/test_services.py` (+ intégration workflow)
  - [ ] `test_generate_seal_creates_record` — hash 64 hex, sealed_metadata/file_hashes peuplés.
  - [ ] `test_sealed_metadata_contains_submitter_and_comment` — `submitted_by` + `comment` présents (D2).
  - [ ] `test_file_hashes_match_evidence_sha256` — file_hashes == sha256 stockés des fichiers ACCEPTED.
  - [ ] `test_verify_returns_true_for_intact_seal` / `test_verify_returns_false_after_tampering` (ex. modifier `description` → invalide).
  - [ ] `test_close_recommendation_generates_seal` (intégration : `close_recommendation_by_audit` → `rec.hmac_seal` existe, hash cohérent).
  - [ ] `test_seal_idempotent` — pas de doublon (get_or_create).
  - [ ] `test_hmac_uses_dedicated_key` **(A3 — version robuste)** : `override_settings(HMAC_SECRET_KEY="clé-test-connue")`, sceller, et **comparer au HMAC recalculé manuellement** avec cette clé (preuve exacte d'usage de `HMAC_SECRET_KEY`, pas seulement « ≠ SECRET_KEY »).
  - [ ] `test_seal_without_accepted_submissions` **(M2)** — reco CLOSED sans soumission ACCEPTED → sceau créé, `submissions=[]`, `file_hashes={}`.
  - [ ] `test_verify_stable_after_user_rename` **(E2)** — renommer l'auteur (`get_full_name` change) → `verify` reste `True` (preuve que le payload n'utilise que des UUID).
  - [ ] `test_backfill_seals_existing_closed` **(M4)** — reco CLOSED sans sceau → la logique de backfill crée un `HmacSeal` avec `sealed_at = closed_at`. (Tester la fonction de backfill extraite, ou via `MigrationExecutor`.)
  - [ ] (Optionnel) test détail-view : contexte `hmac_seal` + `seal_valid`.

- [ ] **Task 8 — Validation**
  - [ ] `docker compose exec web python manage.py makemigrations --check` (seules 0005/0006 audit attendues)
  - [ ] `migrate` (crée la table + backfill) — vérifier que `Rec-Dg-05/2026` (CLOSED) reçoit un sceau.
  - [ ] `test apps.workflow apps.audit` (327 + nouveaux, viser vert)
  - [ ] Manuel : clôturer une reco → bandeau affiche le hash + « ✓ Intègre » ; altérer un champ en shell → bandeau « ⚠ Altéré ».

## Dev Notes

### Décisions validées (2026-05-29)

- **D1 — Emplacement** : modèle `HmacSeal` et services de scellement/vérification dans **`apps/audit`** (table `audit_hmac_seal`), conforme à l'architecture (« Audit & Crypto App »). Le service workflow `close_recommendation_by_audit` importe `apps.audit.services.generate_recommendation_seal`.
- **D2 — Payload** : snapshot complet **+ `submitted_by` + `comment`** des soumissions ACCEPTED. Scelle donc l'identité du soumetteur et le contenu de résolution, pas seulement les métadonnées et les fichiers.
- **D3 — Backfill** : data-migration scelle rétroactivement les clôtures existantes (baseline d'intégrité à la date du backfill).
- **D4 — Vérification** : `verify_recommendation_seal()` incluse (recalcul + `hmac.compare_digest`), alimente le badge « Intègre » et prépare l'archive légale Epic 5 (UC4). Pas d'endpoint/UI de vérification dédié dans cette story.

### Patterns & contraintes (vérifiés)

- **Effet de bord de la transaction FSM finale** (ADR-07, archi L.483 ; séquence L.1118-1122 : *UPDATE status → calcul HMAC → INSERT HmacSeal → INSERT AuditLog*). Conforme au pattern service-layer du repo (logique dans le service, pas dans la méthode `@transition` dont le corps reste `pass`).
- **`HMAC_SECRET_KEY`** déjà câblée et validée ([base.py:22](../../code/config/settings/base.py#L22)) — distincte de `SECRET_KEY` (rotation sûre).
- **`EvidenceFile.sha256_hash`** déjà calculé à l'upload ([models.py:853](../../code/apps/workflow/models.py#L853)) → **réutilisé** (pas de re-lecture disque) → NFR-PERF-03 (< 500 ms) trivial.
- **Sérialisation canonique** : `json.dumps(sort_keys=True, separators=(",",":"), default=str)` pour un HMAC déterministe (UUID/dates → str). `hmac.compare_digest` pour la comparaison (anti-timing).
- **Manager** : les soumissions ACCEPTED via `recommendation.evidence_submissions.filter(status=ACCEPTED)`.

### Cas spéciaux & invariants

- **⚠ Payload = identifiants stables uniquement (E2)** : ne jamais inclure de libellé mutable (`get_full_name()`, `source.label`, `department.name`) dans le payload HMAC — uniquement UUID/codes. Sinon `verify_recommendation_seal` (qui recalcule) renverrait `False` après un simple renommage. Les noms lisibles s'obtiennent par navigation FK (`hmac_seal.sealed_by`, `submitted_by`) **hors** du payload scellé. *(Raison pour laquelle A2 « submitted_by_name » est rejeté.)*
- **Redondance `closed_by` ↔ `sealed_by` (E3, intentionnelle)** : `sealed_by` (FK sur `HmacSeal`) = identité navigable du signataire ; `closed_by` dans `sealed_metadata` = snapshot figé entrant dans le HMAC. Au backfill comme en clôture normale, `sealed_by == closed_by`.
- **`description`/`comment` volumineux (M3)** : pas de troncature (valeur probatoire — snapshot intégral). SHA-256 linéaire, pas d'index GIN sur `sealed_metadata` → taille JSONB acceptable.
- **Exemple de payload canonique (M1)** :
  ```json
  {"files":{"<file-uuid>":"<sha256-hex-64>"},
   "metadata":{"assigned_dm":"<uuid|None>","closed_at":"2026-05-29 20:00:00+01:00",
     "closed_by":"<uuid>","controlled_department":"DOP","department":"DRH","created_at":"2026-04-01 10:30:00+01:00",
     "description":"...","due_date":"2026-06-15","mission_label":"Contrôle KYC","original_due_date":"2026-05-15",
     "priority":"CRITIQUE","reference":"REC-2026-042","source":"COBAC","status":"CLOSED_RESOLVED",
     "submissions":[{"comment":"Actions menées…","id":"<uuid>","submitted_by":"<uuid>"}]}}
  ```
  (`sort_keys=True` → clés ordonnées ; `default=str` → dates au format `str(datetime)` avec espace, UUID en str. Déterministe tant que constant.)
- **1:1 OneToOne** : accès `rec.hmac_seal` lève `RelatedObjectDoesNotExist` si absent → utiliser `getattr(rec, "hmac_seal", None)`.
- **`on_delete=PROTECT`** sur la FK reco : un dossier scellé ne peut être hard-deleted sans retirer le sceau d'abord (note pour le nettoyage dev ; le soft-delete `is_deleted` n'est pas affecté).
- **Migrations sans import de services** : la backfill réplique le calcul HMAC inline (modèles historiques `apps.get_model`) — garder la logique de payload synchronisée avec le service (commentaire de renvoi).
- **Idempotence** : `get_or_create(recommendation=...)` pour ne jamais doubler un sceau (re-clôture impossible de toute façon — AC6 immutabilité 3.8).

### Couverture NFR

- **NFR-SEC-03** (HMAC-SHA256) : AC1, AC3. **NFR-PERF-03** (< 500 ms) : AC3 (réutilise les hash existants).
- **NFR-SEC-04** (intégrité fichiers) : `file_hashes` permet de détecter une substitution disque post-clôture (AC4).

### Project Structure Notes

**Fichiers à créer** :
- `code/apps/audit/services.py` — `generate_recommendation_seal()`, `verify_recommendation_seal()`, `_build_seal_payload()`.
- `code/apps/audit/migrations/0005_add_hmac_seal.py` (CreateModel) + `0006_backfill_hmac_seals.py` (RunPython). *(Vérifié : migrations audit = 0001-0004, donc 0005 libre — M5 = faux positif sur cette branche.)*
- `code/apps/audit/tests/__init__.py` **(E5 — le dossier `tests/` n'existe pas dans l'app audit)** + `code/apps/audit/tests/test_services.py`.

**Fichiers à modifier** :
- `code/apps/audit/models.py` — modèle `HmacSeal`.
- `code/apps/workflow/services.py` — branchement dans `close_recommendation_by_audit`.
- `code/apps/workflow/views.py` — contexte `hmac_seal` / `seal_valid` dans `RecommendationDetailView`.
- `code/templates/workflow/partials/closure_banner.html` — remplacement du placeholder.

### References

- `epics.md` Story 3.10 (L.471-484) ; `prd-v2.md` FR24 (L.295) ; `architecture-v2.md` ADR-07 hook HMAC (L.459-491), séquence clôture (L.1118-1122), ERD/data-dictionary `audit_hmac_seal` (L.1558-1561, 1717-1726, 1839-1840), NFR-PERF-03 (L.195), NFR-SEC-03 (L.194).
- Story 3.8 artifact (`close_recommendation_by_audit`, bandeau de clôture, champs `closed_at`/`closed_by`).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (planification create-story, exécution manuelle)

### Debug Log References

### Completion Notes List

- **2026-05-29** : Artifact créé via workflow bmad `create-story` (exécution manuelle). 4 décisions validées : (D1) modèle dans apps/audit (table audit_hmac_seal), (D2) payload = snapshot complet + submitted_by + comment, (D3) backfill des clôtures existantes, (D4) verify_recommendation_seal() inclus.
  - Sceau confirmé comme effet de bord de la transaction de clôture (service layer), réutilisant `EvidenceFile.sha256_hash` existant (NFR-PERF-03 trivial). HMAC via `hmac`/`hashlib` Python + `HMAC_SECRET_KEY` (pas pgcrypto — plus simple, testable, conforme NFR-SEC-03).

### File List

**Créés :**
- `code/apps/audit/services.py` — `_build_seal_payload`, `generate_recommendation_seal`, `verify_recommendation_seal`.
- `code/apps/audit/migrations/0005_hmacseal.py` (CreateModel) + `0006_backfill_hmac_seals.py` (backfill, logique HMAC répliquée null-safe).
- `code/apps/audit/tests/__init__.py` + `code/apps/audit/tests/test_services.py` (12 tests).

**Modifiés :**
- `code/apps/audit/models.py` — modèle `HmacSeal` (table `audit_hmac_seal`).
- `code/apps/workflow/services.py` — scellement dans `close_recommendation_by_audit` (même transaction).
- `code/apps/workflow/views.py` — contexte `hmac_seal` / `seal_valid` (RecommendationDetailView).
- `code/templates/workflow/partials/closure_banner.html` — affichage hash + badge « Intègre/Altéré ».
- `code/apps/workflow/migrations/0005_configure_cleanup_cron.py` + `0015_configure_overdue_cron.py` — **correctif d'ordre** : dépendance `django_q` → `0018_task_success_index` (le get_or_create utilise le vrai modèle Schedule).

**Validation :** 339 tests verts (327 workflow + 12 audit) ; `makemigrations --check` propre ; backfill `Rec-Dg-05/2026` scellée + `verify=True`.
