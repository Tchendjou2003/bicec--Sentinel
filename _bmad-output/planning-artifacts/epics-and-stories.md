# Epics & User Stories — Sentinel MVP v1.0 *(Fast-Track 11 semaines)*

> **Source de vérité :** Ce document est dérivé du `prd-v2.md` (31 FR, 12 NFR) et de l'`architecture-v2.md`. Chaque Story est référencée à sa FR/NFR d'origine.
>
> **Format des critères d'acceptation :** `GIVEN` (contexte) / `WHEN` (action) / `THEN` (résultat attendu).
>
> **Statuts :** `[ ]` À faire · `[/]` En cours · `[x]` Terminé · `[v2]` Reporté en v2

> [!IMPORTANT]
> **Révision Fast-Track (2026-04-09)** — Délai réduit à **11 semaines (Go-Live : 26 juin 2026)**.
> Les éléments ci-dessous sont **reportés en v2** et marqués `[v2]` :
> - **S1.6** RLS PostgreSQL · **S2.6** Bulk Create · **S3.8** UI Historique versions preuves
> - **E5** Demandes de Report d'Échéance (S5.1–S5.4) · **E9** Import Self-Service
> - **S6.5** Filtres HTMX dynamiques (simplifié en filtres serveur) · **S6.7** Rapport DG séparé (fusionné dans S6.6)

---

## E0 — Infrastructure & DevOps

> **Objectif :** Mettre en place l'environnement conteneurisé reproductible (Docker, Nginx, TLS) sur lequel tous les autres Epics s'appuient.
>
> **Prérequis :** Aucun.
> **NFR couvertes :** NFR-SEC-01 (TLS), NFR-REL-02 (Backup), NFR-REL-03 (RTO).

---

### S0.1 — Dockerfile multi-stage (image de production Django)

**En tant que** développeur,
**Je veux** un `Dockerfile` optimisé en deux étapes (builder + runner),
**Afin de** produire une image Python légère sans les dépendances de build, prête pour la production.

**Critères d'acceptation :**

- `GIVEN` le code source du projet Django,
  `WHEN` je lance `docker build -t sentinel:latest .`,
  `THEN` l'image se construit sans erreur et pèse moins de 400 Mo.

- `GIVEN` l'image construite,
  `WHEN` je lance le conteneur,
  `THEN` Gunicorn démarre avec 4 workers et écoute sur `0.0.0.0:8000`.

- `GIVEN` l'image construite,
  `WHEN` j'inspecte l'image,
  `THEN` aucun fichier `.env`, secret ou clé privée n'est inclus dans les layers de l'image.

**Notes techniques :**
- Stage 1 (`builder`) : installation des dépendances pip + collectstatic.
- Stage 2 (`runner`) : image `python:3.12-slim`, copie uniquement le wheel et les statics.
- L'utilisateur système dans le conteneur est non-root (`appuser`).

---

### S0.2 — Docker Compose (orchestration des 4 services)

**En tant que** ingénieur infrastructure,
**Je veux** un fichier `docker-compose.yml` déclarant les 4 services (db, web, worker, nginx),
**Afin de** démarrer l'intégralité de l'application avec une seule commande.

**Critères d'acceptation :**

- `GIVEN` un fichier `.env` valide à la racine du projet,
  `WHEN` je lance `docker compose up -d`,
  `THEN` les 4 conteneurs démarrent sans erreur dans un délai de 60 secondes.

- `GIVEN` le service `db` en cours de démarrage,
  `WHEN` PostgreSQL n'est pas encore prêt,
  `THEN` les services `web` et `worker` attendent le healthcheck `pg_isready` avant de démarrer (`condition: service_healthy`).

- `GIVEN` un crash du worker Django-Q2,
  `WHEN` le conteneur s'arrête,
  `THEN` Docker le redémarre automatiquement (`restart: unless-stopped`).

- `GIVEN` un crash du service `db`,
  `WHEN` le conteneur redémarre,
  `THEN` les données PostgreSQL sont préservées dans le volume `sentinel_pgdata`.

**Notes techniques :**
- Healthcheck `db` : `pg_isready -U sentinel_user -d sentinel_db`, interval 10s, retries 5.
- 4 volumes nommés : `sentinel_pgdata`, `sentinel_media`, `sentinel_static`, `sentinel_certs`.
- Le réseau interne `sentinel_net` isole les conteneurs de l'hôte.

---

### S0.3 — Configuration Nginx (TLS, sécurité, proxy)

**En tant que** ingénieur infrastructure,
**Je veux** une configuration Nginx complète avec redirection HTTP→HTTPS et headers de sécurité,
**Afin de** respecter NFR-SEC-01 et protéger les utilisateurs contre les attaques réseau.

**Critères d'acceptation :**

- `GIVEN` un utilisateur qui tape `http://sentinel.intra.bicec.local`,
  `WHEN` Nginx reçoit la requête sur le port 80,
  `THEN` il répond `HTTP 301` vers `https://sentinel.intra.bicec.local` (redirection permanente).

- `GIVEN` une requête HTTPS valide,
  `WHEN` Nginx la proxifie vers Django,
  `THEN` les headers `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` sont transmis correctement.

- `GIVEN` un upload d'un fichier de 20 Mo,
  `WHEN` Nginx reçoit la requête,
  `THEN` il retourne `413 Request Entity Too Large` (limite `client_max_body_size 16M`).

- `GIVEN` une réponse Nginx vers le navigateur,
  `WHEN` j'inspecte les headers HTTP,
  `THEN` les headers `HSTS`, `X-Content-Type-Options: nosniff` et `X-Frame-Options: DENY` sont présents.

- `GIVEN` les protocoles TLS disponibles,
  `WHEN` je teste avec `openssl s_client`,
  `THEN` seuls TLSv1.2 et TLSv1.3 sont acceptés (SSLv3, TLSv1.0 et TLSv1.1 rejetés).

**Notes techniques :**
- Certificat TLS monté via volume `sentinel_certs:/etc/nginx/ssl:ro`.
- Le répertoire `/media/` n'est pas servi directement par Nginx (proxy vers Django obligatoire).
- Les fichiers statiques `/static/` sont servis par Nginx avec `expires 1y` et `Cache-Control: immutable`.

---

### S0.4 — Script de backup nocturne (NFR-REL-02 : RPO 24h)

**En tant que** administrateur système BICEC,
**Je veux** un script automatisé de sauvegarde nocturne,
**Afin de** garantir un RPO ≤ 24h en cas de panne matérielle.

**Critères d'acceptation :**

- `GIVEN` le script de backup configuré en `cron` à 02h00,
  `WHEN` le job s'exécute,
  `THEN` un dump PostgreSQL (`pg_dump`) est créé dans `/mnt/sentinel_backups/db/`.

- `GIVEN` le `pg_dump` terminé,
  `WHEN` le script continue,
  `THEN` un `rsync` incrémental copie `/app/media/proofs/` vers `/mnt/sentinel_backups/media/`.

- `GIVEN` une erreur pendant le backup (ex: espace disque insuffisant),
  `WHEN` le script échoue,
  `THEN` un email d'alerte est envoyé à l'adresse RSSI configurée.

- `GIVEN` les backups existants,
  `WHEN` ils ont plus de 30 jours,
  `THEN` le script les supprime automatiquement (rotation).

---

### S0.5 — Fichier `.env.example` et gestion des secrets

**En tant que** développeur ou ingénieur infra,
**Je veux** un fichier `.env.example` documenté avec toutes les variables requises,
**Afin de** ne jamais accidentellement déployer avec des valeurs par défaut non sécurisées.

**Critères d'acceptation :**

- `GIVEN` le dépôt Git du projet,
  `WHEN` j'inspecte le `.gitignore`,
  `THEN` le fichier `.env` est bien exclu du versioning (jamais commité).

- `GIVEN` le fichier `.env.example`,
  `WHEN` je le lis,
  `THEN` toutes les variables obligatoires sont listées avec leur description et aucune valeur de production réelle n'y figure.

- `GIVEN` le fichier `.env` de production sur la VM,
  `WHEN` j'inspecte ses permissions,
  `THEN` seul `root` peut le lire (`chmod 600`).

**Variables minimales requises :** `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_PASSWORD`, `DATABASE_URL`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_PORT`.

---

## E1 — Authentification, Modèles Core & Administration

> **Objectif :** Construire les fondations complètes de l'application : utilisateurs, organigramme, délégations/intérims, RBAC, RLS, et l'interface d'administration Django opérationnelle dès Sprint 1.
>
> **Prérequis :** E0 terminé.
> **FR couvertes :** FR1, FR2, FR3, FR4.
> **NFR couvertes :** NFR-SEC-02 (Session 30min), NFR-PERF-01 (RBAC < 10ms), NFR-REL-01 (Fail-safe RLS).

---

### S1.1 — Modèle `User` custom (avec rôle RBAC)

**En tant que** développeur,
**Je veux** un modèle `User` personnalisé héritant de `AbstractBaseUser`,
**Afin de** contrôler exactement les champs, l'UUID comme clé primaire, et le rôle RBAC directement sur le modèle.

**Critères d'acceptation :**

- `GIVEN` la migration initiale,
  `WHEN` j'inspecte la table `users_user` en base,
  `THEN` la clé primaire `id` est un `UUID` (non un entier auto-incrémenté).

- `GIVEN` un `User` créé,
  `WHEN` j'accède à `user.role`,
  `THEN` la valeur est l'une des constantes définies : `AUDIT`, `DM`, `ETP`, `DG`, `EXTERNE`, `RSSI`.

- `GIVEN` un utilisateur avec `is_active=False`,
  `WHEN` il tente de se connecter,
  `THEN` l'authentification échoue immédiatement (`HTTP 403`), même avec les bons credentials.

- `GIVEN` le modèle `User`,
  `WHEN` j'appelle `user.has_role('DM')`,
  `THEN` la méthode retourne `True` si le rôle correspond, `False` sinon.

**Champs obligatoires :** `id` (UUID PK), `username`, `email` (UK), `first_name`, `last_name`, `role`, `department_id` (FK nullable pour RSSI/DG), `is_active`, `is_staff`, `last_login`, `date_joined`, `created_at`, `updated_at`.

---

### S1.2 — Modèle `Department` (organigramme hiérarchique)

**En tant que** administrateur IT,
**Je veux** un modèle `Department` avec auto-référencement,
**Afin de** représenter la hiérarchie des directions, agences et filiales de la BICEC.

**Critères d'acceptation :**

- `GIVEN` une Direction Générale créée sans `parent_id`,
  `WHEN` je crée une Direction Métier avec `parent_id` pointant vers la DG,
  `THEN` la relation hiérarchique est persistée et `dept.get_children()` retourne la Direction Métier.

- `GIVEN` un `Department`,
  `WHEN` j'appelle `dept.get_full_hierarchy()`,
  `THEN` la méthode retourne la liste ordonnée de tous les ancêtres jusqu'à la racine.

- `GIVEN` le champ `type`,
  `WHEN` j'inspecte les valeurs autorisées,
  `THEN` seules `DIRECTION`, `AGENCE`, `FILIALE` sont acceptées (constraint CHECK PostgreSQL).

- `GIVEN` le champ `code`,
  `WHEN` je tente de créer deux départements avec le même code,
  `THEN` une erreur d'unicité est levée (`UNIQUE constraint`).

---

### S1.3 — Modèle `Delegation` (intérim FR4)

**En tant que** développeur,
**Je veux** un modèle `Delegation` pour gérer les intérims à deux niveaux,
**Afin de** permettre (a) à l'Audit de déléguer les droits d'un DM absent vers un remplaçant DM, et (b) à un DM de déléguer à un ETP intérimaire au sein de sa direction.

**Critères d'acceptation :**

- `GIVEN` une délégation créée avec `start_date=aujourd'hui` et `end_date=dans 7 jours`,
  `WHEN` j'appelle `delegation.is_currently_active()`,
  `THEN` la méthode retourne `True`.

