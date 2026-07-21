"""Settings de Django para TradeFlow Colón (marketplace B2B ZLC).

Lee secretos con python-decouple desde .env en local, o desde el
entorno del proceso en Railway. Los defaults priorizan producción segura
(DEBUG apagado).
"""
from pathlib import Path

import dj_database_url
from decouple import Config, Csv, RepositoryEmpty

try:
    from decouple import RepositoryDict
except ImportError:
    class RepositoryDict:
        """Repositorio de entorno basado en dict para python-decouple viejo."""

        def __init__(self, mapping):
            """Guarda una copia superficial del mapeo clave/valor."""
            self._data = dict(mapping)

        def __contains__(self, key):
            """Indica si la clave existe en el mapeo."""
            return key in self._data

        def __getitem__(self, key):
            """Devuelve el valor crudo en string de la clave."""
            return self._data[key]

from django.utils.translation import gettext_lazy as _

# Rutas: raíz del proyecto (padre de tradeflow_colon/).
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga .env con utf-8-sig para que el BOM de PowerShell no corrompa SECRET_KEY.
# CI / Railway sin .env usan el entorno del proceso.


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parsea líneas KEY=VALUE de un .env a un dict simple.

    Omite vacías y comentarios; quita comillas opcionales para que
    editores Windows no rompan SECRET_KEY o DATABASE_URL.
    """
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

# Seguridad base: SECRET_KEY y hosts desde env (nunca hardcode).
SECRET_KEY = config('SECRET_KEY')

# El .env local suele poner DEBUG=True; en Railway sin valor → False.
DEBUG = config('DEBUG', default=False, cast=bool)

# Hosts separados por coma; healthchecks de Railway usan *.railway.app.
ALLOWED_HOSTS = list(config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv()))
for _railway_host in ('.up.railway.app', '.railway.app'):
    if _railway_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_railway_host)

# Apps Django: auth (axes, allauth) más marketplace core y analytics.
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
    'analytics',
]

# Pipeline: WhiteNoise, i18n, onboarding gate, CSP/cabeceras de seguridad.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serve static in prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'core.middleware.tf_i18n.TfLanguagePrefixRedirectMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'axes.middleware.AxesMiddleware',
    'core.middleware.onboarding_gate.OnboardingGateMiddleware',
    'core.middleware.staff_mfa.StaffMfaMiddleware',
    'core.middleware.db_unavailable.DatabaseUnavailableMiddleware',
    'core.middleware.tf_security.SecurityHeadersMiddleware',
    'core.middleware.tf_security.SecurityEventLogMiddleware',  # OWASP A09
    'core.middleware.tf_security.ApiRateLimitMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tradeflow_colon.urls'

# Template engine: project templates/ plus marketplace context processors.
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
                'core.context_processors.demo_catalog_context',
                'core.context_processors.cart_badge',
                'core.context_processors.pending_applications_badge',
                'core.context_processors.tf_i18n',
                'core.context_processors.tradeflow_contact',
                'core.context_processors.supabase_public',
                'core.context_processors.enterprise_saas',
                'core.context_processors.tf_asset_version',
                'core.context_processors.tf_user_role',
                'core.context_processors.nav_header_categories',
                'core.context_processors.buyer_mega_menu_context',
                'core.context_processors.social_auth_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'tradeflow_colon.wsgi.application'

# Database: DATABASE_URL → Postgres (Supabase/Railway); else local SQLite.
# Set DB_SSL=false locally if the pooler rejects certificates.
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
    # Fail fast on bad DATABASE_URL instead of hanging migrate/gunicorn.
    _db_cfg['OPTIONS'].setdefault('connect_timeout', 15)
    DATABASES = {'default': _db_cfg}
    USING_SUPABASE = 'supabase' in _db_url.lower() or 'postgres' in _db_cfg.get('ENGINE', '')
else:
    USING_SUPABASE = False
    # SQLite fallback for early local work without Postgres.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Short engine label for health/check commands and boot logs.
DATABASE_ENGINE_LABEL = (
    DATABASES['default'].get('ENGINE', 'unknown').split('.')[-1]
)

# Password validation (OWASP A07): min length 12 + Django common-password list.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Password-reset magic links (PasswordResetTokenGenerator). Default Django is 3 days.
PASSWORD_RESET_TIMEOUT = 60 * 15  # 15 minutes

# Password hashing (OWASP A02): Argon2 first; legacy hashers for rehash-on-login.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

# i18n: English default UI with Spanish; Panama timezone for CFZ ops.
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

# Static files: collectstatic → staticfiles/; WhiteNoise serves in prod.
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
# Manifest hashing in prod; TRADEFLOW_ASSET_VERSION for legacy ?v= params.
TRADEFLOW_ASSET_VERSION = config('TRADEFLOW_ASSET_VERSION', default='desktop-v11')
# Runtime picsum URLs in templates (off in production — use catalog seeds).
TRADEFLOW_USE_PICSUM_RUNTIME = config('TRADEFLOW_USE_PICSUM_RUNTIME', default=False, cast=bool)

# ---------------------------------------------------------------------------
# TTLs de caché de servidor (páginas públicas / merchandising).
# Backend: REDIS_URL → Redis; USE_DB_CACHE → DatabaseCache; si no → LocMem.
# Ajustar vía env sin redeploy de código. Ver docs/PAGE_CACHE.md.
#   CACHE_TTL_HOME         — contexto home invitados + API merch (s)
#   CACHE_TTL_STATS        — contadores marketplace home_stats (s)
#   CACHE_TTL_NAV          — categorías del header (s)
#   CACHE_TTL_CATALOG_META — categorías/empresas/conteos del catálogo (s)
# HTTP Cache-Control en home/catálogo es private (sesión/carrito); no CDN.
# ---------------------------------------------------------------------------
CACHE_TTL_HOME = config('CACHE_TTL_HOME', default=120, cast=int)
CACHE_TTL_STATS = config('CACHE_TTL_STATS', default=300, cast=int)
CACHE_TTL_NAV = config('CACHE_TTL_NAV', default=600, cast=int)
CACHE_TTL_CATALOG_META = config('CACHE_TTL_CATALOG_META', default=300, cast=int)
# Hot-path fragments (company visibility, spotlights, mega-menu, seller KPIs).
CACHE_TTL_ACTIVE_COMPANIES = config('CACHE_TTL_ACTIVE_COMPANIES', default=120, cast=int)
CACHE_TTL_SPOTLIGHTS = config('CACHE_TTL_SPOTLIGHTS', default=120, cast=int)
CACHE_TTL_MEGA_MENU = config('CACHE_TTL_MEGA_MENU', default=180, cast=int)
CACHE_TTL_SELLER_DASH = config('CACHE_TTL_SELLER_DASH', default=45, cast=int)

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

# Media: product images under MEDIA_ROOT; optional local serve when DEBUG=False.
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Serve /media/ from disk when DEBUG=False (Docker demo; not S3-only prod).
SERVE_LOCAL_MEDIA = config('SERVE_LOCAL_MEDIA', default=DEBUG, cast=bool)

# Auth: axes + ModelBackend + allauth (Google / Microsoft / LinkedIn).
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
# OWASP A07: never start OAuth on a bare GET (login CSRF / link prefetch).
SOCIALACCOUNT_LOGIN_ON_GET = False
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

# Flash messages: map Django levels to Bootstrap-style CSS class names.
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG:   'debug',
    messages.INFO:    'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR:   'danger',
}

# Email verification gate. Default True for production safety; set
# REQUIRE_EMAIL_VERIFICATION=false only for local CI / agile demos.
REQUIRE_EMAIL_VERIFICATION = config(
    'REQUIRE_EMAIL_VERIFICATION',
    default=True,
    cast=bool,
)

# Seller SaaS trial: free Digitalízate window + post-trial grace before downgrade.
# State machine lives in core/utils/seller_lifecycle.py.
SELLER_TRIAL_DAYS = config('SELLER_TRIAL_DAYS', default=30, cast=int)
SELLER_GRACE_DAYS = config('SELLER_GRACE_DAYS', default=7, cast=int)

# Plan payments without Stripe: mock allowed in DEBUG; prod uses bank transfer.
ALLOW_MOCK_PLAN_PAYMENT = config(
    'ALLOW_MOCK_PLAN_PAYMENT',
    default=DEBUG,
    cast=bool,
)

# Bank details shown on /mi-tienda/plan/pago/... for manual plan settlement.
SELLER_BANK_NAME = config('SELLER_BANK_NAME', default='Banco General')
SELLER_BANK_ACCOUNT_NAME = config('SELLER_BANK_ACCOUNT_NAME', default='TradeFlow Colón S.A.')
SELLER_BANK_ACCOUNT_NUMBER = config('SELLER_BANK_ACCOUNT_NUMBER', default='')
SELLER_BANK_ACCOUNT_TYPE = config('SELLER_BANK_ACCOUNT_TYPE', default='Corriente')
SELLER_BANK_SWIFT = config('SELLER_BANK_SWIFT', default='')
SELLER_BANK_CURRENCY = config('SELLER_BANK_CURRENCY', default='USD')
SELLER_BANK_INSTRUCTIONS = config(
    'SELLER_BANK_INSTRUCTIONS',
    default=(
        'Transfiere el monto exacto e indica el ID de checkout en el concepto. '
        'Un administrador confirmará el pago en 1–2 días hábiles.'
    ),
)

# Daily cron: python manage.py process_seller_subscriptions (e.g. 06:00 UTC).

# Access gating: require approved UserApplication on operational routes.
REQUIRE_APPROVED_APPLICATION = config(
    'REQUIRE_APPROVED_APPLICATION',
    default=True,
    cast=bool,
)
# Allow pre-gate legacy accounts to operate when True (defaults with DEBUG).
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION = config(
    'ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION',
    default=DEBUG,
    cast=bool,
)

# Dashboard revenue KPI: delivered-only vs all non-cancelled (PreExpo tests).
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

# Transactional email via Resend (core/email_service.py); console in local DEBUG.
import os

RESEND_API_KEY = config('RESEND_API_KEY', default=os.environ.get('RESEND_API_KEY', '')).strip()

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
_default_from = (
    config('RESEND_FROM_EMAIL', default='').strip()
    or config(
        'DEFAULT_FROM_EMAIL',
        default='TradeFlow Colón <no-reply@tradeflowcolon.com>',
    ).strip()
)
if LEGACY_GMAIL_ACCOUNT in _default_from.lower():
    _default_from = _default_from.replace(LEGACY_GMAIL_ACCOUNT, TRADEFLOW_GMAIL_ACCOUNT).replace(
        LEGACY_GMAIL_ACCOUNT.upper(),
        TRADEFLOW_GMAIL_ACCOUNT,
    )
DEFAULT_FROM_EMAIL = _default_from
RESEND_FROM_EMAIL = _default_from
TRADEFLOW_CONTACT_EMAIL = normalize_contact_email(
    config('TRADEFLOW_CONTACT_EMAIL', default=TRADEFLOW_GMAIL_ACCOUNT)
)
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://127.0.0.1:8000')


def _csrf_origins_for_base(base_url: str, extra_origins=None):
    """Arma orígenes CSRF HTTPS con variantes apex y www.

    Frontends en Railway/Cloudflare pueden pegar a cualquiera; Django
    necesita ambos listados o los POST fallan CSRF tras el redirect.
    """
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


def _csrf_origins_for_host(host: str, *, allow_http: bool = False):
    """Build scheme://host CSRF origins for one concrete hostname."""
    host = (host or '').strip().lower().rstrip('.')
    if not host or host.startswith('.') or '*' in host or '/' in host:
        return []
    origins = [f'https://{host}']
    if allow_http:
        origins.append(f'http://{host}')
    return origins


