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

    from transaction.models import Transaction, TransactionMessage

    user = request.user

    # Pending enquiries that require lender attention.
    pending_enquiry_ids = set(
        Transaction.objects.filter(
            user_passive=user,
            transaction_status=Transaction.RENTAL_ENQUIRY,
        ).values_list('id', flat=True)
    )

    # Any transaction with unread messages for this user.
    unread_message_txn_ids = set(
        TransactionMessage.objects.filter(
            user_to=user,
            read_by_user_to=False,
            transaction__isnull=False,
        ).values_list('transaction_id', flat=True)
    )

    unseen_ids = pending_enquiry_ids | unread_message_txn_ids
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
