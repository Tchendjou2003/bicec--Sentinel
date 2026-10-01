"""
Sentinel — Test Settings

Choix de base de données : SQLite In-Memory
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Avantage : démarrage instantané (0 ms vs 2-5 s pour PostgreSQL Éphémère Docker),
           exécution de la suite de tests complète en quelques secondes.

CONTRAINTE CONNUE (à respecter impérativement) :
SQLite ne simule pas fidèlement le comportement de PostgreSQL 16 de production
sur les points suivants :
  - MVCC (Multi-Version Concurrency Control) : SQLite verrouille la BDD entière,
    PG verrouille au niveau de la ligne. Les tests de concurrence ne sont pas valides
    sur SQLite.
  - Transactions atomiques imbriquées (import_excel.py) : le comportement
    real de commit/rollback sur PostgreSQL doit être validé manuellement
    sur l'environnement de Staging (Recette).
  - Index partiels : SQLite les ignore, PostgreSQL les exploite.

Règle : Tout test validant le comportement TRANSACTIONNEL ou de CONCURRENCE
de l'import historique (Story 6.8) doit être exécuté en Staging sous vrai
PostgreSQL, et non dans cette suite de tests automatisée.
"""
from .base import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ── Django-Q2 : exécution synchrone obligatoire en tests ─────────────────────
# FAILLE CORRIGÉE : Sans ce paramètre, un appel à async_task() dans un service
# déclenche une tâche dans un processus worker séparé qui n'existe PAS pendant
# l'exécution des tests. Le test échoue silencieusement ou "pend" indéfiniment.
# Avec sync=True, la tâche s'exécute immédiatement dans le même thread de test,
# ce qui permet de vérifier son résultat directement après l'appel au service.
# Ref. Vigilance B — Critique architecture du 2026-07-12.
Q_CLUSTER = {**Q_CLUSTER, "sync": True}  # noqa: F405

# ── E-mail (Story 4.3) ───────────────────────────────────────────────────────
# Backend en mémoire : les envois atterrissent dans django.core.mail.outbox.
# Flag forcé à True pour que la chaîne complète (whitelist → tâche → envoi)
# soit couverte par les tests, alors que le défaut de prod reste False.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_NOTIFICATIONS_ENABLED = True

# ── Axes ─────────────────────────────────────────────────────────────────────
# Désactivé pour les tests (évite les conflits de reset entre cas de test)
AXES_ENABLED = False

# ── Sécurité : hasher rapide pour les tests ───────────────────────────────────
# MD5 est volontairement utilisé ICI UNIQUEMENT pour accélérer la création
# de fixtures utilisateurs dans les tests. Il est strictement interdit en
# production (qui utilise Argon2 via base.py).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ── WhiteNoise : désactivé pour les tests ────────────────────────────────────
# Évite l'erreur "Missing staticfiles manifest entry" sans collectstatic préalable.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
