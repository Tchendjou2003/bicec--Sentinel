# Story 1.1: Setup du Projet depuis le Starter Template

Status: done

## Story

As a **Tech Lead**,
I want **initialiser le projet Sentinel à partir du Starter Template (Django, PostgreSQL, base Tailwind/HTMX)**,
so that **les développeurs puissent commencer à produire de la valeur sur les briques d'authentification et RBAC.**

## Acceptance Criteria (AC)

### AC-1 : Docker Compose démarre sans erreur
**Given** un dépôt Git vierge et le document d'architecture,
**When** je lance `docker compose up --build`,
**Then** les 4 services (`nginx`, `web`, `worker`, `db`) démarrent sans erreur et restent stables pendant 60 secondes.

### AC-2 : PostgreSQL est prêt
**Given** le service `db` en état healthy,
**When** je me connecte via `psql` ou Django shell,
**Then** la base de données `sentinel` est créée et prête à recevoir les premières migrations.

### AC-3 : Page d'accueil Django accessible
**Given** les services `nginx` et `web` en état running,
**When** j'accède à `http://localhost:8080/` dans un navigateur,
**Then** une page d'accueil Django valide (template `base.html`) s'affiche sans erreur 500.
**And** le header `X-Frame-Options` est présent (sécurité de base).

### AC-4 : Tailwind CSS compile correctement
**Given** le fichier `tailwind.config.js` configuré avec les tokens BICEC,
**When** le build CSS s'exécute (`npx tailwindcss`),
**Then** un fichier CSS minifié est généré dans `static/css/output.css`.
**And** les classes utilitaires Tailwind fonctionnent dans le template.

### AC-5 : HTMX et Alpine.js chargés
**Given** la page d'accueil chargée,
**When** j'inspecte le DOM,
**Then** les scripts `htmx.min.js` et `alpine.min.js` sont présents et fonctionnels.
**And** un attribut `hx-get` de test retourne un fragment HTML sans rechargement de page.

### AC-6 : Django-Q2 Worker actif
**Given** le service `worker` en état running,
**When** je consulte l'admin Django `/admin/django_q/`,
**Then** le cluster Q2 est visible et le scheduler heartbeat est actif.

### AC-7 (Erreur) : Variables d'environnement manquantes
**Given** un fichier `.env` incomplet (ex: `SECRET_KEY` manquante),
**When** je lance `docker compose up`,
**Then** le service `web` refuse de démarrer avec un message d'erreur explicite identifiant la variable manquante.

### AC-8 (Erreur) : PostgreSQL indisponible
**Given** le service `db` arrêté manuellement,
**When** le service `web` tente de démarrer,
**Then** il attend le healthcheck `db` (via `depends_on: condition: service_healthy`) et ne crashe pas silencieusement.

## Tasks / Subtasks

