from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from account.models import Profile
from common.models import Category, Order, Product
from transaction.models import StripeSettlement, Transaction
from transaction.stripe_connect import StripeConnectService


@override_settings(STRIPE_CONNECT_SECRET_KEY='sk_test_connect', STRIPE_CONNECT_WEBHOOK_SECRET='whsec_test_connect')
class StripeConnectServiceTests(TestCase):
    def setUp(self):
        self.lender = User.objects.create_user('connect-lender', 'lender@example.test', 'x')
        self.renter = User.objects.create_user('connect-renter', 'renter@example.test', 'x')
        self.profile = Profile.objects.create(
            user=self.lender, date_of_birth=date(1990, 1, 1), mobile_number='07123456789',
            address_line_1='1 Test Street', town='London', postcode='SW1A 1AA',
        )
        category = Category.objects.create(title='Connect tests')
        product = Product.objects.create(category_id=category, name='Camera')
        order = Order.objects.create(
            product=product, user=self.lender, direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=30), status=Order.ACTIVE,
            price=20, deposit=0, postcode='SW1A 1AA', max_rental_days=30,
        )
        self.transaction = Transaction.objects.create(
            user_passive=self.lender, user_aggressive=self.renter, order_passive=order,
            product=product, price=20, quantity=1, delivery_cost=5, rentalution_fee=2.5,
            deposit=0, current_spot_value=100, price_as_pct_spot_value=20,
            payment_collection_reference='pi_rental', return_handover_verified_at=timezone.now(),
        )
        self.service = StripeConnectService()

    def test_account_update_syncs_lender_transfer_state(self):
        self.service.sync_connected_account(SimpleNamespace(
            id='acct_connect', metadata={'profile_id': str(self.profile.id)},
            capabilities={'transfers': 'active'}, payouts_enabled=True,
            requirements={'currently_due': ['external_account']},
        ))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_connect_account_id, 'acct_connect')
        self.assertTrue(self.profile.stripe_connect_transfers_enabled)
        self.assertTrue(self.profile.stripe_connect_payouts_enabled)
        self.assertEqual(self.profile.stripe_connect_requirements, ['external_account'])

    def test_signed_account_updated_webhook_syncs_lender_state(self):
        stripe = Mock()
        stripe.Webhook.construct_event.return_value = SimpleNamespace(
            type='account.updated',
            data=SimpleNamespace(object=SimpleNamespace(
                id='acct_signed', metadata={'profile_id': str(self.profile.id)},
                capabilities={'transfers': 'active'}, payouts_enabled=True,
                requirements={'currently_due': []},
            )),
        )
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.process_webhook(payload=b'{}', signature='signed')
        self.assertTrue(result['ok'])
        self.assertEqual(result['event_type'], 'account.updated')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_connect_account_id, 'acct_signed')

    def test_onboarding_reuses_saved_account_and_creates_single_use_link(self):
        self.profile.stripe_connect_account_id = 'acct_existing'
        self.profile.save(update_fields=['stripe_connect_account_id'])
        stripe = Mock()
        stripe.AccountLink.create.return_value = SimpleNamespace(url='https://connect.stripe.test/link')
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.create_lender_onboarding_link(
                profile=self.profile, refresh_url='https://app.test/refresh', return_url='https://app.test/return',
            )
        self.assertTrue(result['ok'])
        self.assertEqual(result['url'], 'https://connect.stripe.test/link')
        stripe.Account.create.assert_not_called()
        stripe.AccountLink.create.assert_called_once()

    def test_transfer_requires_enabled_lender_account(self):
        result = self.service.transfer_rental_proceeds(transaction=self.transaction)
        self.assertFalse(result['ok'])
        self.assertIn('not enabled', result['error'])

    def test_transfer_is_idempotent_and_tied_to_original_charge(self):
        self.profile.stripe_connect_account_id = 'acct_enabled'
        self.profile.stripe_connect_transfers_enabled = True
        self.profile.save(update_fields=['stripe_connect_account_id', 'stripe_connect_transfers_enabled'])
        stripe = Mock()
        stripe.PaymentIntent.retrieve.return_value = SimpleNamespace(latest_charge='ch_rental')
        stripe.Transfer.create.return_value = SimpleNamespace(id='tr_rental')
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.transfer_rental_proceeds(transaction=self.transaction)
            repeated = self.service.transfer_rental_proceeds(transaction=self.transaction)
        self.assertTrue(result['ok'])
        self.assertTrue(repeated['existing'])
        stripe.Transfer.create.assert_called_once()
        self.assertEqual(stripe.Transfer.create.call_args.kwargs['source_transaction'], 'ch_rental')
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.stripe_rental_transfer_id, 'tr_rental')
        self.assertEqual(self.transaction.stripe_rental_transfer_amount, 25)
        settlement = StripeSettlement.objects.get(transaction=self.transaction, kind='rental')
        self.assertEqual(settlement.transfer_id, 'tr_rental')
        self.assertEqual(settlement.net_transfer_amount, 25)

    def test_deposit_award_deducts_actual_fee_before_lender_transfer(self):
        self.profile.stripe_connect_account_id = 'acct_enabled'
        self.profile.stripe_connect_transfers_enabled = True
        self.profile.save(update_fields=['stripe_connect_account_id', 'stripe_connect_transfers_enabled'])
        stripe = Mock()
        stripe.PaymentIntent.retrieve.return_value = SimpleNamespace(latest_charge='ch_deposit')
        stripe.Charge.retrieve.return_value = SimpleNamespace(
            id='ch_deposit', balance_transaction=SimpleNamespace(id='txn_fee', fee=150, net=850),
        )
        stripe.Transfer.create.return_value = SimpleNamespace(id='tr_deposit')
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.transfer_deposit_award(
                transaction=self.transaction, payment_intent_id='pi_deposit', award_amount=10,
            )
        self.assertTrue(result['ok'])
        self.assertEqual(stripe.Transfer.create.call_args.kwargs['amount'], 850)
        settlement = StripeSettlement.objects.get(transaction=self.transaction, kind='deposit')
        self.assertEqual(settlement.stripe_fee, 1.5)
        self.assertEqual(settlement.net_transfer_amount, 8.5)

    def test_deposit_award_smaller_than_fee_records_shortfall_without_transfer(self):
        self.profile.stripe_connect_account_id = 'acct_enabled'
        self.profile.stripe_connect_transfers_enabled = True
        self.profile.save(update_fields=['stripe_connect_account_id', 'stripe_connect_transfers_enabled'])
        stripe = Mock()
        stripe.PaymentIntent.retrieve.return_value = SimpleNamespace(latest_charge='ch_deposit')
        stripe.Charge.retrieve.return_value = SimpleNamespace(
            id='ch_deposit', balance_transaction=SimpleNamespace(id='txn_fee', fee=150, net=0),
        )
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.transfer_deposit_award(
                transaction=self.transaction, payment_intent_id='pi_deposit', award_amount=1,
            )
        self.assertTrue(result['ok'])
        stripe.Transfer.create.assert_not_called()
        settlement = StripeSettlement.objects.get(transaction=self.transaction, kind='deposit')
        self.assertEqual(settlement.platform_shortfall, 0.5)

    def test_full_deposit_release_creates_zero_value_settlement_without_stripe_transfer(self):
        result = self.service.transfer_deposit_award(
            transaction=self.transaction, payment_intent_id='pi_deposit', award_amount=0,
        )
        self.assertTrue(result['ok'])
        self.assertTrue(result['no_transfer'])
        settlement = StripeSettlement.objects.get(transaction=self.transaction, kind='deposit')
        self.assertEqual(settlement.status, StripeSettlement.STATUS_SUCCEEDED)
        self.assertEqual(settlement.gross_amount, 0)

    def test_card_confirmation_reuses_an_already_attached_payment_method(self):
        stripe = Mock()
        stripe.SetupIntent.retrieve.return_value = SimpleNamespace(status='succeeded', payment_method='pm_attached')
        stripe.PaymentMethod.retrieve.return_value = SimpleNamespace(
            customer='cus_existing',
            card=SimpleNamespace(brand='visa', funding='credit', last4='4242'),
            billing_details=SimpleNamespace(name='Test Renter'),
        )
        stripe.PaymentIntent.create.return_value = SimpleNamespace(status='requires_capture', id='pi_verify')
        stripe.PaymentIntent.cancel.return_value = SimpleNamespace(id='pi_verify')
        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.confirm_card_setup(
                transaction=self.transaction, setup_intent_id='seti_done', payment_method_id='pm_attached',
            )
        self.assertTrue(result['ok'])
        self.assertEqual(result['stripe_customer_id'], 'cus_existing')
        stripe.Customer.create.assert_not_called()
        stripe.PaymentMethod.attach.assert_not_called()
        self.assertEqual(
            stripe.PaymentIntent.create.call_args.kwargs['idempotency_key'],
            f'deposit-card-verification-{self.transaction.id}-pm_attached',
        )

    def test_card_confirmation_accepts_a_concurrently_cancelled_verification_hold(self):
        stripe = Mock()
        stripe.SetupIntent.retrieve.return_value = SimpleNamespace(status='succeeded', payment_method='pm_attached')
        stripe.PaymentMethod.retrieve.return_value = SimpleNamespace(
            customer='cus_existing',
            card=SimpleNamespace(brand='visa', funding='credit', last4='4242'),
            billing_details=SimpleNamespace(name='Test Renter'),
        )
        stripe.PaymentIntent.create.return_value = SimpleNamespace(status='requires_capture', id='pi_verify')
        stripe.PaymentIntent.cancel.side_effect = RuntimeError('already canceled')
        stripe.PaymentIntent.retrieve.return_value = SimpleNamespace(status='canceled', id='pi_verify')

        with patch.object(self.service, '_load_stripe_client', return_value=(stripe, None)):
            result = self.service.confirm_card_setup(
                transaction=self.transaction, setup_intent_id='seti_done', payment_method_id='pm_attached',
            )

        self.assertTrue(result['ok'])
