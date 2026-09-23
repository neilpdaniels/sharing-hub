from datetime import date, timedelta
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from transaction.models import Transaction


# Stripe's documented test tokens: no PAN/CVC is stored or printed by this command.
SUCCESS_CASES = (
    ('short_visa_debit', 3, 'tok_visa_debit', 'short', 'manual'),
    ('standard_visa_credit', 7, 'tok_visa', 'standard', 'manual'),
    ('standard_mastercard_credit', 30, 'tok_mastercard', 'standard', 'manual'),
    ('long_visa_debit', 31, 'tok_visa_debit', 'long', 'automatic'),
)
DECLINE_CASES = (
    ('generic_decline', 'tok_visa_chargeDeclined', 'card_declined'),
    ('insufficient_funds', 'tok_visa_chargeDeclinedInsufficientFunds', 'card_declined'),
    ('lost_card', 'tok_visa_chargeDeclinedLostCard', 'card_declined'),
    ('stolen_card', 'tok_visa_chargeDeclinedStolenCard', 'card_declined'),
    ('expired_card', 'tok_chargeDeclinedExpiredCard', 'expired_card'),
    ('incorrect_cvc', 'tok_chargeDeclinedIncorrectCvc', 'incorrect_cvc'),
    ('processing_error', 'tok_chargeDeclinedProcessingError', 'processing_error'),
    ('velocity_limit', 'tok_visa_chargeDeclinedVelocityLimitExceeded', 'card_declined'),
)
ATTACHED_DECLINE_CASES = (
    ('decline_after_attaching', 'tok_chargeCustomerFail', 'card_declined'),
    ('lost_card_after_attaching', 'tok_visa_chargeCustomerFailLostCard', 'card_declined'),
)
MATRIX_VERSION = 'v3'


