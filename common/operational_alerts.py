"""Best-effort operational alerts for newly created marketplace records."""

import logging

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


EVENT_SETTINGS = {
    'user_registration': 'NEW_USER_REGISTRATION_ALERTS_ENABLED',
    'order': 'NEW_ORDER_ALERTS_ENABLED',
    'transaction': 'NEW_TRANSACTION_ALERTS_ENABLED',
}


def is_operational_alert_enabled(event_type):
    """Return whether alerts for one operational event type are enabled."""
    setting_name = EVENT_SETTINGS[event_type]
    return bool(getattr(settings, setting_name, True))


def _absolute_url(path):
    return '{}{}'.format(getattr(settings, 'SITE_URL', '').rstrip('/'), path)


def _build_alert(event_type, object_id):
    if event_type == 'user_registration':
        user = get_user_model().objects.get(pk=object_id)
        return {
            'subject': '[Rentalution] New user registration',
            'message': 'Username: {username}\nEmail: {email}\n\nReview: {url}'.format(
                username=user.username,
                email=user.email or '(no email)',
                url=_absolute_url(reverse('admin:auth_user_change', args=(user.pk,))),
            ),
        }

    if event_type == 'order':
        from common.models import Order

        order = Order.objects.select_related('product', 'user').get(pk=object_id)
        return {
            'subject': '[Rentalution] New listing',
            'message': (
                'Listing: {listing}\nOwner: {owner}\nDirection: {direction}\n'
                'Price: {currency} {price:.2f}\n\nReview: {url}'
            ).format(
                listing=order.display_name,
                owner=order.user.username,
                direction=order.get_direction_display(),
                currency=order.currency,
                price=order.price,
                url=_absolute_url(reverse('admin:common_order_change', args=(order.pk,))),
            ),
        }

    if event_type == 'transaction':
        from transaction.models import Transaction

        transaction = Transaction.objects.select_related(
            'order_passive__product', 'user_aggressive', 'user_passive',
        ).get(pk=object_id)
        listing = getattr(transaction.order_passive, 'display_name', '') or getattr(
            transaction.product, 'name', 'Unknown listing'
        )
        return {
            'subject': '[Rentalution] New rental transaction',
            'message': (
                'Reference: {reference}\nListing: {listing}\nBorrower: {borrower}\n'
                'Lender: {lender}\nStatus: {status}\n\nReview: {url}'
            ).format(
                reference=transaction.transaction_reference,
                listing=listing,
                borrower=transaction.user_aggressive.username,
                lender=transaction.user_passive.username,
                status=transaction.get_transaction_status_display(),
                url=_absolute_url(reverse('admin:transaction_transaction_change', args=(transaction.pk,))),
            ),
        }

    raise ValueError('Unknown operational alert event: %s' % event_type)


@shared_task
def send_operational_alert(event_type, object_id):
    """Deliver an operational alert without affecting the originating request."""
    if event_type not in EVENT_SETTINGS:
        logger.error('Ignoring unknown operational alert event %s.', event_type)
        return {'sent': False, 'reason': 'unknown_event'}
    if not is_operational_alert_enabled(event_type):
        return {'sent': False, 'reason': 'disabled'}

    try:
        alert = _build_alert(event_type, object_id)
    except ObjectDoesNotExist:
        return {'sent': False, 'reason': 'record_deleted'}
    except Exception:
        logger.exception('Could not prepare %s operational alert for %s.', event_type, object_id)
        return {'sent': False, 'reason': 'prepare_failed'}

    email_sent = False
    recipients = tuple(getattr(settings, 'OPERATIONAL_ALERT_RECIPIENTS', ()))
    if recipients:
        try:
            send_mail(
                alert['subject'],
                alert['message'],
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
            email_sent = True
        except Exception:
            logger.exception('Could not email %s operational alert for %s.', event_type, object_id)

    discord_sent = False
    webhook_url = getattr(settings, 'DISCORD_OPERATIONAL_ALERT_WEBHOOK_URL', '')
    if webhook_url:
        try:
            requests.post(
                webhook_url,
                json={'content': '{}\n{}'.format(alert['subject'], alert['message'])[:2000]},
                timeout=8,
            ).raise_for_status()
            discord_sent = True
        except Exception:
            logger.exception('Could not send %s operational Discord alert for %s.', event_type, object_id)

    return {'sent': email_sent or discord_sent, 'email_sent': email_sent, 'discord_sent': discord_sent}
