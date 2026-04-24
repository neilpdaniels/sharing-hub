from django.db import models
from common.models import Order, Product, TransactionFee
from django.core.validators import MaxValueValidator, MinValueValidator
from simple_history.models import HistoricalRecords
import random
import string
from common.helpers import RandomFileName 
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from django.conf import settings
#from djongo import models


    # def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    #     return ''.join(random.choice(chars) for _ in range(size))

def unique_txn_ref_generator():
    new_txn_ref= ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    qs_exists= Transaction.objects.filter(transaction_reference = new_txn_ref).exists()
    if qs_exists:
        return unique_txn_ref_generator()
    return new_txn_ref

class Transaction(models.Model):
    # objects = models.DjongoManager()

    user_passive = models.ForeignKey('auth.User', 
                                    related_name='rel_from_set',
                                    on_delete=models.CASCADE)
    user_aggressive = models.ForeignKey('auth.User', 
                                    related_name='rel_to_set',
                                    on_delete=models.CASCADE)
    order_passive = models.ForeignKey(Order, on_delete=models.CASCADE,
                                    related_name='rel_order_passive',
                                     blank=True, null=True)
    order_passive_description = models.TextField(blank=True, max_length=250)    
    NEW = 'NEW'
    NEW_TIMEOUT = 'NEWTOUT'
    PAYMENT_PROCESSING = 'PAYPROC'
    DELIVERY_PROCESSING = 'DELPROC'
    CANCEL_REQUESTED = 'CREQ'
    CANCEL_CANCELLED = 'CCAN'
    CANCEL_ACCEPTED = 'CACK'
    CANCEL_REFUSED = 'CREF'
    DISPUTE_REQUESTED = 'DREQ'
    DISPUTE_RESOLVED = 'DRES'
    DISPUTE_TIMEOUT = 'DTOUT'
    COMPLETED_ACK = 'COMP'
    PENDING = 'PEND'
    PENDING_TIMEOUT = 'PENDTOUT'
    RETURN_PENDING = 'RTNPND'
    RETURNED_ACK = 'RTNACK'
    PENDING_BOTH = 'PBOTH'
    PENDING_BUYER = 'PBUY'
    PENDING_SELLER = 'PSELL'
    VOIDED =  'VOID'

    PAYMENT_NOT_SENT = 'PYNOTSNT'
    PAYMENT_SENT = 'PYSNT'
    PAYMENT_ACKED = 'PYACK'
    REFUND_REQUESTED = 'REFREQ'
    REFUND_REJECTED = 'REFREJ'
    REFUND_SENT = 'REFSNT'
    REFUND_ACKED = 'REFACK'
    PAYMENT_TIMEOUT = 'PAYTOUT'
    REFUND_TIMEOUT = 'REFTOUT'
    REFUND_COMPLETE = 'REFACK'
    FUNDS_RELEASED = 'FUNDRE'
    FUNDS_IN_ESCROW = 'ESCROW'

    PRODUCT_NOT_SENT = 'PNOTSNT'
    PRODUCT_SENT = 'PSENT'
    PRODUCT_RECEIVED = 'PREC'
    PRODUCT_NOT_AS_SHOWN = 'PNACK'
    PRODUCT_VERIFIED_OK = 'PACK'
    PRODUCT_NOT_RECEIVED = 'PNOTREC'
    PRODUCT_NOT_SENT_TIMEOUT = 'PNOTSNTTOUT'
    PRODUCT_NOT_RECEIVED_TIMEOUT = 'PNOTRECTOUT'
    PRODUCT_RETURNED = 'PRET'
    PRODUCT_RETURNED_ACKED = 'PRETACK'
    PRODUCT_RETURNED_TIMEOUT = 'PRETTOUT'


    TRANSACTION_STATUS_CHOICES = (
        (NEW, 'New'),
        (NEW_TIMEOUT, 'New Timeout'),
        (PAYMENT_PROCESSING, 'Awaiting Payment to ESCROW'),
        (DELIVERY_PROCESSING, 'Delivery process pending'),
        (CANCEL_REQUESTED,'Cancel Requested'),
        (CANCEL_CANCELLED,'Cancellation reversed'),
        (CANCEL_ACCEPTED,'Cancel Accepted'),
        (CANCEL_REFUSED,'Cancel Refused'),
        (DISPUTE_REQUESTED, 'Dispute Request Raised'),
        (DISPUTE_RESOLVED, 'Dispute Resolved'),
        (DISPUTE_TIMEOUT, 'Dispute Timeout'),
        (COMPLETED_ACK, 'Completed'),
        (PENDING, 'Pending'),
        (PENDING_TIMEOUT, 'Pending Timeout'),
        (RETURN_PENDING, 'Return Pending'),
        (RETURNED_ACK, 'Return Ack'),
        (PENDING_BOTH, 'Pending term acceptance - both parties'),
        (PENDING_BUYER, 'Pending term acceptance - buyer'),
        (PENDING_SELLER, 'Pending term acceptance - seller'),
        (VOIDED, 'Transaction Voided - terms rejected'),
        (FUNDS_IN_ESCROW, 'Funds received and protected in escrow'),
        (PRODUCT_NOT_AS_SHOWN, 'Product Not as Advertised'),
        (PRODUCT_VERIFIED_OK, 'Product Verified OK'),
    )
    transaction_status = models.CharField(
        'transaction status',
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default=NEW,
    )
    prev_transaction_status = models.CharField(
        'previous transaction status',
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default=NEW,
    )
    transaction_status_raised_by = models.ForeignKey('auth.User', 
                                    related_name='status_raised_by',
                                    on_delete=models.CASCADE,
                                    blank=True, null=True)


    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_NOT_SENT, 'Payment Not Sent'),
        (PAYMENT_SENT, 'Payment Sent'),
        (PAYMENT_ACKED, 'Payment Received'),
        (REFUND_REQUESTED, 'Refund Requested'),
        (REFUND_REJECTED, 'Refund Rejected'),
        (REFUND_SENT, 'Refund Sent'),
        (REFUND_ACKED, 'Refund Received'),
        (PAYMENT_TIMEOUT, 'Payment Timeout'),
        (REFUND_TIMEOUT, 'Refund Timeout'),
        (REFUND_COMPLETE, 'Refund Completed'),
        (FUNDS_IN_ESCROW, 'Funds received and protected in escrow'),
        (FUNDS_RELEASED, 'Funds released to seller'),
    )
    payment_status = models.CharField(
        'payment status',
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_NOT_SENT,
    )


    PRODUCT_STATUS_CHOICES = (
        (PRODUCT_NOT_SENT, 'Product Not Sent'),
        (PRODUCT_SENT, 'Product Sent'),
        (PRODUCT_RECEIVED, 'Product Received'),
        (PRODUCT_NOT_AS_SHOWN, 'Product Not as Advertised'),
        (PRODUCT_VERIFIED_OK, 'Product Verified OK'),
        (PRODUCT_NOT_RECEIVED, 'Product Not Received'),
        (PRODUCT_NOT_SENT_TIMEOUT, 'Product Not Sent Timeout'),
        (PRODUCT_NOT_RECEIVED_TIMEOUT, 'Product Not Received Timeout'),
        (PRODUCT_RETURNED, 'Product Returned'),
        (PRODUCT_RETURNED_ACKED, 'Product Returned Received'),
        (PRODUCT_RETURNED_TIMEOUT, 'Product Received Timeout')
    )
    product_status = models.CharField(
        'product status',
        max_length=20,
        choices=PRODUCT_STATUS_CHOICES,
        default=PRODUCT_NOT_SENT,
    )

    # public view of transaction ref to avoid sequential numbers
    transaction_reference = models.CharField(max_length=25, default=unique_txn_ref_generator, db_index=True)
    
    transpact_text_status = models.CharField(max_length=500, blank=True, null=True)
    transpact_update_datetime = models.DateTimeField(blank=True, null=True)
    transpact_scraped_datetime = models.DateTimeField(blank=True, null=True)
    # naming is wrong, but this is in case the orders are matched systematically rather than manually
    order_aggressive = models.ForeignKey(Order, on_delete=models.CASCADE,
                                        related_name='rel_order_aggressive',
                                        blank=True, null=True)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(9999)], default=1)
    
    # price for non-friends
    price = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])
    
    # price for friends (optional - if not set, same as regular price)
    friend_price = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        null=True,
        blank=True,
        help_text='Special price for friends. If not set, regular price applies to all.'
    )
    
    # deposit for non-friends
    deposit = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        help_text='Deposit required from non-friends'
    )
    
    # deposit for friends (optional - if not set, same as regular deposit)
    friend_deposit = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        null=True,
        blank=True,
        help_text='Special deposit for friends. If not set, regular deposit applies to all.'
    )
    
    # How far the lender is willing to deliver/travel (in km)
    delivery_distance_km = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text='Maximum distance in km the lender can deliver/travel'
    )
    
    total_weight = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])

    # TODO: add
    current_spot_value = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price_as_pct_spot_value = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])

    created = models.DateField(auto_now_add=True)
    amended = models.DateField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.transaction_reference

