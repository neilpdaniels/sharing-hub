from celery import shared_task
import logging
from django.utils import timezone

from common.models import Order


@shared_task
def expireOrders():
    logging.info('Running order expiry')
    orders = Order.objects.filter(expiry_date__lte=timezone.now(), status=Order.ACTIVE)
    for order in orders:
        order.status = Order.EXPIRED
        order.save()


@shared_task
def getUserTransactions(user_id):
    # Placeholder for future payment/deposit provider sync.
    logging.info('Payment provider sync placeholder called for user_id=%s', user_id)
    return {'status': 'placeholder', 'user_id': user_id}


@shared_task
def createNewTransaction(txn_id):
    # Placeholder for future payment/deposit provider transaction setup.
    logging.info('Payment provider create placeholder called for txn_id=%s', txn_id)
    return {'status': 'placeholder', 'transaction_id': txn_id}
