"""
Sentinel — Production Settings
"""
from .base import *  # noqa: F401, F403

DEBUG = False

# Sécurité production
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

# HTTPS redirect (géré par Nginx, mais safety net)
SECURE_SSL_REDIRECT = False  # Nginx gère la redirection
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
