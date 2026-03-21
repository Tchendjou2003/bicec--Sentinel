---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
date: 2026-03-20
author: Dave Lahe
---

# Product Brief: Sentinel — BICEC (v2)

## Executive Summary

Dans le secteur bancaire de la zone CEMAC, la résilience d'une organisation se mesure à sa capacité à remédier rapidement à ses défaillances. Aujourd'hui, la gestion du cycle de vie des recommandations d'audit à la BICEC se heurte à des obstacles majeurs : l'usage persistant de tableurs Excel et d'emails fragmente l'information, génère des erreurs et alourdit considérablement la production des reportings pour les comités d'audit.

Pour le régulateur (COBAC), l'accumulation de recommandations non traitées est le "Péché Capital", un signal d'alerte majeur précédant les difficultés bancaires.

**Sentinel v2** est la plateforme numérique développée pour éradiquer ce risque. En remplaçant les processus manuels fastidieux par un flux de travail centralisé, automatisé et transparent, Sentinel supprime la charge mentale pesant sur l'Audit Interne et instaure une culture de la redevabilité stricte chez les audités. La proposition de valeur est claire : garantir l'intégrité de la remédiation et protéger la banque contre les failles opérationnelles et les sanctions réglementaires.

---

## Core Vision

### Problème Central

La gestion actuelle des recommandations est paralysée par 6 maux structurels profonds :

1. **Inefficacité et Fragmentation (Excel/Emails)** : Le suivi manuel entraîne la perte d'informations cruciales, des erreurs et des doublons. L'absence d'alertes automatiques force l'Audit Interne à un travail d'extraction et de relance chronophage.
2. **L'accumulation des recommandations ("Péché Capital")** : Le stock de recommandations en souffrance paralyse l'organisation, génère une lourde charge mentale pour l'audit interne et expose immédiatement aux foudres du régulateur (COBAC).
3. **Culture et comportement des audités** : Faible réactivité, réponses évasives ("oui/non"), contestation tardive des constats pourtant validés de façon contradictoire, et rupture de suivi (oubli pur et simple) lors de la passation de service entre responsables.
4. **Dilution des responsabilités (Actions Transverses)** : Dès qu'une recommandation implique plusieurs entités, chaque service se défausse souvent sur l'autre, bloquant toute possibilité de clôture par manque de visibilité globale de l'environnement.
5. **Risque de gouvernance** : La Direction Générale et l'Audit Interne ne disposent d'aucune vue consolidée fiable sur le taux de couverture réel des contrôles.
6. **Opacité et manque de redevabilité** : Les résultats du suivi restent souvent en vase clos. Sans publication ni transparence, les responsables ne sont pas incités à agir promptement pour rendre des comptes.

### Pourquoi les Solutions Actuelles Échouent

Il n'existe pas à ce jour d'outil dédié, spécialisé et conforme aux exigences
réglementaires CEMAC/COBAC disponible pour les banques de la sous-région.
Les outils internationaux (MetricStream, Rsam, etc.) sont :
- Trop coûteux pour le contexte camerounais
- Non adaptés au cadre réglementaire local (COBAC, BEAC, CEMAC)
- Non configurés pour les exigences de souveraineté des données (On-Premise)
- Sans support pour les flux de travail spécifiques à l'audit bancaire CEMAC
- Ne sont pas taillés sur mesure et ne répondent pas entièrement aux besoins évoqués

Excel n'est pas une alternative : il ne génère pas de hash SHA-256, n'envoie pas
d'alertes J-30 avant échéance, et ne constitue aucune preuve opposable devant
un inspecteur COBAC.

### Solution Proposée

Pour répondre à ces défis dans le contexte exigeant de la zone CEMAC, Sentinel est structuré autour d'un outil GRC (Governance, Risk & Compliance) proposant 5 piliers fonctionnels fondamentaux :

