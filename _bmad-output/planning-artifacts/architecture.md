---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - planning-artifacts/prd.md
  - planning-artifacts/product-brief-bicec--Sentinel-2026-03-06.md
workflowType: 'architecture'
project_name: 'bicec--Sentinel'
user_name: 'Dave Lahe'
date: '2026-03-16'
lastStep: 8
status: 'complete'
completedAt: '2026-03-17'
---

# Architecture Decision Document — Sentinel (BICEC)

_Ce document se construit collaborativement, étape par étape. Chaque section est ajoutée au fur et à mesure de nos décisions architecturales._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
Le système repose sur une Machine à États Finis (FSM - via `django-fsm`) stricte pour orchestrer un workflow de validation à double niveau. Il requiert un profilage complexe (6 rôles, délégations d'intérim), une gestion de fichiers volumineux pour les preuves, et la génération d'archives dynamiques (ZIP/PDF). Le besoin d'une traçabilité absolue impose un mécanisme d'Audit Trail cryptographique (SHA-256) fonctionnant en "append-only".

**Non-Functional Requirements:**
- Sécurité des données maximale (AES-256 au repos, intégration AD SSO).
- Performance et asynchronisme : Chargement UI < 2s, traitement des exports < 30s.
- Haute disponibilité (99.5%) pour un maximum de 200 utilisateurs simultanés.

**Scale & Complexity:**
Le projet s'inscrit dans un cadre RegTech critique ("Compliance-First") sous forte contrainte réglementaire (CEMAC/COBAC), exigeant une robustesse transactionnelle à toute épreuve.

- Primary domain: Full-Stack Enterprise Web App (Single-Tenant On-Premise)
- Complexity level: HIGH
- Estimated architectural components: 4 principaux (Frontend SPA, Backend API REST, Worker Asynchrone, SGBDR avec RLS)

### Technical Constraints & Dependencies

- Hébergement On-Premise obligatoire sur l'infrastructure BICEC.
- Authentification couplée à l'Active Directory existant (LDAP/SAML).
- SGBDR PostgreSQL ciblé pour sa gestion native de la Row-Level Security (RLS).
- Absence d'intégration API externe (Core Banking, RH) pour le MVP, limitant la complexité d'interfaçage.

### Cross-Cutting Concerns Identified

- **Sécurité et Habilitations :** Application de la *Séparation des Tâches (SoD)* et de la *Row-Level Security (RLS)*.
- **Ordonnancement Asynchrone :** Tâches planifiées (alertes J-7, basculement OVERDUE, rapports).
- **Audit et Immuabilité :** Traçabilité cryptographique de chaque mutation d'état protégée par des Triggers BDD (Append-Only).
- **Manipulation de Fichiers :** Upload sécurisé, stockage pérenne orienté Object Storage (S3/MinIO WORM) et compression ZIP/PDF des preuves.
- **Résilience Système :** Calcul dynamique de secours pour l'état OVERDUE et compte d'urgence "Break-Glass" hors AD.

## Starter Template Evaluation

### Primary Technology Domain

Full-Stack Enterprise Web App (Architecture découplée : React SPA + Django REST API) basé sur l'analyse des exigences du projet.

### Starter Options Considered

1.  **Pre-packaged Full-Stack Boilerplates (ex: divers `django-react-boilerplate` sur GitHub)**
    -   *Avantages :* Rapide à lancer, inclut souvent Docker et l'authentification de base pré-câblée.
    -   *Inconvénients :* Fortement opiniâtre. Ces starters imposent souvent l'authentification par Token JWT (peu adaptée à notre besoin de SSO Active Directory fluide) et incluent des modèles User génériques qui compliqueraient l'intégration propre de notre Row-Level Security (RLS) PostgreSQL.

2.  **Enterprise Custom Foundation (Vite React TS + Pure Django-Admin)**
    -   *Avantages :* Contrôle absolu sur la chaîne de sécurité. Permet d'intégrer `django-fsm` proprement dès le jour 1, de configurer le SSO Active Directory sans conflits de librairies tierces, et de mettre en place une architecture frontend Vite/TypeScript moderne et performante.
    -   *Inconvénients :* Nécessite de configurer manuellement le pont CORS et l'infrastructure asynchrone (Celery/Redis) lors du sprint d'initialisation.

### Selected Starter: Enterprise Custom Foundation (Vite React TypeScript + Django Pure)

**Rationale for Selection:**
Pour une application RegTech où la sécurité (RLS) et l'Audit Trail immuable sont vitaux, utiliser un boilerplate monolithique générique introduit des risques de sécurité et de la dette technique en forçant l'équipe de développement à détricoter des choix par défaut incompatibles. Une fondation sur-mesure utilisant les générateurs officiels modernes (`vite` et `django-admin`) garantit une base saine, 100% maîtrisée, prête pour nos exigences strictes (SSO, WORM, FSM).

**Initialization Command:**

```bash
# Frontend Initialization
npm create vite@latest sentinel-frontend -- --template react-ts

# Backend Initialization
python -m venv venv
source venv/bin/activate
pip install django djangorestframework django-fsm-2 psycopg2-binary celery redis
django-admin startproject sentinel_backend .
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Frontend : TypeScript strict (garantit la robustesse du typage pour les données bancaires) sur Node.js.
- Backend : Python 3.12+ avec Django 5.x.

**Styling Solution:**
- Tailwind CSS (Standard de facto pour Vite) couplé à des composants type Shadcn UI pour une interface financière sobre, lisible et ultra-performante sans surcharge CSS.

**Build Tooling:**
- Frontend : Vite (builds Rollup ultra-rapides, Hot Module Replacement instantané).
- Backend : Gunicorn/Uvicorn pour la production sécurisée.

**Testing Framework:**
- Frontend : Vitest (plus rapide que Jest avec Vite) + React Testing Library.
- Backend : Pytest-django.

**Code Organization:**
- Frontend ségrégé par "Features" (Architecture *Feature-Sliced Design* ou ségrégation par domaine métiers ex: `features/audit`, `features/workflow`) plutôt que technique.
- Backend organisé en petites Applications Django modulaires (`apps.core`, `apps.recommandations`, `apps.audit_trail`).

**Development Experience:**
- Hot Reloading natif ultra-rapide côté React et API.
- Typage fort bout-en-bout : génération de types TypeScript à partir de l'API Django (via OpenAPI/Swagger).

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Authentication Mechanism (Session Auth)
- Identity Provider Integration (LDAP)
- State Machine Engine (`django-fsm`)

**Important Decisions (Shape Architecture):**
- Frontend State Management (TanStack Query)
- Background Task Engine (Django-Q2)

### Data Architecture

- **SGBDR**: PostgreSQL (Provided by Starter/Context). *Rationale*: Native Row-Level Security (RLS) support is mandatory for strictly isolating audit recommendations by department/user.
- **File Storage**: Object Storage S3-Compatible (MinIO) On-Premise. *Rationale*: Allows WORM (Write Once Read Many) policy, preventing system administrators from deleting audit evidence.
- **State Machine**: `django-fsm` (ou fork moderne). *Rationale*: Sécurité maximale via le code, RLS native directe sur le modèle, intégrité transactionnelle avec l'Audit Trail.

### Authentication & Security

- **Authentication Method**: Session-based Auth with CSRF (Cookies `HttpOnly`). *Rationale*: Le standard le plus sécurisé contre le vol de session (XSS) pour une architecture On-Premise sur domaine interne commun. Évite la complexité fragile des JWT.
- **SSO Protocol**: LDAP Direct via `django-auth-ldap`. *Rationale*: Intégration simple, directe et robuste avec l'Active Directory interne de la BICEC.

### Frontend Architecture

- **State Management (Data Fetching)**: `@tanstack/react-query` (v5+). *Rationale*: Standard moderne, gère nativement le cache, le chargement et les erreurs des requêtes API REST.
- **State Management (UI Local)**: `zustand`. *Rationale*: Mini-store léger pour l'état de l'interface non lié à l'API (ex: menu ouvert/fermé).
- **Routing**: `react-router` (v7). *Rationale*: "Boring Technology", standard de l'industrie, stable et maîtrisé par 100% des développeurs React.

### Infrastructure & Deployment

- **Background Tasks Engine**: `django-q2` (v1.9+). *Rationale*: Utilise PostgreSQL comme broker (file d'attente). Beaucoup plus léger à maintenir en On-Premise que Celery (qui nécessite Redis ou RabbitMQ). La charge base de données supplémentaire est négligeable pour <200 utilisateurs.

### Decision Impact Analysis

**Implementation Sequence:**
1. Setup PostgreSQL Database & Django Backend with Session Auth + LDAP Configuration.
2. Initialize React Frontend + React Router + TanStack Query.
3. Configure Django-Q2 & Django-FSM.

**Cross-Component Dependencies:**
Le choix de Session Auth + CSRF implique que le Frontend React et le Backend Django doivent absolument être servis sous le même "Site" (ex: Frontend sur `sentinel.bicec.cm` et Backend sur `api.sentinel.bicec.cm` avec domaine de cookie `.sentinel.bicec.cm`, ou via un Reverse Proxy Nginx).

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
4 domaines où les agents IA pourraient faire des choix différents (nommage, structure et échange de données) sont désormais standardisés.

### Naming Patterns

**API & Data Variables:**
- **Full Snake Case**: Le backend Django dicte le format. Le Frontend React consommera et enverra des variables réseau en `snake_case` (ex: `user_id`, `date_creation`).

**Code Naming Conventions (Frontend):**
- **PascalCase** : Les fichiers contenant des composants React doivent impérativement utiliser le PascalCase (Ex: `UserCard.tsx`, `UploadProof.tsx`).
- Les variables et fonctions internes purement JavaScript/TypeScript (non liées au payload API) restent en `camelCase`.

### Structure Patterns

**Project Organization (Frontend):**
- **Feature-Sliced Design (Par Domaine) :** L'application React est structurée autour des fonctionnalités métiers (ex: `src/features/audit-trail/`, `src/features/recommandations/`). Chaque feature encapsule ses propres composants locaux, ses hooks purs et ses appels API (services).

### Format Patterns

**API Formats:**
- **Wrapped Responses (Enveloppées) :** L'API Django REST Framework (via des middlewares ou serializers custom) renvoie systématiquement une structure enveloppée :
  - Succès : `{"status": "success", "data": <payload>, "error": null}`
  - Erreur : `{"status": "error", "data": null, "message": "Description claire de l'erreur (ex: RLS bloquée)"}`

### Enforcement Guidelines & AI Safeguards

**All AI Agents MUST:**
- Utiliser rigoureusement le `snake_case` pour toutes les interfaces TypeScript mappant des données de l'API.
- Placer tout nouveau composant métier React dans le dossier de `feature` correspondante, et réserver un dossier global `src/components/ui/` uniquement pour les composants visuels purs et agnostiques (ex: Boutons génériques, Inputs).
- Déballer la propriété `data` ou vérifier `message` de l'enveloppe API lors de la création des requêtes avec TanStack Query.

**Blue Team Anti-Hallucination Directives (Critical constraints for Backend Agents):**
1. **Directive "Zero Trust API"** : Les agents ne doivent *jamais* faire un `.objects.get()` sans filtrer par le `request.user` ou sans passer par un queryset pré-filtré par la politique RLS.
2. **Directive "FSM Native"** : L'agent ne doit jamais changer le champ `status` manuellement (`reco.status = 'PENDING'`). Il doit OBLIGATOIREMENT appeler la méthode de transition générée par `django-fsm` (`reco.submit_to_audit()`) qui vérifiera les conditions préalables.
3. **Directive "Audit Hook"** : L'agent qui code le backend n'a pas le droit d'écrire une "Vue" (Endpoint) API responsable d'une mutation sans vérifier formellement que cette modification déclenche bien le signal ou le trigger d'insertion dans l'Audit Trail immuable.

### Advanced Resilience & Security Patterns

Issues issues de l'élicitation *Risk & Stress-Testing* :

**Policy "Context-Bound Filters" (RLS Hardening) :**
- L'API ne doit *JAMAIS* faire confiance aux IDs de département ou de rôle fournis dans la requête réseau par le frontend (vulnérabilité de falsification). Les QuerySets Django (`get_queryset()`) DOIVENT exclusivement extraire le contexte de filtrage depuis le `request.user` (validé via la Session sécurisée).

**Emergency Fallback (Active Directory Failure) :**
- L'authentification `django-auth-ldap` est le point d'entrée unique, MAIS le système implémente un compte "Break-Glass" (Administrateur/Auditeur Local crypté) natif à `django.contrib.auth`. Un Middleware détecte les pannes LDAP globales (`LDAPError`) et autorise la bascule vers cette authentification d'urgence locale pour maintenir l'opérationnel.

**Atomic FSM & Outbox Pattern (Database Crash) :**
- La cohérence entre (1) le statut de la recommandation, (2) le hash cryptographique, et (3) la ligne insérée dans l'Audit Trail est vitale. *Toute transition* `django-fsm` doit être enveloppée dans un bloc `transaction.atomic()`.
- En cas de crash serveur post-upload du fichier de preuve sur MinIO S3 mais pré-commit PostgreSQL, le fichier devient "Orphelin" sur S3. Un "Clean-Up Worker" (Django-Q2) balayera régulièrement le MinIO pour supprimer les preuves non référencées en base.

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
bicec--Sentinel/
├── README.md
├── docker-compose.yml       # Infrastructure de Dev locale (PostgreSQL, MinIO)
├── docs/                    # Documentation technique et PRD
├── e2e-tests/               # Tests de bout en bout globaux (Playwright/Cypress)
├── frontend/                # Vite React TS SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/             # Global Providers (React Query, Router v7)
│   │   ├── components/      # UI Partagée agnostique (Boutons, Modales)
│   │   │   ├── ui/
│   │   │   └── layout/      # Sidebar, Header
│   │   ├── shared/          # Contexte Global (Session) et hooks partagés inter-features
│   │   ├── features/        # Découpage par Domaine Métier
│   │   │   ├── auth/        # Hook de Session, Composant Login
│   │   │   ├── habilitations/ # Intérims, Matrices de rôles
│   │   │   ├── recommandations/ # Listes, Formulaires, Actions FSM
│   │   │   ├── audit-trail/ # Visualisation Historique immuable
│   │   │   └── dashboard/   # Statistiques et KPIs
│   │   ├── lib/             # API Client (Axios), Utilitaires API
│   │   ├── stores/          # Zustand global store (UI State = sidebar ouverte)
│   │   └── types/           # Interfaces TypeScript partagées globales
│   └── tests/
│       └── components/      # Tests Unitaires Vitest UI
└── backend/                 # Django REST API
    ├── manage.py
    ├── requirements.txt
    ├── config/              # Django settings (base, dev, prod), URLs globales
    └── apps/                # Applications Django modulaires
        ├── core/            # Permissions RLS globales, utilitaires de base
        │   └── tests/
        ├── users/           # Identity Management (LDAP)
        │   └── tests/
        ├── habilitations/   # RBAC, RLS Policies, Intérim/Délégations
        │   └── tests/
        ├── recommandations/ # Modèles FSM, Serializers, Vues, Workers (Django-Q2)
        │   └── tests/
        ├── audit_trail/     # Modèle Immuable, Calculs SHA-256, Triggers BDD
        │   └── tests/
        └── documents/       # Upload sécurisé S3/MinIO
            └── tests/
```

### Architectural Boundaries

**API Boundaries:**
- Le Frontend (React) dialoguera exclusivement avec le Backend (Django) via des endpoints RESTful sous le préfixe `/api/v1/`.
- L'Authentification (Active Directory) est le premier point d'entrée Backend. Aucune donnée structurelle de l'AD ne traverse vers React, seul le Cookie de Session `HttpOnly` est échangé.

**Component Boundaries (Frontend):**
- Les modules dans `src/features/*` sont strictement isolés. Pour éviter les dépendances circulaires entre domaines, l'état global et les types transitoires sont levés dans `src/shared/`. L'application connecte les features au niveau du Router principal.

**Data Access Boundaries (Backend):**
- **Silos de Responsabilité (Habilitations vs Users)** : L'application `users` gère l'identité brute (Qui es-tu, vérifié via Active Directory). L'application `habilitations` gère les droits applicatifs (Que peux-tu faire, Intérims).
- **Politique de RLS unifiée** : Les autres applications (`recommandations`, `documents`) n'ont pas l'autorité de contourner la politique d'habilitation sans l'aval du contexte de l'utilisateur courant validé par l'app `habilitations`.

### Requirements to Structure Mapping

- **Epic: Workflow & FSM (PRD FR1 à FR6)**
  - Frontend : `frontend/src/features/recommandations/` (Action Hooks, Formulaires Zod).
  - Backend : `backend/apps/recommandations/` (`django-fsm` transitions, endpoint mutations).
- **Epic: Security & RBAC (PRD FR17 à FR18, Intérim)**
  - Frontend : `frontend/src/features/habilitations/` (Modales ou vues d'attribution, UI Admin).
  - Backend : `backend/apps/habilitations/` (Modèles de Rôles, Logique de délégation calendaire, Matrices).
- **Epic: Preuves & Fichiers (PRD FR14 à FR16)**
  - Backend : `backend/apps/documents/` (Connexion MinIO WORM, API de streaming sécurisé).
- **Epic: Traçabilité Auditeur & SHA-256 (PRD FR19)**
  - Backend : `backend/apps/audit_trail/` (Modèles append-only, génération cryptographique sur `post_save`).

### Integration Points

**Internal Communication:**
- **Appels Asynchrones :** L'application Django communique avec la base de données PostgreSQL pour gérer le broker de sa file d'attente (via `django-q2`), par exemple pour relancer le statut OVERDUE à minuit sans Redis.

**External Integrations:**
- **LDAP Server :** Intégration par configuration `LDAPBackend` dans l'app `users`, interfaçage avec le réseau de la BICEC.
- **S3 Object Storage :** Connexion MinIO On-Premise pour le dépôt "WORM" intégré via `django-storages` dans l'app `documents`.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
Toutes les décisions technologiques s'alignent parfaitement. L'utilisation de `django-fsm` couplée à PostgreSQL et sa RLS est le standard or pour une RegTech. Le choix de *Session Auth* + *LDAP* élimine les failles de sécurité liées au stockage des tokens (XSS). L'utilisation de *Django-Q2* pour l'asynchrone au lieu de Celery/Redis réduit intelligemment la surface d'attaque et la complexité d'infrastructure "On-Premise".

**Pattern Consistency:**
Les règles d'agents (Full Snake Case pour l'API, Feature-Sliced Design pour React, Wrapped API Responses) sont strictes et laissent peu de place à l'interprétation. Les "Blue Team Directives" et "Resilience & Security Patterns" (Atomic FSM, Context-Bound RLS, AD Fallback) garantissent que Sentinel restera "Zero Trust" même en cas de crash infrastructurel.

**Structure Alignment:**
La structure du projet supporte l'architecture : un découpage clair entre applications Django (Core, Users, Habilitations, Recommandations, Audit Trail, Documents), un frontend isolé mais structuré par domaines métiers, avec l'état global remonté dans `shared/`.

### Requirements Coverage Validation ✅

**PRD / Feature Coverage:**
- Le workflow restrictiel (FSM) est couvert par `django-fsm`.
- L'intérim et les 6 rôles sont gérés par la nouvelle app modulaire `habilitations`.
- Le stockage WORM est couvert par l'intégration S3/MinIO locale (`django-storages`).
- L'Audit Trail immuable est sécurisé par des triggers bases de données et une fonction cryptographique (SHA-256).

### Implementation Readiness Validation ✅

**Decision Completeness:**
Les limites (Boundaries) sont claires : le frontend est agnostique de la logique métier (qui réside dans l'API), et l'API est construite en "append-only" pour la traçabilité.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Contexte RegTech / On-Premise pleinement assimilé
- [x] Contraintes techniques (AD, PostgreSQL) fixées

**✅ Architectural Decisions**
- [x] Décisions critiques (Session Auth, LDAP, FSM) validées
- [x] Starter (Vite React TS + Django Pure) documenté
- [x] Validation anti-crash (Atomic FSM, Outbox, Emergency Fallback) sécurisée

**✅ Implementation Patterns & Structure**
- [x] Règles de nommage (`snake_case` API, `PascalCase` Composants)
- [x] Directives Anti-Hallucination (Zero Trust API, FSM Native)
- [x] Arborescence complète validée en configuration "Party Mode"

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION
**Confidence Level:** HIGH

**Key Strengths:**
La séparation complète `users` (Identité LDAP) vs `habilitations` (Rôles Métiers) est le point fort de cette architecture. Les choix "Boring Technology" (Session Auth, React Router v7) garantissent que les LLMs généreront du code hautement fonctionnel du premier coup. L'architecture respecte les contraintes COBAC via RLS et Audit Trail, avec une empreinte opérationnelle On-Premise réduite.

### Implementation Handoff

**AI Agent Guidelines:**
- L'Initialisation avec `npm create vite@latest` et `django-admin startproject` doit être la toute première User Story d'implémentation.
- Respectez les règles de nommage (Snake back / Pascal front) à la lettre.
- Tout nouveau endpoint API modifiant l'état doit être obligatoirement revu sous le spectre "Audit Hook" et `transaction.atomic()`.

**First Implementation Priority:**
```bash
# Frontend Initialization
npm create vite@latest sentinel-frontend -- --template react-ts

# Backend Initialization
python -m venv venv
source venv/bin/activate
pip install django djangorestframework django-fsm-2 psycopg2-binary celery redis django-q2 django-auth-ldap
django-admin startproject sentinel_backend .
```
