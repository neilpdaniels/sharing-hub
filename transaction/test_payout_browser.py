"""Real-browser regression tests for the lender payout acceptance gate.

Run with ``./run_payout_browser_tests``.  The script installs Chromium once;
these tests create their own disposable database records and never call Stripe.
"""

import os
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Profile
from common.models import Category, Order, Product
from transaction.models import Transaction

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - keeps ordinary Django tests usable before setup.
    sync_playwright = None


class LenderPayoutBrowserTests(StaticLiveServerTestCase):
    """Exercise the rendered website rather than only calling its view directly."""

    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            raise cls.skipTest('Install browser test dependencies with ./run_payout_browser_tests.')
        # Playwright's sync bridge uses an event loop internally. Django sees
        # that loop when this class creates its disposable test data, even
        # though the test itself is synchronous. Scope this bypass to this
        # isolated browser-test process only; production code is unaffected.
        cls._previous_async_unsafe = os.environ.get('DJANGO_ALLOW_ASYNC_UNSAFE')
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        try:
            super().setUpClass()
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=True)
        except Exception as exc:
            if hasattr(cls, '_playwright'):
                cls._playwright.stop()
            super().tearDownClass()
            cls._restore_async_unsafe_environment()
            raise cls.skipTest(
                f'Chromium is not installed for Playwright ({exc}). '
                'Run ./run_payout_browser_tests once to install it.'
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, '_browser'):
            cls._browser.close()
        if hasattr(cls, '_playwright'):
            cls._playwright.stop()
        super().tearDownClass()
        cls._restore_async_unsafe_environment()

    @classmethod
    def _restore_async_unsafe_environment(cls):
        if cls._previous_async_unsafe is None:
            os.environ.pop('DJANGO_ALLOW_ASYNC_UNSAFE', None)
        else:
            os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = cls._previous_async_unsafe

    def setUp(self):
        self.category = Category.objects.create(title='Browser payout tests')
        self.product = Product.objects.create(category_id=self.category, name='Browser test drill')
        self.lender = User.objects.create_user(
            username='browser-lender', email='browser-lender@example.com', password='not-used-in-browser-test',
        )
        self.renter = User.objects.create_user(
            username='browser-renter', email='browser-renter@example.com', password='not-used-in-browser-test',
        )
        Profile.objects.create(
            user=self.lender,
            date_of_birth=timezone.now().date() - timedelta(days=365 * 30),
            mobile_number='07700900123',
            address_line_1='1 Test Street',
            town='London',
            postcode='SW1A1AA',
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
        self.transaction = Transaction.objects.create(
            user_passive=self.lender,
            user_aggressive=self.renter,
            order_passive=self.order,
            product=self.product,
            transaction_status=Transaction.RENTAL_ENQUIRY,
            prev_transaction_status=Transaction.RENTAL_ENQUIRY,
            rental_start_date=timezone.now().date() + timedelta(days=2),
            rental_end_date=timezone.now().date() + timedelta(days=5),
            price=20,
            deposit=100,
            current_spot_value=100,
            price_as_pct_spot_value=20,
        )
        self.context = self._browser.new_context()
        self.page = self.context.new_page()
        self._authenticate_browser_as(self.lender)

    def tearDown(self):
        self.context.close()

    def _authenticate_browser_as(self, user):
        self.client.force_login(user)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.context.add_cookies([{
            'name': settings.SESSION_COOKIE_NAME,
            'value': cookie.value,
            'url': self.live_server_url,
        }])

    def _transaction_url(self):
        return f'{self.live_server_url}{reverse("transaction:view_transaction", kwargs={"transaction_reference": self.transaction.transaction_reference})}'

    def _set_lender_payout_ready(self):
        Profile.objects.filter(user=self.lender).update(
            stripe_connect_transfers_enabled=True,
            stripe_connect_payouts_enabled=True,
        )

    def test_unready_lender_is_sent_to_payout_details_from_rendered_transaction_page(self):
        self.page.goto(self._transaction_url())
        self.page.locator(
            'form:has(input[name="action"][value="agree_rental"]) button[type="submit"]',
        ).click()
        self.page.wait_for_url(re.compile(r'.*/my_rentalution/my_details/\?tab=payouts$'))

        self.assertIn('Payout details', self.page.content())
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.transaction_status, Transaction.RENTAL_ENQUIRY)

    def test_ready_lender_can_accept_from_rendered_transaction_page(self):
        self._set_lender_payout_ready()
        self.page.goto(self._transaction_url())
        self.page.locator(
            'form:has(input[name="action"][value="agree_rental"]) button[type="submit"]',
        ).click()
        self.page.wait_for_url(f'**/transaction/view_transaction/{self.transaction.transaction_reference}/')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.transaction_status, Transaction.RENTAL_AGREED)