class TransactionImage(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, blank=True, null=True)
    image = models.ImageField(upload_to=RandomFileName('images/transactions/'))

class TransactionCharge(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, blank=True, null=True)
    transaction_fee = models.ForeignKey(TransactionFee, on_delete=models.CASCADE, blank=True, null=True)
    user_to_pay = models.ForeignKey('auth.User', 
                                    related_name='user_to_pay',
                                    on_delete=models.CASCADE)
    price = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])

class TransactionMessage(models.Model):
    user_from = models.ForeignKey('auth.User', 
                                    related_name='message_user_from',
                                    on_delete=models.CASCADE) 
    user_to = models.ForeignKey('auth.User', 
                                    related_name='message_user_to',
                                    on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, blank=True, null=True)
    subject = models.CharField(blank=True, max_length=150) 
    description = models.TextField(blank=True, max_length=2500) 
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    email_to_sender = models.BooleanField(default=False)
    read_by_user_to = models.BooleanField(default=False)
    email_to_recepient = models.BooleanField(default=False)
    include_admin = models.BooleanField(default=False)
    history = HistoricalRecords()


class TransactionMessageImage(models.Model):
    txn_message = models.ForeignKey(TransactionMessage, related_name='txn_msg_img', on_delete=models.CASCADE, blank=True, null=True)
    image = models.ImageField(upload_to=RandomFileName('images/txn_msg/'))
    uploaded_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    first_image = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def saveNoImageModification(self, *args, **kwargs):
        super(TransactionMessageImage, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        #Opening the uploaded image
        im = Image.open(self.image)
        output = BytesIO()
        fill_color = 'white'  # your background
        if im.mode in ('RGBA', 'LA'):
            background = Image.new(im.mode[:-1], im.size, fill_color)
            background.paste(im, im.split()[-1])
            im = background

        #Resize/modify the image
        max_h = 1600
        if im.size[0] > max_h:
            ratio = im.size[0] / max_h
            v_height = im.size[1] / ratio
            im = im.resize( (max_h, int(v_height)) )
        max_v = 1600
        if im.size[1] > max_v:
            ratio = im.size[1] / max_v
            h_height = im.size[0] / ratio
            im = im.resize( (int(h_height), max_v) )
		
        #after modifications, save it to the output
        im.save(output, format='JPEG', quality=100)
        output.seek(0)

        #change the imagefield value to be the newley modifed image value
        self.image = InMemoryUploadedFile(output,'ImageField', "%s.jpg" %self.image.name.split('.')[0], 'image/jpeg', sys.getsizeof(output), None)
        super(TransactionMessageImage, self).save(*args, **kwargs)
