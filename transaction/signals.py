from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import DisputeCase, Transaction, TransactionMessage
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
    Transaction.DISPUTE_DECIDED,
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
    return f'{_transition_title(instance)}'


def _transition_title(instance):
    titles = {
        Transaction.RENTAL_AGREED: 'Rental agreed',
        Transaction.RENTAL_DAY_AWAITING_VERIFICATION: 'Rental day is here',
        Transaction.RENTAL_ONGOING: 'Rental started',
        Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION: 'Return started',
        Transaction.RENTAL_RETURNED_DEPOSIT_PENDING: 'Item returned',
        Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED: 'Deposit return needs review',
        Transaction.DISPUTE_REQUESTED: 'Dispute requested',
        Transaction.AWAITING_FEEDBACK: 'Rental complete',
        Transaction.FEEDBACK_ONE_SIDED: 'Feedback received',
        Transaction.RENTAL_PROCESS_COMPLETED: 'Rental fully complete',
        Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED: 'Rental closed',
        Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK: 'Rental closed',
        Transaction.DISPUTE_DECIDED: 'Dispute decided',
        Transaction.CANCEL_ACCEPTED: 'Rental cancelled',
    }
    return f'{titles.get(instance.transaction_status, instance.get_transaction_status_display())} · {instance.transaction_reference}'


def _transition_description(instance):
    next_steps = {
        Transaction.RENTAL_AGREED: 'Review and confirm the rental agreement, then add the borrower payment card if required.',
        Transaction.RENTAL_DAY_AWAITING_VERIFICATION: 'Complete the checkout evidence and handover confirmation.',
        Transaction.RENTAL_ONGOING: 'Keep the item safe and return it on the agreed return date.',
        Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION: 'Complete the return evidence and handover confirmation.',
        Transaction.RENTAL_RETURNED_DEPOSIT_PENDING: 'Review and agree the deposit return.',
        Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED: 'Review the deposit proposal or continue with dispute handling.',
        Transaction.DISPUTE_REQUESTED: 'Keep your evidence and messages available for dispute review.',
        Transaction.AWAITING_FEEDBACK: 'Leave feedback about the rental experience.',
        Transaction.FEEDBACK_ONE_SIDED: 'The other party can still leave their feedback.',
        Transaction.RENTAL_PROCESS_COMPLETED: 'This rental is complete.',
        Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED: 'This rental is closed.',
        Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK: 'This rental is closed.',
        Transaction.DISPUTE_DECIDED: 'Review the dispute outcome and deposit decision.',
        Transaction.CANCEL_ACCEPTED: 'This rental has been cancelled.',
    }
    status_label = instance.get_transaction_status_display()
    next_step = next_steps.get(instance.transaction_status, 'Review the booking for the next available step.')
    return f'{status_label}. Next step: {next_step}'


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


def _ensure_dispute_case(txn, *, owner=None):
    if txn.transaction_status not in {txn.DISPUTE_REQUESTED, txn.CANCEL_ACCEPTED} and txn.deposit_status != txn.DEPOSIT_MEDIATION:
        return None

    reason_code = DisputeCase.REASON_GENERAL
    summary = (txn.deposit_resolution_notes or '').strip()
    if '[MISSING_RENTAL_VOIDED]' in summary:
        reason_code = DisputeCase.REASON_MISSING_RENTAL
    elif 'missing return' in summary.lower():
        reason_code = DisputeCase.REASON_MISSING_RETURN
    elif 'deposit' in summary.lower():
        reason_code = DisputeCase.REASON_DEPOSIT_CONTEST
    elif 'arbitration' in summary.lower() or 'dispute team' in summary.lower():
        reason_code = DisputeCase.REASON_DISPUTE_TEAM

    dispute_case, created = DisputeCase.objects.get_or_create(
        transaction=txn,
        reason_code=reason_code,
        defaults={
            'owner': owner,
            'raised_by': txn.transaction_status_raised_by,
            'status': DisputeCase.STATUS_OPEN,
            'outcome': DisputeCase.OUTCOME_PENDING,
            'summary': summary or f'Dispute raised for transaction {txn.transaction_reference}.',
            'evidence_bundle': {
                'transaction_reference': txn.transaction_reference,
                'transaction_status': txn.transaction_status,
                'raised_by_id': txn.transaction_status_raised_by_id,
                'deposit_status': txn.deposit_status,
                'notes': summary,
            },
        },
    )

    if not created:
        updates = []
        if owner and dispute_case.owner_id != owner.id:
            dispute_case.owner = owner
            updates.append('owner')
        if summary and dispute_case.summary != summary:
            dispute_case.summary = summary
            updates.append('summary')
        if txn.transaction_status_raised_by_id and dispute_case.raised_by_id != txn.transaction_status_raised_by_id:
            dispute_case.raised_by = txn.transaction_status_raised_by
            updates.append('raised_by')
        if updates:
            dispute_case.save(update_fields=updates + ['amended'])

    return dispute_case


@receiver(post_save, sender=Transaction)
def notify_major_status_transition(sender, instance, created, **kwargs):
    if created:
        if instance.transaction_status in {instance.DISPUTE_REQUESTED, instance.CANCEL_ACCEPTED}:
            _ensure_dispute_case(instance)
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

    if instance.transaction_status in {instance.DISPUTE_REQUESTED, instance.CANCEL_ACCEPTED}:
        _ensure_dispute_case(instance)


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
