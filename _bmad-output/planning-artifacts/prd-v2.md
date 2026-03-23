---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments: ['product-brief-v2.md', 'product-brief-bicec--Sentinel-2026-03-06.md', 'prd.md', 'market-sentinel-grc-cemac-research-2026-03-21.md', 'domain-audit-interne-cemac-research-2026-03-21.md']
workflowType: 'prd'
classification:
  projectType: "On-Premise Compliance Workflow Platform (SPA + API + PostgreSQL + Async Scheduler)"
  domain: "RegTech — Audit Compliance Management (Banking / CEMAC)"
  complexity: "HIGH (accumulation de sous-systèmes MEDIUM + conformité réglementaire HIGH)"
  projectContext: "Process-Mature Greenfield (code neuf, processus métier existant, données historiques à migrer)"
---

# Product Requirements Document - bicec--Sentinel

**Author:** Dave Lahe
**Date:** 2026-03-21

## Executive Summary

Sentinel est une plateforme de conformité audit On-Premise conçue pour la BICEC. Elle répond aux exigences de la COBAC (R-2016/04) et de la Loi camerounaise 2024-017 sur la protection des données personnelles (entrée en vigueur : 23 juin 2026).

L'application gère le cycle de vie complet des recommandations d'audit — internes (Audit BICEC) et externes (COBAC, BEAC, CAC, NIF, Consultants) — en remplaçant les processus manuels fragmentés (Excel, emails, relances téléphoniques) par un workflow centralisé et infalsifiable au niveau applicatif.

Sentinel transforme le suivi des recommandations d'audit en un système de pilotage intégré :

1. **Libère l'Audit** des relances manuelles grâce à un workflow automatisé et un moteur de relances intelligent
2. **Simplifie la vie des DM/ETP** en remplaçant le chaos par un processus plus rapide et plus clair que l'existant
3. **Garantit que chaque action est documentée**, vérifiable et restituable en cas de contrôle

**6 rôles utilisateurs :** Auditeur Interne, Directeur Métier, Employé Traitant, Direction Générale, Auditeur Externe, RSSI.

**Contexte critique :** La BICEC a été sanctionnée par la COBAC en 2019 (700M FCFA répartis sur 6 banques). Sentinel fournit la preuve opérationnelle que l'institution a pris les mesures correctives structurelles.

**Vision long terme :** Devenir le standard de conformité audit pour la zone CEMAC.

### What Makes This Special

- **Workflow verrouillé en 5 étapes (FSM) + flag OVERDUE :** Le cycle de vie (`ASSIGNED` → `IN_PROGRESS` → `PENDING_DM_REVIEW` → `PENDING_AUDIT_REVIEW` → `CLOSED_RESOLVED`) avec détection proactive des retards.
- **Cloisonnement natif par direction (RBAC + RLS) :** 6 niveaux d'accès + Row-Level Security PostgreSQL empêchant toute fuite d'information entre périmètres.
- **Empreinte d'intégrité finale (HMAC-SHA256) :** L'historique des actions est verrouillé par des Triggers d'Audit inaltérables en base de données, et le dossier complet est scellé cryptographiquement à sa clôture.
- **Aucun équivalent identifié en zone CEMAC :** L'étude de marché n'a identifié aucun outil combinant conformité CEMAC native, hébergement On-Premise souverain et workflow de recommandations d'audit.

## Project Classification

- **Project Type :** On-Premise Compliance Workflow Platform
- **Domain :** RegTech — Audit Compliance Management (Banking / CEMAC)
- **Complexity :** HIGH (accumulation de sous-systèmes MEDIUM + conformité réglementaire HIGH)
- **Project Context :** Process-Mature Greenfield (code neuf, processus métier existant, données historiques à migrer)

## Success Criteria

### User Success
- **Audit Interne :** N'a plus besoin de relancer manuellement. Visualise l'état global en temps réel. Les rapports pour le Comité de Direction sont générés en quelques clics.
- **Directeur Métier (DM) & ETP :** Processus plus rapide et plus clair qu'Excel. Charge mentale réduite grâce aux notifications proactives avant échéance. ≤ 3 clics pour valider une preuve.
- **Direction Générale :** Dashboard de supervision consulté en < 5 minutes/semaine, donnant une vision immédiate de l'exposition réglementaire.