def _build_csrf_trusted_origins():
    """Combina PUBLIC_BASE_URL, hosts concretos y CSRF_TRUSTED_ORIGINS.

    Incluye dominios Railway públicos cuando existen, para que un POST
    desde ``*.up.railway.app`` no falle Origin check si el proxy mezcla
    Host/X-Forwarded-Proto.
    """
    origins = _csrf_origins_for_base(
        PUBLIC_BASE_URL,
        config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv()),
    )
    allow_http = bool(DEBUG)
    for host in ALLOWED_HOSTS:
        for origin in _csrf_origins_for_host(host, allow_http=allow_http):
            if origin not in origins:
                origins.append(origin)
            # www variant for bare domains (skip localhost / IPs / railway wildcards).
            if (
                origin.startswith('https://')
                and not origin.startswith('https://www.')
                and host.count('.') >= 1
                and not host.replace('.', '').isdigit()
                and 'localhost' not in host
            ):
                www_origin = origin.replace('https://', 'https://www.', 1)
                if www_origin not in origins:
                    origins.append(www_origin)
    for env_key in ('RAILWAY_PUBLIC_DOMAIN', 'RAILWAY_STATIC_URL'):
        raw = config(env_key, default='').strip()
        if not raw:
            continue
        if raw.startswith('http'):
            origins = _csrf_origins_for_base(raw, origins)
        else:
            for origin in _csrf_origins_for_host(raw, allow_http=False):
                if origin not in origins:
                    origins.append(origin)
    return origins


