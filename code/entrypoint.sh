#!/bin/bash
set -e

echo "=== Sentinel Entrypoint ==="

# Collect static files (required for Nginx volume sharing)
# Le worker ne sert pas de fichiers statiques — seul le container web/nginx en a besoin.
if [ "${SKIP_COLLECTSTATIC:-0}" != "1" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
else
    echo "Skipping collectstatic (SKIP_COLLECTSTATIC=1)"
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

if [ "$#" -eq 0 ]; then
    echo "Starting Gunicorn..."
    exec gunicorn config.wsgi:application -c gunicorn.conf.py
else
    echo "Executing command: $*"
    exec "$@"
fi
