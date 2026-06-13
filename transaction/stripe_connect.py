import logging

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


class StripeConnectService:
    """
    Stripe Connect deposit operations.

    The service now assumes real Stripe test/live credentials are configured.
    If Stripe cannot be loaded or configured, it fails loudly instead of
    silently falling back to a placeholder flow.
    """

    def _build_reference(self, prefix, transaction_reference):
        ts = int(timezone.now().timestamp())
        return f'{prefix}_{transaction_reference}_{ts}'

    def _load_stripe_client(self):
        try:
            import stripe  # type: ignore
        except Exception:
            return None, {
                'ok': False,
                'error': 'Stripe SDK not installed. Install the stripe package and configure test keys.'
            }

        stripe.api_key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if not stripe.api_key:
            return None, {
                'ok': False,
                'error': 'STRIPE_CONNECT_SECRET_KEY not configured.'
            }

        return stripe, None

    def _to_minor_units(self, amount):
        try:
            return int(round(max(0, float(amount or 0)) * 100))
        except (TypeError, ValueError):
            return 0

    def _rental_total_minor(self, transaction):
        rental_amount = (transaction.quantity or 0) * (transaction.price or 0)
        delivery_amount = transaction.delivery_cost or 0
        rentalution_amount = transaction.rentalution_fee or 0
        return self._to_minor_units(rental_amount + delivery_amount + rentalution_amount)

    def _long_rental_requires_credit_or_mastercard(self, transaction):
        return int(getattr(transaction, 'max_rental_days', 0) or 0) > 5

    def _is_deposit_card_allowed_for_long_rental(self, card_brand, card_funding):
        brand = (card_brand or '').strip().lower()
        funding = (card_funding or '').strip().lower()
        return brand in ('visa', 'mastercard') and funding in ('credit', 'charge')

    def _ensure_customer_and_payment_method(self, stripe, *, transaction):
        customer_id = (transaction.stripe_customer_id or '').strip()
        if not customer_id:
            user = transaction.user_aggressive
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                metadata={'user_id': str(user.id)},
            )
            customer_id = getattr(customer, 'id', '') or ''

        payment_method_id = (transaction.stripe_payment_method_id or '').strip()
        if not payment_method_id:
            return None, customer_id, {
                'ok': False,
                'error': 'No Stripe payment method is attached to this transaction.'
            }

        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        pm_customer = getattr(payment_method, 'customer', None)
        if isinstance(pm_customer, str):
            attached_customer = pm_customer
        else:
            attached_customer = getattr(pm_customer, 'id', None)

        if not attached_customer:
            stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
        elif attached_customer != customer_id:
            # Safety fallback for mismatched local customer pointers.
            try:
                stripe.PaymentMethod.detach(payment_method_id)
                stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
            except Exception as exc:
                return None, customer_id, {
                    'ok': False,
                    'error': f'Payment method is attached to a different customer: {str(exc)}'
                }

        return payment_method_id, customer_id, None

    def create_setup_intent(self, *, transaction):
        """
        Create a Stripe SetupIntent for secure card collection.
        Returns dict with client_secret for Stripe Elements.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

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

    def create_user_setup_intent(self, *, user):
        """
        Create a Stripe SetupIntent for a user-level saved card flow.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        try:
            setup_intent = stripe.SetupIntent.create(
                payment_method_types=['card'],
                metadata={
                    'user_id': str(user.id),
                    'purpose': 'saved_card',
                },
            )
            return {
                'ok': True,
                'provider': 'stripe',
                'client_secret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id,
            }
        except Exception as e:
            logger.error(f'User setup intent creation failed: {str(e)}')
            return {
                'ok': False,
                'error': f'Failed to create setup intent: {str(e)}'
            }

    def confirm_user_payment_method(self, *, user, setup_intent_id, payment_method_id):
        """
        Persist a user-level payment method after Stripe setup completes and run a £0.30 verification hold.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        if not setup_intent_id and not payment_method_id:
            return {
                'ok': False,
                'error': 'Missing SetupIntent/payment method details from Stripe confirmation.'
            }

        try:
            pm_obj = None
            if setup_intent_id:
                setup_intent = stripe.SetupIntent.retrieve(
                    setup_intent_id,
                    expand=['payment_method'],
                )
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
            card_funding = (getattr(card_data, 'funding', None) or '').lower()
            card_last4 = getattr(card_data, 'last4', None) or 'xxxx'
            stripe_setup_intent_id = setup_intent_id or ''
            stripe_payment_method_id = payment_method_id
            cardholder_name = getattr(billing, 'name', None) or user.get_full_name() or user.username

            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                metadata={'user_id': str(user.id)},
            )
            customer_id = getattr(customer, 'id', None)

            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )

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
                    'user_id': str(user.id),
                    'purpose': 'saved_card_verification',
                },
            )

            vi_status = getattr(verify_intent, 'status', None)
            test_reference = getattr(verify_intent, 'id', None)
            if vi_status == 'requires_capture':
                canceled = stripe.PaymentIntent.cancel(getattr(verify_intent, 'id', None))
                test_reference = getattr(canceled, 'id', test_reference)
            elif vi_status not in ('succeeded', 'processing'):
                return {
                    'ok': False,
                    'error': f'Card verification authorization failed (status: {vi_status}).'
                }

            from account.models import PaymentMethod

            PaymentMethod.objects.update_or_create(
                stripe_payment_method_id=stripe_payment_method_id,
                defaults={
                    'user': user,
                    'stripe_setup_intent_id': stripe_setup_intent_id,
                    'card_brand': card_brand,
                    'card_funding': card_funding,
                    'card_last4': card_last4,
                },
            )

            return {
                'ok': True,
                'provider': 'stripe',
                'card_brand': card_brand,
                'card_funding': card_funding,
                'card_last4': card_last4,
                'cardholder_name': cardholder_name,
                'test_hold_status': 'success',
                'test_hold_amount': 0.30,
                'test_hold_reference': test_reference,
                'stripe_customer_id': customer_id,
                'stripe_setup_intent_id': stripe_setup_intent_id,
                'stripe_payment_method_id': stripe_payment_method_id,
            }
        except Exception as exc:
            logger.exception('Stripe user card confirmation failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to confirm Stripe card setup: {str(exc)}'
            }

    def confirm_card_setup(self, *, transaction, setup_intent_id, payment_method_id):
        """
        Confirm card setup after Stripe Elements submission.
        Extract card details and run £0.30 test hold.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

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
            card_funding = (getattr(card_data, 'funding', None) or '').lower()
            card_last4 = getattr(card_data, 'last4', None) or 'xxxx'
            cardholder_name = getattr(billing, 'name', None) or 'Stripe'

            if self._long_rental_requires_credit_or_mastercard(transaction):
                if not self._is_deposit_card_allowed_for_long_rental(card_brand, card_funding):
                    return {
                        'ok': False,
                        'error': 'Long rentals require a Visa or Mastercard credit card for the deposit.'
                    }

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
                'card_funding': card_funding,
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
        Prepare card details and run a Stripe £0.30 test hold.
        Returns dict with fields required by the transaction view.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        return {
            'ok': False,
            'error': 'Direct card setup is not supported here. Use the Stripe SetupIntent flow.'
        }

    def collect_deposit_hold(self, *, transaction):
        """
        Trigger full deposit authorization hold/retrieval.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        deposit_minor = self._to_minor_units(transaction.deposit)
        if deposit_minor <= 0:
            return {
                'ok': True,
                'provider': 'stripe',
                'collection_status': transaction.COLLECT_SUCCESS,
                'collection_requested_at': timezone.now(),
                'collection_reference': '',
                'payment_intent_status': 'not_required',
            }

        try:
            existing_reference = (transaction.deposit_collection_reference or '').strip()
            if existing_reference:
                existing_intent = stripe.PaymentIntent.retrieve(existing_reference)
                existing_status = getattr(existing_intent, 'status', '')
                if existing_status in ('requires_capture', 'succeeded', 'processing'):
                    return {
                        'ok': True,
                        'provider': 'stripe',
                        'collection_status': transaction.COLLECT_SUCCESS,
                        'collection_requested_at': transaction.deposit_collection_requested_at or timezone.now(),
                        'collection_reference': existing_reference,
                        'payment_intent_status': existing_status,
                    }

            payment_method_id, customer_id, attach_error = self._ensure_customer_and_payment_method(
                stripe,
                transaction=transaction,
            )
            if attach_error:
                return attach_error

            intent = stripe.PaymentIntent.create(
                amount=deposit_minor,
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
                    'purpose': 'deposit_hold',
                    'delivery_cost': f'{float(getattr(transaction, "delivery_cost", 0) or 0):.2f}',
                    'rentalution_fee': f'{float(getattr(transaction, "rentalution_fee", 0) or 0):.2f}',
                },
            )

            status = getattr(intent, 'status', '')
            if status not in ('requires_capture', 'succeeded', 'processing'):
                return {
                    'ok': False,
                    'error': f'Deposit authorization failed (status: {status}).'
                }

            return {
                'ok': True,
                'provider': 'stripe',
                'collection_status': transaction.COLLECT_SUCCESS,
                'collection_requested_at': timezone.now(),
                'collection_reference': getattr(intent, 'id', ''),
                'payment_intent_status': status,
                'stripe_customer_id': customer_id,
            }
        except Exception as exc:
            logger.exception('Stripe deposit hold collection failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to collect deposit hold: {str(exc)}'
            }

    def collect_rental_payment(self, *, transaction):
        """
        Capture rental payment (rental + delivery + Rentalution fee) at rental start.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        total_minor = self._rental_total_minor(transaction)
        if total_minor <= 0:
            return {
                'ok': True,
                'provider': 'stripe',
                'payment_status': transaction.PAYMENT_NOT_REQUIRED,
                'collection_requested_at': timezone.now(),
                'collection_reference': '',
                'payment_intent_status': 'not_required',
                'charged_amount': 0.0,
            }

        try:
            existing_reference = (transaction.payment_collection_reference or '').strip()
            if existing_reference:
                existing_intent = stripe.PaymentIntent.retrieve(existing_reference)
                existing_status = getattr(existing_intent, 'status', '')
                if existing_status in ('succeeded', 'processing', 'requires_capture'):
                    return {
                        'ok': True,
                        'provider': 'stripe',
                        'payment_status': transaction.PAYMENT_CAPTURED_PLACEHOLDER,
                        'collection_requested_at': transaction.payment_collection_requested_at or timezone.now(),
                        'collection_reference': existing_reference,
                        'payment_intent_status': existing_status,
                        'charged_amount': total_minor / 100.0,
                    }

            payment_method_id, customer_id, attach_error = self._ensure_customer_and_payment_method(
                stripe,
                transaction=transaction,
            )
            if attach_error:
                return attach_error

            intent = stripe.PaymentIntent.create(
                amount=total_minor,
                currency='gbp',
                customer=customer_id,
                payment_method=payment_method_id,
                confirmation_method='automatic',
                confirm=True,
                off_session=True,
                metadata={
                    'transaction_id': str(transaction.id),
                    'transaction_reference': transaction.transaction_reference,
                    'purpose': 'rental_payment',
                    'rental_price': f'{float((transaction.quantity or 0) * (transaction.price or 0)):.2f}',
                    'delivery_cost': f'{float(getattr(transaction, "delivery_cost", 0) or 0):.2f}',
                    'rentalution_fee': f'{float(getattr(transaction, "rentalution_fee", 0) or 0):.2f}',
                },
            )

            status = getattr(intent, 'status', '')
            if status not in ('succeeded', 'processing', 'requires_capture'):
                return {
                    'ok': False,
                    'error': f'Rental payment capture failed (status: {status}).'
                }

            return {
                'ok': True,
                'provider': 'stripe',
                'payment_status': transaction.PAYMENT_CAPTURED_PLACEHOLDER,
                'collection_requested_at': timezone.now(),
                'collection_reference': getattr(intent, 'id', ''),
                'payment_intent_status': status,
                'stripe_customer_id': customer_id,
                'charged_amount': total_minor / 100.0,
            }
        except Exception as exc:
            logger.exception('Stripe rental payment capture failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to capture rental payment: {str(exc)}'
            }

    def resolve_deposit_hold(self, *, transaction, return_amount):
        """
        Settle an existing manual-capture deposit hold after return outcome.

        return_amount is the amount returned to borrower. The charged amount is:
        deposit - return_amount.
        """
        deposit_minor = self._to_minor_units(transaction.deposit)
        return_minor = self._to_minor_units(return_amount)
        if return_minor > deposit_minor:
            return_minor = deposit_minor
        charge_minor = max(0, deposit_minor - return_minor)

        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        reference = (transaction.deposit_collection_reference or '').strip()
        if not reference:
            return {
                'ok': False,
                'error': 'No Stripe deposit hold reference is stored on this transaction.'
            }

        try:
            intent = stripe.PaymentIntent.retrieve(reference)
            status = getattr(intent, 'status', '')
            captured_minor = int(getattr(intent, 'amount_received', 0) or 0)

            if status == 'requires_capture':
                if charge_minor == 0:
                    canceled = stripe.PaymentIntent.cancel(reference)
                    return {
                        'ok': True,
                        'provider': 'stripe',
                        'resolution_action': 'release_hold',
                        'resolution_reference': getattr(canceled, 'id', reference),
                        'charged_amount': 0.0,
                        'returned_amount': return_minor / 100.0,
                        'payment_intent_status': getattr(canceled, 'status', 'canceled'),
                    }

                captured = stripe.PaymentIntent.capture(
                    reference,
                    amount_to_capture=charge_minor,
                )
                capture_action = 'capture_full' if charge_minor == deposit_minor else 'capture_partial'
                return {
                    'ok': True,
                    'provider': 'stripe',
                    'resolution_action': capture_action,
                    'resolution_reference': getattr(captured, 'id', reference),
                    'charged_amount': charge_minor / 100.0,
                    'returned_amount': return_minor / 100.0,
                    'payment_intent_status': getattr(captured, 'status', ''),
                }

            if status in ('succeeded', 'processing'):
                # Already captured: use refund to match intended final charge.
                if charge_minor >= captured_minor:
                    return {
                        'ok': True,
                        'provider': 'stripe',
                        'resolution_action': 'already_captured',
                        'resolution_reference': reference,
                        'charged_amount': captured_minor / 100.0,
                        'returned_amount': max(0, (captured_minor - charge_minor)) / 100.0,
                        'payment_intent_status': status,
                    }

                refund_minor = captured_minor - charge_minor
                refund = stripe.Refund.create(
                    payment_intent=reference,
                    amount=refund_minor,
                    metadata={
                        'transaction_id': str(transaction.id),
                        'transaction_reference': transaction.transaction_reference,
                        'purpose': 'deposit_settlement_refund',
                        'delivery_cost': f'{float(getattr(transaction, "delivery_cost", 0) or 0):.2f}',
                        'rentalution_fee': f'{float(getattr(transaction, "rentalution_fee", 0) or 0):.2f}',
                    },
                )
                refund_action = 'refund_full' if charge_minor == 0 else 'refund_partial'
                return {
                    'ok': True,
                    'provider': 'stripe',
                    'resolution_action': refund_action,
                    'resolution_reference': getattr(refund, 'id', reference),
                    'charged_amount': charge_minor / 100.0,
                    'returned_amount': refund_minor / 100.0,
                    'payment_intent_status': status,
                }

            if status == 'canceled':
                if charge_minor > 0:
                    return {
                        'ok': False,
                        'error': 'Deposit hold has already been canceled; cannot charge deposit now.'
                    }
                return {
                    'ok': True,
                    'provider': 'stripe',
                    'resolution_action': 'already_released',
                    'resolution_reference': reference,
                    'charged_amount': 0.0,
                    'returned_amount': return_minor / 100.0,
                    'payment_intent_status': status,
                }

            return {
                'ok': False,
                'error': f'Unsupported PaymentIntent status for settlement: {status}'
            }
        except Exception as exc:
            logger.exception('Stripe deposit settlement failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to resolve deposit hold: {str(exc)}'
            }

    def refund_rental_payment(self, *, transaction, refund_amount):
        """
        Refund part of the rental payment so dispute resolution can offset the
        lender payout against the original product-fee payment.
        """
        refund_minor = self._to_minor_units(refund_amount)
        if refund_minor <= 0:
            return {
                'ok': True,
                'provider': 'stripe',
                'refund_action': 'none',
                'refund_reference': '',
                'refunded_amount': 0.0,
            }

        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

        reference = (transaction.payment_collection_reference or '').strip()
        if not reference:
            return {
                'ok': False,
                'error': 'No Stripe payment reference is stored on this transaction.'
            }

        try:
            refund = stripe.Refund.create(
                payment_intent=reference,
                amount=refund_minor,
                metadata={
                    'transaction_id': str(transaction.id),
                    'transaction_reference': transaction.transaction_reference,
                    'purpose': 'dispute_payment_offset_refund',
                },
            )
            return {
                'ok': True,
                'provider': 'stripe',
                'refund_action': 'refund_partial' if refund_minor > 0 else 'none',
                'refund_reference': getattr(refund, 'id', reference),
                'refunded_amount': refund_minor / 100.0,
            }
        except Exception as exc:
            logger.exception('Stripe rental payment refund failed: %s', exc)
            return {
                'ok': False,
                'error': f'Failed to refund rental payment: {str(exc)}'
            }

    def process_webhook(self, *, payload, signature):
        """
        Webhook scaffold for Stripe Connect events.
        """
        stripe, stripe_error = self._load_stripe_client()
        if stripe_error:
            return stripe_error

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
