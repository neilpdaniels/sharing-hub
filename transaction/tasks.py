from celery import shared_task
import logging
from django.utils import timezone

from common.models import Order
from .models import Transaction
from .stripe_connect import stripe_connect_service


logger = logging.getLogger(__name__)


@shared_task
def expireOrders():
    logging.info('Running order expiry')
    orders = Order.objects.filter(expiry_date__lte=timezone.now(), status=Order.ACTIVE)
    for order in orders:
        order.status = Order.EXPIRED
        order.save()


@shared_task
def async_confirm_card_setup(transaction_id, setup_intent_id, payment_method_id):
    """
    Async task to confirm Stripe card setup and run test hold.
    Updates transaction with card details and test hold results.
    """
    transaction = None
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        logger.info(f'Starting async card setup confirmation for transaction {transaction.transaction_reference}')

        # Persist submitted Stripe identifiers early for visibility/debugging.
        transaction.stripe_setup_intent_id = setup_intent_id or ''
        transaction.stripe_payment_method_id = payment_method_id or ''
        transaction.save(update_fields=['stripe_setup_intent_id', 'stripe_payment_method_id', 'amended'])
        
        result = stripe_connect_service.confirm_card_setup(
            transaction=transaction,
            setup_intent_id=setup_intent_id,
            payment_method_id=payment_method_id,
        )
        
        if result.get('ok'):
            # Update transaction with successful card setup
            transaction.deposit_card_setup_status = result.get('card_setup_status', transaction.CARD_READY)
            transaction.deposit_cardholder_name = result.get('cardholder_name', '')
            transaction.deposit_card_brand = result.get('card_brand', '')[:20]
            transaction.deposit_card_last4 = result.get('card_last4', '')
            transaction.stripe_setup_intent_id = setup_intent_id
            transaction.stripe_payment_method_id = payment_method_id
            transaction.stripe_customer_id = result.get('stripe_customer_id', '')
            
            transaction.deposit_test_hold_status = result.get('test_hold_status', transaction.TEST_HOLD_SUCCESS)
            transaction.deposit_test_hold_amount = result.get('test_hold_amount', 0.30)
            transaction.deposit_test_hold_at = result.get('test_hold_at', timezone.now())
            transaction.deposit_test_hold_reference = result.get('test_hold_reference', '')
            
            transaction.save()
            logger.info(f'Card setup confirmed for transaction {transaction.transaction_reference}')
        else:
            # Update transaction with failure status
            transaction.deposit_card_setup_status = transaction.CARD_FAILED
            transaction.deposit_test_hold_status = transaction.TEST_HOLD_FAILED
            transaction.save()
            logger.error(f'Card setup failed for transaction {transaction.transaction_reference}: {result.get("error")}')
            
    except Transaction.DoesNotExist:
        logger.error(f'Transaction {transaction_id} not found for card setup')
    except Exception as e:
        logger.exception(f'Async card setup failed: {str(e)}')
        if transaction is not None:
            transaction.deposit_card_setup_status = transaction.CARD_FAILED
            transaction.deposit_test_hold_status = transaction.TEST_HOLD_FAILED
            transaction.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'amended'])


@shared_task
def async_setup_deposit_card_and_test_hold(transaction_id, cardholder_name, card_brand, card_last4):
    """
    Async task to setup deposit card and run test hold with manual card details.
    """
    transaction = None
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        logger.info(f'Starting async deposit card setup for transaction {transaction.transaction_reference}')
        
        result = stripe_connect_service.setup_deposit_card_and_test_hold(
            transaction=transaction,
            cardholder_name=cardholder_name,
            card_brand=card_brand,
            card_last4=card_last4,
        )
        
        if result.get('ok'):
            # Update transaction with card setup details
            transaction.deposit_card_setup_status = result.get('card_setup_status', transaction.CARD_READY)
            transaction.deposit_cardholder_name = result.get('cardholder_name', cardholder_name)
            transaction.deposit_card_brand = result.get('card_brand', card_brand.upper()[:20])
            transaction.deposit_card_last4 = result.get('card_last4', card_last4)
            
            transaction.deposit_test_hold_status = result.get('test_hold_status', transaction.TEST_HOLD_SUCCESS)
            transaction.deposit_test_hold_amount = result.get('test_hold_amount', 0.30)
            transaction.deposit_test_hold_at = result.get('test_hold_at', timezone.now())
            transaction.deposit_test_hold_reference = result.get('test_hold_reference', '')
            
            transaction.save()
            logger.info(f'Deposit card setup complete for transaction {transaction.transaction_reference}')
        else:
            transaction.deposit_card_setup_status = transaction.CARD_FAILED
            transaction.deposit_test_hold_status = transaction.TEST_HOLD_FAILED
            transaction.save()
            logger.error(f'Deposit card setup failed for transaction {transaction.transaction_reference}: {result.get("error")}')
            
    except Transaction.DoesNotExist:
        logger.error(f'Transaction {transaction_id} not found for deposit card setup')
    except Exception as e:
        logger.exception(f'Async deposit card setup failed: {str(e)}')
        if transaction is not None:
            transaction.deposit_card_setup_status = transaction.CARD_FAILED
            transaction.deposit_test_hold_status = transaction.TEST_HOLD_FAILED
            transaction.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'amended'])


