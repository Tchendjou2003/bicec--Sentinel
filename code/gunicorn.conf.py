# Gunicorn Configuration — Sentinel (ADR-02)
import os
import multiprocessing

bind = "0.0.0.0:8000"
# Calcul recommandé: 2 * num_cores + 1, mais on autorise l'override env
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = 30

# Sécurité & Robustesse en production
graceful_timeout = 30
max_requests = 1000        # Redémarre les workers après 1000 req (évite memory leaks)
max_requests_jitter = 50   # Décalage aléatoire pour éviter un redémarrage simultané
preload_app = True         # Charge l'app en mémoire avant le fork (économise de la RAM)
forwarded_allow_ips = "*"  # Confiance au proxy Nginx devant Gunicorn

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
