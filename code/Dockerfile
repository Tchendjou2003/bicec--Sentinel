# ============================================
# Sentinel — Dockerfile (Multi-stage)
# ============================================

# ---------- Stage 1: Builder ----------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefix=/install -r requirements/prod.txt

# ---------- Stage 2: Production ----------
FROM python:3.12-slim AS production

# Security: run as non-root
RUN groupadd -r sentinel && useradd -r -g sentinel sentinel

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

# Copy project files
COPY manage.py .
COPY config/ config/
COPY apps/ apps/
COPY templates/ templates/
COPY static/ static/
COPY tests/ tests/
COPY entrypoint.sh .
COPY gunicorn.conf.py .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create media & staticfiles directories
RUN mkdir -p /app/media /app/staticfiles && \
    chown -R sentinel:sentinel /app

USER sentinel

# H3 fix: ensure entrypoint (migrate, collectstatic) uses prod settings
ENV DJANGO_SETTINGS_MODULE=config.settings.prod

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
