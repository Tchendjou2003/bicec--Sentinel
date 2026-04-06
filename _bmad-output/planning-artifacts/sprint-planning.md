# Sprint Planning — Sentinel MVP v1.0

> **Durée de sprint :** 2 semaines · **Équipe :** 1 Backend Dev + 1 Frontend Dev + 1 IT Admin (Sprint 0 uniquement)
> **Deadline MVP :** 6 mois (12 sprints disponibles)
> **Référence :** [`epics-and-stories.md`](./epics-and-stories.md) · [`prd-v2.md`](./prd-v2.md) · [`architecture-v2.md`](./architecture-v2.md)

---

## Philosophie de Priorisation

1. **Fondations d'abord :** L'infra et le RBAC bloquent tout le reste.
2. **Happy Path complet avant les edge cases :** Livrer le flux nominal (Audit crée → ETP soumet → DM valide → Audit clôture) dès le Sprint 5.
3. **Feedback business tôt :** Le pilote BICEC peut commencer dès Sprint 6 sur un périmètre limité.
4. **Edge cases et reporting ensuite :** Notifications, dashboards avancés, COBAC, Import en dernière phase.

---

## Vue d'Ensemble des Sprints

```mermaid
gantt
    title Plan de Release Sentinel MVP (6 mois)
    dateFormat  YYYY-MM-DD
    axisFormat  S%W

    section Fondations
    S0 · Infra & DevOps            :s0, 2026-04-06, 14d
    S1 · Auth, RBAC, Admin Django  :s1, after s0, 14d

    section Cœur Métier
    S2 · Modèles FSM & CRUD Recos  :s2, after s1, 14d
    S3 · Preuves & Sécurité Fichiers :s3, after s2, 14d
    S4 · Workflow Validation DM    :s4, after s3, 14d
    S5 · Clôture HMAC & DG Porteur :s5, after s4, 14d

    section Pilote (UAT)
    S6 · Notifications & Scheduler :s6, after s5, 14d
    S7 · Dashboards & Filtres HTMX :s7, after s6, 14d

    section Secondaire
    S8 · Reports & Import Historique :s8, after s7, 14d
    S9 · Audit Externe COBAC       :s9, after s8, 14d

    section Finalisation
    S10 · Rapport PDF & Polish UI  :s10, after s9, 14d
    S11 · QA, Tests, Go-Live       :s11, after s10, 14d
```

---

## Détail des Sprints

### 🏗️ Sprint 0 — Infrastructure & DevOps
**Objectif :** L'environnement de développement est prêt. Un `docker compose up` lance les 4 services.
**NFR validées :** NFR-SEC-01 (TLS), NFR-REL-02 (Backup).

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S0.1 · Dockerfile multi-stage | 3 | IT Admin |
| 🔴 BLOQUANT | S0.2 · Docker Compose (4 services, healthchecks) | 3 | IT Admin |
| 🔴 BLOQUANT | S0.3 · Nginx (TLS, HTTP→HTTPS, headers sécu) | 3 | IT Admin |
| 🟠 HAUTE | S0.5 · Fichier `.env.example` et secrets | 1 | IT Admin |
| 🟢 NORMALE | S0.4 · Script de backup nocturne | 2 | IT Admin |

**Total : 12 points**

**Critère de complétion du Sprint :**
- [ ] `docker compose up -d` → 4 conteneurs sains (healthcheck OK)
- [ ] HTTPS accessible sur `https://localhost` avec certificat auto-signé
- [ ] Django admin accessible sur `/admin/`

---

