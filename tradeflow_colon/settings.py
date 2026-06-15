"""
=============================================================================
TRADEFLOW COLÓN — settings.py  (Producción-seguro)
=============================================================================
Usa python-decouple para leer variables desde .env en desarrollo
y desde variables de entorno en Railway (producción).

SETUP LOCAL (PyCharm):
  1. pip install -r requirements.txt
  2. Copia .env.example → .env y rellena los valores
  3. python manage.py migrate
  4. python manage.py createsuperuser
  5. python manage.py runserver

DEPLOY RAILWAY:
  git push → Railway lee las variables de entorno del panel
  (Settings → Variables) y despliega automáticamente.
=============================================================================
"""
from pathlib import Path

import dj_database_url
from decouple import Config, Csv, RepositoryEmpty

try:
    from decouple import RepositoryDict
except ImportError:
    class RepositoryDict:  # noqa: D106 — compat decouple antiguo
        def __init__(self, mapping):
            self._data = dict(mapping)

        def __contains__(self, key):
            return key in self._data

        def __getitem__(self, key):
            return self._data[key]

from django.utils.translation import gettext_lazy as _

# ── Rutas ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# .env en la raíz del repo (Windows/PyCharm); en CI sin .env → variables de entorno.
# utf-8-sig: evita que PowerShell Set-Content -Encoding utf8 rompa SECRET_KEY (BOM).


def _parse_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        data[key] = value
    return data


_ENV_FILE = BASE_DIR / '.env'
_env_vars = _parse_dotenv(_ENV_FILE)
config = Config(RepositoryDict(_env_vars)) if _env_vars else Config(RepositoryEmpty())

# ── Seguridad ─────────────────────────────────────────────────────────────
# NUNCA hardcodear esto. Viene del archivo .env o de Railway → Variables.
SECRET_KEY = config('SECRET_KEY')

# En .env local: DEBUG=True
# En Railway: DEBUG=False  (o simplemente no definir la variable → default False)
DEBUG = config('DEBUG', default=False, cast=bool)

# En .env local: ALLOWED_HOSTS=127.0.0.1,localhost
# En Railway:    ALLOWED_HOSTS=tuapp.up.railway.app,tradeflow.pa
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

# ── Aplicaciones ──────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'core',
]

# ── Middleware ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',       # ← sirve static en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'axes.middleware.AxesMiddleware',
    'core.middleware.onboarding_gate.OnboardingGateMiddleware',
    'core.middleware.tf_security.SecurityHeadersMiddleware',
    'core.middleware.tf_security.SecurityEventLogMiddleware',  # OWASP A09
    'core.middleware.tf_security.ApiRateLimitMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tradeflow_colon.urls'

# ── Templates ──────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.csp_nonce_context',  # OWASP A03 (CSP nonce)
                'core.context_processors.cart_badge',
                'core.context_processors.pending_applications_badge',
                'core.context_processors.tf_i18n',
                'core.context_processors.tradeflow_contact',
                'core.context_processors.supabase_public',
                'core.context_processors.enterprise_saas',
                'core.context_processors.tf_asset_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'tradeflow_colon.wsgi.application'

# ── Base de datos ──────────────────────────────────────────────────────────
# SQLite (por defecto): no definas DATABASE_URL en .env
#
# PostgreSQL remoto (Supabase, Neon, Railway, etc.):
#   1. Crea el proyecto en Supabase y copia la URI (Settings → Database → URI).
#   2. En .env: DATABASE_URL=postgresql://postgres:TU_CONTRASENA@db.ayyukcenmtujsshzoebp.supabase.co:5432/postgres
#   3. pip install -r requirements.txt   (ya incluye psycopg2-binary y dj-database-url)
#   4. python manage.py migrate
#   5. Carga datos una vez: python manage.py cargar_demo  (o fixtures / SQL desde Supabase)
# Supabase usa SSL; en local con DEBUG=True pon DB_SSL=false si el pooler da error de certificado.
#
# DATABASE_URL en Railway: la provee el addon PostgreSQL automáticamente.
#
_db_url = config('DATABASE_URL', default='')

if _db_url:
    _ssl_required = config('DB_SSL', default=True, cast=bool)
    _db_cfg = dj_database_url.parse(
        _db_url,
        conn_max_age=600,
        ssl_require=_ssl_required,
    )
    if _ssl_required:
        _db_cfg.setdefault('OPTIONS', {})
        _db_cfg['OPTIONS']['sslmode'] = config('DB_SSLMODE', default='require')
    _db_cfg.setdefault('OPTIONS', {})
    # Evita que migrate/gunicorn cuelguen minutos si DATABASE_URL es incorrecta.
    _db_cfg['OPTIONS'].setdefault('connect_timeout', 15)
    DATABASES = {'default': _db_cfg}
    USING_SUPABASE = 'supabase' in _db_url.lower() or 'postgres' in _db_cfg.get('ENGINE', '')
else:
    USING_SUPABASE = False
    # Fallback SQLite solo para desarrollo inicial sin PostgreSQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Indicador para comandos de verificación / logs
