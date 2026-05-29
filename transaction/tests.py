from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.models import Category, Order, OrderBlockedDate, Product
from transaction.models import Transaction, TransactionFeedback, TransactionMessage


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


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class WebTransactionWorkflowExtensionTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(title='Garden')
		self.product = Product.objects.create(
			category_id=self.category,
			name='Hedge Trimmer',
		)
		self.lender = User.objects.create_user(
			username='workflow-lender',
			email='workflow-lender@example.com',
			password='x',
		)
		self.renter = User.objects.create_user(
			username='workflow-renter',
			email='workflow-renter@example.com',
			password='x',
		)
		self.order = Order.objects.create(
			product=self.product,
			user=self.lender,
			direction=Order.TO_LET,
			expiry_date=timezone.now() + timedelta(days=30),
			status=Order.ACTIVE,
			price=20,
			deposit=100,
			postcode='SW1A1AA',
		)

	def _create_txn(self, *, status, start_offset_days, end_offset_days):
		start = timezone.now().date() + timedelta(days=start_offset_days)
		end = timezone.now().date() + timedelta(days=end_offset_days)
		return Transaction.objects.create(
			user_passive=self.lender,
			user_aggressive=self.renter,
			order_passive=self.order,
			product=self.product,
			transaction_status=status,
			prev_transaction_status=Transaction.RENTAL_ENQUIRY,
			rental_start_date=start,
			rental_end_date=end,
			price=20,
			deposit=100,
			current_spot_value=100,
			price_as_pct_spot_value=20,
		)

	def test_report_missing_rental_voids_and_allows_borrower_feedback(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_AGREED,
			start_offset_days=-2,
			end_offset_days=1,
		)

		self.client.force_login(self.renter)
		response = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'report_missing_rental',
				'missing_rental_reason': 'No handover happened.',
			},
		)
		self.assertEqual(response.status_code, 302)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)
		self.assertEqual(txn.deposit_status, Transaction.DEPOSIT_MEDIATION)
		self.assertIn('[MISSING_RENTAL_VOIDED]', txn.deposit_resolution_notes)

		feedback_response = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'submit_feedback',
				'communication_rating': '4',
				'delivery_return_rating': '1',
				'overall_rating': '2',
				'feedback_comment': 'Rental never started.',
			},
		)
		self.assertEqual(feedback_response.status_code, 302)
		self.assertTrue(
			TransactionFeedback.objects.filter(
				transaction=txn,
				left_by=self.renter,
				left_for=self.lender,
			).exists()
		)

	def test_report_missing_return_escalates_to_dispute(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_ONGOING,
			start_offset_days=-6,
			end_offset_days=-1,
		)

		self.client.force_login(self.lender)
		response = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'report_missing_return',
				'missing_return_reason': 'Item not returned.',
			},
		)
		self.assertEqual(response.status_code, 302)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)
		self.assertEqual(txn.deposit_status, Transaction.DEPOSIT_MEDIATION)

	def test_deposit_proposal_cycle_cap_blocks_sixth_proposal_and_auto_escalates_contest(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
			start_offset_days=-10,
			end_offset_days=-5,
		)

		for idx in range(5):
			TransactionMessage.objects.create(
				user_from=self.lender,
				user_to=self.renter,
				transaction=txn,
				subject=f'Deposit return proposal {txn.transaction_reference}',
				description=f'Iteration {idx + 1}',
				is_system_generated=True,
			)

		txn.deposit_proposed_by_lender_at = timezone.now()
		txn.save(update_fields=['deposit_proposed_by_lender_at'])

		self.client.force_login(self.lender)
		blocked_response = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'propose_deposit_return',
				'deposit_proposed_return_amount': '50.00',
				'deposit_resolution_notes': 'Sixth proposal',
			},
			follow=True,
		)
		self.assertEqual(blocked_response.status_code, 200)
		self.assertContains(blocked_response, 'Maximum deposit proposal iterations reached')

		self.client.force_login(self.renter)
		escalate_response = self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'contest_deposit_return',
				'deposit_resolution_notes': 'Still disagree after max cycles.',
			},
		)
		self.assertEqual(escalate_response.status_code, 302)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)

