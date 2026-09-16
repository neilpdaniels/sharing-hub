"""Date/role parity and complete handover regression tests (no real payments)."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from mobile_api import tests as fixtures
from transaction.models import Transaction
from transaction.tasks import async_collect_deposit_hold


@override_settings(MOBILE_VERIFICATION_ENABLED=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WorkflowParityTests(TestCase):
    setUp = fixtures.TransactionActionWorkflowTests.setUp
    _create_txn = fixtures.TransactionActionWorkflowTests._create_txn

    def ready(self, start=0, end=3, deposit=120):
        txn = self._create_txn(status=Transaction.RENTAL_AGREED,
                               start_offset_days=start, end_offset_days=end)
        txn.rental_start_date = txn.workflow_today() + timedelta(days=start)
        txn.rental_end_date = txn.workflow_today() + timedelta(days=end)
        txn.lender_agreed_at = timezone.now()
        txn.renter_agreed_at = timezone.now()
        txn.deposit_card_setup_status = Transaction.CARD_READY
        txn.deposit_test_hold_status = Transaction.TEST_HOLD_SUCCESS
        txn.deposit = deposit
        txn.save()
        return txn

    def api(self, txn, user, action, **fields):
        self.client.force_login(user)
        return self.client.post(reverse('mobile_api:transactions_actions', kwargs={
            'transaction_reference': txn.transaction_reference,
        }), {'action': action, **fields}, content_type='application/json')

    def actions(self, txn, user):
        self.client.force_login(user)
        response = self.client.get(reverse('mobile_api:transactions_detail', kwargs={
            'transaction_reference': txn.transaction_reference,
        }))
        self.assertEqual(response.status_code, 200)
        return response.json()['workflow_payload']['allowed_actions']

    def notification_labels(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('mobile_api:notifications_transactions'))
        self.assertEqual(response.status_code, 200)
        return {
            item['transaction_reference']: item['action_label']
            for item in response.json()['txn_notice_items']
        }

    def test_booking_alerts_name_the_actual_next_handover_action(self):
        checkout = self.ready(start=0)
        self.assertEqual(
            self.notification_labels(self.lender)[checkout.transaction_reference],
            'Submit checkout evidence',
        )

        checkout.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        checkout.checkout_condition_video_url = 'https://example.test/checkout.mp4'
        checkout.save()
        self.assertEqual(
            self.notification_labels(self.renter)[checkout.transaction_reference],
            'Review checkout evidence — confirm or submit counter-evidence',
        )

        checkout.checkout_borrower_confirmed = True
        checkout.checkout_handover_pin = '123456'
        checkout.payment_status = Transaction.PAYMENT_CAPTURED_PLACEHOLDER
        checkout.deposit_collected_placeholder = True
        checkout.save()
        self.assertEqual(
            self.notification_labels(self.lender)[checkout.transaction_reference],
            'Confirm collection using the renter’s PIN / QR code',
        )

        returned = self.ready(start=-1, end=0)
        returned.transaction_status = Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
        returned.return_borrower_video_url = 'https://example.test/return.mp4'
        returned.save()
        self.assertEqual(
            self.notification_labels(self.lender)[returned.transaction_reference],
            'Review return evidence — confirm or submit counter-evidence',
        )

        returned.return_handover_pin = '654321'
        returned.save()
        self.assertEqual(
            self.notification_labels(self.renter)[returned.transaction_reference],
            'Confirm return using the lender’s PIN / QR code',
        )

        deposit = self.ready(start=-1, end=0)
        deposit.transaction_status = Transaction.RENTAL_RETURNED_DEPOSIT_PENDING
        deposit.deposit_proposed_by_lender_at = timezone.now()
        deposit.save()
        self.assertEqual(
            self.notification_labels(self.renter)[deposit.transaction_reference],
            'Review the deposit proposal — accept or contest it',
        )

    def codes(self, txn, user):
        self.client.force_login(user)
        response = self.client.get(reverse('mobile_api:transactions_codes', kwargs={
            'transaction_reference': txn.transaction_reference,
        }))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assert_web_parity(self, txn, user):
        api_actions = self.actions(txn, user)
        response = self.client.get(reverse('transaction:view_transaction', kwargs={
            'transaction_reference': txn.transaction_reference,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['allowed_actions']), set(api_actions))
        self.assertContains(response, txn.get_workflow_message())
        return response

    def test_overdue_collection_is_visible_and_either_participant_can_confirm(self):
        for user in (self.lender, self.renter):
            for channel in ('api', 'web'):
                txn = self.ready(start=-1)
                self.assertEqual(txn.get_overdue_kind(), 'collection')
                response = self.assert_web_parity(txn, user)
                self.assertContains(response, 'Confirm collection did not happen')
                self.assertEqual(txn.get_status_display_verbose(), 'Collection overdue — confirm whether it happened')
                if channel == 'api':
                    response = self.api(txn, user, 'confirm_no_collection')
                    self.assertEqual(response.status_code, 200)
                else:
                    self.client.force_login(user)
                    response = self.client.post(reverse('transaction:view_transaction', kwargs={
                        'transaction_reference': txn.transaction_reference}), {'action': 'confirm_no_collection'})
                    self.assertEqual(response.status_code, 302)
                txn.refresh_from_db()
                self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)
                self.assertEqual(txn.transaction_status_raised_by, user)
                self.assertEqual(txn.get_overdue_kind(), '')
                self.assertIn('[NO_COLLECTION_CONFIRMED]', txn.deposit_resolution_notes)
                self.assertEqual(txn.get_status_display_verbose(), 'Cancelled')
                self.assertEqual(txn.get_workflow_stage_label(), 'Cancelled')
                self.assertEqual(txn.get_workflow_message(), 'This booking was cancelled because collection did not happen.')

    def test_collection_confirmation_rejects_same_day_and_verified_handover(self):
        txn = self.ready(start=0)
        self.assertEqual(self.api(txn, self.lender, 'confirm_no_collection').status_code, 400)
        txn.rental_start_date -= timedelta(days=1)
        txn.checkout_handover_verified_at = timezone.now()
        txn.save()
        self.assertEqual(txn.get_overdue_kind(), '')
        self.assertEqual(self.api(txn, self.renter, 'confirm_no_collection').status_code, 400)

    def test_overdue_return_opens_non_return_case_only_for_lender(self):
        from transaction.models import DisputeCase
        for channel in ('api', 'web'):
            txn = self.ready(start=-3, end=-1)
            txn.transaction_status = Transaction.RENTAL_ONGOING
            txn.checkout_handover_verified_at = timezone.now() - timedelta(days=3)
            txn.save()
            self.assertEqual(txn.get_overdue_kind(), 'return')
            self.assert_web_parity(txn, self.lender)
            self.assert_web_parity(txn, self.renter)
            self.assertEqual(self.api(txn, self.renter, 'report_missing_return').status_code, 400)
            if channel == 'api':
                self.assertEqual(self.api(txn, self.lender, 'report_missing_return').status_code, 200)
            else:
                self.client.force_login(self.lender)
                response = self.client.post(reverse('transaction:view_transaction', kwargs={
                    'transaction_reference': txn.transaction_reference}), {'action': 'report_missing_return'})
                self.assertEqual(response.status_code, 302)
            txn.refresh_from_db()
            self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)
            self.assertTrue(DisputeCase.objects.filter(transaction=txn, reason_code=DisputeCase.REASON_MISSING_RETURN).exists())
            self.assertEqual(txn.get_overdue_kind(), '')

    def test_verified_return_and_return_day_do_not_offer_non_return(self):
        txn = self.ready(start=-2, end=0)
        txn.transaction_status = Transaction.RENTAL_ONGOING
        txn.save()
        self.assertEqual(txn.get_overdue_kind(), '')
        self.assertEqual(self.api(txn, self.lender, 'report_missing_return').status_code, 400)
        txn.rental_end_date -= timedelta(days=1)
        txn.return_handover_verified_at = timezone.now()
        txn.save()
        self.assertEqual(txn.get_overdue_kind(), '')
        self.assertEqual(self.api(txn, self.lender, 'report_missing_return').status_code, 400)

    def test_collection_due_date_and_contract_and_card_prerequisites(self):
        txn = self.ready(start=1)
        self.assertNotIn('initiate_rental', self.actions(txn, self.lender))
        self.assertNotIn('collect_deposit', self.actions(txn, self.lender))
        self.assertEqual(self.api(txn, self.lender, 'initiate_rental',
                                 checkout_video_url='https://example.test/video.mp4').status_code, 400)
        txn.rental_start_date = txn.workflow_today()
        txn.save()
        self.assertIn('initiate_rental', self.actions(txn, self.lender))
        self.assertNotIn('initiate_rental', self.actions(txn, self.renter))
        self.assertNotIn('awaiting rental day', txn.get_status_display_verbose())
        self.assert_web_parity(txn, self.lender)
        self.assert_web_parity(txn, self.renter)
        for field, value in [('renter_agreed_at', None), ('lender_agreed_at', None),
                             ('deposit_test_hold_status', Transaction.TEST_HOLD_NOT_RUN)]:
            original = getattr(txn, field)
            setattr(txn, field, value)
            self.assertNotIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))
            setattr(txn, field, original)

    @patch('mobile_api.views.async_collect_deposit_hold.delay')
    @patch('mobile_api.views.stripe_connect_service.collect_rental_payment')
    def test_full_collection_return_and_deposit_contest_flow(self, capture, collect):
        txn = self.ready()
        capture.return_value = {'ok': True, 'payment_status': Transaction.PAYMENT_CAPTURED_PLACEHOLDER}
        self.assertEqual(self.api(txn, self.lender, 'initiate_rental',
                                 checkout_video_url='https://example.test/checkout.mp4').status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        self.assertEqual(self.api(txn, self.renter, 'confirm_checkout_evidence').status_code, 200)
        self.assertIsNone(self.codes(txn, self.renter)['checkout_code'])
        self.assertNotIn('verify_checkout_handover_pin', self.actions(txn, self.lender))
        # A late deposit worker must unblock the PIN without re-submitting evidence.
        with patch('transaction.tasks.stripe_connect_service.collect_deposit_hold', return_value={
            'ok': True, 'collection_status': Transaction.COLLECT_SUCCESS,
        }):
            async_collect_deposit_hold(txn.id)
        txn.refresh_from_db()
        pin = self.codes(txn, self.renter)['checkout_code']['pin']
        self.assertIsNone(self.codes(txn, self.lender)['checkout_code'])
        self.assert_web_parity(txn, self.renter)
        self.assert_web_parity(txn, self.lender)
        self.assertEqual(self.api(txn, self.lender, 'verify_checkout_handover_pin', pin='wrong').status_code, 400)
        self.assertEqual(self.api(txn, self.renter, 'verify_checkout_handover_pin', pin=pin).status_code, 400)
        self.assertEqual(self.api(txn, self.lender, 'verify_checkout_handover_pin', pin=pin).status_code, 200)
        txn.refresh_from_db()
        self.assertIn('Rental commenced, awaiting return day on', txn.get_workflow_message())
        self.assertNotIn('submit_return_borrower_evidence', self.actions(txn, self.renter))
        self.assertEqual(self.api(txn, self.renter, 'submit_return_borrower_evidence',
                                 return_video_url='https://example.test/return.mp4').status_code, 400)
        txn.rental_end_date = txn.workflow_today()
        txn.save()
        self.assertEqual(
            txn.get_workflow_message(),
            'Return due today. Borrower: submit return evidence.',
        )
        self.assertIn('submit_return_borrower_evidence', self.actions(txn, self.renter))
        self.assert_web_parity(txn, self.renter)
        self.assertEqual(self.api(txn, self.renter, 'submit_return_borrower_evidence',
                                 return_video_url='https://example.test/return.mp4').status_code, 200)
        self.assertNotIn('verify_return_handover_pin', self.actions(txn, self.renter))
        self.assertEqual(self.api(txn, self.lender, 'submit_lender_return_evidence',
                                 lender_return_video_url='https://example.test/counter.mp4').status_code, 200)
        code = self.codes(txn, self.lender)['return_code']
        self.assertIsNone(self.codes(txn, self.renter)['return_code'])
        txn.refresh_from_db()
        self.assert_web_parity(txn, self.lender)
        self.assertEqual(self.api(txn, self.renter, 'verify_return_handover_pin', qr_payload=code['qr_payload']).status_code, 200)
        self.assertNotIn('agree_deposit_return', self.actions(txn, self.renter))
        self.assertEqual(self.api(txn, self.renter, 'contest_deposit_return', deposit_resolution_notes='No proposal').status_code, 400)
        self.assertEqual(self.api(txn, self.lender, 'propose_deposit_return',
                                 deposit_proposed_return_amount=100, deposit_resolution_notes='Damage').status_code, 200)
        self.assertEqual(self.api(txn, self.renter, 'contest_deposit_return', deposit_resolution_notes='Disagree').status_code, 200)
        self.assertIn('propose_deposit_return', self.actions(txn, self.lender))
        self.assertEqual(self.api(txn, self.lender, 'propose_deposit_return', deposit_proposed_return_amount=120).status_code, 200)
        with patch('mobile_api.views.async_resolve_deposit_hold.delay') as settle:
            self.assertEqual(self.api(txn, self.renter, 'agree_deposit_return').status_code, 200)
            settle.assert_called_once_with(transaction_id=txn.id, return_amount=120)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.AWAITING_FEEDBACK)

    def test_zero_deposit_return_goes_straight_to_feedback(self):
        txn = self.ready(deposit=0)
        txn.transaction_status = Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
        txn.return_borrower_video_url = 'https://example.test/return.mp4'
        txn.save()
        self.assertEqual(self.api(txn, self.lender, 'confirm_return_evidence').status_code, 200)
        pin = self.codes(txn, self.lender)['return_code']['pin']
        self.assertEqual(self.api(txn, self.renter, 'verify_return_handover_pin', pin=pin).status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.AWAITING_FEEDBACK)
        self.assertIn('submit_feedback', self.actions(txn, self.renter))
        self.assertNotIn('propose_deposit_return', self.actions(txn, self.lender))

    def test_midnight_london_unlocks_collection_and_return_without_status_change(self):
        txn = self.ready(start=1)
        txn.rental_start_date = datetime(2026, 7, 2).date()
        before = datetime(2026, 7, 1, 22, 59, tzinfo=dt_timezone.utc)
        after = before + timedelta(minutes=1)
        with patch('transaction.models.timezone.now', return_value=before):
            self.assertNotIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))
        with patch('transaction.models.timezone.now', return_value=after):
            self.assertIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))
        txn.transaction_status = Transaction.RENTAL_ONGOING
        txn.rental_end_date = txn.rental_start_date
        with patch('transaction.models.timezone.now', return_value=before):
            self.assertNotIn('submit_return_borrower_evidence', txn.get_allowed_actions_for_user(self.renter))
        with patch('transaction.models.timezone.now', return_value=after):
            self.assertIn('submit_return_borrower_evidence', txn.get_allowed_actions_for_user(self.renter))

    def test_missed_collection_includes_unverified_handover(self):
        txn = self.ready(start=-1)
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        txn.save()
        self.assertIn('report_missing_rental', self.actions(txn, self.renter))
        self.assertNotIn('report_missing_rental', self.actions(txn, self.lender))
        self.assertEqual(self.api(txn, self.renter, 'report_missing_rental', reason='Not collected').status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)

    def test_expired_confirmation_uses_shared_deadline(self):
        txn = self.ready(start=1)
        txn.renter_agreed_at = None
        txn.lender_agreed_at = timezone.now() - timedelta(hours=25)
        txn.save()
        self.assertNotIn('confirm_renter_contract', self.actions(txn, self.renter))
        self.assertIn('reinitiate_lender_contract', self.actions(txn, self.lender))
        self.assertEqual(self.api(txn, self.renter, 'confirm_renter_contract').status_code, 400)
        self.assertEqual(self.api(txn, self.lender, 'reinitiate_lender_contract').status_code, 200)
        self.assertIn('confirm_renter_contract', self.actions(txn, self.renter))

    def test_web_code_is_only_rendered_to_the_presenting_party(self):
        txn = self.ready()
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        txn.checkout_condition_video_url = 'https://example.test/checkout.mp4'
        txn.checkout_borrower_confirmed = True
        txn.payment_status = Transaction.PAYMENT_CAPTURED_PLACEHOLDER
        txn.deposit_collection_status = Transaction.COLLECT_SUCCESS
        txn.checkout_handover_pin = '987654'
        txn.save()
        borrower = self.assert_web_parity(txn, self.renter)
        lender = self.assert_web_parity(txn, self.lender)
        self.assertContains(borrower, '987654')
        self.assertNotContains(lender, '987654')
        self.assertContains(lender, 'Verify Handover & Start Rental')
        self.assertNotContains(borrower, 'id_checkout_handover_pin')
        txn.transaction_status = Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
        txn.return_borrower_video_url = 'https://example.test/return.mp4'
        txn.return_handover_pin = '876543'
        txn.save()
        lender = self.assert_web_parity(txn, self.lender)
        borrower = self.assert_web_parity(txn, self.renter)
        self.assertContains(lender, '876543')
        self.assertNotContains(borrower, '876543')
        self.assertContains(borrower, 'id_return_handover_pin')
        self.assertNotContains(lender, 'id_return_handover_pin')

    def test_qr_from_other_transaction_is_rejected(self):
        txn = self.ready()
        txn.transaction_status = Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
        txn.return_handover_pin = '654321'
        txn.save()
        response = self.api(txn, self.renter, 'verify_return_handover_pin',
                            qr_payload='SHARINGHUB:RETURN_PIN:OTHER:654321')
        self.assertEqual(response.status_code, 400)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION)

    def test_free_rental_does_not_require_payment_card(self):
        txn = self.ready(deposit=0)
        txn.price = txn.delivery_cost = txn.rentalution_fee = 0
        txn.deposit_card_setup_status = Transaction.CARD_NONE
        self.assertIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))
        self.assertNotIn('add_deposit_card', txn.get_allowed_actions_for_user(self.renter))

    @patch('mobile_api.views.stripe_connect_service.collect_rental_payment')
    def test_failed_rental_payment_keeps_collection_retry_available(self, capture):
        txn = self.ready()
        capture.return_value = {'ok': False, 'error': 'Declined'}
        response = self.api(txn, self.lender, 'initiate_rental',
                            checkout_video_url='https://example.test/checkout.mp4')
        self.assertEqual(response.status_code, 400)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_AGREED)
        self.assertIn('initiate_rental', self.actions(txn, self.lender))
        self.assertIsNone(self.codes(txn, self.renter)['checkout_code'])

    def test_return_evidence_cannot_skip_collection_verification(self):
        txn = self.ready(end=0)
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        txn.save()
        self.assertEqual(self.api(txn, self.renter, 'submit_return_borrower_evidence',
                                 return_video_url='https://example.test/return.mp4').status_code, 400)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)

    @patch('transaction.views.stripe_connect_service.collect_rental_payment')
    def test_web_can_complete_collection_and_same_day_return(self, capture):
        txn = self.ready(end=0, deposit=0)
        capture.return_value = {'ok': True, 'payment_status': Transaction.PAYMENT_CAPTURED_PLACEHOLDER}
        url = reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference})

        def post(user, action, **fields):
            self.client.force_login(user)
            response = self.client.post(url, {'action': action, **fields})
            self.assertEqual(response.status_code, 302)
            txn.refresh_from_db()

        post(self.lender, 'initiate_rental', checkout_video_url='https://example.test/checkout.mp4')
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        post(self.renter, 'submit_checkout_borrower_evidence', checkout_borrower_video_url='https://example.test/counter.mp4')
        self.assertTrue(txn.checkout_handover_pin)
        post(self.lender, 'verify_checkout_handover_pin', checkout_handover_pin=txn.checkout_handover_pin)
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_ONGOING)
        post(self.renter, 'submit_return_borrower_evidence', return_video_url='https://example.test/return.mp4')
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION)
        post(self.lender, 'confirm_return_evidence')
        self.assertTrue(txn.return_handover_pin)
        post(self.renter, 'verify_return_handover_pin', return_handover_pin=txn.return_handover_pin)
        self.assertEqual(txn.transaction_status, Transaction.AWAITING_FEEDBACK)

    def test_deposit_retry_does_not_overwrite_fast_worker_success(self):
        txn = self.ready()
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        txn.save()

        def finish_hold(**kwargs):
            Transaction.objects.filter(pk=kwargs['transaction_id']).update(
                deposit_collection_status=Transaction.COLLECT_SUCCESS,
            )

        with patch('mobile_api.views.async_collect_deposit_hold.delay', side_effect=finish_hold):
            self.assertEqual(self.api(txn, self.lender, 'collect_deposit').status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.deposit_collection_status, Transaction.COLLECT_SUCCESS)
        txn.deposit_collection_status = Transaction.COLLECT_FAILED
        txn.save()
        self.client.force_login(self.lender)
        with patch('transaction.views.async_collect_deposit_hold.delay', side_effect=finish_hold):
            response = self.client.post(reverse('transaction:view_transaction', kwargs={
                'transaction_reference': txn.transaction_reference,
            }), {'action': 'collect_deposit'})
        self.assertEqual(response.status_code, 302)
        txn.refresh_from_db()
        self.assertEqual(txn.deposit_collection_status, Transaction.COLLECT_SUCCESS)

    def test_current_summary_tracks_rental_day_and_later_stages(self):
        txn = self.ready(start=1)
        def summary():
            return next(row['help_text'] for row in txn.get_workflow_timeline() if row['current'])
        self.assertIn('Nothing else is required until the rental day', summary())
        txn.rental_start_date = txn.workflow_today()
        self.assertIn('submit checkout evidence', summary())
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        self.assertIn('submit checkout evidence', summary())
        txn.checkout_condition_video_url = 'https://example.test/checkout.mp4'
        self.assertIn('borrower agreement', summary())
        txn.transaction_status = Transaction.RENTAL_ONGOING
        self.assertNotIn('fully prepared', summary())

    @patch('mobile_api.views.stripe_connect_service.collect_rental_payment')
    @patch('transaction.views.stripe_connect_service.collect_rental_payment')
    def test_checkout_without_lender_evidence_can_resume_on_web_and_mobile(self, web_capture, api_capture):
        for capture in (web_capture, api_capture):
            capture.return_value = {'ok': True, 'payment_status': Transaction.PAYMENT_CAPTURED_PLACEHOLDER}
        for channel in ('web', 'mobile'):
            with self.subTest(channel=channel):
                txn = self.ready(deposit=0)
                txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
                txn.save()
                self.assertIn('initiate_rental', self.actions(txn, self.lender))
                self.assert_web_parity(txn, self.lender)
                self.assertNotIn('confirm_checkout_evidence', self.actions(txn, self.renter))
                self.assertIsNone(self.codes(txn, self.renter)['checkout_code'])
                fields = {'checkout_video_url': 'https://example.test/checkout.mp4'}
                if channel == 'mobile':
                    response = self.api(txn, self.lender, 'initiate_rental', **fields)
                    self.assertEqual(response.status_code, 200)
                else:
                    self.client.force_login(self.lender)
                    response = self.client.post(reverse('transaction:view_transaction', kwargs={
                        'transaction_reference': txn.transaction_reference,
                    }), {'action': 'initiate_rental', **fields})
                    self.assertEqual(response.status_code, 302)
                txn.refresh_from_db()
                self.assertEqual(txn.checkout_condition_video_url, fields['checkout_video_url'])
                self.assertNotIn('initiate_rental', self.actions(txn, self.lender))
                self.assertIn('confirm_checkout_evidence', self.actions(txn, self.renter))
                self.assertEqual(self.api(txn, self.renter, 'confirm_checkout_evidence').status_code, 200)
                self.assertTrue(self.codes(txn, self.renter)['checkout_code'])

    def test_checkout_evidence_recovery_requires_rental_day_and_verified_card(self):
        txn = self.ready(start=1)
        txn.transaction_status = Transaction.RENTAL_DAY_AWAITING_VERIFICATION
        self.assertNotIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))
        txn.rental_start_date = txn.workflow_today()
        txn.deposit_card_setup_status = Transaction.CARD_NONE
        self.assertNotIn('initiate_rental', txn.get_allowed_actions_for_user(self.lender))

    def test_shifted_finish_date_return_flow_on_web_and_mobile(self):
        from io import StringIO
        from django.core.management import call_command

        for channel in ('web', 'mobile'):
            for initial_status in (Transaction.RENTAL_ONGOING,
                                   Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION):
                with self.subTest(channel=channel, initial_status=initial_status):
                    txn = self.ready(start=-2, end=2, deposit=0)
                    txn.transaction_status = initial_status
                    txn.save()
                    call_command('seed_transaction_scenarios', '--transaction-id', str(txn.pk),
                                 '--finish-date', txn.workflow_today().isoformat(), stdout=StringIO())
                    txn.refresh_from_db()
                    self.assertEqual(txn.transaction_status, initial_status)
                    summary = next(row['help_text'] for row in txn.get_workflow_timeline() if row['current'])
                    self.assertIn('submit return evidence', summary)
                    self.assertNotIn('fully prepared', summary)
                    self.assertNotIn('Awaiting lender agreement', txn.get_workflow_message())
                    self.assertIn('submit_return_borrower_evidence', self.actions(txn, self.renter))
                    self.assertNotIn('confirm_return_evidence', self.actions(txn, self.lender))
                    self.assertIsNone(self.codes(txn, self.lender)['return_code'])
                    self.assert_web_parity(txn, self.renter)
                    self.assert_web_parity(txn, self.lender)

                    def post(user, action, **fields):
                        if channel == 'mobile':
                            self.assertEqual(self.api(txn, user, action, **fields).status_code, 200)
                        else:
                            self.client.force_login(user)
                            response = self.client.post(reverse('transaction:view_transaction', kwargs={
                                'transaction_reference': txn.transaction_reference,
                            }), {'action': action, **fields})
                            self.assertEqual(response.status_code, 302)
                        txn.refresh_from_db()

                    post(self.renter, 'submit_return_borrower_evidence',
                         return_video_url='https://example.test/return.mp4')
                    self.assertTrue(txn.return_borrower_video_url)
                    self.assertIn('Awaiting lender agreement', txn.get_workflow_message())
                    self.assertIn('confirm_return_evidence', self.actions(txn, self.lender))
                    post(self.lender, 'confirm_return_evidence')
                    code = self.codes(txn, self.lender)['return_code']
                    self.assertTrue(code['pin'])
                    self.assertTrue(code['qr_payload'])
                    self.assertIsNone(self.codes(txn, self.renter)['return_code'])
                    self.assertIn('verify_return_handover_pin', self.actions(txn, self.renter))
                    post(self.renter, 'verify_return_handover_pin',
                         **({'pin': code['pin']} if channel == 'mobile'
                            else {'return_handover_pin': code['pin']}))
                    self.assertEqual(txn.transaction_status, Transaction.AWAITING_FEEDBACK)

    @override_settings(FILE_UPLOAD_MAX_MEMORY_SIZE=0)
    @patch('transaction.views.stripe_connect_service.collect_rental_payment')
    def test_disk_backed_checkout_video_keeps_display_and_raw_copies(self, capture):
        from tempfile import TemporaryDirectory
        from django.core.files.uploadedfile import SimpleUploadedFile
        from transaction.models import TransactionMessageImage

        capture.return_value = {'ok': True, 'payment_status': Transaction.PAYMENT_CAPTURED_PLACEHOLDER}
        content = b'\x00\x00\x00\x18ftypmp42' + b'video evidence' * 250000
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            for channel in ('web', 'mobile'):
                with self.subTest(channel=channel):
                    txn = self.ready(deposit=0)
                    self.client.force_login(self.lender)
                    video = SimpleUploadedFile('checkout.mp4', content, content_type='video/mp4')
                    if channel == 'web':
                        url = reverse('transaction:view_transaction', kwargs={'transaction_reference': txn.transaction_reference})
                        fields = {'action': 'initiate_rental', 'checkout_video_file': video}
                    else:
                        url = reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference})
                        fields = {'action': 'initiate_rental', 'videos': video}
                    response = self.client.post(url, fields)
                    self.assertEqual(response.status_code, 302 if channel == 'web' else 200)
                    txn.refresh_from_db()
                    self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
                    evidence = TransactionMessageImage.objects.get(transaction=txn, evidence_stage='checkout_lender')
                    self.assertEqual(evidence.video.name, evidence.video_raw.name)
                    for field in (evidence.video, evidence.video_raw):
                        with field.open('rb') as saved:
                            self.assertEqual(saved.read(), content)
                    original_names = (evidence.video.name, evidence.video_raw.name)
                    evidence.active = False
                    evidence.save(update_fields=['active'])
                    self.assertEqual((evidence.video.name, evidence.video_raw.name), original_names)
