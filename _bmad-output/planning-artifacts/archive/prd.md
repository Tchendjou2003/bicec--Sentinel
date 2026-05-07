---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional']
classification:
  projectType: On-Premise Enterprise Web App (RBAC 6 profils + RLS, FSM 5 états + flag OVERDUE, Async In-Memory Scheduler, Audit Trail)
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
- **Rigueur Automatisée (FSM 5 états + flag OVERDUE) :** Le cycle de vie d'une recommandation est régi par une machine à états finis inviolable (`ASSIGNED` → `IN_PROGRESS` → `PENDING_DM_REVIEW` → `PENDING_AUDIT_REVIEW` → `CLOSED_RESOLVED`), gérant les chemins nominaux, les rejets itératifs (retour à `IN_PROGRESS`), et détectant proactivement les délais dépassés via un flag `OVERDUE` superposé.
- **Sécurité et Ségrégation (RBAC & RLS) :** La Row-Level Security intégrée nativement en base de données empêche techniquement, au-delà de la simple couche applicative, toute fuite d'information métiers entre les 6 profils d'accès.
- **Réactivité Asynchrone :** Un ordonnanceur (Scheduler In-Memory/Database) scrute silencieusement le système pour détecter les échéances approchantes (alerte J-7), basculer les dossiers en retard et envoyer les rappels quotidiens sans saturer l'infrastructure de la banque.
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

### KPIs Opérationnels (Cibles à 6 mois post-déploiement)

| KPI | Description | Cible |
|---|---|---|
| Taux d'adoption active | % d'ETP et DM connectés ≥ 1x/semaine | > 95% |
| Délai moyen de résolution | % de recommandations clôturées avant échéance | > 85% |
| Taux de rejet Audit | % de preuves validées par DM mais rejetées par l'Audit | < 5% |
| Taux de rejet Métier | % de preuves rejetées par DM vers ETP | < 15% |
| Durée moyenne par statut | Temps passé à chaque étape du workflow (hors `IN_PROGRESS`) | < 48h |
| Taux de reports tracés | % de retards ayant fait l'objet d'une demande formelle de prolongation | > 90% |

**North Star Metric :** *Réduction du délai moyen d'éradication d'un risque critique* + *100% de conformité de l'audit trail*.

## Product Scope

