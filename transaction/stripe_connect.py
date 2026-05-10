import json
import logging

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


class StripeConnectService:
    """
    Scaffold service for Stripe Connect deposit operations.

    For now this supports a placeholder mode and a live-mode scaffold path.
    When full integration is ready, replace TODO blocks with real Stripe calls.
    """

    def _is_placeholder_mode(self):
        return getattr(settings, 'STRIPE_CONNECT_PLACEHOLDER_MODE', True)

    def _build_reference(self, prefix, transaction_reference):
        ts = int(timezone.now().timestamp())
        return f'{prefix}_{transaction_reference}_{ts}'

    def create_setup_intent(self, *, transaction):
        """
        Create a Stripe SetupIntent for secure card collection.
        Returns dict with client_secret for Stripe Elements.
        """
        if self._is_placeholder_mode():
            return {
                'ok': True,
                'provider': 'placeholder',
                'client_secret': f'seti_placeholder_{transaction.id}_{int(timezone.now().timestamp())}_secret_placeholder',
                'setup_intent_id': f'seti_placeholder_{transaction.id}',
            }

        try:
            import stripe  # type: ignore
        except Exception:
            return {
                'ok': False,
                'error': 'Stripe SDK not installed for live mode. Enable placeholder mode or install stripe package.'
            }

        stripe.api_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not stripe.api_key:
            return {
                'ok': False,
                'error': 'STRIPE_CONNECT_SECRET_KEY not configured.'
            }

        try:
            setup_intent = stripe.SetupIntent.create(
                payment_method_types=['card'],
                metadata={
                    'transaction_id': str(transaction.id),
                    'transaction_reference': transaction.transaction_reference,
                }
            )
            return {
                'ok': True,
                'provider': 'stripe',
                'client_secret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id,
            }
        except Exception as e:
            logger.error(f'SetupIntent creation failed: {str(e)}')
            return {
                'ok': False,
                'error': f'Failed to create setup intent: {str(e)}'
            }

    def confirm_card_setup(self, *, transaction, setup_intent_id, payment_method_id):
        """
        Confirm card setup after Stripe Elements submission.
        Extract card details and run £0.01 test hold.
        """
        if self._is_placeholder_mode():
            now = timezone.now()
            return {
                'ok': True,
                'provider': 'placeholder',
                'card_setup_status': transaction.CARD_READY,
                'card_brand': 'Visa',
                'card_last4': '4242',
                'test_hold_status': transaction.TEST_HOLD_SUCCESS,
                'test_hold_amount': 0.01,
                'test_hold_at': now,
                'test_hold_reference': self._build_reference('stripe_connect_test', transaction.transaction_reference),
            }

        try:
            import stripe  # type: ignore
        except Exception:
            return {
                'ok': False,
                'error': 'Stripe SDK not installed for live mode. Enable placeholder mode or install stripe package.'
            }

        stripe.api_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not stripe.api_key:
            return {
                'ok': False,
                'error': 'STRIPE_CONNECT_SECRET_KEY not configured.'
            }

        # TODO: Retrieve payment method, extract card details, create PaymentIntent for £0.01 test hold
        return {
            'ok': False,
            'error': 'Live Stripe card confirmation scaffold is present but not implemented yet.'
        }

    def setup_deposit_card_and_test_hold(self, *, transaction, cardholder_name, card_brand, card_last4):
        """
        Prepare card details and run a placeholder/live £0.01 test hold.
        Returns dict with fields required by the transaction view.
        """
        brand = (card_brand or '').upper()[:20]

        if self._is_placeholder_mode():
            now = timezone.now()
            return {
                'ok': True,
                'provider': 'placeholder',
                'card_setup_status': transaction.CARD_READY,
                'cardholder_name': cardholder_name,
                'card_brand': brand,
                'card_last4': card_last4,
                'test_hold_status': transaction.TEST_HOLD_SUCCESS,
                'test_hold_amount': 0.01,
                'test_hold_at': now,
                'test_hold_reference': self._build_reference('stripe_connect_test', transaction.transaction_reference),
            }

        # Live-mode scaffold (to be implemented with real Stripe Connect calls)
        try:
            import stripe  # type: ignore
        except Exception:
            return {
                'ok': False,
                'error': 'Stripe SDK not installed for live mode. Enable placeholder mode or install stripe package.'
            }

        stripe.api_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not stripe.api_key:
            return {
                'ok': False,
                'error': 'STRIPE_CONNECT_SECRET_KEY not configured.'
            }

        # TODO: create Customer + SetupIntent/PaymentMethod and run £0.01 verification hold.
        return {
            'ok': False,
            'error': 'Live Stripe Connect card setup scaffold is present but not implemented yet.'
        }

    def collect_deposit_hold(self, *, transaction):
        """
        Trigger full deposit authorization hold/retrieval.
        """
        if self._is_placeholder_mode():
            now = timezone.now()
            return {
                'ok': True,
                'provider': 'placeholder',
                'collection_status': transaction.COLLECT_SUCCESS,
                'collection_requested_at': now,
                'collection_reference': self._build_reference('stripe_connect_collect', transaction.transaction_reference),
            }

        try:
            import stripe  # type: ignore
        except Exception:
            return {
                'ok': False,
                'error': 'Stripe SDK not installed for live mode. Enable placeholder mode or install stripe package.'
            }

        stripe.api_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not stripe.api_key:
            return {
                'ok': False,
                'error': 'STRIPE_CONNECT_SECRET_KEY not configured.'
            }

        # TODO: create/capture PaymentIntent in connected-account flow.
        return {
            'ok': False,
            'error': 'Live Stripe Connect deposit collection scaffold is present but not implemented yet.'
        }

    def process_webhook(self, *, payload, signature):
        """
        Webhook scaffold for Stripe Connect events.
        """
        if self._is_placeholder_mode():
            try:
                data = json.loads(payload.decode('utf-8') if isinstance(payload, (bytes, bytearray)) else payload)
                event_type = data.get('type', 'placeholder.unknown')
            except Exception:
                event_type = 'placeholder.unknown'
            return {
                'ok': True,
                'event_type': event_type,
                'provider': 'placeholder',
            }

        try:
            import stripe  # type: ignore
        except Exception:
            return {
                'ok': False,
                'error': 'Stripe SDK not installed for live webhook verification.'
            }

        endpoint_secret = getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET', '')
        if not endpoint_secret:
            return {
                'ok': False,
                'error': 'STRIPE_CONNECT_WEBHOOK_SECRET not configured.'
            }

        try:
            event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
        except Exception as exc:
            logger.warning('Stripe webhook verification failed: %s', exc)
            return {
                'ok': False,
                'error': 'Invalid webhook signature.'
            }

        # TODO: handle stripe events: payment_intent.succeeded/payment_intent.payment_failed/etc.
        return {
            'ok': True,
            'event_type': event.get('type', 'stripe.unknown'),
            'provider': 'stripe',
        }


stripe_connect_service = StripeConnectService()