- `GIVEN` une délégation dont `end_date` est passée,
  `WHEN` j'appelle `delegation.is_currently_active()`,
  `THEN` la méthode retourne `False`.

- `GIVEN` le middleware RBAC,
  `WHEN` il traite une requête d'un utilisateur `delegate` avec une délégation active,
  `THEN` les permissions résolues incluent celles du `delegator` pour son périmètre.

- `GIVEN` la table `users_delegation`,
  `WHEN` j'inspecte les relations en base,
  `THEN` les FK `delegator_id` et `delegate_id` pointent toutes deux vers `users_user.id`.

- `GIVEN` toute création ou désactivation de délégation,
  `WHEN` l'opération est effectuée,
  `THEN` une entrée est créée dans `audit_auditlog` avec l'action `CREATE` ou `UPDATE`.

---

### S1.4 — Authentification (Login/Logout) avec verrouillage anti-brute-force

**En tant que** utilisateur Sentinel,
**Je veux** pouvoir me connecter avec mon identifiant et mot de passe,
**Afin d'** accéder à mon espace de travail selon mon rôle.

**Critères d'acceptation :**

- `GIVEN` un utilisateur avec des credentials valides,
  `WHEN` il soumet le formulaire de login,
  `THEN` il est redirigé vers son dashboard rôle (`/dashboard/`) et un cookie `HttpOnly; Secure; SameSite=Lax` est posé.

- `GIVEN` un utilisateur avec un mauvais mot de passe,
  `WHEN` il soumet le formulaire,
  `THEN` le message d'erreur est générique ("Identifiants incorrects") sans préciser si le username ou le mot de passe est en cause.

- `GIVEN` 5 tentatives de connexion échouées consécutives depuis la même IP,
  `WHEN` une 6ème tentative est effectuée,
  `THEN` le compte est verrouillé et le message "Compte verrouillé. Contactez l'administrateur." est affiché. Un `django-axes` `AccessAttempt` est créé.

- `GIVEN` un utilisateur connecté depuis 30 minutes sans action,
  `WHEN` il effectue une nouvelle requête,
  `THEN` il est redirigé vers `/login/` avec le message "Session expirée."

- `GIVEN` un utilisateur qui clique "Se déconnecter",
  `WHEN` la requête POST `/logout/` est envoyée,
  `THEN` la session est détruite, le cookie supprimé, et l'entrée `AuditLog(action=LOGOUT)` est créée.

**Notes techniques :** Utiliser `django-axes` pour le rate limiting. `SESSION_COOKIE_AGE = 1800`, `SESSION_SAVE_EVERY_REQUEST = True`.

---

### S1.5 — Middleware RBAC (filtrage QuerySet par périmètre)

**En tant que** développeur,
**Je veux** un middleware injectant le contexte de tenant dans chaque requête,
**Afin que** tous les QuerySets soient automatiquement filtrés au périmètre de l'utilisateur sans effort supplémentaire dans les vues.

**Critères d'acceptation :**

- `GIVEN` un DM de la Direction des Risques (dept_id=5) connecté,
  `WHEN` le middleware traite sa requête,
  `THEN` `request.user.accessible_departments` contient uniquement les IDs de sa direction et sous-directions.

