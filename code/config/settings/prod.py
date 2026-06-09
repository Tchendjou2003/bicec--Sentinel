"""
Sentinel — Production Settings
"""
import os
from .base import *  # noqa: F401, F403

DEBUG = False

# Sécurité production
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

# HSTS (Strict-Transport-Security)
SECURE_HSTS_SECONDS = 31536000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Domaines autorisés (ex: sentinel.intra.bicec.local)
# Le HTTPS est forcé ici pour faire correspondre le referer du front TLS Nginx.
CSRF_TRUSTED_ORIGINS = [
    "https://sentinel.intra.bicec.local",
    "https://localhost",
]

# HTTPS redirect (géré par Nginx, mais safety net)
SECURE_SSL_REDIRECT = False  # Nginx gère la redirection HTTP -> HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Logging JSON Structuré (pour analyse via SIEM/Elasticsearch)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
