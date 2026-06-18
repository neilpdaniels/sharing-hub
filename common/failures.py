import logging
import traceback

from django.conf import settings
from django.core.mail import mail_admins

from .models import SiteFailure

logger = logging.getLogger(__name__)


def record_site_failure(title, details='', exception=None, context=None):
    """Persist a site failure and notify admins if possible."""
    exception_text = ''
    traceback_text = ''

    if exception is not None:
        exception_text = f'{exception.__class__.__name__}: {exception}'
        traceback_text = traceback.format_exc()

    message_parts = [part for part in [details, exception_text, traceback_text] if part]
    message = '\n\n'.join(message_parts)

    failure = SiteFailure.objects.create(
        title=title[:255],
        details=message,
        context=context or {},
    )

    admin_subject = f'[{getattr(settings, "ENVIRONMENT_NAME", "Rentalution")}] {title}'
    try:
        mail_admins(admin_subject, message or title)
    except Exception:
        logger.exception('Failed to mail admins for site failure %s', failure.id)

    return failure