CSRF_TRUSTED_ORIGINS = _build_csrf_trusted_origins()
CSRF_FAILURE_VIEW = 'core.views.csrf.csrf_failure'
EMAIL_USE_REAL_SMTP = bool(RESEND_API_KEY)
EMAIL_SMTP_CONFIGURED = EMAIL_USE_REAL_SMTP

# Supabase: Postgres vía DATABASE_URL; Storage con URL + service key (no email).
SUPABASE_URL = config('SUPABASE_URL', default='').strip()
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='').strip()
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='').strip()
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
SUPABASE_STORAGE_BUCKET = config('SUPABASE_STORAGE_BUCKET', default='media')
# Public bucket → native /object/public/ URLs (recommended for product images).
SUPABASE_STORAGE_PUBLIC = config('SUPABASE_STORAGE_PUBLIC', default=True, cast=bool)
SUPABASE_SIGNED_URL_TTL = config('SUPABASE_SIGNED_URL_TTL', default=3600, cast=int)

import logging as _logging

# Diagnóstico de arranque email/Supabase (solo DEBUG).
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

# Storage default: filesystem en local; WhiteNoise manifest para static en prod.
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

# Access-application reviewers (comma-separated emails, normalized).
_application_review_raw = config(
    'APPLICATION_REVIEW_EMAILS',
    default=TRADEFLOW_GMAIL_ACCOUNT,
    cast=Csv(),
)
APPLICATION_REVIEW_EMAILS = [
    normalize_project_gmail(addr) for addr in _application_review_raw if str(addr).strip()
] or [TRADEFLOW_GMAIL_ACCOUNT]

