from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from common.models import Category, Order, Product
from transaction.models import Transaction


SCENARIOS = [
    ('scenario-enquiry', Transaction.RENTAL_ENQUIRY, 'Initial enquiry'),
    ('scenario-agreed', Transaction.RENTAL_AGREED, 'Agreement signed'),
    ('scenario-checkout', Transaction.RENTAL_DAY_AWAITING_VERIFICATION, 'Checkout evidence pending'),
    ('scenario-ongoing', Transaction.RENTAL_ONGOING, 'Rental ongoing'),
    ('scenario-return', Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION, 'Return evidence pending'),
    ('scenario-deposit', Transaction.RENTAL_RETURNED_DEPOSIT_PENDING, 'Deposit review pending'),
    ('scenario-feedback', Transaction.AWAITING_FEEDBACK, 'Feedback window open'),
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
        category = Category.objects.create(title=f'Scenario Tools {timezone.now().strftime("%Y%m%d%H%M%S")}')
        product = Product.objects.create(category_id=category, name='Scenario Drill')
        order = Order.objects.create(
            product=product,
            user=lender,
            direction=Order.TO_LET,
            expiry_date=timezone.now() + timedelta(days=30),
            status=Order.ACTIVE,
            price=30,
            deposit=80,
            postcode='SW1A1AA',
            max_rental_days=7,
        )

        created = 0
        for scenario_name, status, note in SCENARIOS:
            marker = f'SCENARIO:{scenario_name}'
            txn = Transaction.objects.filter(transpact_text_status=marker).first()
            was_created = txn is None
            if was_created:
                txn = Transaction.objects.create(
                    user_passive=lender,
                    user_aggressive=renter,
                    order_passive=order,
                    product=product,
                    transaction_status=status,
                    prev_transaction_status=Transaction.RENTAL_ENQUIRY,
                    rental_start_date=timezone.localdate() + timedelta(days=1),
                    rental_end_date=timezone.localdate() + timedelta(days=3),
                    quantity=1,
                    price=30,
                    deposit=80,
                    current_spot_value=100,
                    price_as_pct_spot_value=30,
                    deposit_resolution_notes=note,
                    enquiry_message=note,
                    delivery_distance_km=5,
                    delivery_cost=0,
                    rentalution_fee=0,
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
        Product.objects.filter(name='Scenario Drill').delete()
        Category.objects.filter(title__startswith='Scenario Tools ').delete()
        User.objects.filter(username__in=['scenario-lender', 'scenario-renter']).delete()
