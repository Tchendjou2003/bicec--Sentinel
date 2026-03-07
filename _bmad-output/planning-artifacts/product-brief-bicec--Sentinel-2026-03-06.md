---
stepsCompleted: [1, 2, 3]
inputDocuments: []
date: 2026-03-06
author: Dave Lahe
---

# Product Brief: Sentinel — BICEC

## Executive Summary

Sentinel est une application web interne développée pour la BICEC afin de centraliser,
orchestrer et tracer le cycle de vie complet des recommandations d'audit bancaire —
qu'elles soient émises par l'Audit Interne, les Commissaires aux Comptes (CAC),
la COBAC, la BEAC, la NIF ou des consultants externes.

Face à une réglementation bancaire de plus en plus exigeante dans l'espace CEMAC
(COBAC R-2023/01, CEMAC, loi camerounaise 2024-017), la BICEC ne peut plus se
permettre un suivi fragmenté reposant sur des fichiers Excel, des emails informels
et des relances manuelles. **Sentinel transforme cette contrainte réglementaire en un
dispositif de contrôle maîtrisé, démontrable et auditable.**

> **Proposition de valeur centrale :** Sentinel n'est pas un outil de productivité,
> c'est une **assurance contre les sanctions réglementaires**. Son ROI est assurantiel :
> une seule sanction COBAC évitée couvre plusieurs années d'exploitation.

---

## Core Vision

### Problème Central

Sans système centralisé dédié, le suivi des recommandations d'audit à la BICEC
repose entièrement sur des canaux informels (emails, Excel partagé, réunions).
Cette fragmentation crée trois risques majeurs :

1. **Risque réglementaire** : incapacité à démontrer aux inspecteurs COBAC/BEAC
   qui a traité quelle recommandation, quand et avec quelles preuves — en violation
   directe du règlement COBAC R-2023/01.
2. **Risque opérationnel** : des recommandations critiques restent sans surveillance
   effective, leurs délais de correction dépassés sans alerte ni escalade.
3. **Risque de gouvernance** : la Direction Générale et l'Audit Interne ne disposent
   d'aucune vue consolidée fiable sur le taux de couverture réel des contrôles.

### Impact du Problème

- Impossibilité de produire des rapports d'avancement fiables pour les instances
  de gouvernance
- Exposition directe à des sanctions réglementaires lors des contrôles COBAC/BEAC
- Fragilisation du dispositif de contrôle interne au sens de la réglementation CEMAC
- Non-conformité potentielle à la loi camerounaise 2024-017 sur la protection
  des données personnelles (au-delà du seul hébergement : contrôle d'accès,
  consentement, traçabilité des accès)

### Pourquoi les Solutions Actuelles Échouent

Il n'existe pas à ce jour d'outil dédié, spécialisé et conforme aux exigences
réglementaires CEMAC/COBAC disponible pour les banques de la sous-région.
Les outils internationaux (MetricStream, Rsam, etc.) sont :
- Trop coûteux pour le contexte camerounais
- Non adaptés au cadre réglementaire local (COBAC, BEAC, CEMAC)
- Non configurés pour les exigences de souveraineté des données (On-Premise)
- Sans support pour les flux de travail spécifiques à l'audit bancaire CEMAC

Excel n'est pas une alternative : il ne génère pas de hash SHA-256, n'envoie pas
d'alertes J-30 avant échéance, et ne constitue aucune preuve opposable devant
un inspecteur COBAC.

### Solution Proposée

Sentinel est une plateforme web On-Premise qui orchestre le cycle de vie complet
de chaque recommandation d'audit, de son émission jusqu'à sa clôture définitive.

**Principe de design fondamental : l'utilisation est obligatoire par construction.**
Les validations officielles, les soumissions de preuves et les approbations NE PEUVENT
se faire qu'à travers Sentinel — ce qui garantit l'adoption et l'intégrité des données.

Fonctionnalités clés :
- Workflow structuré multi-acteurs avec 6 profils distincts (cf. section Utilisateurs)
- Rôles multi-contextuels : un utilisateur peut être DM sur une recommandation
  et ETP sur une autre selon le contexte
