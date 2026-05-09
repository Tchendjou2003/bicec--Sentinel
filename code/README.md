# Sentinel — Plateforme de Suivi des Recommandations d'Audit

## Prérequis

- Docker Engine ≥ 24.x
- Docker Compose v2 (natif)
- Node.js ≥ 18.x (développement uniquement, pour Tailwind CSS)

## Démarrage rapide

```bash
# 1. Copier le fichier d'environnement
cp .env.example .env

# 2. Générer une SECRET_KEY Django
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 3. Générer une HMAC_SECRET_KEY séparée
python -c "import secrets; print(secrets.token_hex(32))"

# 4. Mettre à jour .env avec les clés générées

# 5. Construire et lancer
docker compose up --build

# 6. Accéder à l'application
# http://localhost:8080/
```

## Architecture

- **Backend :** Django 5.2 LTS (Python 3.12+)
- **Frontend :** Templates Django SSR + HTMX + Alpine.js
- **CSS :** Tailwind CSS (compilé, pas de Node en production)
- **Base de données :** PostgreSQL 16
- **Task Queue :** Django-Q2 (scheduler nocturne)
- **Reverse Proxy :** Nginx (TLS-ready)
- **Conteneurisation :** Docker Compose (4 services)

## Structure du projet

```
sentinel/
├── config/          # Configuration Django (settings, urls, wsgi)
├── apps/            # Applications métier (users, workflow, audit, ...)
├── templates/       # Templates HTML (base.html, composants)
├── static/          # CSS/JS/Fonts (Tailwind compilé, htmx, alpine)
├── media/           # Uploads preuves (volume Docker)
├── nginx/           # Configuration Nginx
├── requirements/    # Dépendances Python (base, dev, prod)
└── docker-compose.yml
```

## Services Docker

| Service | Port | Rôle |
|---------|------|------|
| `nginx` | 8080 | Reverse proxy, fichiers statiques |
| `web` | 8000 (interne) | Django/Gunicorn |
| `worker` | — | Django-Q2 scheduler |
| `db` | 5432 (interne) | PostgreSQL 16 |

## Licence

Propriétaire — BICEC (Banque Internationale du Cameroun pour l'Épargne et le Crédit)