@shared_task
def async_collect_deposit_hold(transaction_id):
    """
    Async task to collect full deposit hold authorization.
    """
    transaction = None
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        logger.info(f'Starting async deposit collection for transaction {transaction.transaction_reference}')
        
        result = stripe_connect_service.collect_deposit_hold(transaction=transaction)
        
        if result.get('ok'):
            transaction.deposit_collection_status = result.get('collection_status', transaction.COLLECT_SUCCESS)
            transaction.deposit_collection_requested_at = result.get('collection_requested_at', timezone.now())
            transaction.deposit_collection_reference = result.get('collection_reference', '')
            
            transaction.save()
            logger.info(f'Deposit collection complete for transaction {transaction.transaction_reference}')
        else:
            transaction.deposit_collection_status = transaction.COLLECT_FAILED
            transaction.save()
            logger.error(f'Deposit collection failed for transaction {transaction.transaction_reference}: {result.get("error")}')
            
    except Transaction.DoesNotExist:
        logger.error(f'Transaction {transaction_id} not found for deposit collection')
    except Exception as e:
        logger.exception(f'Async deposit collection failed: {str(e)}')
        if transaction is not None:
            transaction.deposit_collection_status = transaction.COLLECT_FAILED
            transaction.save(update_fields=['deposit_collection_status', 'amended'])


@shared_task
def getUserTransactions(user_id):
    """Placeholder for future payment/deposit provider sync."""
    logger.info('Payment provider sync placeholder called for user_id=%s', user_id)
    return {'status': 'placeholder', 'user_id': user_id}


@shared_task
def createNewTransaction(txn_id):
    """Placeholder for future payment/deposit provider transaction setup."""
    logger.info('Payment provider create placeholder called for txn_id=%s', txn_id)
    return {'status': 'placeholder', 'transaction_id': txn_id}


@shared_task
def process_transaction_message_image(image_id):
    """
    Async task to process and resize transaction message images.
    Handles RGBA conversion, resizing, and JPEG compression.
    """
    from .models import TransactionMessageImage
    from PIL import Image
    from io import BytesIO
    from django.core.files.uploadedfile import InMemoryUploadedFile
    import sys
    
    try:
        image_obj = TransactionMessageImage.objects.get(id=image_id)
        
        if not image_obj.image:
            logger.warning(f'TransactionMessageImage {image_id} has no image to process')
            return
        
        # Open the image
        im = Image.open(image_obj.image)
        output = BytesIO()
        fill_color = 'white'
        
        # Convert RGBA to RGB
        if im.mode in ('RGBA', 'LA'):
            background = Image.new(im.mode[:-1], im.size, fill_color)
            background.paste(im, im.split()[-1])
            im = background
        
        # Resize if too large
        max_h = 1600
        if im.size[0] > max_h:
            ratio = im.size[0] / max_h
            v_height = im.size[1] / ratio
            im = im.resize((max_h, int(v_height)))
        
        max_v = 1600
        if im.size[1] > max_v:
            ratio = im.size[1] / max_v
            h_height = im.size[0] / ratio
            im = im.resize((int(h_height), max_v))
        
        # Save as JPEG
        im.save(output, format='JPEG', quality=100)
        output.seek(0)
        
        # Update the image field
        filename = f"{image_obj.image.name.split('.')[0]}.jpg"
        image_obj.image = InMemoryUploadedFile(
            output, 'ImageField', filename, 'image/jpeg', sys.getsizeof(output), None
        )
        
        # Save without triggering image processing again
        image_obj._skip_image_processing = True
        image_obj.save()
        
        logger.info(f'Successfully processed TransactionMessageImage {image_id}')
    except TransactionMessageImage.DoesNotExist:
        logger.error(f'TransactionMessageImage {image_id} not found')
    except Exception as e:
        logger.exception(f'Error processing TransactionMessageImage {image_id}: {str(e)}')
