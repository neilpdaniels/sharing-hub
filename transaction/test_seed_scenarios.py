from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from common.models import Category, Order, OrderBlockedDate, Product
from transaction.models import Transaction, TransactionMessage


@override_settings(ENVIRONMENT_NAME='dev server')
class ScenarioDateCommandTests(TestCase):
    def setUp(self):
        self.lender = User.objects.create_user(username='date-lender', email='date-lender@example.test')
        self.renter = User.objects.create_user(username='date-renter', email='date-renter@example.test')
        category = Category.objects.create(title='Date tests')
        self.product = Product.objects.create(category_id=category, name='Date test drill')
        self.order = Order.objects.create(product=self.product, user=self.lender,
                                          direction=Order.TO_LET, price=0, deposit=0,
                                          expiry_date=timezone.now() + timedelta(days=90))
        self.today = Transaction.workflow_today()

    def make_txn(self, marker='SCENARIO:scenario-ongoing', start=-5, end=-3):
        return Transaction.objects.create(
            user_passive=self.lender, user_aggressive=self.renter,
            order_passive=self.order, product=self.product,
            transpact_text_status=marker,
            transaction_status=Transaction.RENTAL_ONGOING,
            prev_transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
            rental_start_date=self.today + timedelta(days=start),
            rental_end_date=self.today + timedelta(days=end),
            price=0, deposit=0, current_spot_value=100, price_as_pct_spot_value=0,
            checkout_handover_pin='123456',
            checkout_condition_video_url='https://example.test/checkout.mp4',
        )

    def run_command(self, flag):
        output = StringIO()
        call_command('seed_transaction_scenarios', flag, stdout=output)
        return output.getvalue()

    def test_commence_today_preserves_duration_progress_and_non_scenarios(self):
        txn = self.make_txn()
        other = self.make_txn(marker='Real transaction')
        unknown = self.make_txn(marker='SCENARIO:not-a-seeded-scenario')
        messages_before = TransactionMessage.objects.count()
        result = self.run_command('--commence-today')
        txn.refresh_from_db()
        other.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(txn.rental_start_date, self.today)
        self.assertEqual(txn.rental_end_date, self.today + timedelta(days=2))
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_ONGOING)
        self.assertEqual(txn.prev_transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        self.assertEqual(txn.checkout_handover_pin, '123456')
        self.assertEqual(txn.checkout_condition_video_url, 'https://example.test/checkout.mp4')
        self.assertEqual(other.rental_start_date, self.today - timedelta(days=5))
        self.assertEqual(unknown.rental_start_date, self.today - timedelta(days=5))
        self.assertEqual(TransactionMessage.objects.count(), messages_before)
        self.assertIn('Updated 1 scenario transactions', result)

    def test_finish_today_preserves_long_and_single_day_ranges(self):
        long = self.make_txn(start=5, end=36)
        single = self.make_txn(marker='SCENARIO:scenario-zero-cost', start=3, end=3)
        self.run_command('--finish-today')
        long.refresh_from_db()
        single.refresh_from_db()
        self.assertEqual(long.rental_start_date, self.today - timedelta(days=31))
        self.assertEqual(long.rental_end_date, self.today)
        self.assertEqual(single.rental_start_date, self.today)
        self.assertEqual(single.rental_end_date, self.today)
        self.assertIn('submit_return_borrower_evidence', long.get_allowed_actions_for_user(self.renter))

    def test_moves_booked_dates_but_preserves_manual_and_other_rental_holds(self):
        txn = self.make_txn()
        self.make_txn(marker='Real transaction', start=-5, end=-5)
        for offset in [-5, -4]:
            OrderBlockedDate.objects.create(order=self.order,
                date=self.today + timedelta(days=offset), reason=OrderBlockedDate.BOOKED)
        OrderBlockedDate.objects.create(order=self.order, date=self.today - timedelta(days=3),
                                        reason=OrderBlockedDate.MANUAL)
        self.run_command('--commence-today')
        rows = dict(self.order.blocked_dates.values_list('date', 'reason'))
        self.assertEqual(rows[self.today - timedelta(days=5)], OrderBlockedDate.BOOKED)
        self.assertNotIn(self.today - timedelta(days=4), rows)
        self.assertEqual(rows[self.today - timedelta(days=3)], OrderBlockedDate.MANUAL)
        for offset in range(3):
            self.assertEqual(rows[self.today + timedelta(days=offset)], OrderBlockedDate.BOOKED)

    def test_invalid_range_prevents_partial_updates(self):
        good = self.make_txn()
        bad = self.make_txn(marker='SCENARIO:scenario-return', start=5, end=2)
        with self.assertRaisesMessage(CommandError, 'No dates were changed'):
            self.run_command('--finish-today')
        good.refresh_from_db()
        self.assertEqual(good.rental_start_date, self.today - timedelta(days=5))
        self.assertFalse(self.order.blocked_dates.exists())

    def test_date_modes_do_not_create_missing_scenarios(self):
        count = User.objects.count()
        self.assertIn('Seed scenarios first', self.run_command('--commence-today'))
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(User.objects.count(), count)

    def test_today_uses_london_date_at_summer_midnight(self):
        txn = self.make_txn()
        now = datetime(2026, 7, 1, 23, 30, tzinfo=dt_timezone.utc)
        with patch('transaction.models.timezone.now', return_value=now):
            self.run_command('--commence-today')
        txn.refresh_from_db()
        self.assertEqual(txn.rental_start_date.isoformat(), '2026-07-02')

    @override_settings(ENVIRONMENT_NAME='Production')
    def test_all_modes_are_disabled_in_production(self):
        txn = self.make_txn()
        for args in [[], ['--reset'], ['--repair'], ['--commence-today'], ['--finish-today']]:
            with self.subTest(args=args), self.assertRaisesMessage(CommandError, 'disabled in production'):
                call_command('seed_transaction_scenarios', *args, stdout=StringIO())
        self.assertTrue(Transaction.objects.filter(pk=txn.pk).exists())

    def test_modes_are_mutually_exclusive(self):
        with self.assertRaises(CommandError):
            call_command('seed_transaction_scenarios', '--reset', '--finish-today', stdout=StringIO())

    def test_specific_dates_target_only_selected_non_scenario_transaction(self):
        txn = self.make_txn(marker='Real transaction')
        other = self.make_txn()
        target = self.today + timedelta(days=20)
        messages_before = TransactionMessage.objects.count()
        for flag in ['--commence-date', '--finish-date']:
            call_command('seed_transaction_scenarios', '--transaction-id', str(txn.pk),
                         flag, target.isoformat(), stdout=StringIO())
            txn.refresh_from_db()
            self.assertEqual(txn.rental_start_date if flag == '--commence-date'
                             else txn.rental_end_date, target)
            self.assertEqual(txn.rental_end_date - txn.rental_start_date, timedelta(days=2))
            self.assertEqual(txn.transaction_status, Transaction.RENTAL_ONGOING)
            self.assertEqual(txn.checkout_handover_pin, '123456')
        other.refresh_from_db()
        self.assertEqual(other.rental_start_date, self.today - timedelta(days=5))
        self.assertEqual(TransactionMessage.objects.count(), messages_before)

    def test_targeted_date_validation(self):
        for args in [
            ['--commence-date', '2026-09-15'],
            ['--transaction-id', '1'],
            ['--transaction-id', '1', '--reset'],
            ['--transaction-id', '1', '--finish-date', 'invalid'],
            ['--transaction-id', '1', '--finish-date', '2026-02-30'],
            ['--transaction-id', '1', '--commence-date', '2026-09-15', '--finish-today'],
        ]:
            with self.subTest(args=args), self.assertRaises(CommandError):
                call_command('seed_transaction_scenarios', *args, stdout=StringIO())
        with self.assertRaisesMessage(CommandError, 'does not exist'):
            call_command('seed_transaction_scenarios', '--transaction-id', '999999',
                         '--finish-date', '2026-09-15', stdout=StringIO())
        self.assertFalse(Transaction.objects.exists())

    def test_new_checkout_seed_requires_real_card_setup_before_collection(self):
        from transaction.management.commands.seed_transaction_scenarios import SCENARIOS
        checkout = next(row for row in SCENARIOS if row['name'] == 'scenario-checkout')
        with patch('transaction.management.commands.seed_transaction_scenarios.SCENARIOS', [checkout]):
            call_command('seed_transaction_scenarios', stdout=StringIO())
        txn = Transaction.objects.get(transpact_text_status='SCENARIO:scenario-checkout')
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_AGREED)
        self.assertTrue(txn.lender_agreed_at)
        self.assertTrue(txn.renter_agreed_at)
        self.assertEqual(txn.rental_start_date, self.today)
        self.assertEqual(txn.get_workflow_stage_number(), 4)
        self.assertIn('add_deposit_card', txn.get_allowed_actions_for_user(txn.user_aggressive))
        self.assertNotIn('initiate_rental', txn.get_allowed_actions_for_user(txn.user_passive))
        txn.deposit_card_setup_status = Transaction.CARD_READY
        txn.deposit_test_hold_status = Transaction.TEST_HOLD_SUCCESS
        self.assertEqual(txn.get_workflow_stage_number(), 5)
        self.assertIn('initiate_rental', txn.get_allowed_actions_for_user(txn.user_passive))

    def test_repair_incomplete_checkout_preserves_dates_and_is_idempotent(self):
        txn = self.make_txn(marker='SCENARIO:scenario-checkout', start=0, end=2)
        Transaction.objects.filter(pk=txn.pk).update(
            transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
            checkout_condition_video_url='', checkout_handover_pin='', price=30, deposit=80,
        )
        messages_before = TransactionMessage.objects.count()
        call_command('seed_transaction_scenarios', '--repair', '--transaction-id', str(txn.pk), stdout=StringIO())
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_AGREED)
        self.assertEqual(txn.get_workflow_stage_number(), 4)
        self.assertEqual(txn.rental_start_date, self.today)
        self.assertEqual(txn.rental_end_date, self.today + timedelta(days=2))
        self.assertFalse(txn.has_verified_payment_card())
        original = (txn.lender_agreed_at, txn.renter_agreed_at, txn.amended)
        call_command('seed_transaction_scenarios', '--repair', '--transaction-id', str(txn.pk), stdout=StringIO())
        txn.refresh_from_db()
        self.assertEqual(original, (txn.lender_agreed_at, txn.renter_agreed_at, txn.amended))
        self.assertEqual(TransactionMessage.objects.count(), messages_before)

    def test_repair_preserves_existing_checkout_evidence_and_rejects_non_seed(self):
        txn = self.make_txn(marker='SCENARIO:scenario-checkout')
        Transaction.objects.filter(pk=txn.pk).update(transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        call_command('seed_transaction_scenarios', '--repair', '--transaction-id', str(txn.pk), stdout=StringIO())
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        self.assertEqual(txn.checkout_handover_pin, '123456')
        self.assertEqual(txn.checkout_condition_video_url, 'https://example.test/checkout.mp4')
        other = self.make_txn(marker='Real transaction')
        with self.assertRaisesMessage(CommandError, 'not a known seeded scenario'):
            call_command('seed_transaction_scenarios', '--repair', '--transaction-id', str(other.pk), stdout=StringIO())

    def test_rental_ready_seed_verifies_stripe_test_card_and_is_repeatable(self):
        from types import SimpleNamespace
        from transaction.management.commands.seed_transaction_scenarios import SCENARIOS
        ready = next(row for row in SCENARIOS if row['name'] == 'scenario-rental-ready')
        pm = SimpleNamespace(id='pm_test_seed', customer=None,
                             card=SimpleNamespace(brand='visa', funding='credit', last4='4242'),
                             billing_details=SimpleNamespace(name='Scenario Renter'))
        with override_settings(STRIPE_CONNECT_SECRET_KEY='sk_test_seed'), \
                patch('transaction.management.commands.seed_transaction_scenarios.SCENARIOS', [ready]), \
                patch('stripe.PaymentMethod.create', return_value=pm) as create_method, \
                patch('stripe.PaymentMethod.retrieve', return_value=pm), \
                patch('stripe.PaymentMethod.attach'), \
                patch('stripe.Customer.create', return_value=SimpleNamespace(id='cus_test_seed')), \
                patch('stripe.PaymentIntent.create', return_value=SimpleNamespace(id='pi_test_seed', status='requires_capture')) as hold, \
                patch('stripe.PaymentIntent.cancel', return_value=SimpleNamespace(id='pi_test_seed')) as cancel:
            call_command('seed_transaction_scenarios', stdout=StringIO())
            self.assertFalse(Transaction.objects.exists())
            call_command('seed_transaction_scenarios', '--rental-ready', stdout=StringIO())
            txn = Transaction.objects.get(transpact_text_status='SCENARIO:scenario-rental-ready')
            self.assertEqual(txn.get_workflow_stage_number(), 5)
            self.assertTrue(txn.lender_agreed_at)
            self.assertTrue(txn.renter_agreed_at)
            self.assertEqual(txn.rental_start_date, self.today)
            self.assertEqual(txn.rental_end_date, self.today + timedelta(days=2))
            self.assertTrue(txn.has_verified_payment_card())
            self.assertEqual(txn.stripe_payment_method_id, pm.id)
            self.assertEqual(txn.stripe_customer_id, 'cus_test_seed')
            self.assertEqual(txn.deposit_test_hold_reference, 'pi_test_seed')
            self.assertIsNotNone(txn.deposit_test_hold_at)
            self.assertIn('initiate_rental', txn.get_allowed_actions_for_user(txn.user_passive))
            self.assertFalse(txn.checkout_handover_pin)
            self.assertEqual(hold.call_args.kwargs['amount'], 30)
            cancel.assert_called_once_with('pi_test_seed')
            self.assertEqual(create_method.call_args.kwargs['card'], {'token': 'tok_visa'})
            before = txn.amended
            call_command('seed_transaction_scenarios', '--rental-ready', stdout=StringIO())
            txn.refresh_from_db()
            self.assertEqual(txn.amended, before)
            self.assertEqual(Transaction.objects.count(), 1)
            create_method.assert_called_once()

    def test_rental_ready_rejects_missing_live_keys_and_production_before_creating(self):
        for key in ('', 'sk_live_not_allowed', 'rk_live_not_allowed'):
            with self.subTest(key=key), override_settings(STRIPE_CONNECT_SECRET_KEY=key):
                with self.assertRaisesMessage(CommandError, 'requires STRIPE_CONNECT_SECRET_KEY'):
                    call_command('seed_transaction_scenarios', '--rental-ready', stdout=StringIO())
                self.assertFalse(Transaction.objects.exists())
        with override_settings(ENVIRONMENT_NAME='production', STRIPE_CONNECT_SECRET_KEY='sk_test_seed'):
            with self.assertRaisesMessage(CommandError, 'disabled in production'):
                call_command('seed_transaction_scenarios', '--rental-ready', stdout=StringIO())
        self.assertFalse(Transaction.objects.exists())

    @override_settings(STRIPE_CONNECT_SECRET_KEY='sk_test_seed')
    def test_failed_rental_ready_verification_does_not_mark_card_verified(self):
        from types import SimpleNamespace
        txn = self.make_txn(marker='SCENARIO:scenario-rental-ready', start=0, end=2)
        Transaction.objects.filter(pk=txn.pk).update(transaction_status=Transaction.RENTAL_AGREED,
                                                     price=30, deposit=80)
        with patch('stripe.PaymentMethod.create', return_value=SimpleNamespace(id='pm_test_seed')), \
                patch('transaction.stripe_connect.stripe_connect_service.confirm_card_setup',
                      return_value={'ok': False, 'error': 'Declined'}):
            with self.assertRaisesMessage(CommandError, 'verification failed'):
                call_command('seed_transaction_scenarios', '--rental-ready', stdout=StringIO())
        txn.refresh_from_db()
        self.assertFalse(txn.has_verified_payment_card())
        self.assertFalse(txn.stripe_payment_method_id)
        self.assertFalse(txn.deposit_test_hold_reference)