DATABASE_ENGINE_LABEL = (
    DATABASES['default'].get('ENGINE', 'unknown').split('.')[-1]
)

# ── Validación de contraseñas (OWASP A07:2021) ────────────────────────────
# Endurecido en auditoria 2026-06:
#   - MinimumLength sube de 8 (default) a 12 caracteres.
#   - CommonPassword sigue (lista de 20k passwords mas comunes integrada en Django).
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Hashing de contraseñas (OWASP A02:2021) ────────────────────────────────
# Argon2 ganador del Password Hashing Competition (PHC). Resistente a GPU/ASIC.
# PBKDF2/BCrypt mantenidos para verificar hashes legacy (Django rehashea al login).
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

# ── Internationalization ───────────────────────────────────────────────────
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
]
TIME_ZONE     = 'America/Panama'
USE_I18N      = True
USE_L10N      = True
USE_TZ        = True
LOCALE_PATHS = [BASE_DIR / 'locale']

# ── Archivos estáticos ─────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
# Cache-bust query param for JS/CSS after deploy (set TRADEFLOW_ASSET_VERSION on Railway).
TRADEFLOW_ASSET_VERSION = config('TRADEFLOW_ASSET_VERSION', default='auth-nav-v2')

# ── Archivos de medios (imágenes de productos) ────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Autenticación ──────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ── Mensajes flash ─────────────────────────────────────────────────────────
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG:   'debug',
    messages.INFO:    'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR:   'danger',
}

# ── Email ──────────────────────────────────────────────────────────────────
# Verificación de email activa por defecto (demo/local y producción).
# Desactivar solo en CI o desarrollo ágil: REQUIRE_EMAIL_VERIFICATION=false en .env
REQUIRE_EMAIL_VERIFICATION = config(
    'REQUIRE_EMAIL_VERIFICATION',
    default=False,
    cast=bool,
)

# Solicitud de acceso: en producción exige UserApplication aprobada para rutas operativas.
REQUIRE_APPROVED_APPLICATION = config(
    'REQUIRE_APPROVED_APPLICATION',
    default=True,
    cast=bool,
)
# Usuarios sin solicitud previa (cuentas antiguas) pueden operar si True.
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION = config(
    'ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION',
    default=DEBUG,
    cast=bool,
)

# Dashboard KPI ingresos: False = suma órdenes no canceladas (modo pruebas PreExpo);
# True = solo status=delivered (producción / cierre contable).
DASHBOARD_KPI_REVENUE_DELIVERED_ONLY = config(
    'DASHBOARD_KPI_REVENUE_DELIVERED_ONLY',
    default=False,
    cast=bool,
)
from core.utils.email_config import (
    LEGACY_GMAIL_ACCOUNT,
    TRADEFLOW_GMAIL_ACCOUNT,
    normalize_contact_email,
    normalize_project_gmail,
)

# Correo (fallback Django cuando Supabase Edge Function no está disponible)
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
_default_from = config(
    'DEFAULT_FROM_EMAIL',
    default='TradeFlow <noreply@tradeflow.pa>',
)
if LEGACY_GMAIL_ACCOUNT in _default_from.lower():
    _default_from = _default_from.replace(LEGACY_GMAIL_ACCOUNT, TRADEFLOW_GMAIL_ACCOUNT).replace(
        LEGACY_GMAIL_ACCOUNT.upper(),
        TRADEFLOW_GMAIL_ACCOUNT,
    )
DEFAULT_FROM_EMAIL = _default_from
TRADEFLOW_CONTACT_EMAIL = normalize_contact_email(
    config('TRADEFLOW_CONTACT_EMAIL', default=TRADEFLOW_GMAIL_ACCOUNT)
)
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://127.0.0.1:8000')

# Gmail SMTP opcional (fallback cuando la Edge Function de Supabase no envía)
_email_host_user = normalize_project_gmail(config('EMAIL_HOST_USER', default='').strip())
EMAIL_HOST_USER = _email_host_user
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='').strip()
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    if 'console' in (EMAIL_BACKEND or '').lower():
        EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)

EMAIL_USE_REAL_SMTP = 'console' not in (EMAIL_BACKEND or '').lower()
EMAIL_SMTP_CONFIGURED = EMAIL_USE_REAL_SMTP

# Supabase — Postgres (DATABASE_URL), Storage, Edge Functions (email transaccional)
SUPABASE_URL = config('SUPABASE_URL', default='').strip()
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='').strip()
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='').strip()
SUPABASE_EMAIL_FUNCTION = config(
    'SUPABASE_EMAIL_FUNCTION',
    default='send-transactional-email',
)
SUPABASE_EMAIL_ENABLED = config('SUPABASE_EMAIL_ENABLED', default=False, cast=bool)
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

import logging as _logging