class Command(BaseCommand):
    help = 'Run the non-production Stripe Connect card/deposit matrix. Successful test holds are cancelled or refunded.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Create Stripe Sandbox test objects. Without this flag the matrix is only printed.')
        parser.add_argument('--include-declines', action='store_true', help='Also verify issuer-decline and saved-card decline paths.')
        parser.add_argument('--webhooks', action='store_true', help='Check the managed Stripe CLI listener and offer to start it before executing.')

    def handle(self, *args, **options):
        environment = getattr(settings, 'ENVIRONMENT_NAME', '').lower()
        key = getattr(settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        if environment == 'production' or not key.startswith(('sk_test_', 'rk_test_')):
            raise CommandError('This command requires a non-production Stripe test/restricted test key.')

        self._verify_policy_matrix()
        if options['webhooks']:
            self._ensure_webhook_listener()
        if not options['execute']:
            self.stdout.write(self.style.WARNING('Dry run only. Add --execute to create and clean up Sandbox test payments.'))
            for name, days, _token, tier, capture_method in SUCCESS_CASES:
                self.stdout.write(f'{name}: {days} days → {tier} tier, {capture_method} deposit handling')
            return

        try:
            import stripe
        except ImportError as exc:
            raise CommandError('Install the Stripe SDK before running this command.') from exc
        stripe.api_key = key
        run_id = uuid4().hex[:12]
        self.stdout.write(f'Running Stripe Sandbox matrix {MATRIX_VERSION}-{run_id}.')

        for name, _days, token, _tier, capture_method in SUCCESS_CASES:
            payment_method = stripe.PaymentMethod.create(type='card', card={'token': token})
            intent = stripe.PaymentIntent.create(
                amount=100, currency='gbp', payment_method=payment_method.id,
                confirm=True, capture_method=capture_method,
                automatic_payment_methods={'enabled': True, 'allow_redirects': 'never'},
                metadata={'purpose': 'rentalution_connect_matrix', 'case': name},
                idempotency_key=f'rentalution-matrix-{MATRIX_VERSION}-{run_id}-{name}',
            )
            status = getattr(intent, 'status', '')
            if capture_method == 'manual':
                if status != 'requires_capture':
                    raise CommandError(f'{name}: expected requires_capture, got {status}.')
                stripe.PaymentIntent.cancel(intent.id)
                outcome = 'authorisation cancelled'
            else:
                if status not in ('succeeded', 'processing'):
                    raise CommandError(f'{name}: expected successful capture, got {status}.')
                stripe.Refund.create(payment_intent=intent.id, metadata={'purpose': 'rentalution_connect_matrix_cleanup'})
                outcome = 'captured then fully refunded'
            self.stdout.write(self.style.SUCCESS(f'PASS {name}: {outcome}'))

        if options['include_declines']:
            for name, token, expected_code in DECLINE_CASES:
                try:
                    method = stripe.PaymentMethod.create(type='card', card={'token': token})
                    stripe.PaymentIntent.create(
                        amount=100, currency='gbp', payment_method=method.id, confirm=True,
                        automatic_payment_methods={'enabled': True, 'allow_redirects': 'never'},
                        metadata={'purpose': 'rentalution_connect_matrix', 'case': name},
                        idempotency_key=f'rentalution-matrix-{MATRIX_VERSION}-{run_id}-{name}',
                    )
                except Exception as exc:
                    code = getattr(exc, 'code', '')
                    if code != expected_code:
                        raise CommandError(f'{name}: expected {expected_code}, got {code or type(exc).__name__}.') from exc
                    self.stdout.write(self.style.SUCCESS(f'PASS {name}: {expected_code}'))
                else:
                    raise CommandError(f'{name}: Stripe unexpectedly accepted the decline test card.')

            for name, token, expected_code in ATTACHED_DECLINE_CASES:
                customer = stripe.Customer.create(email=f'{name}@rentalution.test')
                method = stripe.PaymentMethod.create(type='card', card={'token': token})
                stripe.PaymentMethod.attach(method.id, customer=customer.id)
                try:
                    stripe.PaymentIntent.create(
                        amount=100, currency='gbp', customer=customer.id,
                        payment_method=method.id, confirm=True,
                        automatic_payment_methods={'enabled': True, 'allow_redirects': 'never'},
                        metadata={'purpose': 'rentalution_connect_matrix', 'case': name},
                        idempotency_key=f'rentalution-matrix-{MATRIX_VERSION}-{run_id}-{name}',
                    )
                except Exception as exc:
                    code = getattr(exc, 'code', '')
                    if code != expected_code:
                        raise CommandError(f'{name}: expected {expected_code}, got {code or type(exc).__name__}.') from exc
                    self.stdout.write(self.style.SUCCESS(f'PASS {name}: {expected_code} after Customer attachment'))
                else:
                    raise CommandError(f'{name}: Stripe unexpectedly accepted the attached decline test card.')

    def _verify_policy_matrix(self):
        today = date.today()
        for name, days, _token, expected_tier, expected_capture in SUCCESS_CASES:
            transaction = Transaction(rental_start_date=today, rental_end_date=today + timedelta(days=days - 1))
            if transaction.get_deposit_policy_tier() != expected_tier:
                raise CommandError(f'{name}: application policy tier mismatch.')
            actual_capture = 'automatic' if transaction.get_deposit_policy_tier() == 'long' else 'manual'
            if actual_capture != expected_capture:
                raise CommandError(f'{name}: application capture policy mismatch.')

    def _ensure_webhook_listener(self):
        log_dir = Path(settings.BASE_DIR) / 'logs'
        log_dir.mkdir(exist_ok=True)
        pid_path = log_dir / 'stripe_listener.pid'
        secret_path = Path(getattr(settings, 'STRIPE_CONNECT_WEBHOOK_SECRET_FILE'))
        if pid_path.exists():
            try:
                os.kill(int(pid_path.read_text().strip()), 0)
                if secret_path.exists() and secret_path.read_text().strip().startswith('whsec_'):
                    self.stdout.write('Managed Stripe CLI listener is already running.')
                    return
            except (OSError, ValueError):
                pass

        if not sys.stdin.isatty():
            raise CommandError('No managed Stripe CLI listener is running. Run interactively with --webhooks to start one.')
        answer = input('Stripe CLI listener is not running. Start it now? [y/N] ').strip().lower()
        if answer not in ('y', 'yes'):
            raise CommandError('Stripe CLI listener is required for webhook verification.')
        if not shutil.which('stripe'):
            raise CommandError('Stripe CLI is not installed or not on PATH. Run stripe login after installing it.')
        log_path = log_dir / 'stripe_listen.log'
        with log_path.open('w', encoding='utf-8') as log_handle:
            process = subprocess.Popen(
                ['stripe', 'listen', '--forward-to', 'localhost:8000/transaction/stripe/connect/webhook/'],
                stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True,
            )
        pid_path.write_text(str(process.pid), encoding='utf-8')
        os.chmod(pid_path, 0o600)
        for _ in range(50):
            time.sleep(0.2)
            if log_path.exists():
                import re
                match = re.search(r'(whsec_[A-Za-z0-9_]+)', log_path.read_text(encoding='utf-8'))
                if match:
                    secret_path.parent.mkdir(exist_ok=True)
                    secret_path.write_text(f'{match.group(1)}\n', encoding='utf-8')
                    os.chmod(secret_path, 0o600)
                    self.stdout.write(self.style.SUCCESS('Managed Stripe CLI listener started; server and matrix share its runtime secret.'))
                    return
            if process.poll() is not None:
                break
        raise CommandError(f'Stripe CLI did not become ready. Inspect {log_path}.')
