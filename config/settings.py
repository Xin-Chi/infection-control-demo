"""
Django settings for the 感染管控收案系統 demo site.

All values that differ between environments (secret key, debug flag, allowed
hosts, database location) are read from the environment.  ``.env.example``
documents every variable; copy it to ``.env`` and adjust.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    """Read a boolean from the environment ('1', 'true', 'yes' are True)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=()):
    """Read a comma-separated list from the environment."""
    raw = os.environ.get(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(',') if item.strip()]


# Load a .env file if present, so local development does not need the variables
# exported by hand.  Values already in the environment always win.
def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(BASE_DIR / '.env')


# -- Core -------------------------------------------------------------------

DEBUG = env_bool('DJANGO_DEBUG', default=False)

# No fallback secret in source control.  In DEBUG an ephemeral key is generated
# so a fresh checkout runs; any other environment must supply one.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
    else:
        raise RuntimeError(
            'DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off. '
            'See .env.example.'
        )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# -- Demo mode --------------------------------------------------------------
#
# The public showcase build.  Every record on the site is fictional, so there
# is nothing to protect behind a login, and publishing demo credentials would
# only add a step for visitors.  With this on:
#
#   * the 查詢 page is readable without an account,
#   * navigation is trimmed to that one page,
#   * every data-modifying endpoint is refused.
#
# Turn it off (DJANGO_DEMO_MODE=0) to get the full application back: login is
# required, all sections appear, and the per-section permission system in
# ``accounts.permissions`` governs access.
DEMO_MODE = env_bool('DJANGO_DEMO_MODE', default=True)

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts.apps.AccountsConfig',
    'clinical.apps.ClinicalConfig',
    'infection.apps.InfectionConfig',
    'research.apps.ResearchConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
                'accounts.context_processors.navigation',
            ],
        },
    },
]


# -- Database ---------------------------------------------------------------
#
# The demo runs entirely on a local SQLite file seeded with fictional data
# (``manage.py seed_demo``).  There is no hospital network dependency.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', BASE_DIR / 'db.sqlite3'),
    }
}


# -- Authentication ---------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:index'
LOGOUT_REDIRECT_URL = 'accounts:index'


# -- Internationalisation ---------------------------------------------------

LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_I18N = True
USE_TZ = True


# -- Static files -----------------------------------------------------------

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'


# -- Security ---------------------------------------------------------------
#
# Cookies stay session-scoped and inaccessible to JavaScript.  The HTTPS-only
# flags are enabled automatically once DEBUG is off.

X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# Uploads are capped well below the original 5 GB, which was large enough to be
# a denial-of-service vector.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[{levelname}] {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}