### Business Success
- **Zéro Sanction Réglementaire** liée à un défaut de traçabilité lors des prochains contrôles COBAC/BEAC.
- **Couverture 100%** : La totalité des nouvelles recommandations transitent exclusivement par Sentinel dans les 6 mois post-déploiement. Abandon définitif d'Excel.
- **Taux d'Adoption Proactive :** > 80% des DM se connectent et traitent leurs dossiers avant le déclenchement de la première alerte de retard.
- **Zéro recommandation créée hors Sentinel** après J+6 mois post-déploiement.

### Technical Success
- **Intégrité cryptographique :** 100% des recommandations clôturées possèdent un hash SHA-256 vérifiable. Aucun utilisateur (y compris le DBA) ne peut altérer une preuve archivée sans briser l'empreinte de contrôle.
- **Ségrégation holistique :** Le RLS garantit zéro accès croisé entre directions.
- **HTTPS interne obligatoire** pour toutes les communications.
- **Contrôle d'intégrité de fichier** : Validation stricte des Magic Bytes sur chaque upload de fichier (le scan récursif par antivirus de type ClamAV étant repoussé post-MVP).

### Pré-lancement
- **Import historique complété** : L'intégralité des recommandations existantes (450+) est importée et validée dans Sentinel avant le Go-Live.
- **Sprint 0 technique validé** : SSO/Active Directory opérationnel + environnement On-Premise configuré.
- **Sprint UX/Design complété** : Maquettes validées par un panel d'utilisateurs cibles (DM + ETP).

### Measurable Outcomes

| KPI | Description | Cible |
|---|---|---|
| Taux d'adoption proactive | % de DM traitant leurs dossiers avant la 1ère alerte | > 80% |
| Jalons d'adoption | J+30 : > 60%, J+60 : > 80%, J+90 : > 95% des utilisateurs actifs | Progressif |
| Délai moyen de résolution | % de recommandations clôturées avant échéance | > 85% |
| Taux de rejet Audit | % de preuves validées par DM mais rejetées par l'Audit | 2% — 5% |
| Taux de rejet Métier | % de preuves rejetées par DM vers ETP | < 15% |
| Durée moyenne par statut | Temps dans les états de validation (hors `IN_PROGRESS`) | < 48h |
| Taux de reports tracés | % de retards avec demande formelle de prolongation | > 90% |
| Recommandations > 24 mois | Filtre dashboard : recos non traitées depuis > 24 mois | 0 à terme |

**North Star Metric :** Réduction du délai moyen d'éradication d'un risque critique + 100% de conformité de l'audit trail.

## User Journeys

### 1. 🟢 La Validation Parfaite (Happy Path)

**Personas :** Jean-Paul M. (Audit Interne), Claire D. (DM Opérations), Marc T. (ETP)

**Opening Scene :** Jean-Paul revient d'une réunion de restitution avec le Commissaire aux Comptes. Trois nouvelles recommandations touchent la direction de Claire. Il ouvre Sentinel et crée les recommandations en renseignant les champs obligatoires (source : CAC, priorité : Haute, échéance : 30 jours), joint le rapport d'inspection et assigne le lot à Claire. **Statut : `ASSIGNED`.**

*Note : Si Jean-Paul ne sait pas encore à quel DM assigner (recommandation touchant plusieurs directions), il peut l'assigner temporairement à lui-même le temps de clarifier le périmètre (étape de triage).*

**Rising Action :** Claire reçoit une notification email + in-app. Elle ouvre son dashboard DM, consulte les 3 recommandations, et assigne la plus urgente à Marc avec une note contextuelle. **Statut : `IN_PROGRESS`.** Marc voit apparaître un nouveau dossier dans sa vue "To-Do", trié par **indicateur visuel de priorité** (rouge = Critique, orange = Haute, vert = Normale). À J+20, il a collecté ses éléments de réponse, rédige un commentaire justificatif détaillé et clique "Soumettre à validation DM". **Statut : `PENDING_DM_REVIEW`.**

