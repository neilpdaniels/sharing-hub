from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging


logger = logging.getLogger(__name__)


class TransactionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transaction'

    def ready(self):
        import transaction.signals  # noqa: F401

        configured_values = (
            getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''),
            getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', ''),
            getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET', ''),
        )
        # An entirely unconfigured development environment is supported. Once
        # any Connect value is supplied, require a complete, mode-consistent set.
        if not any(configured_values):
            return

        missing = []
        if not getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''):
            missing.append('STRIPE_CONNECT_PUBLIC_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', ''):
            missing.append('STRIPE_CONNECT_SECRET_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET', ''):
            missing.append('STRIPE_CONNECT_WEBHOOK_SECRET')

        if missing:
            message = 'Stripe Connect configuration is incomplete: %s' % ', '.join(missing)
            if getattr(settings, 'ENVIRONMENT_NAME', '').lower() == 'production':
                raise ImproperlyConfigured(message)
            logger.warning(message)
            return

        public_key = getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', '')
        secret_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not public_key.startswith(('pk_test_', 'pk_live_')) or not secret_key.startswith(('sk_test_', 'sk_live_', 'rk_test_', 'rk_live_')):
            raise ImproperlyConfigured('Stripe Connect API key format is invalid.')
        if public_key.split('_', 2)[1] != secret_key.split('_', 2)[1]:
            raise ImproperlyConfigured('Stripe Connect publishable and secret keys are from different modes.')
        if getattr(settings, 'STRIPE_CONNECT_PLATFORM_COUNTRY', 'GB') != 'GB' or getattr(settings, 'STRIPE_CONNECT_CURRENCY', 'gbp') != 'gbp':
            raise ImproperlyConfigured('Rentalution Stripe Connect currently supports a UK platform and GBP only.')