# Checkout: True = immediate pay; False = awaiting_seller (PreExpo flow).
CHECKOUT_AUTO_APPROVE = config('CHECKOUT_AUTO_APPROVE', default=False, cast=bool)

# Expo demo: bypass onboarding gate after OTP (approved + active application).
EXPO_DEMO_MODE = config('EXPO_DEMO_MODE', default=False, cast=bool)

# Staff/admin must enroll TOTP (skipped automatically when EXPO_DEMO_MODE=True).
STAFF_MFA_REQUIRED = config('STAFF_MFA_REQUIRED', default=True, cast=bool)

# Public SaaS walkthrough account: read-only, MFA-exempt, no Django Admin.
# Set to an empty string to disable this narrowly scoped exception.
SAAS_READ_ONLY_DEMO_USERNAME = config(
    'SAAS_READ_ONLY_DEMO_USERNAME',
    default='demo_admin',
).strip()

# django-axes: lock after failed logins (username or IP).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'core/bloqueado.html'
AXES_LOCKOUT_PARAMETERS = [['username'], ['ip_address']]
# Prefer proxy-appended (rightmost) XFF hop — see core.utils.client_ip.
AXES_CLIENT_IP_CALLABLE = 'core.utils.client_ip.get_client_ip'

# Optional shared token for detailed /health/ready/?detail=1&token=…
HEALTH_DETAIL_TOKEN = config('HEALTH_DETAIL_TOKEN', default='').strip()

