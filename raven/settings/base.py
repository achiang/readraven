import os
from unipath import Path


PROJECT_DIR = Path(__file__).ancestor(3)

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Alex Chiang', 'alex@readraven.com'),
)

MANAGERS = ADMINS

AUTH_USER_MODEL = 'usher.User'
LOGIN_URL = '/usher/sign_in'


# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['www.readraven.com']

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = False

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = ''

# Additional locations of static files
STATICFILES_DIRS = (
    PROJECT_DIR.child("static"),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.environ['SECRET_KEY']

# We do store some low-risk secrets in the filesystem, such as Google
# API json files
SECRETS_DIR = PROJECT_DIR.child("secrets")

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    #'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'djangosecure.middleware.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'raven.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'raven.wsgi.application'

TEMPLATE_DIRS = (
    PROJECT_DIR.child("templates"),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',

    'django_push.subscriber',
    'djangosecure',
    'djcelery',
    'south',
    'payments',
    'taggit',
    'storages',

    'raven',
    'usher',
)

# django-stripe-payments
STRIPE_PUBLIC_KEY = os.environ['STRIPE_PUBLIC_KEY']
STRIPE_SECRET_KEY = os.environ['STRIPE_SECRET_KEY']

PAYMENTS_PLANS = {
    "free": {
        "stripe_plan_id": "raven-free",
        "name": "raven-free",
        "description": "Free during beta",
        "price": 0,
        "currency": "usd",
        "interval": "month"
    },
    "monthly": {
        "stripe_plan_id": "raven-monthly",
        "name": "raven-monthly",
        "description": "The monthly subscription plan",
        "price": 5,
        "currency": "usd",
        "interval": "month"
    },
}

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

# Security shit
SESSION_COOKIE_SECURE = True
SECURE_FRAME_DENY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# XXX: Do NOT turn this off. Google OAuth2 will break on you in strange
# and horrifying ways.
SECURE_SSL_REDIRECT = True

# XXX: If you remove this, you will get an infinite-redirect loop on
# heroku
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

API_LIMIT_PER_PAGE = 0

# django-push setting, use https for callback urls
PUSH_SSL_CALLBACK = True

import dj_database_url
DATABASES = {
    'default' : dj_database_url.config(),
}
DATABASES['default']['ENGINE'] = 'django_postgrespool'

# XXX: slaves will need to define the env variable. kinda nasty...
if os.environ.get('I_AM_SLAVE', False):
    DATABASES['writedb'] = dj_database_url.config(env='WRITEDB_URL', default='DATABASE_URL')
    DATABASES['writedb']['ENGINE'] = 'django_postgrespool'
    DATABASE_ROUTERS = ['raven.routers.MasterSlaveRouter']

SOUTH_DATABASE_ADAPTERS = {
    'default': 'south.db.postgresql_psycopg2'
}

DATABASE_POOL_ARGS = {
    'max_overflow': 50,
    'pool_size': 5,
    'recycle': 300
}
