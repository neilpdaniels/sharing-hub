from .base import *

DEBUG = True
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DATABASES = {
    'default': {
       'ENGINE': 'django.db.backends.sqlite3',
       'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
    # 'default': {
    #     'ENGINE': 'django.db.backends.postgresql_psycopg2',
    #     'NAME': 'sharing_hub',
    #     'USER': 'sharing_hub_admin',
    #     'PASSWORD': '10mB9wRrX',
    #     'HOST': 'localhost',
    #     'PORT' : '5432',
    # }
}

CACHES = {
    'default' : {
        'BACKEND' : 'django.core.cache.backends.locmem.LocMemCache',
    }
}

### debug toolbar ### 
DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'template_timings_panel.panels.TemplateTimings.TemplateTimings',
    ]
INSTALLED_APPS += ('debug_toolbar', )
INSTALLED_APPS += ('template_timings_panel',)
MIDDLEWARE += ('debug_toolbar.middleware.DebugToolbarMiddleware',)
INTERNAL_IPS = '127.0.0.1'
### end of debug toolbar ###

LOGGING = {
    "version": 1,
    'disable_existing_loggers': False,
    "root": {
        "level": "INFO"
    }
}

ENVIRONMENT_NAME = 'dev server'
ENVIRONMENT_COLOR = 'green'

SHARING_HUB_DEFAULT_ADMIN_USER = 'ndaniels'

TRANSPACT_IS_TEST = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

GETADDRESS_IO_API_KEY = 'LqMIyzNTgEOnNrk_lBtVJA51693'

MOBILE_VERIFICATION_ENABLED = os.environ.get('MOBILE_VERIFICATION_ENABLED', '0') == '1'