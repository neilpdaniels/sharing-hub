"""Small, reusable helpers for Rentalution's transactional email."""

from email.mime.image import MIMEImage
from pathlib import Path

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
        # cid images do not depend on an email client being able to fetch an
        # external image URL (or on a recipient being able to access a
        # password-protected preview site).
        'site_url': getattr(settings, 'SITE_URL', 'https://rentalution.co.uk').rstrip('/'),
        'logo_url': 'cid:rentalution-logo',
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
    logo_path = Path(settings.BASE_DIR) / 'brand' / 'images' / 'rentalution.png'
    if logo_path.is_file():
        logo = MIMEImage(logo_path.read_bytes(), _subtype='png')
        logo.add_header('Content-ID', '<rentalution-logo>')
        logo.add_header('Content-Disposition', 'inline', filename='rentalution.png')
        message.attach(logo)
    return message.send(fail_silently=False)
