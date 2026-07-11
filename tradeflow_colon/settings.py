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
# En Railway:    ALLOWED_HOSTS=web-production-xxxx.up.railway.app,tu-dominio.com
ALLOWED_HOSTS = list(config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv()))
# Healthchecks internos de Railway usan subdominios *.up.railway.app
for _railway_host in ('.up.railway.app', '.railway.app'):
    if _railway_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_railway_host)

# ── Aplicaciones ──────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'axes',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.microsoft',
    'allauth.socialaccount.providers.linkedin_oauth2',
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
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'axes.middleware.AxesMiddleware',
    'core.middleware.onboarding_gate.OnboardingGateMiddleware',
    'core.middleware.db_unavailable.DatabaseUnavailableMiddleware',
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
                'core.context_processors.nav_header_categories',
                'core.context_processors.buyer_mega_menu_context',
                'core.context_processors.social_auth_context',
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
from core.utils.database_url import normalize_database_url

_db_url = normalize_database_url(config('DATABASE_URL', default=''))

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
    ('es', 'Español'),
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
# Cache-bust: production uses WhiteNoise CompressedManifestStaticFilesStorage
# (content hash in filename, e.g. login.3a80a22efbb7.css). TRADEFLOW_ASSET_VERSION
# remains for legacy ?v= query params on templates not yet migrated.
TRADEFLOW_ASSET_VERSION = config('TRADEFLOW_ASSET_VERSION', default='desktop-v11')
# Runtime picsum URLs in templates (off in production — use bundled catalog seeds).
TRADEFLOW_USE_PICSUM_RUNTIME = config('TRADEFLOW_USE_PICSUM_RUNTIME', default=False, cast=bool)

# ── Cache (páginas públicas / merchandising) ───────────────────────────────
# REDIS_URL en Railway → compartido entre workers Gunicorn (recomendado).
# Sin Redis: LocMem por worker (default). USE_DB_CACHE=true + createcachetable
# para cache compartida en PostgreSQL.
CACHE_TTL_HOME = config('CACHE_TTL_HOME', default=120, cast=int)
CACHE_TTL_STATS = config('CACHE_TTL_STATS', default=300, cast=int)
CACHE_TTL_NAV = config('CACHE_TTL_NAV', default=600, cast=int)
CACHE_TTL_CATALOG_META = config('CACHE_TTL_CATALOG_META', default=300, cast=int)

_redis_url = config('REDIS_URL', default='')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'KEY_PREFIX': 'tf',
        }
    }
else:
    # LocMem works out of the box (per Gunicorn worker). For shared cache across
    # workers without Redis, set USE_DB_CACHE=true and run createcachetable once.
    _use_db_cache = config('USE_DB_CACHE', default=False, cast=bool)
    if _use_db_cache and _db_url:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
                'LOCATION': 'tradeflow_cache',
            }
        }
    else:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'tradeflow-local',
            }
        }

# ── Archivos de medios (imágenes de productos) ────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Serve /media/ from MEDIA_ROOT when DEBUG=False but files are stored locally (Docker demo).
SERVE_LOCAL_MEDIA = config('SERVE_LOCAL_MEDIA', default=DEBUG, cast=bool)

# ── Autenticación ──────────────────────────────────────────────────────────
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/'
LOGOUT_REDIRECT_URL = '/login/'

ACCOUNT_ADAPTER = 'core.social_auth.TradeFlowAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'core.social_auth.TradeFlowSocialAccountAdapter'
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

_GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='').strip()
_GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='').strip()
_MICROSOFT_CLIENT_ID = config('MICROSOFT_CLIENT_ID', default='').strip()
_MICROSOFT_CLIENT_SECRET = config('MICROSOFT_CLIENT_SECRET', default='').strip()
_LINKEDIN_CLIENT_ID = config('LINKEDIN_CLIENT_ID', default='').strip()
_LINKEDIN_CLIENT_SECRET = config('LINKEDIN_CLIENT_SECRET', default='').strip()

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': _GOOGLE_CLIENT_ID,
            'secret': _GOOGLE_CLIENT_SECRET,
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'microsoft': {
        'APP': {
            'client_id': _MICROSOFT_CLIENT_ID,
            'secret': _MICROSOFT_CLIENT_SECRET,
            'key': '',
        },
        'TENANT': 'common',
    },
    'linkedin_oauth2': {
        'APP': {
            'client_id': _LINKEDIN_CLIENT_ID,
            'secret': _LINKEDIN_CLIENT_SECRET,
            'key': '',
        },
        'SCOPE': ['openid', 'profile', 'email'],
    },
}

