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
from decouple import config, Csv
import dj_database_url

from django.utils.translation import gettext_lazy as _

# ── Rutas ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

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
                'core.context_processors.cart_badge',
                'core.context_processors.tf_i18n',
                'core.context_processors.supabase_public',
                'core.context_processors.enterprise_saas',
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

# ── Validación de contraseñas ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internacionalización ───────────────────────────────────────────────────
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('es', _('Español')),
    ('en', _('English')),
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
# REQUIRE_EMAIL_VERIFICATION: en DEBUG por defecto False (login sin bloqueo);
# en producción por defecto True. Forzar con .env en cualquier entorno.
# Con EMAIL_BACKEND consola los enlaces de verificación se imprimen en la
# terminal del runserver (no llegan a Gmail).
REQUIRE_EMAIL_VERIFICATION = config(
    'REQUIRE_EMAIL_VERIFICATION',
    default=not DEBUG,
    cast=bool,
)

# Solicitud de acceso: en producción exige UserApplication aprobada para rutas operativas.
REQUIRE_APPROVED_APPLICATION = config(
    'REQUIRE_APPROVED_APPLICATION',
    default=not DEBUG,
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
EMAIL_HOST         = config('EMAIL_HOST',     default='smtp.gmail.com')
EMAIL_PORT         = config('EMAIL_PORT',     default=587, cast=int)
EMAIL_USE_TLS      = config('EMAIL_USE_TLS',  default=True, cast=bool)
EMAIL_HOST_USER    = config('EMAIL_HOST_USER',    default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='TradeFlow <no-reply@tradeflow.pa>')
# URL pública (sin / final) para enlaces en correos: ej. https://tuapp.railway.app o http://127.0.0.1:8000
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://127.0.0.1:8000')

# Gmail SMTP (App Password de Google, no la contraseña normal)
_gmail_ready = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
    if _gmail_ready
    else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_USE_REAL_SMTP = 'smtp' in EMAIL_BACKEND and _gmail_ready

# Supabase (opcional — Storage S3-compatible)
SUPABASE_URL = config('SUPABASE_URL', default='')
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='')
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='')

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
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
APPLICATION_REVIEW_EMAILS = config(
    'APPLICATION_REVIEW_EMAILS',
    default='',
    cast=Csv(),
)

# Checkout: True = flujo antiguo (pago inmediato). False = awaiting_seller (PreExpo).
CHECKOUT_AUTO_APPROVE = config('CHECKOUT_AUTO_APPROVE', default=False, cast=bool)

# ── django-axes (bloqueo por intentos fallidos de login) ──────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'core/bloqueado.html'
AXES_LOCKOUT_PARAMETERS = [['username'], ['ip_address']]

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