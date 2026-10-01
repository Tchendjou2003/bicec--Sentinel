# Story 6.7: Portail Audit Externe — Consultation + Export ZIP

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **Auditeur Externe (COBAC, CAC, Consultant)**,
I want **accéder à mon portail dédié en lecture seule pour consulter les recommandations rattachées à mes missions actives, visualiser la timeline d'audit et télécharger d'un clic toutes les preuves en archive ZIP**,
so that **je puisse réaliser mes contrôles réglementaires et archiver les données justificatives via mon propre système, sans risque d'altérer la base de production (FR25, FR26).**

## Acceptance Criteria

1. **Given** un compte IT avec `role=EXT` sans mission active,
   **When** il se connecte,
   **Then** il voit une page d'attente sobre indiquant *"Aucune mission d'audit n'est actuellement ouverte pour votre compte"*.
2. **Given** un auditeur externe rattaché à une ou plusieurs `ExternalMission` avec `status=ACTIVE`,
   **When** il accède à son portail,
   **Then** il voit la liste des recommandations regroupées par mission, sans aucun bouton d'action (pas de modification, suppression, assignation, FSM).
3. **Given** une recommandation dans le périmètre d'une mission,
   **When** l'auditeur clique sur une ligne du tableau,
   **Then** il accède à une page de détail en lecture seule affichant la description, les observations, la timeline AuditLog et les preuves acceptées (fichiers listés avec nom, taille, date).
4. **Given** une recommandation avec preuves acceptées,
   **When** l'auditeur clique sur *"Télécharger l'archive ZIP"*,
   **Then** le système compile en mémoire (`BytesIO`) toutes les `EvidenceFile` de statut `ACCEPTED` dans un ZIP nommé `{reference}-Preuves.zip` et le sert via `FileResponse`. La génération ne dépasse pas 5 secondes (NFR-PERF-04).
5. **Given** une mission dont le `status` passe à `CLOSED` ou dont la `end_date` est dépassée,
   **When** l'auditeur tente d'accéder au portail,
   **Then** le selector renvoie un QuerySet vide pour cette mission et les recommandations associées disparaissent du tableau.
6. **Given** un accès ou un téléchargement ZIP par l'auditeur externe,
   **When** l'action se produit,
   **Then** une entrée `AuditLog` est créée (`action=ACCESS` ou `action=EXPORT`) traçant qui a consulté ou téléchargé quoi et quand.

---

## Analyse de l'Existant

### Modèle `ExternalMission` — déjà existant mais incomplet

