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
        for args in [[], ['--reset'], ['--commence-today'], ['--finish-today']]:
            with self.subTest(args=args), self.assertRaisesMessage(CommandError, 'disabled in production'):
                call_command('seed_transaction_scenarios', *args, stdout=StringIO())
        self.assertTrue(Transaction.objects.filter(pk=txn.pk).exists())

    def test_modes_are_mutually_exclusive(self):
        with self.assertRaises(CommandError):
            call_command('seed_transaction_scenarios', '--reset', '--finish-today', stdout=StringIO())
