#!/bin/bash
set -e

echo "=== Sentinel Entrypoint ==="

# Collect static files (required for Nginx volume sharing)
echo "Collecting static files..."
python manage.py collectstatic --noinput

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
