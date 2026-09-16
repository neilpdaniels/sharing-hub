"""Participant confirmation for bookings with no recorded collection."""
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Transaction, TransactionMessage


def confirm_no_collection(txn, user):
    with transaction.atomic():
        locked = Transaction.objects.select_for_update().get(pk=txn.pk)
        if 'confirm_no_collection' not in locked.get_allowed_actions_for_user(user):
            raise ValidationError('This booking no longer needs collection confirmation. Refresh and try again.')
        locked.prev_transaction_status = locked.transaction_status
        locked.transaction_status = locked.CANCEL_ACCEPTED
        locked.transaction_status_raised_by = user
        note = '[NO_COLLECTION_CONFIRMED] Participant confirmed that collection did not happen.'
        locked.deposit_resolution_notes = '\n'.join(filter(None, [locked.deposit_resolution_notes, note]))
        locked.save(update_fields=['prev_transaction_status', 'transaction_status',
                                   'transaction_status_raised_by', 'deposit_resolution_notes', 'amended'])
        TransactionMessage.objects.create(
            transaction=locked, user_from=user,
            user_to=locked.user_aggressive if user.pk == locked.user_passive_id else locked.user_passive,
            subject='Collection did not happen', description=note.split('] ', 1)[1],
            is_system_generated=True,
        )
    txn.refresh_from_db()


def report_non_return(txn, user, reason=''):
    with transaction.atomic():
        locked = Transaction.objects.select_for_update().get(pk=txn.pk)
        if user.pk != locked.user_passive_id or locked.get_overdue_kind() != 'return':
            raise ValidationError('Only the lender can report an unconfirmed return after the return date.')
        locked.prev_transaction_status = locked.transaction_status
        locked.transaction_status = locked.DISPUTE_REQUESTED
        locked.transaction_status_raised_by = user
        locked.deposit_status = locked.DEPOSIT_MEDIATION
        locked.deposit_resolution_notes = '\n'.join(filter(None, [locked.deposit_resolution_notes,
            f'Lender reported missing return. {reason}'.strip()]))
        locked.save(update_fields=['prev_transaction_status', 'transaction_status',
            'transaction_status_raised_by', 'deposit_status', 'deposit_resolution_notes', 'amended'])
        from .signals import _ensure_dispute_case
        _ensure_dispute_case(locked)
        TransactionMessage.objects.create(
            transaction=locked, user_from=user, user_to=locked.user_aggressive,
            subject='Missing return reported',
            description='The lender confirmed the item was not returned. Non-return dispute review is now open.',
            include_admin=True, is_system_generated=True,
        )
    txn.refresh_from_db()
