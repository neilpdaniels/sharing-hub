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
        Extract card details and run £0.30 test hold.
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
                'test_hold_amount': 0.30,
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

        if not setup_intent_id and not payment_method_id:
            return {
                'ok': False,
                'error': 'Missing SetupIntent/payment method details from Stripe confirmation.'
            }

        try:
            pm_obj = None

            # Prefer SetupIntent as source of truth when available.
            if setup_intent_id:
                setup_intent = stripe.SetupIntent.retrieve(
                    setup_intent_id,
                    expand=['payment_method'],
                )

                # Guard against incomplete setup intent confirmation.
                si_status = getattr(setup_intent, 'status', None)
                if si_status not in ('succeeded', 'processing'):
                    return {
                        'ok': False,
                        'error': f'SetupIntent is not complete (status: {si_status}).'
                    }

                if not payment_method_id:
                    pm_ref = getattr(setup_intent, 'payment_method', None)
                    if isinstance(pm_ref, str):
                        payment_method_id = pm_ref
                    elif pm_ref:
                        payment_method_id = getattr(pm_ref, 'id', None)
                        pm_obj = pm_ref

            if not payment_method_id:
                return {
                    'ok': False,
                    'error': 'No payment method was returned by Stripe.'
                }

            if pm_obj is None:
                pm_obj = stripe.PaymentMethod.retrieve(payment_method_id)

            card_data = getattr(pm_obj, 'card', {}) or {}
            billing = getattr(pm_obj, 'billing_details', {}) or {}
            card_brand = (getattr(card_data, 'brand', None) or 'Card').title()
            card_last4 = getattr(card_data, 'last4', None) or 'xxxx'
            cardholder_name = getattr(billing, 'name', None) or 'Stripe'

            # Create/retrieve Stripe Customer and attach PaymentMethod
            # This is required for off_session transactions
            user = transaction.user_aggressive
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                metadata={'user_id': str(user.id)},
            )
            customer_id = getattr(customer, 'id', None)
            
            # Attach PaymentMethod to Customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )

            # Authorize £0.30 and immediately cancel to mimic a verification hold.
            verify_intent = stripe.PaymentIntent.create(
                amount=30,
                currency='gbp',
                customer=customer_id,
                payment_method=payment_method_id,
                confirmation_method='automatic',
                confirm=True,
                capture_method='manual',
                off_session=True,
                metadata={
                    'transaction_id': str(transaction.id),
                    'transaction_reference': transaction.transaction_reference,
                    'purpose': 'deposit_card_verification',
                },
            )

            vi_status = getattr(verify_intent, 'status', None)
            test_reference = getattr(verify_intent, 'id', None)

            if vi_status == 'requires_capture':
                canceled = stripe.PaymentIntent.cancel(getattr(verify_intent, 'id', None))
                test_reference = getattr(canceled, 'id', test_reference)
            elif vi_status in ('succeeded', 'processing'):
                # Succeeded can occur for some payment method/card behaviors.
                pass
            else:
                return {
                    'ok': False,
                    'error': f'Card verification authorization failed (status: {vi_status}).'
                }

            now = timezone.now()
            return {
                'ok': True,
                'provider': 'stripe',
                'card_setup_status': transaction.CARD_READY,
                'cardholder_name': cardholder_name,
                'card_brand': card_brand,
                'card_last4': card_last4,
                'test_hold_status': transaction.TEST_HOLD_SUCCESS,
                'test_hold_amount': 0.30,
                'test_hold_at': now,
                'test_hold_reference': test_reference,
                'stripe_customer_id': customer_id,
            }
        except Exception as exc:
            logger.exception('Stripe live card confirmation failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to confirm Stripe card setup: {str(exc)}'
            }

    def setup_deposit_card_and_test_hold(self, *, transaction, cardholder_name, card_brand, card_last4):
        """
        Prepare card details and run a placeholder/live £0.30 test hold.
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
                'test_hold_amount': 0.30,
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

        # TODO: create Customer + SetupIntent/PaymentMethod and run £0.30 verification hold.
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

        event_type = getattr(event, 'type', 'stripe.unknown')
        event_data = getattr(event, 'data', None)
        event_object = getattr(event_data, 'object', None) if event_data else None

        def _meta_value(meta, key):
            if isinstance(meta, dict):
                return meta.get(key)
            return getattr(meta, key, None)

        if event_type in ('setup_intent.succeeded', 'setup_intent.setup_failed', 'setup_intent.canceled') and event_object:
            try:
                from .models import Transaction

                metadata = getattr(event_object, 'metadata', {}) or {}
                transaction_id = _meta_value(metadata, 'transaction_id')
                transaction_reference = _meta_value(metadata, 'transaction_reference')

                txn = None
                if transaction_id:
                    txn = Transaction.objects.filter(id=transaction_id).first()
                if txn is None and transaction_reference:
                    txn = Transaction.objects.filter(transaction_reference=transaction_reference).first()

                if txn:
                    setup_intent_id = getattr(event_object, 'id', '') or ''
                    pm_ref = getattr(event_object, 'payment_method', None)
                    if isinstance(pm_ref, str):
                        payment_method_id = pm_ref
                    else:
                        payment_method_id = getattr(pm_ref, 'id', '') or ''

                    if setup_intent_id:
                        txn.stripe_setup_intent_id = setup_intent_id
                    if payment_method_id:
                        txn.stripe_payment_method_id = payment_method_id

                    if event_type == 'setup_intent.succeeded':
                        already_completed = (
                            txn.deposit_card_setup_status == txn.CARD_READY
                            and txn.deposit_test_hold_status == txn.TEST_HOLD_SUCCESS
                        )
                        if not already_completed:
                            result = self.confirm_card_setup(
                                transaction=txn,
                                setup_intent_id=setup_intent_id,
                                payment_method_id=payment_method_id,
                            )
                            if result.get('ok'):
                                txn.deposit_card_setup_status = result.get('card_setup_status', txn.CARD_READY)
                                txn.deposit_cardholder_name = result.get('cardholder_name', txn.deposit_cardholder_name)
                                txn.deposit_card_brand = result.get('card_brand', txn.deposit_card_brand)
                                txn.deposit_card_last4 = result.get('card_last4', txn.deposit_card_last4)
                                txn.deposit_test_hold_status = result.get('test_hold_status', txn.TEST_HOLD_SUCCESS)
                                txn.deposit_test_hold_amount = result.get('test_hold_amount', txn.deposit_test_hold_amount)
                                txn.deposit_test_hold_at = result.get('test_hold_at', timezone.now())
                                txn.deposit_test_hold_reference = result.get('test_hold_reference', txn.deposit_test_hold_reference)
                                txn.stripe_customer_id = result.get('stripe_customer_id', txn.stripe_customer_id)
                            else:
                                txn.deposit_card_setup_status = txn.CARD_FAILED
                                txn.deposit_test_hold_status = txn.TEST_HOLD_FAILED
                    else:
                        txn.deposit_card_setup_status = txn.CARD_FAILED
                        txn.deposit_test_hold_status = txn.TEST_HOLD_FAILED

                    txn.save()
            except Exception as exc:
                logger.exception('Stripe webhook processing failed for %s: %s', event_type, exc)

        return {
            'ok': True,
            'event_type': event_type,
            'provider': 'stripe',
        }


stripe_connect_service = StripeConnectService()
