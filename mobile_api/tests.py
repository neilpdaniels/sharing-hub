from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.models import Category, Order, Product
from transaction.models import Transaction, TransactionMessage


class LenderListingsViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Tools')
        self.product_one = Product.objects.create(
            category_id=self.category,
            name='Drill',
        )
        self.product_two = Product.objects.create(
            category_id=self.category,
            name='Sander',
        )
        self.lender = User.objects.create_user(
            username='lender',
            email='lender@example.com',
            password='x',
        )
        self.other_lender = User.objects.create_user(
            username='other-lender',
            email='other-lender@example.com',
            password='x',
        )

    def _create_order(self, *, user, product, status, price, amended_offset_hours):
        order = Order.objects.create(
            product=product,
            user=user,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=7),
            status=status,
            price=price,
            postcode='SW1A1AA',
        )
        Order.objects.filter(pk=order.pk).update(
            amended=timezone.now() + timedelta(hours=amended_offset_hours),
        )
        order.refresh_from_db()
        return order

    def test_returns_active_listings_for_requested_lender_only(self):
        newest = self._create_order(
            user=self.lender,
            product=self.product_one,
            status=Order.ACTIVE,
            price=15,
            amended_offset_hours=2,
        )
        older = self._create_order(
            user=self.lender,
            product=self.product_two,
            status=Order.ACTIVE,
            price=8,
            amended_offset_hours=1,
        )
        self._create_order(
            user=self.lender,
            product=self.product_one,
            status=Order.EXPIRED,
            price=12,
            amended_offset_hours=3,
        )
        self._create_order(
            user=self.other_lender,
            product=self.product_two,
            status=Order.ACTIVE,
            price=20,
            amended_offset_hours=4,
        )

        response = self.client.get(
            reverse('mobile_api:lender_listings', kwargs={'lender_id': self.lender.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item['id'] for item in payload], [newest.id, older.id])
        self.assertTrue(all(item['lender']['id'] == self.lender.id for item in payload))

    def test_returns_404_for_unknown_lender(self):
        response = self.client.get(
            reverse('mobile_api:lender_listings', kwargs={'lender_id': 999999})
        )

        self.assertEqual(response.status_code, 404)


class ProductDetailDistanceFilterTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Cameras')
        self.product = Product.objects.create(
            category_id=self.category,
            name='Mirrorless Camera',
        )
        self.lender = User.objects.create_user(
            username='camera-lender',
            email='camera-lender@example.com',
            password='x',
        )

    def _create_order(self, *, price, postcode, amended_offset_hours):
        order = Order.objects.create(
            product=self.product,
            user=self.lender,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=7),
            status=Order.ACTIVE,
            price=price,
            postcode=postcode,
        )
        Order.objects.filter(pk=order.pk).update(
            amended=timezone.now() + timedelta(hours=amended_offset_hours),
        )
        order.refresh_from_db()
        return order

    @patch('mobile_api.views.PostcodeGeocoder.calculate_distance')
    @patch('mobile_api.views.PostcodeGeocoder.geocode_location')
    def test_product_detail_filters_active_orders_by_distance(
        self,
        mock_geocode_location,
        mock_calculate_distance,
    ):
        near_order = self._create_order(
            price=25,
            postcode='SW1A1AA',
            amended_offset_hours=2,
        )
        far_order = self._create_order(
            price=30,
            postcode='SW1A2AA',
            amended_offset_hours=1,
        )
        Order.objects.filter(pk=near_order.pk).update(latitude=51.500000, longitude=-0.100000)
        Order.objects.filter(pk=far_order.pk).update(latitude=51.700000, longitude=-0.300000)

        mock_geocode_location.return_value = {'latitude': 51.500000, 'longitude': -0.100000}
        mock_calculate_distance.side_effect = [3.2, 14.8]

        response = self.client.get(
            reverse('mobile_api:products_detail', kwargs={'product_slug': self.product.slug}),
            {'location': 'London', 'distance': '10'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['active_order_count'], 1)
        self.assertEqual(payload['nearest_distance_km'], 3.2)
        self.assertEqual(len(payload['active_orders']), 1)
        self.assertEqual(payload['active_orders'][0]['id'], near_order.id)
        self.assertEqual(payload['active_orders'][0]['distance_km'], 3.2)


class PendingReservationReleaseTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Audio')
        self.product = Product.objects.create(
            category_id=self.category,
            name='Mixer',
        )
        self.lender = User.objects.create_user(
            username='lender-audio',
            email='lender-audio@example.com',
            password='x',
        )
        self.renter_one = User.objects.create_user(
            username='renter-one',
            email='renter-one@example.com',
            password='x',
        )
        self.renter_two = User.objects.create_user(
            username='renter-two',
            email='renter-two@example.com',
            password='x',
        )
        self.order = Order.objects.create(
            product=self.product,
            user=self.lender,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=30),
            status=Order.ACTIVE,
            price=15,
            postcode='SW1A1AA',
        )

    def test_pending_enquiry_blocks_dates_and_reject_releases_them(self):
        start = (timezone.now().date() + timedelta(days=5)).isoformat()
        end = (timezone.now().date() + timedelta(days=7)).isoformat()

        self.client.force_login(self.renter_one)
        create_one = self.client.post(
            reverse('mobile_api:transactions_list'),
            {
                'order_reference': self.order.order_reference,
                'rental_start_date': start,
                'rental_end_date': end,
            },
        )
        self.assertEqual(create_one.status_code, 201)
        txn_ref = create_one.json()['transaction_reference']

        self.client.force_login(self.renter_two)
        create_two = self.client.post(
            reverse('mobile_api:transactions_list'),
            {
                'order_reference': self.order.order_reference,
                'rental_start_date': start,
                'rental_end_date': end,
            },
        )
        self.assertEqual(create_two.status_code, 400)

        self.client.force_login(self.lender)
        reject = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn_ref}),
            {'action': 'reject_enquiry'},
            content_type='application/json',
        )
        self.assertEqual(reject.status_code, 200)

        self.client.force_login(self.renter_two)
        create_after_release = self.client.post(
            reverse('mobile_api:transactions_list'),
            {
                'order_reference': self.order.order_reference,
                'rental_start_date': start,
                'rental_end_date': end,
            },
        )
        self.assertEqual(create_after_release.status_code, 201)


class TransactionActionWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Power Tools')
        self.product = Product.objects.create(category_id=self.category, name='Router')
        self.lender = User.objects.create_user(
            username='api-lender',
            email='api-lender@example.com',
            password='x',
        )
        self.renter = User.objects.create_user(
            username='api-renter',
            email='api-renter@example.com',
            password='x',
        )
        self.order = Order.objects.create(
            product=self.product,
            user=self.lender,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=30),
            status=Order.ACTIVE,
            price=18,
            deposit=120,
            postcode='SW1A1AA',
        )

    def _create_txn(self, *, status, start_offset_days, end_offset_days):
        return Transaction.objects.create(
            user_passive=self.lender,
            user_aggressive=self.renter,
            order_passive=self.order,
            product=self.product,
            transaction_status=status,
            prev_transaction_status=Transaction.RENTAL_ENQUIRY,
            rental_start_date=timezone.now().date() + timedelta(days=start_offset_days),
            rental_end_date=timezone.now().date() + timedelta(days=end_offset_days),
            price=18,
            deposit=120,
            current_spot_value=120,
            price_as_pct_spot_value=15,
        )

    def test_mobile_report_missing_rental_and_feedback_path(self):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=-2,
            end_offset_days=2,
        )

        self.client.force_login(self.renter)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'report_missing_rental',
                'reason': 'Lender never arrived.',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.CANCEL_ACCEPTED)
        self.assertIn('[MISSING_RENTAL_VOIDED]', txn.deposit_resolution_notes)

        feedback = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'submit_feedback',
                'communication_rating': 4,
                'delivery_return_rating': 1,
                'overall_rating': 2,
                'feedback_comment': 'No handover happened.',
            },
            content_type='application/json',
        )
        self.assertEqual(feedback.status_code, 200)

    def test_mobile_report_missing_return_escalates_dispute(self):
        txn = self._create_txn(
            status=Transaction.RENTAL_ONGOING,
            start_offset_days=-8,
            end_offset_days=-1,
        )

        self.client.force_login(self.lender)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'report_missing_return',
                'reason': 'Borrower did not return item.',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)

    def test_mobile_deposit_iteration_cap_blocks_lender_and_auto_escalates_renter_contest(self):
        txn = self._create_txn(
            status=Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
            start_offset_days=-12,
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

        self.client.force_login(self.lender)
        blocked = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'propose_deposit_return',
                'deposit_proposed_return_amount': 60,
                'deposit_resolution_notes': 'Sixth attempt',
            },
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 400)

        self.client.force_login(self.renter)
        escalated = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'contest_deposit_return',
                'deposit_resolution_notes': 'Still contested after max attempts',
            },
            content_type='application/json',
        )
        self.assertEqual(escalated.status_code, 200)

        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.DISPUTE_REQUESTED)

    @patch('mobile_api.views.async_confirm_card_setup.delay')
    def test_mobile_confirm_stripe_card_queues_async_confirmation(self, mock_async_confirm):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=2,
            end_offset_days=5,
        )

        self.client.force_login(self.renter)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'confirm_stripe_card',
                'payment_method_id': 'pm_test_123',
                'setup_intent_id': 'seti_test_123',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.stripe_payment_method_id, 'pm_test_123')
        self.assertEqual(txn.stripe_setup_intent_id, 'seti_test_123')
        mock_async_confirm.assert_called_once_with(
            transaction_id=txn.id,
            setup_intent_id='seti_test_123',
            payment_method_id='pm_test_123',
        )

    def test_mobile_initiate_rental_accepts_multipart_video_upload(self):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=0,
            end_offset_days=3,
        )
        txn.deposit_card_setup_status = Transaction.CARD_READY
        txn.deposit_test_hold_status = Transaction.TEST_HOLD_SUCCESS
        txn.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'amended'])

        video_file = SimpleUploadedFile(
            'handover.mp4',
            b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom',
            content_type='video/mp4',
        )

        self.client.force_login(self.lender)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'initiate_rental',
                'videos': video_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.RENTAL_DAY_AWAITING_VERIFICATION)
        self.assertTrue(bool(txn.checkout_condition_video_url))