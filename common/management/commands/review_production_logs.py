from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from common.log_review import build_report, report_as_json, report_as_text


class Command(BaseCommand):
    help = 'Create a deterministic error-log digest and optionally e-mail it.'

    def add_arguments(self, parser):
        window = parser.add_mutually_exclusive_group()
        window.add_argument('--hours', type=int, help='Lookback window in hours (1–168; default: 6).')
        window.add_argument('--minutes', type=int, help='Lookback window in minutes (60–10,080).')
        parser.add_argument('--source', choices=('loki',), default='loki', help='Log source (default: loki).')
        parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
        parser.add_argument('--email', action='store_true', help='Send the digest to LOG_REVIEW_RECIPIENTS.')
        parser.add_argument(
            '--email-on-problems-only',
            action='store_true',
            help='With --email, skip a clean OK report.',
        )

    def handle(self, *args, **options):
        if options['minutes'] is not None and not 60 <= options['minutes'] <= 10_080:
            raise CommandError('--minutes must be between 60 and 10,080.')
        lookback_hours = options['hours'] if options['hours'] is not None else (
            options['minutes'] / 60 if options['minutes'] is not None else 6
        )
        try:
            report = build_report(hours=lookback_hours, source=options['source'])
        except (OSError, ValueError, RuntimeError) as exc:
            raise CommandError(f'Log review failed: {exc}') from exc
        output = report_as_json(report) if options['json'] else report_as_text(report)
        self.stdout.write(output)

        should_email = options['email'] and (
            report['status'] != 'OK' or not options['email_on_problems_only']
        )
        if should_email:
            recipients = tuple(getattr(settings, 'LOG_REVIEW_RECIPIENTS', ()))
            if not recipients:
                raise CommandError('LOG_REVIEW_RECIPIENTS is not configured.')
            send_mail(
                subject=f"[{report['status']}] Rentalution log review ({report['window']['minutes']}m)",
                message=report_as_text(report),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=recipients,
                fail_silently=False,
            )
        elif options['email']:
            self.stdout.write('No e-mail sent: report status is OK.')
        return report['status']
