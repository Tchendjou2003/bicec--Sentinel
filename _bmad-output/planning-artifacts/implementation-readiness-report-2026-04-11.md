# Rapport d'Analyse Croisée — PRD v2 ↔ Architecture v2

**Date :** 2026-04-11  
**Projet :** bicec--Sentinel  
**Délai projet :** ~2 mois 3 semaines  

---

## Méthodologie

Lecture intégrale, ligne par ligne, des deux documents de référence :
- `prd-v2.md` (328 lignes, 31 FR + 17 NFR)
- `architecture-v2.md` (2657 lignes, §0–§17)

Chaque incohérence est classée par **sévérité** :
- 🔴 **CRITIQUE** — Bloquant pour l'implémentation, doit être corrigé avant de coder
- 🟠 **MAJEUR** — Ambiguïté qui va générer des questions/erreurs pendant le dev
- 🟡 **MINEUR** — Écart cosmétique, mais à aligner pour la cohérence documentaire

---

## 🔴 Incohérences CRITIQUES

### INC-01 : Nombre de NFRs — 13 vs 17

| Document | Valeur |
|---|---|
| **PRD v2** §NFR | 17 NFRs distinctes (SEC-01 à SEC-05, PERF-01 à PERF-04, SCA-01 à SCA-03 + SCA-02b, REL-01 à REL-04) |
| **Architecture v2** §1.3 (L42) | Annonce "**13 NFR**" |
| **Architecture v2** §14 Bilan | Valide 13 NFRs dans le bilan (manque `NFR-SCA-02b`, `NFR-REL-04`, `NFR-SEC-05` dans certaines tables) |

