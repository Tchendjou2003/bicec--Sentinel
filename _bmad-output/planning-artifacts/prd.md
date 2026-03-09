---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional']
classification:
  projectType: On-Premise Enterprise Web App (RBAC 6 profils + RLS, FSM 7 états incl. RETARD, Async In-Memory Scheduler, Audit Trail)
  domain: Fintech / RegTech
  complexity: HIGH
  projectContext: Greenfield
---

# Product Requirements Document - bicec--Sentinel

**Author:** Dave Lahe
**Date:** 2026-03-08

## Executive Summary

Sentinel est une démarche de conformité active conçue pour répondre aux exigences strictes de la Commission Bancaire de l'Afrique Centrale (COBAC R-2023/01) et du régulateur local (Loi 2024-017). L'application gère le cycle de vie complet des recommandations d'audit (Internes et Externes) opérant au sein de la BICEC. Déployée sur l'infrastructure interne sécurisée de la BICEC, elle remplace des processus manuels fragmentés (fichiers Excel, e-mails) par un flux de travail centralisé, hautement sécurisé et opposable, garantissant que chaque anomalie soulevée est traitée, vérifiée et clôturée avec une stricte Séparation des Tâches (SoD).

### What Makes This Special

Sentinel est une **Enterprise Web App à haute valeur probatoire** dont l'architecture même force le respect du processus canonique d'audit :
- **Rigueur Automatisée (FSM 7 états) :** Le cycle de vie d'une recommandation est régi par une machine à états finis inviolable, gérant les chemins nominaux, les rejets hiérarchiques, et détectant proactivement les délais dépassés (statut `OVERDUE`).
- **Sécurité et Ségrégation (RBAC & RLS) :** La Row-Level Security intégrée nativement en base de données empêche techniquement, au-delà de la simple couche applicative, toute fuite d'information métiers entre les 6 profils d'accès.
- **Réactivité Asynchrone :** Un ordonnanceur (Scheduler In-Memory/Database) scrute silencieusement le système pour calculer les taux de franchissement (40/60/80%), basculer les dossiers en retard et envoyer les relances sans saturer l'infrastructure de la banque.
- **Immuabilité (Audit Trail) :** Les preuves sont archivées de manière immuable avec empreinte d'intégrité (SHA-256), rendant l'historique opposable en cas de contrôle des autorités de régulation financière.

## Project Classification

- **Project Type :** On-Premise Enterprise Web App
- **Domain :** Fintech / RegTech
- **Complexity :** HIGH
- **Project Context :** Greenfield

## Success Criteria

### User Success
- **Audit Interne :** N'a plus besoin d'agir comme un "flic" faisant des relances manuelles. Visualise l'état global en temps réel.
- **Directeur Métier (DM) & ETP :** Utilisent l'outil de manière fluide avec une charge mentale réduite, guidés par les notifications asynchrones avant l'échéance des délais.

### Business Success
- **Zéro Sanction Réglementaire :** Élimination totale des pénalités COBAC liées à une perte de preuve ou à un retard non tracé/non justifié.
- **Taux de Couverture à 100% :** La totalité des recommandations (internes et externes) de la banque sont gérées exclusivement dans Sentinel, certifiant l'abandon définitif d'Excel.
- **Taux d'Adoption Proactive :** > 80% des Directeurs Métiers se connectent et traitent leurs dossiers de manière proactive, avant le déclenchement de la première contrainte (alerte de retard du Scheduler).

### Technical Success
- **Intégrité Cryptographique Résiliente (Zéro Faille) :** Aucun utilisateur (y compris l'Administrateur BDD disposant d'un accès direct) ne doit pouvoir altérer la date de clôture ou modifier une preuve archivée sans briser irrémédiablement l'empreinte de contrôle (Audit Trail inviolable).
- **Ségrégation Holistique :** Le RLS garantit qu'aucune brèche applicative ne permettra les accès croisés entre directions.