Le modèle existe dans [users/models.py L631-725](file:///d:/bicec--Sentinel/code/apps/users/models.py#L631-L725).
Le code lui-même contient le TODO : *"La relation M2M avec les recommandations sera implémentée dans l'Epic 2 lorsque l'app workflow sera créée."*

**Éléments existants :**
| Champ | Type | Commentaire |
|---|---|---|
| `id` | UUID | ✅ OK |
| `auditor` | FK → User (EXT) | ⚠️ FK simple → 1 auditeur/mission. Doit devenir M2M. |
| `organization` | CharField(100) | ⚠️ Champ libre. Doit devenir un choix structuré (type). |
| `scope_description` | TextField | ✅ OK |
| `start_date` | DateField | ✅ OK |
| `end_date` | DateField (nullable) | ✅ OK |
| `is_active` | BooleanField | ⚠️ Trop binaire. Doit être remplacé par un `status` à 3 états. |
| `created_at` / `updated_at` | DateTimeField | ✅ OK |

**Éléments manquants à ajouter :**
| Champ | Type | Raison |
|---|---|---|
| `name` | CharField(200) | Nom humain de la campagne ("Contrôle COBAC 2026") |
| `type` | TextChoices | COBAC / CAC / INSPECTION_GROUPE / CONSULTANT |
| `status` | TextChoices | PREPARATION / ACTIVE / CLOSED (remplace `is_active`) |
| `auditors` | M2M → User | Remplace la FK `auditor` pour permettre plusieurs auditeurs/mission |
| `recommendations` | M2M → Recommendation | Le lien périmètre mission ↔ recommandations |
| `created_by` | FK → User | Qui a créé la mission (Audit Interne) |
| `approved_by` | FK → User (nullable) | Qui a validé l'ouverture de la mission |

### Admin Django — existant mais non pertinent pour l'Audit
L'admin `ExternalMissionAdmin` dans [users/admin.py L123-158](file:///d:/bicec--Sentinel/code/apps/users/admin.py#L123-L158) est réservé aux superusers IT.
L'Audit Interne gère les missions via **l'interface applicative HTMX**, pas le Django Admin.

### Shell Externe — existant et opérationnel
Le layout [external_shell.html](file:///d:/bicec--Sentinel/code/templates/layouts/external_shell.html) est prêt : topbar avec badge "Lecture seule", nom de l'utilisateur, bouton de déconnexion.

### Dashboard Externe — placeholder statique
Le template [external/dashboard.html](file:///d:/bicec--Sentinel/code/templates/external/dashboard.html) n'affiche qu'un message d'attente. Il faut le remplacer.

### Selector — Fail-Closed
Dans [selectors.py L100](file:///d:/bicec--Sentinel/code/apps/workflow/selectors.py#L100), le rôle EXT tombe dans le `else: return qs.none()`. Il faut ajouter un branchement dédié.

### Modèle des preuves — prêt
- `EvidenceSubmission` : [models.py L697](file:///d:/bicec--Sentinel/code/apps/workflow/models.py#L697) — contient le `status` (ACCEPTED = preuves validées).
- `EvidenceFile` : [models.py L817](file:///d:/bicec--Sentinel/code/apps/workflow/models.py#L817) — contient le `file` (FileField), `original_filename`, `file_size`, `sha256_hash`.

---

## Tasks / Subtasks

### Task 0: Découplage du Provisioning IT (Rôle EXT autonome)
- [x] 0.1 — Modifier `UserProvisioningRequestForm` dans `forms.py` : supprimer complètement tous les champs `mission_*` du formulaire, car l'IT ne s'occupe plus des missions pour le rôle `EXT`.
- [x] 0.2 — Modifier `UserProvisioningRequest` dans `models.py` : supprimer complètement les champs `mission_organization`, `mission_scope_description`, `mission_start_date`, `mission_end_date`. Créer une migration pour supprimer ces colonnes en base de données. L'IT crée le compte `EXT` sans mission.
- [x] 0.3 — Modifier `approve_provisioning_request` dans [services.py](file:///d:/bicec--Sentinel/code/apps/users/services.py) : supprimer la création automatique d'une instance `ExternalMission` lors de l'approbation d'un compte `EXT`.
- [x] 0.4 — Adapter et corriger les tests unitaires dans [test_provisioning.py](file:///d:/bicec--Sentinel/code/apps/users/tests/test_provisioning.py) pour refléter le découplage (les tests de provisioning EXT doivent s'assurer que le compte est créé avec le rôle `EXT` mais sans mission associée).

### Task 1: Évolution du modèle `ExternalMission` (AC: #2, #5)
- [x] 1.1 — Ajouter le champ `name` (CharField, 200).
- [x] 1.2 — Créer les `TextChoices` pour `type` (COBAC, CAC, INSPECTION_GROUPE, CONSULTANT).
- [x] 1.3 — Remplacer `is_active` par un champ `status` (TextChoices : PREPARATION, ACTIVE, CLOSED).
- [x] 1.4 — Remplacer la FK `auditor` par un M2M `auditors` (`ManyToManyField → User`, `limit_choices_to={"role": "EXT"}`). **Migration** : données existantes → créer la M2M, migrer la FK, supprimer l'ancien champ.
- [x] 1.5 — Ajouter le M2M `recommendations` (`ManyToManyField → Recommendation`, `blank=True`).
- [x] 1.6 — Ajouter `created_by` (FK → User, PROTECT) et `approved_by` (FK → User, nullable, SET_NULL).
- [x] 1.7 — Mettre à jour l'`ExternalMissionAdmin` pour refléter les nouveaux champs.
- [x] 1.8 — Générer et appliquer les migrations Django.

### Task 2: Interface Audit — Gestion des Missions (AC: #2)
- [x] 2.1 — Créer la vue et le template **`missions_list.html`** dans l'espace Audit (accessible via la sidebar `app_shell.html`).
- [x] 2.2 — Créer le formulaire HTMX de création/édition de mission (slide-over, cohérent avec le pattern existant).
- [x] 2.3 — Créer le sélecteur de recommandations à rattacher (TomSelect M2M, filtre par statut `CLOSED_RESOLVED`).
- [x] 2.4 — Créer le sélecteur d'auditeurs à rattacher (TomSelect M2M, filtre `role=EXT`).
- [x] 2.5 — Ajouter le bouton d'action pour passer la mission en `ACTIVE` ou `CLOSED`.

### Task 3: Ouverture dynamique des droits d'accès (AC: #1, #2, #5)
- [x] 3.1 — Modifier `get_recommendations_for_user` dans [selectors.py](file:///d:/bicec--Sentinel/code/apps/workflow/selectors.py) : ajouter la branche `EXT` qui filtre par `ExternalMission.status=ACTIVE` + `auditors__in=[user]` + `end_date >= today OR end_date IS NULL`.
- [x] 3.1 — Modifier `get_recommendations_for_user` dans [selectors.py](file:///d:/bicec--Sentinel/code/apps/workflow/selectors.py) : ajouter la branche `EXT`.
- [x] 3.2 — Mettre à jour `WorkflowAccessMixin` et `RecommendationAccessService` dans [mixins.py](file:///d:/bicec--Sentinel/code/apps/users/mixins.py) et [services.py](file:///d:/bicec--Sentinel/code/apps/workflow/services.py).
- [x] 3.3 — Créer une route `/audit/externe/waiting/`.

### Task 4: Interface Externe — Dashboard (AC: #1, #2, #3)
- [x] 4.1 — Refondre `external/dashboard.html`.
- [x] 4.2 — Créer le partial `external/partials/mission_card.html`.
- [x] 4.3 — Créer le partial `external/partials/recommendation_table_ext.html`.

### Task 5: Interface Externe — Détail Recommandation en Lecture Seule (AC: #3)
- [x] 5.1 — Créer le template `external/recommendation_detail_ext.html` : version expurgée avec ZÉRO bouton d'action FSM.
- [x] 5.2 — Afficher les cartes : Contexte Mission (C1 simplifié), Recommandation (C4), Observations (C5).
- [x] 5.3 — Afficher la colonne droite : Avancement (C6), Intégrité/Sceau HMAC (C7), Timeline AuditLog.
- [x] 5.4 — Afficher la section Preuves Acceptées (liste des fichiers avec nom, taille, date, bouton de téléchargement individuel).
- [x] 5.5 — Ajouter le bouton "Télécharger l'archive ZIP" proéminent en haut de la section Preuves.

### Task 6: Export ZIP (AC: #4)
- [x] 6.1 — Créer le service `generate_evidence_zip(recommendation_id) → BytesIO` dans `apps/audit/services.py` : itérer sur les `EvidenceFile` des soumissions `ACCEPTED`, ajouter chaque fichier dans le ZIP avec son `original_filename`.
- [x] 6.2 — Implémenter `RecommendationEvidenceZipExportView` dans `apps/workflow/views.py` (ou `apps/audit/views.py`) : appeler le service et renvoyer un `FileResponse(as_attachment=True)`.
- [x] 6.3 — S'assurer que le téléchargement déclenche un enregistrement dans l'AuditLog.e ZIP (si 2 fichiers ont le même `original_filename`, préfixer par un compteur : `1_rapport.pdf`, `2_rapport.pdf`).
- [ ] 6.4 — Créer la vue de proxy de téléchargement individuel de fichier (contrôle d'accès Django avant de servir le fichier depuis le filesystem protégé par Nginx).

### Task 7: Traçabilité (AC: #6)
- [x] 7.1 — S'assurer que `AuditLog.objects.create` est appelé lors de l'export ZIP massif.
- [x] 7.2 — Mettre à jour `AuditLogAdmin` dans `apps/audit/admin.py` pour s'assurer que l'action `EXPORT_ZIP` est bien tracée.

---

## UI/UX — Spécifications Visuelles

### Écran 1 : État d'attente (aucune mission active)

```
┌──────────────────────────────────────────────────────────────┐
│ [S] Sentinel          Espace Auditeur Externe   🔒 Lecture   │
│                       seule   cobac.jean  Déconnexion        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│              ┌────────────────────────┐                      │
│              │    🔍  (icône loupe)    │                      │
│              └────────────────────────┘                      │
│                                                              │
│        Aucune mission d'audit active                         │
│                                                              │
│    Votre compte est configuré. Les missions                  │
│    d'audit vous seront attribuées par la                     │
│    Direction de l'Audit Interne.                             │
│                                                              │
│    Contactez l'Audit Interne si vous estimez                 │
│    que votre mission devrait être ouverte.                   │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Sentinel — Plateforme de suivi des recommandations BICEC    │
└──────────────────────────────────────────────────────────────┘
```

**Design tokens :** Réutiliser le pattern `empty-state` de [recommendation_table.html L101-124](file:///d:/bicec--Sentinel/code/templates/workflow/partials/recommendation_table.html#L101-L124) — icône dans un cercle `bg-sentinel-orange-light`, texte centré, pas de bouton d'action.

---

### Écran 2 : Dashboard avec missions actives

```
┌──────────────────────────────────────────────────────────────┐
│ [S] Sentinel          Espace Auditeur Externe   🔒 cobac.j   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Bienvenue, Jean Dupont                                      │
│  Vous avez 2 mission(s) active(s).                           │
│                                                              │
│  ┌── Carte Mission ─────────────────────────────────────┐    │
│  │ 🏛 Contrôle COBAC 2026                    COBAC      │    │
│  │ Périmètre : Audit des procédures de crédit           │    │
│  │ Du 01/06/2026 au 30/09/2026                          │    │
│  │ 12 recommandations rattachées                        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌── Barre de recherche ────────────────────────────────┐    │
│  │ 🔍  Rechercher par référence ou mission...           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌── Tableau ───────────────────────────────────────────┐    │
│  │ Réf.     │ Mission │ Statut │ Priorité │ Échéance │ ⬇ │   │
│  │ RECO-001 │ Crédit  │ CLOSED │ CRITIQUE │ 15/03/26 │ 📦│   │
│  │ RECO-002 │ Crédit  │ CLOSED │ HAUTE    │ 20/04/26 │ 📦│   │
│  │ ...      │         │        │          │          │   │   │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  Page 1 sur 2 — 12 recommandations                           │
└──────────────────────────────────────────────────────────────┘
```

**Composant `mission_card.html` :**
- Utilise la carte `bg-white border border-border-subtle rounded-xl shadow-premium-sm` (même design que la carte C1 de `recommendation_detail.html`).
- Badge de type coloré : `COBAC` → bleu institutionnel, `CAC` → violet, `INSPECTION_GROUPE` → ambre, `CONSULTANT` → gris.
- Compteur de recommandations rattachées affiché en bas de la carte.
- Si l'auditeur a plusieurs missions, afficher une carte par mission avec un accordéon ou un empilement vertical.

**Tableau `recommendation_table_ext.html` :**
- Colonnes simplifiées : **Réf.**, **Mission** (troncature à 20 chars), **Statut** (badge), **Priorité** (badge), **Échéance** (icône alerte si OVERDUE), **Direction**, **⬇ ZIP** (icône de téléchargement).
- **Pas de colonne DM assigné** (information interne non pertinente pour l'externe).
- **Pas de menu contextuel** (...), **pas de bouton Créer/Importer**.
- Clic sur la ligne → page de détail. Clic sur l'icône ZIP → téléchargement direct.
- Pattern de style identique à [recommendation_table.html](file:///d:/bicec--Sentinel/code/templates/workflow/partials/recommendation_table.html) : hover `bg-sentinel-orange-light`, police mono pour la référence.

---

### Écran 3 : Détail Recommandation (lecture seule)

```
┌──────────────────────────────────────────────────────────────┐
│ ← Retour aux recommandations                                │
│                                                              │
│  ┌─ Bandeau lecture seule ──────────────────────────────┐    │
│  │ ⚠ Vous consultez cette recommandation en lecture     │    │
│  │   seule dans le cadre de la mission "Contrôle COBAC" │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ C1 : Carte Contexte (identique interne, sans boutons)┐   │
│  │ RECO-2026-0089  │ CLOSED_RESOLVED │ CRITIQUE           │   │
│  │ "Revoir le processus d'habilitation des caissiers"     │   │
│  │ Direction : Réseau  │ Porteur : M. Kamga │ 15/03/2026  │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── 60% ──────────────────────┐ ┌─── 40% ────────────┐    │
│  │ C4 : Recommandation          │ │ C6 : Avancement     │    │
│  │ (description, observations)  │ │ ████████████ 100%   │    │
│  │                              │ │                     │    │
│  │ C5 : Observations de la      │ │ C7 : Intégrité      │    │
│  │ mission                      │ │ ✅ Sceau HMAC       │    │
│  │                              │ │    vérifié           │    │
│  │ ── Preuves Acceptées ──      │ │ 0a3f…9c1d           │    │
│  │ ┌───────────────────────┐    │ │                     │    │
│  │ │ 📦 Télécharger le ZIP │    │ │ ── Timeline ──      │    │
│  │ │    des preuves (3)    │    │ │ 15/03 Clôturé       │    │
│  │ └───────────────────────┘    │ │ 10/03 Preuve OK     │    │
│  │                              │ │ 08/03 Soumission    │    │
│  │ 📄 PV_Recette.pdf  1.2 Mo   │ │ 01/02 Assigné       │    │
│  │ 📄 Capture.png     340 Ko   │ │ 15/01 Créé          │    │
│  │                              │ │                     │    │
│  └──────────────────────────────┘ └─────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

**Principes UI :**
- **Layout 60/40** identique à `recommendation_detail.html` (split grid `1fr 320px`).
- **Bandeau contextuel** en haut : fond `bg-warning/5`, bordure `border-warning/20`, texte indiquant la mission et le mode lecture seule. Pattern existant dans [external/dashboard.html L44-59](file:///d:/bicec--Sentinel/code/templates/external/dashboard.html#L44-L59).
- **Carte Contexte (C1)** : identique au design existant MAIS sans aucun `{% if can_close_by_audit %}`, `{% if can_submit_evidence %}`, etc. Zéro bouton d'action.
- **Bouton ZIP** : composant proéminent, pleine largeur de la section preuves, utilisant la classe `btn btn-primary` avec une icône d'archive. Visible uniquement si la recommandation a au moins 1 fichier `ACCEPTED`.
- **Liste des fichiers** : chaque fichier affiché en tant que carte compacte (nom original, taille formatée via `file_size_display`, date de dépôt, bouton "Télécharger" individuel).
- **Timeline** : réutiliser le partial existant `audit_log_drawer.html` intégralement mais en mode embarqué (pas de drawer), seulement les 5 dernières entrées + un lien "Voir tout".

---

## Dev Notes

### Découplage et Cycle de vie du compte EXT
- **Séparation Maker/Checker IT & Métier** : Le rôle `EXT` est attribué par l'IT lors de la création technique du compte (Maker/Checker de provisioning). Ce compte naît sans aucune mission. Ses accès sont entièrement régis par les missions créées et gérées par l'Audit Interne. Les champs `mission_*` du formulaire IT deviennent optionnels et n'auto-génèrent plus de mission.
- **Révocation automatique** : Le sélecteur de droits interroge dynamiquement `end_date` et `status` pour interdire toute lecture dès que la mission se termine ou est clôturée.

### Modèle de données
- **Migration critique :** La transformation FK `auditor` → M2M `auditors` nécessite une migration en 3 étapes :
  1. Ajouter le M2M `auditors` (nouveau champ).
  2. Data migration : copier chaque `auditor` existant dans la table M2M.
  3. Supprimer l'ancienne FK `auditor`.
- Le champ `is_active` doit être supprimé au profit de `status`. Data migration : `is_active=True` → `status=ACTIVE`, `is_active=False` → `status=CLOSED`.

### Performance ZIP
- Utiliser `FileResponse` avec un buffer `BytesIO`. **Ne pas** utiliser `StreamingHttpResponse` pour un ZIP car `zipfile` a besoin de seeker pour écrire le Central Directory.
- Taille max estimée : 5 fichiers × 15 Mo = 75 Mo max par recommandation. Cela tient en mémoire.

### Sécurité
- **Téléchargement individuel de fichier :** Les fichiers sont stockés dans `/media/evidence/` protégé par Nginx (`deny all`). Créer une vue Django de proxy (lire le fichier avec `open(path, 'rb')` et le servir via `FileResponse`) avec vérification que l'utilisateur est bien rattaché à une mission active couvrant cette recommandation.
- **Aucune mutation FSM** : les vues EXT ne doivent accepter que `GET`. Aucun formulaire POST ne doit exister dans les templates externes.
- **CSRF** : le seul `POST` autorisé est le logout (déjà dans le shell externe).

### Traçabilité
- Ne pas créer de nouveau type d'action `AuditLog` via migration. Utiliser le champ `description` pour stocker le contexte (nom de la mission, username de l'auditeur). L'action peut être `UPDATE` avec un `description` explicite, ou un nouveau type `ACCESS`/`EXPORT` ajouté aux `TextChoices` existants.

### Structure des fichiers
- **Vues :** Créer `code/apps/external/views.py` (ou un package) pour isoler du monolithe `workflow/views.py`.
- **URLs :** Enregistrer les routes sous le namespace `external:` (ex: `external:dashboard`, `external:recommendation-detail`, `external:evidence-zip`).
- **Templates :** `code/templates/external/dashboard.html`, `external/recommendation_detail_ext.html`, `external/partials/mission_card.html`, `external/partials/recommendation_table_ext.html`.
- **Services :** `code/apps/audit/services.py` ou `code/apps/audit/export_services.py` pour `generate_evidence_zip()`.

### Project Structure Notes

- Le design system de Sentinel utilise les classes : `bg-white`, `border-border-subtle`, `rounded-xl`, `shadow-premium-sm`, `text-text-primary`, `text-text-body`, `text-text-faint`, `sentinel-orange`, `sentinel-orange-light`, `surface-warm`, etc.
- Les badges de statut et de priorité sont des composants partagés : `components/status_badge.html` et `components/priority_badge.html`.
- Le pattern des tableaux avec hover orange est standard (cf. `recommendation_table.html`).

### References

- [ExternalMission model](file:///d:/bicec--Sentinel/code/apps/users/models.py#L631-L725)
- [ExternalMission admin](file:///d:/bicec--Sentinel/code/apps/users/admin.py#L123-L158)
- [external_shell.html](file:///d:/bicec--Sentinel/code/templates/layouts/external_shell.html)
- [external/dashboard.html](file:///d:/bicec--Sentinel/code/templates/external/dashboard.html)
- [selectors.py — get_recommendations_for_user](file:///d:/bicec--Sentinel/code/apps/workflow/selectors.py#L54-L110)
- [recommendation_table.html](file:///d:/bicec--Sentinel/code/templates/workflow/partials/recommendation_table.html)
- [recommendation_detail.html](file:///d:/bicec--Sentinel/code/templates/workflow/recommendation_detail.html)
- [EvidenceSubmission model](file:///d:/bicec--Sentinel/code/apps/workflow/models.py#L697-L809)
- [EvidenceFile model](file:///d:/bicec--Sentinel/code/apps/workflow/models.py#L817-L898)
- Epic 5 Story 5.2 (epics.md) — FR25, FR26
- Sprint Status — Story 6.7

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
