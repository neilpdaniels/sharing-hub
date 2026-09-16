from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from common.models import OrderBlockedDate
from transaction.models import Transaction, TransactionMessage
from transaction import test_seed_scenarios as fixtures


@override_settings(MOBILE_VERIFICATION_ENABLED=False, ENVIRONMENT_NAME='dev server')
class AdminTransactionDatesTests(TestCase):
    make_txn = fixtures.ScenarioDateCommandTests.make_txn

    def setUp(self):
        fixtures.ScenarioDateCommandTests.setUp(self)
        self.admin = User.objects.create_user(
            username='dates-admin', email='dates-admin@example.test', is_staff=True,
        )
        self.txn = self.make_txn(start=2, end=4)
        self.url = reverse('transaction:edit_transaction_dates', kwargs={
            'transaction_reference': self.txn.transaction_reference,
        })
        self.detail_url = reverse('transaction:view_transaction', kwargs={
            'transaction_reference': self.txn.transaction_reference,
        })
        self.client.force_login(self.admin)

    def data(self, start=0, end=2):
        return {
            'rental_start_date': (self.today + timedelta(days=start)).isoformat(),
            'rental_end_date': (self.today + timedelta(days=end)).isoformat(),
            'reason': 'Correct dates for agreed collection',
        }

    def test_admin_outside_transaction_can_view_edit_link_and_prefilled_form(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, 'Edit rental dates (admin)')
        self.assertContains(response, self.url)
        response = self.client.get(self.url)
        self.assertContains(response, f'value="{self.txn.rental_start_date}"')
        self.assertContains(response, 'Reason for change')

    def test_regular_parties_cannot_view_or_submit_admin_dates(self):
        for user in [self.lender, self.renter]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertNotContains(self.client.get(self.detail_url), 'Edit rental dates (admin)')
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.rental_start_date, self.today + timedelta(days=2))

    def test_anonymous_user_is_sent_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.rental_start_date, self.today + timedelta(days=2))

    def test_edit_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, self.data()).status_code, 403)

    def test_edit_records_admin_and_reason_without_replaying_progress(self):
        before_messages = TransactionMessage.objects.count()
        before_history = self.txn.history.count()
        original_status = self.txn.transaction_status
        original_prev_status = self.txn.prev_transaction_status
        response = self.client.post(self.url, self.data(-2, 0))
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.rental_end_date, self.today)
        self.assertEqual(self.txn.transaction_status, original_status)
        self.assertEqual(self.txn.prev_transaction_status, original_prev_status)
        self.assertEqual(self.txn.checkout_handover_pin, '123456')
        self.assertEqual(TransactionMessage.objects.count(), before_messages)
        self.assertEqual(self.txn.history.count(), before_history + 1)
        history = self.txn.history.first()
        self.assertEqual(history.history_user_id, self.admin.id)
        self.assertEqual(history.history_change_reason, 'Dates: Correct dates for agreed collection')
        self.assertEqual(history.rental_end_date, self.today)
        self.assertEqual(history.prev_record.rental_end_date, self.today + timedelta(days=4))
        self.assertIn('submit_return_borrower_evidence', self.txn.get_allowed_actions_for_user(self.renter))
        self.assertContains(self.client.get(self.url), 'dates-admin')
        self.assertContains(self.client.get(self.url), 'Correct dates for agreed collection')

    def test_invalid_range_and_missing_reason_leave_dates_and_history_unchanged(self):
        count = self.txn.history.count()
        for data in [self.data(3, 1), {**self.data(), 'reason': ''},
                     {**self.data(), 'rental_start_date': 'invalid'}]:
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.txn.refresh_from_db()
                self.assertEqual(self.txn.rental_start_date, self.today + timedelta(days=2))
                self.assertEqual(self.txn.history.count(), count)

    def test_other_rental_and_manual_block_conflicts_are_rejected(self):
        self.make_txn(marker='Real booking', start=-2, end=-1)
        self.assertContains(self.client.post(self.url, self.data(-2, 0)), 'Another rental already reserves')
        OrderBlockedDate.objects.create(order=self.order, date=self.today,
                                        reason=OrderBlockedDate.MANUAL)
        self.assertContains(self.client.post(self.url, self.data()), 'marked unavailable')
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.rental_start_date, self.today + timedelta(days=2))

    def test_handover_block_only_prevents_boundary_dates(self):
        OrderBlockedDate.objects.create(order=self.order, date=self.today + timedelta(days=1),
                                        reason=OrderBlockedDate.HANDOVER_UNAVAILABLE)
        self.assertContains(self.client.post(self.url, self.data(1, 3)), 'boundary dates')
        self.assertEqual(self.client.post(self.url, self.data(0, 2)).status_code, 302)
        self.assertTrue(self.order.blocked_dates.filter(
            date=self.today + timedelta(days=1), reason=OrderBlockedDate.HANDOVER_UNAVAILABLE).exists())

    def test_existing_own_hold_is_allowed_and_old_booked_dates_are_released(self):
        for offset in range(2, 5):
            OrderBlockedDate.objects.create(order=self.order, date=self.today + timedelta(days=offset),
                                            reason=OrderBlockedDate.BOOKED)
        self.assertEqual(self.client.post(self.url, self.data(0, 2)).status_code, 302)
        booked = set(self.order.blocked_dates.filter(reason=OrderBlockedDate.BOOKED).values_list('date', flat=True))
        self.assertEqual(booked, {self.today + timedelta(days=i) for i in range(3)})

    def test_completed_transaction_correction_does_not_reserve_dates(self):
        Transaction.objects.filter(pk=self.txn.pk).update(transaction_status=Transaction.RENTAL_PROCESS_COMPLETED)
        self.assertEqual(self.client.post(self.url, self.data(-10, -9)).status_code, 302)
        self.assertFalse(self.order.blocked_dates.exists())

    def test_no_change_does_not_add_history(self):
        count = self.txn.history.count()
        self.assertEqual(self.client.post(self.url, self.data(2, 4)).status_code, 302)
        self.assertEqual(self.txn.history.count(), count)

    def test_date_and_reservation_changes_roll_back_together(self):
        OrderBlockedDate.objects.create(order=self.order, date=self.today + timedelta(days=2),
                                        reason=OrderBlockedDate.BOOKED)
        count = self.txn.history.count()
        with patch('transaction.views._reserve_transaction_dates', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.data())
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.rental_start_date, self.today + timedelta(days=2))
        self.assertEqual(self.txn.history.count(), count)
        self.assertTrue(self.order.blocked_dates.filter(date=self.today + timedelta(days=2)).exists())
