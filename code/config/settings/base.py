"""
Sentinel — Base Settings (shared between dev and prod)
Architecture: Django 5.2 LTS + HTMX + Alpine.js + Tailwind CSS
Convention: HackSoft Style (Models / Selectors / Services / Views)
"""
from pathlib import Path

from decouple import config, Csv

# ============================================
# Paths
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ============================================
# Security — Core Keys
# ============================================
SECRET_KEY = config("SECRET_KEY")

# HMAC key — TOTALEMENT séparée de SECRET_KEY (ADR-07)
# Ne JAMAIS utiliser SECRET_KEY pour les sceaux HMAC
HMAC_SECRET_KEY = config("HMAC_SECRET_KEY")

# Validation: refuse de démarrer sans les clés critiques
if not SECRET_KEY or SECRET_KEY == "changeme-generate-with-get-random-secret-key":
    raise ValueError(
        "❌ SECRET_KEY non configurée. Générez-en une avec:\n"
        "python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )

if not HMAC_SECRET_KEY or HMAC_SECRET_KEY == "changeme-generate-separate-hmac-key":
    raise ValueError(
        "❌ HMAC_SECRET_KEY non configurée. Générez-en une avec:\n"
        "python -c \"import secrets; print(secrets.token_hex(32))\""
    )

DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ============================================
# Applications
# ============================================
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "widget_tweaks",
    "django_fsm",
    "axes",
    "django_q",
]

LOCAL_APPS = [
    "apps.ui",
    "apps.users",
    "apps.workflow",
    "apps.audit",
    "apps.notifications",
    "apps.dashboards",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ============================================
# Middleware
# ============================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.users.middleware.IdleTimeoutMiddleware",  # NFR-SEC-02
    "apps.users.middleware.RoleRequiredMiddleware", # ADR-10 / FR37
    "apps.users.middleware.ExternalIsolationMiddleware", # Story 1.3 / AC1+AC3
]

ROOT_URLCONF = "config.urls"

# ============================================
# Templates
# ============================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.users.context_processors.sidebar_context",
                "apps.notifications.context_processors.notifications_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ============================================
# Database — PostgreSQL 16 (ADR-09)
# ============================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="sentinel"),
        "USER": config("POSTGRES_USER", default="sentinel"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="sentinel_dev_password"),
        "HOST": config("POSTGRES_HOST", default="db"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,  # ADR-02: éviter l'épuisement du pool
    }
}

# ============================================
# Authentication — Sessions Django Natives (ADR-06)
# ============================================
AUTH_USER_MODEL = "users.User"
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/auth/login/"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================================
# Sessions — Idle timeout 30 min (NFR-SEC-02)
# ============================================
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Vrai idle timeout (reset à chaque requête)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ============================================
# CSRF — HTTPONLY=False requis pour HTMX (lecture cookie JS)
# ============================================
CSRF_COOKIE_HTTPONLY = False

# ============================================
# Django-Axes — Brute Force Protection (ADR)
# ============================================
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # Heure(s)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "axes/lockout.html"
AXES_NEVER_LOCKOUT_SUPERUSER = True  # Défense en profondeur : le superutilisateur ne peut pas être verrouillé par Axes.

# ============================================
# Security
# ============================================
X_FRAME_OPTIONS = "SAMEORIGIN"

# ============================================
# Provisioning — Groupe d'approbateurs (Story 6.2.0)
# ============================================
# Nom du groupe Django dont les membres peuvent valider (checker)
# les demandes de création de compte (UserProvisioningRequest).
# Ce groupe est créé automatiquement via la migration 0009.
PROVISIONING_APPROVER_GROUP_NAME = "Administrateurs Sentinel"

# ============================================
# Django-Q2 — Task Queue Asynchrone (ADR-05)
# ============================================
Q_CLUSTER = {
    "name": "sentinel",
    "workers": 1,
    "timeout": 300,  # Imports historiques volumineux (500 lignes + ZIP 100 Mo)
    "retry": 360,    # Doit rester > timeout, sinon Django-Q2 retente une tâche en cours
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
    "poll": 10,  # Polling 10s (pas 5s par défaut — batch nocturne)
}

# ============================================
# Internationalization
# ============================================
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

# ============================================
# Static Files (Tailwind CSS compilé)
# ============================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ============================================
# Media Files (Preuves d'audit — Volume Docker)
# ============================================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024  # 6 Mo (FR15/NFR-SCA-01)

# ============================================
# Email — SMTP BICEC (ADR-03, Story 4.3)
# ============================================
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="sentinel@bicec.cm")

# Flag maître du canal e-mail (Story 4.3). False tant que les SMTP BICEC ne sont
# pas fournis : le moteur in-app fonctionne, aucun e-mail ne part, aucune tâche
# n'est enqueuée. La bascule prod se fait uniquement par variables d'environnement.
EMAIL_NOTIFICATIONS_ENABLED = config(
    "EMAIL_NOTIFICATIONS_ENABLED", default=False, cast=bool
)
EMAIL_SUBJECT_PREFIX = "[SENTINEL] "

# Types de notification qui partent aussi par e-mail. Doctrine « alarme
# incendie » assouplie (décision 2026-07-16) : les ruptures rares/haut-signal
# ET deux événements de workflow à forte valeur d'action (assignation, rejet
# de preuves) sont e-mailés ; le reste (J-7/J-3, OVERDUE simple, clôtures…)
# demeure in-app. OVERDUE_J60_ESCALATION est listé par anticipation — le type
# n'est émis nulle part tant que l'escalade J60 (v2) n'est pas implémentée.
EMAIL_NOTIFICATION_TYPES = (
    "TAMPER_ALERT",
    "OVERDUE_J30",
    "OVERDUE_J60_ESCALATION",
    "SYSTEM_ALERT",
    "ASSIGNED",
    "EVIDENCE_REJECTED",
)

# Base des URLs absolues dans les e-mails (les notifications stockent des URLs
# relatives). À pointer vers l'URL interne du serveur Sentinel en production.
SITE_BASE_URL = config("SITE_BASE_URL", default="http://localhost:8000")

# ============================================
# Default primary key
# ============================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================
# Sentry — dev local uniquement
# ============================================
# Ne s'initialise pas si SENTRY_DSN est absent ou si DEBUG=False.
# La double garde garantit qu'aucun event ne part en production,
# même si le DSN est présent dans l'environnement par erreur.
SENTRY_DSN = config("SENTRY_DSN", default="")

# Import résilient : l'absence du paquet (image Docker pas encore reconstruite,
# environnement minimal) ne doit jamais empêcher le démarrage — Sentry est de
# l'observabilité, pas une dépendance métier.
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

if SENTRY_DSN and DEBUG and sentry_sdk is not None:

    def _strip_local_vars(event, hint):
        # Retire les valeurs des variables locales de chaque frame.
        # Garde la stack trace (fichier, ligne, fonction) sans données métier.
        if "exception" in event:
            for exc in event["exception"].get("values", []):
                for frame in exc.get("stacktrace", {}).get("frames", []):
                    frame.pop("vars", None)
        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config("ENVIRONMENT", default="development"),
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_strip_local_vars,
    )
