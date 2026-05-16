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
    'core',
]

# ── Middleware ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',       # ← sirve static en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
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
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
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
_db_url = config('DATABASE_URL', default=None)

if _db_url:
    DATABASES = {
        'default': dj_database_url.parse(
            _db_url,
            conn_max_age=600,       # mantiene conexiones vivas 10 min (performance)
            ssl_require=config('DB_SSL', default=not DEBUG, cast=bool),
        )
    }
else:
    # Fallback SQLite solo para desarrollo inicial sin PostgreSQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── Validación de contraseñas ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internacionalización ───────────────────────────────────────────────────
LANGUAGE_CODE = 'es-pa'
TIME_ZONE     = 'America/Panama'
USE_I18N      = True
USE_TZ        = True

# ── Archivos estáticos ─────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise comprime y cachea los estáticos en producción automáticamente
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Archivos de medios (imágenes de productos) ────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Autenticación ──────────────────────────────────────────────────────────
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
# Para desarrollo: imprime emails en consola (sin configurar nada más)
# Para producción: cambia a smtp y rellena las variables en .env / Railway
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST         = config('EMAIL_HOST',     default='smtp.gmail.com')
EMAIL_PORT         = config('EMAIL_PORT',     default=587, cast=int)
EMAIL_USE_TLS      = config('EMAIL_USE_TLS',  default=True, cast=bool)
EMAIL_HOST_USER    = config('EMAIL_HOST_USER',    default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='TradeFlow <no-reply@tradeflow.pa>')
# URL pública (sin / final) para enlaces en correos: ej. https://tuapp.railway.app o http://127.0.0.1:8000
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://127.0.0.1:8000')

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

# ── Campo de clave primaria ────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Si es True, tras migrar la app core y con la tabla de productos vacía, se ejecuta
# automáticamente el comando cargar_demo (útil en Supabase / Postgres nuevo).
# Por defecto sigue el valor de DEBUG (True en local .env, False en producción).
# Fuerza con SEED_DEMO_IF_EMPTY=false o true en .env.
SEED_DEMO_IF_EMPTY = config('SEED_DEMO_IF_EMPTY', default=DEBUG, cast=bool)