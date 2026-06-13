from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.models import Category, Order, OrderBlockedDate, Product
from account.models import Profile
from common.models import System
from transaction.models import Transaction, TransactionFeedback, TransactionMessage
from transaction.tasks import (
    auto_cancel_overdue_first_day_bookings,
    auto_close_feedback_windows,
    escalate_overdue_disputes,
    send_pending_action_reminders,
)


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

	def test_workflow_payload_exposes_user_specific_allowed_actions(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_AGREED,
			start_offset_days=2,
			end_offset_days=5,
		)

		lender_actions = txn.get_allowed_actions_for_user(self.lender)
		renter_actions = txn.get_allowed_actions_for_user(self.renter)

		self.assertIn('confirm_lender_contract', lender_actions)
		self.assertIn('collect_deposit', lender_actions)
		self.assertNotIn('confirm_renter_contract', lender_actions)

		self.assertIn('confirm_renter_contract', renter_actions)
		self.assertIn('add_deposit_card', renter_actions)
		self.assertNotIn('confirm_lender_contract', renter_actions)

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

		txn.deposit_proposal_iteration_count = 5
		txn.deposit_proposed_by_lender_at = timezone.now()
		txn.save(update_fields=['deposit_proposal_iteration_count', 'deposit_proposed_by_lender_at'])

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

	def test_missing_rental_feedback_enters_one_sided_state(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_AGREED,
			start_offset_days=-2,
			end_offset_days=1,
		)

		self.client.force_login(self.renter)
		self.client.post(
			reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}),
			{
				'action': 'report_missing_rental',
				'missing_rental_reason': 'No handover happened.',
			},
		)
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
		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.FEEDBACK_ONE_SIDED)
		self.assertIsNotNone(txn.feedback_window_expires_at)

	def test_feedback_window_auto_closes_without_feedback(self):
		txn = self._create_txn(
			status=Transaction.AWAITING_FEEDBACK,
			start_offset_days=-10,
			end_offset_days=-5,
		)
		txn.feedback_window_expires_at = timezone.now() - timedelta(days=1)
		txn.save(update_fields=['feedback_window_expires_at', 'amended'])

		result = auto_close_feedback_windows()
		self.assertGreaterEqual(result.get('updated', 0), 1)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK)
		self.assertIsNone(txn.feedback_window_expires_at)

	def test_feedback_window_auto_closes_as_one_sided_when_single_feedback_exists(self):
		txn = self._create_txn(
			status=Transaction.FEEDBACK_ONE_SIDED,
			start_offset_days=-10,
			end_offset_days=-5,
		)
		txn.feedback_window_expires_at = timezone.now() - timedelta(days=1)
		txn.save(update_fields=['feedback_window_expires_at', 'amended'])
		TransactionFeedback.objects.create(
			transaction=txn,
			left_by=self.renter,
			left_for=self.lender,
			rating=4,
			communication_rating=4,
			delivery_return_rating=3,
			overall_rating=4,
		)

		auto_close_feedback_windows()
		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED)
		self.assertIsNone(txn.feedback_window_expires_at)

	def test_workflow_payload_is_consistent_for_web_context(self):
		txn = self._create_txn(
			status=Transaction.RENTAL_AGREED,
			start_offset_days=1,
			end_offset_days=4,
		)

		payload = txn.get_workflow_payload()
		self.assertEqual(payload['current_stage'], 4)
		self.assertEqual(payload['current_label'], 'Agreement')
		self.assertEqual(len(payload['timeline']), 7)
		self.assertEqual(payload['timeline'][0]['label'], 'Discussion')
		self.assertTrue(payload['timeline'][3]['current'])


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class PendingReminderWorkflowTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(title='Tools')
		self.product = Product.objects.create(category_id=self.category, name='Ladder')
		self.lender = User.objects.create_user(username='reminder-lender', email='rl@example.com', password='x')
		self.renter = User.objects.create_user(username='reminder-renter', email='rr@example.com', password='x')
		Profile.objects.create(
			user=self.lender,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07111111111',
			address_line_1='1 High Street',
			town='London',
			postcode='SW1A1AA',
		)
		Profile.objects.create(
			user=self.renter,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07222222222',
			address_line_1='2 High Street',
			town='London',
			postcode='SW1A1AA',
		)
		self.order = Order.objects.create(
			product=self.product,
			user=self.lender,
			direction=Order.TO_LET,
			expiry_date=timezone.now() + timedelta(days=30),
			status=Order.ACTIVE,
			price=25,
			deposit=100,
			postcode='SW1A1AA',
		)

	def _create_txn(self, status):
		return Transaction.objects.create(
			user_passive=self.lender,
			user_aggressive=self.renter,
			order_passive=self.order,
			product=self.product,
			transaction_status=status,
			prev_transaction_status=Transaction.RENTAL_ENQUIRY,
			rental_start_date=timezone.now().date() + timedelta(days=2),
			rental_end_date=timezone.now().date() + timedelta(days=4),
			price=25,
			deposit=100,
			current_spot_value=100,
			price_as_pct_spot_value=25,
		)

	def test_contract_counterparty_reminder_with_countdown(self):
		now = timezone.now().replace(hour=13, minute=0, second=0, microsecond=0)
		txn = self._create_txn(Transaction.RENTAL_AGREED)
		txn.lender_agreed_at = now - timedelta(hours=3)
		txn.save(update_fields=['lender_agreed_at', 'amended'])

		with patch('transaction.tasks.timezone.now', return_value=now):
			result = send_pending_action_reminders()
		self.assertGreaterEqual(result.get('contract_counterparty', 0), 1)

		msg = TransactionMessage.objects.filter(
			transaction=txn,
			user_to=self.renter,
			subject__startswith='Contract confirmation reminder',
		).last()
		self.assertIsNotNone(msg)
		self.assertIn('24-hour window', msg.description)
		txn.refresh_from_db()
		self.assertIsNotNone(txn.contract_counterparty_reminder_at)

	def test_contract_first_signer_reminder_sent(self):
		now = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
		txn = self._create_txn(Transaction.RENTAL_AGREED)

		with patch('transaction.tasks.timezone.now', return_value=now):
			result = send_pending_action_reminders()
		self.assertGreaterEqual(result.get('contract_first_signer', 0), 1)
		msg = TransactionMessage.objects.filter(
			transaction=txn,
			user_to=self.lender,
			subject__startswith='First signature reminder',
		).last()
		self.assertIsNotNone(msg)
		self.assertIn('first signer', msg.description.lower())

	def test_feedback_reminder_sent_to_missing_side(self):
		now = timezone.now().replace(hour=17, minute=0, second=0, microsecond=0)
		txn = self._create_txn(Transaction.FEEDBACK_ONE_SIDED)
		txn.feedback_window_expires_at = now + timedelta(days=5)
		txn.save(update_fields=['feedback_window_expires_at', 'amended'])
		TransactionFeedback.objects.create(
			transaction=txn,
			left_by=self.lender,
			left_for=self.renter,
			rating=4,
			communication_rating=4,
			delivery_return_rating=4,
			overall_rating=4,
		)

		with patch('transaction.tasks.timezone.now', return_value=now):
			result = send_pending_action_reminders()
		self.assertGreaterEqual(result.get('feedback', 0), 1)
		msg = TransactionMessage.objects.filter(
			transaction=txn,
			user_to=self.renter,
			subject__startswith='Feedback reminder',
		).last()
		self.assertIsNotNone(msg)
		self.assertIn('Time left before auto-close', msg.description)


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class DisputeWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Tools')
        self.product = Product.objects.create(category_id=self.category, name='Drill')
        self.lender = User.objects.create_user(username='dispute-lender', email='dl@example.com', password='x')
        self.renter = User.objects.create_user(username='dispute-renter', email='dr@example.com', password='x')
        self.staff = User.objects.create_user(username='dispute-admin', email='da@example.com', password='x', is_staff=True)
        self.order = Order.objects.create(
            product=self.product,
            user=self.lender,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=30),
            status=Order.ACTIVE,
            price=30,
            deposit=80,
            postcode='SW1A1AA',
        )

    def _create_txn(self):
        return Transaction.objects.create(
            user_passive=self.lender,
            user_aggressive=self.renter,
            order_passive=self.order,
            product=self.product,
            transaction_status=Transaction.DISPUTE_REQUESTED,
            prev_transaction_status=Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            rental_start_date=timezone.localdate() - timedelta(days=5),
            rental_end_date=timezone.localdate() - timedelta(days=2),
            price=30,
            deposit=80,
            current_spot_value=100,
            price_as_pct_spot_value=30,
            deposit_resolution_notes='Deposit dispute',
            transaction_status_raised_by=self.lender,
        )

    def test_dispute_case_created_and_review_link_exposed(self):
        txn = self._create_txn()
        case = txn.dispute_cases.first()
        self.assertIsNotNone(case)

        self.client.force_login(self.staff)
        response = self.client.get(reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, case.case_number)
        self.assertContains(response, reverse('transaction:dispute_case_review', kwargs={'case_number': case.case_number}))

    @patch('transaction.views.stripe_connect_service.refund_rental_payment')
    @patch('transaction.views.async_resolve_deposit_hold.delay')
    def test_dispute_resolution_closes_transaction_and_triggers_settlement(
        self,
        mock_resolve_deposit_hold,
        mock_refund_rental_payment,
    ):
        txn = self._create_txn()
        case = txn.dispute_cases.first()
        mock_refund_rental_payment.return_value = {'ok': True, 'refunded_amount': 12.50, 'refund_reference': 're_123'}

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('transaction:dispute_case_review', kwargs={'case_number': case.case_number}),
            {
                'action': 'resolve_lender',
                'resolution_notes': 'Evidence supports lender.',
                'deposit_return_amount': '20.00',
                'payment_offset_amount': '20.00',
            },
        )

        self.assertEqual(response.status_code, 302)
        txn.refresh_from_db()
        case.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.DISPUTE_DECIDED)
        self.assertEqual(case.status, case.STATUS_RESOLVED)
        self.assertEqual(case.outcome, case.OUTCOME_LENDER)
        self.assertAlmostEqual(case.deposit_return_amount, 20.00)
        self.assertAlmostEqual(case.payment_offset_amount, 20.00)
        mock_resolve_deposit_hold.assert_called_once()
        mock_refund_rental_payment.assert_called_once()
        self.assertEqual(mock_refund_rental_payment.call_args.kwargs['refund_amount'], 20.00)

    def test_overdue_dispute_case_is_escalated(self):
        txn = self._create_txn()
        case = txn.dispute_cases.first()
        case.sla_due_at = timezone.now() - timedelta(hours=1)
        case.save(update_fields=['sla_due_at', 'amended'])

        result = escalate_overdue_disputes()
        self.assertGreaterEqual(result.get('updated', 0), 1)
        case.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(case.status, case.STATUS_ESCALATED)
        self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)

    def test_admin_transaction_browser_allows_state_override(self):
        txn = self._create_txn()

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('transaction:admin_transaction_browser'),
            {
                'transaction_reference': txn.transaction_reference,
                'new_status': Transaction.RENTAL_PROCESS_COMPLETED,
                'note': 'Admin override for closure.',
            },
        )
        self.assertEqual(response.status_code, 302)

        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_PROCESS_COMPLETED)
        self.assertIn('[ADMIN_STATE_CHANGE]', txn.deposit_resolution_notes)


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class TransitionNotificationTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(title='Electronics')
		self.product = Product.objects.create(category_id=self.category, name='Camera')
		self.lender = User.objects.create_user(username='notif-lender', email='nl@example.com', password='x')
		self.renter = User.objects.create_user(username='notif-renter', email='nr@example.com', password='x')
		self.order = Order.objects.create(
			product=self.product,
			user=self.lender,
			direction=Order.TO_LET,
			expiry_date=timezone.now() + timedelta(days=30),
			status=Order.ACTIVE,
			price=30,
			deposit=80,
			postcode='SW1A1AA',
		)
		Profile.objects.create(
			user=self.lender,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07333333333',
			address_line_1='1 High Street',
			town='London',
			postcode='SW1A1AA',
		)
		Profile.objects.create(
			user=self.renter,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07444444444',
			address_line_1='2 High Street',
			town='London',
			postcode='SW1A1AA',
		)

	def _create_txn(self):
		return Transaction.objects.create(
			user_passive=self.lender,
			user_aggressive=self.renter,
			order_passive=self.order,
			product=self.product,
			transaction_status=Transaction.RENTAL_ENQUIRY,
			prev_transaction_status=Transaction.RENTAL_ENQUIRY,
			rental_start_date=timezone.now().date() + timedelta(days=2),
			rental_end_date=timezone.now().date() + timedelta(days=3),
			price=30,
			deposit=80,
			current_spot_value=100,
			price_as_pct_spot_value=30,
		)

	def test_major_transition_creates_email_enabled_system_message(self):
		txn = self._create_txn()
		txn.prev_transaction_status = txn.transaction_status
		txn.transaction_status = txn.RENTAL_AGREED
		txn.transaction_status_raised_by = self.lender
		txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])

		msg = TransactionMessage.objects.filter(transaction=txn, user_to=self.renter).last()
		self.assertIsNotNone(msg)
		self.assertTrue(msg.is_system_generated)
		self.assertTrue(msg.email_to_recepient)
		self.assertIn('Transaction status changed', msg.description)

	def test_dispute_transition_marks_include_admin(self):
		txn = self._create_txn()
		txn.prev_transaction_status = txn.transaction_status
		txn.transaction_status = txn.DISPUTE_REQUESTED
		txn.transaction_status_raised_by = self.lender
		txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])

		msg = TransactionMessage.objects.filter(transaction=txn, user_to=self.renter).last()
		self.assertIsNotNone(msg)
		self.assertTrue(msg.include_admin)

	def test_admin_config_can_disable_specific_transition_notifications(self):
		System.objects.create(name='TRANSACTION_MAJOR_NOTIFICATION_STATUSES', value='DREQ')
		txn = self._create_txn()
		txn.prev_transaction_status = txn.transaction_status
		txn.transaction_status = txn.RENTAL_AGREED
		txn.transaction_status_raised_by = self.lender
		txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])

		msg = TransactionMessage.objects.filter(transaction=txn, user_to=self.renter).last()
		self.assertIsNone(msg)

	def test_admin_config_can_enable_dispute_notification_only(self):
		System.objects.create(name='TRANSACTION_MAJOR_NOTIFICATION_STATUSES', value='DREQ')
		txn = self._create_txn()
		txn.prev_transaction_status = txn.transaction_status
		txn.transaction_status = txn.DISPUTE_REQUESTED
		txn.transaction_status_raised_by = self.lender
		txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])

		msg = TransactionMessage.objects.filter(transaction=txn, user_to=self.renter).last()
		self.assertIsNotNone(msg)
		self.assertIn('Dispute requested', msg.subject)


