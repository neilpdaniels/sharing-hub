from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.models import Category, Order, OrderBlockedDate, Product
from transaction.models import Transaction


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class WebTransactionDateHoldTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(title='Instruments')
		self.product = Product.objects.create(
			category_id=self.category,
			name='Synthesizer',
		)
		self.lender = User.objects.create_user(
			username='site-lender',
			email='site-lender@example.com',
			password='x',
		)
		self.renter_one = User.objects.create_user(
			username='site-renter-one',
			email='site-renter-one@example.com',
			password='x',
		)
		self.renter_two = User.objects.create_user(
			username='site-renter-two',
			email='site-renter-two@example.com',
			password='x',
		)
		self.order = Order.objects.create(
			product=self.product,
			user=self.lender,
			direction=Order.TO_LET,
			expiry_date=timezone.now() + timedelta(days=30),
			status=Order.ACTIVE,
			price=20,
			postcode='SW1A1AA',
			max_rental_days=14,
		)

	def _date_range(self, start_offset, end_offset):
		start = timezone.now().date() + timedelta(days=start_offset)
		end = timezone.now().date() + timedelta(days=end_offset)
		return start, end

	@patch('transaction.views.verify_turnstile_token', return_value=True)
	def test_enquiry_blocks_dates_and_reject_releases_for_site_flow(self, _mock_turnstile):
		start, end = self._date_range(5, 7)

		self.client.force_login(self.renter_one)
		create_one = self.client.post(
			reverse('transaction:hit_order', kwargs={'order_id': self.order.id}),
			{
				'rental_start_date': start.isoformat(),
				'rental_end_date': end.isoformat(),
				'enquiry_message': 'Can I rent this next week?',
				'cf-turnstile-response': 'ok',
			},
		)
		self.assertEqual(create_one.status_code, 302)

		txn = Transaction.objects.get(order_passive=self.order, user_aggressive=self.renter_one)
		self.assertEqual(txn.transaction_status, Transaction.RENTAL_ENQUIRY)

		blocked_count = OrderBlockedDate.objects.filter(
			order=self.order,
			reason=OrderBlockedDate.BOOKED,
			date__gte=start,
			date__lte=end,
		).count()
		self.assertEqual(blocked_count, 3)

		self.client.force_login(self.renter_two)
		overlapping_attempt = self.client.post(
			reverse('transaction:hit_order', kwargs={'order_id': self.order.id}),
			{
				'rental_start_date': start.isoformat(),
				'rental_end_date': end.isoformat(),
				'enquiry_message': 'Trying the same dates.',
				'cf-turnstile-response': 'ok',
			},
		)
		self.assertEqual(overlapping_attempt.status_code, 200)
		self.assertEqual(Transaction.objects.filter(order_passive=self.order).count(), 1)

		self.client.force_login(self.lender)
		reject = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{'action': 'reject_enquiry'},
		)
		self.assertEqual(reject.status_code, 302)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)

		released_count = OrderBlockedDate.objects.filter(
			order=self.order,
			reason=OrderBlockedDate.BOOKED,
			date__gte=start,
			date__lte=end,
		).count()
		self.assertEqual(released_count, 0)

	@patch('transaction.views.verify_turnstile_token', return_value=True)
	def test_enquiry_blocks_dates_and_renter_cancellation_releases_them(self, _mock_turnstile):
		start, end = self._date_range(10, 12)

		self.client.force_login(self.renter_one)
		create_one = self.client.post(
			reverse('transaction:hit_order', kwargs={'order_id': self.order.id}),
			{
				'rental_start_date': start.isoformat(),
				'rental_end_date': end.isoformat(),
				'enquiry_message': 'Please reserve these dates.',
				'cf-turnstile-response': 'ok',
			},
		)
		self.assertEqual(create_one.status_code, 302)

		txn = Transaction.objects.get(order_passive=self.order, user_aggressive=self.renter_one)

		blocked_count = OrderBlockedDate.objects.filter(
			order=self.order,
			reason=OrderBlockedDate.BOOKED,
			date__gte=start,
			date__lte=end,
		).count()
		self.assertEqual(blocked_count, 3)

		cancel = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'request_cancellation',
				'cancellation_reason': 'Plans changed.',
			},
		)
		self.assertEqual(cancel.status_code, 302)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)

		released_count = OrderBlockedDate.objects.filter(
			order=self.order,
			reason=OrderBlockedDate.BOOKED,
			date__gte=start,
			date__lte=end,
		).count()
		self.assertEqual(released_count, 0)