- Collecte sécurisée de preuves multi-formats (PDF, Word, Excel, Images, Logs)
- Audit Trail immuable horodaté et haché (SHA-256 chaîné) par action
- Tableaux de bord temps réel et rapports automatisés PDF/Excel
- Authentification SSO via Active Directory BICEC existant
- Hébergement On-Premise avec module de gestion des accès aux données
  (conformité complète loi 2024-017)

### Différenciateurs Clés

| Différenciateur | Détail |
|---|---|
| **Conformité CEMAC native** | Conçu dès la base pour les exigences COBAC R-2023/01 et CEMAC |
| **Audit Trail cryptographique** | SHA-256 chaîné — chaque action est immuable et vérifiable |
| **On-Premise souverain complet** | Hébergement interne + contrôle d'accès conforme loi 2024-017 |
| **Usage obligatoire par design** | Les flux officiels ne peuvent passer que par Sentinel |
| **Multi-sources d'audit** | Interne + CAC + COBAC + BEAC + NIF + Consultants en un seul outil |
| **Rôles contextuels flexibles** | Un utilisateur peut avoir plusieurs rôles selon les recommandations |

---

## Hypothèses & Risques Critiques

### Hypothèses Fondamentales

| Hypothèse | Vérité fondamentale | Implication design |
|---|---|---|
| La BICEC a besoin d'un outil | La BICEC a une **obligation légale** de démontrer la mise en œuvre | L'outil est le moyen, la conformité est la fin |
| Un système centralisé suffit | La centralisation sans usage est pire qu'Excel (fausse sécurité) | L'utilisation doit être obligatoire par construction |
| 6 rôles fixes et étanches | Les acteurs peuvent jouer plusieurs rôles selon les recommandations | Rôles multi-contextuels nécessaires |
| On-Premise = conformité 2024-017 | La loi exige aussi contrôle d'accès, consentement, traçabilité accès | Module de gestion des droits d'accès requis dès le MVP |

### Risques Critiques Identifiés

| # | Risque | Probabilité | Prévention |
|---|---|---|---|
| 1 | **Adoption nulle** — Les ETP continuent par email | Élevée | Les validations officielles ne peuvent se faire que via Sentinel |
| 2 | **Périmètre non maîtrisé** — Features creep en cours de projet | Moyenne | MVP strict défini dans le PRD. Toute extension = nouvelle version. |
| 3 | **Valeur juridique SHA-256 non reconnue** | Faible mais critique | Validation avec le département juridique BICEC avant le lancement |
| 4 | **Perte de données historiques** | Faible | Architecture append-only + backups quotidiens + aucune suppression physique |
| 5 | **Résistance des Directeurs Métier** | Moyenne | Dashboards DM centrés sur la progression, non sur l'exposition aux retards |

---

## Target Users

### Primary Users