### 🔑 Sprint 1 — Authentification, Modèles Core & Admin Django
**Objectif :** Les fondations des données sont en place. L'IT Admin peut créer l'organigramme et les utilisateurs.
**FR validées :** FR1, FR3, FR4. **NFR validées :** NFR-SEC-02 (Session), NFR-PERF-01 (RBAC), NFR-REL-01 (RLS).

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S1.1 · Modèle `User` custom (UUID + rôle) | 3 | Backend |
| 🔴 BLOQUANT | S1.2 · Modèle `Department` (hiérarchie) | 2 | Backend |
| 🔴 BLOQUANT | S1.3 · Modèle `Delegation` (intérims FR4) | 3 | Backend |
| 🔴 BLOQUANT | S1.4 · Login/Logout + anti-brute-force | 3 | Backend |
| 🔴 BLOQUANT | S1.5 · Middleware RBAC (périmètre tenant) | 5 | Backend |
| 🔴 BLOQUANT | S1.6 · RLS PostgreSQL (garde-fou fail-safe) | 3 | Backend |
| 🔴 BLOQUANT | S1.7 · Modèle `AuditLog` (append-only + trigger) | 3 | Backend |
| 🟠 HAUTE | S1.8 · Templates de base (layout + navigation) | 3 | Frontend |
| 🟠 HAUTE | S1.9 · Admin Django — `Department` | 2 | Backend |
| 🟠 HAUTE | S1.10 · Admin Django — `User` (+ révocation session) | 2 | Backend |
| 🟠 HAUTE | S1.11 · Admin Django — `Delegation` | 2 | Backend |
| 🟢 NORMALE | S1.12 · Admin Django — `AuditLog` (read-only) | 1 | Backend |
| 🟢 NORMALE | S1.13 · Admin Django — `SiteConfiguration` | 1 | Backend |

**Total : 33 points** *(Sprint chargé – priorité absolue)*

**Critère de complétion du Sprint :**
- [ ] Un DM peut se connecter, voir son périmètre, sa session expire à 30min
- [ ] L'IT Admin peut créer l'organigramme BICEC dans l'Admin Django
- [ ] Un test pytest d'isolation RLS passe au vert

---

### ⚙️ Sprint 2 — Recommandations (Modèles, FSM, CRUD)
**Objectif :** L'Audit peut créer des recommandations, les assigner, et le FSM bloque toute transition illégale.
**FR validées :** FR5, FR6, FR7, FR10, FR11, FR12.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S2.1 · Modèle `Recommendation` + `django-fsm` | 5 | Backend |
| 🔴 BLOQUANT | S2.2 · Transitions assignation (Audit) | 3 | Backend |
| 🔴 BLOQUANT | S2.3 · Transitions DM : `delegate_to_etp` + `accept_by_dm` | 3 | Backend |
| 🔴 BLOQUANT | S2.7 · Modèle `Comment` + Selectors `for_tenant()` | 3 | Backend |
| 🟠 HAUTE | S2.5 · Création unitaire (formulaire HTMX) | 3 | Frontend + Backend |
| 🟠 HAUTE | S2.4 · Soft Delete (statut ASSIGNED uniquement) | 2 | Backend |
| 🟢 NORMALE | S2.6 · Bulk Create (formulaire multi-lignes) | 4 | Frontend + Backend |

**Total : 23 points**

**Critère de complétion du Sprint :**
- [ ] L'Audit crée une reco et l'assigne à un DM
- [ ] Le DM délègue à un ETP → statut `IN_PROGRESS`
- [ ] Une transition illégale lève `TransitionNotAllowed` (test pytest)

---

### 📎 Sprint 3 — Preuves & Sécurité Fichiers
**Objectif :** L'ETP peut uploader des preuves en DRAFT, la validation Magic Bytes bloque les fichiers dangereux.
**FR validées :** FR15, FR16, FR18, FR25. **NFR validées :** NFR-SEC-04, NFR-SCA-01.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S3.1 · Modèle `Proof` (statuts, versioning, types) | 3 | Backend |
| 🔴 BLOQUANT | S3.2 · `upload_proof()` + validation Magic Bytes | 5 | Backend |
| 🔴 BLOQUANT | S3.6 · Renommage UUID + stockage sécurisé | 2 | Backend |
| 🔴 BLOQUANT | S3.7 · Téléchargement sécurisé (contrôle RBAC) | 2 | Backend |
| 🟠 HAUTE | S3.3 · `submit_proofs()` → DRAFT→PENDING | 3 | Backend |
| 🟠 HAUTE | S3.4 · Soft Delete brouillon par auteur | 2 | Backend |
| 🟠 HAUTE | S3.8 · Historique des versions de preuves | 2 | Frontend |
| 🟢 NORMALE | S3.5 · Upload PV de Recette (par le DM) | 2 | Backend |

