"""Small, reusable helpers for Rentalution's transactional email."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_branded_email(*, subject, recipient, heading, intro, cta_label='', cta_url='',
                       details=None, steps=None):
    """Send a responsive HTML email with a reliable plain-text alternative."""
    if not recipient:
        return 0

    context = {
        'heading': heading,
        'intro': intro,
        'cta_label': cta_label,
        'cta_url': cta_url,
        'details': details or [],
        'steps': steps or [],
    }
    html_body = render_to_string('common/emails/transactional_email.html', context)
    text_body = strip_tags(html_body).replace('&nbsp;', ' ')
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        to=[recipient],
    )
    message.attach_alternative(html_body, 'text/html')
    return message.send(fail_silently=False)