SOCIAL_AUTH_ENABLED = bool(
    (_GOOGLE_CLIENT_ID and _GOOGLE_CLIENT_SECRET)
    or (_MICROSOFT_CLIENT_ID and _MICROSOFT_CLIENT_SECRET)
    or (_LINKEDIN_CLIENT_ID and _LINKEDIN_CLIENT_SECRET)
)

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

# Correo transaccional vía Resend (core/email_service.py). Consola solo en DEBUG local.
import os

RESEND_API_KEY = config('RESEND_API_KEY', default=os.environ.get('RESEND_API_KEY', '')).strip()

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


def _csrf_origins_for_base(base_url: str, extra_origins=None):
    """Pure helper — apex + www variants for HTTPS CSRF trust."""
    origins = list(extra_origins or [])
    base = (base_url or '').rstrip('/')
    if not base.startswith('http'):
        return origins
    if base not in origins:
        origins.append(base)
    if base.startswith('https://www.'):
        apex = base.replace('https://www.', 'https://', 1)
        if apex not in origins:
            origins.append(apex)
    elif base.startswith('https://'):
        www = base.replace('https://', 'https://www.', 1)
        if www not in origins:
            origins.append(www)
    return origins


def _build_csrf_trusted_origins():
    """HTTPS origins for Django CSRF behind Railway/Cloudflare (www + apex)."""
    return _csrf_origins_for_base(
        PUBLIC_BASE_URL,
        config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv()),
    )


CSRF_TRUSTED_ORIGINS = _build_csrf_trusted_origins()

EMAIL_USE_REAL_SMTP = bool(RESEND_API_KEY)
EMAIL_SMTP_CONFIGURED = EMAIL_USE_REAL_SMTP

# Supabase — Postgres (DATABASE_URL) y Storage (no email; ver RESEND_API_KEY)
SUPABASE_URL = config('SUPABASE_URL', default='').strip()
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='').strip()
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='').strip()
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
SUPABASE_STORAGE_BUCKET = config('SUPABASE_STORAGE_BUCKET', default='media')
# Public bucket → native /object/public/ URLs (recommended for product images).
SUPABASE_STORAGE_PUBLIC = config('SUPABASE_STORAGE_PUBLIC', default=True, cast=bool)
SUPABASE_SIGNED_URL_TTL = config('SUPABASE_SIGNED_URL_TTL', default=3600, cast=int)

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
        _boot_log.warning('Supabase incomplete — DB/Storage pueden fallar.')
    if RESEND_API_KEY:
        _boot_log.info('Resend configurado (RESEND_API_KEY).')
    elif not DEBUG:
        _boot_log.warning(
            'Producción sin correo: configura RESEND_API_KEY (resend.com/api-keys).'
        )
    elif 'console' in (EMAIL_BACKEND or '').lower():
        _boot_log.info('Email en consola (DEBUG + EMAIL_BACKEND console).')

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}
if SUPABASE_SERVICE_KEY and SUPABASE_URL:
    if 'storages' not in INSTALLED_APPS:
        INSTALLED_APPS.append('storages')
    STORAGES['default'] = {
        'BACKEND': 'core.storage.supabase_media.SupabaseMediaStorage',
        'OPTIONS': {
            'endpoint_url': SUPABASE_URL.rstrip('/') + '/storage/v1/s3',
            'access_key': 'service_role',
            'secret_key': SUPABASE_SERVICE_KEY,
            'bucket_name': SUPABASE_STORAGE_BUCKET,
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

# Demo Expo: bypass onboarding gate tras OTP (UserApplication approved + is_active).
EXPO_DEMO_MODE = config('EXPO_DEMO_MODE', default=False, cast=bool)

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
    # El probe interno de Railway llega por HTTP sin X-Forwarded-Proto.
    SECURE_REDIRECT_EXEMPT = [
        r'^health/live/?$',
        r'^health/ready/?$',
    ]

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
        'tradeflow.auth': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
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