### MVP - Minimum Viable Product
- **Workflow & FSM :** Machine à 5 états (`ASSIGNED` → `IN_PROGRESS` → `PENDING_DM_REVIEW` → `PENDING_AUDIT_REVIEW` → `CLOSED_RESOLVED`) + flag `OVERDUE` superposé. Tout rejet (DM ou Audit) ramène à `IN_PROGRESS` avec versioning des preuves (pas d'état terminal `REJECTED`).
- **Sécurité :** RBAC 6 profils, Row-Level Security (RLS) en base de données, SSO Active Directory.
- **Async & Notifications :** Ordonnanceur BDD (In-Memory Scheduler) pour les alertes J-7 avant échéance et le basculement automatique en `OVERDUE` avec rappels quotidiens.
- **Preuves & Audit Trail :** Upload de preuves textuelles ou fichiers avec justification obligatoire, scellement par empreinte d'intégrité à la clôture.
- **Export Légal :** Génération de l'archive cryptée (Preuves + Synthèse de conformité) à destination de l'auditeur externe. **L'audit trail complet (journal des actions) est exclu de l'export externe** — seul l'Audit Interne peut le consulter.
- **Reprise de l'Historique :** Module d'import massif (Excel) pour intégrer les recommandations dormantes ou passées (Indispensable pour l'adoption V1).

### Growth Features (Post-MVP)
- Portail de consultation interactive sécurisé (DMZ) pour les Auditeurs Externes.
- Seuils de relance proportionnels (40/60/80% du délai) avec dédoublonnage intelligent.

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
**Le scénario :** Luc soumet ses preuves (`PENDING_DM_REVIEW`). Sarah part en congé sans déléguer ses droits. L'ordonnanceur asynchrone détecte l'échéance : le délai initial est franchi, le système ajoute le flag `OVERDUE` avec notification à la DG. À son retour, Sarah ouvre le dossier, trouve les preuves incomplètes, et clique sur "Rejeter" avec le motif "Signature DSI manquante". Le statut repasse à `IN_PROGRESS` (les preuves rejetées sont taguées `REJECTED_V1` et restent visibles dans l'historique). Luc doit fournir de nouvelles preuves.
**Bénéfice :** La FSM attribue factuellement le goulot d'étranglement au bon acteur (Sarah) sans bloquer l'exécutant éternellement dans le silence.

### 3. Parcours de l'Auditeur Externe : La Mission COBAC (Compliance Path)
**Persona impliqué :** M. Atangana (Inspecteur COBAC).
**Le scénario :** M. Atangana effectue un contrôle inopiné à la BICEC. Il reçoit un accès "Auditeur Externe" (Lecture seule cloisonnée par RLS). Via le module de filtrage, il isole son périmètre de mission et consulte les recommandations avec leurs preuves associées. Il peut télécharger les pièces jointes de son périmètre. **L'audit trail (journal des actions internes) n'est pas accessible** — seul un résumé de conformité (statut, dates clés, hash SHA-256 de clôture) lui est présenté.
**Bénéfice :** Transparence suffisante pour le régulateur avec preuve d'intégrité cryptographique, tout en préservant la confidentialité du processus interne de la banque.

### Journey Requirements Summary
Ces parcours utilisateurs induisent des exigences techniques spécifiques pour l'implémentation :
- **Délégation Asynchrone :** Gérer l'affectation N+1 -> N (fonctionnalité de co-affectation ou assignation d'ETP).
- **Historisation des Rejets :** Versioning des soumissions (un ETP peut soumettre N fois le même dossier avec des commentaires/preuves différents suite à des rejets).
- **Gestion de l'Intérim :** Nécessité absolue d'un mécanisme de délégation temporaire des droits de validation (vacances DM).
- **Export Zip Synchrone :** Téléchargement direct HTTP de l'archive. L'infrastructure réseau LAN Gigabit On-Premise de la BICEC rend un service de génération asynchrone en arrière-plan superflu pour le MVP.

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
  - *Option B (Java Spring Boot) :* Si la Direction IT de la BICEC impose le langage Java par standardisation. Spring State Machine est exceptionnellement robuste pour garantir l'inaltérabilité des 5 états du cycle de vie. Mais c'est un choix plus "lourd" à démarrer que Django.

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
- FSM 5 états + flag `OVERDUE` et RBAC 6 profils.
- Base de données Single-Tenant avec Row-Level Security.
- Frontend Single Page Application optimisé pour la fluidité.
- Scheduler asynchrone interne (Alertes J-7 & basculement `OVERDUE` & rappels quotidiens).
- Architecture "API Régulateur Ready" (Module d'export natif).
- Interface d'administration pour gestion 100% manuelle de l'organigramme.
- Module central d'Import Massif d'Historique (Excel) pour intégrer les encours existants.

### Post-MVP Features
**Phase 2 (Growth):**
- Portail DMZ "Read-Only" pour auditeurs externes non-salariés.
- Seuils de relance proportionnels (40/60/80%) avec dédoublonnage intelligent.
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
- FR7: L'Audit Interne peut créer une nouvelle recommandation et l'assigner à une Direction Métier avec une échéance fixée. La création exige les champs suivants :

  | Champ | Type | Obligatoire | Description |
  |---|---|---|---|
  | `titre` | Texte (255 car.) | ✅ | Intitulé de la recommandation |
  | `description` | Texte long | ✅ | Corps détaillé de la recommandation |
  | `source` | Enum | ✅ | COBAC / BEAC / NIF / CAC / Consultant Externe / Audit Interne |
  | `categorie` | Enum | ✅ | Ex : Crédit, Opérationnel, Conformité, Trésorerie… (configurable) |
  | `priorite` | Enum | ✅ | Critique / Haute / Moyenne / Faible |
  | `date_emission` | Date | ✅ | Date d'émission officielle de la recommandation |
  | `date_echeance` | Date | ✅ | Délai de résolution fixé |
  | `directeur_metier` | FK User (DM) | ✅ | DM affecté à cette recommandation |
  | `reference_externe` | Texte | ✅ | Référence officielle du régulateur (ex: COBAC-2025-REF-042) |
  | `document_source` | Fichier | ✅ | Document officiel source (rapport d'inspection, etc.) |
  | `tags` | Texte[] | ❌ | Tags optionnels pour faciliter la recherche et le filtrage |

- FR8: Le Directeur Métier peut réassigner une recommandation reçue à **un seul** Employé Traitant (ETP) de son équipe. *Note MVP : une recommandation = un seul ETP.*
- FR9: L'Employé Traitant peut soumettre des preuves pour demander la clôture d'une recommandation. La soumission exige un **commentaire justificatif obligatoire** (minimum 50 caractères) expliquant comment la preuve répond à la recommandation. La soumission est bloquée sans ce champ.
- FR9b: L'Employé Traitant peut **sauvegarder en brouillon** ses preuves et commentaires avant de soumettre définitivement.
- FR10: L'Employé Traitant peut soumettre de nouvelles versions de preuves sur une même recommandation s'il subit un rejet hiérarchique, créant ainsi un cycle itératif d'allers-retours tracé jusqu'à l'obtention d'une validation.
- FR11: Le Directeur Métier peut valider ou rejeter la preuve soumise par son Employé Traitant. **Tout rejet nécessite un motif obligatoire** — le rejet est bloqué sans motif renseigné. En cas de rejet, le statut **repasse à `IN_PROGRESS`** et les preuves rejetées sont taguées (`REJECTED_V1`, `REJECTED_V2`…) et restent visibles dans l'historique. Le DM peut optionnellement joindre un PV de recette lors de l'approbation.
- FR12: L'Audit Interne peut valider ou rejeter la preuve avalisée par le Directeur Métier. **Tout rejet nécessite un motif obligatoire.** En cas de rejet, le statut **repasse à `IN_PROGRESS`** (les preuves rejetées sont taguées et historisées). Lors de la validation, l'Audit Interne doit définir un **taux de réalisation** (0–100%). Une clôture partielle est possible si le taux est jugé acceptable. Ce taux est figé dans l'audit trail à la clôture.
- FR13 *(Modification unilatérale de l'échéance par l'Audit)* : L'Audit Interne peut modifier la date limite d'une recommandation active dans les deux sens (avancer ou reculer), sous réserve d'une justification obligatoire et tracée dans l'historique. C'est un pouvoir régalien de l'Audit.
- FR13b *(Demande de prolongation soumise par le Métier)* : Le DM ou l'ETP peut **soumettre une demande formelle de prolongation de délai** via le système. Cette demande est notifiée à l'Audit Interne qui peut l'approuver ou la refuser (avec motif obligatoire). L'ensemble du workflow de prolongation est tracé dans l'audit trail.
- FR14: L'Audit Interne peut clôturer positivement la recommandation (`CLOSED_RESOLVED`) après validation des preuves, avec attribution du taux de réalisation.
- FR14b: La réaffectation d'une recommandation d'un DM vers un autre DM nécessite la **validation explicite de l'Audit Interne**. Elle est tracée dans l'audit trail avec justification.
- FR15: L'Audit Interne peut forcer la clôture d'une recommandation (ex: inspection inopinée terrain prouvant la résolution) sans nécessiter de soumission préalable par l'ETP/DM.( à discuter)

### 3. Proofs & Audit Trail

> [!IMPORTANT]
> **Restriction d'accès à l'Audit Trail :** L'audit trail (journal des actions) est **exclusivement consultable par l'Audit Interne**. Les Auditeurs Externes, les Directeurs Métiers (DM) et les Employés Traitants (ETP) n'ont **aucun accès** en lecture à l'audit trail. Les DM et ETP voient uniquement l'historique des preuves et des statuts de leurs recommandations, sans le détail du journal d'audit. Les Auditeurs Externes accèdent aux preuves et à une synthèse de conformité (statut, dates clés, hash SHA-256).
- FR16: Les Utilisateurs peuvent uploader des fichiers multiformats (PDF, DOCX, XLSX, JPEG, PNG, TXT, LOG) en pièce jointe lors d'une soumission de preuve. Chaque preuve est horodatée (timestamp UTC) et associée à l'utilisateur qui l'a uploadée.
- FR17: Toutes les preuves soumises (acceptées ou rejetées) restent archivées et indélébiles (principe **append-only**). Toute suppression de preuve est techniquement impossible. Un utilisateur peut soumettre des preuves complémentaires en cas de rejet, sans effacer les précédentes.
- FR18: Le Système génère une empreinte cryptographique (SHA-256) par recommandation :
  - **Hash par recommandation :** À la clôture, un hash final est calculé sur l'ensemble de l'audit trail de cette recommandation. Ce hash est permanent et figé.

  ```
  Recommandation #INT-2026-042
  │
  ├── Action 1 : Création par Marc         (01/03 09:00)
  ├── Action 2 : Affectation à Sarah       (01/03 09:01)
  ├── Action 3 : Délégation à Luc          (01/03 10:30)
  ├── Action 4 : Soumission preuves Luc    (05/03 14:00)
  ├── Action 5 : Validation Sarah          (06/03 11:00)
  └── Action 6 : Clôture Marc              (07/03 16:00)
            │
            ▼
     SHA-256 de TOUT ça
            │
            ▼
     hash_final = "a3f8c2d9..." ← FIGÉ DÉFINITIVEMENT
  ```

  - **Chaînage :** Chaque entrée de l'audit trail inclut le hash de l'entrée précédente (`hash_precedent`), formant une chaîne cryptographique. Toute altération d'une entrée historique invalide les hashes de toutes les entrées suivantes.
- FR19: Le Système enregistre un journal immuable de chaque événement du workflow. Chaque entrée de l'audit trail contient :

  | Champ | Description |
  |---|---|
  | `id_action` | Identifiant unique de l'action |
  | `timestamp` | Horodatage UTC précis (millisecondes) |
  | `utilisateur_id` | ID de l'acteur |
  | `utilisateur_nom` | Nom complet (snapshot au moment de l'action) |
  | `role_contexte` | Rôle de l'acteur sur cette recommandation au moment de l'action |
  | `type_action` | Enum : création, affectation, soumission_preuve, validation, rejet, clôture, prolongation, réaffectation, etc. |
  | `statut_avant` | Statut de la recommandation avant l'action |
  | `statut_apres` | Statut de la recommandation après l'action |
  | `commentaire` | Commentaire justificatif ou motif (quand applicable) |
  | `fichiers_joints` | Liste des fichiers joints à cette action |
  | `hash_precedent` | Hash SHA-256 de l'entrée précédente (chaînage) |
  | `hash_courant` | Hash SHA-256 de l'entrée courante |

- FR20: Le Système applique la Séparation des Tâches (SoD) selon le contexte :
  - **Cas ETP → DM → Audit :** Un ETP ne peut pas valider ses propres preuves au niveau DM. La validation métier est assurée par le DM.
  - **Cas DM traite lui-même :** Lorsque le DM prend en charge directement une recommandation (sans délégation à un ETP), sa soumission de preuves **passe directement en `PENDING_AUDIT_REVIEW`**, sautant l'étape de validation métier. La SoD est garantie par l'Audit Interne qui reste le valideur final indépendant.
  - **Invariant :** Aucun acteur ne peut être à la fois soumetteur de preuve ET valideur sur le même dossier au même niveau hiérarchique.

### 4. Notifications (In-App & Email) & Scheduler
- FR21: Le Système envoie des alertes emails internes sécurisées (serveur SMTP interne BICEC) aux acteurs dès qu'une action est requise de leur part.
- FR22: Le Système expose un "Centre de Notifications In-App" comportant : une icône avec badge (non-lus), une liste chronologique cliquable redirigeant vers la recommandation, et une conservation des logs de 90 jours.
- FR23: Le Système émet un rappel automatique **J-7** avant l'échéance aux DM + ETP + Audit Interne concernés. *Post-MVP : ajout de seuils proportionnels (40/60/80% du délai) avec dédoublonnage intelligent.*
- FR24: Le Système bascule automatiquement le flag `OVERDUE` (En Retard) si le délai d'échéance est franchi. Le flag `OVERDUE` est **superposé** aux autres statuts — une recommandation peut être simultanément `PENDING_AUDIT_REVIEW` ET `OVERDUE`. Un rappel quotidien est envoyé tant que le retard persiste.

**Matrice des Notifications :**

| Événement | Destinataire(s) | Trigger |
|---|---|---|
| Nouvelle recommandation affectée | DM concerné | Immédiat |
| Délégation vers ETP | ETP concerné | Immédiat |
| Preuve soumise par ETP | DM concerné | Immédiat |
| Preuve validée par DM | Audit Interne | Immédiat |
| Rejet DM → ETP (retour `IN_PROGRESS`) | ETP concerné | Immédiat |
| Rejet Audit → DM/ETP (retour `IN_PROGRESS`) | DM + ETP concernés | Immédiat |
| Recommandation clôturée | DM + ETP + Audit Interne | Immédiat |
| Alerte J-7 avant échéance | DM + ETP + Audit Interne | Automatique |
| Dépassement d'échéance (`OVERDUE`) | DM + ETP + Audit Interne | Immédiat + rappel quotidien |
| Remontée hiérarchique (absence) | Supérieur hiérarchique | Immédiat |
| Demande de prolongation soumise | Audit Interne | Immédiat |
| Prolongation approuvée/refusée | Demandeur (DM/ETP) | Immédiat |

### 5. Reporting, Dashboards & Exports
- FR25: Le Système génère des indicateurs calculant le temps passé dans les goulots d'étranglement de validation (< 48h) et les KPIs opérationnels définis dans la section Success Criteria.
- FR26: Le Système affiche des tableaux de bord distincts par profil :

  **Dashboard Audit Interne / Direction Générale :**
  | Widget | Description |
  |---|---|
  | Répartition par statut | Graphique en secteurs ou barres : nombre de recos par statut |
  | Taux de clôture global | % de recos clôturées sur total actif |
  | Taux de clôture par source | Comparatif COBAC / BEAC / CAC / Interne / NIF / Consultants |
  | Progression par Direction Métier | Tableau : chaque DM, nb de recos, % clôturé, nb en retard |
  | Recommandations en retard | Liste filtrée avec responsable, date d'échéance, jours de retard |
  | Taux de rejet Audit vs Métier | Indicateurs de qualité du circuit de validation |
  | Délai moyen de résolution | Délai global et par DM / ETP |
  | Alertes actives | J-7, dépassements — liste consolidée |

  **Dashboard Directeur Métier (DM) :**
  - Liste "À valider" (en attente de sa validation)
  - Liste de toutes ses recommandations avec statut en temps réel
  - % de progression de son périmètre
  - Alertes sur ses échéances à venir

  **Dashboard ETP (vue "To-Do") :**
  - Liste des recommandations assignées avec statut et délai
  - Indicateur visuel d'urgence (Normal / Bientôt / En retard)
  - Accès direct à la soumission de preuves

- FR27: Le Système supporte 4 types d'exports :

  | Export | Format | Déclencheur | Destinataire |
  |---|---|---|---|
  | Dossier complet d'une recommandation (preuves + synthèse de conformité, **sans audit trail**) | PDF | À la demande, sur toute reco clôturée ou active | Audit Interne, Auditeur Externe |
  | Liste filtrée des recommandations | Excel (.xlsx) | À la demande avec filtres actifs | Audit Interne, DG |
  | Rapport de synthèse | PDF | À la demande (période choisie) | DG, Comité de Direction |
  | Audit trail brut | CSV ou JSON | À la demande (par reco ou par période) | **Audit Interne uniquement** |

- FR28: L'Auditeur Externe accède en lecture seule stricte aux recommandations de son périmètre préalablement défini par l'Audit Interne. **L'Auditeur Externe ne peut pas consulter l'audit trail (journal des actions).** Il a accès uniquement aux preuves, aux statuts et à une fiche de synthèse de conformité (dates clés + hash SHA-256 de clôture). Les Auditeurs Externes utilisent des credentials locaux gérés par l'Admin IT (hors Active Directory).
- FR29: L'Auditeur Externe peut télécharger les preuves rattachées aux recommandations de son périmètre d'inspection.
- FR30 (MVP simplifié) : L'Audit Interne peut 
générer et télécharger une archive ZIP d'une 
recommandation clôturée contenant : Le journal d'audit en PDF, toutes les preuves soumises, Le hash SHA-256 final de référence



### 6. Data Initialization (MVP)
- FR32 : Le Support/RSSI, sous supervision 
de l'Audit Interne, peut importer 
massivement les recommandations historiques 
via un fichier Excel/CSV conforme au 
template fourni par Sentinel.

Règles d'import :
1. Un template Excel normalisé est fourni
   par le système (colonnes et formats fixes)

2. Seul l'Audit Interne peut déclencher
   l'import final (pas le Support seul)

3. Toute recommandation importée entre en 
   statut ASSIGNED avec un tag "IMPORTED" 
   permanent dans l'audit trail


## Règles Métier Critiques

Les règles suivantes constituent des invariants du système qui ne doivent jamais être contournés :

| # | Règle | Description |
|---|---|---|
| R1 | Commentaire justificatif obligatoire | Tout ETP soumettant des preuves doit renseigner un commentaire ≥ 50 caractères. La soumission est bloquée sans ce champ. |
| R2 | Motif de rejet obligatoire | Tout rejet (DM → ETP ou Audit → DM/ETP) nécessite un motif. Le rejet est bloqué sans motif. |
| R3 | Taux de réalisation | Seul l'Audit Interne définit un taux (0–100%) à la clôture. Figé dans l'audit trail. |
| R4 | Réaffectation entre DM | Nécessite la validation explicite de l'Audit Interne. Tracée dans l'audit trail. |
| R5 | Un ETP par recommandation (MVP) | Une recommandation est assignée à un seul ETP. Multi-ETP prévu en Post-MVP. |
| R6 | Flag `OVERDUE` superposé | Calculé automatiquement par le système. Superposé aux autres statuts actifs. |
| R7 | Remontée hiérarchique automatique | En cas d'absence (flag activé par l'Admin), les recos remontent au supérieur hiérarchique avec notification. |
| R8 | Versioning des preuves rejetées | Tout rejet (DM ou Audit) ramène le statut à `IN_PROGRESS`. Les preuves rejetées sont taguées (`REJECTED_V1`, `REJECTED_V2`…) et restent visibles dans l'historique. |
| R9 | Prolongation et retard | Quand une prolongation est approuvée sur une reco en `OVERDUE`, le flag est automatiquement recalculé. Si la nouvelle échéance est dans le futur, le flag `OVERDUE` est retiré. L'historique de retard reste conservé dans l'audit trail. |

## Non-Functional Requirements (NFR)

| Contrainte | Cible |
|---|---|
| Disponibilité | 99.5% pendant les heures ouvrables (lun–ven, 7h–20h) |
| Performance pages | Chargement d'une page < 2 secondes |
| Performance exports | Génération de PDF < 30 secondes |
| Sécurité réseau | HTTPS obligatoire |
| Sécurité données | Chiffrement des données au repos (AES-256) |
| Session timeout | Expiration après 30 minutes d'inactivité (configurable) |
| Sauvegarde | Backup quotidien automatique + vérification d'intégrité |
| Scalabilité | Supporter jusqu'à 200 utilisateurs simultanés |
| Journal système | Toute connexion/déconnexion est tracée dans le journal système |

## Conformité Réglementaire

### Conformité Loi Camerounaise 2024-017

| Exigence | Implémentation Sentinel |
|---|---|
| Hébergement des données personnelles | On-Premise — serveurs BICEC en territoire camerounais |
| Contrôle d'accès strict | 6 profils RBAC + RLS par recommandation |
| Traçabilité des accès | Journal système : toute consultation est enregistrée |
| Consentement & finalité | Usage interne délimité, données liées au contexte professionnel |
| Droit d'accès / rectification | Processus défini via le support IT/RSSI |

### Conformité COBAC R-2023/01

| Exigence | Implémentation Sentinel |
|---|---|
| Traçabilité du cycle de vie | Audit trail exhaustif par recommandation (12 champs) |
| Preuve de mise en œuvre des corrections | Preuves multi-formats + commentaires justificatifs ≥ 50 car. |
| Valeur probatoire des documents | Hash SHA-256 chaîné par recommandation — intégrité vérifiable |
| Accès des inspecteurs | Portail Read-Only dédié avec credentials locaux + exports (preuves et synthèse de conformité — **audit trail exclu**) |

## Critères d'Acceptance du MVP

### Critères Fonctionnels
- ✅ Une recommandation peut être créée, affectée, traitée et clôturée de bout en bout sans sortir de Sentinel.
- ✅ L'audit trail de chaque recommandation clôturée contient 100% des actions avec hash SHA-256 vérifiable.
- ✅ Un Auditeur Externe peut se connecter, visualiser un dossier autorisé, consulter les preuves et télécharger une synthèse de conformité (**sans accès à l'audit trail**).
- ✅ Les alertes J-7 sont envoyées automatiquement par email ET in-app aux bons destinataires.
- ✅ Le flag `OVERDUE` est activé automatiquement au dépassement d'échéance avec rappels quotidiens.
- ✅ Un rapport de synthèse PDF peut être généré en moins de 30 secondes.
- ✅ L'ETP peut sauvegarder un brouillon avant soumission définitive.

### Critères Réglementaires
- ✅ La BICEC peut démontrer à un inspecteur COBAC/BEAC : qui a fait quoi, quand, avec quelles preuves, sur chaque recommandation.
- ✅ L'intégrité de l'audit trail est vérifiable via le hash SHA-256 chaîné.
- ✅ Excel n'est plus utilisé pour le suivi centralisé (adoption ≥ 95% à J+30).

### Critères Techniques
- ✅ L'application fonctionne entièrement On-Premise sur l'infrastructure BICEC.
- ✅ L'authentification SSO via Active Directory est opérationnelle.
- ✅ Les temps de réponse respectent les cibles NFR (pages < 2s, PDF < 30s).
- ✅ Les backups quotidiens sont configurés et testés.

## Glossaire

| Terme | Définition |
|---|---|
| AI | Audit Interne BICEC |
| DM | Directeur Métier — responsable d'une direction opérationnelle |
| ETP | Employé Traitant — collaborateur opérationnel chargé de l'exécution |
| DG | Direction Générale |
| CAC | Commissaires aux Comptes |
| COBAC | Commission Bancaire de l'Afrique Centrale |
| BEAC | Banque des États de l'Afrique Centrale |
| NIF | Numéro d'Identification Fiscale (autorité fiscale camerounaise) |
| CEMAC | Communauté Économique et Monétaire de l'Afrique Centrale |
| SHA-256 | Algorithme de hachage cryptographique (Secure Hash Algorithm 256 bits) |
| On-Premise | Hébergement sur les serveurs physiques internes de la BICEC |
| Audit Trail | Journal immuable et horodaté de toutes les actions sur une recommandation |
| Taux de réalisation | Pourcentage d'accomplissement, défini par l'Audit Interne à la clôture |
| SSO | Single Sign-On — authentification unique via Active Directory |
| PV de recette | Procès-Verbal de Recette — document optionnel joint par le DM |
| Append-only | Principe d'architecture où les données ne peuvent être qu'ajoutées, jamais modifiées ou supprimées |
| RCC | Responsable du Contrôle de Conformité — profil Admin dans Sentinel |
| FSM | Finite State Machine — machine à états finis régissant le cycle de vie |
| RLS | Row-Level Security — cloisonnement des données au niveau de la base de données |
| SoD | Separation of Duties — séparation des tâches |