### Measurable Outcomes
- **Durée moyenne de validation (Goulots d'étranglement) :** Le temps passé *exclusivement* dans les états transitoires d'approbation humaine (`PENDING_DM_REVIEW` et `PENDING_AUDIT_REVIEW`) doit être inférieur à 48 heures ouvrées. *Note : Cette métrique exclut volontairement l'état `IN_PROGRESS`, car la correction technique ou métier d'une recommandation par un ETP peut pertinemment nécessiter un délai de 3 à 6 mois.*
- **Taux de reports justifiés (OVERDUE) :** > 90% des recommandations tombant en retard doivent avoir fait l'objet d'une sollicitation de délai supplémentaire tracée dans la FSM *avant* l'échéance.

## Product Scope

### MVP - Minimum Viable Product
- **Workflow & FSM :** Machine à 7 états (`DRAFT` à `CLOSED_RESOLVED`) gérant les 5 acteurs y compris les statuts d'exceptions (`OVERDUE`, `REJECTED`).
- **Sécurité :** RBAC 6 profils, Row-Level Security (RLS) en base de données, SSO Active Directory.
- **Async & Notifications :** Ordonnanceur BDD (In-Memory Scheduler) pour les relances dynamiques (40/60/80%) et le basculement automatique des statuts.
- **Preuves & Audit Trail :** Upload de preuves textuelles ou fichiers avec justification obligatoire, scellement par empreinte d'intégrité à la clôture.
- **Export Légal :** Génération de l'archive cryptée complète (Preuves + Journal) à destination de l'auditeur externe.
- **Reprise de l'Historique :** Module d'import massif (Excel) pour intégrer les recommandations dormantes ou passées (Indispensable pour l'adoption V1).

### Growth Features (Post-MVP)
- Portail de consultation interactive sécurisé (DMZ) pour les Auditeurs Externes.
- Reconnaissance Optique de Caractères (OCR) pour pré-validation des preuves scannées.

### Vision (Future)
- **Hub de Conformité SaaS On-Premise :** Standardisation de l'outil pour commercialisation sécurisée au sein d'autres banques de la zone CEMAC.
- **IA de Conformité :** Validation sémantique algorithmique de la pertinence d'une preuve soumise vis-à-vis du texte de la recommandation.

## User Journeys

### 1. Parcours Nominal : La Validation Parfaite (Happy Path)
**Personas impliqués :** Marc (Audit Interne), Sarah (Directrice Métier), Luc (ETP Opérationnel).
**Le scénario :** Marc saisit une recommandation et l'assigne à la direction de Sarah avec un délai de 30 jours (`ASSIGNED`). Sarah la délègue immédiatement via son dashboard à Luc (`IN_PROGRESS`). À J-20, Luc termine, uploade les preuves en PDF avec commentaire et soumet (`PENDING_DM_REVIEW`). Sarah vérifie les preuves de Luc et valide, transmettant le dossier à Marc (`PENDING_AUDIT_REVIEW`). Marc certifie les preuves. Le système clôture le dossier (`CLOSED_RESOLVED`) et génère l'empreinte SHA-256.
**Bénéfice :** 0 e-mail de relance, charge mentale réduite, process 100% tracé.

### 2. Parcours d'Exception : Le Goulot et le Rejet (Edge Case)
**Personas impliqués :** Sarah (Directrice Métier), Luc (ETP Opérationnel).
**Le scénario :** Luc soumet ses preuves (`PENDING_DM_REVIEW`). Sarah part en congé sans déléguer ses droits. L'ordonnanceur asynchrone détecte l'échéance : 48h passent et au terme du délai initial, le dossier bascule en `OVERDUE` (En retard) avec notification à la DG. À son retour, Sarah ouvre le dossier, trouve les preuves incomplètes, et clique sur "Rejeter" (`REJECTED`) avec le motif "Signature DSI manquante". Luc doit fournir de nouvelles preuves pour sortir du retard.
**Bénéfice :** La FSM attribue factuellement le goulot d'étranglement au bon acteur (Sarah) sans bloquer l'exécutant éternellement dans le silence.

### 3. Parcours de l'Auditeur Externe : La Mission COBAC (Compliance Path)
**Persona impliqué :** M. Atangana (Inspecteur COBAC).
**Le scénario :** M. Atangana effectue un contrôle inopiné à la BICEC. Il reçoit un accès "Auditeur Externe" (Lecture seule cloisonnée par RLS). Via le module de filtrage, il isole son périmètre de mission et clique sur "Générer Export Légal". Un job asynchrone compile un fichier ZIP contenant le registre d'audit trail complet en PDF et l'intégralité des pièces jointes natives indélébiles.
**Bénéfice :** Transparence immédiate et preuve technique irréfutable de non-altération à posteriori des dossiers.

### Journey Requirements Summary
Ces parcours utilisateurs induisent des exigences techniques spécifiques pour l'implémentation :
- **Délégation Asynchrone :** Gérer l'affectation N+1 -> N (fonctionnalité de co-affectation ou assignation d'ETP).
- **Historisation des Rejets :** Versioning des soumissions (un ETP peut soumettre N fois le même dossier avec des commentaires/preuves différents suite à des rejets).
- **Gestion de l'Intérim :** Nécessité absolue d'un mécanisme de délégation temporaire des droits de validation (vacances DM).
- **Générateur d'Export Zip Asynchrone :** Service background (`pdf-gen`, `zip-gen`) impératif pour ne pas faire exploser les timeouts HTTP du navigateur lors des requêtes d'auditeurs externes.

## Domain-Specific Requirements

### Compliance & Regulatory
- **Normes Prudentielles COBAC (Régulation R-2019/02 - 23 sept. 2019) :** Impose aux établissements financiers un dispositif de contrôle interne robuste. Sentinel agit comme le registre officiel de suivi des recommandations de ce dispositif, dont les preuves doivent être restituables à tout moment.
- **Loi Cybersécurité Cameroun (Loi Num. 2010/012 - 21 déc. 2010) :** Encadre la protection des systèmes d'information et la cybergouvernance. Cette loi verrouille le choix architectural de Sentinel sur une infrastructure sécurisée *On-Premise* à la BICEC.
- **Protection des données personnelles (Loi Num. 2023/009 - 25 juil. 2023) :** Exige un consentement strict et une protection accrue des données identifiantes. Sentinel devra potentiellement anonymiser ou pseudonymiser les noms des collaborateurs (ETP) dans les exports destinés à des tiers non habilités.

### Technical Constraints
- **Separation of Duties (SoD) systémique :** L'Administrateur technique (IT) ou Base de Données ne doit disposer d'aucun droit applicatif permettant de valider ou de manipuler le workflow métier d'une recommandation.
- **Row-Level Security (RLS) :** Cloisonnement étanche des données applicatives en base. Le compte d'un Directeur de Branche ne doit pouvoir techniquement lire que les recommandations affectées à son périmètre d'habilitation (principe de moindre privilège).

### Integration Requirements
- **SSO Active Directory (LDAP/SAML) :** L'authentification doit s'adosser à l'annuaire existant de la BICEC. Le départ d'un collaborateur (désactivation locale AD) doit révoquer instantanément son accès à Sentinel.
- **Relais SMTP Interne :** L'envoi des volumes de notifications asynchrones doit utiliser le flux e-mail interne de la banque pour des raisons de sécurité de l'information.

### Risk Mitigations
- **Risque d'Opacité des Décisions (Répudiation) :** "Je n'ai pas pu soumettre à temps."
  *Mitigation :* Traçabilité inaltérable des rejets et historisation complète de chaque version des preuves soumises par un ETP avant la clôture finale.
- **Risque de Contournement Hiérarchique :**
  *Mitigation :* Validation algorithmique dans la FSM empêchant toute auto-validation (un ETP ne peut cumuler les rôles de créateur de la preuve et de valideur managérial sur une même recommandation).

## Innovation & Novel Patterns

### Detected Innovation Areas
Bien que Sentinel soit par essence un outil de mise en conformité réglementaire (RegTech), son principal axe d'innovation réside dans son interopérabilité future avec les autorités de tutelle :

1. **Intégration API Régulateur (Direct-to-Regulator) :**
Plutôt que de se limiter éternellement à la génération de fichiers ZIP manuels pour les inspecteurs de la COBAC, Sentinel posera dès l'origine les bases d'une intégration "Machine-to-Machine". Dès qu'un état spécifique sera atteint ou qu'un dossier sera clôturé (`CLOSED_RESOLVED`), Sentinel sera capable de transmettre la preuve cryptographique (payload structuré + empreinte SHA-256) directement aux systèmes d'information du régulateur via des webhooks/API sécurisés. Cette automatisation "Temps Réel" constitue une véritable rupture dans la relation et la transparence entre la Banque et le Régulateur.

### Validation Approach
- Cette capacité "API Régulateur" sera préparée architecturalement en cloisonnant le module d'export, qui devra pouvoir tant générer un fichier physique (MVP) qu'émettre un payload JSON chiffré vers des endpoints externes configurables (Post-MVP).

### Risk Mitigation
- L'envoi automatique de factes d'audit à un régulateur de façon autonome présente un risque d'emballement ou de fuite de données si déclenché par erreur. *Mitigation :* Toute transmission API vers le régulateur nécessitera une gouvernance stricte (ex: validation électronique à "4-yeux" par le Directeur de l'Audit et la Direction Fiscale/Légale) avant paramétrage et activation de la route.