**1. Jean-Paul M. — Chef de Mission, Audit Interne** *(Chef d'orchestre)*
- **Contexte :** Responsable de la coordination de toutes les recommandations. Gère une quarantaine de recommandations actives simultanément, de sources multiples (COBAC, interne, CAC).
- **Douleur actuelle :** Passe 30% de son temps à relancer manuellement par email, à consolider des fichiers Excel de chaque département.
- **Succès Sentinel :** Ouvre son dashboard le matin pour voir les recommandations en retard ou en attente d'audit final. Relances automatiques. Rapport COBAC généré en 2 clics.

**2. Claire D. — Directrice des Opérations** *(Directeur Métier)*
- **Contexte :** Reçoit les affectations d'Audit Interne et gère la résolution au niveau de sa direction. Supervise les sous-directions et ETPs.
- **Douleur actuelle :** Délègue oralement, transfert des emails. Difficile de suivre l'avancement avant l'échéance.
- **Succès Sentinel :** Dashboard temps-réel sur l'état des recommandations affectées. Permet de réaffecter facilement (cascading) vers ses équipes. Contrôle qualité (via PV de recette) avant soumission finale à l'Audit.

**3. Marc T. — Chargé de Conformité / Opérationnel** *(ETP / Sous-direction)*
- **Contexte :** Traite les recommandations assignées par son DM. Responsable de produire et joindre les évidences/preuves.
- **Douleur actuelle :** Envoie les preuves par mail sans savoir si elles suffisent. Recommence en cas de feedback flou.
- **Succès Sentinel :** Actions claires exigées, upload de preuves multi-format. Validation instantanée de "soumission de travail", suivi clair en cas de demande de compléments d'informations.

### Secondary Users

**4. Dr. Emmanuel K. — Directeur Général Adjoint** *(Direction Générale)*
- **Usage :** Vue Macro. Taux de progression, risques majeurs restants ou dépassements critiques. Interface Dashboard pure.

**5. Inspecteur Martin N. — Contrôleur COBAC/BEAC** *(Auditeur Externe)*
- **Usage :** Accès de consultation Read-Only ciblé. Accès transparent à l'audit trail et aux preuves certifiées pour les missions de contrôle sur place.

**6. Sandra O. — Admin IT** *(Support / RCC)*
- **Usage :** Maintien du SSO, gestion en cas de modification d'organigramme (turnover), supervision de sécurité.

### User Journey : Cycle de traitement de la recommandation d'audit

1. **RÉCEPTION / LANCEMENT :** Une recommandation de contrôle (interne/COBAC/autres) est enregistrée par l'Audit Interne dans Sentinel, catégorisée et affectée à un **Directeur Métier (DM)** avec un délai.
2. **AFFECTATION / DÉLÉGATION :** Le DM examine la recommandation. Il peut la traiter lui-même **OU** la déléguer à une sous-direction métier ou un collaborateur opérationnel (**ETP**) pour exécution.
3. **EXÉCUTION (Niveau Opérationnel) :** L'ETP étudie la recommandation, exécute les mesures correctives et charge les preuves (PDF, images, logs, etc.) dans Sentinel. **Il doit obligatoirement inclure un commentaire justificatif expliquant comment la preuve répond à la recommandation.** Il valide ensuite opérationnellement son travail pour avertir sa direction. *(Statut : "En attente validation Métier")*
4. **DOUBLE VALIDATION (Métier puis Audit) :**
   - **Check Métier :** Le DM vérifie les preuves fournies par son équipe (éventuellement appuyé par un PV de recette).
     - Si insuffisant : Rejet vers l'ETP (retour à l'étape 3).
     - Si valide : Approbation et transmission à l'Audit Interne. *(Statut : "En attente validation Audit")*
   - **Check Audit :** L'Audit (Jean-Paul) réalise la revue finale.
     - Si preuve insuffisante : "Délai supplémentaire / À compléter", avec retour direct à la Direction Métier ou à l'ETP.
     - Si rejet net : Motif fourni, retour à l'étape 3.
     - Si valide (Taux plein ou partiel acceptable) : Acceptation.
5. **CLÔTURE :** La recommandation obtient le statut **Clôturée**. L'**Audit Trail complet est généré au format immuable (avec SHA-256)** retraçant formellement tout le parcours et ses acteurs.

---

## Success Metrics

### Business Objectives

1. **Zéro sanction réglementaire** liée à un défaut de traçabilité lors des prochains contrôles COBAC/BEAC.
2. **Couverture à 100%** de toutes les nouvelles recommandations d'audit dans Sentinel dès le déploiement (abandon total d'Excel/Emails pour les processus officiels).
3. **Réduction drastique du temps de reporting** pour la préparation des comités de direction et des réponses aux régulateurs.

### User Success Metrics

- **Audit Interne (Jean-Paul) :** Le temps passé à relancer ou chercher des preuves chute de 30% du temps de travail à moins de 5%.
- **Direction Métier (Claire) :** Capacité à connaître l'état précis (en cours, clôturé, en retard) de 100% de son périmètre en moins de 1 minute.
- **Opérationnel (Marc) :** Zéro "preuve perdue" ou feedback ignoré ; chaque ETP a une liste de tâches claire ("To-Do") avec des délais fermes.

### Key Performance Indicators (KPIs)

*Le North Star Metric n'est pas le temps gagné, mais la "Réduction du délai moyen d'éradication d'un risque critique" et "100% de conformité de l'audit trail".*

