from django.conf import settings
from django.db.models import Q
from django.utils import timezone

def from_settings(request):
    return {
        'ENVIRONMENT_NAME': settings.ENVIRONMENT_NAME,
        'ENVIRONMENT_COLOR': settings.ENVIRONMENT_COLOR,
    }


def top_categories(request):
    from common.models import Category
    try:
        top_cat = Category.objects.get(slug='top')
        cats = list(Category.objects.filter(parent_category=top_cat).order_by('title'))
    except Category.DoesNotExist:
        cats = []
    return {'top_categories': cats}


def transaction_notifications(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'unseen_txn_count': 0,
            'unseen_txn_items': [],
            'txn_login_notice': False,
            'txn_notice_count': 0,
            'txn_notice_items': [],
        }

    from transaction.models import Transaction

    user = request.user
    show_login_notice = bool(request.session.pop('show_txn_login_notice', False))
    today = timezone.localdate()

    def _requires_action_and_label(txn):
        is_lender = txn.user_passive_id == user.id
        is_renter = txn.user_aggressive_id == user.id
        status = txn.transaction_status

        if status == txn.RENTAL_ENQUIRY and is_lender:
            return True, 'Respond to enquiry'

        if status == txn.RENTAL_AGREED:
            lender_done = bool(txn.lender_agreed_at)
            renter_done = bool(txn.renter_agreed_at)

            if not lender_done and is_lender:
                return True, 'Confirm contract'
            if lender_done and not renter_done and is_renter:
                return True, 'Confirm contract'
            if lender_done and renter_done:
                if txn.deposit_card_setup_status != txn.CARD_READY and is_renter:
                    return True, 'Set up payment card'
                if (
                    is_lender
                    and txn.deposit_card_setup_status == txn.CARD_READY
                    and txn.rental_start_date
                    and today >= txn.rental_start_date
                ):
                    return True, 'Start rental'

        if (
            status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
            and is_renter
            and txn.rental_end_date
            and today >= txn.rental_end_date
        ):
            return True, 'Mark item returned'

        if status == txn.RENTAL_RETURNED_DEPOSIT_PENDING and is_lender:
            return True, 'Resolve deposit'

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

    # Only include transactions that are currently pending action for this user.
    lender_pending = Q(user_passive=user) & (
        Q(transaction_status=Transaction.RENTAL_ENQUIRY) |
        Q(transaction_status=Transaction.RENTAL_AGREED, lender_agreement_pending_at__isnull=False, lender_agreed_at__isnull=True) |
        Q(transaction_status=Transaction.RENTAL_AGREED, lender_agreed_at__isnull=False, renter_agreed_at__isnull=False) |
        Q(transaction_status=Transaction.RENTAL_RETURNED_DEPOSIT_PENDING)
    )

    renter_pending = Q(user_aggressive=user) & (
        Q(transaction_status=Transaction.RENTAL_AGREED, renter_agreed_at__isnull=True) |
        Q(
            transaction_status=Transaction.RENTAL_AGREED,
            renter_agreed_at__isnull=False,
            deposit__gt=0,
        ) & ~Q(deposit_card_setup_status=Transaction.CARD_READY) |
        Q(
            transaction_status=Transaction.RENTAL_AGREED,
            renter_agreed_at__isnull=False,
            price__gt=0,
        ) & ~Q(deposit_card_setup_status=Transaction.CARD_READY) |
        Q(transaction_status=Transaction.RENTAL_DAY_AWAITING_VERIFICATION) |
        Q(transaction_status=Transaction.RENTAL_ONGOING) |
        Q(transaction_status=Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION)
    )

    pending_qs = Transaction.objects.filter(lender_pending | renter_pending).filter(
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
        })

    return {
        'unseen_txn_count': unseen_count,
        'unseen_txn_items': unseen_items,
        'txn_login_notice': show_login_notice and bool(txn_notice_items),
        'txn_notice_count': len(txn_notice_items),
        'txn_notice_items': txn_notice_items,
    }
