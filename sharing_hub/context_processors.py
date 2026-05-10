from django.conf import settings
from django.db.models import Q

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
        }

    from transaction.models import Transaction

    user = request.user

    # Only include transactions that are currently pending action for this user.
    lender_pending = Q(user_passive=user) & (
        Q(transaction_status=Transaction.RENTAL_ENQUIRY) |
        Q(transaction_status=Transaction.RENTAL_AGREED, lender_agreement_pending_at__isnull=False, lender_agreed_at__isnull=True) |
        Q(transaction_status=Transaction.RENTAL_AGREED, lender_agreed_at__isnull=False, renter_agreed_at__isnull=False) |
        Q(transaction_status=Transaction.RENTAL_RETURNED)
    )

    renter_pending = Q(user_aggressive=user) & (
        Q(transaction_status=Transaction.RENTAL_AGREED, renter_agreed_at__isnull=True) |
        Q(
            transaction_status=Transaction.RENTAL_AGREED,
            lender_agreed_at__isnull=False,
            renter_agreed_at__isnull=False,
            deposit__gt=0,
        ) & ~Q(deposit_card_setup_status=Transaction.CARD_READY) |
        Q(transaction_status=Transaction.RENTAL_INITIATED)
    )

    pending_qs = Transaction.objects.filter(lender_pending | renter_pending).filter(
        Q(user_passive=user) | Q(user_aggressive=user)
    )

    unseen_ids = set(pending_qs.values_list('id', flat=True))
    unseen_items = []
    unseen_count = len(unseen_ids)

    if unseen_ids:
        unseen_items = list(
            Transaction.objects.filter(id__in=unseen_ids)
            .filter(Q(user_passive=user) | Q(user_aggressive=user))
            .select_related('product')
            .order_by('-amended', '-created')[:5]
        )

    return {
        'unseen_txn_count': unseen_count,
        'unseen_txn_items': unseen_items,
    }