**Climax :** Claire reçoit l'alerte "Preuve soumise". Elle ouvre le dossier, vérifie la cohérence des pièces de Marc. Si tout est correct, elle rédige et uploade le **PV de recette signé** (la preuve officielle) — ce qui l'exempte du commentaire obligatoire de validation — puis valide le dossier. **Statut : `PENDING_AUDIT_REVIEW`.** Jean-Paul ouvre sa file d'attente, constate que les preuves sont solides et complètes, et clôture le dossier. **Statut : `CLOSED_RESOLVED`.** Le système génère automatiquement le Sceau Final HMAC-SHA256, scellant définitivement la recommandation et ses preuves.

**Resolution :** Zéro email de relance. Zéro coup de téléphone. Le dossier est clos en 20 jours, traçable de bout en bout, avec une preuve infalsifiable.

---

### 2. 🟡 Le Goulot et le Rejet (Edge Case)

**Personas :** Claire D. (DM), Marc T. (ETP), Scheduler automatique

**Opening Scene :** Marc a soumis ses preuves pour une recommandation de priorité Critique. **Statut : `PENDING_DM_REVIEW`.** Mais Claire est partie en mission à l'agence de Douala pour une semaine, sans avoir demandé à l'Audit Interne de ré-assigner manuellement ses recommandations urgentes à son remplaçant.

**Rising Action :** Le Scheduler détecte que l'échéance approche. À J-7, il émet une alerte email + in-app à Claire, Marc et Jean-Paul (Audit). Claire ne réagit pas. L'échéance est franchie. Le Scheduler bascule automatiquement le flag **`OVERDUE`** sur la recommandation — qui est désormais simultanément `PENDING_DM_REVIEW` ET `OVERDUE`. Un rappel **quotidien** est envoyé (priorité Critique). Pour les priorités Haute/Moyenne/Faible, un **digest hebdomadaire** consolidé remplace les rappels quotidiens. Le dashboard DG affiche un indicateur rouge.

**Climax :** Claire revient, ouvre son dashboard et voit le dossier en retard surligné. Elle consulte les éléments de Marc, constate qu'il manque des signatures, et **rejette** avec le motif obligatoire : "Signature absente — merci de refaire signer." Le statut repasse à **`IN_PROGRESS`**. Les preuves rejetées sont taguées `REJECTED_V1` et restent visibles dans l'historique. Marc reçoit la notification avec le motif.

**Resolution :** Marc corrige, re-soumet (V2). Cette fois Claire génère le PV de recette, l'uploade et valide rapidement. L'Audit clôture. L'audit trail montre factuellement : le goulot était Claire (5 jours en `PENDING_DM_REVIEW` + `OVERDUE`). Le flag OVERDUE est documenté, le motif de rejet est tracé.

---

### 2b. ⏳ La Demande de Report (Extension Path)

**Personas :** Claire D. (DM), Jean-Paul M. (Audit Interne)

**Opening Scene :** Claire constate à J-10 que le développement informatique requis par une recommandation prendra 2 mois supplémentaires. Elle ne peut pas tenir l'échéance initiale.

**Rising Action :** Dans Sentinel, Claire clique sur "Demander un report". Elle saisit la nouvelle date d'échéance souhaitée et fournit la justification métier détaillée (obligatoire). Le dossier signale une extension en attente, sans bloquer les autres actions (ou passe dans un statut dédié transitoire). 

**Climax :** Jean-Paul (Audit) reçoit la demande de délai. Il évalue la justification apportée par le DM. S'il l'estime valable, il **accepte** : la nouvelle échéance est enregistrée dans le système et le compteur est réinitialisé. S'il l'estime non fondée, il **refuse** : l'échéance initiale est maintenue, avec le commentaire de l'Audit.

**Resolution :** Les négociations de délai ne se font plus par email ou téléphone de manière officieuse. L'Audit garde le contrôle absolu sur le calendrier, et chaque report accordé (ou refusé) est tracé et justifié dans l'audit trail.

---

### 3. 🔵 La Mission COBAC (Compliance Path)

**Personas :** M. Atangana (Inspecteur COBAC), Jean-Paul M. (Audit Interne)

**Opening Scene :** La COBAC annonce un contrôle inopiné. M. Atangana et son équipe arrivent à la BICEC. Jean-Paul crée un compte "Auditeur Externe" avec des credentials locaux (hors Active Directory) et définit le périmètre de mission : uniquement les recommandations liées aux opérations de crédit sur les 12 derniers mois.