- `GIVEN` le Selector `RecommendationSelector.for_tenant(user)`,
  `WHEN` un DM l'appelle,
  `THEN` le QuerySet retourné ne contient que les recommandations de son périmètre (jamais celles d'autres directions).

- `GIVEN` un utilisateur avec une délégation active,
  `WHEN` le middleware résout ses permissions,
  `THEN` les délégations actives (`is_currently_active()=True`) sont incluses dans le périmètre calculé.

- `GIVEN` le middleware et un Auditeur Interne,
  `WHEN` la requête est traitée,
  `THEN` `for_tenant(user)` retourne toutes les recommandations (aucun filtre direction pour l'Audit).

**Notes techniques :** Le résultat de la résolution des permissions doit être mis en cache dans la session Django pour respecter NFR-PERF-01 (< 10ms par requête).

---

---

### S1.7 — Modèle `AuditLog` (append-only)

**En tant que** RSSI,
**Je veux** que chaque action significative dans l'application soit tracée dans un journal immuable,
**Afin de** répondre aux exigences de traçabilité COBAC (NFR-SEC-05 : 12 mois de conservation).

**Critères d'acceptation :**

- `GIVEN` un utilisateur qui se connecte,
  `WHEN` le login réussit,
  `THEN` une entrée `AuditLog(action='LOGIN', user=user, ip_address=...)` est créée.

- `GIVEN` une action système du scheduler (ex: passage OVERDUE),
  `WHEN` l'entrée AuditLog est créée,
  `THEN` le champ `user_id` est `NULL` et `action='SYSTEM'`.

- `GIVEN` la table `audit_auditlog`,
  `WHEN` un développeur tente d'exécuter `DELETE FROM audit_auditlog`,
  `THEN` un trigger PostgreSQL bloque la suppression et lève une exception.

- `GIVEN` les entrées AuditLog de plus de 12 mois,
  `WHEN` la tâche de purge Django-Q2 s'exécute,
  `THEN` elles sont archivées (export CSV) puis supprimées.

**Actions tracées :** `CREATE`, `UPDATE`, `DELETE` (soft), `LOGIN`, `LOGIN_FAILED`, `LOGOUT`, `TRANSITION`, `SYSTEM`, `EXPORT`.

---

### S1.8 — Templates de base (layout et navigation par rôle)

**En tant que** utilisateur Sentinel,
**Je veux** une interface cohérente avec une navigation adaptée à mon rôle,
**Afin de** trouver rapidement mes outils sans être distrait par des menus non pertinents.

**Critères d'acceptation :**

- `GIVEN` un Auditeur Interne connecté,
  `WHEN` il consulte la navigation,
  `THEN` il voit : Tableau de bord · Recommandations · Import · Rapports · Administration.

- `GIVEN` un DM connecté,
  `WHEN` il consulte la navigation,
  `THEN` il voit uniquement : Mon tableau de bord · Mes recommandations (son périmètre uniquement).

- `GIVEN` un ETP connecté,
  `WHEN` il consulte la navigation,
  `THEN` il voit uniquement : Ma to-do list · Mes preuves soumises.

- `GIVEN` n'importe quel utilisateur connecté,
  `WHEN` il clique sur son avatar (coin supérieur droit),
  `THEN` il accède à son profil et au bouton "Se déconnecter".

- `GIVEN` la page d'erreur 403,
  `WHEN` un utilisateur tente d'accéder à une ressource non autorisée,
  `THEN` un message clair "Accès non autorisé" s'affiche sans divulguer d'informations techniques.

---

### S1.9 — Admin Django : Gestion de l'organigramme (`Department`)

**En tant que** IT Admin / RSSI,
**Je veux** gérer l'organigramme de la BICEC depuis l'interface Admin Django,
**Afin de** créer, modifier et désactiver les Directions, Agences et Filiales sans intervention des développeurs.

**Critères d'acceptation :**

- `GIVEN` l'interface Admin Django,
  `WHEN` l'IT Admin accède à la section `Department`,
  `THEN` il voit la liste de toutes les unités organisationnelles avec leur type et hiérarchie.

- `GIVEN` la création d'une nouvelle Direction,
  `WHEN` le formulaire Admin est soumis,
  `THEN` le code est vérifié pour l'unicité et l'unité est créée.

- `GIVEN` un `Department` avec des utilisateurs actifs,
  `WHEN` l'Admin tente de le supprimer physiquement,
  `THEN` une erreur de contrainte d'intégrité est levée (protection PostgreSQL FK).

---

### S1.10 — Admin Django : Gestion des utilisateurs (`User`)

**En tant que** IT Admin / RSSI,
**Je veux** créer, modifier le rôle et désactiver les comptes utilisateurs depuis l'Admin Django,
**Afin de** contrôler les accès à Sentinel en temps réel (FR3).

**Critères d'acceptation :**

- `GIVEN` la création d'un compte utilisateur DM,
  `WHEN` le formulaire Admin est soumis,
  `THEN` l'utilisateur peut se connecter avec les credentials créés.

- `GIVEN` un utilisateur actif avec une session ouverte,
  `WHEN` l'IT Admin bascule `is_active=False` depuis l'Admin,
  `THEN` la session de l'utilisateur est immédiatement invalidée (`invalidate_all_sessions()`) et il est déconnecté à sa prochaine requête.

- `GIVEN` la liste des utilisateurs dans l'Admin,
  `WHEN` l'IT Admin filtre par rôle,
  `THEN` seuls les utilisateurs du rôle sélectionné sont affichés.

---

### S1.11 — Admin Django : Gestion des délégations (`Delegation`)

**En tant que** IT Admin ou DM,
**Je veux** créer et gérer les intérims depuis l'Admin Django,
**Afin de** substituer temporairement un utilisateur absent sans rupture du workflow (FR4).

**Critères d'acceptation :**

- `GIVEN` la création d'une délégation DM→DM avec des dates d'effet,
  `WHEN` la date de début est atteinte,
  `THEN` le middleware RBAC reconnaît automatiquement le `delegate` comme ayant les droits du `delegator`.

- `GIVEN` une délégation existante,
  `WHEN` l'IT Admin la désactive manuellement (`is_active=False`),
  `THEN` les droits délégués sont immédiatement révoqués.

- `GIVEN` la création d'une délégation,
  `WHEN` l'opération est sauvegardée,
  `THEN` une entrée `AuditLog` est créée avec le détail de la délégation.

---

### S1.12 — Admin Django : Consultation de l'Audit Log (lecture seule)

**En tant que** RSSI,
**Je veux** consulter et filtrer l'Audit Log depuis l'Admin Django,
**Afin de** surveiller les actions de sécurité et répondre aux demandes d'audit COBAC (NFR-SEC-05).

**Critères d'acceptation :**

- `GIVEN` la section `AuditLog` de l'Admin Django,
  `WHEN` le RSSI y accède,
  `THEN` la liste est en **lecture seule** (aucun bouton Modifier ni Supprimer).

- `GIVEN` la liste AuditLog,
  `WHEN` le RSSI filtre par `action=LOGIN_FAILED`,
  `THEN` uniquement les tentatives de connexion échouées sont affichées, triées par date décroissante.

- `GIVEN` la liste AuditLog,
  `WHEN` le RSSI filtre par `user` et une plage de dates,
  `THEN` les résultats correspondent exactement aux critères (requête optimisée avec index).

---

### S1.13 — Admin Django : Configuration globale du site (`SiteConfiguration`)

**En tant que** IT Admin,
**Je veux** un modèle singleton `SiteConfiguration` éditable depuis l'Admin,
**Afin de** modifier les paramètres applicatifs globaux (email expéditeur, seuils d'alerte) sans redéploiement.

**Critères d'acceptation :**

- `GIVEN` la section `SiteConfiguration` de l'Admin,
  `WHEN` l'IT Admin modifie l'email expéditeur des notifications,
  `THEN` les prochains emails sont envoyés avec le nouvel expéditeur, sans redémarrage du conteneur.

- `GIVEN` le modèle `SiteConfiguration`,
  `WHEN` un développeur tente de créer une deuxième instance,
  `THEN` une contrainte (pattern Singleton) lève une erreur.

**Paramètres gérés :** Email expéditeur, seuil d'alerte disque (%), adresse email RSSI pour les alertes système.

---

---

## E2 — Recommandations (CRUD & FSM)

> **Objectif :** Implémenter le cœur métier : création unitaire et en masse, machine à états FSM, triage et assignation.
>
> **Prérequis :** E1 terminé.
> **FR couvertes :** FR5, FR6, FR7, FR10, FR11, FR12.
> **NFR couvertes :** NFR-PERF-02 (TTFB < 200ms).

---

### S2.1 — Modèle `Recommendation` avec `django-fsm` (5 états)

**En tant que** développeur,
**Je veux** un modèle `Recommendation` avec un `FSMField` gérant les 5 états du workflow,
**Afin que** aucune transition illégale ne puisse se produire, même via une manipulation directe de l'ORM.

**Critères d'acceptation :**

- `GIVEN` le modèle `Recommendation`,
  `WHEN` j'inspecte le champ `status`,
  `THEN` c'est un `FSMField` avec les 5 valeurs autorisées : `ASSIGNED`, `IN_PROGRESS`, `PENDING_DM_REVIEW`, `PENDING_AUDIT_REVIEW`, `CLOSED_RESOLVED`.

- `GIVEN` une recommandation au statut `ASSIGNED`,
  `WHEN` je tente d'appeler directement `reco.status = 'CLOSED_RESOLVED'` puis `reco.save()`,
  `THEN` `django-fsm` lève une exception `TransitionNotAllowed` et bloque la mutation.

- `GIVEN` une recommandation au statut `ASSIGNED`,
  `WHEN` je tente d'appeler `reco.close_by_audit()`,
  `THEN` `django-fsm` lève une exception `TransitionNotAllowed` (transition non autorisée depuis cet état).

- `GIVEN` toute transition FSM,
  `WHEN` elle s'exécute,
  `THEN` elle s'exécute dans une transaction atomique avec `select_for_update()` (protection accès concurrent).

**Champs obligatoires :** `id` (UUID PK), `title`, `description`, `source` (CHECK), `priority` (CHECK), `status` (FSMField), `is_overdue` (bool), `due_date`, `original_due_date`, `created_by_id` (FK), `assigned_dm_id` (FK nullable), `assigned_etp_id` (FK nullable), `department_id` (FK), `import_tag` (nullable), `is_deleted` (bool), `deleted_at`, `reference_rapport`, `created_at`, `updated_at`.

---

### S2.2 — Transitions d'assignation (Audit : `assign_to_dm`, `reassign_dm`, `self_assign`)

**En tant que** Auditeur Interne,
**Je veux** pouvoir assigner une recommandation à un DM, me la ré-assigner temporairement pour triage, ou la réassigner à un autre DM,
**Afin de** contrôler le flux d'entrée des recommandations (FR10, FR11).

**Critères d'acceptation :**

- `GIVEN` une reco au statut `ASSIGNED` sans DM assigné,
  `WHEN` l'Audit appelle `assign_to_dm(dm_user)`,
  `THEN` `assigned_dm_id` est mis à jour, une notification est envoyée au DM, et l'AuditLog trace la transition.

- `GIVEN` une reco au statut `ASSIGNED` avec un DM assigné,
  `WHEN` l'Audit appelle `reassign_dm(new_dm_user)`,
  `THEN` `assigned_dm_id` pointe vers le nouveau DM, l'ancien DM reçoit une notification, le nouveau DM reçoit une notification.

- `GIVEN` une reco au statut `ASSIGNED` dont le DM n'est pas encore identifié,
  `WHEN` l'Audit appelle `self_assign()`,
  `THEN` `assigned_dm_id` pointe vers l'Auditeur lui-même et une entrée AuditLog est créée (pour traçabilité du triage).

- `GIVEN` un Auditeur qui tente d'assigner à un utilisateur avec le rôle `ETP`,
  `WHEN` la transition est tentée,
  `THEN` le service lève une erreur de validation ("Le destinataire doit avoir le rôle DM").

---

### S2.3 — Transitions DM : `delegate_to_etp()` et `accept_by_dm()` (DM Porteur)

**En tant que** Directeur Métier,
**Je veux** choisir de déléguer une recommandation à un ETP de mon équipe OU de la traiter moi-même (DM Porteur),
**Afin de** gérer mon équipe avec flexibilité (FR12).

**Critères d'acceptation :**

- `GIVEN` une reco au statut `ASSIGNED` assignée à un DM,
  `WHEN` le DM appelle `delegate_to_etp(etp_user)`,
  `THEN` le statut passe à `IN_PROGRESS`, `assigned_etp_id` est défini, l'ETP reçoit une notification.

- `GIVEN` une tentative de délégation à un ETP hors de la direction du DM,
  `WHEN` la transition est tentée,
  `THEN` le service lève une erreur de validation ("L'ETP doit appartenir à votre direction").

- `GIVEN` une reco au statut `ASSIGNED` assignée à un DM,
  `WHEN` le DM appelle `accept_by_dm()` (DM Porteur),
  `THEN` le statut passe à `IN_PROGRESS`, `assigned_etp_id` reste `NULL`, et le DM peut uploader des preuves directement.

- `GIVEN` une reco en `IN_PROGRESS` gérée en DM Porteur (`assigned_etp_id=NULL`),
  `WHEN` le DM accède au formulaire d'upload de preuves,
  `THEN` le formulaire est bien accessible (le RBAC reconnaît le DM comme porteur).

---

### S2.4 — Soft Delete (uniquement si statut `ASSIGNED`)

**En tant que** Auditeur Interne,
**Je veux** pouvoir supprimer (soft delete) une recommandation mal saisie,
**Afin de** corriger les erreurs de frappe avant qu'elle ne soit traitée (FR6).

**Critères d'acceptation :**

- `GIVEN` une reco au statut `ASSIGNED`,
  `WHEN` l'Audit clique "Supprimer" et confirme,
  `THEN` `is_deleted=True` et `deleted_at=now()` sont posés, la reco disparaît des listes, mais reste en base.

- `GIVEN` une reco au statut `IN_PROGRESS` (ou tout autre statut après ASSIGNED),
  `WHEN` l'Audit tente de la supprimer,
  `THEN` le service lève une erreur ("La suppression est impossible après l'assignation active").

- `GIVEN` une reco soft-deleted,
  `WHEN` le QuerySet `for_tenant()` est appelé,
  `THEN` la reco est exclue de tous les résultats (`filter(is_deleted=False)`).

- `GIVEN` le soft delete d'une recommandation,
  `WHEN` l'opération est effectuée,
  `THEN` une entrée `AuditLog(action='DELETE')` est créée avec l'état avant suppression dans `changes`.

---

### S2.5 — Création unitaire d'une recommandation (Formulaire HTMX)

**En tant que** Auditeur Interne,
**Je veux** créer une recommandation individuelle via un formulaire,
**Afin d'** enregistrer une nouvelle recommandation d'audit (FR5).

**Critères d'acceptation :**

- `GIVEN` le formulaire de création,
  `WHEN` l'Audit soumet un formulaire valide (titre, source, priorité, échéance, direction),
  `THEN` la recommandation est créée au statut `ASSIGNED`, et l'Audit est redirigé vers la fiche de la recommandation.

- `GIVEN` le formulaire avec un champ `due_date` dans le passé,
  `WHEN` le formulaire est soumis,
  `THEN` une erreur de validation s'affiche ("La date d'échéance doit être dans le futur").

- `GIVEN` le formulaire HTMX,
  `WHEN` l'Audit change la valeur du champ `direction`,
  `THEN` la liste des DM disponibles se met à jour dynamiquement (requête HTMX partielle) sans rechargement complet.

- `GIVEN` la création réussie,
  `WHEN` la reco est enregistrée,
  `THEN` `original_due_date` et `due_date` sont identiques (la date originale est préservée intacte).

---

### `[v2]` ~~S2.6 — Création en masse (Bulk Create)~~

> **Reporté en v2.** Économie : 4 points. La création unitaire (S2.5) est suffisante pour le MVP. Cette fonctionnalité sera disponible dans la version suivante post Go-Live.

~~**En tant que** Auditeur Interne,
**Je veux** saisir plusieurs recommandations simultanément via un formulaire multi-lignes,
**Afin de** réduire la friction de saisie post-mission (FR7).~~

**Critères d'acceptation :**

- `GIVEN` le formulaire Bulk Create,
  `WHEN` l'Audit saisit N lignes de recommandations et soumet,
  `THEN` toutes les recommandations valides sont créées en une seule transaction atomique.

- `GIVEN` N lignes avec 1 ligne invalide (ex: champ `title` vide à la ligne 3),
  `WHEN` le formulaire est soumis,
  `THEN` une erreur de validation s'affiche sur la ligne 3 uniquement, sans créer aucune recommandation (tout ou rien).

- `GIVEN` la soumission réussie de N recommandations,
  `WHEN` l'opération se termine,
  `THEN` l'Audit est redirigé vers la liste des recommandations créées, avec un message de confirmation "N recommandations créées".

- `GIVEN` le formulaire Bulk Create,
  `WHEN` l'Audit clique "+ Ajouter une ligne",
  `THEN` une nouvelle ligne de formulaire apparaît dynamiquement (HTMX, sans rechargement).

---

### S2.7 — Modèle `Comment` et Selectors

**En tant que** développeur,
**Je veux** un modèle `Comment` et des Selectors optimisés pour les QuerySets de recommandations,
**Afin de** centraliser la logique de lecture et garantir les performances (NFR-PERF-01).

**Critères d'acceptation :**

- `GIVEN` la création d'un commentaire de type `SUBMISSION`,
  `WHEN` l'ETP soumet ses preuves,
  `THEN` un `Comment(type='SUBMISSION', content=justification, recommendation=reco, author=etp)` est créé automatiquement par le `WorkflowService`.

- `GIVEN` le Selector `RecommendationSelector.for_tenant(user)`,
  `WHEN` un DM l'appelle,
  `THEN` le QuerySet ne provoque pas de requêtes N+1 (utilise `select_related('assigned_etp', 'assigned_dm', 'department')`).

- `GIVEN` le Selector `get_overdue_recommendations(user)`,
  `WHEN` il est appelé,
  `THEN` il retourne uniquement les recos avec `is_overdue=True` et `status != 'CLOSED_RESOLVED'`.

---

## E3 — Preuves & Sécurité Fichiers

> **Objectif :** Gérer l'upload sécurisé des fichiers de preuves avec le cycle DRAFT → PENDING, validation Magic Bytes, et versioning.
>
> **Prérequis :** E2 terminé.
> **FR couvertes :** FR15, FR16, FR18, FR19, FR25.
> **NFR couvertes :** NFR-SEC-04 (Magic Bytes), NFR-SCA-01 (15 Mo, 5 fichiers).

---

### S3.1 — Modèle `Proof` (statuts, versioning, types)

**En tant que** développeur,
**Je veux** un modèle `Proof` avec gestion des statuts et du versioning,
**Afin de** tracer l'historique complet des soumissions et rejets (FR25).

**Critères d'acceptation :**

- `GIVEN` un fichier uploadé par un ETP,
  `WHEN` le `Proof` est créé,
  `THEN` son statut initial est `DRAFT` et son `version` vaut `1`.

- `GIVEN` une preuve au statut `REJECTED`,
  `WHEN` l'ETP uploade une nouvelle version,
  `THEN` un nouveau `Proof` est créé avec `version=N+1` et statut `DRAFT`. L'ancienne preuve reste en base avec statut `REJECTED`.

- `GIVEN` une recommandation `CLOSED_RESOLVED`,
  `WHEN` j'inspecte ses preuves en base,
  `THEN` toutes les preuves (DRAFT, PENDING, ACCEPTED, REJECTED) sont préservées (aucune n'est supprimée physiquement, sauf soft-delete explicite des DRAFT par l'auteur).

- `GIVEN` le champ `proof_type`,
  `WHEN` j'inspecte les valeurs autorisées,
  `THEN` seules `EVIDENCE` (preuve standard) et `PV_RECETTE` (PV signé par DM) sont acceptées.

**Champs obligatoires :** `id` (UUID PK), `recommendation_id` (FK), `uploaded_by_id` (FK), `original_filename`, `file_path` (UUID renamed), `content_type`, `file_size_bytes`, `status` (DRAFT/PENDING/ACCEPTED/REJECTED), `version` (int), `rejection_reason` (nullable), `proof_type`, `created_at`.

---

### S3.2 — `upload_proof()` : Upload sécurisé avec validation Magic Bytes

**En tant que** ETP (ou DM Porteur),
**Je veux** uploader un fichier de preuve avec validation automatique du type réel,
**Afin de** m'assurer que seuls les formats légitimes sont acceptés (NFR-SEC-04, FR15).

**Critères d'acceptation :**

- `GIVEN` un fichier `rapport.pdf` (vrai PDF),
  `WHEN` l'ETP l'uploade,
  `THEN` le fichier est accepté, renommé en `{uuid}.pdf` et stocké dans `media/proofs/{reco_id}/`. Un `Proof(status=DRAFT)` est créé.

- `GIVEN` un fichier `virus.exe` renommé `rapport.pdf`,
  `WHEN` l'ETP tente de l'uploader,
  `THEN` `python-magic` détecte le vrai type `application/x-dosexec`, et le fichier est **rejeté avant écriture sur le disque** avec le message "Type de fichier non autorisé".

- `GIVEN` un fichier Excel avec macros (`rapport.xlsm`),
  `WHEN` l'ETP tente de l'uploader,
  `THEN` le fichier est rejeté avec le message "Les fichiers avec macros sont interdits pour des raisons de sécurité".

- `GIVEN` un fichier de 16 Mo,
  `WHEN` l'ETP tente de l'uploader,
  `THEN` Nginx retourne `413` avant même d'atteindre Django (`client_max_body_size 16M`).

- `GIVEN` un upload simultané de 6 fichiers en une seule requête,
  `WHEN` la vue traite la requête,
  `THEN` une erreur de validation s'affiche ("Maximum 5 fichiers par soumission").

**Formats autorisés :** PDF (`application/pdf`), JPG/PNG (`image/jpeg`, `image/png`), XLSX (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), CSV (`text/csv`), MSG/EML (email), TXT (`text/plain`).

---

### S3.3 — `submit_proofs()` : Soumission (bascule DRAFT → PENDING)

**En tant que** ETP,
**Je veux** soumettre mes brouillons de preuves au DM en ajoutant un commentaire justificatif,
**Afin de** déclencher sa revue (FR16).

**Critères d'acceptation :**

- `GIVEN` une reco `IN_PROGRESS` avec ≥ 1 preuve `DRAFT`,
  `WHEN` l'ETP clique "Soumettre au DM" avec un commentaire,
  `THEN` toutes les preuves `DRAFT` passent au statut `PENDING`, la reco transite vers `PENDING_DM_REVIEW`, et le DM reçoit une notification.

- `GIVEN` une tentative de soumission sans preuve DRAFT,
  `WHEN` l'ETP clique "Soumettre",
  `THEN` le service bloque la transition et affiche "Veuillez uploader au moins une preuve avant de soumettre".

- `GIVEN` une soumission avec un commentaire vide,
  `WHEN` le formulaire est soumis,
  `THEN` une erreur de validation s'affiche ("Le commentaire justificatif est obligatoire").

- `GIVEN` la soumission réussie,
  `WHEN` la transition est complète,
  `THEN` un `Comment(type='SUBMISSION', content=commentaire)` est créé et l'entrée AuditLog trace la transition.

---

### S3.4 — Soft Delete de brouillon par l'auteur

**En tant que** ETP,
**Je veux** pouvoir supprimer un fichier en brouillon que j'ai uploadé par erreur,
**Afin de** corriger mes uploads avant soumission.

**Critères d'acceptation :**

- `GIVEN` une preuve au statut `DRAFT` uploadée par l'ETP X,
  `WHEN` l'ETP X clique "Supprimer ce brouillon",
  `THEN` la preuve est soft-deletée (ou statut basculé à REJECTED avec flag `deleted_by_author`).

- `GIVEN` une preuve au statut `DRAFT` uploadée par l'ETP X,
  `WHEN` l'ETP Y (un autre utilisateur) tente de la supprimer,
  `THEN` le RBAC bloque la demande avec une erreur `403 Forbidden`.

- `GIVEN` une preuve au statut `PENDING` ou `ACCEPTED`,
  `WHEN` l'ETP tente de la supprimer,
  `THEN` le service bloque la demande ("Impossible de supprimer une preuve soumise ou validée").

---

### S3.5 — Upload du PV de Recette (par le DM)

**En tant que** Directeur Métier,
**Je veux** pouvoir uploader un PV de recette signé lors de ma validation,
**Afin d'** être exempté du commentaire obligatoire (FR19).

**Critères d'acceptation :**

- `GIVEN` une reco en `PENDING_DM_REVIEW`,
  `WHEN` le DM uploade un fichier PDF de type `PV_RECETTE`,
  `THEN` un `Proof(proof_type='PV_RECETTE', status='PENDING', uploaded_by=dm)` est créé.

- `GIVEN` un PV de recette uploadé,
  `WHEN` le DM valide sans remplir le commentaire,
  `THEN` la validation est acceptée (le PV de recette exempte le commentaire obligatoire).

- `GIVEN` une tentative d'upload de PV de recette par un ETP,
  `WHEN` la requête est envoyée,
  `THEN` le RBAC bloque la demande (`403`) : seul un DM (ou DG porteur) peut uploader un PV de recette.

---

### S3.6 — Renommage UUID et stockage sécurisé

**En tant que** développeur,
**Je veux** que tout fichier uploadé soit renommé en UUIDv4 et stocké dans un répertoire non accessible via Nginx,
**Afin de** bloquer les attaques Path Traversal et empêcher l'exécution directe de fichiers.

**Critères d'acceptation :**

- `GIVEN` un fichier uploadé nommé `../../../../etc/passwd`,
  `WHEN` le service traite l'upload,
  `THEN` `original_filename` conserve le nom original (inoffensif en BDD), mais `file_path` est un UUIDv4 propre.

- `GIVEN` un fichier stocké dans `media/proofs/`,
  `WHEN` j'essaie d'y accéder directement via `https://sentinel.intra.bicec.local/media/proofs/{uuid}.pdf`,
  `THEN` Nginx retourne `404` (le répertoire media n'est pas servi directement).

- `GIVEN` un fichier stocké,
  `WHEN` j'accède à `/download/{proof_uuid}/`,
  `THEN` Django vérifie le RBAC avant de servir le fichier via `FileResponse`.

---

### S3.7 — Téléchargement sécurisé via vue Django (contrôle RBAC)

**En tant que** utilisateur autorisé,
**Je veux** télécharger un fichier de preuve via une URL Sentinel,
**Afin de** consulter les documents de preuve sans bypasser les contrôles de sécurité.

**Critères d'acceptation :**

- `GIVEN` un DM de la Direction des Risques,
  `WHEN` il tente de télécharger une preuve d'une recommandation de sa direction,
  `THEN` Django vérifie son périmètre via le RBAC et sert le fichier.

- `GIVEN` un DM de la Direction des Risques,
  `WHEN` il tente de télécharger une preuve d'une recommandation d'une autre direction,
  `THEN` Django retourne `403 Forbidden`.

- `GIVEN` un Auditeur Externe,
  `WHEN` il tente de télécharger une preuve d'état `DRAFT`,
  `THEN` Django retourne `403 Forbidden` (les Externes ne voient que les preuves `ACCEPTED`).

---

### `[v2]` S3.8 — Historique des versions de preuves (UI uniquement reportée)

> **UI reportée en v2.** Économie : 2 points. **Les données de versioning sont intégralement stockées en base** (champ `version`, statuts REJECTED préservés). Seule la vue dédiée permettant de consulter cet historique est reportée. En v1, l'auditeur peut consulter les données brutes via l'Admin Django si nécessaire.

**En tant que** Auditeur Interne ou Auditeur Externe COBAC,
**Je veux** consulter l'historique complet des versions de preuves soumises et rejetées,
**Afin de** reconstituer la chronologie des corrections (FR25).

**Critères d'acceptation :**

- `GIVEN` une recommandation avec 3 versions de preuves (v1 REJECTED, v2 REJECTED, v3 ACCEPTED),
  `WHEN` l'Audit consulte la fiche de la recommandation,
  `THEN` les 3 versions sont affichées en ordre chronologique avec leur statut et les motifs de rejet.

- `GIVEN` la liste des preuves historisées,
  `WHEN` un inspecteur COBAC consulte la fiche d'une recommandation CLOSED,
  `THEN` il peut télécharger les preuves `ACCEPTED` uniquement (les REJECTED et DRAFT sont masqués pour les Externes).

---

---

## E4 — Workflow de Validation (DM / DG / Audit → Clôture)

> **Objectif :** Implémenter la chaîne de validation complète — revue DM, soumission directe par DG Porteur, revue Audit, clôture avec sceau HMAC-SHA256 et rejet.
>
> **Prérequis :** E2 et E3 terminés.
> **FR couvertes :** FR17, FR20, FR24, FR27.
> **NFR couvertes :** NFR-SEC-03 (HMAC ≤ 500ms), NFR-PERF-03, NFR-PERF-04.

---

### S4.1 — Transition `submit_to_dm()` : ETP → PENDING_DM_REVIEW

**En tant que** ETP,
**Je veux** soumettre mon dossier complet au DM pour validation,
**Afin de** déclencher sa revue officielle (FR16).

**Critères d'acceptation :**

- `GIVEN` une reco `IN_PROGRESS` avec ≥ 1 preuve `DRAFT`,
  `WHEN` l'ETP clique "Soumettre au DM" avec un commentaire justificatif,
  `THEN` le statut passe à `PENDING_DM_REVIEW`, les preuves basculent en `PENDING`, et le DM reçoit une notification immédiate.

- `GIVEN` deux ETP qui cliquent "Soumettre" au même instant (accès concurrent),
  `WHEN` le service traite les deux requêtes,
  `THEN` le `select_for_update()` garantit qu'une seule transition réussit. Le second reçoit "La recommandation a déjà été soumise."

- `GIVEN` la transition réussie,
  `WHEN` j'inspecte l'AuditLog,
  `THEN` une entrée `action='TRANSITION', changes={'status': ['IN_PROGRESS', 'PENDING_DM_REVIEW']}` est créée.

---

### S4.2 — Transition `approve_by_dm()` : DM valide → PENDING_AUDIT_REVIEW

**En tant que** Directeur Métier,
**Je veux** valider les preuves soumises par l'ETP et les transmettre à l'Audit,
**Afin de** certifier que le travail correctif est satisfaisant (FR17).

**Critères d'acceptation :**

- `GIVEN` une reco `PENDING_DM_REVIEW` avec des preuves `PENDING`,
  `WHEN` le DM clique "Valider et transmettre à l'Audit" avec un commentaire,
  `THEN` le statut passe à `PENDING_AUDIT_REVIEW`, les preuves validées basculent en `ACCEPTED`, et l'Audit reçoit une notification.

- `GIVEN` une reco avec un PV de recette uploadé,
  `WHEN` le DM valide sans remplir le champ commentaire,
  `THEN` la validation est acceptée sans erreur (le PV de recette exempte l'obligation du commentaire).

- `GIVEN` une reco sans PV de recette et sans commentaire,
  `WHEN` le DM tente de valider,
  `THEN` une erreur de validation s'affiche : "Un commentaire de validation est obligatoire (ou uploadez un PV de recette signé)."

---

### S4.3 — Transition `reject_by_dm()` : DM rejette → IN_PROGRESS

**En tant que** Directeur Métier,
**Je veux** renvoyer le dossier à l'ETP avec un motif de rejet précis,
**Afin de** guider la correction des preuves insuffisantes (FR17).

**Critères d'acceptation :**

- `GIVEN` une reco `PENDING_DM_REVIEW`,
  `WHEN` le DM clique "Rejeter" avec un motif de correction,
  `THEN` le statut repasse à `IN_PROGRESS`, les preuves rejetées basculent en `REJECTED` (préservées), et l'ETP reçoit une notification avec le motif.

- `GIVEN` une tentative de rejet sans saisir de motif,
  `WHEN` le formulaire est soumis,
  `THEN` une erreur s'affiche : "Le motif de rejet est obligatoire."

- `GIVEN` le rejet tracé,
  `WHEN` l'ETP consulte la fiche,
  `THEN` il voit le motif de rejet du DM affichée dans la timeline, avec la date et l'auteur.

---

### S4.4 — Transitions `submit_to_audit()` : DM Porteur ET DG Porteur

**En tant que** DM Porteur ou DG Porteur,
**Je veux** soumettre mon dossier directement à l'Audit (sans passer par un ETP intermédiaire),
**Afin de** traiter la recommandation en tant que porteur principal (FR12, UC DG.8).

**Critères d'acceptation :**

- `GIVEN` une reco `IN_PROGRESS` en mode DM Porteur (`assigned_etp_id=NULL`),
  `WHEN` le DM clique "Soumettre à l'Audit",
  `THEN` le statut passe à `PENDING_AUDIT_REVIEW` et l'Audit reçoit une notification.

- `GIVEN` une reco `IN_PROGRESS` avec le DG comme porteur,
  `WHEN` le DG clique "Soumettre à l'Audit",
  `THEN` le statut passe à `PENDING_AUDIT_REVIEW`. Le RBAC autorise explicitement le rôle `DG` pour cette transition.

- `GIVEN` un ETP qui tente d'appeler `submit_to_audit()`,
  `WHEN` la requête est envoyée,
  `THEN` le RBAC bloque la demande avec `403 Forbidden`.

---

### S4.5 — Transition `close_by_audit()` + Sceau HMAC-SHA256

**En tant que** Auditeur Interne,
**Je veux** clôturer définitivement une recommandation et apposer un sceau cryptographique,
**Afin de** certifier l'intégrité inaltérable du dossier pour les inspecteurs COBAC (FR20, FR24).

**Critères d'acceptation :**

- `GIVEN` une reco `PENDING_AUDIT_REVIEW`,
  `WHEN` l'Audit clique "Clôturer la recommandation",
  `THEN` le statut passe à `CLOSED_RESOLVED` et un `HmacSeal` est créé dans la table `audit_hmac_seal`.

- `GIVEN` la génération du sceau HMAC,
  `WHEN` le calcul s'effectue,
  `THEN` le `hmac_hash` est calculé via `HMAC-SHA256` en ≤ 500ms (NFR-PERF-03) en combinant : métadonnées normalisées de la reco + hashs SHA-256 individuels de chaque preuve `ACCEPTED`.

- `GIVEN` une reco `CLOSED_RESOLVED`,
  `WHEN` un utilisateur tente n'importe quelle mutation (POST, PUT, PATCH, DELETE),
  `THEN` le middleware d'immutabilité retourne `HTTP 403 Forbidden` avec le message "Cette recommandation est clôturée et ne peut plus être modifiée."

- `GIVEN` une altération manuelle d'une preuve en base de données post-clôture,
  `WHEN` l'Auditeur Externe recalcule le hash HMAC,
  `THEN` le système affiche une pastille rouge ⚠️ "Intégrité compromise" (le hash recalculé diffère du hash stocké).

---

### S4.6 — Transition `reject_by_audit()` : Audit rejette → IN_PROGRESS

**En tant que** Auditeur Interne,
**Je veux** renvoyer un dossier à l'équipe métier si les preuves sont insatisfaisantes,
**Afin de** exiger des corrections avant la clôture définitive (FR20).

**Critères d'acceptation :**

- `GIVEN` une reco `PENDING_AUDIT_REVIEW`,
  `WHEN` l'Audit clique "Rejeter" avec un motif obligatoire,
  `THEN` le statut passe à `IN_PROGRESS`, et une notification est envoyée au DM responsable (+ à l'ETP s'il y en a un + au DG si porteur).

- `GIVEN` une tentative de rejet sans motif,
  `WHEN` le formulaire est soumis,
  `THEN` une erreur s'affiche : "Le motif de rejet est obligatoire pour permettre au métier de corriger."

---

### S4.7 — Middleware d'immutabilité sur `CLOSED_RESOLVED`

**En tant que** architecte sécurité,
**Je veux** un middleware bloquant toute mutation HTTP sur une recommandation clôturée,
**Afin de** garantir l'inviolabilité du dossier après clôture indépendamment de la couche FSM.

**Critères d'acceptation :**

- `GIVEN` une reco `CLOSED_RESOLVED`,
  `WHEN` une requête `POST` ou `DELETE` est envoyée sur n'importe quelle ressource liée à cette reco,
  `THEN` le middleware intercepte la requête et retourne `403` avant même d'atteindre la vue Django.

- `GIVEN` le même middleware,
  `WHEN` une requête `GET` (lecture seule) est envoyée,
  `THEN` le middleware laisse passer normalement.

---

### S4.8 — Vue Timeline (Frise chronologique de l'Audit Trail)

**En tant que** Auditeur Interne, DM, ETP ou Auditeur Externe,
**Je veux** consulter la frise chronologique complète d'une recommandation,
**Afin de** reconstituer précisément l'historique de toutes les actions (FR27).

**Critères d'acceptation :**

- `GIVEN` une recommandation avec 5 transitions enregistrées,
  `WHEN` un utilisateur autorisé consulte la timeline,
  `THEN` les 5 événements sont affichés en ordre chronologique (le plus ancien en premier) avec : date, heure, acteur, action, et description lisible.

- `GIVEN` un Auditeur Externe qui consulte la timeline,
  `WHEN` la vue est rendue,
  `THEN` les événements internes (triage Audit, commentaires SYSTEM) sont masqués. Seules les transitions publiques (ASSIGNED, CLOSED…) sont visibles.

- `GIVEN` la timeline d'une reco CLOSED,
  `WHEN` le sceau HMAC est présent,
  `THEN` la dernière entrée affiche "✓ Sceau cryptographique apposé — Intégrité confirmée" avec le hash tronqué.

---

## `[v2]` ~~E5 — Demandes de Report d'Échéance~~

> **Epic entier reporté en v2.** Économie : 9 points. **Solution de contournement v1 :** L'Audit Interne modifie manuellement le champ `due_date` depuis l'Admin Django suite à un accord verbal avec le DM, en laissant une trace dans les commentaires de la recommandation.
>
> ~~**Objectif :** Permettre aux DM (et DG porteurs) de demander formellement une extension de délai, avec validation ou rejet par l'Audit.~~
>
> ~~**Prérequis :** E2 terminé.~~
> ~~**FR couvertes :** FR13, FR14.~~

---

### S5.1 — Modèle `ExtensionRequest` (FSM : PENDING / APPROVED / REJECTED)

**En tant que** développeur,
**Je veux** un modèle `ExtensionRequest` gérant le cicle de vie des demandes de report,
**Afin de** tracer formellement chaque request et decision avec justification légale pour le régulateur.

**Critères d'acceptation :**

- `GIVEN` une `ExtensionRequest` créée,
  `WHEN` j'inspecte son statut initial,
  `THEN` il vaut `PENDING`.

- `GIVEN` une même recommandation,
  `WHEN` une `ExtensionRequest` au statut `PENDING` existe déjà,
  `THEN` le service interdit d'en créer une nouvelle (une seule demande active à la fois par reco).

- `GIVEN` la table `workflow_extension_request`,
  `WHEN` j'inspecte les FK,
  `THEN` `requested_by_id` est NOT NULL, `decided_by_id` est nullable (rempli à la décision).

- `GIVEN` une `ExtensionRequest` approuvée ou rejetée,
  `WHEN` j'inspecte `decided_at`,
  `THEN` le champ est rempli avec le timestamp de la décision.

---

### S5.2 — Formulaire de demande de report (DM)

**En tant que** Directeur Métier,
**Je veux** soumettre une demande formelle de report d'échéance avec une nouvelle date et une justification,
**Afin d'** obtenir l'accord de l'Audit pour repousser légitimement la deadline (FR13).

**Critères d'acceptation :**

- `GIVEN` une reco `IN_PROGRESS` ou `PENDING_DM_REVIEW`,
  `WHEN` le DM clique "Demander un report d'échéance",
  `THEN` un formulaire s'affiche avec les champs `new_due_date` (date) et `justification` (texte long).

- `GIVEN` le formulaire soumis avec une `new_due_date` antérieure à la date actuelle,
  `WHEN` le formulaire est validé,
  `THEN` une erreur s'affiche : "La nouvelle date d'échéance doit être postérieure à aujourd'hui."

- `GIVEN` une soumission valide,
  `WHEN` la requête est traitée,
  `THEN` une `ExtensionRequest(decision='PENDING')` est créée, la reco reste dans son état FSM courant (pas de blocage du workflow), et l'Audit reçoit une notification.

- `GIVEN` une demande `PENDING` déjà existante,
  `WHEN` le DM tente d'en créer une nouvelle,
  `THEN` le service bloque avec "Une demande de report est déjà en cours d'examen."

---

### S5.3 — Vue d'approbation/rejet par l'Audit

**En tant que** Auditeur Interne,
**Je veux** approuver ou refuser une demande de report d'échéance,
**Afin de** contrôler les délais accordés avec justification traçable (FR14).

**Critères d'acceptation :**

- `GIVEN` l'Audit reçoit la notification de demande de report,
  `WHEN` il consulte la fiche de la recommandation,
  `THEN` un bandeau "Demande de report en attente" avec les détails (nouvelle date demandée, justification) est affiché.

- `GIVEN` l'Audit clique "Approuver le report",
  `WHEN` la décision est confirmée,
  `THEN` `extension_request.decision='APPROVED'`, `reco.due_date` est mis à jour avec `new_due_date`, `reco.original_due_date` reste inchangée, et le DM reçoit une notification "Report approuvé".

- `GIVEN` l'Audit clique "Refuser le report",
  `WHEN` le formulaire de refus est soumis avec un motif obligatoire,
  `THEN` `extension_request.decision='REJECTED'`, `reco.due_date` reste inchangée, et le DM reçoit une notification "Report refusé" avec le motif.

- `GIVEN` la décision prise (approuvée ou refusée),
  `WHEN` j'inspecte l'AuditLog,
  `THEN` une entrée `action='UPDATE', changes={'due_date': [...]}` ou `{'decision': [...]}` est créée.

---

### S5.4 — Conservation de `original_due_date`

**En tant que** inspecteur COBAC,
**Je veux** que la date d'échéance originale soit toujours visible, même si un report a été accordé,
**Afin de** mesurer l'écart entre le délai réglementaire initial et la date effective de clôture.

**Critères d'acceptation :**

- `GIVEN` une reco avec une `original_due_date` initiale,
  `WHEN` un report est approuvé et `due_date` est mis à jour,
  `THEN` `original_due_date` n'est jamais modifiée (colonne protégée en écriture après création).

- `GIVEN` la fiche d'une reco avec un report accordé,
  `WHEN` un utilisateur la consulte,
  `THEN` les deux dates sont affichées : "Échéance initiale : [date]" et "Échéance révisée : [date]".

---

## E6 — Dashboards, Filtres & Rapport de Synthèse PDF

> **Objectif :** Construire les vues de pilotage pour chaque rôle. **MVP Fast-Track :** Les dashboards seront basés sur des templates UI Tailwind (pas de customisation graphique lourde) pour accélérer le développement.
>
> **Prérequis :** E2, E4 et E7 terminés.
> **FR couvertes :** FR28, FR29, FR30, FR31.
> **NFR couvertes :** NFR-PERF-02 (TTFB < 200ms).

---

### S6.1 — Dashboard Audit Interne

**En tant que** Auditeur Interne,
**Je veux** un tableau de bord centralisant toutes les recommandations de la banque,
**Afin de** piloter l'avancement global du plan d'audit (FR28, FR29).

**Critères d'acceptation :**

- `GIVEN` l'Auditeur connecté sur son dashboard,
  `WHEN` la page se charge,
  `THEN` le TTFB est < 200ms (NFR-PERF-02) y compris avec 1000 recommandations en base.

- `GIVEN` le dashboard Audit,
  `WHEN` je consulte la vue,
  `THEN` je vois la liste paginée de toutes les recommandations avec : titre, source, direction, priorité, statut, échéance, indicateur OVERDUE.

- `GIVEN` les filtres disponibles,
  `WHEN` l'Audit sélectionne `source=COBAC` et `priorité=CRITIQUE`,
  `THEN` la liste se met à jour via HTMX (rechargement partiel) sans reload complet de la page.

- `GIVEN` le filtre d'aging,
  `WHEN` l'Audit filtre par "> 24 mois",
  `THEN` seules les recommandations dont l'échéance initiale est dépassée de plus de 24 mois sont affichées.

---

### S6.2 — Dashboard Directeur Métier

**En tant que** Directeur Métier,
**Je veux** un tableau de bord affichant uniquement mes recommandations actives,
**Afin d'** identifier rapidement celles qui nécessitent mon action (FR28, FR30).

**Critères d'acceptation :**

- `GIVEN` le DM connecté,
  `WHEN` il consulte son dashboard,
  `THEN` seules les recommandations de sa direction sont affichées (périmètre RBAC strict).

- `GIVEN` le dashboard DM,
  `WHEN` une recommandation est en `PENDING_DM_REVIEW`,
  `THEN` elle apparaît dans une section "Action requise" avec un badge prioritaire.

- `GIVEN` une recommandation `OVERDUE`,
  `WHEN` elle est affichée,
  `THEN` une pastille rouge "RETARD" est visible sans avoir à ouvrir la fiche.

---

### S6.3 — To-Do List ETP

**En tant que** Employé Traitant,
**Je veux** une liste de tâches claire affichant uniquement mes recommandations assignées,
**Afin de** savoir exactement ce que j'ai à faire aujourd'hui (FR28, FR30).

**Critères d'acceptation :**

- `GIVEN` l'ETP connecté,
  `WHEN` il consulte sa to-do list,
  `THEN` seules les recommandations qui lui sont explicitement délégués (`assigned_etp_id=etp.id`) sont affichées.

- `GIVEN` la to-do list,
  `WHEN` l'ETP voit une reco,
  `THEN` un indicateur visuel de priorité (🔴 Critique / 🟠 Haute / 🟢 Normale) est affiché (NFR FR30).

- `GIVEN` une reco `OVERDUE` dans la to-do list,
  `WHEN` l'ETP la voit,
  `THEN` un badge "⚠️ EN RETARD" est affiché à côté de l'indicateur de priorité.

---

### `[simplifié]` S6.4 — Dashboard Direction Générale (vue filtrée par direction + PDF)

**En tant que** Directeur Général,
**Je veux** une vue de supervision filtrée par direction avec possibilité de télécharger un rapport PDF par direction,
**Afin de** suivre l'avancement par direction et préparer les Comités de Direction (FR28, FR31).

> **Simplifié v1 :** Le Dashboard DG est une copie du Dashboard Audit avec un filtre direction obligatoire. Le DG peut sélectionner une direction et télécharger un rapport PDF de synthèse pour cette direction (`@media print`). Les statistiques globales agrégées (HTMX partiel) sont reportées en v2.

**Critères d'acceptation :**

- `GIVEN` le DG connecté,
  `WHEN` il consulte son dashboard,
  `THEN` il voit la liste paginée de toutes les recommandations (même vue que l'Audit) avec un sélecteur de direction en haut de page.

- `GIVEN` le DG qui sélectionne une direction dans le filtre,
  `WHEN` le formulaire est soumis,
  `THEN` la liste se recharge en affichant uniquement les recommandations de la direction sélectionnée.

- `GIVEN` le DG qui a filtré par direction,
  `WHEN` il clique "Télécharger rapport PDF",
  `THEN` une page `@media print` s'active avec : en-tête BICEC/Sentinel, nom de la direction, liste des recos avec statuts et priorités, date du rapport.

- `GIVEN` le dashboard DG,
  `WHEN` le DG sélectionne une recommandation et clique sur "Voir détails",
  `THEN` il est redirigé vers la fiche complète (lecture seule pour le DG).

---

### `[simplifié]` S6.5 — Filtres serveur (HTMX dynamique reporté en v2)

> **Simplifié.** Économie : 4 points. Les filtres fonctionnent avec soumission de formulaire classique (rechargement complet de la liste). Le filtrage HTMX partiel sans rechargement de page est reporté en v2.

**En tant que** utilisateur avec accès au dashboard,
**Je veux** filtrer les recommandations selon plusieurs critères,
**Afin de** trouver rapidement les dossiers pertinents (FR29).

**Critères d'acceptation :**

- `GIVEN` les filtres du dashboard (source, priorité, statut, aging, OVERDUE),
  `WHEN` l'utilisateur modifie un filtre,
  `THEN` HTMX envoie une requête `GET` avec les paramètres et met à jour uniquement le tableau de résultats (pas le header, pas la navigation).

- `GIVEN` des filtres combinés (ex: `source=COBAC` ET `priorité=CRITIQUE` ET `is_overdue=True`),
  `WHEN` ils sont appliqués simultanément,
  `THEN` les résultats correspondent exactement à l'intersection des critères.

- `GIVEN` des filtres actifs,
  `WHEN` l'utilisateur clique "Réinitialiser les filtres",
  `THEN` tous les filtres sont vidés et la liste complète est affichée.

---

### S6.6 — Rapport de Synthèse Statistique (UC15 — Auditeur Interne)

**En tant que** Auditeur Interne,
**Je veux** générer un rapport de synthèse statistique de l'avancement du plan d'audit,
**Afin de** préparer les présentations aux Comités de Direction et aux inspecteurs COBAC (UC15).

**Critères d'acceptation :**

- `GIVEN` la section "Rapports" dans la navigation Audit,
  `WHEN` l'Audit accède à la vue rapport,
  `THEN` un tableau statistique s'affiche : nbre de recos par statut / par source / par priorité / par direction.

- `GIVEN` le tableau statistique,
  `WHEN` l'Audit applique un filtre (ex: période entre deux dates),
  `THEN` les statistiques sont recalculées dynamiquement (HTMX).

- `GIVEN` le rapport affiché,
  `WHEN` l'Audit clique "Imprimer / Exporter PDF",
  `THEN` la feuille CSS `@media print` s'active, masquant la navigation et les filtres pour n'imprimer que le contenu utile.

---

### `[fusionné]` ~~S6.7 — Rapport de Synthèse DG séparé~~

> **Fusionné dans S6.4 (Dashboard DG).** La fonctionnalité de rapport PDF par direction est intégrée directement dans le Dashboard DG simplifié (S6.4 ci-dessus). Un rapport DG exécutif agrégé (taux de conformité global, top 5 directions en retard) est reporté en v2.

---

### S6.8 — Indicateurs visuels de priorité et statut (Code couleur)

**En tant que** DM ou ETP,
**Je veux** identifier visuellement l'urgence d'une recommandation sans ouvrir la fiche,
**Afin de** prioriser mes actions instantanément (FR30).

**Critères d'acceptation :**

- `GIVEN` une recommandation `CRITIQUE`,
  `WHEN` elle est affichée dans une liste,
  `THEN` un badge rouge 🔴 ou une bordure colorée signale son urgence.

- `GIVEN` une recommandation `HAUTE`,
  `WHEN` elle est affichée,
  `THEN` un badge orange 🟠 est visible.

- `GIVEN` une recommandation `MOYENNE` ou `FAIBLE`,
  `WHEN` elle est affichée,
  `THEN` un badge vert 🟢 est visible.

- `GIVEN` une recommandation avec le flag `is_overdue=True`,
  `WHEN` elle est affichée,
  `THEN` un badge supplémentaire "⚠️ EN RETARD" est affiché, indépendamment de la priorité.

---

## E7 — Notifications & Scheduler (Django-Q2)

> **Objectif :** Mettre en place le moteur de relance automatique nocturne, les alertes OVERDUE et les notifications in-app.
>
> **Prérequis :** E2 terminé.
> **FR couvertes :** FR21, FR22, FR23.

---

### S7.1 — Modèles `Notification` et `Digest`

**En tant que** développeur,
**Je veux** des modèles `Notification` et `Digest` pour gérer le cycle de vie des envois,
**Afin de** tracer chaque tentative d'envoi et permettre la relance automatique en cas d'échec.

**Critères d'acceptation :**

- `GIVEN` une nouvelle assignation DM,
  `WHEN` la transition est effectuée,
  `THEN` une `Notification(type='ASSIGNMENT', send_status='PENDING', channel='EMAIL')` est créée.

- `GIVEN` une `Notification(send_status='PENDING')`,
  `WHEN` l'envoi échoue (SMTP indisponible),
  `THEN` `send_status='FAILED'`, `retry_count` est incrémenté, et `error_message` contient le détail de l'erreur.

- `GIVEN` une `Notification(retry_count >= 3)`,
  `WHEN` la tâche de relance vérifie,
  `THEN` elle n'est plus tentée (abandon après 3 échecs).

---

### S7.2 — Tâche `cron_check_overdue()` (Détection OVERDUE nocturne)

**En tant que** scheduler Django-Q2,
**Je veux** détecter automatiquement chaque nuit les recommandations dont l'échéance est dépassée,
**Afin de** mettre à jour le flag `is_overdue` et déclencher les alertes (FR21).

**Critères d'acceptation :**

- `GIVEN` une reco avec `due_date < aujourd'hui` et `is_overdue=False`,
  `WHEN` la tâche `cron_check_overdue()` s'exécute,
  `THEN` `is_overdue` passe à `True` et une entrée `AuditLog(action='SYSTEM')` est créée.

- `GIVEN` une reco `CLOSED_RESOLVED` avec `due_date < aujourd'hui`,
  `WHEN` la tâche s'exécute,
  `THEN` le flag `is_overdue` n'est **pas** mis à jour (les recos clôturées sont exclues).

- `GIVEN` une reco passée en `is_overdue=True` lors du dernier cycle,
  `WHEN` la tâche s'exécute à nouveau le lendemain,
  `THEN` elle n'est pas retraitée (idempotence — pas de doublon d'AuditLog).

---

### S7.3 — Tâche `cron_send_consolidated_notifications()` (Digest email)

**En tant que** scheduler Django-Q2,
**Je veux** envoyer chaque nuit un seul email consolidé par utilisateur listant ses recommandations en retard,
**Afin d'** éviter la fatigue de notification et garantir la compatibilité Outlook (FR23).

**Critères d'acceptation :**

- `GIVEN` un DM avec 3 recos `OVERDUE`,
  `WHEN` la tâche `cron_send_consolidated_notifications()` s'exécute,
  `THEN` un **seul email** est envoyé au DM listant les 3 recos groupées par priorité (CRITIQUE en premier).

- `GIVEN` un utilisateur sans reco `OVERDUE`,
  `WHEN` la tâche s'exécute,
  `THEN` aucun email n'est envoyé pour cet utilisateur.

- `GIVEN` l'email envoyé,
  `WHEN` j'inspecte son format HTML,
  `THEN` il est compatible Outlook (pas de flexbox complexe, mise en page par tableaux HTML).

- `GIVEN` une tâche qui s'exécute deux fois le même jour (incident),
  `WHEN` le second run est lancé,
  `THEN` les utilisateurs ne reçoivent pas de doublon (vérification idempotence via `Digest` en BDD).

---

### S7.4 — Tâche `cron_proactive_alerts()` (Alerte J-7)

**En tant que** scheduler Django-Q2,
**Je veux** envoyer une alerte proactive aux ETP et DM dont une échéance approche dans 7 jours,
**Afin de** anticiper les retards avant qu'ils ne se produisent (FR23).

**Critères d'acceptation :**

- `GIVEN` une reco avec `due_date = aujourd'hui + 7 jours` et `is_overdue=False`,
  `WHEN` la tâche `cron_proactive_alerts()` s'exécute,
  `THEN` une `Notification(type='PROACTIVE_J7')` est créée et l'ETP/DM reçoit un email d'alerte.

- `GIVEN` la même reco le lendemain (J-6),
  `WHEN` la tâche s'exécute,
  `THEN` aucune nouvelle alerte J-7 n'est envoyée (une seule alerte J-7 par recommandation).

---

### S7.5 — Template email HTML (Digest consolidé)

**En tant que** utilisateur recevant un email de relance,
**Je veux** un email clair, lisible et actionnable,
**Afin de** savoir exactement quelles recommandations nécessitent mon attention.

**Critères d'acceptation :**

- `GIVEN` le template email,
  `WHEN` il est rendu dans Outlook,
  `THEN` la mise en page est correcte (pas de CSS flotté mal rendu) et les liens cliquables mènent vers les fiches Sentinel.

- `GIVEN` l'email,
  `WHEN` je l'inspecte,
  `THEN` il affiche : en-tête BICEC/Sentinel, liste des recos par priorité (CRITIQUE en rouge, HAUTE en orange), lien direct vers chaque fiche, footer avec lien de gestion de préférences.

---

### S7.6 — Heartbeat Scheduler et alerte RSSI

**En tant que** RSSI,
**Je veux** être alerté si le scheduler Django-Q2 ne s'est pas exécuté depuis plus de 25 heures,
**Afin de** détecter une panne du worker et intervenir avant que des recos OVERDUE soient manquées.

**Critères d'acceptation :**

- `GIVEN` le scheduler Django-Q2 opérationnel,
  `WHEN` chaque task nocturne s'exécute,
  `THEN` un `HeartbeatRecord(timestamp=now())` est mis à jour en base.

- `GIVEN` le heartbeat checker (tâche CRON OS externe à Django-Q2),
  `WHEN` il détecte que `now() - last_heartbeat > 25h`,
  `THEN` un email d'alerte critique est envoyé à l'adresse RSSI configurée dans `SiteConfiguration`.

---

### S7.7 — Notifications in-app (Badge non-lu)

**En tant que** utilisateur Sentinel,
**Je veux** être notifié dans l'interface d'une action qui me concerne,
**Afin de** ne pas dépendre uniquement de l'email pour rester informé.

**Critères d'acceptation :**

- `GIVEN` une notification `IN_APP` non lue,
  `WHEN` l'utilisateur consulte n'importe quelle page,
  `THEN` un badge numérique rouge s'affiche sur l'icône de cloche dans la navigation.

- `GIVEN` l'utilisateur qui clique sur la cloche,
  `WHEN` la liste des notifications s'ouvre (via HTMX),
  `THEN` les notifications non lues sont listées avec : type, recommandation concernée, date. Après lecture, `is_read=True`.

---

## E8 — Audit Externe & Conformité COBAC

> **Objectif :** Ouvrir un accès cloisonné aux inspecteurs COBAC, BEAC, CAC et NIF pour consultation et téléchargement de preuves.
>
> **Prérequis :** E4 terminé.
> **FR couvertes :** FR2, FR26.
> **NFR couvertes :** NFR-PERF-04 (ZIP < 5s), NFR-SCA-01.

---

### S8.1 — Modèle `ExternalMission` (périmètre et accès)

**En tant que** développeur,
**Je veux** un modèle `ExternalMission` liant un auditeur externe à un périmètre de recommandations,
**Afin de** contrôler précisément ce qu'un inspecteur externe peut lire.

**Critères d'acceptation :**

- `GIVEN` une `ExternalMission` créée par l'Audit,
  `WHEN` j'inspecte le modèle,
  `THEN` il contient : `auditor_id` (FK vers User EXTERNE), `organization` (COBAC/BEAC...), `scope_description`, `start_date`, `end_date`, `is_active`, et un M2M vers `workflow_recommendation`.

- `GIVEN` une mission expirée (`end_date < aujourd'hui`),
  `WHEN` l'auditeur externe tente de se connecter,
  `THEN` l'accès est refusé : "Votre mission est terminée. Contactez l'Audit Interne."

- `GIVEN` une `ExternalMission` inactive (`is_active=False`),
  `WHEN` l'auditeur externe tente d'accéder à une recommandation de cette mission,
  `THEN` le RBAC retourne `403 Forbidden`.

---

### S8.2 — Vue liste Read-Only (périmètre mission)

**En tant que** Auditeur Externe (COBAC / BEAC / CAC),
**Je veux** consulter les recommandations de mon périmètre de mission,
**Afin de** vérifier l'avancement des actions correctives de la BICEC (FR2).

**Critères d'acceptation :**

- `GIVEN` un auditeur externe connecté,
  `WHEN` il consulte sa liste de recommandations,
  `THEN` seules les recos incluses dans sa mission `ExternalMission` sont affichées (périmètre strict).

- `GIVEN` la liste des recommandations de l'Externe,
  `WHEN` il l'inspecte,
  `THEN` le flag `OVERDUE` n'est **pas** visible (masqué pour les Externes selon les Use Cases validés).

- `GIVEN` la vue liste,
  `WHEN` l'Externe tente d'effectuer une action de mutation (POST, PUT, DELETE),
  `THEN` le RBAC bloque toute action : l'Externe est en lecture seule.

- `GIVEN` la liste,
  `WHEN` l'Externe filtre par période,
  `THEN` les recos créées entre les deux dates sont affichées.

---

### S8.3 — Export ZIP par recommandation (preuves + fiche synthèse)

**En tant que** Auditeur Externe,
**Je veux** télécharger un archive ZIP contenant les preuves validées d'une recommandation et une fiche de synthèse,
**Afin de** disposer d'un dossier complet hors-connexion pour mon rapport d'inspection (FR26).

**Critères d'acceptation :**

- `GIVEN` l'Externe clique "Télécharger l'archive ZIP" sur une reco `CLOSED_RESOLVED`,
  `WHEN` la requête est traitée,
  `THEN` le ZIP est généré en < 5 secondes (NFR-PERF-04) et le téléchargement démarre.

- `GIVEN` le ZIP téléchargé,
  `WHEN` je l'ouvre,
  `THEN` il contient : tous les fichiers de preuves `ACCEPTED` avec leur nom original, une `fiche_synthese.pdf` (titre, dates, sceau HMAC, statut).

- `GIVEN` le téléchargement du ZIP,
  `WHEN` l'opération est complète,
  `THEN` une entrée `AuditLog(action='EXPORT', user=externe, object_id=reco_id)` est créée.

- `GIVEN` une reco dont les preuves totalisent 80 Mo dans le ZIP,
  `WHEN` l'Externe lance le téléchargement,
  `THEN` le ZIP est streamé via `io.BytesIO` (pas chargé intégralement en mémoire) pour éviter la saturation du serveur.

---

### S8.4 — Vérification du sceau HMAC en temps réel

**En tant que** Auditeur Externe,
**Je veux** vérifier l'intégrité cryptographique d'une recommandation clôturée,
**Afin de** m'assurer qu'aucune donnée n'a été altérée depuis la clôture officielle.

**Critères d'acceptation :**

- `GIVEN` une reco `CLOSED_RESOLVED` avec un `HmacSeal` stocké,
  `WHEN` l'Externe consulte la fiche,
  `THEN` le système recalcule le hash et affiche une pastille verte "✓ Intégrité cryptographique confirmée".

- `GIVEN` qu'un fichier de preuve a été remplacé sur le disque après clôture,
  `WHEN` l'Externe consulte la fiche,
  `THEN` le hash recalculé diffère du hash stocké et une pastille rouge "⚠️ Données potentiellement corrompues" s'affiche.

---

### S8.5 — Création de compte Auditeur Externe par l'Audit

**En tant que** Auditeur Interne,
**Je veux** créer un compte local pour un inspecteur externe et définir son périmètre de mission,
**Afin de** lui donner un accès temporaire et cloisonné à Sentinel (FR2).

**Critères d'acceptation :**

- `GIVEN` l'Audit accède au formulaire de création de mission externe,
  `WHEN` il remplit : organisme, dates de mission, périmètre (liste de recommandations), et soumet,
  `THEN` un compte `User(role='EXTERNE', is_active=True)` et une `ExternalMission(is_active=True)` sont créés simultanément.

- `GIVEN` le compte Externe créé,
  `WHEN` la date `end_date` est atteinte,
  `THEN` une tâche Django-Q2 bascule automatiquement `ExternalMission.is_active=False`.

---

## Récapitulatif Final — Couverture des Exigences (MVP Fast-Track v1)

| Epic | Stories MVP | FR couvertes v1 | NFR couvertes | Notes |
|---|---|---|---|---|
| **E0 — Infra** | S0.1–S0.5 | — | SEC-01, REL-02, REL-03 | ✅ Complet |
| **E1 — Auth & Admin** | S1.1–S1.5, S1.7–S1.13 | FR1, FR3, FR4 | SEC-02, PERF-01 | ⚠️ S1.6 RLS → v2 |
| **E2 — Recommandations** | S2.1–S2.5, S2.7 | FR5, FR6, FR10, FR11, FR12 | PERF-02 | ⚠️ S2.6 Bulk → v2 |
| **E3 — Preuves** | S3.1–S3.7 | FR15, FR16, FR18, FR19, FR25 | SEC-04, SCA-01 | ⚠️ S3.8 UI → v2 (données OK) |
| **E4 — Validation** | S4.1–S4.8 | FR17, FR20, FR24, FR27 | SEC-03, PERF-03 | ✅ Complet |
| **`[v2]` E5 — Reports** | ~~S5.1–S5.4~~ | ~~FR13, FR14~~ | — | 🔴 Reporté v2 — Admin Django |
| **E6 — Dashboards** | S6.1–S6.4, S6.6, S6.8 | FR28, FR29, FR30, FR31 | PERF-02 | ⚠️ S6.5 filtres simplifiés · S6.7 fusionné |
| **E7 — Notifications** | S7.1–S7.7 | FR21, FR22, FR23 | — | ✅ Complet |
| **E8 — Externe COBAC** | S8.1–S8.5 | FR2, FR26 | PERF-04, SCA-01 | ✅ Complet |
| **`[v2]` E9 — Import UI** | ~~S9.1–S9.4~~ | ~~FR8, FR9~~ | — | 🔴 Reporté v2 — management command |
| **Total MVP** | **~50 Stories actives** | **27 FR actives** | **10 NFR** | |

> [!IMPORTANT]
> **FR reportées en v2 :** FR8 et FR9 (Import Self-Service) · FR13 et FR14 (Demandes de Report)
> Ces 4 FR seront couvertes dans la version v2 post Go-Live, avec les solutions de contournement suivantes :
> - FR8/FR9 : Import SQL via `manage.py import_history` au moment du Go-Live
> - FR13/FR14 : Modification manuelle de `due_date` par l'Audit via Admin Django

> [!NOTE]
> **NFR non couvertes en v1 :** NFR-REL-01 (RLS PostgreSQL) est reportée en v2. Le middleware RBAC (S1.5) assure l'isolation des données au niveau applicatif.

