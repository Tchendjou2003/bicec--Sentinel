---
version: '2.0'
status: 'EN CONSTRUCTION'
date: '2026-03-31'
project_name: 'bicec--Sentinel'
author: 'Dave Lahe'
sources:
  - planning-artifacts/prd-v2.md
  - planning-artifacts/product-brief-v2.md
  - planning-artifacts/architecture.md (v1)
  - planning-artifacts/system-diagrams.md
---

# Architecture Sentinel v2 — Document Consolidé

> **Résumé Exécutif**
> Sentinel est une application sécurisée de suivi des recommandations d'audit bancaire, conçue pour opérer **on-premise** sous contraintes réglementaires **COBAC**. L'architecture retenue est un **Monolithe Django SSR** (Server-Side Rendering) propulsé par **HTMX + Alpine.js** pour l'interactivité, stylé avec **Tailwind CSS**, et sécurisé par un dispositif multiniveau (RBAC applicatif + RLS PostgreSQL + HMAC-SHA256 + Audit Trail append-only).
>
> Ce document est le **référentiel technique unique** du projet. Il consolide les décisions d'architecture, les diagrammes système, les analyses de sécurité et les procédures opérationnelles dans un format conçu pour être compris par un public technique et non-technique.

---

## §0. Préambule

### 0.1 Objectif du Document & Public Cible

Ce document d'architecture sert de **référence technique unique** pour toutes les parties prenantes du projet Sentinel. Il est conçu pour être lu et compris par quatre audiences distinctes :

| Public | Ce qu'il cherche dans ce document | Sections clés |
|---|---|---|
| **🔧 Développeur** | Comprendre la stack technique, les patterns de code, les structures de données et les décisions d'implémentation pour coder de manière autonome. | §2 ADRs, §5 FSM, §7 ERD, §8 Classes |
| **🏛️ Direction IT BICEC** | Évaluer les choix d'infrastructure, les coûts de maintenance, la compatibilité avec l'existant et le plan de déploiement on-premise. | §3 C4, §10 Infrastructure, §15 Licences |
| **🔍 Auditeur / Inspecteur COBAC** | Vérifier la conformité réglementaire, la traçabilité des actions, l'intégrité des données et les mesures de sécurité. | §9 Sécurité, §11 Chiffrement, §14 Validation NFR, §16 FAQ |
| **📋 Jury / Évaluateur** | Comprendre la vision globale, les compromis architecturaux, la rigueur méthodologique et la maturité de la solution. | §0 Préambule, §2 ADRs, §12 Risques, §14 Bilan |

### 0.2 Documents Sources & Traçabilité

Ce document est **dérivé exclusivement** des sources suivantes. Aucune fonctionnalité, technologie ou contrainte n'est ajoutée sans référence à ces documents validés :

| Document source | Version | Rôle |
|---|---|---|
| **PRD v2** (`prd-v2.md`) | v2.0 — 2026-03 | Exigences fonctionnelles (31 FR) et non-fonctionnelles (13 NFR). Source de vérité pour le « quoi ». |
| **Product Brief v2** (`product-brief-v2.md`) | v2.0 — 2026-03 | Vision produit, rôles utilisateurs, KPIs de succès. Source de vérité pour le « pourquoi ». |
| **Architecture v1** (`architecture.md`) | v1.0 — 2026-03-23 | Première itération des ADRs et choix techniques. Base raffinée dans ce document. |
| **System Diagrams** (`system-diagrams.md`) | v1.0 — 2026-03-31 | Diagrammes Mermaid (MCD, ERD, FSM, Séquences, Use Cases, Classes). Intégrés dans ce document. |

> **Convention de traçabilité :** Chaque décision architecturale référence les exigences PRD qu'elle résout (ex: `FR10`, `NFR-SEC-01`). Les diagrammes portent un identifiant stable (ex: `SEQ-01`, `UC-AUDIT`).

### 0.3 Guide de Lecture des Diagrammes

Ce document utilise **5 types de diagrammes techniques**, tous rendus en Mermaid (compatible GitLab, GitHub, VS Code). Cette section explique comment les lire pour un lecteur non-technique.

---

#### 🏗️ Diagrammes C4 (Contexte → Conteneur → Composant)

Le modèle **C4** est un standard de visualisation d'architecture logicielle qui fonctionne comme un **zoom progressif**, comparable à une carte géographique :

| Niveau | Analogie | Ce qu'il montre | Exemple Sentinel |
|---|---|---|---|
| **C4 Level 1 — Contexte** | Vue satellite du pays | Le système Sentinel dans son environnement : qui l'utilise et avec quels systèmes externes il interagit. | Sentinel ↔ Active Directory ↔ Serveur SMTP ↔ Navigateur |
| **C4 Level 2 — Conteneurs** | Vue d'une ville | Les composants déployés séparément : application web, base de données, worker asynchrone. | Django App ↔ PostgreSQL ↔ Django-Q2 Worker |
| **C4 Level 3 — Composants** | Plan d'un bâtiment | L'intérieur d'un conteneur : les modules, services et couches logiques. | apps/users ↔ apps/workflow ↔ apps/audit ↔ apps/notifications |

**Comment lire un diagramme C4 :**
- Les **rectangles** représentent des systèmes, conteneurs ou composants.
- Les **flèches** montrent les flux de données avec le protocole utilisé (ex: `HTTPS`, `SQL`, `SMTP`).
- Les **acteurs** (icônes humaines) représentent les utilisateurs du système.
- La **couleur** distingue les éléments internes (bleu) des éléments externes (gris).

---

#### 🔄 Diagrammes de Séquence

Un diagramme de séquence montre **l'ordre chronologique des échanges** entre plusieurs acteurs et composants pour réaliser une action métier.

**Comment le lire :**
- Le temps s'écoule **de haut en bas**.
- Chaque **colonne verticale** (ligne de vie) représente un acteur ou un composant.
- Les **flèches pleines** (`→`) sont des appels (requêtes).
- Les **flèches pointillées** (`-->`) sont des réponses.
- Les **rectangles colorés** (`rect`) regroupent des phases logiques.
- Les **blocs `alt`** montrent des embranchements conditionnels (Si/Sinon).
- Les **blocs `loop`** montrent des répétitions.

```
Exemple de lecture :
  ETP → Django : "L'ETP envoie un fichier au serveur Django"
  Django --> ETP : "Le serveur répond avec un fragment HTML"
```

---

#### 🔀 Diagrammes de Machine à États (State Machine / FSM)

Une machine à états montre les **statuts possibles** d'une entité métier (ex: une recommandation) et les **transitions autorisées** entre ces statuts.

**Comment le lire :**
- Le symbole **`[*]`** est l'état initial (entrée dans le système).
- Chaque **rectangle** est un état possible (ex: `ASSIGNED`, `IN_PROGRESS`).
- Chaque **flèche** est une transition déclenchée par une action utilisateur (ex: `DM délègue à ETP`).
- Le texte sur la flèche indique : **Qui** déclenche l'action + **Quelle** méthode FSM est appelée.
- Un état **terminal** (`[*]` en sortie) signifie qu'aucune transition n'est plus possible — l'entité est « gelée ».

> **Règle Sentinel :** Si aucune flèche ne relie deux états, la transition est **physiquement impossible** dans le code (`django-fsm` la bloquera avec une erreur).

---

#### 📊 Diagrammes Entité-Relation (ERD)

Un ERD montre la **structure de la base de données** : les tables, leurs colonnes, et les relations entre elles.

**Comment le lire :**

| Notation Mermaid | Signification | Exemple |
|---|---|---|
| `PK` | Clé Primaire — identifiant unique de chaque ligne | `uuid id PK` |
| `FK` | Clé Étrangère — lien vers une autre table | `uuid department_id FK` |
| `UK` | Contrainte d'Unicité — pas de doublons autorisés | `varchar email UK` |
| `\|\|--o{` | Relation **un-à-plusieurs** (1:N) | 1 Direction → N Recommandations |
| `\|\|--\|\|` | Relation **un-à-un** (1:1) | 1 Recommandation → 1 Sceau HMAC |
| `}o--\|\|` | Relation **plusieurs-à-un** (N:1), côté optionnel | N Preuves → 1 Recommandation |

---

#### 🏛️ Diagrammes de Classes

Un diagramme de classes montre les **objets métier du code**, leurs attributs (données) et leurs méthodes (actions), organisés par domaine fonctionnel.

**Comment le lire :**
- Chaque **boîte** représente une classe (un concept métier dans le code).
- La partie **haute** liste les attributs (données stockées).
- La partie **basse** liste les méthodes (actions possibles).
- Les **flèches pleines** montrent les relations de données (ex: `User` → `Department`).
- Les **flèches pointillées** montrent les dépendances d'utilisation (ex: `ProofService` utilise `Proof`).
- Les **namespaces** regroupent les classes par domaine (`UsersApp`, `WorkflowApp`, `AuditApp`, `NotificationsApp`).

**Architecture HackSoft (convention de nommage Sentinel) :**

| Couche | Rôle | Analogie |
|---|---|---|
| `Model` | Structure de données (colonnes de la table) | Le « quoi » — les données brutes |
| `Selector` | Requêtes de lecture (récupérer des données filtrées) | La « bibliothécaire » — elle cherche et trie |
| `Service` | Logique métier d'écriture (créer, modifier, supprimer) | Le « chirurgien » — il opère sur les données |
| `View` | Interface HTTP (reçoit la requête, renvoie le HTML) | Le « serveur de restaurant » — il prend la commande et livre le plat |

---

#### 🎯 Diagrammes de Cas d'Utilisation

Un diagramme de cas d'utilisation montre **toutes les actions possibles d'un profil utilisateur** dans le système.

**Comment le lire :**
- L'**acteur** (icône avec un emoji de couleur) est le profil utilisateur.
- Chaque **rectangle** est une action que cet acteur peut réaliser.
- Le **périmètre** (`Système Sentinel`) délimite ce qui est dans l'application.
- Les actions **barrées** (❌) sont explicitement interdites pour ce profil.

> **Convention de couleur des acteurs Sentinel :**
> 🔵 Auditeur Interne | 🟢 Directeur Métier (DM) | 🟡 Employé Traitant (ETP) | 🟣 Direction Générale (DG) | 🔴 Auditeur Externe | ⚫ RSSI/Admin

---

*Fin de la section §0 — Préambule. La section §1 (Contexte & Contraintes) suit.*

---

## §1. Contexte & Contraintes

### 1.1 Résumé Exécutif du Projet

