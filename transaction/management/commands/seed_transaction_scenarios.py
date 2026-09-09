from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction
from django.utils import timezone

from account.models import Profile
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
        'name': 'scenario-verified-users-only',
        'status': Transaction.RENTAL_AGREED,
        'note': 'Verified users only; enquiry is allowed, but rental start should be blocked until the borrower completes Stripe identity verification',
        'lender_username': 'scenario-verified-lender',
        'renter_username': 'scenario-verified-renter',
        'order_overrides': {
            'verified_users_only': True,
            'max_rental_days': 14,
        },
        'renter_profile_overrides': {
            'email_confirmed': False,
            'mobile_verified': False,
            'address_verified': False,
            'stripe_identity_verified': False,
            'stripe_identity_verification_id': '',
            'stripe_identity_verified_at': None,
        },
        'transaction_overrides': {
            'rental_start_delta_days': 5,
            'rental_end_delta_days': 8,
            'price': 38,
            'deposit': 110,
            'deposit_card_setup_status': Transaction.CARD_READY,
            'deposit_test_hold_status': Transaction.TEST_HOLD_SUCCESS,
        },
    },
    {
        'name': 'scenario-long-rental',
        'status': Transaction.RENTAL_AGREED,
        'note': '7 to 30 day rental; deposit card should require Visa credit card or Mastercard credit card',
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
        'note': '31+ day rental; full deposit is taken and returned later rather than held as a card authorisation, with higher fees',
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
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument('--reset', action='store_true', help='Delete existing seeded scenarios before recreating them.')
        actions.add_argument('--commence-today', action='store_true', help='Move existing scenario start dates to today, preserving duration and progress.')
        actions.add_argument('--finish-today', action='store_true', help='Move existing scenario end dates to today, preserving duration and progress.')

    def handle(self, *args, **options):
        if getattr(settings, 'ENVIRONMENT_NAME', '').strip().lower() == 'production':
            raise CommandError('This command is disabled in production.')

        if options['commence_today'] or options['finish_today']:
            self._move_dates(commence_today=options['commence_today'])
            return

        if options['reset']:
            self._reset()

        created = 0
        for scenario in SCENARIOS:
            scenario_name = scenario['name']
            status = scenario['status']
            note = scenario['note']
            lender_username = scenario.get('lender_username', 'scenario-lender')
            renter_username = scenario.get('renter_username', 'scenario-renter')
            lender_email = scenario.get('lender_email', f'{lender_username}@example.com')
            renter_email = scenario.get('renter_email', f'{renter_username}@example.com')
            order_overrides = scenario.get('order_overrides', {})
            txn_overrides = scenario.get('transaction_overrides', {})
            lender_profile_overrides = scenario.get('lender_profile_overrides', {})
            renter_profile_overrides = scenario.get('renter_profile_overrides', {})

            marker = f'SCENARIO:{scenario_name}'
            txn = Transaction.objects.filter(transpact_text_status=marker).first()
            was_created = txn is None

            if was_created:
                lender = self._ensure_user(lender_username, lender_email)
                renter = self._ensure_user(renter_username, renter_email)
                self._ensure_profile(lender, **lender_profile_overrides)
                self._ensure_profile(renter, **renter_profile_overrides)

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
                    rental_start_date=Transaction.workflow_today() + timedelta(days=txn_overrides.get('rental_start_delta_days', 1)),
                    rental_end_date=Transaction.workflow_today() + timedelta(days=txn_overrides.get('rental_end_delta_days', 3)),
                    quantity=1,
                    price=txn_overrides.get('price', 30),
                    deposit=txn_overrides.get('deposit', 80),
                    deposit_card_setup_status=txn_overrides.get('deposit_card_setup_status', Transaction.CARD_NONE),
                    deposit_test_hold_status=txn_overrides.get('deposit_test_hold_status', Transaction.TEST_HOLD_NOT_RUN),
                    payment_status=txn_overrides.get('payment_status', Transaction.PAYMENT_PENDING),
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

    def _move_dates(self, *, commence_today):
        # Reuse the website's reservation policy, including holds by other rentals.
        from transaction.views import _holding_statuses, _release_transaction_dates, _reserve_transaction_dates

        today = Transaction.workflow_today()
        changes = []
        markers = [f"SCENARIO:{scenario['name']}" for scenario in SCENARIOS]
        with db_transaction.atomic():
            transactions = list(Transaction.objects.select_for_update().filter(
                transpact_text_status__in=markers,
            ).order_by('id'))
            for txn in transactions:
                if (not txn.rental_start_date or not txn.rental_end_date
                        or txn.rental_end_date < txn.rental_start_date):
                    raise CommandError(
                        f'{txn.transaction_reference} has an invalid rental date range. '
                        'No dates were changed; correct the range or reset the scenarios first.'
                    )

            for txn in transactions:
                old_start, old_end = txn.rental_start_date, txn.rental_end_date
                duration = old_end - old_start
                new_start = today if commence_today else today - duration
                new_end = today + duration if commence_today else today
                _release_transaction_dates(txn)
                # Date-only maintenance must not replay status-transition signals
                # or alter evidence, contracts, payment state, or handover codes.
                Transaction.objects.filter(pk=txn.pk).update(
                    rental_start_date=new_start, rental_end_date=new_end,
                    amended=timezone.now(),
                )
                txn.rental_start_date, txn.rental_end_date = new_start, new_end
                if txn.transaction_status in _holding_statuses():
                    _reserve_transaction_dates(txn)
                changes.append(
                    f'{txn.transpact_text_status.removeprefix("SCENARIO:")} '
                    f'({txn.transaction_reference}): {old_start} – {old_end} '
                    f'-> {new_start} – {new_end} ({duration.days + 1} rental days)'
                )

        if not changes:
            self.stdout.write('No existing scenario transactions found. Seed scenarios first.')
            return
        for change in changes:
            self.stdout.write(change)
        boundary = 'start' if commence_today else 'end'
        self.stdout.write(self.style.SUCCESS(
            f'Updated {len(changes)} scenario transactions to {boundary} today '
            f'({today}, Europe/London). Rental length and workflow progress preserved.'
        ))

    def _ensure_user(self, username, email):
        user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
        if user.email != email:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(username)
        user.save()
        return user

    def _ensure_profile(self, user, **overrides):
        defaults = {
            'email_confirmed': True,
            'mobile_verified': True,
            'address_verified': True,
            'stripe_identity_verification_id': f'seed-{user.username}',
            'stripe_identity_verified': True,
            'stripe_identity_verified_at': timezone.now(),
            'date_of_birth': timezone.localdate() - timedelta(days=365 * 30),
            'mobile_number': '07123456789',
            'address_line_1': '1 Scenario Lane',
            'town': 'London',
            'postcode': 'SW1A1AA',
        }
        defaults.update(overrides)

        profile, _ = Profile.objects.get_or_create(user=user, defaults=defaults)
        changed = False
        for field, value in defaults.items():
            if getattr(profile, field) != value:
                setattr(profile, field, value)
                changed = True
        if changed:
            profile.save()
        return profile

    def _reset(self):
        Transaction.objects.filter(transpact_text_status__startswith='SCENARIO:').delete()
        Product.objects.filter(name__startswith='Scenario Drill').delete()
        Category.objects.filter(title__startswith='Scenario Tools ').delete()
        User.objects.filter(username__startswith='scenario-').delete()
