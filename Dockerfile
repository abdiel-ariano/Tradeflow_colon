# =============================================================================
# TradeFlow Colón — Dockerfile (deploy determinista en Railway)
# =============================================================================
# Se usa un Dockerfile a propósito: Railway/Nixpacks autodetectaba Deno/Node por
# los archivos .ts (Edge Function de Supabase, frontend Vite) y no instalaba
# Python -> "pip/python: command not found". Con un Dockerfile no hay
# autodetección de provider: Python y pip están siempre disponibles.
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias de sistema para compilar wheels que lo necesiten.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias primero (mejor cache de capas).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copiar el resto del proyecto.
COPY . .

# collectstatic en BUILD (no necesita base de datos). SECRET_KEY dummy solo para
# poder cargar settings; las variables reales llegan en runtime. Así el arranque
# del contenedor es rápido (solo migrate + gunicorn) y el puerto abre enseguida.
RUN SECRET_KEY=build-only-not-a-secret DEBUG=False python manage.py collectstatic --noinput

EXPOSE 8080

# Runtime: migrate + gunicorn (con logs a stdout/stderr para verlos en Railway).
# $PORT lo provee Railway.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn tradeflow_colon.wsgi --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info"]