**Impact :** NFR-SCA-02b (TTFB décorrélé de l'import) est absente du bilan d'architecture. Si non adressée architecturalement, l'import historique risque de geler l'application pour les utilisateurs connectés.

**Action :** Mettre à jour l'architecture §1.3 à "17 NFR" et ajouter SCA-02b dans le bilan §14.

---

### INC-02 : Stratégie RLS — Contradiction frontale PRD ↔ Architecture

| Document | Position |
|---|---|
| **PRD v2** §Technical Constraints (L198) | "Implémentation du Row-Level Security **directement dans PostgreSQL** en plus du RBAC applicatif" |
| **PRD v2** §Success Criteria (L64) | "Le RLS **garantit** zéro accès croisé entre directions" |
| **PRD v2** §Risk Mitigation (L251) | "RLS **Partiel** (garde-fou)" |
| **Architecture v2** ADR-01 (L270) | "Implémenter **uniquement le RBAC applicatif** pour le MVP" — RLS repoussé en V2 |

**Impact :** C'est la contradiction la plus grave de tout le dossier. Le PRD exige le RLS comme garantie de sécurité, l'architecture l'abandonne au MVP. L'implémentation ne saura pas quel camp suivre.

**Action :** **Trancher formellement.** Deux options :
1. Aligner le PRD sur l'architecture (RBAC seul MVP, RLS V2) et modifier les §Success Criteria et §Technical Constraints
2. Imposer le RLS MVP et réviser l'ADR-01

> ⚠️ *Recommandation :* Vu le délai de 2 mois 3 semaines, l'option RBAC-seul (architecture) est réaliste. L'option RLS intégral ajouterait ~2 semaines de complexité.

---

### INC-03 : Clé HMAC — SECRET_KEY vs HMAC_SECRET_KEY distincte

| Document | Position |
|---|---|
| **Architecture v2** ADR-07 §Considérations (L487) | Exige une "variable `HMAC_SECRET_KEY` **totalement distincte** de `SECRET_KEY`" |
| **Architecture v2** §9.3B (L2196) | "La signature utilise la `SECRET_KEY` de Django" |
| **Architecture v2** §11.3 Variables (L2443) | Liste `DJANGO_SECRET_KEY` mais **aucune** `HMAC_SECRET_KEY` |

**Impact :** Le développeur ne saura pas quelle clé utiliser. Si `SECRET_KEY` est utilisée et un jour rotée, tous les sceaux historiques deviennent invalides — exactement le scénario que l'ADR-07 voulait prévenir.

**Action :** Harmoniser sur `HMAC_SECRET_KEY` distincte. Mettre à jour §9.3B et §11.3.

---

### INC-04 : Utilisateurs concurrents — 200 vs 500

| Document | Valeur |
|---|---|
| **PRD v2** NFR-SCA-03 (L321) | "jusqu'à **500** utilisateurs concurrents actifs" |
| **Architecture v2** §1.3 (L196) | "~**200** users concurrents" |
| **Architecture v2** §10.2 (L2275) | Capacity Planning calibré pour "~200 utilisateurs concurrents" |
| **Architecture v2** ADR-02 (L310) | Gunicorn "4 workers × 10 threads = **40** connexions concurrentes" |

**Impact :** L'architecture est dimensionnée pour 200 alors que le PRD exige 500. Le dimensionnement Gunicorn (40 connexions) est même insuffisant pour 200.

**Action :** Aligner les chiffres. 200 est réaliste pour le MVP bancaire (85 users d'après le user journey §4). Modifier le PRD `NFR-SCA-03` à 200 ou augmenter le sizing architecture.

---

### INC-05 : Volume données — 1000 vs 5000 recommandations

| Document | Valeur |
|---|---|
| **PRD v2** NFR-SCA-02 (L319) | "**5 000** recommandations et **20 000** fichiers" |
| **Architecture v2** §10.2 (L2275) | "~**1000** recommandations, ~8000 fichiers" |
| **Architecture v2** ADR-05 (L420) | "suffisant pour le MVP (**~1000 recos**)" |

**Impact :** Le Capacity Planning est sous-dimensionné par rapport au PRD. L'import de 5000 recos sur un sizing prévu pour 1000 pourrait poser des problèmes de performance.

**Action :** Aligner sur le même chiffre. Recommandation : 5000 est le chiffre PRD, harmoniser l'architecture.

---

## 🟠 Incohérences MAJEURES

### INC-06 : Rôle DG — Fonctionnalités orphelines dans l'Architecture

Le diagramme de cas d'utilisation §4.4 (L768–L789) attribue au DG :
- **UC8** : "Soumettre directement preuves à l'Audit"
- **UC9** : "Demander report échéance"
- **UC11** : "Consulter To-Do List (recos assignées)"

**Problème :** Le PRD v2 ne mentionne **aucune** de ces capacités pour la DG. Le PRD décrit la DG comme un rôle purement consultatif (Dashboard macro, filtres, impression). Ni FR13 (report), ni FR15/FR16 (soumission preuves) ne listent la DG comme acteur.

De plus, la matrice RBAC §9.2 ne donne au DG que **R** (Read) sur les recommandations. Aucun droit C/U/X.

**Action :** Supprimer UC8, UC9 et UC11 du diagramme DG dans l'architecture, OU ajouter des FRs au PRD si c'est un besoin réel. Recommandation : supprimer, car le DG n'est pas un acteur opérationnel.

---

### INC-07 : Soft Delete Recommandation — Condition divergente

| Document | Condition |
|---|---|
| **PRD v2** FR6 (L265) | Soft Delete autorisé "tant qu'elle **n'a pas été assignée activement** à un DM" |
| **Architecture v2** FSM §5.4 (L889) | "Soft Delete possible ici **uniquement** [en état ASSIGNED]" |
| **Architecture v2** RBAC §9.2 note¹ (L2177) | "¹ Uniquement si la recommandation est à l'état **`ASSIGNED`**" |

**Problème :** "Pas encore assignée à un DM" (PRD) ≠ "en état ASSIGNED" (Archi). L'état ASSIGNED signifie justement que la reco EST assignée. Le PRD semble vouloir dire "DRAFT/pré-assignation", mais cet état n'existe pas dans le FSM.

**Action :** Clarifier. Si le Soft Delete n'est possible qu'avant l'assignation DM, il faudrait un état DRAFT. Sinon, aligner le PRD sur "tant que la reco est encore en ASSIGNED" (avant que le DM ait délégué ou accepté).

---

### INC-08 : Rapport PDF DG — Contradiction PRD vs Architecture

| Document | Position |
|---|---|
| **PRD v2** FR31 (L300) | "**Aucune génération PDF côté serveur** n'est développée" — uniquement CSS @media print |
| **Architecture v2** §4.1 UC15 (L680) | Auditeur UC15 : "Génerer rapport de synthèse statistique **en PDF**" |
| **PRD v2** User Journey DG (L170) | "export **PDF**" |

**Impact :** L'architecture promet un export PDF pour l'Auditeur, le PRD l'interdit explicitement. Les User Journeys du PRD lui-même mentionnent "export PDF" pour la DG, en contradiction avec son propre FR31.

**Action :** Trancher : CSS @media print uniquement (FR31) ou ajouter la génération PDF serveur (ex: WeasyPrint). Recommandation : garder CSS @media print pour le MVP (deadline serrée).

---

### INC-09 : Modèle `Proof` — Champ `updated_at` manquant

L'ERD §7.2 (table `workflow_proof`, L1599-1612) ne contient **pas** de champ `updated_at`, contrairement à toutes les autres tables métier (`workflow_recommendation`, `users_user`, `users_department`).

**Impact :** Impossible de tracer le moment exact d'un changement de statut d'une preuve (DRAFT→PENDING→ACCEPTED). L'Audit Trail compense partiellement, mais c'est une incohérence de modèle.

**Action :** Ajouter `updated_at` à `workflow_proof`.

---

### INC-10 : Docker Compose — `version: '3.8'` dépréciée

L'Architecture §10.4 (L2349) utilise `version: '3.8'` dans le docker-compose.yml, mais l'ADR-09 (L557) spécifie explicitement "Docker Compose **v2 natif sans directive de version dépréciée**".

**Action :** Supprimer la ligne `version: '3.8'` du docker-compose.yml.

---

### INC-11 : Collectstatic manquant dans Docker Compose

L'ADR-09 (L553) exige : "Exécution systématique de `python manage.py collectstatic --noinput` au démarrage du service `web`". Mais le docker-compose §10.4 (L2370) lance directement Gunicorn sans collectstatic :
```
command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 10
```

**Action :** Ajouter un entrypoint script exécutant collectstatic + la commande Gunicorn, ou utiliser `&&`.

---

### INC-12 : Volume `sentinel_static` non alimenté

Le service `web` (L2371-2377) ne monte **pas** le volume `sentinel_static`. Or le service `nginx` (L2399) le monte en lecture seule (`sentinel_static:/usr/share/nginx/html/static:ro`). Les fichiers statiques ne seront jamais copiés vers Nginx.

**Action :** Ajouter `sentinel_static:/app/staticfiles/` au service `web`.

---

## 🟡 Incohérences MINEURES

### INC-13 : Bloc `/media/` Nginx absent

L'ADR-02 (L314) exige : "la configuration `nginx.conf` inclut **obligatoirement** un bloc `location /media/ { deny all; return 403; }`". Mais la config Nginx §10.3 (L2295-2340) ne contient **pas** ce bloc.

**Action :** Ajouter le bloc à la configuration Nginx.

---

### INC-14 : `proxy_read_timeout 30s` absent

L'ADR-02 (L316) recommande des "Timings étendus (`proxy_read_timeout 30s`)". Absent de la config Nginx réelle §10.3.

**Action :** Ajouter dans le bloc `location /`.

---

### INC-15 : `mem_limit: 512m` absent

L'ADR-02 (L318) recommande une "Limite mémoire côté conteneur (`mem_limit: 512m`)". Absent du docker-compose §10.4.

**Action :** Ajouter `mem_limit` ou `deploy.resources.limits.memory` aux services.

---

### INC-16 : CONN_MAX_AGE absent

L'ADR-02 (L317) exige `CONN_MAX_AGE = 60` côté Django. Non documenté dans le docker-compose ni dans un settings.py de référence.

**Action :** Documenter cette variable dans les settings de production.

---

### INC-17 : Frise OVERDUE masquée pour Externes — Non documenté dans RBAC

Le PRD (L140) et l'architecture §4.5 (L807) indiquent que le flag OVERDUE est masqué pour les Auditeurs Externes. Mais la matrice RBAC §9.2 ne liste **pas** cette restriction. Le champ `is_overdue` n'apparaît pas dans les restrictions contextuelles.

**Action :** Ajouter la note dans la matrice RBAC.

---

## Résumé Quantitatif

| Sévérité | Nombre | Exemples clés |
|---|---|---|
| 🔴 **CRITIQUE** | 5 | RLS contradiction, HMAC key, NFR count, capacity mismatch ×2 |
| 🟠 **MAJEUR** | 7 | DG role inflation, Soft Delete, PDF, Docker issues |
| 🟡 **MINEUR** | 5 | Nginx config, CONN_MAX_AGE, OVERDUE dans RBAC |
| **TOTAL** | **17** | |

---

## Recommandations Prioritaires (Top 5)

1. **INC-02 (RLS)** — Trancher immédiatement : RBAC seul pour le MVP, adapter le PRD
2. **INC-03 (HMAC Key)** — Harmoniser sur `HMAC_SECRET_KEY` distincte partout
3. **INC-04/05 (Capacity)** — Aligner les chiffres 200 users / 5000 recos
4. **INC-06 (DG)** — Retirer les fonctionnalités DG fantômes de l'architecture
5. **INC-08 (PDF)** — Confirmer CSS @media print uniquement pour le MVP
