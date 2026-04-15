"""
Sentinel — Development Settings
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# En dev, ne pas bloquer sur les clés par défaut
SESSION_COOKIE_SECURE = False

# Debug toolbar (optionnel)
try:
    import debug_toolbar  # noqa: F401
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass
