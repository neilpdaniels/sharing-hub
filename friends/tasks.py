from celery import shared_task
from django.contrib.auth.models import User
from django.conf import settings
from common.emails import send_branded_email
from common.failures import record_site_failure


@shared_task
def send_friend_request_notification(from_user_id, to_user_id):
    """Notify an existing member that they have received a friend request."""
    try:
        from_user = User.objects.get(id=from_user_id)
        to_user = User.objects.get(id=to_user_id)
    except User.DoesNotExist:
        return

    from_name = from_user.get_full_name() or from_user.username
    subject = f"{from_name} wants to connect on rentalution"
    try:
        send_branded_email(
            subject=subject, recipient=to_user.email, heading='You have a new connection request',
            intro=f'{from_name} has sent you a friend request on Rentalution.',
            cta_label='Review request', cta_url=f"{getattr(settings, 'SITE_URL', 'https://rentalution.co.uk')}/friends/",
        )
    except Exception as exc:
        record_site_failure(
            'Friend request notification email failed',
            details=f'Failed to notify {to_user.email} about a friend request from {from_user.id}.',
            exception=exc,
            context={
                'from_user_id': from_user.id,
                'from_user_email': from_user.email,
                'to_user_id': to_user.id,
                'to_user_email': to_user.email,
            },
        )
        raise


@shared_task
def send_friend_invite_email(from_user_id, invitee_email):
    """Send an invitation email to a non-member."""
    try:
        from_user = User.objects.get(id=from_user_id)
    except User.DoesNotExist:
        return

    from_name = from_user.get_full_name() or from_user.username
    site_url = getattr(settings, 'SITE_URL', 'https://rentalution.co.uk')
    subject = f"{from_name} has invited you to join rentalution"
    try:
        send_branded_email(
            subject=subject, recipient=invitee_email, heading='You’re invited to Rentalution',
            intro=f'{from_name} thinks you might enjoy borrowing and lending locally.',
            cta_label='Join Rentalution', cta_url=f'{site_url}/account/register/',
            steps=['Create your free account.', 'Find what you need or list something you own.'],
        )
    except Exception as exc:
        record_site_failure(
            'Friend invite email failed',
            details=f'Failed to send invite email to {invitee_email} from user {from_user.id}.',
            exception=exc,
            context={
                'from_user_id': from_user.id,
                'from_user_email': from_user.email,
                'invitee_email': invitee_email,
            },
        )
        raise