1. **Workflow Automatisé avec Relances Dynamiques** : Fini les relances manuelles par email. Le système orchestre les statuts (émise, validée, en cours, réalisée, clôturée) et envoie des **alertes de proximité (15 jours avant l'échéance)** ainsi que des **alertes de retard escaladées au supérieur hiérarchique**.
2. **Piste d'Audit (Audit Trail) Indélébile** : Garantie absolue de transparence et responsabilisation. Toute modification trace irréfutablement : l'utilisateur, l'horodatage, l'adresse IP et les valeurs "avant/après".
3. **Centralisation des Preuves** : Fini les fichiers perdus. Les documents justificatifs sont téléchargés et attachés nativement à la recommandation pour une validation fluide par l'Audit Interne.
4. **Tableaux de Bord Dynamiques et KPIs** : Génération en temps réel d'indicateurs (taux de mise en œuvre, *aging* / ancienneté, répartition des criticités) permettant d'alimenter d'un clic les rapports destinés au Comité d'Audit et à la Direction Générale.
5. **Menu "My To-Do List"** : UX simplifiée à l'extrême. Chaque acteur voit instantanément ses propres actions urgentes, réduisant radicalement sa charge mentale administrative.

### Différenciateurs Clés

| Différenciateur | Détail |
|---|---|
| **Conformité CEMAC native** | Conçu dès la base pour les exigences COBAC R-2016/04, R-2023/01 et l'arsenal réglementaire CEMAC |
| **Audit Trail cryptographique** | SHA-256 à la clôture — chaque action est immuable, horodatée, tracée (IP + avant/après) |
| **Usage obligatoire par design** | Les validations officielles et soumissions de preuves ne peuvent transiter que par Sentinel |
| **On-Premise souverain** | Hébergement interne + chiffrement au repos et en transit, conforme loi 2024-017 |
| **Multi-sources d'audit** | Interne + CAC + COBAC + BEAC + NIF + Consultants — un seul outil de pilotage |
| **Rôles contextuels flexibles** | Un même utilisateur peut être DM sur une recommandation et ETP sur une autre |
| **Aucun équivalent régional** | Pas d'outil GRC dédié, abordable et conforme CEMAC sur le marché de la sous-région |

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

**1. Jean-Paul M. — Chef de Mission, Audit Interne** *(Auditeur)*
- **Contexte :** Coordonne le suivi des recommandations issues des audits internes, COBAC et CAC. Il est responsable de la traçabilité et de la conformité globale du dispositif de contrôle interne.
- **Douleur actuelle :** Passe une part importante de son temps à relancer manuellement les directions et à consolider des données dispersées (emails, Excel), avec un risque élevé d'erreur ou de perte d'information.
- **Risque métier :** En cas de défaillance, la banque s'expose à des sanctions réglementaires (COBAC) et à une perte de crédibilité.
- **Succès Sentinel :** Dispose d'une vision en temps réel des recommandations (en retard, en attente de validation, clôturées). Les relances sont automatisées et les rapports d'audit sont générés instantanément avec une traçabilité complète et opposable.

**2. Claire D. — Directrice des Opérations** *(Directeur Métier / Audité)*
- **Contexte :** Responsable de la mise en conformité de sa direction. Elle supervise les équipes opérationnelles (ETP) et pilote la résolution des recommandations.
- **Douleur actuelle :** Manque de visibilité sur l'avancement réel des actions. Les délégations sont informelles (emails, oral), ce qui génère des retards et des incompréhensions.
- **Risque métier :** Retards non justifiés, mauvaise qualité des preuves, responsabilité engagée devant la Direction Générale et l'Audit.
- **Succès Sentinel :** Visualise en temps réel l'état de ses recommandations. Peut déléguer, suivre et valider les actions efficacement. Formalise la validation via un PV de recette avant transmission à l'Audit.

**3. Marc T. — Chargé de Conformité** *(ETP / Opérationnel de Terrain)*
- **Contexte :** Exécute les actions correctives demandées par la direction métier et fournit les preuves associées.
- **Douleur actuelle :** Manque de clarté sur les attentes. Les retours sont tardifs ou imprécis, entraînant des cycles de correction inefficaces.
- **Risque métier :** Non-respect des délais, soumissions incomplètes, surcharge opérationnelle.
- **Succès Sentinel :** Dispose d'une liste de tâches claire et priorisée. Soumet ses preuves avec un commentaire justificatif obligatoire. Reçoit des notifications proactives (J-7, retard).

### Secondary Users

**4. Dr. Emmanuel K. — Directeur Général Adjoint** *(Direction Générale)*
- **Contexte :** Supervise globalement la gestion des risques et doit rendre compte aux organes de gouvernance et aux régulateurs.
- **Rôle clé :** Peut être directement impliqué dans le traitement de recommandations critiques ou stratégiques.
- **Succès Sentinel :** Accède à une vue consolidée des risques et des recommandations. Identifie rapidement les blocages et peut intervenir pour arbitrer ou accélérer les traitements.

**5. Inspecteur Martin N. — Contrôleur COBAC/BEAC** *(Auditeur Externe)*
- **Contexte :** Vérifie la mise en œuvre effective des recommandations lors des missions d'inspection.
- **Succès Sentinel :** Accède en lecture seule aux recommandations de son périmètre, avec les preuves associées et une synthèse de conformité (statut, dates clés, hash SHA-256).
- **Restriction :** N'a pas accès à l'audit trail interne détaillé.

**6. Aboubakar N. — RSSI** *(Responsable Sécurité des SI / Support)*
- **Contexte :** Garant de la sécurité du système d'information et du respect des politiques internes.
- **Rôle clé :** Supervise les mécanismes de sécurité (SSO, RLS, gestion des accès, audit trail).
- **Succès Sentinel :** Garantit que les accès sont correctement contrôlés (principe du moindre privilège), que les données sont cloisonnées (RLS), et que la traçabilité est intacte et inviolable (hash SHA-256).
- **Restriction :** Ne peut consulter ni accéder aux recommandations ni aux preuves qui ne sont pas dans son périmètre.

### User Journey : Cycle de traitement de la recommandation d'audit

1. **RÉCEPTION / LANCEMENT** : Une recommandation de contrôle (interne, COBAC ou autre) est enregistrée par l'Audit Interne dans Sentinel, catégorisée et affectée à un **Directeur Métier (DM)** ou à un **Directeur Général (DG)** avec une échéance.
   → *(Statut : `ASSIGNED`)*

2. **AFFECTATION / DÉLÉGATION** : Le DM (ou DG) analyse la recommandation. Il peut soit la traiter lui-même, soit la déléguer à un collaborateur opérationnel (sous-directeur métier / ETP) pour exécution.
   → *(Statut : `IN_PROGRESS`)*

3. **EXÉCUTION (Niveau Opérationnel ou Managérial)** : L'acteur en charge (ETP, sous-directeur, DM ou DG) met en œuvre les mesures correctives, charge les preuves (PDF, images, logs, etc.) dans Sentinel et renseigne **obligatoirement** un commentaire justificatif expliquant comment la preuve répond à la recommandation.
   → *(Statut : `IN_PROGRESS`)*

4. **SOUMISSION DES PREUVES** (selon le niveau hiérarchique) :

   - **Cas 1 — Traitement par ETP / Sous-directeur métier :**
     L'ETP soumet les preuves avec commentaire et valide opérationnellement son travail pour avertir sa direction.
     → *(Statut : `PENDING_DM_REVIEW`)*
     Le DM vérifie les preuves fournies par son équipe :
     - ✅ Si valide → Approbation et transmission à l'Audit Interne accompagnée d'un **PV de recette signé** → *(Statut : `PENDING_AUDIT_REVIEW`)*
     - ❌ Si rejet → Retour à l'état `IN_PROGRESS` pour correction ou complément de preuve.

   - **Cas 2 — Traitement par DM :**
     Le DM soumet directement les preuves avec commentaire (possibilité de joindre un PV de recette signé).
     → *(Statut : `PENDING_AUDIT_REVIEW`)*

   - **Cas 3 — Traitement par DG :**
     Le DG soumet directement les preuves avec commentaire.
     → *(Statut : `PENDING_AUDIT_REVIEW`)*

5. **VALIDATION PAR L'AUDIT INTERNE** : L'Audit Interne réalise la revue finale des preuves.
   - ❌ Si preuves insuffisantes : Rejet avec motif + délai supplémentaire → retour à `IN_PROGRESS` pour correction.
   - ✅ Si preuves conformes : Validation avec attribution d'un **taux de réalisation (0–100%)** → passage à la clôture.

6. **CLÔTURE** : La recommandation obtient le statut **`CLOSED_RESOLVED`**. Le système génère un **audit trail immuable** et calcule un **hash SHA-256 final**, garantissant l'intégrité et la traçabilité complète du dossier.

---

## Success Metrics

### Business Objectives

1. **Zéro sanction réglementaire** liée à un défaut de traçabilité lors des prochains contrôles COBAC/BEAC.
2. **Couverture à 100%** de toutes les nouvelles recommandations d'audit dans Sentinel dès le déploiement (abandon total d'Excel/Emails pour les processus officiels).
3. **Réduction drastique du temps de reporting** pour la préparation des comités de direction et des réponses aux régulateurs.

