from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings


@shared_task
def send_friend_request_notification(from_user_id, to_user_id):
    """Notify an existing member that they have received a friend request."""
    try:
        from_user = User.objects.get(id=from_user_id)
        to_user = User.objects.get(id=to_user_id)
    except User.DoesNotExist:
        return

    from_name = from_user.get_full_name() or from_user.username
    subject = f"{from_name} wants to connect on Sharing Hub"
    message = (
        f"Hi {to_user.first_name or to_user.username},\n\n"
        f"{from_name} ({from_user.email}) has sent you a friend request on Sharing Hub.\n\n"
        f"Log in to accept or decline:\n"
        f"{getattr(settings, 'SITE_URL', 'https://sharing-hub.com')}/friends/\n\n"
        f"The Sharing Hub team"
    )
    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sharing-hub.com'),
        [to_user.email],
        fail_silently=True,
    )


@shared_task
def send_friend_invite_email(from_user_id, invitee_email):
    """Send an invitation email to a non-member."""
    try:
        from_user = User.objects.get(id=from_user_id)
    except User.DoesNotExist:
        return

    from_name = from_user.get_full_name() or from_user.username
    site_url = getattr(settings, 'SITE_URL', 'https://sharing-hub.com')
    subject = f"{from_name} has invited you to join Sharing Hub"
    message = (
        f"Hi,\n\n"
        f"{from_name} ({from_user.email}) thinks you might enjoy Sharing Hub — "
        f"a community marketplace for sharing and trading.\n\n"
        f"Sign up for free at:\n{site_url}/account/register/\n\n"
        f"The Sharing Hub team"
    )
    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sharing-hub.com'),
        [invitee_email],
        fail_silently=True,
    )
