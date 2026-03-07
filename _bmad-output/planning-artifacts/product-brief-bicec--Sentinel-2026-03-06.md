---
stepsCompleted: [1, 2]
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

<!-- Content will continue to be appended sequentially through collaborative workflow steps -->
