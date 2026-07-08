from django.apps import AppConfig
from django.conf import settings
import logging


logger = logging.getLogger(__name__)


class TransactionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transaction'

    def ready(self):
        import transaction.signals  # noqa: F401

        missing = []
        if not getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''):
            missing.append('STRIPE_CONNECT_PUBLIC_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', ''):
            missing.append('STRIPE_CONNECT_SECRET_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET', ''):
            missing.append('STRIPE_CONNECT_WEBHOOK_SECRET')

        if missing:
            logger.warning(
                'Stripe Connect is enabled but required settings are missing: %s',
                ', '.join(missing)
            )
