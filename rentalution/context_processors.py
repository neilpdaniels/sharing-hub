from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def get_transaction_notification_payload(user, session=None):
    if not user or not user.is_authenticated:
        return {
            'unread_message_count': 0,
            'unseen_txn_count': 0,
            'unseen_txn_items': [],
            'txn_login_notice': False,
            'txn_notice_count': 0,
            'txn_notice_items': [],
            'txn_enquiry_notice_count': 0,
            'txn_enquiry_notice_items': [],
        }

    from transaction.models import Transaction, TransactionMessage

    show_login_notice = bool(session.pop('show_txn_login_notice', False)) if session is not None else False
    today = Transaction.workflow_today()

    def _requires_action_and_label(txn):
        actions = set(txn.get_allowed_actions_for_user(user))
        # These labels are deliberately ordered. For example, once a handover
        # code exists, entering it is more useful than re-offering evidence.
        if 'confirm_no_collection' in actions:
            return True, 'Confirm whether collection happened'
        if 'report_missing_return' in actions:
            return True, 'Confirm whether the item was returned'
        if actions.intersection({
            'add_deposit_card', 'use_existing_card', 'confirm_stripe_card',
        }):
            return True, 'Set up your payment card'
        if actions.intersection({
            'confirm_checkout_evidence', 'submit_checkout_borrower_evidence',
        }):
            return True, 'Review checkout evidence — confirm or submit counter-evidence'
        if actions.intersection({
            'confirm_return_evidence', 'submit_lender_return_evidence',
        }):
            return True, 'Review return evidence — confirm or submit counter-evidence'
        if actions.intersection({
            'agree_deposit_return', 'contest_deposit_return',
        }):
            return True, 'Review the deposit proposal — accept or contest it'
        action_labels = (
            ('confirm_lender_contract', 'Confirm the rental contract'),
            ('reinitiate_lender_contract', 'Re-send the rental contract'),
            ('confirm_renter_contract', 'Confirm the rental contract'),
            ('initiate_rental', 'Submit checkout evidence'),
            ('verify_checkout_handover_pin', 'Confirm collection using the renter’s PIN / QR code'),
            ('verify_return_handover_pin', 'Confirm return using the lender’s PIN / QR code'),
            ('submit_return_borrower_evidence', 'Submit return evidence'),
            ('propose_deposit_return', 'Propose the deposit return'),
            ('submit_feedback', 'Leave rental feedback'),
        )
        for action, label in action_labels:
            if action in actions:
                return True, label
        return False, ''

    def _product_name(txn):
        if getattr(txn, 'product', None):
            return txn.product.name
        if getattr(txn, 'order_passive', None) and getattr(txn.order_passive, 'product', None):
            return txn.order_passive.product.name
        return 'Rental item'

    def _date_label(txn):
        if txn.rental_start_date and txn.rental_end_date:
            return f"{txn.rental_start_date:%b %d, %Y} to {txn.rental_end_date:%b %d, %Y}"
        if txn.rental_start_date:
            return f"{txn.rental_start_date:%b %d, %Y}"
        return 'Dates not set'

    lender_pending = Q(user_passive=user) & (
        Q(transaction_status=Transaction.RENTAL_ENQUIRY) |
        Q(transaction_status=Transaction.RENTAL_AGREED) |
        Q(transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION) |
        Q(transaction_status=Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION) |
        Q(transaction_status=Transaction.RENTAL_RETURNED_DEPOSIT_PENDING)
    )

    renter_pending = Q(user_aggressive=user) & (
        Q(transaction_status=Transaction.RENTAL_AGREED) &
        ~Q(deposit_card_setup_status=Transaction.CARD_READY) |
        Q(transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION) |
        Q(transaction_status=Transaction.RENTAL_ONGOING) |
        Q(transaction_status=Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION) |
        Q(transaction_status=Transaction.RENTAL_RETURNED_DEPOSIT_PENDING)
    )

    overdue = (
        Q(rental_start_date__lt=today, checkout_handover_verified_at__isnull=True,
          transaction_status__in=[Transaction.RENTAL_ENQUIRY, Transaction.RENTAL_AGREED,
                                  Transaction.RENTAL_DAY_AWAITING_VERIFICATION]) |
        Q(rental_end_date__lt=today, return_handover_verified_at__isnull=True,
          transaction_status__in=[Transaction.RENTAL_ONGOING, Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION])
    )
    pending_qs = Transaction.objects.filter(lender_pending | renter_pending | overdue).filter(
        Q(user_passive=user) | Q(user_aggressive=user)
    )

    unseen_ids = set(pending_qs.values_list('id', flat=True))
    unseen_items = []
    unseen_count = len(unseen_ids)
    txn_notice_items = []

    if unseen_ids:
        unseen_items = list(
            Transaction.objects.filter(id__in=unseen_ids)
            .filter(Q(user_passive=user) | Q(user_aggressive=user))
            .select_related('product', 'order_passive__product')
            .order_by('-amended', '-created')[:5]
        )

    for txn in unseen_items:
        requires_action, action_label = _requires_action_and_label(txn)
        if not requires_action:
            continue
        txn_notice_items.append({
            'transaction_reference': txn.transaction_reference,
            'product_name': _product_name(txn),
            'date_label': _date_label(txn),
            'action_label': action_label,
            'notice_type': 'transaction_enquiry' if txn.transaction_status == txn.RENTAL_ENQUIRY else 'transaction_update',
        })

    txn_enquiry_notice_items = [
        item for item in txn_notice_items if item.get('notice_type') == 'transaction_enquiry'
    ]

    unread_message_count = TransactionMessage.objects.filter(
        user_to=user,
        read_by_user_to=False,
    ).count()

    return {
        'unread_message_count': unread_message_count,
        'unseen_txn_count': unseen_count,
        'unseen_txn_items': unseen_items,
        'txn_login_notice': show_login_notice and bool(txn_notice_items),
        'txn_notice_count': len(txn_notice_items),
        'txn_notice_items': txn_notice_items,
        'txn_enquiry_notice_count': len(txn_enquiry_notice_items),
        'txn_enquiry_notice_items': txn_enquiry_notice_items,
    }

def from_settings(request):
    return {
        'ENVIRONMENT_NAME': settings.ENVIRONMENT_NAME,
        'ENVIRONMENT_COLOR': settings.ENVIRONMENT_COLOR,
    }


def top_categories(request):
    from common.models import Category
    from common.helpers import get_ordered_top_categories
    try:
        Category.objects.get(slug='top')
        cats = list(get_ordered_top_categories())
    except Category.DoesNotExist:
        cats = []
    return {'top_categories': cats}


def transaction_notifications(request):
    return get_transaction_notification_payload(getattr(request, 'user', None), getattr(request, 'session', None))