## Project-Type Specific Requirements

### Project-Type Overview
En tant que **On-Premise Enterprise Web App**, Sentinel se détache des architectures SaaS modernes légères. Le projet privilégie à 100% la sécurité, la robustesse et la ségrégation des données au détriment de l'élasticité cloud.

### Technical Architecture Considerations

À la lumière de nos contraintes (FSM stricte, RLS, asynchrone lourd), voici l'architecture recommandée et justifiée pour le MVP de Sentinel :

**1. Modèle d'Hébergement : Single-Tenant (Dédié BICEC)**
- **Choix :** Le code et la base de données ne gèreront qu'une seule entité bancaire (la BICEC) pour la V1.
- **Justification :** Le développement en "Multi-tenant" (SaaS) impose d'ajouter une clé (`tenant_id`) dans *chaque* table et d'alourdir la logique RLS. En restant Single-Tenant pour le MVP, on supprime cette complexité technique, ce qui accélère drastiquement le temps de développement et réduit considérablement les failles de sécurité critiques.

**2. Architecture Frontend : SPA (Single Page Application - React.js)**
- **Choix :** Interface Web découplée gérée par une bibliothèque moderne (React ou Vue.js).
- **Justification :** Sentinel n'a pas besoin de SEO (Référencement Google), c'est un intranet. En revanche, les Directeurs Métiers et l'Audit ont besoin de tableaux de bord financiers interactifs (Filtres instantanés, changement d'états dynamiques, uploaders de preuves fluides). Une SPA permet une expérience utilisateur "Desktop-like", essentielle pour l'adoption interne de l'outil.