**Total : 21 points**

**Critère de complétion du Sprint :**
- [ ] Un `.exe` renommé `.pdf` est rejeté par `python-magic`
- [ ] Un ETP uploade 3 DRAFT et les soumet → statut `PENDING_DM_REVIEW`
- [ ] Un ETP d'une autre direction ne peut pas voir les preuves (test RBAC)

---

### ✅ Sprint 4 — Validation DM & Clôture Audit (HMAC)
**Objectif :** Le Happy Path complet est opérationnel. L'Audit peut clôturer avec un sceau HMAC.
**FR validées :** FR17, FR19, FR20, FR24, FR27. **NFR validées :** NFR-SEC-03, NFR-PERF-03.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S4.1 · `submit_to_dm()` ETP → PENDING_DM_REVIEW | 2 | Backend |
| 🔴 BLOQUANT | S4.2 · `approve_by_dm()` → PENDING_AUDIT_REVIEW | 3 | Backend |
| 🔴 BLOQUANT | S4.3 · `reject_by_dm()` (motif obligatoire) | 2 | Backend |
| 🔴 BLOQUANT | S4.5 · `close_by_audit()` + HMAC-SHA256 | 5 | Backend |
| 🔴 BLOQUANT | S4.7 · Middleware immutabilité CLOSED_RESOLVED | 2 | Backend |
| 🟠 HAUTE | S4.4 · `submit_to_audit()` DM Porteur + DG Porteur | 3 | Backend |
| 🟠 HAUTE | S4.6 · `reject_by_audit()` (notif DM + ETP + DG) | 2 | Backend |
| 🟢 NORMALE | S4.8 · Vue Timeline (Audit Trail) | 3 | Frontend |

**Total : 22 points**

**Critère de complétion du Sprint :**
- [ ] Happy Path complet testé de bout en bout (pytest + Playwright)
- [ ] HMAC généré en ≤ 500ms
- [ ] Mutation post-CLOSED retourne `403 Forbidden`

---

### 🔔 Sprint 5 — Notifications & Scheduler Django-Q2
**Objectif :** Le moteur de relance automatique est opérationnel. Les OVERDUE sont détectées chaque nuit.
**FR validées :** FR21, FR22, FR23.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S7.1 · Modèles `Notification` + `Digest` | 3 | Backend |
| 🔴 BLOQUANT | S7.2 · `cron_check_overdue()` (flag OVERDUE) | 3 | Backend |
| 🔴 BLOQUANT | S7.3 · `cron_send_consolidated_notifications()` | 4 | Backend |
| 🟠 HAUTE | S7.4 · `cron_proactive_alerts()` (J-7) | 2 | Backend |
| 🟠 HAUTE | S7.5 · Template email HTML (Outlook compatible) | 3 | Frontend |
| 🟠 HAUTE | S7.7 · Notifications in-app (badge HTMX) | 3 | Frontend |
| 🟢 NORMALE | S7.6 · Heartbeat Scheduler + alerte RSSI | 2 | Backend |

**Total : 20 points**

**Critère de complétion du Sprint :**
- [ ] Un email est reçu dans Exchange à 08h00 pour une reco OVERDUE
- [ ] Un seul email consolidé par utilisateur (pas de doublons)
- [ ] Le badge in-app s'affiche et se marque lu via HTMX

---

