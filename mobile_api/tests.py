from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Profile
from common.models import Category, Order, Product
from friends.models import Friendship
from transaction.models import Transaction


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


class MobilePasswordAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='password-user',
            email='password-user@example.com',
            password='old-password',
        )

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse('mobile_api:auth_password_reset'),
            {'email': self.user.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertIn('reset your password', mail.outbox[0].subject.lower())

    def test_password_change_updates_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('mobile_api:auth_password_change'),
            {
                'old_password': 'old-password',
                'new_password1': 'NewStrongPass123!',
                'new_password2': 'NewStrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))


class NearbyPeopleApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nearby-user',
            email='nearby-user@example.com',
            password='secret',
        )
        self.profile = Profile.objects.create(
            user=self.user,
            date_of_birth='1990-01-01',
            mobile_number='07111111111',
            address_line_1='1 Main St',
            town='London',
            postcode='SW1A1AA',
            latitude=51.5000,
            longitude=-0.1000,
        )
        self.friend = User.objects.create_user(
            username='friend-user',
            email='friend@example.com',
            password='secret',
        )
        Profile.objects.create(
            user=self.friend,
            date_of_birth='1990-01-01',
            mobile_number='07222222222',
            address_line_1='2 Main St',
            town='London',
            postcode='SW1A2AA',
            latitude=51.5010,
            longitude=-0.1010,
        )
        self.other = User.objects.create_user(
            username='other-user',
            email='other@example.com',
            password='secret',
        )
        Profile.objects.create(
            user=self.other,
            date_of_birth='1990-01-01',
            mobile_number='07333333333',
            address_line_1='3 Main St',
            town='London',
            postcode='SW1A3AA',
            latitude=51.6000,
            longitude=-0.3000,
        )

    def test_nearby_people_excludes_existing_friendships(self):
        Friendship.objects.create(user_from=self.user, user_to=self.friend, status=Friendship.ACCEPTED)
        self.client.force_login(self.user)

        response = self.client.get(reverse('mobile_api:friends_nearby'), {'radius_km': 10})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 0)

    def test_nearby_people_returns_local_profiles(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('mobile_api:friends_nearby'), {'radius_km': 10})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['username'], 'friend-user')

    def test_send_friend_request(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('mobile_api:friends_add', kwargs={'user_id': self.other.id}))

        self.assertEqual(response.status_code, 201)
        friendship = Friendship.objects.get(user_from=self.user, user_to=self.other)
        self.assertEqual(friendship.status, Friendship.PENDING)


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

    @patch('mobile_api.views.PostcodeGeocoder.calculate_distance')
    @patch('mobile_api.views.PostcodeGeocoder.geocode_location')
    def test_product_detail_accepts_coordinate_location_without_geocoding(
        self,
        mock_geocode_location,
        mock_calculate_distance,
    ):
        order = self._create_order(
            price=25,
            postcode='SW1A1AA',
            amended_offset_hours=2,
        )
        Order.objects.filter(pk=order.pk).update(latitude=51.500000, longitude=-0.100000)

        mock_calculate_distance.return_value = 1.1

        response = self.client.get(
            reverse('mobile_api:products_detail', kwargs={'product_slug': self.product.slug}),
            {'location': '51.500000, -0.100000', 'distance': '10'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['active_order_count'], 1)
        self.assertEqual(payload['active_orders'][0]['id'], order.id)
        self.assertEqual(payload['active_orders'][0]['distance_km'], 1.1)
        mock_geocode_location.assert_not_called()


class OrderCreateApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='listing-owner',
            email='listing-owner@example.com',
            password='x',
        )
        self.category = Category.objects.create(title='Garden')
        self.product = Product.objects.create(
            category_id=self.category,
            name='Lawn Mower',
        )

    def test_create_listing_via_mobile_api(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('mobile_api:orders_create'),
            {
                'product_id': self.product.id,
                'expiry_date': '2026-12-31',
                'price': 18.5,
                'radius_km': 12,
                'postcode': 'SW1A1AA',
                'collection_policy': Order.MUST_COLLECT,
                'let_visibility': Order.FRIENDS_AND_PUBLIC,
                'description': 'Reliable mower in excellent condition.',
                'additional_comments': 'Please message before collection.',
                'max_rental_days': 5,
                'price_bands': [
                    {'duration_days': 3, 'price_per_day': 20},
                    {'duration_days': 7, 'price_per_day': 17},
                ],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        created_order = Order.objects.get(id=payload['id'])

        self.assertEqual(created_order.user_id, self.user.id)
        self.assertEqual(created_order.product_id, self.product.id)
        self.assertEqual(created_order.status, Order.ACTIVE)
        self.assertEqual(created_order.direction, Order.TO_LET)
        self.assertEqual(created_order.price, 18.5)
        self.assertEqual(created_order.radius_km, 12)
        self.assertEqual(created_order.max_rental_days, 5)
        self.assertEqual(created_order.price_bands.count(), 2)


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

    def test_transaction_detail_exposes_role_aware_allowed_actions(self):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=2,
            end_offset_days=5,
        )

        self.client.force_login(self.lender)
        lender_response = self.client.get(
            reverse(
                'mobile_api:transactions_detail',
                kwargs={'transaction_reference': txn.transaction_reference},
            )
        )
        self.assertEqual(lender_response.status_code, 200)
        lender_payload = lender_response.json()
        lender_actions = lender_payload.get('workflow_payload', {}).get('allowed_actions', [])
        self.assertIn('confirm_lender_contract', lender_actions)
        self.assertIn('collect_deposit', lender_actions)
        self.assertNotIn('confirm_renter_contract', lender_actions)

        self.client.force_login(self.renter)
        renter_response = self.client.get(
            reverse(
                'mobile_api:transactions_detail',
                kwargs={'transaction_reference': txn.transaction_reference},
            )
        )
        self.assertEqual(renter_response.status_code, 200)
        renter_payload = renter_response.json()
        renter_actions = renter_payload.get('workflow_payload', {}).get('allowed_actions', [])
        self.assertIn('confirm_renter_contract', renter_actions)
        self.assertIn('add_deposit_card', renter_actions)
        self.assertNotIn('confirm_lender_contract', renter_actions)

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
        txn.refresh_from_db()
        self.assertEqual(txn.transaction_status, Transaction.FEEDBACK_ONE_SIDED)
        self.assertIsNotNone(txn.feedback_window_expires_at)

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

        txn.deposit_proposal_iteration_count = 5
        txn.save(update_fields=['deposit_proposal_iteration_count', 'amended'])

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

    @patch('mobile_api.views.stripe_connect_service.create_setup_intent')
    def test_mobile_create_stripe_setup_intent_returns_session_payload(self, mock_create_setup_intent):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=2,
            end_offset_days=5,
        )
        mock_create_setup_intent.return_value = {
            'ok': True,
            'provider': 'stripe',
            'setup_intent_id': 'seti_mobile_123',
            'client_secret': 'seti_mobile_123_secret',
        }

        self.client.force_login(self.renter)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'create_stripe_setup_intent',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('setup_intent_id'), 'seti_mobile_123')
        self.assertEqual(payload.get('client_secret'), 'seti_mobile_123_secret')
        self.assertEqual(payload.get('provider'), 'stripe')

        txn.refresh_from_db()
        self.assertEqual(txn.stripe_setup_intent_id, 'seti_mobile_123')
        mock_create_setup_intent.assert_called_once_with(transaction=txn)

    @patch('mobile_api.views.stripe_connect_service.create_setup_intent')
    def test_mobile_create_stripe_setup_intent_propagates_provider_error(self, mock_create_setup_intent):
        txn = self._create_txn(
            status=Transaction.RENTAL_AGREED,
            start_offset_days=2,
            end_offset_days=5,
        )
        mock_create_setup_intent.return_value = {
            'ok': False,
            'error': 'Setup intent unavailable',
        }

        self.client.force_login(self.renter)
        response = self.client.post(
            reverse('mobile_api:transactions_actions', kwargs={'transaction_reference': txn.transaction_reference}),
            {
                'action': 'create_stripe_setup_intent',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Setup intent unavailable', str(response.json()))
        mock_create_setup_intent.assert_called_once_with(transaction=txn)
