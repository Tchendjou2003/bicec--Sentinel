"""
Sentinel — Test Settings
Utilise SQLite pour les tests locaux (plus rapide, pas besoin de PostgreSQL).
"""
from .base import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Désactuer Axes pour les tests (évite les problèmes de reset)
AXES_ENABLED = False

# Password hasher rapide pour les tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Désactiver WhiteNoise ManifestStaticFilesStorage pour les tests
# (évite l'erreur "Missing staticfiles manifest entry" sans collectstatic préalable)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