- [x] **Task 1 — Initialisation du dépôt** (AC: #1, #7)
  - [x] 1.1 Créer la structure de dossiers Django (HackSoft convention)
  - [x] 1.2 Créer le fichier `.env.example` avec toutes les variables requises
  - [x] 1.3 Créer le `Dockerfile` multi-stage (builder + production)
  - [x] 1.4 Créer le `docker-compose.yml` avec 4 services
  - [x] 1.5 Créer le script d'entrypoint (`entrypoint.sh`) avec `collectstatic` + `migrate`
  - [x] 1.6 Configurer `settings.py` avec lecture `.env` et validation des variables critiques

- [x] **Task 2 — Configuration PostgreSQL** (AC: #2, #8)
  - [x] 2.1 Configurer le service `db` avec healthcheck `pg_isready`
  - [x] 2.2 Configurer `DATABASES` dans `settings.py` (read from env)
  - [x] 2.3 Créer la migration initiale (`python manage.py migrate`)
  - [x] 2.4 Configurer `CONN_MAX_AGE = 60` (ADR-02)

- [x] **Task 3 — Configuration Frontend** (AC: #3, #4, #5)
  - [x] 3.1 Créer `base.html` avec les meta tags SEO de base
  - [x] 3.2 Installer et configurer `tailwind.config.js` avec tokens BICEC
  - [x] 3.3 Copier `htmx.min.js` et `alpine.min.js` en local (On-Premise, pas de CDN)
  - [x] 3.4 Configurer `django-htmx` middleware
  - [x] 3.5 Créer `nginx.conf` avec bloc `location /media/ { deny all; }` (ADR-02)
  - [x] 3.6 Configurer le service `nginx` pour TLS-ready (volumes pour certificats)
  - [x] 3.7 Confirmer un test `hx-get` basique sur la page d'accueil

- [x] **Task 4 — Configuration Django-Q2** (AC: #6)
  - [x] 4.1 Ajouter `django_q` à `INSTALLED_APPS`
  - [x] 4.2 Configurer `Q_CLUSTER` dans `settings.py` (ORM broker, polling 10s, timeout 60s, retry 120s)
  - [x] 4.3 Configurer le service `worker` dans `docker-compose.yml` (`python manage.py qcluster`)

- [x] **Task 5 — Vérification et documentation** (AC: tous)
  - [x] 5.1 Tester `docker compose up --build` complet
  - [x] 5.2 Vérifier l'accès à la page d'accueil
  - [x] 5.3 Vérifier le healthcheck PostgreSQL
  - [x] 5.4 Documenter les commandes de démarrage dans `README.md`

## Dev Notes

### Architecture Critique — À Respecter Impérativement

#### Stack Technique Exacte (ADR/Architecture v2)

| Composant | Version Exacte | Package PyPI |
|-----------|---------------|--------------|
| Python | 3.12+ | — |
| Django | **5.2 LTS** (latest: 5.2.13) | `Django==5.2.13` |
| PostgreSQL | **16** | — (Docker image) |
| HTMX | Latest stable | Fichier JS local (pas de CDN) |
| Alpine.js | Latest stable | Fichier JS local (pas de CDN) |
| Tailwind CSS | Latest v3/v4 | Node dev dependency |
| django-fsm | **4.2.4** | `django-fsm-2==4.2.4` |
| django-htmx | **1.27.0** | `django-htmx==1.27.0` |
| django-widget-tweaks | **1.5.1** | `django-widget-tweaks==1.5.1` |
| django-axes | **8.3.1** | `django-axes==8.3.1` |
| Django-Q2 | Latest stable | `django-q2` |
| Gunicorn | Latest stable | `gunicorn` (mode `gthread`) |
| Nginx | Stable | Docker image `nginx:stable` |

> ⚠️ **ATTENTION:** Le package `django-fsm` original est inactif. Utiliser **`django-fsm-2`** (v4.2.4, actif mars 2026).

#### Convention de Code — HackSoft Style

L'architecture impose strictement la séparation HackSoft :
- **Models** : Structure de données (colonnes)
- **Selectors** : Requêtes de lecture (`get_*`, `list_*`, `filter_*`)
- **Services** : Logique métier d'écriture (`create_*`, `update_*`, `delete_*`)
- **Views** : Interface HTTP (reçoit requête, renvoie HTML)

[Source: architecture-v2.md §0.3, §3.3]

#### Docker Compose — 4 Services Obligatoires (ADR-09)

```yaml
services:
  nginx:   # Reverse proxy TLS + static files
  web:     # Django/Gunicorn (gthread: 4 workers × 10 threads)
  worker:  # Django-Q2 qcluster
  db:      # PostgreSQL 16
```

**Règles impératives :**
- `restart: unless-stopped` sur tous les services
- Healthcheck `pg_isready` sur `db` + `depends_on: condition: service_healthy` sur `web` et `worker`
- `collectstatic --noinput` dans l'entrypoint du service `web`
- `location /media/ { deny all; return 403; }` dans `nginx.conf` (ADR-02)
- Docker Compose v2 natif (pas de directive `version:` dépréciée)
- Volume partagé pour `static/` entre `web` et `nginx`
- Volume partagé (prévu) pour uploadé `media/` entre `web` et `nginx` (mais bloqué par 403)

[Source: architecture-v2.md ADR-02, ADR-09]

#### Variables d'Environnement Requises

```bash
# .env.example
SECRET_KEY=changeme-generate-with-get-random-secret-key
HMAC_SECRET_KEY=changeme-separate-from-django-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://sentinel:password@db:5432/sentinel
EMAIL_HOST=smtp.bicec.internal
EMAIL_PORT=587
```

> ⚠️ `HMAC_SECRET_KEY` est **totalement distincte** de `SECRET_KEY` Django (ADR-07). Une rotation de `SECRET_KEY` ne doit jamais invalider les sceaux d'audit existants.

#### Gunicorn Configuration (ADR-02)

```python
# gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "gthread"
threads = 10
timeout = 30
```

Avec `CONN_MAX_AGE = 60` dans `settings.py` (éviter l'épuisement du pool PostgreSQL).

#### Nginx Configuration Minimale (ADR-02)

```nginx
server {
    listen 80;
    # TLS sera configuré en production avec certificats IT BICEC
    
    location /static/ {
        alias /app/staticfiles/;
    }
    
    location /media/ {
        deny all;
        return 403;
    }
    
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
        client_max_body_size 15M;
    }
}
```

- `client_max_body_size 15M` aligne avec FR15/NFR-SCA-01 (limite fichier 15 Mo)
- `proxy_read_timeout 30s` pour les exports ZIP (ADR-02)

#### Django Settings Critiques

```python
SESSION_COOKIE_AGE = 1800  # 30 min idle timeout (NFR-SEC-02)
SESSION_SAVE_EVERY_REQUEST = True  # Vrai idle timeout
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True  # En production (TLS)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

# Django-Q2 (ADR-05)
Q_CLUSTER = {
    "name": "sentinel",
    "workers": 1,
    "timeout": 60,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
    "poll": 10,  # Polling 10s (pas 5s par défaut)
}
```

#### Tailwind Config — Tokens BICEC (UX Design Spec)

```javascript
// tailwind.config.js
module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        "bicec-yellow": "#FAB50B",
        "bicec-yellow-dark": "#D89A0A",
        "bicec-blue": "#1A3A5C",
        "bicec-blue-light": "#2B5080",
      },
      fontFamily: {
        sans: ["Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
```

[Source: ux-design-specification.md, Visual Design Foundation]

### Structure de Dossiers Recommandée

```
sentinel/
├── docker-compose.yml        # 4 services (nginx, web, worker, db)
├── Dockerfile                # Multi-stage build
├── .env.example              # Variables d'environnement template
├── entrypoint.sh             # collectstatic + migrate + gunicorn
├── gunicorn.conf.py          # Config Gunicorn gthread
├── requirements/
│   ├── base.txt              # Dépendances communes
│   ├── dev.txt               # Dev tools (debug-toolbar, etc.)
│   └── prod.txt              # Production (gunicorn, etc.)
├── nginx/
│   └── nginx.conf            # Config Nginx (TLS-ready)
├── config/                   # Projet Django principal
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py           # Settings communes
│   │   ├── dev.py            # Override dev
│   │   └── prod.py           # Override production
│   ├── urls.py
│   └── wsgi.py
├── apps/                     # Applications Django métier
│   ├── users/                # Auth, RBAC, Organigramme
│   ├── workflow/             # FSM, Recommandations
│   ├── audit/                # Audit Trail, HMAC, Export
│   ├── notifications/        # Django-Q2 tasks, emails
│   └── dashboards/           # KPIs, filtres, vues DG
├── templates/
│   ├── base.html             # Layout principal (Navbar, Sidebar)
│   └── components/           # Atomic Design partials
├── static/
│   ├── css/
│   │   └── output.css        # Tailwind compilé
│   ├── js/
│   │   ├── htmx.min.js       # LOCAL (pas de CDN)
│   │   └── alpine.min.js     # LOCAL (pas de CDN)
│   └── fonts/                # Roboto, JetBrains Mono
├── media/                    # Uploads preuves (volume Docker)
├── tailwind.config.js
├── package.json              # Node dev dependencies (Tailwind)
└── manage.py
```

[Source: architecture-v2.md §3.3 C4 Level 3, §0.3 HackSoft convention]

### Project Structure Notes

- Alignement avec l'architecture C4 Level 3 (5 apps Django : users, workflow, audit, notifications, dashboards)
- HackSoft convention : chaque app contient `models.py`, `selectors.py`, `services.py`, `views.py`
- Les bibliothèques JS (htmx, alpine) sont servies localement car le système est **On-Premise isolé** (aucune dépendance CDN)
- Node.js est utilisé uniquement en développement pour compiler Tailwind CSS — **Node.js n'est PAS installé en production**

### References

- [Source: architecture-v2.md#§1.7 — Stack Technique](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: architecture-v2.md#ADR-02 — Nginx + Gunicorn](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: architecture-v2.md#ADR-04 — SSR + HTMX](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: architecture-v2.md#ADR-05 — Django-Q2](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: architecture-v2.md#ADR-08 — Tailwind CSS](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: architecture-v2.md#ADR-09 — Docker Compose](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/architecture-v2.md)
- [Source: ux-design-specification.md — Visual Design Foundation](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/ux-design-specification.md)
- [Source: epics.md — Epic 1, Story 1.1](file:///d:/bicec--Sentinel/_bmad-output/planning-artifacts/epics.md)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Flash

### Debug Log References
- Fixed `django-q2` dependency to valid PyPI version `1.9.0`
- Fixed `entrypoint.sh` to correctly inherit command arguments for worker (allowing `python manage.py qcluster` execution)

### Completion Notes List
- ✅ Dockerized architecture created successfully (4 services)
- ✅ Implemented HackSoft convention with 5 Django app stubs
- ✅ Applied strict Nginx media blocking per ADR-02, generated `X-Frame-Options` via Django Middleware
- ✅ Initialized Tailwind CSS with BICEC design tokens
- ✅ Included fully local `alpine.min.js` and `htmx.min.js` for isolated on-premise execution
- ✅ Code review fixes applied: CSRF, {% load static %}, DJANGO_SETTINGS_MODULE, AXES, .dockerignore, DB port, smoke tests

## Senior Developer Review (AI)

**Date:** 2026-04-14
**Outcome:** Approve (after fixes)
**Total Issues:** 3 High, 4 Medium, 3 Low → All HIGH/MEDIUM fixed

### Action Items
- [x] H1: CSRF_COOKIE_HTTPONLY set to False for HTMX compatibility
- [x] H2: {% load static %} moved to top of base.html
- [x] H3: ENV DJANGO_SETTINGS_MODULE=config.settings.prod added to Dockerfile
- [x] M1: .env verified excluded by .gitignore
- [x] M2: PostgreSQL port changed from `ports` to `expose`
- [x] M3: .dockerignore created (excludes node_modules, .git, .env, _bmad)
- [x] M4: ip_address added to AXES_LOCKOUT_PARAMETERS
- [x] L1: Smoke tests created (5 tests, all pass)
- [x] L3: Removed unused os/sys imports from base.py

### File List
- `code/docker-compose.yml` [NEW]
- `code/Dockerfile` [NEW]
- `code/entrypoint.sh` [NEW]
- `code/gunicorn.conf.py` [NEW]
- `code/nginx/nginx.conf` [NEW]
- `code/requirements/base.txt`, `prod.txt`, `dev.txt` [NEW]
- `code/config/settings/base.py`, `dev.py`, `prod.py` [NEW]
- `code/config/urls.py`, `wsgi.py` [NEW]
- `code/apps/` (users, audit, notifications, dashboards, workflow stubs) [NEW]
- `code/static/` (htmx.min.js, alpine.min.js, input.css) [NEW]
- `code/templates/base.html`, `home.html`, `partials/htmx_test.html` [NEW]
- `code/tailwind.config.js`, `package.json` [NEW]

### Change Log

- 2026-04-12: Story created by create-story workflow — ultimate context engine analysis completed
- 2026-04-14: Story implementation complete, architecture instantiated successfully. Moved to review.
- 2026-04-14: Code review completed — 7 issues fixed (3H, 4M). 5 smoke tests added. Status → done.