### KPIs pour l'Audit Interne (Pilotage de l'Efficacité)

| KPI | Description |
|---|---|
| **Taux de mise en œuvre global** | % de recommandations clôturées par rapport au stock total émis |
| **Analyse de l'ancienneté (Aging)** | Suivi spécifique des recommandations non traitées depuis **plus de 24 mois** |
| **Répartition par statut** | Vue temps réel : Réalisée, En cours conforme, À accélérer, En retard, Sans objet |
| **Couverture des risques** | Taux de recommandations par macro-processus (RH, SI, Comptabilité, etc.) |
| **Taux de clôture par source** | Comparatif COBAC / BEAC / CAC / Interne / NIF / Consultants |
| **Alertes actives** | Liste consolidée des alertes J-7 et des dépassements en cours |

### KPIs pour le Management (Action et Arbitrage)

| KPI | Description |
|---|---|
| **Taux de réalisation par entité/pôle** | Performance opérationnelle des directeurs métier dans la remédiation |
| **Indicateur de criticité pondérée** | Score de risque basé sur la priorité (Élevée, Modérée, Faible) pour prioriser les ressources |

---

## Architecture Technique & Exigences de Sécurité

Les exigences non-négociables garantissent l'intégrité du système face au régulateur :

| Exigence | Détail |
|---|---|
| **Piste d'Audit indélébile** | Capture systématique : Identité utilisateur, horodatage système non modifiable, adresse IP, valeurs "avant/après" pour chaque modification |
| **Gestion de l'Identité (IAM)** | Intégration LDAP / Active Directory pour SSO et mise à jour des rôles |
| **Hébergement & Chiffrement** | Architecture modulaire On-Premise avec chiffrement des données au repos et en transit |
| **Séparation des tâches (RBAC)** | Isolation stricte : Auditeurs (clôture) / Audités (saisie des preuves) / Management (consultation) |