**Rising Action :** M. Atangana se connecte via HTTPS. Son accès est cloisonné par RLS : il ne voit que les recommandations de son périmètre autorisé. Il consulte la liste filtrée, ouvre chaque dossier, visualise les preuves jointes (PDF signés, screenshots), et constate les dates de soumission et de validation. **L'audit trail (journal des actions internes) n'est PAS accessible.** Le flag **`OVERDUE` est masqué** pour les Auditeurs Externes. Il voit uniquement une fiche de synthèse de conformité : statuts, dates clés, hash SHA-256 de clôture.

**Climax :** M. Atangana sélectionne un dossier de recommandation validé et clique lui-même sur "Télécharger l'Archive ZIP" pour obtenir les preuves. L'archive (preuves + synthèse de conformité) est générée et téléchargée de manière synchrone en < 5 secondes directement depuis son espace.

**Resolution :** En 2 heures, M. Atangana a consulté l'intégralité de son périmètre. Habituellement, cette phase prenait 3 jours de fouille dans des classeurs et des emails. La BICEC démontre un dispositif de conformité structuré et opposable.

---

### 4. 🟣 L'Onboarding & Administration (Admin/Ops Path)

**Personas :** Aboubakar N. (RSSI / Support)

**Opening Scene :** Le Sprint 0 technique est lancé. Aboubakar configure l'environnement On-Premise : serveur web, base PostgreSQL, certificat HTTPS interne. Il connecte Sentinel à l'Active Directory de la BICEC pour l'authentification SSO. Première validation : un utilisateur test se connecte avec ses identifiants AD.

**Rising Action :** Aboubakar crée l'organigramme dans l'interface d'administration de Sentinel : 12 directions, 45 agences, structure hiérarchique. Il crée les comptes utilisateurs et assigne les rôles métiers (en coordination stricte avec l'Audit Interne qui valide chaque affectation). L'Audit Interne gère exclusivement les ré-assignations manuelles en cas d'absence des DM. Du côté métier, c'est ensuite Jean-Paul (Audit Interne) qui télécharge le template d'import normalisé depuis son espace sécurisé, y transfère ses 450+ recommandations historiques et lance l'import. Lors de la première tentative, le système bloque tout à cause d'une date invalide à la ligne 42 (transaction atomique). Jean-Paul corrige son fichier et valide l'import global avec succès en statut `ASSIGNED` avec le tag `IMPORTED`.

**Climax :** La première connexion réelle des utilisateurs. Aboubakar surveille les logs système : connexions, erreurs SSO, performances. Un DM signale un problème d'accès — son périmètre RLS n'inclut pas sa nouvelle agence. Aboubakar met à jour l'organigramme, le RLS se réapplique instantanément. Problème résolu en 5 minutes.

**Resolution :** L'environnement est opérationnel. L'historique est migré. Les 85 utilisateurs sont formés et connectés. Aboubakar supervise le turnover : quand un collaborateur quitte la BICEC, la désactivation AD révoque instantanément son accès Sentinel.

---

### 5. 🔴 La Supervision Stratégique (DG Path)

**Personas :** Direction Générale

**Opening Scene :** Lundi matin, 8h. Le Directeur Général ouvre Sentinel. Son dashboard de supervision s'affiche : une vue macro synthétique avec les indicateurs clés. Il voit en un coup d'œil : 127 recommandations actives, 14 en retard (`OVERDUE`), 3 en attente de validation DM depuis > 5 jours.

**Rising Action :** Le DG filtre par source (COBAC uniquement) : 8 recommandations COBAC dont 2 en retard. Il clique sur le filtre d'aging : 1 recommandation datant de > 24 mois n'a jamais été clôturée. Il note la direction responsable. Il filtre par priorité "Critique" : 5 dossiers, dont 3 en bonne progression et 2 en retard.

**Climax :** Le Comité de Direction de 9h utilise le rapport de synthèse généré par Sentinel (export PDF) comme unique source de vérité. Plus de consolidation Excel préparée la veille par un analyste. Les données sont en temps réel. Le DG interpelle le DM de la direction en retard — les faits sont indiscutables car tirés directement du système.