**3. Base de Données : PostgreSQL**
- **Choix :** Système de Gestion de Base de Données Relationnelle (SGBDR) open-source de classe entreprise.
- **Justification :** Choix incontournable. C'est le SGBD qui possède la gestion la plus robuste et native du *Row-Level Security* (RLS) pour cloisonner les données par branche/département au niveau même du moteur de stockage, indépendamment d'une potentielle faille dans le code backend. Il supporte également très bien les transactions complexes de notre Machine à États (FSM).

**4. Architecture Backend : Framework Orienté Modèle (Python/Django ou Java/Spring Boot)**
- **Choix :** Un framework monolithique "Headless" (exposant uniquement une API REST pour le Frontend React).
- **Justification de la pertinence :** 
  - *Option A (Django + Celery) :* Sentinel repose sur un ordonnanceur asynchrone (Celery). L'écosystème Python/Django s'intègre nativement à Celery + Redis pour gérer les alertes, les relances et la génération de PDF sans ralentir l'utilisateur. De plus, Django possède un système d'ORB/Transitions qui gère parfaitement les machines à états finis (FSM).
  - *Option B (Java Spring Boot) :* Si la Direction IT de la BICEC impose le langage Java par standardisation. Spring State Machine est exceptionnellement robuste pour garantir l'inaltérabilité des 7 états du cycle de vie. Mais c'est un choix plus "lourd" à démarrer que Django.

