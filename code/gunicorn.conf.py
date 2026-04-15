# Gunicorn Configuration — Sentinel (ADR-02)
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", 4))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 10))
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
