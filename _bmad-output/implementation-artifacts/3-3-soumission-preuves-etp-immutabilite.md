# Story 3.3: Soumission de Preuves (ETP) et Immutabilité

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Employé Traitant (ETP)**,
I want **uploader mes fichiers justificatifs (<6 Mo) rattachés à des livrables et un commentaire de résolution**,
so that **le statut passe à `PENDING_DM_REVIEW` pour que mon manager vérifie avant envoi final (FR15, FR16).**

## Acceptance Criteria

1. **AC1 — Upload de fichier avec validation sécurisée**
   - **Given** une recommandation en état `IN_PROGRESS` m'étant assignée (`assigned_etp == request.user`),
   - **When** j'uploade un fichier justificatif via le formulaire de soumission,
   - **Then** le fichier est sauvegardé sur le système de fichiers (volume Docker `/media/`).
   - **And** le système valide l'intégrité du fichier par **Magic Bytes** : les 8 premiers octets du fichier sont comparés aux signatures connues des formats autorisés (PDF, DOCX, XLSX, JPEG, PNG). Les macros XLSM et les faux renommages sont interdits (NFR-SEC-04).
   - **And** la taille du fichier ne dépasse pas **6 Mo** (NFR-SCA-01) avec une limite globale de **20 Mo max par recommandation** pour les preuves actives. La validation applicative doit vérifier la taille réelle du fichier uploadé et lever une erreur claire.
   - **And** le fichier est enregistré via un modèle `EvidenceFile` avec métadonnées (nom original, taille, hash SHA-256, type MIME détecté par magic bytes, date d'upload, utilisateur).

2. **AC2 — Tags et Catégorisation des Fichiers**
   - **Given** une recommandation en cours de traitement,
   - **When** l'ETP soumet le formulaire de preuves,
   - **Then** l'utilisateur peut associer un tag (catégorie) à chaque fichier (`"Justificatif"`, `"PV de Recette"`, `"Rapport"`, `"Autre"`).
   - **And** le tag est stocké dans le modèle `EvidenceFile` pour catégoriser la preuve.

3. **AC3 — Soumission avec commentaire et transition FSM**
   - **Given** un ou plusieurs fichiers uploadés et un commentaire de résolution saisi,
   - **When** l'ETP clique sur "Soumettre les preuves",
   - **Then** le système crée un enregistrement `EvidenceSubmission` regroupant les fichiers et le commentaire.
   - **And** l'état FSM de la recommandation passe de `IN_PROGRESS` à `PENDING_DM_REVIEW` via la transition `submit_evidence()`.
   - **And** l'action est tracée dans l'Audit Log (action=TRANSITION, description="Soumission de preuves par [ETP] pour [Référence]").
   - **And** un message de confirmation est affiché à l'ETP ("Vos preuves ont été soumises avec succès. En attente de validation par votre Directeur Métier.").

4. **AC4 — Immutabilité des fichiers (Append-Only)**
   - **Given** un fichier uploadé et associé à une soumission,
   - **Then** il est impossible de le supprimer physiquement ou de l'altérer en base de données.
   - **And** le modèle `EvidenceFile` n'expose aucune méthode `delete()` fonctionnelle (override avec `raise` ou protection via un manager).
   - **And** le hash SHA-256 du contenu du fichier est calculé et stocké lors de l'upload pour vérification ultérieure d'intégrité.
   - **And** le fichier est stocké avec un nom de fichier UUID (pas le nom original) pour éviter les collisions et les injections de chemin.

5. **AC5 — UI de soumission (modale HTMX)**
   - **Given** la page de détail d'une recommandation (Centre de Contrôle) en état `IN_PROGRESS`,
   - **And** l'utilisateur connecté est l'ETP assigné (`assigned_etp == user`) OU le DM assigné (s'il est DM Porteur, c'est-à-dire `assigned_etp == null`),
   - **Then** un bouton **"Soumettre Preuves"** est visible dans la barre d'actions.
   - **And** en cliquant dessus, une modale HTMX s'ouvre avec :
     - Un sélecteur permettant d'ajouter dynamiquement jusqu'à 5 fichiers (géré via Alpine.js).
     - Un sélecteur de tag (catégorie) pour chaque fichier.
     - Un champ texte "Commentaire de résolution" (textarea, obligatoire).
     - Un bouton de validation "Soumettre les preuves".
   - **And** le bouton est masqué si le statut n'est pas `IN_PROGRESS`.
   - **And** le bouton est masqué si l'utilisateur n'est pas l'ETP assigné ou le DM Porteur.

6. **AC6 — Sécurité RBAC**
   - **Given** un utilisateur qui n'est pas l'ETP assigné (ni le DM Porteur),
   - **When** il tente d'accéder à la vue de soumission (`/audit/recommandations/<uuid>/submit-evidence/`),
   - **Then** il reçoit une erreur **403 Forbidden**.
   - **And** un Audit Interne, un DG, ou tout autre utilisateur non autorisé ne peut pas soumettre de preuves.

7. **AC7 — Notification placeholder**
   - **Given** une soumission réussie,
   - **Then** le système prépare le hook de notification pour le DM (deferred to Epic 4).
   - **And** un message de succès est affiché à l'écran via le framework de messages Django.

## Tasks / Subtasks

- [ ] Task 1 : Backend — Modèles de données (Evidence)
  - [ ] Subtask 1.1 : Créer le modèle `EvidenceFile` dans `apps/workflow/models.py` :
    - Champ `id` : UUIDField (primary key, auto-généré).
    - Champ `submission` : ForeignKey vers `EvidenceSubmission` (related_name="files").
    - Champ `file` : FileField (upload_to="evidence/<uuid_reco>/%Y/%m/").
    - Champ `original_filename` : CharField (nom d'origine du fichier).
    - Champ `file_size` : PositiveIntegerField (taille en octets).
    - Champ `mime_type` : CharField (type MIME détecté par magic bytes).
    - Champ `sha256_hash` : CharField(max_length=64) (empreinte SHA-256 du contenu).
    - Champ `tag` : CharField avec TextChoices (`JUSTIFICATIF`, `PV_RECETTE`, `RAPPORT`, `AUTRE`).
    - Champ `uploaded_by` : ForeignKey vers User.
    - Champ `created_at` : DateTimeField auto_now_add.
    - **Override `delete()` → raise ProtectedError** pour garantir l'immutabilité (AC4).
    - **Override du Manager par défaut** pour empêcher `bulk_delete`.
  - [ ] Subtask 1.2 : Créer le modèle `EvidenceSubmission` dans `apps/workflow/models.py` :
    - Champ `id` : UUIDField (primary key).
    - Champ `recommendation` : ForeignKey vers `Recommendation` (related_name="evidence_submissions").
    - Champ `comment` : TextField (commentaire de résolution, obligatoire).
    - Champ `submitted_by` : ForeignKey vers User.
    - Champ `created_at` : DateTimeField auto_now_add.
    - **Note** : Plusieurs soumissions peuvent exister par recommandation (en cas de rejet DM puis re-soumission, Story 3.4/FR18).
  - [ ] Subtask 1.3 : Créer la migration Django (`python manage.py makemigrations workflow`).

- [ ] Task 2 : Backend — Validation Magic Bytes & sécurité fichiers
  - [ ] Subtask 2.1 : Créer un module utilitaire `apps/workflow/validators.py` :
    - Fonction `validate_magic_bytes(file)` : lit les 8 premiers octets et compare aux signatures connues :
      - PDF : `%PDF` (25 50 44 46)
      - DOCX/XLSX : PK ZIP header (50 4B 03 04) — **rejeter si fichier XLSM** (vérifier `[Content_Types].xml` dans le ZIP pour `application/vnd.ms-excel.sheet.macroEnabled`).
      - JPEG : `FF D8 FF`
      - PNG : `89 50 4E 47 0D 0A 1A 0A`
    - Fonction `validate_file_size(file, max_size_mb=6)` : rejette si `file.size > max_size_mb * 1024 * 1024`.
    - Fonction `validate_total_active_evidence_size(recommendation, new_files_size, max_size_mb=20)` : rejette si la taille totale (actifs + nouveaux) > 20 Mo.
    - Fonction `compute_sha256(file)` : calcule le hash SHA-256 du contenu par chunks de 8192 octets.
    - Fonction `detect_mime_type(file)` : déduit le type MIME à partir des magic bytes.
  - [ ] Subtask 2.2 : Intégrer les validators dans le formulaire `EvidenceUploadForm`.

- [ ] Task 3 : Backend — Transition FSM et service
  - [ ] Subtask 3.1 : Ajouter la transition FSM `submit_evidence()` dans le modèle `Recommendation` (models.py) :
    - Source : `IN_PROGRESS`
    - Target : `PENDING_DM_REVIEW`
  - [ ] Subtask 3.2 : Créer `submit_evidence_for_recommendation(*, recommendation, files_data, comment, performed_by, ip_address)` dans `apps/workflow/services.py` :
    - Verrouiller l'objet via `select_for_update()` (ADR-07 §5.4).
    - Vérifier que `recommendation.status == IN_PROGRESS`.
    - Vérifier que `performed_by` est bien l'ETP assigné OU le DM Porteur.
    - Vérifier la limite globale de 20 Mo via `validate_total_active_evidence_size`.
    - Créer l'`EvidenceSubmission` avec le commentaire.
    - Pour chaque fichier : valider magic bytes, vérifier taille (6 Mo), calculer SHA-256, créer `EvidenceFile` avec son tag.
    - Appeler `recommendation.submit_evidence()` (transition FSM).
    - Sauvegarder la recommandation (`update_fields=["status", "updated_at"]`).
    - Tracer dans l'Audit Log (action=TRANSITION).
    - Retourner la recommandation mise à jour.

- [ ] Task 4 : Backend — Formulaire et vue
  - [ ] Subtask 4.1 : Créer `EvidenceUploadForm` dans `apps/workflow/forms.py` :
    - Champ `comment` : CharField(widget=Textarea) obligatoire.
    - Champ `files` : FileField avec `widget=ClearableFileInput(attrs={'multiple': True})`.
    - Champ `tags` : liste de tags correspondant à chaque fichier (géré côté JS/Alpine).
    - Méthode `clean_files()` : valide magic bytes et taille pour chaque fichier.
  - [ ] Subtask 4.2 : Créer `RecommendationSubmitEvidenceView` dans `apps/workflow/views.py` :
    - GET : Retourne la modale/page HTMX avec formulaire d'upload.
    - POST : Exécute la soumission via le service layer.
    - Sécurité : Vérifier que `request.user == recommendation.assigned_etp` OU (DM Porteur : `request.user == recommendation.assigned_dm and recommendation.assigned_etp is None`).
    - Gérer `TransitionNotAllowed` et `ValueError` dans le POST.
    - Renvoyer `HX-Refresh: true` après succès (pattern Story 2.5/3.2).
  - [ ] Subtask 4.3 : Ajouter l'URL `recommandations/<uuid:pk>/submit-evidence/` dans `apps/workflow/urls.py`.

- [ ] Task 5 : Frontend — UI de soumission
  - [ ] Subtask 5.1 : Créer `templates/workflow/partials/submit_evidence_modal.html` :
    - Zone de drag & drop / bouton de sélection de fichiers.
    - Prévisualisation des fichiers sélectionnés (nom, taille, tag).
    - Sélecteur de tag par fichier (dropdown).
    - Textarea pour le commentaire de résolution.
    - Indicateur de progression (optionnel, UX).
    - Style cohérent avec les modales existantes (assignation, délégation).
  - [ ] Subtask 5.2 : Modifier `templates/workflow/recommendation_detail.html` :
    - Ajouter un bouton "Soumettre Preuves" dans la barre d'actions :
      - Visible uniquement si `status == 'IN_PROGRESS'` ET (`user == recommendation.assigned_etp` OU DM Porteur).
    - Ajouter le conteneur Alpine.js pour la modale (`x-data="{ submitEvidenceModalOpen: false }"`).
    - Ajouter le template x-teleport pour la modale HTMX.
  - [ ] Subtask 5.3 : Afficher dans la section "Preuves" de la page détail :
    - Liste des soumissions existantes avec leurs fichiers.
    - Pour chaque fichier : nom original, taille formatée, tag, date d'upload.
    - Lien de téléchargement sécurisé (via une vue Django qui contrôle l'accès RBAC).

- [ ] Task 6 : Backend — Vue de téléchargement sécurisé des fichiers
  - [ ] Subtask 6.1 : Créer `EvidenceFileDownloadView` dans `apps/workflow/views.py` :
    - Sert le fichier via `FileResponse` ou `StreamingHttpResponse`.
    - Contrôle d'accès RBAC : seuls l'ETP assigné, le DM assigné, les Auditeurs et les superusers peuvent télécharger.
    - **Critique** : les fichiers ne sont **pas** servis directement par Nginx (bloc `deny all` sur `/media/`) mais uniquement via cette vue Django (architecture ADR-02).
  - [ ] Subtask 6.2 : Ajouter l'URL `recommandations/<uuid:pk>/evidence/<uuid:file_id>/download/` dans `apps/workflow/urls.py`.

- [ ] Task 7 : Tests
  - [ ] Subtask 7.1 : **Test upload valide** : `test_etp_can_submit_evidence` (ETP assigné uploade un fichier PDF valide + commentaire → statut passe à PENDING_DM_REVIEW).
  - [ ] Subtask 7.2 : **Test Magic Bytes** : `test_magic_bytes_rejects_xlsm` (fichier avec extension .xlsx mais contenu XLSM → rejeté) et `test_magic_bytes_rejects_invalid_file` (fichier texte renommé en .pdf → rejeté).
  - [ ] Subtask 7.3 : **Test taille et quota** : `test_file_over_6mb_rejected` (fichier > 6 Mo rejeté) et `test_total_quota_over_20mb_rejected` (quota global > 20 Mo rejeté).
  - [ ] Subtask 7.4 : **Test immutabilité** : `test_evidence_file_cannot_be_deleted` (appel à `EvidenceFile.delete()` → raise ProtectedError ou ValueError).
  - [ ] Subtask 7.5 : **Test RBAC** : `test_non_assigned_user_cannot_submit_evidence` (403 Forbidden pour un ETP non assigné, un Audit, un DG).
  - [ ] Subtask 7.6 : **Test DM Porteur** : `test_dm_porteur_can_submit_evidence` (DM Porteur peut soumettre des preuves si `assigned_etp` est null).
  - [ ] Subtask 7.7 : **Test Audit Log** : `test_evidence_submission_traced_in_audit_log` (vérifier qu'une entrée TRANSITION est créée).
  - [ ] Subtask 7.8 : **Test téléchargement sécurisé** : `test_download_evidence_rbac` (seuls les utilisateurs autorisés peuvent télécharger un fichier).
  - [ ] Subtask 7.9 : **Test SHA-256** : `test_sha256_hash_computed_on_upload` (vérifier que le hash est bien calculé et stocké).
  - [ ] Subtask 7.10 : **Test FSM négatif** : `test_cannot_submit_evidence_when_not_in_progress` (rejet si statut != IN_PROGRESS).

## Dev Notes

- **Architecture & Constraints:**
  - Conserver le pattern HackSoft : selector → service → view.
  - La transition FSM `submit_evidence` s'ajoute à `start_processing` (Story 3.2) comme nouvelle transition sortante depuis `IN_PROGRESS`.
  - Le volume Docker `/media/` est monté mais protégé par Nginx (`deny all` sur `/media/`). Tout téléchargement DOIT passer par une vue Django contrôlée.
  - `FILE_UPLOAD_MAX_MEMORY_SIZE = 6 Mo` est configuré dans `base.py:214`. Les fichiers > 6 Mo seront écrits en fichier temporaire par Django, ce qui est le comportement souhaité pour les gros uploads. La validation applicative doit vérifier la taille réelle (max 15 Mo) séparément.
  - Le modèle `EvidenceSubmission` permet de regrouper les fichiers d'une même soumission et de supporter la re-soumission après rejet (Story 3.4).
  - L'`AuditLog` existant (`apps/audit/models.py`) a déjà l'action `TRANSITION` — pas besoin de nouveau type.
  - Le sélecteur `get_recommendations_for_user` filtre déjà par `assigned_etp=user` pour les ETP (Story 3.1).
  - Le `DM Porteur` est le cas où `assigned_etp is None` et `status == IN_PROGRESS` — le DM agit directement.

- **Source tree components to touch:**
  - `code/apps/workflow/models.py` (ajouter `EvidenceSubmission`, `EvidenceFile`, transition FSM `submit_evidence`)
  - `code/apps/workflow/validators.py` **(nouveau fichier)** — validators magic bytes, taille, SHA-256
  - `code/apps/workflow/services.py` (ajouter `submit_evidence_for_recommendation`)
  - `code/apps/workflow/selectors.py` (ajouter éventuellement `get_evidence_for_recommendation`)
  - `code/apps/workflow/forms.py` (ajouter `EvidenceUploadForm`)
  - `code/apps/workflow/views.py` (ajouter `RecommendationSubmitEvidenceView`, `EvidenceFileDownloadView`)
  - `code/apps/workflow/urls.py` (ajouter 2 routes : soumission + téléchargement)
  - `code/templates/workflow/partials/submit_evidence_modal.html` **(nouveau fichier)**
  - `code/templates/workflow/recommendation_detail.html` (ajouter bouton + modale + section preuves)
  - `code/apps/workflow/tests/test_views.py` (ajouter tests de soumission)

- **Magic Bytes à implémenter (NFR-SEC-04):**
  | Format | Signature (hex)            | Notes |
  |--------|----------------------------|-------|
  | PDF    | `25 50 44 46`              | `%PDF` |
  | DOCX   | `50 4B 03 04`              | ZIP header, vérifier `[Content_Types].xml` pour word |
  | XLSX   | `50 4B 03 04`              | ZIP header, vérifier `[Content_Types].xml` pour spreadsheet |
  | XLSM   | `50 4B 03 04`              | **INTERDIRE** — même ZIP mais avec `vnd.ms-excel.sheet.macroEnabled` dans Content_Types |
  | JPEG   | `FF D8 FF`                 | |
  | PNG    | `89 50 4E 47 0D 0A 1A 0A`  | 8 octets de signature |

- **Stockage fichier :**
  - Upload path : `evidence/{recommendation_uuid}/{YYYY}/{MM}/{uuid_filename}.ext`
  - Le nom du fichier physique doit être un UUID (pas le nom original) pour éviter les collisions et les injections de chemin.
  - Le nom original est conservé dans le champ `original_filename` du modèle.

### Project Structure Notes

- Alignement avec la structure HackSoft existante : models → selectors → services → views → forms → templates.
- Le fichier `validators.py` est un nouveau module, mais cohérent avec les conventions Django (cf. `django.core.validators`).
- Les templates de modales suivent le pattern établi dans les stories 2.5 (assign) et 3.2 (delegate).

### Previous Story Intelligence (Story 3.2)

- **Pattern HTMX Modale validé** : La modale HTMX avec `hx-get` + `hx-target` + Alpine.js `x-teleport` fonctionne bien. Réutiliser exactement le même pattern pour la modale de soumission.
- **Pattern Service Layer validé** : `select_for_update()` + vérification statut + transition FSM + AuditLog + `HX-Refresh: true` est le pattern standard. Le service `submit_evidence_for_recommendation` doit suivre ce schéma.
- **Bug résolu Story 3.2** : Le sélecteur `get_available_etps_for_department` utilisait un filtre strict par département et non hiérarchique. Corrigé avec `_get_department_and_descendants_ids()`. Ce correctif n'impacte pas la Story 3.3.
- **Bug résolu Story 3.2** : La validation backend dans `services.py` faisait un `etp.department_id != recommendation.department_id` au lieu d'utiliser la hiérarchie. Corrigé pour inclure les descendants. Même logique corrigée.
- **Tests** : 103 tests passent actuellement pour `apps.workflow`. Les nouveaux tests doivent s'intégrer sans régression.

### Git Intelligence

- Dernier commit pertinent : `126c471 feat(workflow): résolution complète de l'epics 2 (tests FSM, exceptions, UI) et réparation du background login`
- Les Stories 3.1 et 3.2 sont implémentées mais pas encore commitées (27 fichiers modifiés, 1171 insertions).
- Pattern de commit : `feat(workflow): description`.

### References

- [Source: epics.md#Story 3.3] — Définition de la story et critères d'acceptation.
- [Source: epics.md#FR15] — Upload de preuves (Draft) avec formats stricts, limite 6 Mo.
- [Source: epics.md#FR16] — Soumission des preuves au DM avec commentaire justificatif (passage en PENDING_DM_REVIEW).
- [Source: epics.md#FR18] — Re-soumission après rejet (pris en compte via le modèle `EvidenceSubmission` multi-entrées).
- [Source: epics.md#FR19] — Exemption commentaire si PV de Recette (le tag `PV_RECETTE` est posé ici, exploité dans Story 3.5).
- [Source: epics.md#NFR-SEC-04] — Check Magic Bytes strict, format macros XLSM interdits.
- [Source: epics.md#NFR-SCA-01] — Max 6 Mo unitaire / 20 Mo global par recommandation.
- [Architecture v2] — django-fsm pour les transitions d'état, HTMX pour les interactions UI.
- [Architecture v2] — Nginx `deny all` sur `/media/`, téléchargement via vue Django (ADR-02).
- [Settings base.py:214] — `FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024` (6 Mo).
- [Settings base.py:213] — `MEDIA_ROOT = BASE_DIR / "media"`.
- [Nginx nginx.conf:35-38] — `location /media/ { deny all; return 403; }`.
- [Story 3.2] — Pattern modale HTMX, service layer, FSM transitions.
- [PRD v2] — FR15, FR16, NFR-SEC-04, NFR-SCA-01.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