### 📊 Sprint 6 — Dashboards, Filtres HTMX & Rapport PDF (UC15)
**Objectif :** Chaque rôle a son tableau de bord. Les dashboards Audit et DG peuvent être imprimés.
**FR validées :** FR28, FR29, FR30, FR31. **NFR validées :** NFR-PERF-02.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S6.1 · Dashboard Audit Interne | 4 | Frontend + Backend |
| 🔴 BLOQUANT | S6.2 · Dashboard Directeur Métier | 3 | Frontend + Backend |
| 🔴 BLOQUANT | S6.3 · To-Do List ETP | 2 | Frontend + Backend |
| 🟠 HAUTE | S6.4 · Dashboard Direction Générale | 4 | Frontend + Backend |
| 🟠 HAUTE | S6.5 · Filtres dynamiques HTMX | 4 | Frontend |
| 🟠 HAUTE | S6.8 · Indicateurs visuels priorité/statut | 2 | Frontend |
| 🟢 NORMALE | S6.6 · Rapport de synthèse Audit (UC15) | 3 | Frontend + Backend |
| 🟢 NORMALE | S6.7 · Rapport DG (vue exécutive) | 2 | Frontend + Backend |

**Total : 24 points**

> **🚩 Point de pilotage BICEC possible :** Après Sprint 6, le Happy Path complet + dashboards sont disponibles pour un UAT restreint (1 Direction pilote, 20 recommandations test).

**Critère de complétion du Sprint :**
- [ ] TTFB dashboard < 200ms avec 1000 recos en base (test de charge)
- [ ] Filtres HTMX fonctionnels sans rechargement page
- [ ] Rapport UC15 imprimable

---

### 📅 Sprint 7 — Demandes de Report d'Échéance
**Objectif :** Les DM peuvent demander formellement un report. L'Audit décide. La date originale est préservée.
**FR validées :** FR13, FR14.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S5.1 · Modèle `ExtensionRequest` | 2 | Backend |
| 🔴 BLOQUANT | S5.2 · Formulaire de demande de report (DM) | 3 | Frontend + Backend |
| 🔴 BLOQUANT | S5.3 · Vue approbation/rejet Audit | 3 | Frontend + Backend |
| 🟠 HAUTE | S5.4 · Conservation `original_due_date` | 1 | Backend |

**Total : 9 points** *(Sprint volontairement light — budget pour la dette technique et les bugs du pilote)*

**Critère de complétion du Sprint :**
- [ ] Un report approuvé met à jour `due_date` mais préserve `original_due_date`
- [ ] Double affichage (date initiale + date révisée) sur la fiche

---

### 📥 Sprint 8 — Import Historique Atomique
**Objectif :** L'Audit peut importer les 450+ recommandations avec prévisualisation des erreurs.
**FR validées :** FR8, FR9.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S9.1 · Template Excel normalisé (téléchargeable) | 2 | Backend |
| 🔴 BLOQUANT | S9.2 · `preview_import()` (validation + aperçu erreurs) | 5 | Backend + Frontend |
| 🔴 BLOQUANT | S9.3 · `execute_import()` (transaction atomique) | 5 | Backend |
| 🟠 HAUTE | S9.4 · Tag `IMPORTED` + AuditLog groupé | 2 | Backend |

**Total : 14 points**

**Critère de complétion du Sprint :**
- [ ] Un import de 500 lignes réussit atomiquement
- [ ] Une erreur à la ligne 200 déclenche un ROLLBACK complet
- [ ] L'import est exécuté en async (dashboard non bloqué)

---

### 🌍 Sprint 9 — Audit Externe & Conformité COBAC
**Objectif :** Les inspecteurs COBAC/BEAC ont un accès cloisonné. L'export ZIP et la vérification HMAC fonctionnent.
**FR validées :** FR2, FR26. **NFR validées :** NFR-PERF-04.

| Priorité | Story | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | S8.1 · Modèle `ExternalMission` (périmètre) | 3 | Backend |
| 🔴 BLOQUANT | S8.2 · Vue liste Read-Only (périmètre mission) | 3 | Frontend + Backend |
| 🔴 BLOQUANT | S8.5 · Création compte Externe par l'Audit | 2 | Backend |
| 🟠 HAUTE | S8.3 · Export ZIP streamé (preuves + fiche synthèse) | 5 | Backend |
| 🟠 HAUTE | S8.4 · Vérification HMAC en temps réel (pastille) | 3 | Frontend + Backend |

