from .base import *
import os

DEBUG = False

ADMINS = (
    ('Rentalution Admin', 'admin@rentalution.co.uk'),
)

INSTALLED_APPS += ("djcelery_email",)

DATABASES = {
    #'default': {
    #    'ENGINE': 'django.db.backends.sqlite3',
    #    'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    #}
    'default': {
        'ENGINE': 'djongo',
        'NAME': 'rentalution_prod',
        'ENFORCE_SCHEMA': False,
    }
}

CACHES = {
    'default' : {
        'BACKEND' : 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION' : '127.0.0.1:11211'
    }
}

ALLOWED_HOSTS = ['sharing-hub.com','www.sharing-hub.com','rentalution.co.uk','www.rentalution.co.uk']

ENVIRONMENT_NAME = 'Production'
ENVIRONMENT_COLOR = 'red'

EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'
EMAIL_HOST = 'smtp.zoho.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'application@rentalution.co.uk'
EMAIL_HOST_PASSWORD = os.environ.get('APP_EMAIL_PASSWORD', '')
DEFAULT_FROM_EMAIL = 'application@rentalution.co.uk'
SERVER_EMAIL = 'admin@rentalution.co.uk'

SHARING_HUB_DEFAULT_ADMIN_USER = 'wastaco_admin'

TRANSPACT_IS_TEST = False
STRIPE_CONNECT_ALLOW_LEGACY_CARD_FALLBACK = False