### Implementation Considerations : Gestion de l'Organigramme
- **Création des Départements / Agences :** 
  - **La Solution :** Sentinel n'interrogera **aucun** système externe (ni Core Banking, ni SI RH) pour récupérer l'organigramme de la BICEC. La création, la modification et l'assignation des Directions/Agences seront entièrement gérées **manuellement** par le Super-Administrateur au sein d'une interface d'administration dédiée dans Sentinel.
  - **Justification :** Cette approche radicale de "déconnexion" élimine 100% des risques de sécurité liés à l'ouverture de flux vers des systèmes centraux de la banque. De plus, l'organigramme global d'une banque évolue relativement peu à l'échelle d'une année financière. Ce choix simplifie massivement le code du MVP tout en garantissant une maîtrise absolue des habilitations (RLS) par l'équipe d'Audit.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**MVP Approach:** "Compliance-First" & "Lean Engineering". L'objectif du MVP est uniquement de sécuriser légalement le cycle de vie de l'audit et de remplacer l'archaïsme d'Excel par un outil opposable en cas d'inspection. Toute complexité technique optionnelle (Multi-tenant, synchronisation SI RH automatique, IA) a été volontairement repoussée. L'import manuel d'historique a été inclus au MVP pour dérisquer l'adoption métier.
**Resource Requirements (Estimation) :** 1 Tech Lead Backend/FSM (Architecture & RLS), 1 Développeur Backend, 1 Développeur Frontend SPA (React/Vue).

### MVP Feature Set (Phase 1)
**Core User Journeys Supported:**
- Création, assignation et traitement complet d'une recommandation ("Happy Path").
- Gestion des goulots, rejets et basculement asynchrone en retard ("Edge Case").
- Mission d'inspection inopinée avec génération de preuve cryptée ("Compliance Path").