**Total : 16 points**

**Critère de complétion du Sprint :**
- [ ] Un Externe ne voit que son périmètre de mission
- [ ] ZIP téléchargé en < 5s pour un dossier de 10 preuves
- [ ] Pastille verte confirmée sur une reco intègre

---

### 🎨 Sprint 10 — Polish UI, Accessibilité & Tests E2E
**Objectif :** L'application est prête pour la démonstration Go-Live. L'UX est soignée, les tests E2E passent.

| Priorité | Tâche | Points | Assigné |
|:---:|---|:---:|---|
| 🔴 BLOQUANT | Tests Playwright E2E : Happy Path complet | 5 | QA |
| 🔴 BLOQUANT | Tests Playwright E2E : Rejet DM + OVERDUE | 3 | QA |
| 🟠 HAUTE | Polish UI : cohérence visuelle tous rôles | 4 | Frontend |
| 🟠 HAUTE | Page 403/404/500 soignées | 1 | Frontend |
| 🟠 HAUTE | Review WCAG accessibilité (contraste, labels) | 2 | Frontend |
| 🟢 NORMALE | Documentation opérationnelle (README + runbook) | 3 | Backend |

**Total : 18 points**

---

### 🚀 Sprint 11 — QA Finale & Go-Live
**Objectif :** UAT complet avec l'équipe BICEC. Correction des bugs remontés. Go-Live officiel.

| Priorité | Tâche | Assigné |
|:---:|---|---|
| 🔴 BLOQUANT | UAT pilote (1 Direction, 20 recommandations réelles) | Tous |
| 🔴 BLOQUANT | Correction bugs UAT priorité CRITIQUE | Backend + Frontend |
| 🔴 BLOQUANT | Import de l'historique réel BICEC (450+ recos) | Backend + IT Admin |
| 🔴 BLOQUANT | Configuration organigramme BICEC réel | IT Admin |
| 🟠 HAUTE | Formation utilisateurs (DM, ETP, Audit) | PM |
| 🟢 NORMALE | Livraison documentation utilisateur | PM |

---

## Récapitulatif Exécutif

| Sprint | Durée | Epics | Stories | Points | Livrable Clé |
|---|---|---|---|---|---|
| **S0** | 2 sem. | E0 | 5 | 12 | Docker + Nginx opérationnel |
| **S1** | 2 sem. | E1 | 13 | 33 | Auth + RBAC + Admin Django |
| **S2** | 2 sem. | E2 | 7 | 23 | FSM + CRUD Recommandations |
| **S3** | 2 sem. | E3 | 8 | 21 | Upload sécurisé + Magic Bytes |
| **S4** | 2 sem. | E4 | 8 | 22 | Happy Path complet + HMAC |
| **S5** | 2 sem. | E7 | 7 | 20 | Scheduler + Notifications |
| **S6** | 2 sem. | E6 | 8 | 24 | Dashboards + Rapport PDF · **🚩 Pilote BICEC possible** |
| **S7** | 2 sem. | E5 | 4 | 9 | Demandes de report |
| **S8** | 2 sem. | E9 | 4 | 14 | Import historique atomique |
| **S9** | 2 sem. | E8 | 5 | 16 | Accès COBAC + ZIP HMAC |
| **S10** | 2 sem. | — | — | 18 | Polish UI + Tests E2E |
| **S11** | 2 sem. | — | — | — | UAT + Go-Live |
| **Total** | **24 sem.** | **E0→E9** | **66** | **~212 pts** | **MVP Sentinel en production** |

> [!IMPORTANT]
> **Le point de pilotage naturel est après Sprint 6 (semaine 14).**
> À ce stade : Happy Path complet, 4 dashboards, rapport PDF et notifications sont opérationnels.
> L'équipe BICEC peut démarrer un pilote restreint (Direction des Risques) sur des données réelles,
> ce qui génère du feedback concret pour les sprints 7 à 9.