| KPI | Description | Cible à 6 mois |
|---|---|---|
| **Taux d'adoption active** | % d'ETP et DM se connectant au moins 1x/semaine | > 95% |
| **Délai moyen de résolution** | Taux de recos clôturées avant la date d'échéance | > 85% à l'heure |
| **Taux de Rejet par l'Audit** | % de preuves validées par le DM mais rejetées par l'Audit (mesure de la qualité de la validation métier) | < 5% |
| **Taux de Rejet Métier** | % de preuves rejetées par le DM vers l'ETP (mesure la clarté de la requête initiale) | < 15% |
| **Durée moyenne par statut** | Temps passé à une étape donnée (ex: "En attente validation DM"). Plus précis que le retard global pour identifier les goulots d'étranglement | < 48 heures / statut |
| **Taux de reports justifiés tracés** | % de retards ayant fait l'objet d'une demande de délai supplémentaire approuvée dans le système | > 90% des retards |

---

## MVP Scope

### Core Features

Pour que Sentinel atteigne ses objectifs réglementaires dès le jour 1, voici les fonctionnalités incontournables :

1. **Gestion Centralisée Multi-Sources**
   - Suivi des recommandations **Externes** (COBAC, BEAC, NIF, CAC, Consultants).
   - Suivi des recommandations **Internes** (issues des missions sur le terrain de l'Audit Interne BICEC).
2. **Workflow de Double Validation**
   - Affectation et délégation en cascade (Audit → DM → ETP/Sous-direction).
   - Soumission de preuves (PDF, Images, etc.) avec champ de commentaire justificatif obligatoire.
   - Circuit d'approbation strict avec motifs de rejet obligatoires.
3. **Traçabilité Extrême et Journal d'Audit (Audit Trail)**
   - Journal d'audit complet retraçant chaque action (utilisateur, horodatage, action).
   - Génération de l'empreinte cryptographique (SHA-256) à la clôture de la recommandation.
4. **Portail Auditeur Externe (Régulateurs)**
   - Accès de consultation sécurisé (Read-Only).
   - **Capacité d'exportation** : Les auditeurs externes peuvent visualiser, télécharger et exporter les dossiers de preuves et le journal d'audit justifiant la clôture.
5. **Tableaux de bord & Gouvernance**
   - Vues "To-Do" pour les opérationnels (ETP, DM).
   - Vues de supervision globales pour la Direction Générale et l'Audit Central.
6. **Sécurité et Accès (Loi 2024-017)**
   - Authentification via SSO Active Directory BICEC.
   - Gestion stricte de 6 profils et des délégations (intérim en cas d'absence).

### Out of Scope for MVP

Ces éléments sont repoussés à des itérations ultérieures pour garantir la livraison rapide du cœur de conformité :
- *Génération automatique des rapports réglementaires annuels pré-formatés* (L'export Excel/PDF brut du système suffira pour le MVP).
- *Notifications automatiques par SMS ou WhatsApp* (Alertes in-app ou Email suffiront).
- *Reconnaissance Optique de Caractères (OCR)* pour valider automatiquement des documents scannés.
- *Intégration API temps-réel avec le Core Banking System (Amplitude ou autre).*

### MVP Success Criteria

Le MVP sera considéré comme achevé et réussi lorsque :
- La BICEC pourra abandonner *définitivement* l'usage d'Excel pour le suivi centralisé.
- La COBAC/BEAC validera formellement la valeur probatoire de l'Audit Trail et du système d'export des preuves fourni par Sentinel.

### Future Vision

Si le MVP valide son adoption interne et sa conformité réglementaire :
- **Commercialisation SaaS On-Premise :** Sentinel pourrait devenir un hub de conformité standard proposé aux autres banques de la place CEMAC.
- **Intégration I.A. de Conformité :** Capacité algorithmique à suggérer si une preuve attachée est pertinente vis-à-vis du texte de la recommandation initiale.
- **Cartographie des Risques :** Lier dynamiquement les recommandations non-clôturées à la cartographie des risques opérationnels globale de la banque.

<!-- Content will continue to be appended sequentially through collaborative workflow steps -->