@override_settings(MOBILE_VERIFICATION_ENABLED=False)
class AutoCancelOverdueRentalTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(title='Home')
		self.product = Product.objects.create(category_id=self.category, name='Projector')
		self.lender = User.objects.create_user(username='cancel-lender', email='cl@example.com', password='x')
		self.renter = User.objects.create_user(username='cancel-renter', email='cr@example.com', password='x')
		Profile.objects.create(
			user=self.lender,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07555555555',
			address_line_1='1 High Street',
			town='London',
			postcode='SW1A1AA',
		)
		Profile.objects.create(
			user=self.renter,
			date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
			mobile_number='07666666666',
			address_line_1='2 High Street',
			town='London',
			postcode='SW1A1AA',
		)
		self.order = Order.objects.create(
			product=self.product,
			user=self.lender,
			direction=Order.TO_LET,
			expiry_date=timezone.now() + timedelta(days=30),
			status=Order.ACTIVE,
			price=25,
			deposit=50,
			postcode='SW1A1AA',
		)

	def test_overdue_first_day_booking_is_cancelled_and_stats_are_recalculated(self):
		start_date = timezone.localdate() - timedelta(days=1)
		end_date = start_date + timedelta(days=2)
		txn = Transaction.objects.create(
			user_passive=self.lender,
			user_aggressive=self.renter,
			order_passive=self.order,
			product=self.product,
			transaction_status=Transaction.RENTAL_AGREED,
			prev_transaction_status=Transaction.RENTAL_ENQUIRY,
			rental_start_date=start_date,
			rental_end_date=end_date,
			price=25,
			deposit=50,
			current_spot_value=100,
			price_as_pct_spot_value=25,
		)

		with patch('transaction.tasks.timezone.localtime') as mock_localtime:
			mock_localtime.return_value = timezone.now()
			result = auto_cancel_overdue_first_day_bookings()

		self.assertEqual(result['cancelled'], 1)

		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)
		self.assertEqual(txn.transaction_status_raised_by, None)
		self.assertIn('[AUTO_CANCELLED_BY_SYSTEM]', txn.deposit_resolution_notes)

		msgs = TransactionMessage.objects.filter(transaction=txn).order_by('created')
		self.assertEqual(msgs.count(), 2)
		self.assertTrue(all(msg.is_system_generated for msg in msgs))

		self.lender.profile.refresh_from_db()
		self.renter.profile.refresh_from_db()
		self.assertEqual(self.lender.profile.user_bookings_pending_my_action, 0)
		self.assertEqual(self.lender.profile.user_bookings_pending_other_party, 0)
		self.assertEqual(self.renter.profile.user_bookings_pending_my_action, 0)
		self.assertEqual(self.renter.profile.user_bookings_pending_other_party, 0)

	def test_first_day_booking_is_not_cancelled_before_end_of_day(self):
		start_date = timezone.localdate()
		end_date = start_date + timedelta(days=2)
		txn = Transaction.objects.create(
			user_passive=self.lender,
			user_aggressive=self.renter,
			order_passive=self.order,
			product=self.product,
			transaction_status=Transaction.RENTAL_AGREED,
			prev_transaction_status=Transaction.RENTAL_ENQUIRY,
			rental_start_date=start_date,
			rental_end_date=end_date,
			price=25,
			deposit=50,
			current_spot_value=100,
			price_as_pct_spot_value=25,
		)

		now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
		with patch('transaction.tasks.timezone.localtime') as mock_localtime:
			mock_localtime.return_value = now
			result = auto_cancel_overdue_first_day_bookings()

		self.assertEqual(result['cancelled'], 0)
		txn.refresh_from_db()
		self.assertEqual(txn.transaction_status, Transaction.RENTAL_AGREED)
