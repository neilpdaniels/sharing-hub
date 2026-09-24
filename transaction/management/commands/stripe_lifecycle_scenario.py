"""Run a complete Stripe test-mode transaction lifecycle without either UI."""

from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from account.models import Profile
from transaction.models import PaymentAttempt, StripeSettlement, Transaction
from transaction.stripe_connect import stripe_connect_service


CASES = {
    'full-release': {
        'return_amount': Decimal('80.00'),
        'description': 'Charge rental, transfer rental proceeds, then cancel the full £80.00 deposit hold.',
    },
    'partial-award': {
        'return_amount': Decimal('60.00'),
        'description': 'Charge rental, transfer rental proceeds, then capture a £20.00 deposit award.',
    },
    'fee-shortfall': {
        'return_amount': Decimal('79.00'),
        'description': 'Charge rental, transfer rental proceeds, then capture a £1.00 deposit award to exercise the fee-shortfall path.',
    },
}


class Command(BaseCommand):
    help = (
        'Create and advance a fresh non-production transaction through the real Stripe '
        'test-mode rental, return, and deposit-settlement lifecycle.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--case', choices=CASES, default='full-release',
            help='Settlement outcome to exercise (default: full-release).',
        )
        parser.add_argument(
            '--destination-account', metavar='acct_...',
            help=(
                'Stripe test Connect account for the scenario lender. Required with --execute; '
                'it must be enabled to receive transfers in the Stripe Sandbox.'
            ),
        )
        parser.add_argument(
            '--execute', action='store_true',
            help='Create real Stripe Sandbox objects. Without this flag, print the planned flow only.',
        )

    def handle(self, *args, **options):
        self.case = options['case']
        self.definition = CASES[self.case]
        self._validate_environment(execute=options['execute'])

        if not options['execute']:
            self._print_plan()
            return

        destination_account = (options['destination_account'] or '').strip()
        if not destination_account.startswith('acct_'):
            raise CommandError('--execute requires --destination-account=acct_... for an enabled Stripe Sandbox Connect account.')

        # This recreates the marked seed transaction and verifies a Stripe test
        # card without needing the web/mobile card form. It is deliberately
        # unavailable in production in the seed command as well.
        call_command('seed_transaction_scenarios', '--reset', verbosity=0)
        call_command('seed_transaction_scenarios', '--rental-ready', verbosity=0)
        txn = Transaction.objects.get(transpact_text_status='SCENARIO:scenario-rental-ready')
        # Make all amount components visible in the resulting PaymentIntent:
        # £30 rental + £10 delivery + £4 platform fee = £44 renter charge.
        # These are FloatFields. Keep the in-memory instance aligned with the
        # persisted field type because it is reused throughout this runner.
        txn.delivery_cost = 10.00
        txn.rentalution_fee = 4.00
        txn.save(update_fields=['delivery_cost', 'rentalution_fee', 'amended'])

        lender_profile = Profile.objects.get(user=txn.user_passive)
        existing_owner = Profile.objects.filter(
            stripe_connect_account_id=destination_account,
        ).exclude(pk=lender_profile.pk).first()
        if existing_owner:
            raise CommandError(
                f'{destination_account} is already linked to local profile {existing_owner.pk}. '
                'Use a dedicated Sandbox Connect account for this runner.'
            )
        lender_profile.stripe_connect_account_id = destination_account
        lender_profile.stripe_connect_transfers_enabled = True
        lender_profile.stripe_connect_payouts_enabled = True
        lender_profile.save(update_fields=[
            'stripe_connect_account_id', 'stripe_connect_transfers_enabled',
            'stripe_connect_payouts_enabled',
        ])

        self.stdout.write(f'Using transaction {txn.transaction_reference} (ID {txn.id}) for {self.case}.')
        self._collect_rental_payment(txn)
        self._collect_deposit_hold(txn)
        self._transfer_rental_proceeds(txn)
        self._settle_deposit(txn)
        self.stdout.write(self.style.SUCCESS(
            f'PASS {self.case}: transaction {txn.transaction_reference} completed. '
            'Inspect the printed Stripe IDs and the transaction payment summary/ledger.'
        ))

    def _validate_environment(self, *, execute):
        environment = getattr(settings, 'ENVIRONMENT_NAME', '').strip().lower()
        key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '') or ''
        if environment == 'production':
            raise CommandError('This command is disabled in production.')
        if execute and not key.startswith(('sk_test_', 'rk_test_')):
            raise CommandError('--execute requires STRIPE_CONNECT_SECRET_KEY to be a Stripe test/restricted test key.')

    def _print_plan(self):
        definition = self.definition
        self.stdout.write(f'Stripe lifecycle scenario: {self.case}')
        self.stdout.write(definition['description'])
        self.stdout.write('Fresh seed: rental £30.00 + delivery £10.00 + service fee £4.00; deposit £80.00.')
        self.stdout.write('The scenario will create a test card, rental PaymentIntent, deposit PaymentIntent, rental transfer, and deposit settlement.')
        self.stdout.write('Run with --execute --destination-account=acct_... to create Stripe Sandbox objects.')

    def _collect_rental_payment(self, txn):
        result = stripe_connect_service.collect_rental_payment(transaction=txn)
        self._require_ok('rental payment', result)
        txn.payment_status = result['payment_status']
        txn.payment_collection_requested_at = result['collection_requested_at']
        txn.payment_collection_reference = result['collection_reference']
        if result.get('stripe_customer_id'):
            txn.stripe_customer_id = result['stripe_customer_id']
        txn.save()
        attempt = PaymentAttempt.objects.filter(
            transaction=txn,
            failure_point=PaymentAttempt.POINT_RENTAL_CAPTURE,
        ).order_by('-id').first()
        context = attempt.context if attempt else {}
        self.stdout.write(
            f"Rental PaymentIntent {txn.payment_collection_reference}: "
            f"£{result['charged_amount']:.2f}, status={result['payment_intent_status']}; "
            f"Stripe fee £{Decimal(str(context.get('stripe_processing_fee', 0))):.2f}; "
            f"net £{Decimal(str(context.get('stripe_net_amount', 0))):.2f}"
        )

    def _collect_deposit_hold(self, txn):
        result = stripe_connect_service.collect_deposit_hold(transaction=txn)
        self._require_ok('deposit hold', result)
        txn.deposit_collection_status = result['collection_status']
        txn.deposit_collection_requested_at = result['collection_requested_at']
        txn.deposit_collection_reference = result['collection_reference']
        if result.get('stripe_customer_id'):
            txn.stripe_customer_id = result['stripe_customer_id']
        txn.save()
        self.stdout.write(
            f"Deposit PaymentIntent {txn.deposit_collection_reference}: "
            f"£{txn.deposit:.2f}, status={result['payment_intent_status']}"
        )

    def _transfer_rental_proceeds(self, txn):
        txn.return_handover_verified_at = timezone.now()
        txn.save(update_fields=['return_handover_verified_at', 'amended'])
        result = stripe_connect_service.transfer_rental_proceeds(transaction=txn)
        self._require_ok('rental proceeds transfer', result)
        gross = (txn.quantity or 0) * (txn.price or 0) + (txn.delivery_cost or 0)
        self.stdout.write(f"Rental transfer {result.get('transfer_id', '')}: lender gross £{gross:.2f}")

    def _settle_deposit(self, txn):
        result = stripe_connect_service.resolve_deposit_hold(
            transaction=txn,
            return_amount=self.definition['return_amount'],
        )
        self._require_ok('deposit settlement', result)
        award = Decimal(str(result['charged_amount']))
        transfer = stripe_connect_service.transfer_deposit_award(
            transaction=txn,
            payment_intent_id=txn.deposit_collection_reference,
            award_amount=award,
        )
        self._require_ok('deposit award transfer', transfer)
        settlement = StripeSettlement.objects.get(
            transaction=txn,
            kind=StripeSettlement.KIND_DEPOSIT,
        )
        self.stdout.write(
            f"Deposit {result['resolution_action']}: charged £{award:.2f}; "
            f"lender transfer £{Decimal(str(settlement.net_transfer_amount)):.2f}; "
            f"Stripe fee £{Decimal(str(settlement.stripe_fee)):.2f}; "
            f"shortfall £{Decimal(str(settlement.platform_shortfall)):.2f}"
        )

    @staticmethod
    def _require_ok(stage, result):
        if not result.get('ok'):
            raise CommandError(f'{stage} failed: {result.get("error") or "unknown error"}')