---

## MVP Scope

### Core Features (Jour 1)

Pour que Sentinel atteigne ses objectifs réglementaires dès le jour 1 :

1. **Gestion Centralisée Multi-Sources**
   - Suivi des recommandations **Externes** (COBAC, BEAC, NIF, CAC, Consultants).
   - Suivi des recommandations **Internes** (issues des missions de l'Audit Interne BICEC).
2. **Workflow de Double Validation**
   - Affectation et délégation en cascade (Audit → DM/DG → Sous-direction/ETP).
   - Soumission de preuves (PDF, Images, etc.) avec commentaire justificatif obligatoire.
   - Circuit d'approbation strict avec motifs de rejet obligatoires.
3. **Traçabilité Extrême et Journal d'Audit (Audit Trail)**
   - Journal complet retraçant chaque action (utilisateur, horodatage, action).
   - Génération de l'empreinte cryptographique (SHA-256) à la clôture.
4. **Portail Auditeur Externe (Régulateurs)**
   - Accès de consultation sécurisé (Read-Only).
   - **Capacité d'exportation** : Visualiser, télécharger et exporter les dossiers de preuves et le journal d'audit.
5. **Tableaux de Bord & Gouvernance**
   - Vues "To-Do" (My To-Do List) pour les opérationnels (ETP, DM, DG).
   - Vues de supervision globales pour la Direction Générale et l'Audit interne.
6. **Sécurité et Accès (Loi 2024-017)**
   - Authentification via SSO Active Directory BICEC.
   - Gestion stricte des profils et des délégations (intérim en cas d'absence).
7. **Moteur de Notifications Automatisé**
   - Alertes de proximité (15 jours avant échéance, 50% du delai depassé).
   - Alertes de retard escaladées à la hiérarchie.

### MVP Success Criteria

Critères mesurables pour déclarer le MVP comme opérationnel et réussi :

1. **Abandon définitif d'Excel** — La BICEC abandonne les tableurs pour le suivi centralisé des recommandations d'audit.
2. **Couverture totale** — 100% des nouvelles recommandations transitent par Sentinel dans les 3 mois suivant le déploiement.
3. **Traçabilité opposable** — L'Audit Trail (SHA-256, horodatage, IP) est validé comme preuve recevable par le département juridique BICEC.

### Out of Scope for MVP

Ces éléments sont explicitement repoussés à des itérations ultérieures :
- Intégration API temps-réel avec le Core Banking System (Amplitude ou autre)


### Future Vision

- **Commercialisation SaaS On-Premise :** Sentinel pourrait devenir un hub de conformité standard proposé aux autres banques de la place CEMAC.
- **Intégration I.A. de Conformité :** Capacité algorithmique à suggérer si une preuve attachée est pertinente vis-à-vis du texte de la recommandation initiale, et analyse prédictive des risques pour anticiper les non-conformités futures.
- **Cartographie des Risques :** Lier dynamiquement les recommandations non-clôturées à la cartographie des risques opérationnels globale de la banque.
- **Intégration API temps-réel avec le Core Banking System (Amplitude ou autre).**
