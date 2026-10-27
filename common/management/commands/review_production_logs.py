from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from common.log_review import build_report, report_as_json, report_as_text


class Command(BaseCommand):
    help = 'Create a deterministic Loki error-log digest and optionally e-mail it.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=6, help='Lookback window (1–168; default: 6).')
        parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
        parser.add_argument('--email', action='store_true', help='Send the digest to LOG_REVIEW_RECIPIENTS.')

    def handle(self, *args, **options):
        try:
            report = build_report(hours=options['hours'])
        except (OSError, ValueError, RuntimeError) as exc:
            raise CommandError(f'Log review failed: {exc}') from exc
        output = report_as_json(report) if options['json'] else report_as_text(report)
        self.stdout.write(output)

        if options['email']:
            recipients = tuple(getattr(settings, 'LOG_REVIEW_RECIPIENTS', ()))
            if not recipients:
                raise CommandError('LOG_REVIEW_RECIPIENTS is not configured.')
            send_mail(
                subject=f"[{report['status']}] Rentalution log review ({report['window']['hours']}h)",
                message=report_as_text(report),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=recipients,
                fail_silently=False,
            )
        return report['status']
