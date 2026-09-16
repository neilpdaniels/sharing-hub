from datetime import date, timedelta

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
        'name': 'scenario-rental-ready',
        'status': Transaction.RENTAL_AGREED,
        'note': 'Stripe test card verified; ready for lender checkout evidence on rental day.',
        'stripe_test_card': True,
        'transaction_overrides': {'rental_start_delta_days': 0, 'rental_end_delta_days': 2},
    },
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
        'status': Transaction.RENTAL_AGREED,
        'note': 'Contracts confirmed; verify a Stripe test card, then submit checkout evidence on rental day.',
        'transaction_overrides': {'rental_start_delta_days': 0, 'rental_end_delta_days': 2},
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
        'note': 'Deposit review pending; lender can propose a return amount in the mobile app.',
        'transaction_overrides': {'deposit': 120},
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
        parser.add_argument('--transaction-id', type=int, help='Target one existing transaction by database ID (including non-scenario transactions).')
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument('--rental-ready', action='store_true', help='Seed a rental starting today with a real Stripe test payment method and verification hold. Requires a Stripe test secret key.')
        actions.add_argument('--repair', action='store_true', help='Repair incomplete seeded contract/checkout prerequisites without resetting dates or completed work.')
        actions.add_argument('--reset', action='store_true', help='Delete existing seeded scenarios before recreating them.')
        actions.add_argument('--commence-today', action='store_true', help='Move existing scenario start dates to today, preserving duration and progress.')
        actions.add_argument('--finish-today', action='store_true', help='Move existing scenario end dates to today, preserving duration and progress.')

        actions.add_argument('--commence-date', type=date.fromisoformat, metavar='YYYY-MM-DD', help='Move the selected transaction start date, preserving duration and progress. Requires --transaction-id.')
        actions.add_argument('--finish-date', type=date.fromisoformat, metavar='YYYY-MM-DD', help='Move the selected transaction end date, preserving duration and progress. Requires --transaction-id.')

    def handle(self, *args, **options):
        if getattr(settings, 'ENVIRONMENT_NAME', '').strip().lower() == 'production':
            raise CommandError('This command is disabled in production.')

        target_date = options['commence_date'] or options['finish_date']
        date_mode = target_date or options['commence_today'] or options['finish_today']
        if target_date and options['transaction_id'] is None:
            raise CommandError('--commence-date and --finish-date require --transaction-id.')
        if options['transaction_id'] is not None and not date_mode and not options['repair']:
            raise CommandError('--transaction-id requires a date option or --repair.')

        if date_mode:
            self._move_dates(
                commence_today=bool(options['commence_today'] or options['commence_date']),
                target_date=target_date, transaction_id=options['transaction_id'],
            )
            return

        if options['repair']:
            self._repair(options['transaction_id'])
            return

        if options['reset']:
            self._reset()

        if options['rental_ready']:
            key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '') or ''
            if not key.startswith(('sk_test_', 'rk_test_')):
                raise CommandError('--rental-ready requires STRIPE_CONNECT_SECRET_KEY set to a Stripe test key (sk_test_ or rk_test_). No scenario was created.')

        created = 0
        for scenario in SCENARIOS:
            if bool(scenario.get('stripe_test_card')) != options['rental_ready']:
                continue
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
                    lender_agreed_at=timezone.now() if status != Transaction.RENTAL_ENQUIRY else None,
                    renter_agreed_at=timezone.now() if status != Transaction.RENTAL_ENQUIRY else None,
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

            if scenario.get('stripe_test_card'):
                self._verify_seed_card(txn)

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created {scenario_name}: {txn.transaction_reference}'))
            else:
                self.stdout.write(f'Exists {scenario_name}: {txn.transaction_reference}')

        self.stdout.write(self.style.SUCCESS(f'Seeding complete. Created {created} scenario transactions.'))

    def _verify_seed_card(self, txn):
        import stripe
        from transaction.stripe_connect import stripe_connect_service

        with db_transaction.atomic():
            txn = Transaction.objects.select_for_update().get(pk=txn.pk)
            if (txn.has_verified_payment_card() and txn.stripe_payment_method_id
                    and txn.stripe_customer_id and txn.deposit_test_hold_reference
                    and txn.deposit_test_hold_at):
                self.stdout.write(f'Existing verified test card preserved for {txn.transaction_reference}. Dates and progress unchanged.')
                return
            if txn.transaction_status != Transaction.RENTAL_AGREED:
                raise CommandError('This scenario has progressed; refusing to replace its payment method.')
            try:
                # A new reusable test PaymentMethod, never a real card number.
                method = stripe.PaymentMethod.create(
                    type='card', card={'token': 'tok_visa'},
                    billing_details={'name': 'Scenario Renter'},
                    api_key=settings.STRIPE_CONNECT_SECRET_KEY,
                )
                result = stripe_connect_service.confirm_card_setup(
                    transaction=txn, setup_intent_id='', payment_method_id=method.id,
                )
            except Exception as exc:
                raise CommandError('Stripe test-card setup failed. The scenario remains unverified; fix the Stripe configuration and rerun --rental-ready.') from exc
            if not result.get('ok'):
                raise CommandError(
                    f'Stripe test-card verification failed: {result.get("error", "unknown error")}. '
                    'The scenario remains unverified; rerun --rental-ready after resolving the error.'
                )
            updates = {
                'stripe_payment_method_id': method.id,
                'stripe_customer_id': result['stripe_customer_id'],
                'deposit_card_setup_status': result['card_setup_status'],
                'deposit_cardholder_name': result['cardholder_name'],
                'deposit_card_brand': result['card_brand'],
                'deposit_card_funding': result['card_funding'],
                'deposit_card_last4': result['card_last4'],
                'deposit_test_hold_status': result['test_hold_status'],
                'deposit_test_hold_amount': result['test_hold_amount'],
                'deposit_test_hold_at': result['test_hold_at'],
                'deposit_test_hold_reference': result['test_hold_reference'],
                'amended': timezone.now(),
            }
            Transaction.objects.filter(pk=txn.pk).update(**updates)
            self.stdout.write(self.style.SUCCESS(
                f'Verified Stripe test card for {txn.transaction_reference} (ID {txn.pk}). '
                'Lender checkout evidence is available from the rental start date.'
            ))

    def _repair(self, transaction_id=None):
        markers = [f"SCENARIO:{scenario['name']}" for scenario in SCENARIOS]
        with db_transaction.atomic():
            rows = Transaction.objects.select_for_update().filter(transpact_text_status__in=markers)
            if transaction_id is not None:
                rows = rows.filter(pk=transaction_id)
            rows = list(rows)
            if transaction_id is not None and not rows:
                raise CommandError(f'Transaction ID {transaction_id} is not a known seeded scenario.')
            for txn in rows:
                updates = {}
                if txn.transaction_status != Transaction.RENTAL_ENQUIRY:
                    for field in ('lender_agreed_at', 'renter_agreed_at'):
                        if not getattr(txn, field):
                            updates[field] = timezone.now()
                if (txn.transaction_status == Transaction.RENTAL_DAY_AWAITING_VERIFICATION
                        and not txn.checkout_condition_video_url
                        and not txn.checkout_borrower_video_url
                        and not txn.checkout_borrower_confirmed
                        and not txn.checkout_handover_pin
                        and not txn.checkout_handover_verified_at):
                    updates['transaction_status'] = Transaction.RENTAL_AGREED
                    updates['prev_transaction_status'] = Transaction.RENTAL_ENQUIRY
                if updates:
                    # Seed maintenance must not send notifications or replay payments.
                    Transaction.objects.filter(pk=txn.pk).update(**updates, amended=timezone.now())
                    self.stdout.write(f'Repaired {txn.pk}: {", ".join(updates)}')
                else:
                    self.stdout.write(f'Unchanged {txn.pk}')
        self.stdout.write(self.style.SUCCESS(
            'Repair complete. Dates and evidence preserved. Paid checkout scenarios still require real Stripe test-card verification.'
        ))

    def _move_dates(self, *, commence_today, target_date=None, transaction_id=None):
        # Reuse the website's reservation policy, including holds by other rentals.
        from transaction.views import _holding_statuses, _release_transaction_dates, _reserve_transaction_dates

        today = target_date or Transaction.workflow_today()
        changes = []
        markers = [f"SCENARIO:{scenario['name']}" for scenario in SCENARIOS]
        with db_transaction.atomic():
            queryset = Transaction.objects.select_for_update()
            if transaction_id is None:
                queryset = queryset.filter(transpact_text_status__in=markers)
            else:
                queryset = queryset.filter(pk=transaction_id)
            transactions = list(queryset.order_by('id'))
            if transaction_id is not None and not transactions:
                raise CommandError(f'Transaction ID {transaction_id} does not exist.')
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
                    f'{(txn.transpact_text_status or "Transaction").removeprefix("SCENARIO:")} '
                    f'({txn.transaction_reference}): {old_start} – {old_end} '
                    f'-> {new_start} – {new_end} ({duration.days + 1} rental days)'
                )

        if not changes:
            self.stdout.write('No existing scenario transactions found. Seed scenarios first.')
            return
        for change in changes:
            self.stdout.write(change)
        boundary = 'start' if commence_today else 'end'
        scope = 'scenario transactions' if transaction_id is None else 'transaction'
        when = f'on {today}' if target_date else f'today ({today}, Europe/London)'
        self.stdout.write(self.style.SUCCESS(
            f'Updated {len(changes)} {scope} to {boundary} {when}. '
            'Rental length and workflow progress preserved.'
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
