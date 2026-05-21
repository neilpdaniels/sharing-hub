from django.apps import AppConfig
from django.conf import settings
import logging


logger = logging.getLogger(__name__)


class TransactionConfig(AppConfig):
    name = 'transaction'

    def ready(self):
        import transaction.signals  # noqa: F401

        # Warn once on startup if live Stripe mode is enabled without required keys.
        placeholder_mode = getattr(settings, 'STRIPE_CONNECT_PLACEHOLDER_MODE', True)
        if placeholder_mode:
            logger.warning(
                'Stripe Connect is running in placeholder mode '
                '(STRIPE_CONNECT_PLACEHOLDER_MODE=1). No live Stripe API calls will be made.'
            )
            return

        missing = []
        if not getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''):
            missing.append('STRIPE_CONNECT_PUBLIC_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', ''):
            missing.append('STRIPE_CONNECT_SECRET_KEY')
        if not getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET', ''):
            missing.append('STRIPE_CONNECT_WEBHOOK_SECRET')

        if missing:
            logger.warning(
                'Stripe Connect live mode is enabled but required settings are missing: %s',
                ', '.join(missing)
            )
