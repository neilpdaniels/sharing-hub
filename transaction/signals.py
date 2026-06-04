from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Transaction, TransactionMessage
from .tasks import send_new_message_push_notification
from common.models import System


MAJOR_STATUS_NOTIFICATION_SET = {
    Transaction.RENTAL_AGREED,
    Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
    Transaction.RENTAL_ONGOING,
    Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
    Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
    Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED,
    Transaction.DISPUTE_REQUESTED,
    Transaction.AWAITING_FEEDBACK,
    Transaction.FEEDBACK_ONE_SIDED,
    Transaction.RENTAL_PROCESS_COMPLETED,
    Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
    Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
    Transaction.CANCEL_ACCEPTED,
}


def _configured_major_statuses():
    """
    Resolve configurable major status notification list.

    Priority:
    1) common.System row with name='TRANSACTION_MAJOR_NOTIFICATION_STATUSES'
       value='RAGR,RDAYAWV,...'
    2) settings.TRANSACTION_MAJOR_NOTIFICATION_STATUSES (list/tuple/string)
    3) built-in defaults in MAJOR_STATUS_NOTIFICATION_SET
    """
    try:
        system_value = (
            System.objects.filter(name='TRANSACTION_MAJOR_NOTIFICATION_STATUSES')
            .order_by('-amended')
            .values_list('value', flat=True)
            .first()
        )
    except Exception:
        system_value = None

    raw_value = system_value
    if raw_value is None:
        raw_value = getattr(settings, 'TRANSACTION_MAJOR_NOTIFICATION_STATUSES', None)

    if raw_value is None:
        return set(MAJOR_STATUS_NOTIFICATION_SET)

    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(item).strip() for item in raw_value if str(item).strip()]
    else:
        candidates = [part.strip() for part in str(raw_value).split(',') if part.strip()]

    valid_codes = {choice[0] for choice in Transaction.TRANSACTION_STATUS_CHOICES}
    configured = {code for code in candidates if code in valid_codes}
    return configured or set(MAJOR_STATUS_NOTIFICATION_SET)


def _transition_subject(instance):
    return f'Transaction update {instance.transaction_reference}: {instance.get_transaction_status_display()}'


def _transition_description(instance):
    prev_label = dict(instance.TRANSACTION_STATUS_CHOICES).get(instance.prev_transaction_status, instance.prev_transaction_status)
    new_label = instance.get_transaction_status_display()
    return (
        f'Transaction status changed from "{prev_label}" to "{new_label}". '
        f'Reference: {instance.transaction_reference}.'
    )


def _create_system_transition_message(*, txn, user_from, user_to):
    if not user_from or not user_to or user_from == user_to:
        return
    TransactionMessage.objects.create(
        user_from=user_from,
        user_to=user_to,
        transaction=txn,
        subject=_transition_subject(txn),
        description=_transition_description(txn),
        email_to_recepient=True,
        include_admin=(txn.transaction_status in {txn.RENTAL_RETURNED_DEPOSIT_CONTESTED, txn.DISPUTE_REQUESTED}),
        is_system_generated=True,
    )


@receiver(post_save, sender=Transaction)
def notify_major_status_transition(sender, instance, created, **kwargs):
    if created:
        return
    if instance.transaction_status == instance.prev_transaction_status:
        return
    if instance.transaction_status not in _configured_major_statuses():
        return

    actor_id = instance.transaction_status_raised_by_id
    if actor_id == instance.user_passive_id:
        _create_system_transition_message(
            txn=instance,
            user_from=instance.user_passive,
            user_to=instance.user_aggressive,
        )
        return
    if actor_id == instance.user_aggressive_id:
        _create_system_transition_message(
            txn=instance,
            user_from=instance.user_aggressive,
            user_to=instance.user_passive,
        )
        return

    # System/async transitions without a raised_by user: notify both parties.
    _create_system_transition_message(
        txn=instance,
        user_from=instance.user_passive,
        user_to=instance.user_aggressive,
    )
    _create_system_transition_message(
        txn=instance,
        user_from=instance.user_aggressive,
        user_to=instance.user_passive,
    )


# move into order.save
# @receiver(post_save, sender=Order)
# def update_summary_prices(sender, instance, created, **kwargs):
#     # order = instance
#     logging.error("received order save")
#     updateSummaryPrices(instance)


@receiver(post_save, sender=TransactionMessage)
def trigger_message_push_notification(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.user_from_id == instance.user_to_id:
        return

    if instance.is_system_generated and not instance.email_to_recepient:
        TransactionMessage.objects.filter(pk=instance.pk).update(email_to_recepient=True)

    send_new_message_push_notification.delay(instance.id)