_boot_log = _logging.getLogger('tradeflow.boot')
if DEBUG:
    if REQUIRE_EMAIL_VERIFICATION:
        _boot_log.info(
            'REQUIRE_EMAIL_VERIFICATION=True — compradores deben verificar email antes de la tienda.'
        )
    else:
        _boot_log.warning(
            'REQUIRE_EMAIL_VERIFICATION=False — CI/agile dev only (.env).'
        )
    if SUPABASE_CONFIGURED:
        _boot_log.info('Supabase configurado (URL + service key).')
    else:
        _boot_log.warning(
            'Supabase incomplete — verification emails will use Django EMAIL_BACKEND only.'
        )
    if not DEBUG and not EMAIL_SMTP_CONFIGURED and not (
        SUPABASE_CONFIGURED and SUPABASE_EMAIL_ENABLED
    ):
        _boot_log.warning(
            'Producción sin correo: activa SUPABASE_EMAIL_ENABLED + Supabase '
            'o EMAIL_HOST_USER/PASSWORD (Gmail App Password).'
        )

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedStaticFilesStorage'
        ),
    },
}
if SUPABASE_SERVICE_KEY and SUPABASE_URL:
    if 'storages' not in INSTALLED_APPS:
        INSTALLED_APPS.append('storages')
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'endpoint_url': SUPABASE_URL.rstrip('/') + '/storage/v1/s3',
            'access_key': 'service_role',
            'secret_key': SUPABASE_SERVICE_KEY,
            'bucket_name': config('SUPABASE_STORAGE_BUCKET', default='media'),
            'region_name': config('AWS_S3_REGION_NAME', default='us-east-1'),
            'default_acl': 'public-read',
            'file_overwrite': False,
        },
    }

# Revisores de solicitudes de acceso (lista separada por comas)
_application_review_raw = config(
    'APPLICATION_REVIEW_EMAILS',
    default=TRADEFLOW_GMAIL_ACCOUNT,
    cast=Csv(),
)
APPLICATION_REVIEW_EMAILS = [
    normalize_project_gmail(addr) for addr in _application_review_raw if str(addr).strip()
] or [TRADEFLOW_GMAIL_ACCOUNT]

# Checkout: True = flujo antiguo (pago inmediato). False = awaiting_seller (PreExpo).
CHECKOUT_AUTO_APPROVE = config('CHECKOUT_AUTO_APPROVE', default=False, cast=bool)

# ── django-axes (bloqueo por intentos fallidos de login) ──────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'core/bloqueado.html'
AXES_LOCKOUT_PARAMETERS = [['username'], ['ip_address']]

# ── Seguridad de cookies (todos los entornos) ──────────────────────────────
# OWASP A05:2021 — aplican siempre, no solo en produccion.
SESSION_COOKIE_HTTPONLY = True        # JS no puede leer la cookie de sesion
SESSION_COOKIE_SAMESITE = 'Lax'       # mitiga CSRF basico
CSRF_COOKIE_HTTPONLY = True           # JS no puede leer la cookie CSRF
CSRF_COOKIE_SAMESITE = 'Lax'

# Session timeout: expira a las 12 horas de inactividad (sliding window).
# Reduce ventana de uso de cookies robadas.
SESSION_COOKIE_AGE = 12 * 60 * 60     # 12 horas en segundos
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True     # sliding (extiende sesion en cada hit)

# Referrer-Policy (privacy + no leak de URLs internas a sitios externos).
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ── Seguridad en producción ────────────────────────────────────────────────
# Estas opciones solo se activan cuando DEBUG=False
if not DEBUG:
    SECURE_SSL_REDIRECT          = True   # fuerza HTTPS
    SECURE_HSTS_SECONDS          = 31536000  # 1 año de HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True
    SESSION_COOKIE_SECURE        = True   # cookie de sesión solo por HTTPS
    CSRF_COOKIE_SECURE           = True   # cookie CSRF solo por HTTPS
    SECURE_BROWSER_XSS_FILTER   = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True
    X_FRAME_OPTIONS              = 'DENY'

    # Railway usa un proxy inverso — esto confía en su header X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── Logging estructurado (email, media, release) ───────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'tradeflow': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'tradeflow',
        },
    },
    'loggers': {
        'tradeflow.email': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'tradeflow.media': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'tradeflow.platform': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'tradeflow.saas': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        # OWASP A09:2021 — log de eventos de seguridad (401/403/429/5xx, admin scans).
        # En produccion, conectar a Sentry / Datadog / Loki redirigiendo el handler.
        'tradeflow.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# ── Campo de clave primaria ────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Si es True, tras migrar la app core y con la tabla de productos vacía, se ejecuta
# automáticamente el comando cargar_demo (útil en Supabase / Postgres nuevo).
# Por defecto sigue el valor de DEBUG (True en local .env, False en producción).
# Fuerza con SEED_DEMO_IF_EMPTY=false o true en .env.
SEED_DEMO_IF_EMPTY = config('SEED_DEMO_IF_EMPTY', default=DEBUG, cast=bool)

# ── Asistente IA (Groq API gratuita) ───────────────────────────────────────
GROQ_API_KEY = config('GROQ_API_KEY', default='')
GROQ_MODEL = config('GROQ_MODEL', default='llama-3.1-8b-instant')