**Must-Have Capabilities:**
- FSM 7 états et RBAC 6 profils.
- Base de données Single-Tenant avec Row-Level Security.
- Frontend Single Page Application optimisé pour la fluidité.
- Scheduler asynchrone interne (Relances & Changements d'états).
- Architecture "API Régulateur Ready" (Module d'export natif).
- Interface d'administration pour gestion 100% manuelle de l'organigramme.
- Module central d'Import Massif d'Historique (Excel) pour intégrer les encours existants.

### Post-MVP Features
**Phase 2 (Growth):**
- Portail DMZ "Read-Only" pour auditeurs externes non-salariés.
- Pré-lecture OCR des preuves scannées.

**Phase 3 (Expansion):**
- Intégration complète en temps réel "Machine-to-Machine" avec les API du Régulateur.
- Architecture SaaS "Hub de conformité" (Multi-tenant) pour commercialisation intra-groupe.

### Risk Mitigation Strategy
- **Technical Risks:** Complexité des accès croisés et de la FSM. *Mitigation :* Choix de framework "Headless" robustes avec transactions et RLS natif sur PostgreSQL.
- **Market (Adoption) Risks:** Rejet de l'outil par les Directeurs Métiers s'il est jugé chronophage. *Mitigation :* Architecture Frontend moderne (SPA) pour minimiser les clics, et importation systématique de l'historique lors du Go-Live pour épargner la double-saisie aux opérationnels.
- **Resource Risks:** Débordement des délais face aux exigences de sécurité. *Mitigation :* Scope MVP verrouillé (Organigramme géré à 100% manuellement, aucune intégration tierce autre que l'AD/LDAP).

## Functional Requirements (Capability Contract)

### 1. User Management & Security (RBAC & RLS)
- FR1: L'équipe Support/RCC peut créer, modifier et désactiver des comptes utilisateurs.
- FR2: L'équipe Support/RCC peut créer et modifier l'arborescence des Directions et Agences (Gestion de l'organigramme manuel).
- FR3: L'équipe Support/RCC peut assigner des rôles métiers (Audit, DM, ETP) aux utilisateurs. L'accès en clôture est techniquement dénié au Support/RCC.
- FR4: L'équipe Support/RCC peut configurer une délégation temporaire des droits d'un utilisateur à un autre (Gestion de l'intérim).
- FR5: Le Système restreint l'accès en lecture/écriture aux seules recommandations appartenant au périmètre de l'utilisateur (Row-Level Security).
- FR6: Le Système révoque automatiquement la session d'un utilisateur si son compte Active Directory est désactivé.

### 2. Core Workflow & Validation FSM
- FR7: L'Audit Interne peut créer une nouvelle recommandation et l'assigner à une Direction Métier avec une échéance fixée.
- FR8: Le Directeur Métier peut réassigner une recommandation reçue à un Employé Traitant (ETP) de son équipe.
- FR9: L'Employé Traitant peut soumettre une ou plusieurs preuves pour demander la clôture d'une recommandation.
- FR10: L'Employé Traitant peut soumettre de nouvelles versions de preuves sur une même recommandation s'il subit un rejet hiérarchique, créant ainsi un cycle itératif d'allers-retours tracé jusqu'à l'obtention d'une validation.
- FR11: Le Directeur Métier peut valider ou rejeter la preuve soumise par son Employé Traitant.
- FR12: L'Audit Interne peut valider ou rejeter la preuve avalisée par le Directeur Métier.
- FR13: L'Audit Interne peut modifier la date limite d'une recommandation active, sous réserve d'une justification obligatoire et tracée dans l'historique.
- FR14: L'Audit Interne peut clôturer positivement la recommandation (`CLOSED_RESOLVED`) après validation des preuves.
- FR15: L'Audit Interne peut forcer la clôture d'une recommandation (ex: inspection inopinée terrain prouvant la résolution) sans nécessiter de soumission préalable par l'ETP/DM.

### 3. Proofs & Audit Trail
- FR16: Les Utilisateurs peuvent uploader des fichiers multiformats (PDF, Images, Excel, Word, Logs système) en pièce jointe lors d'une soumission de preuve.
- FR17: Toutes les preuves soumises (acceptées ou rejetées) restent archivées et indélébiles. Toute suppression de preuve est techniquement impossible.
- FR18: Le Système génère une empreinte cryptographique (SHA-256) inaltérable de la recommandation et de la preuve exacte utilisée au moment de la clôture.
- FR19: Le Système enregistre un journal immuable de chaque événement du workflow (Qui, Quand, Ancien État, Nouvel État, modification de date limite, Motif de rejet).
- FR20: Le Système bloque logiciellement l'auto-validation (Séparation des Tâches : un ETP ne peut cumuler le rôle de valideur DM sur le dossier qu'il a soumis).

### 4. Notifications (In-App & Email) & Scheduler
- FR21: Le Système envoie des alertes emails internes sécurisées aux acteurs dès qu'une action est requise de leur part.
- FR22: Le Système expose un "Centre de Notifications In-App" comportant : une icône avec badge (non-lus), une liste chronologique cliquable redirigeant vers la recommandation, et une conservation des logs de 90 jours.
- FR23: Le Système émet des rappels automatiques d'échéance à 40%, 60% et 80% du délai imparti.
- FR24: Le Système bascule automatiquement le statut de la recommandation en `OVERDUE` (En Retard) si le délai d'échéance est franchi sans soumission en attente.

### 5. Reporting, Dashboards & Exports
- FR25: Le Système génère des indicateurs limités calculant le temps passé dans les goulots d'étranglement de validation (< 48h).
- FR26: Le Système affiche un tableau de bord global de pilotage (Lecture seule pour Direction Générale et Audit) comprenant : Taux de conformité global, Répartition par statut (Graphique), Recommandations en retard par métier, et Évolution mensuelle.
- FR27: La Direction Générale peut exporter les rapports issus du tableau de bord consolidé.
- FR28: L'Auditeur Externe accède en lecture seule stricte aux recommandations de son périmètre préalablement défini par l'Audit Interne.
- FR29: L'Auditeur Externe peut télécharger les preuves rattachées aux recommandations de son périmètre d'inspection.
- FR30: L'Audit Interne peut demander la génération asynchrone d'une archive ZIP contenant le journal et les preuves d'une recommandation clôturée.
- FR31: L'Audit Interne peut (après double validation à "4-yeux") déclencher l'envoi d'un payload cryptographique vers l'API du Régulateur COBAC.

### 6. Data Initialization (MVP)
- FR32: L'équipe Support/RCC peut uploader un fichier plat (Excel/CSV) pour importer massivement l'historique des recommandations dormantes dans la base de données.
