# =============================================================================
# TradeFlow Colón — Dockerfile (deploy determinista en Railway)
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg2-binary ships prebuilt wheels — no build-essential / libpq-dev / gcc.
RUN apt-get update \
    && rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* \
    && apt-get clean

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# collectstatic en build (vars inline — no persistir SECRET_KEY en la imagen final).
RUN SECRET_KEY=collectstatic-build-only-not-for-runtime \
    DEBUG=false \
    ALLOWED_HOSTS=localhost,127.0.0.1 \
    python manage.py collectstatic --noinput

RUN chmod +x scripts/docker-entrypoint.sh

EXPOSE 8080

CMD ["/bin/sh", "scripts/docker-entrypoint.sh"]