**Resolution :** En 5 minutes, le DG a une vision complète de l'exposition réglementaire de la banque. Il peut se présenter sereinement devant le Conseil d'Administration avec des chiffres fiables et actualisés.

---

### Journey Requirements Summary

| Parcours | Capacités révélées |
|---|---|
| **Happy Path** | Création reco (Unitaire & Bulk), triage Audit, assignation DM→ETP, indicateur visuel priorité, soumission ETP, upload PV de recette par DM (exempté du comm. de validation), validation Audit, clôture |
| **Edge Case & Report** | Ré-assignation manuelle par Audit (en cas d'absence DM), flag OVERDUE, rappels quotidiens (Critique) / digest hebdo, rejet motivé, **demande de report par DM avec justification / validation Audit** |
| **Compliance** | Compte Auditeur Externe (credentials locaux), RLS, OVERDUE masqué, synthèse conformité (pas d'audit trail), **téléchargement autonome ZIP unitaire par recommandation** |
| **Data Init (Audit)** | Téléchargement exclusif du template, import transactionnel strict (tout ou rien), rollback sur erreur, tag inaltérable IMPORTED, statut initial ASSIGNED |
| **Admin/Ops** | Configuration SSO/AD, gestion globale de l'organigramme des directions, monitoring système |
| **DG** | Dashboard supervision macro, filtres, export PDF temps réel, rapport Comité de Direction |

## Domain-Specific Requirements

### Compliance & Regulatory
- **COBAC R-2016/04 :** Obligation stricte de traçabilité des recommandations d'audit et de conservation des preuves d'exécution.
- **Loi 2024-017 (Cameroun) :** Protection des données personnelles impliquant un hébergement **souverain** (On-Premise obligatoire pour la BICEC) et des durées de rétention maîtrisées.
- **Opposabilité Juridique :** L'historique validé dans l'application doit faire foi lors des inspections des régulateurs sans nécessiter de documents annexes.
- **Séparation des Fonctions (SoD) :** L'administration technique (IT/RSSI) gère l'infra, mais l'Audit Interne gère les habilitations métiers et les délégations/intérims.

### Technical Constraints
- **Environnement Isolé (On-Premise) :** L'application ne dépend d'aucun service Cloud externe pour son fonctionnement métier ou son stockage.
- **Intégrité et Audit (Triggers & HMAC-SHA256) :** L'immutabilité est garantie par des Triggers PostgreSQL stricts. L'intégrité cryptographique globale est scellée au moment de la clôture finale.
- **Ségrégation Holistique (RLS) :** Implémentation du Row-Level Security directement dans PostgreSQL en plus du RBAC applicatif.
- **Sécurité et Réseau :** HTTPS interne obligatoire ; validation stricte par Magic Bytes (scan antivirus différé en V2).

### Integration Requirements
- **SSO Active Directory :** Connexion fluide via l'AD de la BICEC pour assurer l'adoption des DM et ETP.
- **Cycle de Vie Utilisateurs :** La désactivation d'un compte dans l'AD doit révoquer instantanément l'accès à Sentinel. L'import Excel (initial) fonctionne en mode strict "data-only".
- **Post-MVP (Future-proofing) :** Architecture API-first pour permettre de futures intégrations avec SPECTRA II et le Core Banking.

### Risk Mitigations
- **Risque d'Adoption (Rejet des DM) :** Atténué par un plan de notifications graduel (digest vs quotidien), un design UX ultra-rapide et l'exemption de commentaires si présentation du PV de recette signé.
- **Risque de Migration (Historique Excel) :** Atténué par une restriction d'import stricte à l'Audit Interne et un moteur transactionnel atomique (tout-ou-rien) interdisant toute corruption partielle.
- **Risque d'Usurpation de Délégation :** Atténué par l'absence de système de délégation autonome (les ré-assignations en cas d'absence sont effectuées exclusivement par l'Audit Interne).

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**MVP Approach :** Compliance & Efficiency MVP. Focus absolu sur la fiabilité du workflow, l'intégrité des preuves (SHA-256), la sécurité (RLS) et l'adoption par les Directeurs Métiers (UX ultra-rapide).
**Resource Estimation :** 1 Backend Dev, 1 Frontend Dev, 1 Admin Infra/Sécurité (Sprint 0), 1 PM/QA.


### MVP Feature Set (Phase 1)
**Core User Journeys Supported :**
- Happy Path (Assignation → Soumission → Validation DM → Clôture)
- Edge Case & Report (Rejet, OVERDUE, Demande de délai / ré-assignation Audit)
- Import Transactionnel Atomique (Historique) & Onboarding SSO AD.
- Mission COBAC (Création accès local limité).

**Must-Have Capabilities :**
- Workflow FSM strict (5 états + statut transitoire d'extension)
- **Création Audit en "Bulk"** (Saisie par lots pour réduire la friction de création)
- Intégration SSO Active Directory (Read-Only)
- Isolation des données (RLS PostgreSQL)
- Sceau cryptographique de clôture (HMAC-SHA256) et Audit Triggers natifs
- **Sécurité Fichiers allégée :** Validation par magic bytes + whitelist d'extensions (PDF, JPG, PNG) + limite 50 Mo. (Le scan ClamAV est repoussé en V2 pour économiser l'infra).
- Dashboards simplifiés : Vue liste filtrable pour Audit/ETP/DM. Pour le DG : Vue liste agrégée statique ou simple export PDF des retards (Pas de graphiques interactifs complexes en MVP).
- Moteur de notification asynchrone (Digest vs Alertes temps réel)

### Post-MVP Features

**Phase 2 (Growth) :**
- **Sécurité Fichiers Avancée :** Intégration du scan antivirus serveur actif (ClamAV).
- **Dashboard DG Avancé :** DataViz, graphiques interactifs et comparatifs temporels.
- Portail DMZ "Read-Only" automatisé pour Auditeurs Externes.
- Seuils de relance proportionnels proactifs (50/80% du délai imparti).
- Taux de réalisation granulaire (0-100%) défini par l'Audit à la clôture, au lieu du binaire.
- Multi-assignation d'une recommandation à plusieurs ETP simultanément.

**Phase 3 (Vision / Expansion) :**
- Hub de Conformité SaaS On-Premise (Multi-Tenant pour d'autres banques CEMAC).
- IA de Conformité (Validation sémantique automatique des preuves).
- Intégration API Core Banking & SPECTRA II.

### Risk Mitigation Strategy
**Technical Risks (Performance & RLS) :** Protéger le MVP en remplaçant la blockchain logicielle complexe par un Sceau HMAC-SHA256 unique à la clôture. Si le RLS PostgreSQL résiste plus de 5 jours, basculer immédiatement sur un RBAC applicatif — mais activer immédiatement les tests d'isolation automatisés sur chaque endpoint avant de continuer le développement. Ces tests sont bloquants pour le Go-Live.
**Adoption Risks (Rejet DM ou Epuisement Audit) :** Ajout de la saisie "Bulk" pour soulager l'Audit à la création. Règle des "≤ 3 clics" pour la validation côté DM avec exemption de commentaire si PV de recette signé.
**Resource Risks (Temps infra) :** Remplacement de ClamAV par une validation Magic Bytes au MVP pour réduire la surface d'attaque sans dépendance infrastructure, sécurisant ainsi la deadline de 6 mois.

## Functional Requirements

### 1. User Management & Authentication
- **FR1:** Les utilisateurs internes peuvent s'authentifier via leurs identifiants Active Directory (SSO).
- **FR2:** Les Auditeurs Externes peuvent s'authentifier via des identifiants locaux spécifiques au système.
- **FR3:** L'Audit Interne peut valider et associer les comptes AD aux profils métiers (Audit, DM, ETP, DG, Externe).
- **FR4:** L'Audit Interne conserve le privilège exclusif de ré-assigner manuellement une recommandation associée à un Directeur Métier absent vers son remplaçant, garantissant ainsi le routage correct des alertes.

### 2. Recommendation Initialization & Import
- **FR5:** L'Audit Interne peut créer manuellement une recommandation d'audit individuelle.
- **FR6:** L'Audit Interne peut modifier ou supprimer (Soft Delete) une recommandation *tant qu'elle n'a pas été assignée activement* à un DM, afin de corriger les erreurs de frappe.
- **FR7:** L'Audit Interne peut créer des recommandations en masse (Bulk Create) pour accélérer la saisie Post-Mission.
- **FR8 (Data Initialization) :** L'Audit Interne est le **seul habilité** à préparer, prévisualiser et déclencher l'import historique. Aucun autre profil (IT/RSSI, DM) n'a accès à l'interface d'import des données métier. Le template normalisé est téléchargeable uniquement depuis l'espace Audit.
- **FR9 (Atomic Import) :** L'import s'exécute numériquement en **transaction atomique stricte (tout ou rien)**. Toute erreur d'intégrité annule l'intégralité de l'opération et retourne le numéro de la ligne en erreur. Toute recommandation importée obtient le statut `ASSIGNED` avec un tag `IMPORTED` permanent et inaltérable dans l'audit trail.

### 3. Workflow & Triage
- **FR10:** L'Audit Interne peut s'auto-assigner temporairement une recommandation lors de la phase de triage complexe.
- **FR11:** L'Audit Interne peut assigner définitivement une recommandation à un Directeur Métier cible.
- **FR12:** Le Directeur Métier peut ré-assigner la recommandation à un ETP de son équipe.
- **FR13:** Le Directeur Métier peut soumettre une demande formelle de report d'échéance incluant une justification métier de la durée.
- **FR14:** L'Audit Interne peut approuver (en validant la nouvelle date) ou rejeter (maintien de l'échéance initiale) la demande de report.

### 4. Evidence Submission & Validation
- **FR15:** L'ETP peut uploader des fichiers comme preuves (max 50 Mo) limités strictement aux formats autorisés (Magic Bytes : PDF, Images).
- **FR16:** L'ETP peut soumettre les preuves au DM en y incluant un commentaire justificatif exhaustif.
- **FR17:** Le Directeur Métier peut valider les preuves de l'ETP, ou les rejeter en fournissant un motif obligatoire de correction à l'ETP.
- **FR18:** L'ETP peut uploader de nouveaux fichiers et re-soumettre un dossier suite au rejet du DM ou d'un rejet consécutif de l'Audit.
- **FR19:** Le Directeur Métier peut uploader un document "PV de recette" signé qui l'exempte du commentaire obligatoire lors de sa validation pour l'Audit.
- **FR20:** L'Audit Interne peut clôturer définitivement la recommandation après avoir examiné et jugé satisfaisantes les preuves validées par le DM.

### 5. Notifications & Reminders
- **FR21:** Le système calcule quotidiennement le temps écoulé et bascule automatiquement les recommandations échues au statut OVERDUE.
- **FR22:** Le système génère et transmet des alertes (Email/In-app) de façon quotidienne pour tout dossier OVERDUE priorisé "Critique".
- **FR23:** Le système exécute une boucle nocturne générant l'envoi d'une alerte email distincte (texte brut ou HTML basique 1995) pour *chaque* recommandation en état de retard, garantissant 100% de compatibilité Outlook et supprimant le besoin de template d'agrégation complexe.

### 6. Cryptographic Auditing & Export
- **FR24:** Le système calcule un sceau cryptographique global (HMAC-SHA256) au moment exact de la clôture de la recommandation par l'Audit Interne (FR20), verrouillant le dossier complet.
- **FR25:** Le système archive et conserve toutes les versions chronologiques des fichiers soumis comme preuves, garantissant que l'historique des rejets et des re-soumissions demeure auditable et inaltérable.
- **FR26:** Les Auditeurs Externes peuvent déclencher et télécharger de manière autonome une archive ZIP consolidant les preuves spécifiques d'une recommandation unique de leur périmètre.
- **FR27:** Tout utilisateur autorisé à voir la recommandation peut afficher une frise chronologique détaillée (Timeline) de son cycle de vie (Audit Trail descriptif complet).

### 7. Supervisory Dashboards (RLS)
- **FR28:** L'architecture restreint impérativement la visibilité des données SQL et objets affichés au périmètre organisationnel exact de l'utilisateur requérant (Row-Level Security).
- **FR29:** Les utilisateurs peuvent filtrer leurs vues liste par source d'audit, priorité, statut de workflow actuel et vieillissement de l'échéance (aging).
- **FR30:** L'interface ETP et DM signale l'urgence de traitement par un code couleur immédiatement identifiable (ex: Rouge/Orange/Vert) sur la vue d'ensemble.
- **FR31:** L'interface DG est optimisée pour impression navigateur via CSS `@media print`. Aucune génération PDF côté serveur n'est développée.

## Non-Functional Requirements

### Security & Compliance
- **NFR-SEC-01 :** Le trafic externe (Client ↔ Serveur) doit impérativement utiliser le protocole **HTTPS (TLS 1.2 minimum)**. Le chiffrement intra-infrastructure (API ↔ BDD) n'est différé à la V2 *que si et seulement si* le déploiement MVP est mono-serveur (API et BDD sur la même machine/VM).
- **NFR-SEC-02 :** La session applicative doit expirer automatiquement après **30 minutes d'inactivité absolue** du navigateur (équilibre sécurité / UX pour les sessions de lecture DM).
- **NFR-SEC-03 :** Le calcul de l'empreinte cryptographique de clôture doit utiliser **HMAC-SHA256** (clé serveur + métadonnées + preuves), sans impliquer de mécanique logicielle de chaînage transactionnel récurrent.
- **NFR-SEC-04 :** L'API doit refouler instantanément tout fichier dont les **Magic Bytes** ne correspondent pas exactement à une signature PDF, JPG ou PNG autorisée.
- **NFR-SEC-05 :** Les logs systèmes (Activity Logging) doivent être conservés 12 mois et accessibles en mode "Read-Only" par le RSSI (ou extraits via Syslog).

### Performance
- **NFR-PERF-01 :** La résolution des règles de **Row-Level Security (RLS)** doit s'exécuter en **< 10ms** par requête (matérialisation des permissions hiérarchiques requise au niveau du token/session pour éviter les jointures récursives bloquantes).
- **NFR-PERF-02 :** Les opérations de routine de l'interface utilisateur (Changement de statut, Assignation) doivent obtenir une réponse serveur en **< 1 seconde** (95ème percentile).
- **NFR-PERF-03 :** L'overhead de calcul du Sceau HMAC-SHA256 lors de la clôture finale ne doit pas dépasser **500 millisecondes**.
- **NFR-PERF-04 :** La génération et le téléchargement synchrone d'une archive ZIP unitaire (pour une seule recommandation) pour les Auditeurs Externes doit prendre **< 5 secondes**.

### Scalability & Capacity
- **NFR-SCA-01 :** Le système autorise un upload unitaire maximal de **50 Mo par fichier**, limité à un lot de **5 fichiers simultanés maximum par requête** pour empêcher la saturation mémoire du serveur (Déni de Service).
- **NFR-SCA-02 :** L'architecture MVP doit pouvoir ingérer le lancement (Import) de **5 000 recommandations** et **20 000 fichiers de preuves** historiques initiaux.
- **NFR-SCA-02b :** Le Time-To-Interactive (TTI) de l'application frontend doit rester décorrelé du volume de l'import historique en toile de fond (l'import ne doit pas verrouiller la base de données pour les opérations synchrones de lecture des utilisateurs connectés).
- **NFR-SCA-03 :** Le système doit garantir des temps de réponse nominaux avec **jusqu'à 500 utilisateurs concurrents** actifs (Périodes de rush : audits trimestriels, fins de mois).

### Reliability & Data Integrity
- **NFR-REL-01 :** Fail-Safe Security : Si l'identifiant utilisateur est absent du contexte de requête base de données (middleware défaillant), le RLS doit bloquer l'accès en retournant **zéro ligne** (défaut bloquant, jamais permissif).
- **NFR-REL-02 :** Le Recovery Point Objective (RPO) de l'infrastructure d'hébergement On-Premise est fixé à **24 heures** pour le MVP (tolérance d'une perte de données de la journée de travail via un Backup incrémental nocturne chiffré).
- **NFR-REL-03 :** Le Recovery Time Objective (RTO) est fixé à **4 heures** en cas de crash critique du serveur applicatif ou de la Base de Données.
- **NFR-REL-04 :** L'application doit garantir un Uptime de **99,5%** durant les heures ouvrées critiques de la banque (8h00 - 18h00).