# Comma-separated extra DB hosts staff Analytics may connect to in production.
ANALYTICS_DB_HOST_ALLOWLIST = config('ANALYTICS_DB_HOST_ALLOWLIST', default='').strip()

# Endurecimiento de cookies (OWASP A05) — aplica en todos los entornos.
SESSION_COOKIE_HTTPONLY = True        # JS cannot read session cookie
SESSION_COOKIE_SAMESITE = 'Lax'       # basic CSRF mitigation
# CSRF cookie stays readable by same-origin JS (cart/AJAX). The session
# cookie remains HttpOnly; XSS can already read {% csrf_token %} from DOM.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'

# Session lifetime 12h. Default: save only when modified (avoids a DB write on
# every HTML hit against remote Postgres). Opt into sliding saves via env.
SESSION_COOKIE_AGE = 12 * 60 * 60     # 12 hours in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = config('SESSION_SAVE_EVERY_REQUEST', default=False, cast=bool)

# Referrer-Policy: avoid leaking internal URLs to third parties.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# TLS/HSTS/cookies Secure en producción (solo con DEBUG=False).
if not DEBUG:
    SECURE_SSL_REDIRECT          = True   # force HTTPS
    SECURE_HSTS_SECONDS          = 31536000  # 1 year HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True
    SESSION_COOKIE_SECURE        = True   # session cookie HTTPS-only
    CSRF_COOKIE_SECURE           = True   # CSRF cookie HTTPS-only
    SECURE_BROWSER_XSS_FILTER   = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True
    X_FRAME_OPTIONS              = 'DENY'
    # Railway internal probes hit HTTP without X-Forwarded-Proto.
    SECURE_REDIRECT_EXEMPT = [
        r'^health/live/?$',
        r'^health/ready/?$',
    ]

    # Trust Railway reverse-proxy HTTPS indicator.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Logging estructurado a consola: email, auth, media, SaaS, seguridad.
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
        # OWASP A09: security events (401/403/429/5xx, admin scans).
        # In production, ship this logger to Sentry/Datadog/Loki.
        'tradeflow.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# Tipo de PK por defecto en modelos nuevos.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# After core migrate, run cargar_demo if product table is empty (new Postgres).
# Defaults to DEBUG; override with SEED_DEMO_IF_EMPTY in .env.
SEED_DEMO_IF_EMPTY = config('SEED_DEMO_IF_EMPTY', default=DEBUG, cast=bool)

# Public disclosure for environments backed by generated catalog data.
# Keep enabled until supplier identities and commercial metrics are real.
DEMO_CATALOG_DISCLOSURE = config(
    'DEMO_CATALOG_DISCLOSURE',
    default=EXPO_DEMO_MODE or SEED_DEMO_IF_EMPTY,
    cast=bool,
)

# Clave Groq del asistente in-app (API free-tier).
GROQ_API_KEY = config('GROQ_API_KEY', default='')
GROQ_MODEL = config('GROQ_MODEL', default='llama-3.1-8b-instant')

# Chat analytics: modelo Groq mayor; puente de env hacia analytics/engine.
ANALYTICS_LLM_MODEL = config('ANALYTICS_LLM_MODEL', default='llama-3.3-70b-versatile')
os.environ.setdefault('LLM_BASE_URL', 'https://api.groq.com/openai/v1')
os.environ.setdefault('LLM_MODEL', ANALYTICS_LLM_MODEL)
if GROQ_API_KEY:
    os.environ.setdefault('LLM_API_KEY', GROQ_API_KEY)

# Optional Sentry (OWASP A09) — no-op when SENTRY_DSN is empty.
SENTRY_DSN = config('SENTRY_DSN', default='').strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(config('SENTRY_TRACES_SAMPLE_RATE', default='0.05')),
            send_default_pii=False,
            environment='debug' if DEBUG else 'production',
        )
    except Exception:
        # Never block boot if the SDK is missing or misconfigured.
        pass
