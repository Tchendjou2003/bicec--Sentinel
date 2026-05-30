---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments: ['prd-v2.md', 'architecture-v2.md']
---

# bicec--Sentinel - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for bicec--Sentinel, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

- **FR1:** Les utilisateurs s'authentifient via des identifiants locaux sécurisés (Django Auth MVP).
- **FR2:** Les Auditeurs Externes s'authentifient via identifiants locaux spécifiques.
- **FR3 (ADR-10):** Le Directeur Audit Interne (ou auditeur délégué `is_audit_admin`) attribue les rôles métiers et périmètres aux comptes créés par l'IT via interface dédiée.
- **FR4:** Gestion des intérims tracée (l'intérimaire agit *au nom de* l'absent, tracé dans l'Audit Log).
- **FR5:** Création manuelle unitaire d'une recommandation par l'Audit.
- **FR6:** Soft Delete possible en état DRAFT (pré-assignation) par l'Audit.
- **FR6b:** État DRAFT lors de la création avant assignation à un DM.
- **FR7:** Création de recommandations en masse (Bulk Create).
- **FR8:** Import historique exclusif à l'Audit Interne via template normalisé.
- **FR9:** Import transactionnel atomique (tout ou rien) marquant les recos en ASSIGNED + IMPORTED. Conservation stricte de la date de création originale (Excel) pour le calcul du vieillissement.
- **FR10:** Auto-assignation temporaire par l'Audit pour triage.
- **FR11:** Assignation définitive à un Directeur Métier cible.
- **FR12:** Le DM peut déléguer à un ETP ou traiter personnellement (DM Porteur).
- **FR13:** Le DM peut demander un report d'échéance justifié.
- **FR14:** L'Audit approuve ou rejette les demandes de report.
- **FR15:** Upload de preuves (Draft) avec formats stricts, limite 15 Mo.
- **FR16:** Soumission des preuves au DM avec commentaire justificatif (passage en PENDING_DM_REVIEW).
- **FR17:** Le DM valide ou rejette avec motif.
- **FR18:** L'ETP peut re-soumettre après rejet.
- **FR19:** Exemption de commentaire si un "PV de Recette" est uploadé par le DM.
- **FR20:** Clôture définitive par l'Audit Interne (CLOSED_RESOLVED).
- **FR21:** Bascule automatique en retard (OVERDUE) à échéance dépassée.
- **FR22:** Alertes journalières pour les retards de priorité "Critique".
- **FR23:** Cycle nocturne (digest consolidé par utilisateur) pour les retards globaux et alertes proactives à J-7.
- **FR24:** Calcul du Sceau cryptographique final (HMAC-SHA256) à la clôture.
- **FR25:** Archiving chronologique de toutes les preuves et Audit Trail.
- **FR26:** Téléchargement d'archive ZIP pour Auditeurs Externes.
- **FR27:** Frise chronologique détaillée visible par les personnes autorisées.
- **FR28:** Visibilité restreinte par périmètre via RBAC (MVP) / RLS (V2).
- **FR29:** Filtrage avancé des listes de recommandations (source, urgence, vieillissement).
- **FR30:** Indicateurs de couleurs d'urgence sur les tableaux de bord.
- **FR31:** Interface d'impression navigateur CSS @media print pour la DG.
- **FR32:** La DG dispose d'une To-Do list de supervision de son périmètre.
- **FR33:** La DG peut soumettre directement des preuves (DM Porteur élargi).
- **FR34:** La DG peut demander un report d'échéance.
- **FR35 (ADR-10):** Le RSSI/Support IT paramètre l'organigramme (Directions, Services, Agences) et crée les comptes comme des « coquilles vides » (identité technique sans rôle). Il ne peut **pas** attribuer ou modifier les rôles métiers.
- **FR36 (ADR-10):** Le Directeur Audit Interne peut déléguer la permission d'administration des comptes (`is_audit_admin`) à d'autres auditeurs internes. Délégation tracée dans l'Audit Log.
- **FR37 (ADR-10):** Un compte sans rôle métier attribué affiche une page « en attente d'activation » et n'a zéro accès métier.

### NonFunctional Requirements

- **NFR-SEC-01:** Trafic externe HTTPS TLS 1.2+ obligatoire.
- **NFR-SEC-02:** Timeout session après 30 minutes d'inactivité.
- **NFR-SEC-03:** Empreinte HMAC-SHA256 avec variable d'environnement dédiée (`HMAC_SECRET_KEY`) totalement distincte de `SECRET_KEY`.
- **NFR-SEC-04:** Check "Magic Bytes" strict, format macros XLSM interdits.
- **NFR-SEC-05:** Audit Logs "Append Only", durée 12 mois.
- **NFR-PERF-01:** Calcul du RLS/RBAC en < 10ms.
- **NFR-PERF-02:** Rendu UI < 200ms (P95) via HTMX/Vanilla CSS.
- **NFR-PERF-03:** Sceau HMAC généré en < 500ms.
- **NFR-PERF-04:** Archive ZIP streamée in-memory en < 5s par recommandation.
- **NFR-SCA-01:** Max 5 fichiers par preuve / 15 Mo unitaire.
- **NFR-SCA-02:** Volumétrie import initial de 2 000 recos / 9 000 fichiers.
- **NFR-SCA-02b:** L'import asynchrone ne bloque pas l'UI.
- **NFR-SCA-03:** Support nominal pour ~200 utilisateurs concurrents (4 workers Gunicorn suffisent).
- **NFR-REL-01:** Fail-safe RLS strict (0 ligne si contexte manquant).
- **NFR-REL-02:** RPO < 24h via cron SQL dump nocturne.
- **NFR-REL-03:** RTO < 4h via infrastructure automatisée.
- **NFR-REL-04:** Uptime de 99.5% exigé (heures ouvrées).

### Additional Requirements

- **Architecture Choice:** Monolithe SSR Django (pas de SPA/React), interfaces ultra-rapides générées en HTML grâce à HTMX et Alpine.js avec Tailwind.
- **Background Tasks:** Utilisation de Django-Q2 pour le scheduler et le traitement des rapports et tâches asynchrones (Zéro Redis/Celery au MVP).
- **Security:** Le système de fichiers media est protégé (bloc `/media/` en `deny all` par Nginx) et les URL de téléchargements doivent passer par une vue de contrôle d'accès Django.
- **State Machine:** Intégration de `django-fsm` pour piloter la logique d'état des recommandations.
- **Environment Management:** Utilisation de variables d'environnement (`.env`) distinctes pour `DJANGO_SECRET_KEY` et `HMAC_SECRET_KEY`.
- **Infrastructure:** Déploiement On-Premise via Docker Compose avec Nginx proxy_pass. Scripts de chargement de données statiques (collectstatic) dans le processus de lancement.
- **Design:** CSS @media print optimisé, pas de librairie backend PDF complexe type ReportLab/WeasyPrint exigée pour le MVP.

### FR Coverage Map

- FR1: Epic 1 - Identifiants locaux sécurisés MVP
- FR2: Epic 1 - Identifiants locaux externes
- FR3: Epic 1 - Habilitation des comptes via interface dédiée Audit (ADR-10)
- FR4: Epic 6 - Gestion des intérims et audit logs avec impersonnalisation
- FR28: Epic 1 - Restrictions de visibilité via RBAC applicatif MVP (RLS V2)
- FR35: Epic 1 - Pilotage de la structure de l'organigramme (RSSI) + création comptes coquilles vides (ADR-10)
- FR36: Epic 1 - Délégation admin Directeur Audit → Auditeurs (ADR-10)
- FR37: Epic 1 - Page en attente d'activation pour comptes sans rôle (ADR-10)

- FR5: Epic 2 - Création manuelle unitaire
- FR6: Epic 2 - Soft-delete en état DRAFT
- FR6b: Epic 2 - État transitoire DRAFT pré-assignation
- FR7: Différé en V2 (Bulk create)
- FR8: Epic 4 - Droits d'import pour l'Audit uniquement
- FR9: Epic 4 - File import transactionnel atomique + date originale Excel
- FR10: Epic 2 - Auto-assignation pour triage
- FR11: Epic 2 - Assigner à un DM cible

- FR12: Epic 3 - DM délégue à ETP ou devient 'DM Porteur'
- FR13: Epic 3 - Demande de report par DM
- FR14: Epic 3 - Acceptation / Rejet report par l'Audit
- FR15: Epic 3 - Upload draft des preuves avec validation sécurisée adaptative (<15mb)
- FR16: Epic 3 - Soumission de la preuve et déclenchement DM_REVIEW (ETP)
- FR17: Epic 3 - DM valide ou rejette (avec motif)
- FR18: Epic 3 - Re-soumission suite rejet
- FR19: Epic 3 - Exemption commmentaire si PV de Recette fourni
- FR20: Epic 3 - Clôture par l'Audit
- FR21: Epic 3 - Logique métier déclenchant statut OVERDUE au dépassement
- FR24: Epic 3 - Sceau cryptographique HMAC-SHA256 final (clôture) ← fusionné depuis Epic 5
- FR33: Epic 3 - Action de soumission de preuve par la DG
- FR34: Epic 3 - Action de report par la DG

- FR22: Epic 4 - Alertes pour retards critiques (quotidien)
- FR23: Epic 4 - Sommaire hebdo et alertes proactives à J-7

- FR25: Epic 5 - Archiving des preuves validées et Audit Trail append-only
- FR26: Epic 5 - Export d'archive ZIP compilée sur l'environnement externe
- FR27: Epic 5 - Affichage de l'Audit Trail sous forme de timeline de composants UI

- FR29: Epic 6 - Filtres par statuts, ancienneté, et urgence (Aging)
- FR30: Epic 6 - Balises/Couleurs selon l'urgence sur les tableaux
- FR31: Epic 6 - Bouton export "@media print" pour DG
- FR32: Epic 6 - To-Do List de supervision pour la composante exécutive

## Epic List

### Epic 1: Connexion Sécurisée & Gestion des Périmètres
**User Goal:** The Audit Internal team can manage the precise organizational hierarchy and user access, allowing the entire institution to authenticate securely and ensuring each user is isolated in their proper domain.
**FRs covered:** FR1, FR2, FR3, FR28, FR35, FR36, FR37
**Implementation Notes:** Establishes the foundational setup of the Starter Template (Django + PostgreSQL). Focuses heavily on the RBAC architecture to prevent access bleed and configuring custom login sequences. **[ADR-10] : Le Support IT crée les comptes « coquilles vides » (identité technique sans rôle). Le Directeur de l'Audit Interne (ou ses délégués `is_audit_admin=True`) est le seul habilité à attribuer les rôles métiers et périmètres via une interface dédiée.** Le modèle de données de trace (Audit Log) doit être prêt à recevoir ultérieurement les extensions pour la traçabilité des intérims.

#### Story 1.1: Setup du Projet depuis le Starter Template

As a **Tech Lead**,
I want **initialiser le projet Sentinel à partir du Starter Template (Django, PostgreSQL, base Tailwind/HTMX)**,
So that **les développeurs puissent commencer à produire de la valeur sur les briques d'authentification et RBAC.**

**Acceptance Criteria:**

**Given** un dépôt Git vierge et le document d'architecture,
**When** je déploie le starter template,
**Then** le projet tourne localement via Docker Compose.
**And** la base de données PostgreSQL est prête à recevoir les premières tables (Users).
**And** le worker Django-Q2 est configuré et capable d'exécuter des tâches en arrière-plan.

#### Story 1.1b: Mise en place du moteur d'Audit Log (Append-Only)

As a **Système**,
I want **disposer d'un mécanisme d'interception global pour logger chaque action utilisateur**,
So that **chaque changement d'état ou modification sensible soit tracé de manière inaltérable (NFR-SEC-05).**

**Acceptance Criteria:**

**Given** une action utilisateur sur une recommandation ou un profil,
**When** l'objet est sauvegardé,
**Then** une entrée est créée dans la table AuditLog avec l'horodatage, l'utilisateur, l'action et le delta.
**And** le système empêche toute modification ou suppression d'un log existant (Append-Only).

#### Story 1.2: Authentification des Utilisateurs Internes

As a **Utilisateur Interne (Audit, DM, ETP, DG)**,
I want **m'authentifier via des identifiants locaux et gérer ma session**,
So that **je puisse accéder au système de manière sécurisée.**

**Acceptance Criteria:**

**Given** qu'un utilisateur possède un compte actif,
**When** il saisit ses identifiants valides,
**Then** il est connecté et redirigé vers son tableau de bord.
**And** la session est automatiquement fermée après 30 minutes d'inactivité (NFR-SEC-02).

#### Story 1.3: Plateforme des Auditeurs Externes

As a **Auditeur Externe (COBAC)**,
I want **disposer d'un canal d'authentification dédié**,
So that **je puisse vérifier les données en totale isolation de l'environnement interne.**

**Acceptance Criteria:**

**Given** un auditeur externe,
**When** il se connecte,
**Then** son profil est strictement limité à `is_external=True` et ne peut effectuer aucune action d'écriture.

#### Story 1.4: Gestion de l'Organigramme et Création des Comptes (Admin)

As a **Admin (anciennement RSSI/Support IT)**,
I want **créer et structurer l'organigramme (DG, Directions, Sous-Directions, Départements, Services, Directions Régionales, Agences) et créer les comptes utilisateurs comme des « coquilles vides » (identité technique sans rôle métier)**,
So that **le système reflète fidèlement la structure hiérarchique de la banque et que le Directeur de l'Audit Interne puisse attribuer les rôles métiers aux comptes créés (ADR-10).**

**Acceptance Criteria:**

**Given** le tableau de bord Admin,
**When** je crée une arborescence multi-niveaux (DG → DIRECTION → SOUS_DIRECTION → DEPARTEMENT → SERVICE),
**Then** l'arborescence est sauvegardée et disponible pour l'assignation des utilisateurs (FR35).
**And** les types `DG`, `DIRECTION`, `SOUS_DIRECTION`, `DEPARTEMENT`, `SERVICE`, `REGION`, `AGENCE` sont disponibles.
**And** je peux créer une Direction Régionale (type `REGION`) avec des Agences rattachées.
**And** je peux créer un compte utilisateur avec nom, prénom, email et mot de passe temporaire.
**And** le compte créé n'a **aucun rôle métier** (`role=''`) et ne peut accéder à aucune fonctionnalité métier (FR37).
**And** le formulaire d'administration ne me permet **pas** d'attribuer ou modifier un rôle métier (champ masqué/désactivé pour l'Admin).

#### Story 1.5: Assignation des Profils Métiers et Périmètres (Interface Dédiée Audit — ADR-10)

As a **Directeur de l'Audit Interne (ou auditeur délégué `is_audit_admin=True`)**,
I want **attribuer les rôles métiers (Audit, DM, ETP, DG, Externe) et les périmètres de direction aux comptes « coquilles vides » créés par le Support IT, via une interface dédiée distincte du Django Admin**,
So that **le périmètre de visibilité des données (RBAC) s'applique instantanément et que la séparation des fonctions (SoD) soit garantie.**

**Acceptance Criteria:**

**Given** un compte utilisateur « coquille vide » créé par le RSSI (sans rôle métier),
**When** le Directeur Audit lui octroie le rôle "DM" et l'associe à un département via l'interface dédiée d'habilitation,
**Then** cet utilisateur peut désormais se connecter et ne verra que les données du département auquel il est rattaché (FR3, FR28).
**And** le RSSI/Support IT ne peut pas attribuer ou modifier les rôles métiers.
**And** un auditeur interne standard (sans `is_audit_admin`) ne peut pas non plus attribuer de rôles.
**And** l'assignation est tracée dans l'Audit Log avec l'identité du Directeur Audit (ou du délégué).

#### Story 1.7: Délégation des Permissions d'Administration des Comptes (ADR-10)

As a **Directeur de l'Audit Interne**,
I want **déléguer la permission d'administration des comptes (`is_audit_admin`) à d'autres auditeurs internes de mon choix**,
So that **la gestion des habilitations ne repose pas sur une seule personne et que la continuité opérationnelle soit assurée.**

**Acceptance Criteria:**

**Given** le Directeur Audit connecté à l'interface dédiée,
**When** il active le flag `is_audit_admin` sur le profil d'un autre auditeur interne,
**Then** cet auditeur peut désormais attribuer des rôles métiers aux comptes « coquilles vides » (FR36).
**And** la délégation est tracée dans l'Audit Log : « Délégation admin accordée à [Auditeur Y] par [Directeur X] ».
**And** le Directeur Audit peut révoquer la délégation à tout moment.

#### Story 1.8: Page en Attente d'Activation (Compte sans Rôle — ADR-10)

As a **Utilisateur dont le compte vient d'être créé par l'IT**,
I want **voir une page claire m'indiquant que mon compte est en attente d'activation**,
So that **je comprenne que l'Audit Interne doit d'abord m'attribuer un rôle métier avant que je puisse utiliser Sentinel.**

**Acceptance Criteria:**

**Given** un utilisateur connecté dont le champ `role` est `NULL` ou vide,
**When** il accède à n'importe quelle URL de l'application,
**Then** il est redirigé vers une page « Votre compte est en attente d'activation par l'Audit Interne » (FR37).
**And** il ne peut accéder à aucun dashboard, aucune donnée métier, aucune fonctionnalité.
**And** la page affiche un message de contact (ex: « Veuillez contacter le service d'Audit Interne »).

### Epic 2: Création & Import des Recommandations
**User Goal:** The Audit Internal team can ingest the institution's massive legacy data from Excel and seamlessly create new recommendations, providing a unified single source of truth.
**FRs covered:** FR5, FR6, FR6b, FR8, FR9, FR10, FR11
**Implementation Notes:** Crucial for the capacity NFRs (2000 recos, 9000 files). The Excel import must be an atomic transaction. Requires handling dates safely to use the original Excel creation time for logic rules. **[Affinement Métier] : L'import historique n'est pas un import "Big Bang" unique, mais sera exécuté de manière progressive sur la durée par l'Audit Interne.**

#### Story 2.1: Création Unitaire (Formulaire Standard)

As an **Audit Interne**,
I want **créer unitairement une recommandation qui restera en état "Brouillon (DRAFT)"**,
So that **je puisse la modifier ou l'annuler tranquillement avant son assignation officielle.**

**Acceptance Criteria:**

**Given** un Auditeur,
**When** il soumet le formulaire de création de reco,
**Then** l'entrée est sauvegardée en base avec le statut `DRAFT`.

#### Story 2.2: Soft Delete des recommandations brouillons

As an **Audit Interne**,
I want **supprimer logiquement (Soft Delete) des recommandations en état DRAFT**,
So that **je puisse corriger des erreurs de création sans générer de sauts d'ID dans la séquence.**

**Acceptance Criteria:**

**Given** une reco en `DRAFT`,
**When** l'Audit clique sur supprimer,
**Then** la ligne est marquée `is_deleted=True` au lieu d'une suppression SQL `DELETE` (FR6).

#### Story 2.5: Assignation Définitive au DM (Lancement du Chrono)

As an **Audit Interne**,
I want **assigner formellement une recommandation à la Direction cible**,
So that **le statut passe à `ASSIGNED` et que le délai de résolution réglementaire démarre.**

**Acceptance Criteria:**

**Given** une reco en `DRAFT`,
**When** assignée à un DM,
**Then** l'état FSM passe à `ASSIGNED` et le DM cible peut désormais visualiser la recommandation (FR11).

### Epic 3: Evidence Submission & Collaborative Workflow
**User Goal:** Department Managers and Employees can submit proofs, negotiate required extensions, and collaborate with the Audit team to definitively close compliance issues without using external channels like emails.
**FRs covered:** FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR24, FR33, FR34
**Implementation Notes:** Implements the core 5-state FSM workflow (`django-fsm`). Needs strict validation on uploads (Magic Bytes) and Max 15MB limits. This is the largest and most valuable epic. Includes la génération du Sceau HMAC-SHA256 (FR24) à la clôture — fusionnée depuis Epic 5 pour éliminer la dépendance inter-epic. **[Affinement UX & Logique] : Les tableaux de bord doivent filtrer par défaut "Backlog Historique" vs "Nouveau" pour prévenir la submersion des DMs/ETPs au fil des imports. Le FSM doit inclure une gestion sécurisée de la "Boucle de Rejet" lorsque les délais sont en OVERDUE pour éviter un spam asynchrone.**

#### Story 3.1: To-Do List Filter (Historique vs Récent)

As a **Directeur Métier (DM) ou ETP**,
I want **séparer mon tableau de bord entre le "Backlog Historique" et les "Nouvelles Recos"**,
So that **je ne sois pas paralysé par le volume initial de 2000 recommandations.**

**Acceptance Criteria:**

**Given** un utilisateur connecté (DM/ETP),
**When** il accède à sa liste de recommandations,
**Then** l'interface affiche par défaut les recommandations marquées "Récentes".
**And** un onglet ou bouton de filtre permet de basculer vers le "Backlog Historique" (IMPORTED).

#### Story 3.2: Délégation Opérationnelle (DM -> ETP)

As a **Directeur Métier**,
I want **soit désigner un de mes ETP pour préparer la preuve, soit m'assigner moi-même (DM Porteur)**,
So that **la personne compétente ait la responsabilité concrète du dossier.**

**Acceptance Criteria:**

**Given** une recommandation en état `ASSIGNED` dans mon département,
**When** je sélectionne un agent dans la liste déroulante des ETP,
**Then** le statut reste `ASSIGNED` mais le champ `assignee` est mis à jour avec cet utilisateur.
**And** l'ETP reçoit une notification immédiate l'informant de son assignation.

#### Story 3.3: Soumission de Preuves (ETP) et Immutabilité

As a **ETP**,
I want **uploader mes fichiers justificatifs (<15 Mo) et un commentaire de résolution**,
So that **le statut passe à `PENDING_DM_REVIEW` pour que mon manager vérifie avant envoi final (FR15, FR16).**

**Acceptance Criteria:**

**Given** une recommandation m'étant assignée,
**When** j'uploade un fichier et que je saisis un commentaire,
**Then** l'état FSM passe à `PENDING_DM_REVIEW`.
**And** le système valide l'intégrité du fichier par **Magic Bytes** (interdisant les macros XLSM et les faux renommages) (NFR-SEC-04).
**And** l'utilisateur peut taguer le fichier (ex: "PV de Recette", "Justificatif standard").
**And** une fois le fichier uploadé, il est impossible de le supprimer physiquement ou de l'altérer en base de données (Append-Only).
**And** le Directeur Métier (DM) reçoit une notification l'informant de la soumission de la preuve.

#### Story 3.4: Rejet Interne par le DM (Boucle d'amélioration)

As a **Directeur Métier**,
I want **rejeter une preuve insuffisante déposée par mon ETP, avec motif obligatoire**,
So that **le statut revienne à `IN_PROGRESS` pour correction, sans déclencher de fausses alertes à l'Audit.**

**Acceptance Criteria:**

**Given** une recommandation en état `PENDING_DM_REVIEW`,
**When** je clique sur "Rejeter" et saisis le motif,
**Then** l'état repasse en `IN_PROGRESS` (conformément au PRD, parcours Edge Case).
**And** l'Audit ne reçoit aucune notification de rejet interne.

#### Story 3.5: Validation DM et Envoi à l'Audit (Exemption PV)

As a **Directeur Métier**,
I want **approuver la preuve de l'ETP (ou soumettre la mienne) pour l'envoyer à l'Audit**,
So that **le statut passe à `PENDING_AUDIT_REVIEW`.**

**Acceptance Criteria:**

**Given** une recommandation en état `PENDING_DM_REVIEW` (ou `ASSIGNED` si DM porteur),
**When** je valide le dossier vers l'Audit,
**Then** l'état passe à `PENDING_AUDIT_REVIEW`.
**And** le champ "Commentaire" peut être laissé vide si, et seulement si, un fichier de type "PV de Recette" a été détecté par le système (FR17, FR19).

#### Story 3.6: Demande de Report d'Échéance

As a **Directeur Métier (ou DG)**,
I want **demander un allongement du délai de résolution en fournissant une justification**,
So that **l'Audit puisse approuver la nouvelle date ou rejeter ma demande.**

**Acceptance Criteria:**

**Given** une recommandation assignée (non encore clôturée),
**When** je saisis une nouvelle date cible et un motif,
**Then** le système enregistre une demande en attente (`PENDING_EXTENSION`).
**And** l'Audit Interne peut approuver (met à jour la date) ou rejeter (maintient l'état précédent) (FR13, FR14).

#### Story 3.7: Soumission Exclusive par la DG

As a **DG**,
I want **pouvoir de manière ponctuelle soumettre moi-même des preuves sur des dossiers critiques de mon périmètre**,
So that **je bypass les niveaux intermédiaires lorsque cela s'avère stratégiquement nécessaire.**

**Acceptance Criteria:**

**Given** une recommandation assignée dans mon périmètre DG,
**When** je dépose une preuve et valide,
**Then** le statut passe directement à `PENDING_AUDIT_REVIEW` sans passer par la case DM (FR33).

#### Story 3.8: Clôture Définitive par l'Audit Interne

As a **Audit Interne**,
I want **vérifier les preuves du DM et fermer la recommandation**,
So that **le statut devienne `CLOSED_RESOLVED` et sécurise le dossier.**

**Acceptance Criteria:**

**Given** une recommandation en état `PENDING_AUDIT_REVIEW`,
**When** je valide l'adéquation de la preuve,
**Then** l'état final devient `CLOSED_RESOLVED`.
**And** le dossier n'est plus modifiable (FR20).
**And** le Sceau HMAC-SHA256 est automatiquement calculé et stocké (voir Story 3.10).

#### Story 3.9: Bascule Automatique OVERDUE (Cron)

As a **Système (Background Job)**,
I want **passer automatiquement le statut en `OVERDUE` à minuit si l'échéance est dépassée**,
So that **l'information soit exacte dans les tableaux de bord le lendemain matin.**

**Acceptance Criteria:**

**Given** une recommandation dont la date d'échéance est passée (et état != CLOSED),
**When** le job de nuit (cron) s'exécute,
**Then** l'état passe automatiquement à `OVERDUE` (FR21).

### Epic 4: Proactive Alerting & Notification Engine (In-App d'abord)
**User Goal:** Les utilisateurs sont informés **en temps réel, dans l'application** (feed + badge), des événements qui les concernent (assignation, rejet, validation, clôture, retard, échéances proches) — réduisant la charge mentale **sans dépendre de l'e-mail**.
**FRs covered:** FR22, FR23 (volet **in-app** ; le volet e-mail est reporté post-MVP)
**Implementation Notes:** Focus MVP = **notifications in-app** (modèle `Notification` channel-agnostic + feed/badge). Génération synchrone sur événements workflow + jobs Django-Q2 pour les ruptures/anticipations. L'**idempotence** (pas de doublon) repose sur le modèle `Notification` (**Story 4.0**, prérequis de 4.1/4.2). Le **canal e-mail** (alertes immédiates « alarme incendie » + digest hebdomadaire) est **reporté post-MVP / backlog** et réutilisera le même modèle sans refonte. La **doctrine « alarme incendie »** reste le principe directeur du futur e-mail (canal rare, haut-signal) ; l'in-app, lui, peut porter le routinier.

#### Story 4.0: Socle Notifications In-App (Modèle + Feed)

As a **Utilisateur (DM, ETP, DG, Audit)**,
I want **un modèle `Notification` et un feed in-app (badge + liste déroulante) signalant les événements qui me concernent**,
So that **je sois informé en temps réel sans e-mail, et que le futur canal e-mail (post-MVP) réutilise ce socle.**

**Acceptance Criteria:**

**Given** un événement notifiable destiné à un utilisateur,
**When** il est émis,
**Then** un enregistrement `Notification` est créé (destinataire, type, recommandation liée éventuelle, **clé d'idempotence**, date, statut **lu/non-lu**) — **channel-agnostic** (aucune dépendance e-mail).
**And** un **badge** (compteur de non-lus) et une **liste déroulante** in-app (dans la topbar) affichent les notifications de l'utilisateur, avec **« marquer comme lu »** (individuel + tout).
**And** l'émission est **idempotente** : un même événement (même clé) ne crée jamais de doublon.
**And** le modèle est conçu pour qu'un **canal e-mail** (post-MVP) puisse consommer les mêmes `Notification` sans refonte.

#### Story 4.1: Notifications In-App sur Événements (Workflow + Ruptures)

As a **Utilisateur concerné**,
I want **recevoir une notification in-app quand un événement me concernant survient — assignation, délégation, rejet, validation, clôture, et surtout les ruptures (retard d'une Critique, jalons 30/60 j)**,
So that **je voie immédiatement ce qui exige mon action, sans e-mail (FR22).**

**Acceptance Criteria:**

**Given** un événement workflow me concernant (assignation/délégation, rejet de preuves, validation DM, clôture Audit, demande/décision de report),
**When** il se produit,
**Then** une `Notification` in-app est créée pour le bon destinataire (porteur, DM ou Audit selon l'événement).
**And** pour les **ruptures** : passage à `OVERDUE` (via l'AuditLog `action=SYSTEM` de la Story 3.9) d'une **Critique**, ou franchissement d'un **jalon `≥ 30 j`** de retard (`aujourd'hui − due_date`, **seuil** non encore notifié — pas une égalité « exactement 30 j » fragile aux pannes de cron), une notification **prioritaire** (visuellement distincte) est créée pour le porteur (ETP assigné, ou DM porteur).
**And** au **jalon `≥ 60 j`** de retard sans action, une **escalade** notifie le **supérieur hiérarchique** (le DM assigné si le porteur est un ETP ; sinon le responsable du `Department.parent`).
**And** chaque jalon/événement est **idempotent** (Story 4.0) : jamais plus de deux fois la même notification.

#### Story 4.2: Anticipation In-App des Échéances (J-7 / J-3) et Résumé de Portefeuille

As a **DM / ETP / DG (et Audit pour ses validations)**,
I want **voir in-app, sans e-mail, les échéances qui approchent (J-7, J-3) et un résumé de mon portefeuille**,
So that **je pilote mes échéances de manière proactive sans être spammé (FR23).**

**Acceptance Criteria:**

**Given** une recommandation active dont l'échéance approche (J-7 puis J-3),
**When** le job quotidien s'exécute,
**Then** une `Notification` in-app d'anticipation est créée pour le porteur (**idempotente** : une seule par palier J-7 et une seule par palier J-3).
**And** un **résumé de portefeuille** in-app (en cours / en retard / échéances proches) est consultable par chaque utilisateur ; pour l'**Audit**, les reports en attente de validation y figurent.
**And** **aucun e-mail** n'est émis.

> **Reporté post-MVP / backlog (réutilisera le modèle `Notification`) :**
> - **Digest e-mail hebdomadaire** (lundi matin, un seul e-mail/utilisateur, skip si portefeuille vide, texte brut).
> - **Alertes e-mail immédiates « alarme incendie »** (ruptures Critiques + escalade), texte brut via `EMAIL_BACKEND`.
> Prérequis de réouverture : infra SMTP on-premise COBAC disponible.

#### Story 4.3: Importation Atomique Historique (Substitut de Masse MVP)

As an **Audit Interne (Seulement)**,
I want **uploader le template Excel officiel contenant l'historique massif (2000 lignes)**,
So that **tout l'historique soit intégré de manière fiable dans la base de données.**

**Acceptance Criteria:**

**Given** l'upload d'un Excel par l'Audit,
**When** déclenché,
**Then** l'import exécute une transaction atomique stricte (tout ou rien).
**And** les recos importées avec succès ont le statut `ASSIGNED`, le tag `IMPORTED`, et conservent leur date de création Excel originale (FR8, FR9).


#### Story 4.4: Triage et Auto-Assignation

As an **Audit Interne**,
I want **m'auto-assigner des recommandations à trier (notamment les imports historiques)**,
So that **mon équipe puisse finaliser la complétion des données avant l'envoi légal aux métiers.**

**Acceptance Criteria:**

**Given** une reco importée ou en brouillon,
**When** l'audit se l'auto-assigne,
**Then** elle n'est visible que par le pool Audit et ne déclenche aucune alerte (FR10).


#### Story 4.5: Bannière Contextuelle de Notifications In-App

As a **Utilisateur (DM, ETP, Audit, DG)**,
I want **voir une bannière légère résumant l'activité survenue depuis ma dernière connexion (sans système lourd de type "lu/non-lu")**,
So that **je sois informé des assignations, rejets, et échéances proches dès mon arrivée sur le dashboard, sans recevoir d'e-mail pour ces événements courants.**

**Acceptance Criteria:**

**Given** un utilisateur qui se connecte au dashboard Sentinel,
**When** des événements courants (assignation, preuve rejetée, commentaire ajouté, approche échéance J-14/J-7) ont eu lieu depuis sa dernière visite,
**Then** une bannière contextuelle non intrusive s'affiche en haut de l'écran résumant l'activité (ex: "Depuis votre dernière visite : 1 preuve rejetée, 2 échéances proches").
**And** la bannière peut être fermée et ne gère pas d'états complexes "lu/non-lu" paritairement (stateless feeling).
**And** les indicateurs d'urgence (badges, couleurs) sur les tableaux restent la source de vérité persistante.

#### Story 3.10: Génération du Sceau HMAC-SHA256 à la Clôture

As a **Système**,
I want **générer une empreinte cryptographique unique lors de la clôture d'une recommandation**,
So that **l'intégrité de la recommandation et de ses preuves soit garantie de manière inaltérable (FR24).**

**Acceptance Criteria:**

**Given** une recommandation passant à l'état `CLOSED_RESOLVED` (Story 3.8),
**When** la sauvegarde FSM de fin est invoquée,
**Then** le sceau cryptographique HMAC-SHA256 est calculé en utilisant la clé dédiée `HMAC_SECRET_KEY` et stocké en base.
**And** l'overhead de calcul ne dépasse pas 500ms (NFR-PERF-03).

> **Note :** Story fusionnée depuis Epic 5 (ex-Story 5.1) pour éliminer la dépendance inter-epic entre la clôture et le scellement cryptographique.

### Epic 5: Confiance Réglementaire & Audit Trail
**User Goal:** The regulatory bodies (COBAC, Commisaires) and Management can cryptographically trust that closed recommendations are totally immutable and can rapidly download the full legal archives.
**FRs covered:** FR25, FR26, FR27
**Implementation Notes:** ZIP archives must be generated iteratively via stream (`BytesIO`) to not crash memory constraints. FR24 (Sceau HMAC) a été fusionné dans Epic 3 (Story 3.10) car intrinsèquement lié à la clôture FSM. **[Affinement Scope] : La Timeline chronologique (FR27) est conçue comme un pur tableau HTML listant les événements `AuditLog` sans aucune complexité ou interactivité JavaScript pour sécuriser la deadline.**

#### Story 5.1: Timeline statique de l'Audit Trail

As an **Utilisateur Autorisé**,
I want **visualiser l'historique complet d'une recommandation via un tableau chronologique simple**,
So that **je puisse auditer l'enchaînement des événements sans complexité d'interface.**

**Acceptance Criteria:**

**Given** la page de détail d'une recommandation,
**When** je consulte la section "Audit Trail",
**Then** je vois un tableau HTML (SSR pur) listant chronologiquement les changements d'états, incluant explicitement l'horodatage et les identités, ex: "action par Y agissant pour X" (FR27).

#### Story 5.2: Compilation d'archive ZIP pour l'Audit Externe

As an **Auditeur Externe**,
I want **télécharger d'un clic toutes les preuves et données d'une recommandation**,
So that **je puisse l'archiver et réaliser mes contrôles via mon propre système (FR25, FR26).**

**Acceptance Criteria:**

**Given** une recommandation clôturée,
**When** l'auditeur externe demande un export ZIP,
**Then** le système génère en mémoire (`BytesIO`) l'archive incluant les justificatifs et génère un téléchargement performant.
**And** la génération de l'archive ZIP est streamée et ne dépasse pas 5 secondes par recommandation (NFR-PERF-04).

### Epic 6: Executive Supervision Dashboards
**User Goal:** The Executive Board (DG) and Managers can visualize global compliance risks, identify operational bottlenecks via aging metrics and color-coding, and instantly print reports for steering committees.
**FRs covered:** FR4, FR29, FR30, FR31, FR32
**Implementation Notes:** Avoid heavy frontend. Focus on precise PostgreSQL QuerySets coupled to robust HTMX/Vanilla Tailwind filters. Minimal server overhead. **[Mitigation Performance] L'indicateur de vieillissement (Aging) doit être pré-calculé (Dénormalisé) par le Cron de la Story 3.9 plutôt que calculé à la volée via des JOIN complexes, pour garantir un P95 de rendu UI < 200ms.**

#### Story 6.1: Dashboard de Supervision avec Indicateurs d'Urgence

As a **DG ou DM**,
I want **avoir une vue consolidée de l'exposition au risque réglementaire (code couleurs, aging)**,
So that **je puisse identifier immédiatement les zones et services en alerte (FR29, FR30).**

**Acceptance Criteria:**

**Given** la vue tableau de bord,
**When** je l'affiche,
**Then** les recommandations sont groupées et triées par priorité et niveau d'urgence.
**And** les indicateurs visuels (codes couleurs) reflètent l'urgence et le vieillissement de façon claire.

#### Story 6.2: To-Do List Executive

As a **DG**,
I want **disposer d'une To-Do list affichant uniquement mes propres recommandations assignées**,
So that **je puisse consulter et traiter directement de façon ciblée les dossiers dont j'ai la charge (FR32).**

**Acceptance Criteria:**

**Given** un utilisateur DG connecté,
**When** il accède à sa To-Do list,
**Then** l'interface liste strictement et uniquement les recommandations qui lui sont formellement assignées, sans polluer avec les dossiers réservés aux seuls DMs.

#### Story 6.3: Optimisation de l'impression PDF (CSS Print)

As a **DG**,
I want **imprimer les rapports de dashboard de manière lisible depuis mon navigateur**,
So that **je puisse les présenter ou les archiver en comité sans nécessiter de génération PDF complexe côté serveur (FR31).**

**Acceptance Criteria:**

**Given** le tableau de bord ou la vue liste,
**When** j'utilise la fonctionnalité d'impression native de mon navigateur (`Ctrl+P`),
**Then** des balises CSS `@media print` masquent la navigation globale et adaptent proprement le format pour le format papier standard.

#### Story 6.4: Configuration de l'Intérim et Délégation (Impersonnalisation)

As a **Directeur Métier (DM) ou Audit**,
I want **paramétrer un utilisateur "Intérimaire" pour remplacer un titulaire absent sur une période donnée**,
So that **l'intérimaire puisse agir au nom de l'absent avec une traçabilité totale.**

**Acceptance Criteria:**

**Given** qu'un ETP remplace son DM en congés,
**When** l'ETP effectue une action métier (ex: validation preuve),
**Then** le système permet l'action
**And** l'Audit Log enregistre explicitement que l'action a été effectuée par l'ETP agissant pour le DM (FR4).
