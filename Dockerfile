# =============================================================================
# TradeFlow Colón — Dockerfile (deploy determinista en Railway)
# =============================================================================
# Railway/Nixpacks autodetectaba Deno/Node por .ts (Supabase, Vite) y no instalaba
# Python. Con Dockerfile el stack es siempre Python 3.12 + pip.
#
# collectstatic en BUILD (no en cada arranque) → gunicorn escucha $PORT antes del
# timeout del proxy (~15s) y desaparece el 502 "Application failed to respond".
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Valores dummy solo para collectstatic en build (no se usan en runtime).
ENV SECRET_KEY=collectstatic-build-only-not-for-runtime \
    DEBUG=false \
    ALLOWED_HOSTS=localhost,127.0.0.1
RUN python manage.py collectstatic --noinput

RUN chmod +x scripts/docker-entrypoint.sh

EXPOSE 8080

CMD ["/bin/sh", "scripts/docker-entrypoint.sh"]
