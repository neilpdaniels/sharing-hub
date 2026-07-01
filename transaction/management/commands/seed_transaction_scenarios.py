from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from common.models import Category, Order, Product
from transaction.models import Transaction


SCENARIOS = [
    {
        'name': 'scenario-enquiry',
        'status': Transaction.RENTAL_ENQUIRY,
        'note': 'Initial enquiry',
    },
    {
        'name': 'scenario-agreed',
        'status': Transaction.RENTAL_AGREED,
        'note': 'Agreement signed',
    },
    {
        'name': 'scenario-checkout',
        'status': Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
        'note': 'Checkout evidence pending',
    },
    {
        'name': 'scenario-ongoing',
        'status': Transaction.RENTAL_ONGOING,
        'note': 'Rental ongoing',
    },
    {
        'name': 'scenario-return',
        'status': Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        'note': 'Return evidence pending',
    },
    {
        'name': 'scenario-deposit',
        'status': Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
        'note': 'Deposit review pending',
    },
    {
        'name': 'scenario-feedback',
        'status': Transaction.AWAITING_FEEDBACK,
        'note': 'Feedback window open',
    },
    {
        'name': 'scenario-long-rental',
        'status': Transaction.RENTAL_AGREED,
        'note': 'Long rental over 5 days; deposit card should require Visa or Mastercard credit card',
        'order_overrides': {'max_rental_days': 14},
        'transaction_overrides': {
            'rental_start_delta_days': 7,
            'rental_end_delta_days': 23,
            'price': 42,
            'deposit': 120,
        },
    },
    {
        'name': 'scenario-31-day-rental',
        'status': Transaction.RENTAL_AGREED,
        'note': '31+ day rental; no separate blocker found for rentals over 30 days in the current code',
        'order_overrides': {'max_rental_days': 31},
        'transaction_overrides': {
            'rental_start_delta_days': 10,
            'rental_end_delta_days': 41,
            'price': 55,
            'deposit': 150,
        },
    },
    {
        'name': 'scenario-zero-deposit',
        'status': Transaction.RENTAL_AGREED,
        'note': 'No deposit, payment still applies',
        'transaction_overrides': {
            'price': 25,
            'deposit': 0,
        },
    },
    {
        'name': 'scenario-zero-payment',
        'status': Transaction.RENTAL_AGREED,
        'note': 'No payment, deposit only',
        'transaction_overrides': {
            'price': 0,
            'deposit': 75,
        },
    },
    {
        'name': 'scenario-zero-cost',
        'status': Transaction.RENTAL_AGREED,
        'note': 'No rental charges at all',
        'transaction_overrides': {
            'price': 0,
            'deposit': 0,
            'delivery_cost': 0,
            'rentalution_fee': 0,
        },
    },
    {
        'name': 'scenario-friends-free',
        'status': Transaction.RENTAL_AGREED,
        'note': 'Friends-only rental with no cost',
        'order_overrides': {
            'let_visibility': Order.FRIENDS_ONLY,
            'mates_rates': 0,
            'mates_deposit': 0,
            'deposit': 0,
            'price': 0,
        },
        'transaction_overrides': {
            'price': 0,
            'deposit': 0,
        },
    },
]


class Command(BaseCommand):
    help = 'Seed repeatable transaction scenarios for web/mobile/Stripe walkthroughs.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing seeded scenarios before recreating them.')

    def handle(self, *args, **options):
        if getattr(settings, 'ENVIRONMENT_NAME', '').lower() == 'production':
            self.stderr.write(self.style.ERROR('This command is disabled in production.'))
            return
        if options['reset']:
            self._reset()

        lender = self._ensure_user('scenario-lender', 'scenario-lender@example.com')
        renter = self._ensure_user('scenario-renter', 'scenario-renter@example.com')
        created = 0
        for scenario in SCENARIOS:
            scenario_name = scenario['name']
            status = scenario['status']
            note = scenario['note']
            order_overrides = scenario.get('order_overrides', {})
            txn_overrides = scenario.get('transaction_overrides', {})
            marker = f"SCENARIO:{scenario_name}"
            txn = Transaction.objects.filter(transpact_text_status=marker).first()
            was_created = txn is None
            if was_created:
                category = Category.objects.create(title=f'Scenario Tools {scenario_name} {timezone.now().strftime("%Y%m%d%H%M%S")}')
                product = Product.objects.create(category_id=category, name=f'Scenario Drill {scenario_name}')
                order_defaults = {
                    'product': product,
                    'user': lender,
                    'direction': Order.TO_LET,
                    'expiry_date': timezone.now() + timedelta(days=30),
                    'status': Order.ACTIVE,
                    'price': 30,
                    'deposit': 80,
                    'postcode': 'SW1A1AA',
                    'max_rental_days': 7,
                }
                order_defaults.update(order_overrides)
                order = Order.objects.create(**order_defaults)
                txn = Transaction.objects.create(
                    user_passive=lender,
                    user_aggressive=renter,
                    order_passive=order,
                    product=product,
                    transaction_status=status,
                    prev_transaction_status=Transaction.RENTAL_ENQUIRY,
                    rental_start_date=timezone.localdate() + timedelta(days=txn_overrides.get('rental_start_delta_days', 1)),
                    rental_end_date=timezone.localdate() + timedelta(days=txn_overrides.get('rental_end_delta_days', 3)),
                    quantity=1,
                    price=txn_overrides.get('price', 30),
                    deposit=txn_overrides.get('deposit', 80),
                    current_spot_value=txn_overrides.get('current_spot_value', 100),
                    price_as_pct_spot_value=txn_overrides.get('price_as_pct_spot_value', 30),
                    deposit_resolution_notes=note,
                    enquiry_message=note,
                    delivery_distance_km=txn_overrides.get('delivery_distance_km', 5),
                    delivery_cost=txn_overrides.get('delivery_cost', 0),
                    rentalution_fee=txn_overrides.get('rentalution_fee', 0),
                    transpact_text_status=marker,
                )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created {scenario_name}: {txn.transaction_reference}'))
            else:
                self.stdout.write(f'Exists {scenario_name}: {txn.transaction_reference}')

        self.stdout.write(self.style.SUCCESS(f'Seeding complete. Created {created} scenario transactions.'))

    def _ensure_user(self, username, email):
        user, _ = User.objects.get_or_create(username=username, defaults={'email': username})
        if user.email != username:
            user.email = username
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(username)
        user.save()
        return user

    def _reset(self):
        Transaction.objects.filter(transpact_text_status__startswith='SCENARIO:').delete()
        Product.objects.filter(name__startswith='Scenario Drill').delete()
        Category.objects.filter(title__startswith='Scenario Tools ').delete()
        User.objects.filter(username__in=['scenario-lender', 'scenario-renter']).delete()
