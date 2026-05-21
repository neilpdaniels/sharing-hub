from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.models import Category, Order, Product


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