**Sentinel** est une plateforme de conformité audit On-Premise pour la BICEC (Banque Internationale du Cameroun pour l'Épargne et le Crédit). Elle gère le cycle de vie complet des recommandations d'audit — internes (Audit BICEC) et externes (COBAC, BEAC, CAC, NIF, Consultants) — en remplaçant les processus manuels fragmentés (Excel, emails, relances téléphoniques) par un workflow centralisé et infalsifiable.

**Contexte critique :** La BICEC a été sanctionnée par la COBAC en 2019 (700M FCFA répartis sur 6 banques). Sentinel fournit la preuve opérationnelle que l'institution a pris les mesures correctives structurelles exigées par le régulateur.

**6 rôles utilisateurs :** Auditeur Interne, Directeur Métier (DM), Employé Traitant (ETP), Direction Générale (DG), Auditeur Externe (COBAC/BEAC/CAC), RSSI/Administrateur.

### 1.2 Exigences Fonctionnelles (31 FR — 7 domaines)

| Domaine | FRs | Implications architecturales |
|---|---|---|
| **Gestion Utilisateurs & Auth** | FR1–FR4 | Authentification locale Django (`django.contrib.auth`) MVP. SSO Active Directory (LDAP Read-Only) différé en V2. RBAC multi-rôle contextuel. |
| **Initialisation & Import** | FR5–FR9 | Import transactionnel atomique (tout-ou-rien). Soft delete. Bulk create. Tag `IMPORTED` inaltérable dans l'audit trail. |
| **Workflow & Triage** | FR10–FR14 | FSM strict 5 états + flag `OVERDUE` + demande de report formalisée (DM → Audit). `django-fsm` garantit les transitions au niveau ORM. |
| **Soumission & Validation Preuves** | FR15–FR20 | Upload 15 Mo max. Validation adaptative (magic bytes médias, whitelist stricte XLSX/CSV/TXT/MSG/EML). Macros `.xlsm` interdites. Versioning des preuves. PV de recette signé. |
| **Notifications & Rappels** | FR21–FR23 | Scheduler asynchrone Django-Q2 (CRON nocturne). Emails consolidés par utilisateur. Alertes proactives J-7. |
| **Audit Cryptographique & Export** | FR24–FR27 | Sceau HMAC-SHA256 à la clôture. Archive ZIP synchrone < 5s/reco. Timeline audit trail. Append-only strict. |
| **Dashboards** | FR28–FR31 | Accès filtré par périmètre organisationnel (RBAC). Filtres multi-critères. Code couleur urgence (Rouge/Orange/Vert). CSS `@media print` pour export DG. |

### 1.3 Exigences Non-Fonctionnelles (13 NFR — 4 catégories)

| Catégorie | NFRs clés | Impact architectural |
|---|---|---|
| **Sécurité** | TLS 1.2+ (NFR-SEC-01), session 30min (NFR-SEC-02), HMAC-SHA256 (NFR-SEC-03), Magic Bytes (NFR-SEC-04), logs 12 mois (NFR-SEC-05) | Middleware sécurité robuste, Nginx TLS, stockage structuré des logs |
| **Performance** | Périmètre < 10ms (NFR-PERF-01), UI < 200ms P95 (NFR-PERF-02), HMAC < 500ms (NFR-PERF-03), ZIP < 5s (NFR-PERF-04) | Pré-calcul du périmètre dans la session Django, SSR natif |
| **Scalabilité** | 15 Mo/fichier × 5 max (NFR-SCA-01), ~5000 recos + ~20000 fichiers (NFR-SCA-02), ~200 users concurrents (NFR-SCA-03) | Dimensionnement mono-serveur, volume de stockage de 400 Go minimum |
| **Fiabilité** | Fail-safe / 0 ligne si contexte absent (NFR-REL-01), RPO 24h (NFR-REL-02), RTO 4h (NFR-REL-03), Uptime 99,5% (NFR-REL-04) | Backup nocturne chiffré, RBAC strict et requêtes filtrées |

### 1.4 Contraintes Non-Négociables

| Contrainte | Détail | Conséquence architecturale |
|---|---|---|
| **On-Premise isolé** | Aucune dépendance Cloud. Tout le runtime doit être auto-contenu sur le réseau interne BICEC. | Zéro SaaS, zéro API externe, zéro CDN. |
| **Active Directory (V2)** | Différé au MVP. V2 : Intégration Read-Only LDAP. | MVP : `django.contrib.auth` local. |
| **PostgreSQL obligatoire** | Triggers d'audit natifs, `pgcrypto` (HMAC-SHA256), RLS disponible. | Aucune autre BDD évaluée. |
| **Mono-serveur MVP** | Application + BDD sur la même VM. | Simplifie TLS interne (pas de chiffrement App↔BDD). |
| **SSR pur — Zéro JSON** | Directive managériale : interdit React et les API REST. | Django Templates + HTMX + Alpine.js. |
| **Pas de ClamAV MVP** | Antivirus différé. | Validation magic bytes + whitelist extensions. |
| **Linux obligatoire** | Gunicorn ne fonctionne pas sur Windows. | VM Ubuntu LTS ou RHEL en production. |
| **Docker Engine & Compose** | Conteneurisation de tous les composants runtime. | `Dockerfile` et `docker-compose.yml` à la racine du projet. |

### 1.5 Échelle & Complexité

- **Domaine technique :** Application web full-stack On-Premise (SSR MPA + HTMX + PostgreSQL)
- **Niveau de complexité :** **HIGH** — Accumulation de sous-systèmes MEDIUM (workflow FSM, notifications, uploads, dashboards) + conformité réglementaire HIGH (COBAC R-2016/04, Loi 2024-017)
- **Composants architecturaux :** ~11 modules MVP (Auth, RBAC, FSM Workflow, Import, File Storage, Notifications, Crypto HMAC, Audit Trail, Dashboards, User Management, Export/Archive)
- **Volume de données :** ~5 000 recommandations, ~20 000 fichiers de preuves, ~200 utilisateurs concurrents max

### 1.6 Préoccupations Transversales

Ces 5 préoccupations traversent **tous les composants** de l'architecture :

1. **Sécurité & Conformité** — Chaque endpoint vérifie le RBAC, chaque requête SQL filtre par périmètre organisationnel, chaque mutation est tracée dans l'audit trail.
2. **Audit Trail (Append-Only)** — Triggers PostgreSQL sur chaque table métier. Aucune suppression physique. Capture : utilisateur, horodatage, IP, valeurs avant/après.
3. **Gestion des Fichiers** — Upload sécurisé (validation adaptative médias vs office), stockage versionné (preuves rejetées conservées), génération ZIP synchrone, streaming pour les fichiers volumineux.
4. **Scheduler Asynchrone** — Calcul quotidien OVERDUE, envoi emails consolidés nocturnes, alertes proactives J-7, monitoring par heartbeat indépendant.
5. **Périmètre Organisationnel** — Pré-calcul du périmètre (directions accessibles) dans la session Django pour des requêtes filtrées < 10ms.

### 1.7 Stack Technique

| Composant | Choix | Rôle |
|---|---|---|
| **Backend** | Django 5.x (Python 3.12+) | Framework web, ORM, auth, admin |
| **Frontend (Serveur)** | Templates Django + HTMX | Moteur de données SSR, fragments HTML |
| **Frontend (Client)** | Alpine.js | Micro-états UI (modales, tabs, toggles) |
| **CSS** | Tailwind CSS (PostCSS) | Design system utility-first |
| **Base de données** | PostgreSQL 16 | OLTP, triggers audit, pgcrypto, RLS |
| **Task Queue** | Django-Q2 | Tâches asynchrones, scheduler nocturne |
| **Auth** | Sessions Django Natives | Stateful, CSRF natif, cookie sécurisé |
| **Reverse Proxy** | Nginx (Stable) | TLS termination via montages volumes IT, fichiers statiques, headers sécurité |
| **Serveur WSGI** | Gunicorn (`gthread`) | Exécution Django en production |
| **Forms** | `django-widget-tweaks` | Classes Tailwind sur les widgets Django Forms |
| **HTMX Integration** | `django-htmx` | Détection `HX-Request`, helpers partials |
| **FSM** | `django-fsm` | Machine à états du workflow |
| **Brute Force** | `django-axes` | Verrouillage après 5 tentatives |

---

## §2. Architecture Decision Records (ADRs)

> **Format ADR :** Chaque décision suit le format structuré ci-dessous, inspiré des standards MADR (Markdown ADR) et adapté au contexte BICEC. Les options évaluées sont présentées en tableau comparatif pour permettre au lecteur de comprendre le raisonnement et les alternatives rejetées.

---

### ADR-01 : Stratégie d'Isolation des Données — RBAC Applicatif (MVP)

**Statut :** DÉCIDÉ
**Date :** 2026-04-04 (Mise à jour v2.1)

**Contexte :** Sentinel gère des données confidentielles cloisonnées par direction. Un Directeur Métier de la Direction A ne doit jamais voir les recommandations de la Direction B. Trois stratégies d'isolation ont été évaluées.

**Options évaluées :**

| Critère | RLS Intégral PostgreSQL | **RBAC Applicatif seul** | RLS Partiel + RBAC Applicatif |
|---|---|---|---|
| **Sécurité** | ⭐⭐⭐⭐⭐ Isolation BDD | ⭐⭐⭐⭐ Dépend du code, mais contrôlable | ⭐⭐⭐⭐ Double verrou |
| **Complexité dev** | ⭐⭐ Très lourd (SQL) | ⭐⭐⭐⭐⭐ Requêtes Django standards | ⭐⭐⭐ Moyen |
| **Go-To-Market MVP** | ⭐⭐ Risque de retard élevé | ⭐⭐⭐⭐⭐ Rapide et éprouvé | ⭐⭐⭐ Frein potentiel |

**Décision : Implémenter uniquement le RBAC applicatif pour le MVP.**

**Justification :**
- Le financement et la sécurisation du MVP (deadline serrée de 6 mois) dictent la simplicité. Le RLS (Row-Level Security) ajoute une surcouche de complexité asymétrique par rapport aux gains.
- Le filtrage métier est géré par des **QuerySet Managers** stricts (`.for_tenant(user)`, `.for_direction(direction_id)`) appliqués sur toutes les requêtes.
- V2 : Le RLS pourra être introduit une fois la logique d'état et le modèle de données stabilisés à 100%.

**Conséquences :**
- Développement accéléré de 1 à 2 semaines.
- Le développeur doit impérativement utiliser les QuerySets préparés pour éviter les fuites de données.
- Utilisation systématique d'un décorateur utilitaire `@with_tenant_context` sur les tâches asynchrones Django-Q2 pour éviter les erreurs humaines d'injection.

**Références :** NFR-REL-01 (Fail-safe), PRD FR28-FR31 (Dashboards filtrés)

---

### ADR-02 : Infrastructure Web — Nginx + Gunicorn

**Statut :** DÉCIDÉ
**Date :** 2026-04-04 (mise à jour v2.1)

**Contexte :** Le PRD exige le TLS 1.2+ obligatoire (NFR-SEC-01), le support d'uploads 15 Mo (NFR-SCA-01) et le service de fichiers statiques performant. Afin d'aligner l'architecture de Sentinel sur les standards déjà en place et maîtrisés par l'IT BICEC, le choix du reverse proxy a été réévalué.

**Options évaluées :**

| Critère | Caddy + Gunicorn | **Nginx + Gunicorn** | Apache + Gunicorn |
|---|---|---|---|
| **Complexité déploiement** | ⭐⭐⭐⭐ 1 binaire supplémentaire | ⭐⭐⭐ Config `nginx.conf` complexe | ⭐⭐ Config Apache verbeuse |
| **Fichiers statiques** | ⭐⭐⭐⭐⭐ Natif (Go, très rapide) | ⭐⭐⭐⭐⭐ Natif (C, très rapide) | ⭐⭐⭐⭐ Natif |
| **Headers sécurité** | ⭐⭐⭐⭐⭐ Natif (HSTS, CSP, X-Frame) | ⭐⭐⭐⭐⭐ Natif | ⭐⭐⭐⭐ Natif |
| **Rate limiting** | ⭐⭐⭐⭐ Plugin natif | ⭐⭐⭐⭐⭐ Très mature | ⭐⭐⭐ Modules |
| **Conformité production** | ⭐⭐⭐⭐⭐ Architecture standard | ⭐⭐⭐⭐⭐ Standard industrie bancaire | ⭐⭐⭐⭐ Standard |
| **Familiarité IT BICEC** | ⭐⭐⭐ Nouveau | ⭐⭐⭐⭐⭐ Standard interne | ⭐⭐⭐⭐ Connu |

**Décision : Nginx (Stable) en reverse proxy (TLS + fichiers statiques) + Gunicorn en mode `gthread` (logique Django).**

**Justification :**
- **Nginx** est le reverse proxy standard déjà utilisé et maîtrisé par la Direction IT de la BICEC. Aligner le projet sur cette technologie élimine le risque lié à l'adoption et à la maintenance d'un nouvel outil (comme Caddy).
- La version **Stable** de Nginx garantit une compatibilité maximale avec les exigences institutionnelles.
- Les certificats TLS internes de la banque seront fournis par l'IT et montés via des volumes Docker, plutôt que de dépendre d'un mécanisme automatique (ACME) inadapté aux réseaux isolés.
- **Gunicorn** reste le serveur WSGI standard pour Django, configuré en `gthread` (4 workers × 10 threads = 40 connexions concurrentes).
- Mêmes garanties que Caddy pour le service des fichiers statiques et la configuration des headers de sécurité applicatifs.

**Conséquences & Bonnes Pratiques V2 :**
- **Bloc Sécurité Médias** : La configuration `nginx.conf` inclut obligatoirement un bloc `location /media/ { deny all; return 403; }` pour empêcher l'exposition des preuves d'audit.
- Redirection automatique HTTP (80) vers HTTPS (443).
- Timings étendus (`proxy_read_timeout 30s`) pour permettre la génération des exports ZIP en limitant les faux positifs de timeout.
- Gunicorn maintient 1 connexion à la base de données par thread actif; il est crucial de configurer `CONN_MAX_AGE = 60` côté Django afin de ne pas épuiser le pool (ou prévoir PgBouncer).
- Limite mémoire côté conteneur (`mem_limit: 512m`) pour palier aux pics d'export ZIP.

**Références :** NFR-SEC-01 (TLS), NFR-PERF-02 (UI < 200ms), [Gunicorn Documentation — Deploy](https://docs.gunicorn.org/en/stable/deploy.html)

---

### ADR-03 : Système de Notifications — Emails Consolidés

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** Le PRD (FR21-FR23) exige un système de notifications asynchrone pour les retards (OVERDUE), les échéances proches (J-7), et les événements du workflow (assignation, rejet, clôture). Trois stratégies de diffusion ont été évaluées.

**Options évaluées :**

| Critère | Email individuel (1 par reco) | **Email consolidé (1 par user)** | In-App seulement |
|---|---|---|---|
| **Volume d'emails/nuit** | ⭐ Élevé (15 recos = 15 emails) | ⭐⭐⭐⭐⭐ Minimal (1 email/user) | ⭐⭐⭐⭐⭐ Zéro email |
| **Risque fatigue notification** | ⭐ Très élevé | ⭐⭐⭐⭐ Faible | ⭐⭐⭐⭐⭐ Nul |
| **Adoption utilisateur** | ⭐⭐⭐ Habitudes email fortes | ⭐⭐⭐⭐⭐ Email + in-app combinés | ⭐⭐ Requiert ouverture active de l'app |
| **Implémentation** | ⭐⭐⭐ Simple (1 query → 1 envoi) | ⭐⭐⭐⭐ Groupement par user | ⭐⭐⭐⭐⭐ Triviale |
| **Conformité COBAC** | ⭐⭐⭐⭐ Preuve d'alerte envoyée | ⭐⭐⭐⭐ Preuve d'alerte envoyée | ⭐⭐ Pas de preuve d'envoi externe |

**Décision : 1 email consolidé par utilisateur + notifications in-app.**

**Justification :**
- 1 email consolidé par utilisateur listant toutes ses recommandations en retard, groupées par priorité.
- Alerte proactive J-7 avant échéance.
- Fréquence : quotidien (Critique), digest hebdomadaire (Haute/Moyenne/Faible).
- Format HTML basique compatible Outlook.
- Notifications in-app : badge + liste dans le dashboard utilisateur comme backup visuel.

**Conséquences :** Implémentation plus simple (1 query → 1 template → 1 envoi par utilisateur). Meilleure adoption. Réduction drastique du volume d'emails.

**Références :** FR21-FR23 (Notifications), Product Brief v2 (§ Notifications proactives)

---

### ADR-04 : Paradigme Frontend — SSR + HTMX (Abandon de l'API JSON)

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** Une directive managériale a formellement interdit l'utilisation de JSON et d'API REST pour des raisons de simplicité de maintenance On-Premise. Trois paradigmes frontend ont été évalués.

**Options évaluées :**

| Critère | DRF + React SPA | **Django SSR + HTMX + Alpine.js** | Django SSR pur (sans JS) |
|---|---|---|---|
| **Complexité déploiement** | ⭐⭐ 2 apps séparées (React build + API) | ⭐⭐⭐⭐⭐ 1 app monolithique | ⭐⭐⭐⭐⭐ 1 app monolithique |
| **Interactivité UI** | ⭐⭐⭐⭐⭐ Full SPA | ⭐⭐⭐⭐ SPA-like (fragments HTML) | ⭐⭐ Full page reload |
| **Sécurité réseau** | ⭐⭐ JSON interceptable, CORS requis | ⭐⭐⭐⭐⭐ HTML uniquement, CSRF natif | ⭐⭐⭐⭐⭐ HTML uniquement, CSRF natif |
| **Vélocité développeur** | ⭐⭐ 2 langages (Python + React/TS) | ⭐⭐⭐⭐⭐ 1 langage (Python + HTML) | ⭐⭐⭐⭐ 1 langage mais UX limitée |
| **Maintenance On-Premise** | ⭐⭐ Node.js requis en prod | ⭐⭐⭐⭐⭐ Zéro Node en prod | ⭐⭐⭐⭐⭐ Zéro Node en prod |
| **Performance TTFB** | ⭐⭐⭐ JSON parsing + rendering client | ⭐⭐⭐⭐⭐ HTML pré-rendu serveur | ⭐⭐⭐⭐⭐ HTML pré-rendu serveur |

**Décision : Django SSR + HTMX (moteur de données) + Alpine.js (ciment UI).**

**Justification :**
- **HTMX** (`hx-get`, `hx-post`) offre l'interactivité d'une SPA (modales, soumission sans rechargement) tout en recevant du HTML brut — zéro JSON.
- **Alpine.js** gère les micro-états éphémères côté client (ouverture modale, tabs, toggles, validation).
- Les vues Django détectent les requêtes HTMX (header `HX-Request`) et renvoient un fragment HTML ou la page complète selon le cas.
- Suppression complète de `djangorestframework`.

**Conséquences :** Architecture immensément plus simple. Zéro sérialisation JSON. TTFB < 200ms (NFR-PERF-02). Node.js requis uniquement en développement (compilation Tailwind CSS).

**Références :** NFR-PERF-02, ADR-08 (Tailwind CSS), [HTMX — Why](https://htmx.org/essays/why-htmx/)

---

### ADR-05 : Task Queue Asynchrone — Django-Q2

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** Le scheduler nocturne (détection OVERDUE, envoi emails consolidés, alertes proactives J-7) nécessite un système de tâches asynchrones fiable et résilient. Quatre options ont été évaluées de manière approfondie.

**Options évaluées :**

| Critère (pondération) | Celery + Redis | **Django-Q2 (ORM)** | APScheduler | CRON OS + management commands |
|---|---|---|---|---|
| **Dépendances externes** (×2) | ⭐⭐ Redis/RabbitMQ requis | ⭐⭐⭐⭐⭐ Zéro (ORM comme broker) | ⭐⭐⭐⭐ Zéro (in-process) | ⭐⭐⭐⭐⭐ Zéro |
| **Fiabilité (crash/reboot)** (×2) | ⭐⭐⭐⭐⭐ Persistance broker | ⭐⭐⭐⭐ Persistance ORM + retry | ⭐⭐ In-memory, perdu au crash | ⭐⭐⭐ Dépend du crontab OS |
| **Monitoring intégré** (×1) | ⭐⭐⭐⭐ Flower (outil séparé) | ⭐⭐⭐⭐⭐ Admin Django natif | ⭐⭐ Logs uniquement | ⭐ Logs OS uniquement |
| **Complexité infra** (×2) | ⭐⭐ Service Redis à maintenir | ⭐⭐⭐⭐⭐ 1 worker `qcluster` | ⭐⭐⭐⭐ In-process (simple) | ⭐⭐⭐⭐⭐ Natif OS |
| **Retry/Timeout natif** (×1) | ⭐⭐⭐⭐⭐ Très configurable | ⭐⭐⭐⭐ `timeout` + `retry` | ⭐⭐ Manuel | ⭐ Manuel |
| **Intégration Django** (×1) | ⭐⭐⭐ Bonne mais setup lourd | ⭐⭐⭐⭐⭐ Natif (models, admin) | ⭐⭐⭐⭐ Bonne | ⭐⭐⭐ Management commands |
| **Scalabilité** (×1) | ⭐⭐⭐⭐⭐ Multi-worker, distribué | ⭐⭐⭐ Mono-worker suffisant MVP | ⭐⭐ Non distribué | ⭐⭐ Non distribué |
| **Score pondéré** | **29/50** | **41/50** | **26/50** | **30/50** |

**Décision : Django-Q2 avec résilience absolue (Timeout/Retry).**

**Justification :**
- **Zéro dépendance externe** : utilise l'ORM Django comme broker (pas de Redis/RabbitMQ à installer ni maintenir).
- **Résilience aux redémarrages :** `timeout=60s` + `retry=120s` sur chaque tâche. Toute tâche interrompue par un redémarrage serveur nocturne est automatiquement relancée.
- **Polling optimisé :** Intervalle de `10 secondes` (vs 5s par défaut). Le besoin est un batch nocturne — un polling agressif surchargerait PostgreSQL inutilement.
- **Monitoring intégré** dans l'admin Django — le RSSI voit l'état des tâches immédiatement.
- **Table `scheduler_heartbeat`** pour détecter si le scheduler a cessé de fonctionner (vérification par script CRON OS indépendant toutes les 2h).
- Celery serait surdimensionné pour le volume de tâches de Sentinel (~10 tâches/nuit).

**Conséquences :**
- Infrastructure simplifiée. Pas de broker externe à gérer.
- Scalabilité limitée à un mono-worker — suffisant pour le MVP (~200 users, ~1000 recos).
- V2 : migration vers Celery si le volume de tâches asynchrones augmente significativement.

**Références :** FR21-FR23 (Notifications), NFR-REL-04 (Uptime), [Django-Q2 Documentation](https://django-q2.readthedocs.io/)

---

### ADR-06 : Authentification — Sessions Django Natives (MVP Local, AD en V2)

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** L'interdiction du JSON (ADR-04) annule la pertinence d'une authentification stateless via JWT. L'intégration Active Directory est différée en V2. Trois stratégies ont été évaluées.

**Options évaluées :**

| Critère | JWT Stateless | **Sessions Django (Stateful)** | AD LDAP Direct |
|---|---|---|---|
| **Sécurité révocation** | ⭐⭐ Blacklist Redis requise | ⭐⭐⭐⭐⭐ Révocation immédiate (DELETE session) | ⭐⭐⭐⭐⭐ Désactivation AD = révocation |
| **Compatibilité SSR** | ⭐⭐ Conçu pour SPA/API | ⭐⭐⭐⭐⭐ Natif Django | ⭐⭐⭐⭐ Compatible via backend auth |
| **Protection CSRF** | ⭐⭐ Complexe (token header) | ⭐⭐⭐⭐⭐ Automatique Django | ⭐⭐⭐⭐⭐ Automatique Django |
| **Dépendance externe** | ⭐⭐⭐ Librairie PyJWT | ⭐⭐⭐⭐⭐ Zéro (intégré Django) | ⭐⭐ Serveur AD requis, SPOF |
| **Complexité MVP** | ⭐⭐⭐ Middleware custom + refresh | ⭐⭐⭐⭐⭐ Config settings.py | ⭐⭐ Config LDAP + fallback |
| **Idle timeout 30min** | ⭐⭐⭐ Gestion complexe (exp claim) | ⭐⭐⭐⭐⭐ `SESSION_COOKIE_AGE=1800` | ⭐⭐⭐⭐ Possible mais plus complexe |

**Décision : Sessions Django Natives (Stateful) pour le MVP.**

**Justification :**
- Expiration fixée à 30 minutes d'inactivité (NFR-SEC-02) : `SESSION_COOKIE_AGE = 1800` + `SESSION_SAVE_EVERY_REQUEST = True` → vrai idle timeout (le timer se réinitialise à chaque requête).
- Flags cookie : `HttpOnly`, `Secure`, `SameSite=Lax`.
- Protection CSRF native sur tous les POST/PUT (automatique via `{% csrf_token %}` + header HTMX `hx-headers`).
- V2 : `django-auth-ldap` pour synchronisation AD → transparente grâce au système de backends auth natif de Django.

**Conséquences :** Architecture MVP ultra-simple. Aucune dépendance au serveur AD. Révocation de session immédiate côté serveur. L'ajout AD en V2 est transparent.

**Références :** NFR-SEC-02 (Session 30min), [Django Session Documentation](https://docs.djangoproject.com/en/5.0/topics/http/sessions/)

---

### ADR-07 : Moteur de Workflow — `django-fsm`

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** Le PRD spécifie (FR10) un cycle de vie strict à 5 états. La question est de coder cette logique manuellement (`if/else` dans les vues) ou d'utiliser une librairie spécialisée.

**Options évaluées :**

| Critère | If/else manuels (vues) | **django-fsm** | django-viewflow |
|---|---|---|---|
| **Garantie des transitions** | ⭐⭐ Aucune — le dev peut oublier un cas | ⭐⭐⭐⭐⭐ Bloqué au niveau ORM | ⭐⭐⭐⭐⭐ Bloqué au niveau workflow |
| **Permissions par transition** | ⭐⭐ Logique éparpillée dans les vues | ⭐⭐⭐⭐⭐ `has_transition_perm` natif | ⭐⭐⭐⭐⭐ Permissions intégrées |
| **Hooks pré/post transition** | ⭐⭐ Événements manuels | ⭐⭐⭐⭐⭐ Décorateurs natifs | ⭐⭐⭐⭐⭐ Signaux intégrés |
| **Complexité d'apprentissage** | ⭐⭐⭐⭐⭐ Aucune (Python pur) | ⭐⭐⭐⭐ Faible (1 décorateur) | ⭐⭐ Élevée (BPMN, configuration lourde) |
| **Surcharge architecture** | ⭐⭐⭐⭐⭐ Nulle | ⭐⭐⭐⭐⭐ 1 field + décorateurs | ⭐⭐ Framework complet (views, models, forms) |
| **Testabilité** | ⭐⭐⭐ Tests de vues complexes | ⭐⭐⭐⭐⭐ Tests unitaires sur model | ⭐⭐⭐⭐ Tests sur le workflow engine |

**Décision : `django-fsm` (Finite State Machine).**

**Justification :**
- Parfaitement adapté au besoin (5 états + flag OVERDUE).
- Garantit au niveau ORM qu'une recommandation ne peut pas sauter d'état.
- `has_transition_perm` permet de lier une transition à un rôle (seul l'Audit peut clôturer).
- **Post-Transition Hooks** : Le sceau HMAC est généré comme un **effet de bord automatique de la transaction finale FSM** (hook `@transition`), assurant qu'il est impossible de dériver l'état (SEQ-01).
- Concurrence gérée par `select_for_update()`.

**Considérations Cryptographiques :**
- Une variable d'environnement `HMAC_SECRET_KEY` totalement distincte de la traditionnelle `SECRET_KEY` Django est exigée pour garantir qu'une future rotation de sécurité ne corrompt pas l'historique d'audit.

**Conséquences :** Moins de bugs de logique d'état. Code métier centralisé dans le modèle. Testable unitairement sans HTTP.

**Références :** FR10-FR14 (Workflow), NFR-SEC-03 (HMAC), [django-fsm Repository](https://github.com/viewflow/django-fsm)

---

### ADR-08 : Styling — Tailwind CSS From-Scratch

**Statut :** DÉCIDÉ
**Date :** 2026-03-23

**Contexte :** Le projet impose un délai serré. Le frontend SSR nécessite un framework CSS cohérent compatible avec les templates Django et les attributs HTMX/Alpine.js.

**Options évaluées :**

| Critère | Bootstrap 5 | **Tailwind CSS** | CSS Custom (from scratch) |
|---|---|---|---|
| **Productivité** | ⭐⭐⭐⭐ Composants prêts | ⭐⭐⭐⭐ Utility classes rapides | ⭐⭐ Tout à écrire |
| **Poids production** | ⭐⭐ ~150 Ko (même purgé) | ⭐⭐⭐⭐⭐ < 20 Ko (purge auto) | ⭐⭐⭐⭐⭐ Minimal |
| **Cohérence design** | ⭐⭐⭐ Look Bootstrap reconnaissable | ⭐⭐⭐⭐⭐ Design system personnalisé | ⭐⭐⭐⭐ Tout contrôlable |
| **Compatibilité Django Forms** | ⭐⭐⭐ Widgets Django peu compatibles | ⭐⭐⭐⭐ `django-widget-tweaks` | ⭐⭐⭐ Manuel |
| **Compatibilité HTMX/Alpine** | ⭐⭐⭐ jQuery legacy parfois gênant | ⭐⭐⭐⭐⭐ Zéro conflit JS | ⭐⭐⭐⭐⭐ Zéro conflit |
| **Dépendance Node.js** | ❌ Non requis (CDN possible) | ⚠️ Node.js pour compilation (dev seulement) | ❌ Non requis |
| **Courbe d'apprentissage** | ⭐⭐⭐⭐ Classes sémantiques | ⭐⭐⭐ Classes utilitaires | ⭐⭐ CSS pur, tout à connaître |

**Décision : Tailwind CSS from-scratch avec plugin `@tailwindcss/forms`.**

**Justification :**
- Build CSS < 20 Ko en production (purge automatique des classes inutilisées).
- `tailwind.config.js` définit les couleurs métier (urgence Rouge/Orange/Vert), la typographie et les breakpoints.
- Node.js requis **uniquement en développement** (`npx tailwindcss --watch`). Le CSS est **pré-compilé en local/CI** avant déploiement — Node.js n'est PAS installé en production.
- Zéro conflit avec HTMX et Alpine.js (pas de jQuery, pas de JS bundlé).

**Conséquences :**
- Design system cohérent et maintenable.
- Nécessite `django-widget-tweaks` pour appliquer les classes Tailwind aux widgets Django Forms.
- Un template admin Tailwind premium (Mosaic, Windmill) peut être intégré ultérieurement.

**Références :** NFR-PERF-02 (UI < 200ms), [Tailwind CSS Documentation](https://tailwindcss.com/docs)

---

### ADR-09 : Conteneurisation — Docker Compose

**Statut :** DÉCIDÉ
**Date :** 2026-04-04 (mise à jour v2.1)

**Contexte :** La distribution, l'installation et la maintenance d'une application complexe sur une infrastructure On-Premise (bare-metal) posent des défis liés aux dépendances système et à l'isolation des processus. Une standardisation de la livraison a été décidée pour fiabiliser les déploiements.

**Options évaluées :**

| Critère | Bare-metal `systemd` | **Docker Compose** | Kubernetes |
|---|---|---|---|
| **Complexité opérationnelle** | ⭐⭐⭐ Moyenne (gestion packages OS) | ⭐⭐⭐⭐⭐ Faible (environnement portable) | ⭐ Complexe (etcd, control plane) |
| **Reproductibilité** | ⭐ Faible ("ça marche sur ma machine") | ⭐⭐⭐⭐⭐ Parfaite (identique dev/prod) | ⭐⭐⭐⭐⭐ Parfaite |
| **Isolation** | ⭐ Faible (partage librairies OS) | ⭐⭐⭐⭐⭐ Forte (Namespaces, cgroups) | ⭐⭐⭐⭐⭐ Très forte |
| **Rollback** | ⭐ Complexe (git revert, pip install) | ⭐⭐⭐⭐⭐ Instantané (re-run vieille image) | ⭐⭐⭐⭐⭐ Instantané |

**Décision : Conteneurisation de la stack via Docker Engine et Docker Compose.**

**Justification :**
- L'utilisation de Docker Compose (4 services : `nginx`, `web`, `worker`, `db`) couvre largement les besoins de charge.
- Environnement portable avec des contraintes de production strictes évitant les crashs silencieux :
  - **Healthchecks** (`pg_isready`) actifs sur `db` et liés via `depends_on: condition: service_healthy` sur les workers.
  - Exécution systématique de `python manage.py collectstatic --noinput` au démarrage du service `web` pour alimenter le volume partagé.
  - Politique `restart: unless-stopped` activée sur l'intégralité des briques applicatives.

**Conséquences :**
- Le serveur de production OS requiert l'installation de Docker Engine (Docker Compose v2 natif sans directive de version dépréciée).
- Workflow de mise à jour sécurisé hors ligne via commandes standard (`docker save` / `load`).

---

*Fin de la section §2 — ADRs. La section §3 (Vue C4 — Architecture Système) suit.*

---

## §3. Vue C4 — Architecture Système

Le modèle C4 (Context, Containers, Components) permet de visualiser l'architecture logicielle de Sentinel à différents niveaux de zoom, facilitant la compréhension pour diverses audiences (Direction IT, développeurs, RSSI). Ce projet inclut les syntaxes C4 Mermaid rendues nativement.

### 3.1 C4 Level 1 — Contexte Système

Ce diagramme illustre le système Sentinel dans son environnement global, ses interactions avec les utilisateurs et l'écosystème IT de la BICEC.

```mermaid
C4Context
    title Diagramme de Contexte (Level 1) - Sentinel

    Person(users, "Utilisateurs", "Auditeurs, Directeurs Métier (DM), ETP, DG, RSSI")
    
    System(sentinel, "Sentinel", "Plateforme de suivi des recommandations d'audit (Workflow, Preuves, Traçabilité)")

    System_Ext(smtp, "Serveur SMTP", "Exchange BICEC (Envoi d'emails)")
    System_Ext(nas, "Serveur NAS", "Backup nocturne SQL/Fichiers (Rétention)")
    System_Ext(ntp, "Serveur NTP", "Synchronisation stricte (Intégrité de l'horodatage)")
    System_Ext(ad, "Active Directory", "LDAP BICEC (Prévu en V2 pour authentification)")

    Rel(users, sentinel, "Consulte et interagit", "HTTPS / Navigateur Web")
    Rel(sentinel, smtp, "Envoie des notifications asynchrones", "SMTP")
    Rel(sentinel, nas, "Archive les backups", "SMB / NFS")
    Rel(sentinel, ntp, "Synchronise l'horloge système", "NTP")
    Rel(sentinel, ad, "Valide l'authentification (V2)", "LDAPS")
```

### 3.2 C4 Level 2 — Conteneurs

Ce diagramme détaille les sous-systèmes déployés sur l'infrastructure On-Premise. Sentinel suit le modèle du « Monolithe Modulaire » déployé sur une machine virtuelle Linux unique.

```mermaid
C4Container
    title Diagramme de Conteneurs (Level 2) - Sentinel

    Person(user, "Utilisateur", "Navigateur Web")

    ContainerBoundary(vm, "Machine Virtuelle Linux (On-Premise BICEC)") {
        ContainerBoundary(docker, "Docker Compose") {
            Container(nginx, "Nginx Proxy", "C", "Reverse Proxy, terminateur TLS, sert les fichiers statiques (CSS/JS)")
            Container(django, "Application Web", "Django / Gunicorn", "Logique métier SSR, HTMX, orchestration FSM")
            Container(worker, "Worker Asynchrone", "Django-Q2", "Exécute les tâches de fond (CRON, envois d'emails, alertes)")
            ContainerDb(postgres, "Base de Données", "PostgreSQL 16", "Stockage relationnel, RLS, Triggers Métier (Audit Trail)")
        }
        Container(fs, "Volumes Docker", "Host FS", "Stockage persistant des Preuves, Base de données, et Certificats TLS")
    }

    System_Ext(smtp, "Serveur SMTP Exchange", "Infra BICEC")

    Rel(user, nginx, "Requêtes HTTPS (UI, HTMX)", "TLS 1.2/1.3")
    Rel(nginx, django, "Passe les requêtes dynamiques", "Réseau interne Docker")
    Rel(django, postgres, "Lit et écrit les données métier", "Réseau interne Docker")
    Rel(django, fs, "Écrit/Lit les preuves uploadées", "Montage Volume")
    Rel(django, worker, "Planifie via la base de données", "Django ORM")
    Rel(worker, postgres, "Récupère les tâches à exécuter", "TCP/IP")
    Rel(worker, smtp, "Envoie les digests d'emails", "SMTP")
```

### 3.3 C4 Level 3 — Composants (Backend Django)

Le monolithe Django héberge plusieurs modules fonctionnels (`apps`) orchestrés selon des principes de forte cohésion/faible couplage (Clean Architecture façon HackSoft : Models / Selectors / Services / Views).

```mermaid
C4Component
    title Diagramme de Composants (Level 3) - Monolithe Django

    ContainerBoundary(django_app, "Application Web (Process Django)") {
        Component(users_app, "Users & Auth App", "django.contrib.auth", "Rôles, Organigramme, Sessions, Middleware RBAC")
        Component(workflow_app, "Workflow App", "django-fsm", "Machine à états (FR10), soumissions, logique de report")
        Component(audit_app, "Audit & Crypto App", "pgcrypto", "Audit trail append-only, génération HMAC-SHA256, Exports ZIP")
        Component(notif_app, "Notifications App", "Templates HTML", "Évaluation des retards OVERDUE, génération d'alertes")
        Component(dash_app, "Dashboards App", "HTMX", "Agrégations visuelles, filtres statut, données quantitatives")
    }

    ContainerDb(postgres, "Instance PostgreSQL", "Base de données métier")
    Container(worker, "Process Django-Q2", "Pool de workers")

    Rel(workflow_app, users_app, "Vérifie les droits & RLS")
    Rel(audit_app, workflow_app, "Trace les transitions métier")
    Rel(workflow_app, notif_app, "Déclenche une notification par événement")
    Rel(notif_app, worker, "Enregistre la tâche email", "via ORM")
    Rel(dash_app, workflow_app, "Construit les KPIs de reporting")
    
    Rel_Back(users_app, postgres, "I/O")
    Rel_Back(workflow_app, postgres, "I/O")
    Rel_Back(audit_app, postgres, "I/O")
```

---

## §4. Diagrammes de Cas d'Utilisation

L'accès aux fonctionnalités est strictement régi par un dispositif RBAC matriciel. Chaque rôle utilisateur dispose d'un ensemble prédéfini d'actions, reflété dans les interfaces de l'application via les templates Django.

### 4.1 Auditeur Interne

```mermaid
flowchart LR
    subgraph "Système Sentinel"
        UC1["Créer recommandation\n(unitaire)"]
        UC2["Créer recommandations\n(bulk / par lots)"]
        UC3["Modifier / Soft Delete\nreco non-assignée"]
        UC4["Importer historique\n(atomique)"]
        UC5["Trier et s'auto-assigner\n(triage complexe)"]
        UC6["Assigner DM cible"]
        UC7["Gérer interim DM"]
        UC8["Examiner preuves\nvalidées par DM"]
        UC9["Clôturer recommandation\n+ Sceau HMAC-SHA256"]
        UC10["Rejeter preuves\n(motif obligatoire)"]
        UC11["Approuver / Refuser\ndemande de report"]
        UC12["Consulter Dashboard\nAudit (filtré RBAC)"]
        UC13["Consulter Timeline\nAudit Trail"]
        UC14["Télécharger template\nd'import"]
        UC15["Génerer rapport de synthèse statistique en PDF"]
    end

    AU(("🔵 Auditeur\nInterne"))

    AU --- UC1
    AU --- UC2
    AU --- UC3
    AU --- UC4
    AU --- UC5
    AU --- UC6
    AU --- UC7
    AU --- UC8
    AU --- UC9
    AU --- UC10
    AU --- UC11
    AU --- UC12
    AU --- UC13
    AU --- UC14
    AU --- UC15
```

### 4.2 Directeur Métier (DM)

```mermaid
flowchart LR
    subgraph "Système Sentinel"
        UC1["Consulter recommandations\nassignées (dashboard DM)"]
        UC2["Déléguer reco\nà un ETP"]
        UC3["Gérer interim ETP"]
        UC4["Examiner preuves\nsoumises par ETP"]
        UC5["Valider preuves\n+ Upload PV recette"]
        UC6["Rejeter preuves\n(motif obligatoire)"]
        UC7["Soumettre preuves\nà l'Audit(DM porteur)"]
        UC8["Demander report\néchéance (justification)"]
        UC9["consulter historique des versions preuves"]
        UC10["Consulter Dashboard DM"]
    end

    DM(("🟢 Directeur\nMétier"))

    DM --- UC1
    DM --- UC2
    DM --- UC3
    DM --- UC4
    DM --- UC5
    DM --- UC6
    DM --- UC7
    DM --- UC8
    DM --- UC9
    DM --- UC10
```

### 4.3 Employé Traitant (ETP)

```mermaid
flowchart LR
    subgraph "Système Sentinel"
        UC1["Consulter To-Do List\n(recos assignées)"]
        UC2["Soumettre preuves\n+ commentaire justificatif\nau DM"]
        UC3["Consulter historique\ndes versions preuves"]
        UC4["Consulter motif de\nrejet du DM/Audit feed back"]
        UC5["consulter details recommandation"]
        UC6["Enregistrer preuves recos en brouillon sans soumettre"]
    end

    ETP(("🟡 Employé\nTraitant"))

    ETP --- UC1
    ETP --- UC2
    ETP --- UC3
    ETP --- UC4
    ETP --- UC5
    ETP --- UC6
```

### 4.4 Direction Générale (DG)

```mermaid
flowchart LR
    subgraph "Système Sentinel"
        UC1["Consulter Dashboard\nSupervision macro"]
        UC2["Filtrer par source\n(COBAC, CAC, Interne)"]
        UC3["Filtrer par priorité\net statut"]
        UC4["Filtrer par aging\n(> 24 mois)"]
        UC5["Imprimer rapport de synthese statistiques dashboard\n(CSS @media print)"]
        UC6["Consulter détail\nd'une recommandation"]
        UC7["Consulter Timeline\nAudit Trail reco"]
        UC8["Soumettre directement\npreuves à l'Audit"]
        UC9["Demander report\néchéance (justification)"]
        UC10["Consulter statistiques\nconformité par direction"]
        UC11["Consulter To-Do List\n(recos assignées)"]
        
      
        
    end

    DG(("🟣 Direction\nGénérale"))

    DG --- UC1
    DG --- UC2
    DG --- UC3
    DG --- UC4
    DG --- UC5
    DG --- UC6
    DG --- UC7
    DG --- UC8
    DG --- UC9
    DG --- UC10
    DG --- UC11   
```

### 4.5 Auditeur Externe (COBAC / BEAC / CAC)

```mermaid
flowchart LR
    subgraph "Système Sentinel"
        UC1["Se connecter avec\ncredentials mission"]
        UC2["Consulter recommandations\ndu périmètre mission\n(Read-Only)"]
        UC3["filtrer recos par période"]
        UC4["Vérifier hash\nHMAC-SHA256"]
        UC5["Télécharger preuve\nZIP par recommandation"]
        UC6["Consulter preuves\nacceptées"]
    end

    subgraph "Restrictions"
        R1["❌ Audit Trail interne\nnon accessible"]
        R2["❌ Flag OVERDUE\nmasqué"]
        R3["❌ Aucune action\nde mutation"]
    end

    EXT(("🔴 Auditeur\nExterne"))

    EXT --- UC1
    EXT --- UC2
    EXT --- UC3
    EXT --- UC4
    EXT --- UC5
    EXT --- UC6
```

### 4.6 RSSI / Administrateur Système (support IT)

```mermaid
flowchart LR
    subgraph "Système Sentinel (Espace Admin)"
        UC1["Gérer l'organigramme\n(Directions, Départements)"]
        UC2["Gérer les utilisateurs\n(Rôles & Révocation)"]
        UC3["Monitorer les tâches asynchrones\n(Dashboard Django-Q2)"]
        UC4["Consulter l'Audit Log\nglobal (Sécurité)"]
        UC5["Gérer les paramètres globaux\n(Variables applicatives)"]
    end

    RSSI(("⚫ IT Admin /\nSupport"))

    RSSI --- UC1
    RSSI --- UC2
    RSSI --- UC3
    RSSI --- UC4
    RSSI --- UC5
```

---

*Fin de la section §4 — Cas d'Utilisation. La section §5 (Machine à États) suit.*

---

## §5. Machine à États (FSM — Finite State Machine)

Le workflow de Sentinel repose sur 3 machines à états interdépendantes, gérées par `django-fsm` (ADR-07). Le FSM est le **gardien logique central** de l'application : aucune transition non autorisée ne peut se produire, même en cas de manipulation directe de l'ORM.

### 5.1 FSM Recommandation — Cycle de Vie Complet (5 états + flag OVERDUE)

Ce diagramme est le **schéma directeur** de tout le workflow Sentinel. Chaque flèche correspond à une méthode Python décorée `@transition` dans le modèle `Recommendation`, qui vérifie les permissions et déclenche les effets de bord (audit trail, notifications, HMAC).

```mermaid
stateDiagram-v2
    [*] --> ASSIGNED : Audit cree / importe la reco

    state "ASSIGNED" as ASSIGNED
    state "IN_PROGRESS" as IN_PROGRESS
    state "PENDING_DM_REVIEW" as PENDING_DM_REVIEW
    state "PENDING_AUDIT_REVIEW" as PENDING_AUDIT_REVIEW
    state "CLOSED_RESOLVED" as CLOSED_RESOLVED

    ASSIGNED --> IN_PROGRESS : DM delegue a ETP\n[delegate_to_etp()]
    ASSIGNED --> IN_PROGRESS : DM accepte charge (DM seul)\n[accept_by_dm()]
    ASSIGNED --> ASSIGNED : Audit re-assigne DM\n[reassign_dm()]
    ASSIGNED --> ASSIGNED : Audit s auto-assigne\n[self_assign()]

    IN_PROGRESS --> PENDING_DM_REVIEW : ETP soumet preuves\n[submit_to_dm()]
    IN_PROGRESS --> PENDING_AUDIT_REVIEW : DM soumet directement\n[submit_to_audit()]

    PENDING_DM_REVIEW --> PENDING_AUDIT_REVIEW : DM valide + PV recette\n[approve_by_dm()]
    PENDING_DM_REVIEW --> IN_PROGRESS : DM rejette (motif obligatoire)\n[reject_by_dm()]

    PENDING_AUDIT_REVIEW --> CLOSED_RESOLVED : Audit valide et cloture\n[close_by_audit()]\nDeclenche HMAC-SHA256
    PENDING_AUDIT_REVIEW --> IN_PROGRESS : Audit rejette (motif obligatoire)\n[reject_by_audit()]

    CLOSED_RESOLVED --> [*] : Immutable. Aucune mutation.

    state "FLAG OVERDUE" as OVERDUE_NOTE {
        [*] --> activated : Scheduler CRON detecte\necheance depassee
        activated --> [*] : Se superpose a tout\netat sauf CLOSED_RESOLVED
    }

    note right of ASSIGNED
        Seul l Audit peut creer
        Soft Delete possible ici uniquement
        Tag IMPORTED si import historique
    end note

    note right of PENDING_DM_REVIEW
        Rejet trace dans AuditLog
    end note

    note right of CLOSED_RESOLVED
        Sceau HMAC-SHA256 genere
        Toute mutation POST/PUT/DELETE bloquee
        Preuve immutable et archivable
    end note
```

**Matrice des transitions :**

| État source | Transition | État cible | Qui | Condition | Effet de bord |
|---|---|---|---|---|---|
| `ASSIGNED` | `delegate_to_etp()` | `IN_PROGRESS` | DM | ETP dans sa direction | Notif ETP |
| `ASSIGNED` | `accept_by_dm()` | `IN_PROGRESS` | DM | Action directe (sans ETP) | Notif Audit |
| `ASSIGNED` | `reassign_dm()` | `ASSIGNED` | Audit | DM valide | Notif nouveau DM |
| `ASSIGNED` | `self_assign()` | `ASSIGNED` | Audit | — | AuditLog |
| `IN_PROGRESS` | `submit_to_dm()` | `PENDING_DM_REVIEW` | ETP | ≥ 1 preuve DRAFT | Notif DM |
| `IN_PROGRESS` | `submit_to_audit()` | `PENDING_AUDIT_REVIEW` | DM | ≥ 1 preuve DRAFT | Notif Audit |
| `PENDING_DM_REVIEW` | `approve_by_dm()` | `PENDING_AUDIT_REVIEW` | DM | PV recette uploadé | Notif Audit |
| `PENDING_DM_REVIEW` | `reject_by_dm()` | `IN_PROGRESS` | DM | Motif obligatoire | Notif ETP |
| `PENDING_AUDIT_REVIEW` | `close_by_audit()` | `CLOSED_RESOLVED` | Audit | — | HMAC + AuditLog |
| `PENDING_AUDIT_REVIEW` | `reject_by_audit()` | `IN_PROGRESS` | Audit | Motif obligatoire | Notif DM/ETP |

**Gestion de la concurrence :** Chaque transition utilise `select_for_update()` dans une transaction atomique. Si deux utilisateurs tentent de valider simultanément, le premier réussit et le second reçoit une erreur « État modifié ».

### 5.2 FSM Preuve (Proof)

```mermaid
stateDiagram-v2
    [*] --> DRAFT : ETP uploade (brouillon)
    DRAFT --> PENDING : ETP soumet au DM

    PENDING --> ACCEPTED : DM ou Audit valide
    PENDING --> REJECTED : DM ou Audit rejette\n(motif obligatoire)

    REJECTED --> [*] : Conservee en historique\n(jamais supprimee)
    ACCEPTED --> [*] : Incluse dans le sceau HMAC

    note right of DRAFT
        L'auteur (ETP/DM) peut lire
        ou Soft Delete son propre
        brouillon librement.
    end note

    note right of REJECTED
        Version n reste accessible
        ETP cree version n+1 (DRAFT)
        Puis soumission (PENDING)
    end note
```

### 5.3 FSM Demande de Report (ExtensionRequest)

```mermaid
stateDiagram-v2
    [*] --> PENDING : DM soumet demande\n(nouvelle date + justification)

    PENDING --> APPROVED : Audit accepte\nNouvelle echeance enregistree\nCompteur reinitialise
    PENDING --> REJECTED : Audit refuse\nEcheance initiale maintenue

    APPROVED --> [*]
    REJECTED --> [*]

    note right of PENDING
        Ne bloque pas le workflow
        Reco reste dans son etat courant
    end note
```

### 5.4 Edge Cases & Règles de Concurrence

| Scénario | Comportement |
|---|---|
| **Deux DM valident la même reco en même temps** | `select_for_update()` → le premier réussit, le second reçoit une erreur Django |
| **ETP soumet sans preuve uploadée** | Transition bloquée par `django-fsm` (condition pré-transition vérifie `proofs.filter(status=PENDING).exists()`) |
| **Recommandation CLOSED_RESOLVED → tentative de modification** | Middleware + FSM bloquent toute mutation (POST/PUT/DELETE renvoie HTTP 403) |
| **Import de 450 recos avec 1 erreur à la ligne 200** | Transaction atomique → ROLLBACK complet, 0 reco importée |
| **Scheduler détecte OVERDUE sur une reco CLOSED_RESOLVED** | Ignorée : le filtre SQL exclut `status = CLOSED_RESOLVED` |
| **DM soumet un dossier sans ETP (DM Porteur)** | `accept_by_dm()` passe la reco de `ASSIGNED` à `IN_PROGRESS`, débloquant ses droits d'upload de brouillons. |

---

## §6. Diagrammes de Séquence Critiques

Les 8 diagrammes ci-dessous couvrent l'intégralité des flux métier de Sentinel, du plus fréquent (Happy Path) au plus complexe (Scheduler nocturne). Chaque diagramme est identifié par un code stable (`SEQ-01` à `SEQ-08`).

### SEQ-01 : Happy Path Complet (Assignation → Clôture)

Ce diagramme illustre le parcours nominal d'une recommandation, de sa création par l'Audit jusqu'à sa clôture avec sceau HMAC-SHA256.

```mermaid
sequenceDiagram
    autonumber
    actor AU as Auditeur Interne
    actor DM as Directeur Metier
    actor ETP as Employe Traitant
    participant APP as Django SSR + HTMX
    participant FSM as django-fsm
    participant DB as PostgreSQL
    participant Q2 as Django-Q2
    participant SMTP as Serveur Email

    rect rgb(230, 245, 255)
        Note over AU, APP: Phase 1 — Creation et Assignation
        AU->>APP: Cree recommandation (formulaire HTMX)
        APP->>DB: INSERT Recommendation (status=ASSIGNED)
        APP->>DB: INSERT AuditLog (action=CREATE)
        APP-->>AU: Fragment HTML confirme creation

        AU->>APP: Assigne au DM de la direction cible
        APP->>FSM: assign_to_dm(dm_id)
        FSM->>DB: UPDATE status (ASSIGNED)
        APP->>DB: INSERT AuditLog (action=TRANSITION)
        FSM-->>Q2: async_task(send_assignment_notification)
        Q2->>SMTP: Email notification au DM
        APP-->>AU: Fragment HTML mis a jour
    end

    rect rgb(255, 245, 230)
        Note over DM, ETP: Phase 2 — Delegation et Execution
        DM->>APP: Delegue a ETP de son equipe
        APP->>FSM: delegate_to_etp(etp_id)
        FSM->>DB: UPDATE status => IN_PROGRESS
        APP->>DB: INSERT AuditLog (TRANSITION)
        FSM-->>Q2: async_task(send_delegation_notification)
        APP-->>DM: Fragment HTML confirme delegation

        ETP->>APP: Upload preuve (PDF 5Mo)
        APP->>APP: Valide Magic Bytes + Extension
        APP->>DB: INSERT Proof (status=DRAFT, version=1)
        APP->>DB: Sauvegarde fichier renomme UUID sur disque
        APP-->>ETP: Fragment HTML ligne preuve ajoutee (brouillon)

        ETP->>APP: Soumet preuves + commentaire au DM
        APP->>FSM: submit_to_dm()
        FSM->>DB: UPDATE Proof status => PENDING
        FSM->>DB: UPDATE (Recommendation) status => PENDING_DM_REVIEW
        APP->>DB: INSERT Comment (type=SUBMISSION)
        APP->>DB: INSERT AuditLog (TRANSITION)
        FSM-->>Q2: async_task(notify_dm_submission)
        APP-->>ETP: Fragment HTML confirme soumission
    end

    rect rgb(230, 255, 230)
        Note over DM, AU: Phase 3 — Validation et Cloture
        DM->>APP: Verifie preuves + uploade PV recette signe
        APP->>DB: INSERT Proof (type=PV_RECETTE)
        DM->>APP: Valide pour l Audit
        APP->>FSM: approve_by_dm()
        FSM->>DB: UPDATE status => PENDING_AUDIT_REVIEW
        APP->>DB: INSERT AuditLog (TRANSITION)
        FSM-->>Q2: async_task(notify_audit_validation)
        APP-->>DM: Fragment HTML confirme validation

        AU->>APP: Examine preuves et cloture
        APP->>FSM: close_by_audit()
        FSM->>DB: UPDATE status => CLOSED_RESOLVED
        APP->>APP: Calcul HMAC-SHA256 (metadonnees + hash fichiers)
        APP->>DB: INSERT HmacSeal (hash, sealed_metadata)
        APP->>DB: INSERT AuditLog (TRANSITION + CLOSURE)
        APP-->>AU: Fragment HTML avec badge CLOSED + hash affiche
    end
```

### SEQ-02 : Soumission et Validation de Preuve (Détail Technique)

Ce diagramme zoome sur le processus de validation sécurisée d'un fichier uploadé (magic bytes, whitelist, renommage UUID).

```mermaid
sequenceDiagram
    autonumber
    actor USER as ETP / DM
    participant HTML as Navigateur HTMX
    participant VUE as Vue Django
    participant SVC as ProofService
    participant VALID as Validateur Fichier
    participant DISK as File Storage
    participant ORM as Django ORM
    participant LOG as AuditLog

    USER->>HTML: Selectionne fichier + clic Upload
    HTML->>VUE: POST /recos/{id}/proofs/ (multipart/form-data)

    VUE->>VUE: Verifie RBAC (role autorise)
    VUE->>VUE: Verifie FSM (etat autorise upload)

    VUE->>SVC: submit_proof(reco_id, file, user)
    SVC->>VALID: validate_file(file)

    alt Fichier Media (PDF, JPG, PNG)
        VALID->>VALID: Verifie Magic Bytes (python-magic)
        VALID->>VALID: Verifie Extension whitelist
    else Fichier Office/Texte (XLSX, CSV, TXT, MSG, EML)
        VALID->>VALID: Verifie Extension whitelist stricte
        VALID->>VALID: Verifie MIME type primaire
        VALID->>VALID: Rejette si .xlsm ou .docm (macros)
    end

    alt Validation echouee
        VALID-->>SVC: ValidationError (type invalide)
        SVC-->>VUE: Erreur
        VUE-->>HTML: Fragment HTML erreur inline
        HTML-->>USER: Message erreur affiche
    else Validation OK
        VALID-->>SVC: Fichier valide
        SVC->>SVC: Genere nom UUID4 + conserve extension
        SVC->>DISK: Sauvegarde media/proofs/{reco_id}/{uuid}.ext
        SVC->>ORM: INSERT Proof (original_filename, uuid_path, version, status=DRAFT)
        SVC->>LOG: INSERT AuditLog (action=CREATE, object=Proof)
        SVC-->>VUE: Proof creee (brouillon)
        VUE-->>HTML: Fragment HTML avec nouvelle ligne preuve
        HTML-->>USER: DOM mis a jour via hx-swap
    end
```

### SEQ-03 : Rejet et Re-soumission

```mermaid
sequenceDiagram
    autonumber
    actor DM as Directeur Metier
    actor ETP as Employe Traitant
    participant APP as Django SSR
    participant FSM as django-fsm
    participant DB as PostgreSQL
    participant Q2 as Django-Q2

    Note over DM: Reco en PENDING_DM_REVIEW

    DM->>APP: Examine les preuves de l ETP
    DM->>APP: Rejette avec motif "Signature absente"
    APP->>FSM: reject_by_dm(reason="Signature absente")
    FSM->>DB: UPDATE Proof status => REJECTED (version 1)
    FSM->>DB: UPDATE Recommendation status => IN_PROGRESS
    APP->>DB: INSERT Comment (type=REJECTION, "Signature absente")
    APP->>DB: INSERT AuditLog (TRANSITION, before=PENDING_DM_REVIEW, after=IN_PROGRESS)
    FSM-->>Q2: async_task(notify_etp_rejection, reco_id)
    Q2->>ETP: Email "Preuve rejetee — motif: Signature absente"
    APP-->>DM: Fragment HTML confirme rejet

    Note over ETP: ETP recoit la notification

    ETP->>APP: Consulte la reco et le motif de rejet
    APP-->>ETP: Affiche historique V1 REJECTED + motif

    ETP->>APP: Upload nouvelle preuve corrigee
    APP->>DB: INSERT Proof (version=2, status=DRAFT)
    APP-->>ETP: Fragment HTML version 2 ajoutee (brouillon)

    ETP->>APP: Re-soumet + commentaire "Signature ajoutee"
    APP->>FSM: submit_to_dm()
    FSM->>DB: UPDATE Proof status => PENDING
    FSM->>DB: UPDATE (Recommendation) status => PENDING_DM_REVIEW
    APP->>DB: INSERT Comment (type=SUBMISSION)
    APP->>DB: INSERT AuditLog (TRANSITION)
    APP-->>ETP: Fragment HTML confirme re-soumission
```

### SEQ-04 : Demande de Report d'Échéance

```mermaid
sequenceDiagram
    autonumber
    actor DM as Directeur Metier
    actor AU as Auditeur Interne
    participant APP as Django SSR
    participant DB as PostgreSQL
    participant Q2 as Django-Q2

    Note over DM: Reco en IN_PROGRESS, echeance J-10

    DM->>APP: Clic "Demander un report"
    APP-->>DM: Affiche formulaire (nouvelle date + justification)

    DM->>APP: POST nouvelle_date=+60j, justification="Dev IT requis 2 mois"
    APP->>DB: INSERT ExtensionRequest (decision=PENDING)
    APP->>DB: INSERT Comment (type=REPORT)
    APP->>DB: INSERT AuditLog (CREATE ExtensionRequest)
    APP-->>Q2: async_task(notify_audit_extension_request)
    Q2->>AU: Email "Demande de report DM Clair D. — Reco #42"
    APP-->>DM: Fragment HTML confirme envoi demande

    Note over AU: Audit recoit et examine la demande

    alt Audit accepte
        AU->>APP: Approuve la demande
        APP->>DB: UPDATE ExtensionRequest decision=APPROVED
        APP->>DB: UPDATE Recommendation due_date=nouvelle_date
        APP->>DB: INSERT AuditLog (UPDATE, before_date, after_date)
        APP-->>Q2: async_task(notify_dm_extension_approved)
        APP-->>AU: Fragment HTML confirme approbation
    else Audit refuse
        AU->>APP: Refuse avec motif
        APP->>DB: UPDATE ExtensionRequest decision=REJECTED, rejection_reason
        APP->>DB: INSERT AuditLog (UPDATE, decision=REJECTED)
        APP-->>Q2: async_task(notify_dm_extension_rejected)
        APP-->>AU: Fragment HTML confirme refus
    end
```

### SEQ-05 : Import Historique Atomique

```mermaid
sequenceDiagram
    autonumber
    actor AU as Auditeur Interne
    participant APP as Django SSR
    participant SVC as ImportService
    participant DB as PostgreSQL
    participant Q2 as Django-Q2

    AU->>APP: Telecharge template normalise
    APP-->>AU: Fichier Excel/CSV template

    AU->>APP: Upload fichier rempli (450+ lignes)
    APP->>SVC: preview_import(file)
    SVC->>SVC: Parse et valide chaque ligne
    SVC-->>APP: Apercu avec erreurs surlignees
    APP-->>AU: Fragment HTML preview (ligne 42 erreur date)

    AU->>AU: Corrige le fichier hors-ligne

    AU->>APP: Re-upload fichier corrige
    APP->>SVC: preview_import(file)
    SVC-->>APP: Apercu sans erreurs
    APP-->>AU: Fragment HTML preview OK

    AU->>APP: Clic "Lancer import definitif"
    APP->>SVC: execute_import(file, user)

    rect rgb(255, 230, 230)
        Note over SVC, DB: Transaction atomique (tout-ou-rien)
        SVC->>DB: BEGIN TRANSACTION
        loop Pour chaque ligne
            SVC->>DB: INSERT Recommendation (status=ASSIGNED, import_tag=IMPORTED)
            SVC->>DB: INSERT AuditLog (CREATE, tag=IMPORTED)
        end
        alt Erreur a la ligne N
            SVC->>DB: ROLLBACK
            SVC-->>APP: Erreur "Ligne N: [detail]"
            APP-->>AU: Fragment HTML erreur
        else Toutes les lignes OK
            SVC->>DB: COMMIT
            SVC-->>APP: Succes (N recos importees)
            APP-->>AU: Fragment HTML succes + compteur
        end
    end
```

### SEQ-06 : Cycle de Notifications Asynchrones (Scheduler Nocturne)

Ce diagramme illustre le batch nocturne Django-Q2 — le moteur de relance automatique de Sentinel.

```mermaid
sequenceDiagram
    autonumber
    participant CRON as CRON OS (toutes les 2h)
    participant Q2W as Django-Q2 Worker
    participant SVC as NotificationService
    participant DB as PostgreSQL
    participant SMTP as Serveur SMTP
    participant HB as scheduler_heartbeat

    Note over Q2W: Execution nocturne planifiee

    rect rgb(245, 245, 255)
        Note over Q2W, DB: Phase 1 — Detection OVERDUE
        Q2W->>SVC: cron_check_overdue()
        SVC->>DB: SELECT recos WHERE due_date < NOW() AND status != CLOSED_RESOLVED AND is_overdue = false
        DB-->>SVC: Liste recos nouvellement echues
        loop Pour chaque reco echue
            SVC->>DB: UPDATE is_overdue = true
            SVC->>DB: INSERT AuditLog (SYSTEM, "OVERDUE auto-flag")
        end
        SVC->>HB: UPDATE heartbeat timestamp
    end

    rect rgb(255, 245, 245)
        Note over Q2W, SMTP: Phase 2 — Emails consolides
        Q2W->>SVC: cron_send_consolidated_notifications()
        SVC->>DB: SELECT users avec recos OVERDUE, groupees par user
        loop Pour chaque utilisateur
            SVC->>SVC: Genere 1 email consolide (toutes recos OVERDUE)
            alt Priorite CRITIQUE
                SVC->>SVC: Inclut dans digest quotidien
            else Priorite HAUTE/MOYENNE/FAIBLE
                SVC->>SVC: Inclut dans digest hebdomadaire
            end
            SVC->>DB: INSERT Digest (type, recommendation_ids)
            SVC->>SMTP: Envoi email HTML consolide
            alt Envoi reussi
                SVC->>DB: UPDATE Digest send_status=SENT
            else Envoi echoue
                SVC->>DB: UPDATE Digest send_status=FAILED, retry_count++
                Note over SVC: Retry automatique (max 3 tentatives)
            end
        end
    end

    rect rgb(245, 255, 245)
        Note over Q2W, SMTP: Phase 3 — Alertes proactives J-7
        Q2W->>SVC: cron_proactive_alerts()
        SVC->>DB: SELECT recos WHERE due_date = NOW() + 7 days
        loop Pour chaque reco a J-7
            SVC->>DB: INSERT Notification (type=PROACTIVE_J7)
            SVC->>SMTP: Email alerte proactive
        end
    end

    Note over CRON, HB: Monitoring independant
    CRON->>HB: Verifie dernier heartbeat
    alt Heartbeat > 25h
        CRON->>SMTP: ALERTE RSSI "Scheduler mort"
    end
```

### SEQ-07 : Export ZIP Auditeur Externe (COBAC)

```mermaid
sequenceDiagram
    autonumber
    actor EXT as Auditeur Externe COBAC
    participant HTML as Navigateur HTMX
    participant VUE as Vue Django
    participant RBAC as Middleware RBAC
    participant SEL as Selector
    participant EXP as ZipArchiveExport
    participant DISK as File Storage
    participant DB as PostgreSQL

    EXT->>HTML: Clic "Telecharger Archive ZIP"
    HTML->>VUE: GET /recos/{id}/export-zip/

    VUE->>RBAC: Verifie role EXTERNE + perimetre mission
    RBAC->>DB: SELECT mission WHERE auditor_id AND is_active
    RBAC->>DB: Verifie reco_id IN mission.recommendations

    alt Acces refuse
        RBAC-->>VUE: 403 Forbidden
        VUE-->>HTML: Page erreur "Acces non autorise"
    else Acces autorise
        VUE->>SEL: get_recommendation_for_export(reco_id)
        SEL->>DB: SELECT reco + preuves ACCEPTED + sceau HMAC
        SEL-->>VUE: Donnees reco completes

        VUE->>EXP: generate(reco, preuves)
        EXP->>EXP: Cree ZIP en memoire (io.BytesIO)
        loop Pour chaque preuve ACCEPTED
            EXP->>DISK: Lecture fichier streaming
            EXP->>EXP: Ajoute au ZIP
        end
        EXP->>EXP: Genere fiche_synthese.pdf (statuts, dates, hash)
        EXP->>EXP: Ajoute fiche_synthese au ZIP
        EXP-->>VUE: ZIP complet (< 5 secondes)

        VUE->>DB: INSERT AuditLog (EXPORT, reco_id, user=EXT)
        VUE-->>HTML: FileResponse streaming (Content-Disposition: attachment)
        HTML-->>EXT: Telechargement ZIP demarre
    end
```

### SEQ-08 : Authentification et Contrôle de Session

```mermaid
sequenceDiagram
    autonumber
    actor USER as Utilisateur
    participant HTML as Navigateur
    participant VUE as LoginView
    participant AUTH as django.contrib.auth
    participant AXES as django-axes
    participant DB as PostgreSQL
    participant LOG as AuditLog
    participant SESS as Session Store (DB)

    USER->>HTML: Saisit username + password
    HTML->>VUE: POST /login/ (CSRF token inclus)

    VUE->>AXES: Verifie tentatives precedentes
    alt Compte verrouille (>= 5 echecs)
        AXES-->>VUE: AccessAttempt bloque
        VUE-->>HTML: "Compte verrouille. Contactez l admin."
    else Compte non verrouille
        VUE->>AUTH: authenticate(username, password)
        alt Credentials invalides
            AUTH-->>VUE: None
            VUE->>AXES: Enregistre echec
            VUE->>LOG: INSERT AuditLog (LOGIN_FAILED, ip)
            VUE-->>HTML: "Identifiants incorrects"
        else Credentials valides
            AUTH-->>VUE: User object
            VUE->>AUTH: login(request, user)
            AUTH->>SESS: Cree session (expiry=1800s)
            AUTH->>DB: INSERT django_session
            VUE->>LOG: INSERT AuditLog (LOGIN, user, ip)
            VUE->>DB: set_config(app.tenant_id, user.department_id)
            VUE-->>HTML: Set-Cookie (HttpOnly, Secure, SameSite=Lax)
            HTML-->>USER: Redirect vers dashboard role
        end
    end

    Note over HTML, SESS: Apres connexion — chaque requete

    USER->>HTML: Navigue dans l application
    HTML->>VUE: GET /dashboard/ (cookie session)
    VUE->>SESS: Verifie session valide
    alt Session expiree (> 30min inactivite)
        SESS-->>VUE: Session invalide
        VUE-->>HTML: Redirect /login/ (message session expiree)
    else Session valide
        SESS-->>VUE: Session OK
        VUE->>SESS: SESSION_SAVE_EVERY_REQUEST=True (reset timer)
        VUE->>VUE: Continue traitement normal
    end
```

---

*Fin de la section §6 — Séquences. La section §7 (Modèle de Données) suit.*

---

## §7. Modèle de Données

Cette section présente la structure de données de Sentinel à trois niveaux d'abstraction : conceptuel (MCD), logique (ERD) et sémantique (Data Dictionary). L'ensemble est implémenté sur PostgreSQL 16 avec des triggers d'audit natifs, `pgcrypto` pour le HMAC-SHA256 et des policies RLS sur les tables critiques.

### 7.1 Modèle Conceptuel de Données (MCD)

Le MCD représente les entités métier et leurs relations conceptuelles, indépendamment de l'implémentation technique. Il sert de **carte de lecture** pour les non-développeurs (Direction IT, auditeurs COBAC).

```mermaid
erDiagram
    UTILISATEUR {
        string nom
        string prenom
        string email
        string role_principal
        boolean is_active
    }

    DIRECTION {
        string nom
        string code
        string type
    }

    RECOMMANDATION {
        string titre
        string description
        string source
        string priorite
        date date_echeance
        string statut_fsm
        boolean is_overdue
        boolean is_deleted
        string tag_import
    }

    PREUVE {
        string nom_original
        string chemin_uuid
        string type_mime
        int taille_octets
        string statut
        int version
    }

    COMMENTAIRE {
        string contenu
        string type
        datetime date_creation
    }

    INTERIM {
        date date_debut
        date date_fin
        boolean is_active
    }

    DEMANDE_REPORT {
        date nouvelle_echeance
        string justification
        string statut_decision
        string motif_refus
    }

    JOURNAL_AUDIT {
        string action
        string type_entite
        string id_entite
        json changements
        string adresse_ip
        datetime horodatage
    }

    SCEAU_HMAC {
        string hash_sha256
        json metadonnees_scellees
        datetime date_scellement
    }

    NOTIFICATION {
        string type
        string statut_envoi
        string canal
        datetime date_planifiee
    }

    MISSION_EXTERNE {
        string organisme
        string perimetre
        date date_debut
        date date_fin
    }

    UTILISATEUR ||--o{ DIRECTION : "appartient a"
    DIRECTION ||--o{ RECOMMANDATION : "concerne"
    UTILISATEUR ||--o{ RECOMMANDATION : "cree"
    UTILISATEUR ||--o{ RECOMMANDATION : "est assigne DM"
    UTILISATEUR ||--o{ RECOMMANDATION : "est assigne ETP"
    RECOMMANDATION ||--o{ PREUVE : "contient"
    UTILISATEUR ||--o{ PREUVE : "uploade"
    RECOMMANDATION ||--o{ COMMENTAIRE : "recoit"
    UTILISATEUR ||--o{ COMMENTAIRE : "redige"
    RECOMMANDATION ||--o{ DEMANDE_REPORT : "fait objet de"
    UTILISATEUR ||--o{ DEMANDE_REPORT : "initie"
    UTILISATEUR ||--o{ DEMANDE_REPORT : "decide"
    RECOMMANDATION ||--o| SCEAU_HMAC : "est scellee par"
    RECOMMANDATION ||--o{ JOURNAL_AUDIT : "est tracee dans"
    UTILISATEUR ||--o{ NOTIFICATION : "recoit"
    RECOMMANDATION ||--o{ NOTIFICATION : "declenche"
    UTILISATEUR ||--o{ MISSION_EXTERNE : "est lie a"
    MISSION_EXTERNE ||--o{ RECOMMANDATION : "donne acces a"
    UTILISATEUR ||--o{ INTERIM : "delegue ses droits"
    UTILISATEUR ||--o{ INTERIM : "recoit delegation"
```

### 7.2 Entity-Relationship Diagram (ERD — Modèle Logique)

L'ERD détaille la structure physique de la base de données PostgreSQL avec les types de colonnes, clés primaires/étrangères, contraintes d'unicité et relations. Les 11 tables principales couvrent l'intégralité des besoins fonctionnels (31 FR).

```mermaid
erDiagram
    users_department {
        uuid id PK
        varchar(100) name
        varchar(10) code UK
        varchar(20) type "DIRECTION | AGENCE | FILIALE"
        uuid parent_id FK "Self-referencing"
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    users_user {
        uuid id PK
        varchar(150) username UK
        varchar(254) email UK
        varchar(128) password_hash
        varchar(50) first_name
        varchar(50) last_name
        varchar(20) role "AUDIT | DM | ETP | DG | EXTERNE | RSSI"
        uuid department_id FK
        boolean is_active
        boolean is_staff
        timestamp last_login
        timestamp date_joined
        timestamp created_at
        timestamp updated_at
    }

    users_delegation {
        uuid id PK
        uuid delegator_id FK "Utilisateur absent"
        uuid delegate_id FK "Interimaire"
        date start_date
        date end_date
        boolean is_active
        timestamp created_at
    }

    workflow_recommendation {
        uuid id PK
        varchar(255) title
        text description
        varchar(20) source "INTERNE | COBAC | BEAC | CAC | NIF | CONSULTANT"
        varchar(10) priority "CRITIQUE | HAUTE | MOYENNE | FAIBLE"
        varchar(30) status "FSM: 5 etats"
        boolean is_overdue
        date due_date
        date original_due_date
        uuid created_by_id FK
        uuid assigned_dm_id FK
        uuid assigned_etp_id FK
        uuid department_id FK
        varchar(10) import_tag "IMPORTED | null"
        boolean is_deleted
        timestamp deleted_at
        text reference_rapport
        timestamp created_at
        timestamp updated_at
    }

    workflow_proof {
        uuid id PK
        uuid recommendation_id FK
        uuid uploaded_by_id FK
        varchar(255) original_filename
        varchar(255) file_path "UUID renamed"
        varchar(100) content_type
        integer file_size_bytes
        varchar(20) status "DRAFT | PENDING | ACCEPTED | REJECTED"
        integer version
        text rejection_reason
        varchar(10) proof_type "EVIDENCE | PV_RECETTE"
        timestamp created_at
    }

    workflow_comment {
        uuid id PK
        uuid recommendation_id FK
        uuid author_id FK
        text content
        varchar(20) type "SUBMISSION | VALIDATION | REJECTION | REASSIGN | REPORT | SYSTEM"
        timestamp created_at
    }

    workflow_extension_request {
        uuid id PK
        uuid recommendation_id FK
        uuid requested_by_id FK
        uuid decided_by_id FK
        date new_due_date
        text justification
        varchar(20) decision "PENDING | APPROVED | REJECTED"
        text rejection_reason
        timestamp created_at
        timestamp decided_at
    }

    audit_auditlog {
        uuid id PK
        uuid user_id FK "nullable (null si systeme)"
        varchar(20) action "CREATE | UPDATE | DELETE | LOGIN | LOGIN_FAILED | LOGOUT | TRANSITION | SYSTEM | EXPORT"
        varchar(50) content_type
        uuid object_id
        jsonb changes "Before/After diff"
        inet ip_address
        varchar(200) description
        timestamp created_at
    }

    audit_hmac_seal {
        uuid id PK
        uuid recommendation_id FK "1-to-1"
        varchar(64) hmac_hash
        jsonb sealed_metadata
        jsonb file_hashes "Hash de chaque preuve"
        uuid sealed_by_id FK
        timestamp sealed_at
    }

    notifications_notification {
        uuid id PK
        uuid user_id FK
        uuid recommendation_id FK
        varchar(30) type "ASSIGNMENT | SUBMISSION | OVERDUE | PROACTIVE_J7 | REJECTION | CLOSURE"
        varchar(10) channel "EMAIL | IN_APP"
        varchar(20) send_status "PENDING | SENT | FAILED"
        integer retry_count
        text error_message
        timestamp scheduled_at
        timestamp sent_at
        boolean is_read
        timestamp created_at
    }

    notifications_digest {
        uuid id PK
        uuid user_id FK
        varchar(20) digest_type "DAILY_CRITICAL | WEEKLY_DIGEST"
        jsonb recommendation_ids
        varchar(20) send_status "PENDING | SENT | FAILED"
        timestamp scheduled_at
        timestamp sent_at
    }

    users_external_mission {
        uuid id PK
        uuid auditor_id FK
        varchar(100) organization "COBAC | BEAC | CAC | NIF"
        text scope_description
        date start_date
        date end_date
        boolean is_active
        timestamp created_at
    }

    external_mission_recommendations {
        uuid id PK
        uuid mission_id FK
        uuid recommendation_id FK
    }

    django_q2_schedule {
        integer id PK
        varchar(255) name
        varchar(255) func
        text kwargs
        varchar(20) schedule_type
        integer minutes
        timestamp next_run
    }

    users_user }o--|| users_department : "department_id"
    users_department }o--o| users_department : "parent_id"
    workflow_recommendation }o--|| users_department : "department_id"
    workflow_recommendation }o--|| users_user : "created_by_id"
    workflow_recommendation }o--o| users_user : "assigned_dm_id"
    workflow_recommendation }o--o| users_user : "assigned_etp_id"
    workflow_proof }o--|| workflow_recommendation : "recommendation_id"
    workflow_proof }o--|| users_user : "uploaded_by_id"
    workflow_comment }o--|| workflow_recommendation : "recommendation_id"
    workflow_comment }o--|| users_user : "author_id"
    workflow_extension_request }o--|| workflow_recommendation : "recommendation_id"
    workflow_extension_request }o--|| users_user : "requested_by_id"
    workflow_extension_request }o--o| users_user : "decided_by_id"
    audit_auditlog }o--o| users_user : "user_id"
    audit_hmac_seal |o--|| workflow_recommendation : "recommendation_id"
    audit_hmac_seal }o--|| users_user : "sealed_by_id"
    notifications_notification }o--|| users_user : "user_id"
    notifications_notification }o--o| workflow_recommendation : "recommendation_id"
    notifications_digest }o--|| users_user : "user_id"
    users_external_mission }o--|| users_user : "auditor_id"
    external_mission_recommendations }o--|| users_external_mission : "mission_id"
    external_mission_recommendations }o--|| workflow_recommendation : "recommendation_id"
    users_delegation }o--|| users_user : "delegator_id"
    users_delegation }o--|| users_user : "delegate_id"
```

### 7.3 Data Dictionary — Champs Critiques

Ce dictionnaire de données explique l'**enjeu métier** de chaque colonne critique. Il va au-delà de l'ERD en documentant le « pourquoi » et le « comment » de chaque champ, à destination des développeurs, auditeurs et inspecteurs COBAC.

#### Catégorie 1 — Workflow & Conformité Réglementaire

| Table | Colonne | Type | Contrainte | Description / Enjeu Métier | Exemple |
|---|---|---|---|---|---|
| `workflow_recommendation` | `source` | `VARCHAR(20)` | NOT NULL, CHECK | Origine réglementaire de la recommandation. Détermine la **charge réglementaire** associée (une recommandation COBAC a plus de poids qu'une recommandation interne). Influence les filtres du dashboard DG. | `COBAC` |
| `workflow_recommendation` | `priority` | `VARCHAR(10)` | NOT NULL, CHECK | Niveau d'urgence. Conditionne la **couleur UI** du dashboard (Rouge=CRITIQUE, Orange=HAUTE, Vert=MOYENNE/FAIBLE) et la **fréquence des relances email** (quotidien vs hebdomadaire). | `CRITIQUE` |
| `workflow_recommendation` | `status` | `VARCHAR(30)` | NOT NULL, FSM | État courant piloté par `django-fsm`. Cette colonne **régit les droits d'écriture** : seules les transitions autorisées peuvent modifier la valeur. Aucune UPDATE directe n'est permise en dehors du FSM. | `PENDING_DM_REVIEW` |
| `workflow_recommendation` | `is_overdue` | `BOOLEAN` | NOT NULL, DEFAULT false | Flag calculé automatiquement par le **scheduler nocturne** Django-Q2. Déclenche une alerte visuelle prioritaire dans tous les dashboards et l'inclusion dans le digest email consolidé. N'est jamais recalculé sur `CLOSED_RESOLVED`. | `true` |
| `workflow_recommendation` | `import_tag` | `VARCHAR(10)` | NULLABLE | Prouve qu'une recommandation est issue du **chargement historique initial** (450+ recos). Valeur `IMPORTED` inaltérable une fois posée. Permet de distinguer les recos migrées des recos créées manuellement dans Sentinel. | `IMPORTED` |
| `workflow_recommendation` | `original_due_date` | `DATE` | NOT NULL | Date d'échéance **exigée à l'origine**, avant toute demande de report accordée. Conservée intacte même si `due_date` est modifié par un report approuvé. Essentielle pour les rapports de conformité COBAC (écart entre deadline initiale et réelle). | `2026-06-15` |
| `workflow_extension_request` | `decision` | `VARCHAR(20)` | NOT NULL, CHECK | Statut de la demande de report. Fournit la **justification légale** d'un changement de deadline auprès du régulateur (COBAC peut demander pourquoi une échéance a glissé). Toute approbation/refus est tracée dans l'audit trail. | `APPROVED` |

#### Catégorie 2 — Preuves Documentaires (Security-by-Design)

| Table | Colonne | Type | Contrainte | Description / Enjeu Métier | Exemple |
|---|---|---|---|---|---|
| `workflow_proof` | `status` | `VARCHAR(20)` | NOT NULL, CHECK | Statut de la preuve dans le cycle de validation. Un fichier **rejeté reste tracé** dans la base (jamais supprimé physiquement) — la version N est conservée en historique quand l'ETP soumet la version N+1. | `REJECTED` |
| `workflow_proof` | `version` | `INTEGER` | NOT NULL, DEFAULT 1 | Itération du fichier de preuve. Prouve la **traçabilité des corrections** : v1 rejetée → v2 acceptée. L'inspecteur COBAC peut reconstituer l'historique complet des soumissions. | `2` |
| `workflow_proof` | `content_type` | `VARCHAR(100)` | NOT NULL | Le vrai type MIME inspecté lors de l'upload (pas le type déclaré par le navigateur). Vérifié par `python-magic` (médias) ou par la whitelist stricte (Office/Texte). **Bloque les payloads malveillants** déguisés en fichiers légitimes. | `application/pdf` |
| `workflow_proof` | `file_path` | `VARCHAR(255)` | NOT NULL, UK | Chemin physique du fichier sur le disque, renommé en **UUIDv4** à l'upload. Sécurité contre les attaques de type **Path Traversal** (l'attaquant ne peut pas deviner ou manipuler le nom de fichier). Le nom original est conservé dans `original_filename`. | `proofs/a1b2c3d4/e5f6-...-.pdf` |

#### Catégorie 3 — Traçabilité, Conformité & Audit COBAC

| Table | Colonne | Type | Contrainte | Description / Enjeu Métier | Exemple |
|---|---|---|---|---|---|
| `users_user` | `role` | `VARCHAR(20)` | NOT NULL, CHECK | **Clé de voûte du RBAC**. Détermine les actions autorisées (voir §4 Use Cases), les dashboards accessibles et les données visibles (couplé au `department_id`). Immuable par l'utilisateur lui-même. | `DM` |
| `audit_auditlog` | `action` | `VARCHAR(20)` | NOT NULL | L'événement précis stocké pendant **12 mois minimum** (NFR-SEC-05). Catégories : `CREATE`, `UPDATE`, `DELETE` (soft), `LOGIN`, `LOGIN_FAILED`, `LOGOUT`, `TRANSITION`, `EXPORT`. Chaque action est un enregistrement append-only. | `TRANSITION` |
| `audit_auditlog` | `changes` | `JSONB` | NULLABLE | Le **différentiel exact** (avant/après) pour chaque champ modifié. Format structuré permettant la reconstruction complète de l'historique d'une recommandation. Essentiel pour répondre à la question d'un inspecteur : « Qui a changé quoi, et quand ? ». | `{"status": ["IN_PROGRESS", "CLOSED_RESOLVED"]}` |
| `audit_auditlog` | `ip_address` | `INET` | NULLABLE | Adresse IP interne (réseau BICEC) d'où l'action a été exécutée. **Preuve d'imputabilité** : en cas d'incident de sécurité, permet de remonter au poste de travail physique. Type PostgreSQL natif `inet` pour queries optimisées. | `10.0.5.42` |
| `audit_hmac_seal` | `sealed_metadata` | `JSONB` | NOT NULL | L'**empreinte inaltérable** de la recommandation au moment de la clôture. Contient un snapshot figé : titre, description, source, priorité, dates, DM assigné, statut final. Toute modification post-clôture rompt le hash HMAC et est détectable. | `{"title": "...", "status": "CLOSED_RESOLVED", ...}` |
| `audit_hmac_seal` | `file_hashes` | `JSONB` | NOT NULL | Les **hashs SHA-256 individuels** de chaque fichier de preuve accepté. Permet de vérifier, à tout moment, qu'aucun fichier n'a été corrompu ou remplacé sur le disque après la clôture. | `{"proof_uuid_1": "a3f2...", "proof_uuid_2": "b7e1..."}` |

---

## §8. Diagramme de Classes (Architecture Clean — HackSoft)

Le code source de Sentinel est organisé selon l'architecture **HackSoft Styleguide** pour Django, qui structure chaque domaine métier en 4 couches strictes :

| Couche | Responsabilité | Règle |
|---|---|---|
| **Model** | Colonnes de la table + méthodes de domaine + transitions FSM | Aucune requête SQL complexe — uniquement les champs et les méthodes liées à l'instance |
| **Selector** | Requêtes de lecture (QuerySet avec filtres, annotations, agrégations) | N'écrit **jamais** en base. Retourne des QuerySets ou des dicts |
| **Service** | Logique métier d'écriture (création, transitions, imports, exports) | Orchestre Models + Selectors. Point d'entrée unique pour toute mutation |
| **View** | Interface HTTP (reçoit une requête, appelle un Service/Selector, renvoie du HTML) | Aucune logique métier — délègue tout au Service |

```mermaid
classDiagram
    direction TB

    %% ===== DOMAIN: USERS =====
    namespace UsersApp {
        class Department {
            +UUID id
            +String name
            +String code
            +String type
            +Department parent
            +Boolean is_active
            +DateTime created_at
            +DateTime updated_at
            +get_children() List~Department~
            +get_full_hierarchy() List~Department~
        }

        class User {
            +UUID id
            +String username
            +String email
            +String first_name
            +String last_name
            +String role
            +Department department
            +Boolean is_active
            +DateTime last_login
            +DateTime date_joined
            +has_role(role_name) Boolean
            +get_accessible_departments() QuerySet
        }

        class Delegation {
            +UUID id
            +User delegator
            +User delegate
            +Date start_date
            +Date end_date
            +Boolean is_active
            +DateTime created_at
            +is_currently_active() Boolean
        }

        class ExternalMission {
            +UUID id
            +User auditor
            +String organization
            +String scope_description
            +Date start_date
            +Date end_date
            +Boolean is_active
            +ManyToMany recommendations
        }

        class UserSelector {
            +get_users_by_direction(dept_id) QuerySet
            +get_active_dm_for_direction(dept_id) QuerySet
            +get_etp_for_dm(dm_user) QuerySet
            +get_user_permissions(user) Dict
        }

        class UserService {
            +create_user(data) User
            +update_user_role(user_id, role) User
            +deactivate_user(user_id) None
            +invalidate_all_sessions(user_id) None
        }

        class RBACPermission {
            +check_permission(user, action, obj) Boolean
            +get_allowed_transitions(user, reco) List
            +inject_tenant_context(user) None
        }
    }

    %% ===== DOMAIN: WORKFLOW =====
    namespace WorkflowApp {
        class Recommendation {
            +UUID id
            +String title
            +Text description
            +SourceEnum source
            +PriorityEnum priority
            +FSMField status
            +Boolean is_overdue
            +Date due_date
            +Date original_due_date
            +User created_by
            +User assigned_dm
            +User assigned_etp
            +Department department
            +String import_tag
            +Boolean is_deleted
            +assign_to_dm(dm) void
            +accept_by_dm() void
            +delegate_to_etp(etp) void
            +submit_to_dm() void
            +submit_to_audit() void
            +approve_by_dm() void
            +reject_by_dm(reason) void
            +close_by_audit() void
            +reject_by_audit(reason) void
        }

        class Proof {
            +UUID id
            +Recommendation recommendation
            +User uploaded_by
            +String original_filename
            +String file_path
            +String content_type
            +Integer file_size_bytes
            +StatusEnum status
            +Integer version
            +String rejection_reason
            +ProofTypeEnum proof_type
            +DateTime created_at
        }

        class Comment {
            +UUID id
            +Recommendation recommendation
            +User author
            +Text content
            +CommentTypeEnum type
            +DateTime created_at
        }

        class ExtensionRequest {
            +UUID id
            +Recommendation recommendation
            +User requested_by
            +User decided_by
            +Date new_due_date
            +Text justification
            +DecisionEnum decision
            +Text rejection_reason
            +DateTime decided_at
        }

        class RecommendationSelector {
            +for_tenant(user) QuerySet
            +for_direction(dept_id) QuerySet
            +for_external_mission(mission_id) QuerySet
            +get_overdue_recommendations(user) QuerySet
            +get_dashboard_stats(user) Dict
            +get_by_status(status, user) QuerySet
            +get_aging_over_24months(user) QuerySet
        }

        class WorkflowService {
            +create_recommendation(data, user) Recommendation
            +bulk_create(data_list, user) List
            +soft_delete(reco_id, user) None
            +assign_dm(reco_id, dm_id, user) None
            +delegate_etp(reco_id, etp_id, user) None
            +reassign_dm(reco_id, new_dm_id, user) None
        }

        class ProofService {
            +upload_proof(reco_id, file, user) Proof
            +submit_proofs(reco_id, user) List
            +validate_file(file) Boolean
            +soft_delete_proof(proof_id, user) None
        }

        class ImportService {
            +preview_import(file) PreviewResult
            +execute_import(file, user) ImportResult
            +download_template() FileResponse
        }

        class ExtensionService {
            +request_extension(reco_id, data, user) ExtensionRequest
            +approve_extension(ext_id, user) None
            +reject_extension(ext_id, reason, user) None
        }
    }

    %% ===== DOMAIN: AUDIT =====
    namespace AuditApp {
        class AuditLog {
            +UUID id
            +User user
            +ActionEnum action
            +String content_type
            +UUID object_id
            +JSONB changes
            +IPAddress ip_address
            +String description
            +DateTime created_at
        }

        class HmacSeal {
            +UUID id
            +Recommendation recommendation
            +String hmac_hash
            +JSONB sealed_metadata
            +JSONB file_hashes
            +User sealed_by
            +DateTime sealed_at
        }

        class CryptoService {
            +generate_hmac_seal(reco) HmacSeal
            +verify_hmac_seal(reco) Boolean
            +compute_file_hash(file_path) String
        }

        class ExportStrategy {
            <<interface>>
            +generate(reco, preuves) BytesIO
        }

        class ZipArchiveExport {
            +generate(reco, preuves) BytesIO
        }

        class AuditTrailSelector {
            +get_timeline(reco_id) QuerySet
            +get_logs_by_user(user_id) QuerySet
            +get_system_logs(days) QuerySet
        }
    }

    %% ===== DOMAIN: NOTIFICATIONS =====
    namespace NotificationsApp {
        class Notification {
            +UUID id
            +User user
            +Recommendation recommendation
            +NotifTypeEnum type
            +ChannelEnum channel
            +StatusEnum send_status
            +Integer retry_count
            +DateTime scheduled_at
            +DateTime sent_at
            +Boolean is_read
        }

        class Digest {
            +UUID id
            +User user
            +DigestTypeEnum digest_type
            +JSONB recommendation_ids
            +StatusEnum send_status
            +DateTime scheduled_at
            +DateTime sent_at
        }

        class NotificationTask {
            +cron_check_overdue() None
            +cron_send_consolidated_notifications() None
            +cron_proactive_alerts() None
            +send_single_notification(notif_id) None
        }

        class EmailService {
            +send_consolidated_email(user, recos) Boolean
            +send_proactive_alert(user, reco) Boolean
            +send_assignment_notification(reco) Boolean
        }
    }

    %% ===== ENUMS =====
    namespace Enumerations {
        class SourceEnum {
            <<enumeration>>
            INTERNE
            COBAC
            BEAC
            CAC
            NIF
            CONSULTANT
        }

        class PriorityEnum {
            <<enumeration>>
            CRITIQUE
            HAUTE
            MOYENNE
            FAIBLE
        }

        class RecoStatusEnum {
            <<enumeration>>
            ASSIGNED
            IN_PROGRESS
            PENDING_DM_REVIEW
            PENDING_AUDIT_REVIEW
            CLOSED_RESOLVED
        }

        class ProofStatusEnum {
            <<enumeration>>
            DRAFT
            PENDING
            ACCEPTED
            REJECTED
        }
    }

    %% ===== RELATIONSHIPS =====
    User "*" --> "1" Department : belongs to
    Department "0..1" --> "0..*" Department : parent
    ExternalMission "*" --> "1" User : auditor
    ExternalMission "*" --> "*" Recommendation : scoped to

    Recommendation "*" --> "1" Department : department
    Recommendation "*" --> "1" User : created_by
    Recommendation "*" --> "0..1" User : assigned_dm
    Recommendation "*" --> "0..1" User : assigned_etp
    Proof "*" --> "1" Recommendation : belongs to
    Proof "*" --> "1" User : uploaded_by
    Comment "*" --> "1" Recommendation : belongs to
    Comment "*" --> "1" User : author
    ExtensionRequest "*" --> "1" Recommendation : for
    ExtensionRequest "*" --> "1" User : requested_by
    ExtensionRequest "*" --> "0..1" User : decided_by

    AuditLog "*" --> "0..1" User : performed by
    HmacSeal "1" --> "1" Recommendation : seals
    HmacSeal "*" --> "1" User : sealed_by

    Notification "*" --> "1" User : for
    Notification "*" --> "0..1" Recommendation : about
    Digest "*" --> "1" User : for

    Recommendation ..> SourceEnum : uses
    Recommendation ..> PriorityEnum : uses
    Recommendation ..> RecoStatusEnum : FSM status
    Proof ..> ProofStatusEnum : uses

    ExportStrategy <|.. ZipArchiveExport : implements

    RecommendationSelector ..> Recommendation : reads
    WorkflowService ..> Recommendation : writes
    ProofService ..> Proof : writes
    CryptoService ..> HmacSeal : creates
    NotificationTask ..> Notification : creates
    NotificationTask ..> EmailService : uses
    AuditTrailSelector ..> AuditLog : reads
    UserSelector ..> User : reads
    UserService ..> User : writes
    RBACPermission ..> User : checks
    ImportService ..> WorkflowService : uses
    ExtensionService ..> ExtensionRequest : manages
```

---

*Fin de la section §8 — Classes. La section §9 (Sécurité Architecture) suit.*

---

## §9. Sécurité Architecture & Conformité COBAC

La sécurité de Sentinel n'est pas ajoutée en fin de projet, elle est **by-design**, tissée dans l'architecture même pour répondre aux exigences strictes de la Commission Bancaire de l'Afrique Centrale (COBAC). Cette section documente les mécanismes de protection contre les cybermenaces internes (fraude, altération) et externes.

### 9.1 Modèle de Défense en Profondeur (Defense in Depth)

Sentinel applique le principe de défense en profondeur : si une barrière de sécurité cède (ex: faille dans une vue), une barrière sous-jacente (ex: `django-fsm` ou PostgreSQL RLS) stoppe l'attaque.

| Couche (Layer) | Composant Technique | Rôle Sécuritaire | Conséquence contournement |
|---|---|---|---|
| **L1. Réseau & Infra** | Nginx Reverse Proxy | Terminaison TLS 1.2/1.3 stricte, blocage des requêtes malformées, Rate Limiting natif. | Les requêtes HTTP claires sont impossibles. L'Infra BICEC cloisonne la VM. |
| **L2. Protection Web** | Middleware Django + HTMX | Headers (HSTS, CSP, X-Frame-Options). Protection CSRF `SameSite=Lax`. Validation Formulaires. | Bloque XSS, Clickjacking, CSRF. HTMX n'exécutant pas de script JSON limite les vecteurs d'attaque. |
| **L3. Authentification** | `django-axes` + Sessions | Cookies Stateful HttpOnly/Secure. Verrouillage après 5 échecs consécutifs. | Bloque le Brute-Force et le vol de session via JavaScript (XSS). |
| **L4. Filtrage Métier** | RBAC Middleware + Selectors | Bloque l'accès aux URLs non autorisées. Pré-filtre les QuerySets selon le `department_id`. | Un utilisateur malveillant ne peut lire/modifier que les données de son périmètre. |
| **L5. Workflow (FSM)** | `django-fsm` | Interdit les sauts d'états illogiques (ex: de PENDING à CLOSED directement). | Une requête POST falsifiée est rejetée au niveau du modèle Python. |
| **L6. Persistance (BDD)** | PostgreSQL RLS + Triggers | Row Level Security empêche la lecture hors-scope. Triggers interceptent chaque `INSERT/UPDATE/DELETE`. | Même un DBA malveillant exécutant du SQL direct laisse une trace dans l'Audit Trail. |
| **L7. Intégrité Crypto** | Sceau HMAC-SHA256 | Apposé à la clôture, le sceau lie indissociablement les métadonnées et les fichiers liés. | Toute altération post-clôture rompt mathématiquement l'intégrité de la preuve vis-à-vis du régulateur. |

### 9.2 Matrice Globale des Droits d'Accès (RBAC)

L'accès aux données est régi par un modèle matriciel strict (*Role-Based Access Control*).

Légende : **R** (Read), **C** (Create), **U** (Update), **D** (Delete/Soft-Delete), **X** (Transition FSM), **-** (Interdit)

| Objet Métier | Auditeur Interne | Directeur Métier (DM) | Employé (ETP) | Auditeur Externe | DG | RSSI |
|---|---|---|---|---|---|---|
| **Recommandation** | R, C, U¹, D¹, X | R², X² | R³ | R⁴ | R | - |
| **Preuve (Proof)** | R | R, X | R, C, X | R⁶ | R | - |
| **Commentaire** | R, C | R, C | R, C | - | - | - |
| **Demande de Report**| R, X | R, C | R | - | R | - |
| **Audit Trail** | R | R (sur ses recos) | R (sur ses recos) | - | R | R |
| **Utilisateurs / Rôles**| R, C, U (Métier) | R | - | - | - | R, C, U, D |
| **Logs Système** | - | - | - | - | - | R, Export |

*Restrictions contextuelles :*
- ¹ Uniquement si la recommandation est à l'état `ASSIGNED`.
- ² Uniquement les recommandations assignées à sa direction.
- ³ Uniquement les recommandations qui lui sont spécifiquement déléguées.
- ⁴ Uniquement les recommandations du périmètre de sa mission.
- ⁵ `Soft-Delete` autorisé uniquement tant que la preuve est au statut `PENDING`.
- ⁶ Lecture limitée aux preuves `ACCEPTED` sur les recos `CLOSED_RESOLVED`.

### 9.3 Conformité COBAC : Traçabilité & Immutabilité

Le système est conçu pour répondre aux audits annuels de la COBAC, qui exigent la preuve indéniable des actions correctives.

#### A. Architecture Append-Only (Audit Trail)
- **Principe :** Dans Sentinel, la donnée métier n'est **jamais supprimée physiquement** (`DELETE` SQL interdit par trigger). Le système est *Append-Only* (ajout seul).
- **Soft Delete :** Les suppressions (ex: annuler une recommandation, supprimer une preuve erronée) utilisent un flag `is_deleted=True` ou basculent le statut à `REJECTED`.
- **Triggers PostgreSQL :** Même en cas d'accès direct à la base par un administrateur système, tout événement de création/modification insère une ligne dans la table `audit_auditlog` avec l'ancien état, le nouvel état (JSONB), l'IP et l'horodatage.

#### B. Sceau Cryptographique (HMAC-SHA256)
- **Objectif :** Garantir qu'une recommandation clôturée n'a pas été altérée a posteriori (y compris par l'équipe IT de la BICEC).
- **Génération :** Lors du passage à l'état `CLOSED_RESOLVED`, le système concatène un dictionnaire normalisé des données de la recommandation (titre, échéance...) + les hashs SHA-256 individuels de chaque fichier de preuve validé.
- **Clé secrète :** La signature utilise la `SECRET_KEY` de Django (ou une clé gérée par `pgcrypto`), rendant impossible la falsification d'un faux sceau valide sans accès au serveur.
- **Vérification :** Le dashboard COBAC (Auditeur Externe) recalcule le hash en temps réel et affiche une pastille verte (`✓ Intégrité cryptographique confirmée`) ou rouge (`⚠️ Données corrompues`).

### 9.4 Sécurité des Fichiers (File Handling)

Les fichiers de preuve sont la cible privilégiée des attaques applicatives. Sentinel implémente des contrôles agressifs sur les uploads (NFR-SEC-04).

1. **Vérification du Type Réel (Magic Bytes)** :
   - L'extension `.pdf` n'est pas suffisante. Le backend lit les premiers octets du fichier en mémoire avec `python-magic`.
   - Si le type réel détecté (`ex: application/x-dosexec` pour un `.exe`) ne correspond pas à l'extension ou à la whitelist des types autorisés (`application/pdf`, `image/jpeg`...), le fichier est rejeté avant même d'écrire sur le disque.
2. **Filtrage Anti-Macro Office** :
   - Les fichiers Excel (`.xlsx`), Word (`.docx`) sont acceptés.
   - Les fichiers contenant des macros (`.xlsm`, `.docm`) sont **strictement interdits** et rejetés (vecteurs majeurs de ransomware in-the-wild).
3. **Renommage UUID et Structure du Stockage** :
   - Un fichier `bilan-2026.pdf` est renommé en `7a2b9f...3e.pdf` (UUIDv4) sur le disque (`fs`). Le vrai nom est gardé en BDD (`original_filename`).
   - Ceci bloque complètement les attaques par *Path Traversal* (ex: upload d'un fichier nommé `../../../etc/passwd`).
4. **Pas d'exécution statique (Serveur/Nginx)** :
   - Le répertoire de stockage `/media/proofs/` est inaccessible directement depuis le web. Il n'est pas servi par Nginx.
   - Le téléchargement passe obligatoirement par une vue Django `/download/<uuid>` qui valide la permission RBAC avant de transmettre le fichier.

### 9.5 Mapping OWASP Web Top 10 (2021)

Mise en correspondance des vulnérabilités critiques OWASP avec les mitigations architecturales de Sentinel.

| OWASP 2021 | Vulnérabilité | Mitigation dans Sentinel (By-Design) |
|---|---|---|
| **A01:2021** | Broken Access Control | Middleware RBAC + RLS PostgreSQL partiel. Vérifications contextuelles par QuerySet. Les UUIDv4 empêchent l'énumération prédictive (IDOR). |
| **A02:2021** | Cryptographic Failures | TLS 1.3 imposé par Nginx (HTTPS Only). Mots de passe hashés via Argon2/PBKDF2 natif à Django. Fichiers et base cryptés au repos (LUKS) en V2. |
| **A03:2021** | Injection | L'ORM Django protège nativement contre les injections SQL via paramétrisation. `django-fsm` bloque les injections d'états de flux. Pas de Shell access depuis l'app. |
| **A04:2021** | Insecure Design | Approche "Default Deny". Validation adaptative "Magic Bytes" pour les fichiers bloquant l'upload d'exécutables (NFR-SEC-04). |
| **A05:2021** | Security Misconfiguration | Serveur Nginx configuré avec HSTS, X-Content-Type-Options. Gunicorn derrière un proxy. Mode `DEBUG=False` impératif en production. |
| **A06:2021** | Vulnerable and Outdated Components| Dépendances fixées dans `requirements.txt`. Alertes de vulnérabilité Github/Gitlab intégrées dans la chaîne CI (si mise en place). |
| **A07:2021** | Identification and Authentication Failures | Bloqueur `django-axes` limitant les tentatives à 5 erreurs brutes. Politique de cookies stricts HTTPOnly et Session timeout (idle 30 mins, NFR-SEC-02). |
| **A08:2021** | Software and Data Integrity Failures | Signature cryptographique HMAC-SHA256 (NFR-SEC-03). Append-Only database constraints. Modèles Django sérialisés non altérés par le client. |
| **A09:2021** | Security Logging and Monitoring Failures | Infrastructure de journalisation "AuditLog" conservant l'entièreté des modifications pendant 1 année (NFR-SEC-05), intouchable de manière applicative. |
| **A10:2021** | Server-Side Request Forgery (SSRF) | Sentinel n'interroge pas et ne parse pas de ressources distantes (URLs, webhooks) via inputs utilisateurs. Les interactions externes sont fermées. |

---

*Fin de la section §9 — Sécurité. La section §10 (Infrastructure & Déploiement) suit.*

---

## §10. Infrastructure, Dimensionnement & Déploiement

Le déploiement de Sentinel est conçu pour s'intégrer nativement dans l'environnement On-Premise (local) de la BICEC, sans aucune exposition ni dépendance au Cloud externe. L'architecture physique suit un modèle de monolithe déployé sur une machine virtuelle Linux unique pour le MVP (ADR-02).

### 10.1 Cartographie du Déploiement Physique

Le système est hébergé sur une VM (Virtual Machine) s'exécutant sous un système d'exploitation d'entreprise (**Ubuntu LTS** pour la souplesse du PFE/pilote, ou **RHEL** - Red Hat Enterprise Linux pour la production finale).

```mermaid
C4Deployment
    title Diagramme de Déploiement Physique - Sentinel On-Premise

    Deployment_Node(bicec_dc, "Datacenter BICEC", "LAN Interne / VLAN Applicatif") {
        
        Deployment_Node(vm, "Machine Virtuelle", "Ubuntu 24.04 LTS / RHEL 9") {
            
            Deployment_Node(docker, "Docker Engine", "Environnement conteneurisé") {
                Container(nginx, "Nginx Container", "Port 443", "TLS Termination, Static Files, Rate Limiting")
                Container(gunicorn, "Django Container", "Port 8000 interne", "Workers WSGI synchrones (gthread)")
                Container(worker, "Worker Container", "Django-Q2 Daemon", "Exécution des tâches en arrière-plan")
                ContainerDb(postgres, "PostgreSQL Container", "Port 5432 interne", "Base de données relationnelle")
            }
        }
        
        Deployment_Node(storage_node, "Stockage Froid", "Baie SAN / NAS") {
            ContainerDb(nfs, "NFS Mount", "/mnt/sentinel_backups", "Sauvegardes nocturnes (Fichiers + Dump SQL)")
        }
    }

    Rel(nginx, gunicorn, "Proxy_pass (HTTP django:8000)")
    Rel(gunicorn, postgres, "Connexion TCP/IP locale")
    Rel(worker, postgres, "Polling 10s via ORM")
```

### 10.2 Capacity Planning (Budget RAM & Disque)

Le calibrage (Sizing) suivant est calculé pour supporter la contrainte NFR-SCA-02 (volume cible : ~1000 recommandations, ~8000 fichiers de preuves, ~200 utilisateurs concurrents).

| Ressource | Capacité Recommandée (Production) | Détail de Consommation (Budget) |
|---|---|---|
| **CPU (vCores)**| **4 vCores** | Nginx (0.5), Gunicorn `gthread` avec 4 workers (2.0), PostgreSQL (1.0), OS + background (0.5). |
| **Mémoire (RAM)** | **8 Go** | OS (1 Go), Docker Engine (0.5 Go), PostgreSQL `shared_buffers` au quart (2 Go), Gunicorn 4 workers (2 Go), Django-Q2 (0.5 Go), Nginx + cache (1.5 Go). |
| **Stockage (App)**| **40 Go SSD** | OS Ubuntu/RHEL (~10 Go), Python + lib (~1 Go), Base PostgreSQL volumétrie métier textuelle (~5 Go), Logs système + audit (~4 Go), Marge d'exploitation (20 Go). |
| **Files (Preuves)**| **200 Go HDD/SSD** | Uploads limités à 15 Mo (NFR-SCA-01). 8000 fichiers × ~10 Mo en moyenne = ~80 Go. Provisionnement sur 3 ans (200 Go). Ce disque peut être monté en iSCSI ou NFS. |
| **Réseau** | **Gigabit LAN**| Flux internes massifs (ZIP synchrones). Interfaces réseaux à haut débit nécessaires pour les connexions simultanées vers le NAS. |

> **Stratégie de Backup (NFR-REL-02: RPO 24h)**  
> Un script OS `cron` ou un outil de backup d'entreprise (Veeam) réalise toutes les nuits à 02h00 :
> 1. Un `pg_dump` de la base PostgreSQL.
> 2. Une copie incrémentielle (`rsync`) du répertoire `/media/proofs/`.
> 3. L'export vers le serveur externe NAS de la BICEC.

### 10.3 Configuration Nginx (Reverse Proxy & Serveur Web)

Conformément à l'ADR-02, **Nginx** est chargé d'intercepter le trafic HTTPS, de servir les assets statiques et de protéger le serveur WSGI. Voici l'extrait fondamental de la configuration `nginx.conf` pour Sentinel :

```nginx
# Bloc 1 : Redirection HTTP -> HTTPS (NFR-SEC-01)
server {
    listen 80;
    server_name sentinel.intra.bicec.local;
    return 301 https://$host$request_uri;
}

# Bloc 2 : Serveur HTTPS principal
server {
    listen 443 ssl http2;
    server_name sentinel.intra.bicec.local;

    # 1. Configuration TLS (Certificats d'entreprise internes montés via Docker volumes)
    ssl_certificate /etc/nginx/ssl/sentinel.crt;
    ssl_certificate_key /etc/nginx/ssl/sentinel.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 2. Sécurité : En-têtes obligatoires
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Limite drastique pour les uploads (15MB imposés par NFR-SCA-01)
    client_max_body_size 16M;

    # 3. Fichiers statiques (JS, CSS Tailwind, Fonts)
    location /static/ {
        alias /usr/share/nginx/html/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 4. Applications (Proxy vers le conteneur Django/Gunicorn via docker network)
    location / {
        proxy_pass http://web:8000;
        
        # Transmission de l'IP originale pour l'AuditLog Django
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

*Note* : Le trafic vers le répertoire protégé `/media/` (les preuves uploadées) passe volontairement à travers Django (`proxy_pass`) afin que la vue puisse vérifier que l'utilisateur a les droits d'accès au fichier (contrôle RBAC). Nginx ne gère **jamais** les fichiers Media en direct.

### 10.4 Configuration Docker Compose

Afin d'assurer la reproductibilité isolée dictée par l'ADR-09, `docker-compose.yml` définit la topologie On-Premise :

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - sentinel_pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=sentinel_db
      - POSTGRES_USER=sentinel_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sentinel_user -d sentinel_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build: .
    restart: unless-stopped
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 10
    volumes:
      - sentinel_media:/app/media/
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy

  worker:
    build: .
    restart: unless-stopped
    command: python manage.py qcluster
    volumes:
      - sentinel_media:/app/media/
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy

  nginx:
    image: nginx:1.26-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - sentinel_static:/usr/share/nginx/html/static:ro
      - sentinel_certs:/etc/nginx/ssl:ro
    depends_on:
      - web

volumes:
  sentinel_pgdata:
  sentinel_media:
  sentinel_static:
  sentinel_certs:
```

---

## §11. Stratégie de Chiffrement & Protection des Secrets

La confidentialité des données bancaires manipulées par Sentinel exige une gestion rigoureuse des clés et du chiffrement, scindée en trois périmètres : le réseau (en transit), le stockage physique (au repos) et la configuration logicielle.

### 11.1 Chiffrement en Transit (NFR-SEC-01)

- **Protocole :** HTTPS imposé à tous. Redirection HSTS stricte.
- **Terminaison TLS :** Gérée de manière centralisée par Nginx.
- **Contrainte Interne :** Bien que Sentinel soit installé sur le LAN interne de la BICEC, le trafic applicatif voyageant entre le navigateur de l'utilisateur (ex: laptop sur VPN) et le serveur doit rester intraçable pour se prémunir du *sniffing* interne.
- **Bypass TLS :** Zéro composant cloud public externe autorisé. L'interface avec Exchange (SMTP) utilise du STARTTLS ou TLS explicite.

### 11.2 Chiffrement au Repos (Rest)

Sentinel applique des stratégies défensives pour pallier une éventuelle fuite d'information suite à un vol physique de disque dur ou un accès `root` non autorisé.

| Composant | Stratégie MVP | Recommandation V2 (Grade Bancaire) |
|---|---|---|
| **Mots de passe** | Hachage non réversible via Django (`PBKDF2-SHA256` / `Argon2`). Aucun mot de passe en clair. | Authentification LDAP (AD) déléguée. Les mots de passe locaux ne sont plus utilisés. |
| **Volumes Disques (OS + DB)** | Sécurisation par droits Unix classiques (`chmod 700` sur la Data directory Postgres). | Chiffrement intégral de la partition via **LUKS** au niveau de l'hyperviseur VMware/Hyper-V de la BICEC. |
| **Sceau d'intégrité (HMAC)**| Empreintes cryptographiques `HMAC-SHA256` générées in-app et stockées dans `audit_hmac_seal`. Preuve formelle d'intégrité (ADR-07). | Idem produit MVP. |
| **Fichiers Uploadés (Preuves)**| Stockés sur un FS formaté en EXT4 ou XFS. Nom réel obfusqué (`UUIDv4.pdf`), empêchant un *grep* naïf sur les noms de fichiers métiers. | Modules de chiffrement natif pour fichiers sensibles (chiffrement symétrique, e.g. KMS local ou `Fernet`). |

### 11.3 Gestion des Secrets d'Environnement

L'accès à la base de données, les identifiants SMTP, et la clé mère fonctionnant pour le calcul du MAC (Message Authentication Code) ne doivent **jamais** figurer en dur dans le code source de Sentinel.

L'adoption stricte du principe The Twelve-Factor App dicte la séparation de la configuration du code principal.

| Variable d'Environnement | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Clé maîtresse cryptographique (longue de 50+ caractères). Ne fuiter sous aucun prétexte. Active le `HMAC`. |
| `DATABASE_URL` | Chaine de connexion asymétrique sécurisée (ex: `postgres://user:password@localhost:5432/sentinel`). |
| `EMAIL_HOST_PASSWORD` | Mot de passe AD du compte de service SMTP `sentinel-no-reply@bicec.com`. |

Ces secrets seront fournis dynamiquement aux conteneurs via Docker Compose à l'aide d'un fichier `.env` protégé par des permissions strictes (0600) sur la VM hôte de production :

```bash
# Exemple: /opt/sentinel/.env (Droits: root uniquement - 0600)
DJANGO_SECRET_KEY="bx3@_p+..._g=!(l_"
DEBUG="False"
DB_PASSWORD="pass"
```

---

*Fin de la section §11 — Chiffrement. La section §12 (Matrice des Risques) suit.*

---

## §12. Matrice des Risques (RAID)

Ce projet de digitalisation croise des enjeux réglementaires stricts (COBAC) et des contraintes d'infrastructure On-Premise. La matrice ci-dessous expose les risques critiques identifiés et la manière dont l'architecture agit comme mesure de remédiation préventive.

| ID | Catégorie | Risque Identifié | Probabilité | Impact | Mitigation Architecturale (by-design) |
|---|---|---|---|---|---|
| **R01** | **Adoption** | Les utilisateurs (DM/ETP) refusent d'utiliser l'outil et continuent d'envoyer des preuves par email. | Élevée | Élevé | **SSR + HTMX** : Navigation ultra-rapide (UI < 200ms). Les relances asynchrones (Django-Q2) forcent l'adoption en impliquant la DG si le statut `OVERDUE` s'active. |
| **R02** | **Technique** | Saturation du disque dur (`fs`) local de la VM due à l'upload incontrôlé de fichiers volumineux. | Moyenne | Bloquant | Quotas stricts de 15 Mo/fichier dans les vues Django. Télémétrie et alertes automatiques si seuil > 80% (RSSI). Export asynchrone / Montage NAS en backup (NFR-SCA-01). |
| **R03** | **Securité** | Falsification / Altération d'une recommandation archivée par un compte Audit corrompu. | Faible | Très élevé | Architecture Append-Only : suppression impossible. **Sceau HMAC-SHA256** lié au record. L'AuditLog rendra impossible le camouflage de l'effraction. |
| **R04** | **Securité** | Infection Ransomware via l'upload d'un faux fichier Word/Excel piégé par un macro virus. | Moyenne | Critique | **Validation adaptative (Magic bytes)** + Rejet catégorique (hard-ban) des formats avec macros (`.xlsm`, `.docm`). Les UUIDv4 limitent l'exécution shell. |
| **R05** | **Architecture** | Le Single Point of Failure (SPOF) Monolithe VM plante soudainement (Kernel panic). | Faible | Bloquant | Architecture auto-contenue, temps de restauration système (RTO < 4h, NFR-REL-03) via Snapshot VM / Backup Pg_dump quotidien. |
| **R06** | **Réglementaire** | Retard opérationnel sur un correctif critique COBAC sans remontée d'alerte en temps réel. | Moyenne | Élevé | Le planificateur Django-Q2 identifie automatiquement toute reco non clôturée à péremption, bascule `is_overdue=True` et génère un rapport email prioritaire. |
| **R07** | **Performance** | Temps de réponse excessif (> 5s) lors de l'export ZIP massif demandé par un auditeur externe. | Moyenne | Moyen | Génération ZIP streamée in-memory avec `io.BytesIO`. Limites imposée par le filtrage réseau local plutôt que le CPU. |

---

## §13. Stratégie de Tests & Assurance Qualité

Pour qu'un logiciel destiné à la conformité réglementaire (RegTech) entre en production, un corpus de tests rigoureux doit certifier le respect strict des Exigences Non-Fonctionnelles (NFR). 

### 13.1 Pytest : Pyramide de Tests Backend

L'environnement de tests utilise `pytest` + `pytest-django`, en ciblant les points stratégiques (Coverage visé : ~85% global, 100% sur FSM et RBAC).

1. **Tests Modèles & FSM (Le moteur logique)**
   - Démonstration mathématique que le modèle de Workflow (les 5 états) est infaillible.
   - Validation que `django-fsm` lève bien une exception `TransitionNotAllowed` lors de tentatives d'actions hors-circuit (Ex: Tentative de l'Audit de clôturer une recommandation encore à l'état `ASSIGNED` ou sans preuve).
   - Test d'intégrité de bout en bout des transactions atomiques et de `select_for_update`.

2. **Tests Middlewares & RBAC (La forteresse)**
   - Simulation exhaustive (Matrice M*N). Chaque rôle (DM, Audit, Externe, ETP) tente d'accéder (GET/POST) à des vues non autorisées ou à des instances n'appartenant pas à sa Direction `department_id`.
   - Contrôle strict que le retour renvoyé est HTTP 403 Forbidden ou HTTP 404 (grâce au filtrage du QuerySet Manager `for_tenant()`).

3. **Tests de Génération Cryptographique (L'Intégrité)**
   - Test unitaire : Le Sceau HMAC-SHA256 produit est validé par un ré-enchiffrage indépendant. Muter `title` ou un fichier de preuve dans le JSON rompt invariablement la validation (NFR-SEC-03).

4. **Tests Upload et Parsing Preuves**
   - Piéger la vue avec de faux fichiers (ex: uploader un binaire déguisé en `.pdf`).
   - Vérifier l'exception de sécurité levée par `validate_file()` via `python-magic`.

### 13.2 Automation Frontend & HTMX

Contrairement aux frameworks lourds SPA (React), l'utilisation de SSR (Django Templates) + HTMX simplifie considérablement les tests d'interface utilisateur.

- Les vues applicatives Django traitent des requêtes HTMX (qui transportent le header `HTTP_HX_REQUEST`). Les clients de tests intègrent MockHTMX pour s'assurer que si un `post` HTMX est émis (ex: soumission de commentaire), seul le bon fragment de template est renvoyé en retour (HTTP 200 partiel) plutôt qu'un Layout HTML entier.
- Les tests Cypress/Playwright End-to-End (E2E) sont limités strictement aux flux nominaux complets (Se connecter → Uploader la preuve → Valider au DM).

### 13.3 User Acceptance Testing (UAT - Pilote)

Une fois un MVP technique disponible, la validation ne dépend plus de l'équipe de développement. L'UAT prend la forme d'un **Pilote contrôlé en conditions réelles** à la BICEC :

- **Périmètre Pilote :** Restreint à 1 Direction pilote (ex: Direction des Risques), limitée à ses équipes, + 1 instance restreinte de l'Audit Interne.
- **Scénario :** Import de l'historique partiel (20 recommandations réelles échues). 
- **KPIs d'Acceptation UAT :**
  1. Le temps d'exécution UI d'une soumission complète de preuve PDF de 5 Mo (objectif total < 1 sec in situ).
  2. Le cycle de notification Q2 Scheduler délivre effectivement les e-mails à 08h00 J+1 dans les boites Exchange.
  3. L'export Audit permet le téléchargement du .ZIP et la vérification des clés du hash HMAC sans anomalie.

---

*Fin de la section §13 — Tests. La section §14 (Bilan Validation NFRs) suit.*

---

## §14. Bilan de Validation NFR (Non-Functional Requirements)

Une architecture d'entreprise ne se juge pas uniquement sur les fonctionnalités, mais sur sa capacité à tenir sous charge et résister dans un environnement hostile. Ce tableau valide comment les 13 NFRs critiques dictées par le PRD sont structurellement honorées par Sentinel.

### 14.1 NFR — Sécurité & Conformité

| ID | Exigence (NFR) | Composant de Validation (by-design) | Statut |
|---|---|---|:---:|
| **SEC-01** | TLS 1.2+ obligatoire de bout en bout. | Configuration `nginx.conf` forçant protocole v1.2 / v1.3. Redirection HTTP vers HTTPS automatique. (ADR-02) | ✅ |
| **SEC-02** | Timeout session après 30 minutes inactives. | Stateful Cookies : `SESSION_COOKIE_AGE = 1800` et `SESSION_SAVE_EVERY_REQUEST = True`. (ADR-06) | ✅ |
| **SEC-03** | Sceau d'intégrité infalsifiable à la clôture. | Trigger de hachage `HMAC-SHA256` in-app utilisant `SECRET_KEY` + hash unique des fichiers `proofs`. | ✅ |
| **SEC-04** | Bloquer les virus/exécutables dissimulés. | Check in-memory via librairie `python-magic` sur les headers MIME. Rejet dur des macros Office (`.xlsm`, `.docm`). | ✅ |
| **SEC-05** | Audit Trail append-only (12 mois). | Modèle `AuditLog` interceptant chaque action (via `create`, `update`, transitions FSM). Politique de purge scriptée `> 1 an` via Django-Q2. | ✅ |

### 14.2 NFR — Performance

| ID | Exigence (NFR) | Composant de Validation (by-design) | Statut |
|---|---|---|:---:|
| **PERF-01** | Temps de calcul du périmètre d'accès < 10ms. | Chargé via variable sessile + Selector `for_tenant()`. Les jointures complexes (`select_related`) éliminent le problème N+1. | ✅ |
| **PERF-02** | TTFB Dashboard (Temps UI client) < 200ms P95. | Rendu 100% Server-Side (Vanilla HTML) servi par Gunicorn via socket. Zéro parsing JSON lourd au niveau client (ADR-04). | ✅ |
| **PERF-03** | Génération du Sceau HMAC < 500ms. | Calcul algorithmique immédiat exécuté par Python `hashlib` in-process juste avant le Commit SQL terminal. | ✅ |
| **PERF-04** | Export Archive ZIP de preuves < 5s par Reco. | Streaming In-memory (`io.BytesIO`). Fichiers lus séquentiellement depuis disque et encapsulés à la volée vers `FileResponse` Django. | ✅ |

### 14.3 NFR — Scalabilité & Opérations

| ID | Exigence (NFR) | Composant de Validation (by-design) | Statut |
|---|---|---|:---:|
| **SCA-01**| Max 5 fichiers par preuve (limite de 15 Mo unitaire). | Limites intégrées en durs dans les `Forms Django` (Validation Size) et `client_max_body_size` dans Nginx. | ✅ |
| **SCA-02**| Tenue de DB de 1000 Recos, 8000 fichiers. | Table SQL partitionnées et indexées nativement. Volumétrie considérée comme *"Minuscule"* pour PostgreSQL 16. | ✅ |
| **SCA-03**| Support 200 utilisateurs concurrents. | Le stack `Nginx + Gunicorn 4 Workers (gthread 10)` gère sans surcharge les locks concurrentiels (estimé 1200 req/sec possibles). | ✅ |

### 14.4 NFR — Résilience Globale

| ID | Exigence (NFR) | Composant de Validation (by-design) | Statut |
|---|---|---|:---:|
| **REL-01** | *Fail-safe* accès (Si échec périmètre, zéro données).| RLS PostgreSQL natif + Override des Manager de classes `QuerySet`. Oublier un `.filter()` ne lève pas les clauses d'isolation. (ADR-01) | ✅ |
| **REL-02** | RPO < 24H (Recovery Point Objective - Max perte). | Plan BASH Cron localisant le script de `pg_dump` et le push FTP/NFS quotidien à H04:00 (Hors batch Django). | ✅ |
| **REL-03** | RTO < 4H (Recovery Time Objective). | Définition infrastructurelle d'une Image/Snapshot standardisée via VMWare vSphere local. | ✅ |

---

## §15. Inventaire des Licences Open-Source

Dans le contexte d'un logiciel bancaire On-Premise (code propriétaire BICEC fermé, non distribué), l'audit des licences open-source (FOSS) garantit l'absence de **licences virales (type GPL)** qui obligeraient la banque à rendre public le code source de Sentinel.

Le stack sélectionné est exclusivement certifié par des licences dites "permissives".

| Composant | Rôle Technique | Type de Licence FOSS | Statut d'Utilisation Bancaire |
|---|---|---|:---:|
| **Python 3.12+** | Runtime d'exécution (Langage de l'App). | `PSF License` (GPL-Compatible Permissive) | Totalement Libre |
| **Django (+ extensions)** | Framework backend, Authentification, ORM. | `BSD-3-Clause` | Totalement Libre |
| **PostgreSQL 16** | Moteur de base de données. | `PostgreSQL License` (Similaire MIT) | Totalement Libre |
| **Nginx (Stable)** | Reverse proxy, Terminaison TLS, Serveur statique. | `BSD 2-Clause` | Totalement Libre |
| **Docker Engine** | Plateforme de lancement des conteneurs. | `Apache License 2.0` | Totalement Libre |
| **Redis (Optionnel)** | Broker optionnel (Non-MVP). | `Dual RSALv2 / SSPLv1` | Toléré usage local interne |
| **Tailwind CSS 3+** | Framework CSS utility-first. | `MIT License` | Totalement Libre |
| **HTMX** | Rendu interactif navigateur (pas de SPA). | `Zero-Clause BSD (0BSD)` | Totalement Libre |
| **Alpine.js** | Micro-interactions (Modales, Tabulations). | `MIT License` | Totalement Libre |
| **Django-Q2** | Scheduler Asynchrone Python local (Batchs nuits). | `MIT License` | Totalement Libre |
| **Django-FSM** | State Machine logiques (transitions). | `MIT License` | Totalement Libre |

> **Conclusion Risque Légal :** Le risque de litige de propriété intellectuelle ou de contamination virale ("Copyleft") exigeant de libérer le code propriétaire développé pour Sentinel est évalué à **Zéro**. Aucune librairie GPL/AGPL n'est installée côté Backend ni impliquée par `pip`.

---

*Fin de la section §15 — Licences. La section §16 (FAQ) suit.*

---

## §16. Foire Aux Questions (FAQ) d'Architecture

Ce document d'architecture a pour but d'aligner l'ensemble des parties prenantes. Voici les réponses pragmatiques aux interrogations techniques les plus fréquentes soulevées par les différents acteurs du projet Sentinel.

### 16.1 Pour la Direction IT (Infrastructure & Opérations)

**Q : Pourquoi déployer avec Docker Compose au lieu d'un cluster Kubernetes ?**  
**R :** Conformément à l'ADR-09 et à la contrainte de déploiement, Kubernetes pour une application interne de ~200 utilisateurs génèrerait une complexité opérationnelle démesurée pour l'équipe IT. Docker Compose offre la reproductibilité, l'isolation (conteneurs) et le contrôle local attendus tout en évitant le surcoût de gestion d'un Control Plane complexe.

**Q : Pourquoi préférer Nginx à Caddy ou Apache ?**  
**R :** Nginx est le standard de l'industrie, déjà ancré dans les processus matériels et humains de la BICEC. Assurer la terminaison TLS et le routing via Nginx permet à l'équipe Infra d'opérer avec des outils maîtrisés sans surcharge d'apprentissage (ADR-02).

### 16.2 Pour les Développeurs (La Core Team)

**Q : Où se trouve l'API JSON (Django REST Framework) ?**  
**R :** Il n'y en a pas (ADR-04). Sentinel est une application SSR (Server-Side Rendered) pur-sang. Au lieu de sérialiser les données en JSON et d'exécuter la logique métier en JavaScript côté navigateur (SPA frontend lourd), nous utilisons **HTMX**. HTML est transféré directement sur le réseau, réduisant de 70% le volume de code boilerplate et minimisant la surface d'attaque applicative.

**Q : Pourquoi contourner Celery pour les tâches d'arrière-plan ?**  
**R :** Celery est puissant, mais requiert une stack lourde ajoutant un point de défaillance supplémentaire : un *Message Broker* (Redis ou RabbitMQ). **Django-Q2** (ADR-05) utilise l'ORM PostgreSQL existant pour orchestrer sa queue de messages asynchrone, ce qui consolide nos back-ups (la DB et la Queue sont sauvegardées ensemble).

**Q : Comment maintenir les modèles de la DB sans que ça devienne un chaos (Fat Models) ?**  
**R :** En appliquant strictement l'architecture de composants Django détaillée en §8. Les *Models* ne font que détenir les champs et le FSM. Toute requête de lecture passe par un *Selector* (`RecommendationSelector.for_tenant()`) et toute mutation passe par un *Service* (`WorkflowService.delegate_etp()`). Les Vues ne sont que des passe-plats.

### 16.3 Pour l'Inspecteur COBAC et la Direction Générale

**Q : Que signifie concrètement l'intégrité "HMAC-SHA256" apposée sur nos preuves ?**  
**R :** Cela équivaut à sceller un document avec un sceau de cire contenant un code-barres unique. Si, après la clôture d'une recommandation, une personne modifie la base de données (ex: changer *"Traité"* en *"En cours"*) ou remplace le fichier de preuve PDF sur le disque, l'équation mathématique du sceau est brisée. L'application alertera instantanément qu'une fraude interne a eu lieu.

**Q : L'Audit Interne a-t-il vraiment tout pouvoir sur le système ?**  
**R :** Non. Bien que l'Audit orchestre les flux macro, le **RBAC strict** (§9.2) empêche même le chef de l'Audit de modifier le contenu d'une preuve fournie par un Directeur Métier (principe de non-répudiation des preuves déposées).

### 16.4 Pour le RSSI (Sécurité de l'Information)

**Q : Le système est-il vulnérable à un Database Administrator (DBA) malveillant ?**  
**R :** Bien qu'un DBA connecté avec `psql` bypass les logiciels applicatifs Django, la défense en profondeur limite l'impact. Toute commande `UPDATE/DELETE` passée par le DBA est interceptée par nos Triggers natifs PostgreSQL (bas niveau) et consignée dans `audit_auditlog` avec son adresse IP. S'il tente d'effacer les traces, le sceau HMAC de la fiche en question sera de toute manière invalidé (ADR-07).

**Q : Comment Sentinel se protège-t-il contre un ransomware uploadé par un utilisateur piégé ?**  
**R :** D'abord via `python-magic` qui lit l'entête binaire et rejette tout `.exe`, `.sh` ou `.bat` maquillé en `.pdf`. Ensuite, via le blocage en dur des fichiers Office avec macros (`.xlsm`, `.docm`). Enfin, Nginx empêche l'exécution de tout fichier stocké dans `/media/`, neutralisant un éventuel webshell PHP.

---

## §17. Annexes & Lexique

Ce document de référence rassemble les lois fondatrices de la version 2. Pour toute information fonctionnelle complémentaire, l'équipe est invitée à se référer aux artefacts suivants :

| Document | Rôle & Description | Version |
|---|---|---|
| **PRD v2** | *Product Requirements Document.* Source de vérité ultime répertoriant les 31 FR (Functional Requirements) et détaillant le cycle de vie du Workflow. | `prd-v2.md` |
| **Product Brief v2** | Lettre de cadrage stratégique (Vision, Acteurs, Problème ciblé). Détermine le 'Pourquoi' de Sentinel. | `product-brief-v2.md` |
| **System Diagrams** | Bibliothèque complète (format brut) contenant la genèse des diagrammes Mermaid (MCD, UML, etc.) pour modification ultérieure. | `system-diagrams.md` |

### Lexique

- **FSM** : *Finite-State Machine* (Machine à états finis).
- **HTMX** : Bibliothèque JavaScript permettant d'accéder à AJAX et aux Websockets via de simples attributs HTML.
- **SSR** : *Server-Side Rendering* (Rendu côté serveur). L'HTML est généré sur le serveur Python avant envoi.
- **RBAC** : *Role-Based Access Control* (Contrôle d'accès basé sur les rôles).
- **HMAC** : *Hash-based Message Authentication Code* (Code d'authentification de message par hachage).
- **Docker Compose** : Outil d'orchestration locale permettant de définir et gérer une application multi-conteneurs via un fichier YAML.

---
*Ce document architecture-v2.md (Rév 2.0) est désormais complet et acté comme source canonique de l'ingénierie Sentinel de niveau institutionnel.*
