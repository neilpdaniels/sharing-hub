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
    RENTAL_ENQUIRY = 'RENQ'
    RENTAL_AGREED = 'RAGR'
    RENTAL_INITIATED = 'RINT'
    RENTAL_RETURNED = 'RRTN'
    DEPOSIT_RETURNED = 'DRET'
    DEPOSIT_REDUCED = 'DRED'
    MEDIATION_REQUIRED = 'DMED'

    NEW = 'NEW'
    CANCEL_REQUESTED = 'CREQ'
    CANCEL_ACCEPTED = 'CACK'
    DISPUTE_REQUESTED = 'DREQ'

    PAYMENT_PENDING = 'PAYPEND'
    PAYMENT_CAPTURED_PLACEHOLDER = 'PAYCAP'
    PAYMENT_NOT_REQUIRED = 'PAYNA'

    DEPOSIT_PENDING = 'DEPPEND'
    DEPOSIT_HELD_PLACEHOLDER = 'DEPHOLD'
    DEPOSIT_RETURNED_FULL = 'DEPRETF'
    DEPOSIT_RETURNED_REDUCED = 'DEPRETR'
    DEPOSIT_MEDIATION = 'DEPMED'

    CONDITION_PENDING = 'CONDPEND'
    CHECKOUT_VIDEO_ADDED = 'CHKVID'
    RETURN_VIDEO_ADDED = 'RTNVID'


    TRANSACTION_STATUS_CHOICES = (
        (RENTAL_ENQUIRY, 'Enquiry for rental'),
        (RENTAL_AGREED, 'Rental agreed'),
        (RENTAL_INITIATED, 'Rental initiated'),
        (RENTAL_RETURNED, 'Rental returned'),
        (DEPOSIT_RETURNED, 'Deposit returned'),
        (DEPOSIT_REDUCED, 'Reduced deposit return agreed'),
        (MEDIATION_REQUIRED, 'Mediation required'),
        (CANCEL_REQUESTED, 'Cancellation requested'),
        (CANCEL_ACCEPTED, 'Cancelled'),
        (DISPUTE_REQUESTED, 'Dispute requested'),
    )
    transaction_status = models.CharField(
        'transaction status',
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default=RENTAL_ENQUIRY,
    )
    prev_transaction_status = models.CharField(
        'previous transaction status',
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default=RENTAL_ENQUIRY,
    )
    transaction_status_raised_by = models.ForeignKey('auth.User', 
                                    related_name='status_raised_by',
                                    on_delete=models.CASCADE,
                                    blank=True, null=True)


    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_PENDING, 'Pending capture'),
        (PAYMENT_CAPTURED_PLACEHOLDER, 'Captured (placeholder)'),
        (PAYMENT_NOT_REQUIRED, 'Not required'),
    )
    payment_status = models.CharField(
        'payment status',
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )

    DEPOSIT_STATUS_CHOICES = (
        (DEPOSIT_PENDING, 'Pending hold'),
        (DEPOSIT_HELD_PLACEHOLDER, 'Held (placeholder)'),
        (DEPOSIT_RETURNED_FULL, 'Returned in full'),
        (DEPOSIT_RETURNED_REDUCED, 'Returned with reduction'),
        (DEPOSIT_MEDIATION, 'Mediation required'),
    )
    deposit_status = models.CharField(
        'deposit status',
        max_length=20,
        choices=DEPOSIT_STATUS_CHOICES,
        default=DEPOSIT_PENDING,
    )


    PRODUCT_STATUS_CHOICES = (
        (CONDITION_PENDING, 'Condition evidence pending'),
        (CHECKOUT_VIDEO_ADDED, 'Checkout condition video added'),
        (RETURN_VIDEO_ADDED, 'Return condition video added'),
    )
    product_status = models.CharField(
        'product status',
        max_length=20,
        choices=PRODUCT_STATUS_CHOICES,
        default=CONDITION_PENDING,
    )

    # public view of transaction ref to avoid sequential numbers
    transaction_reference = models.CharField(max_length=25, default=unique_txn_ref_generator, db_index=True)
    
    transpact_text_status = models.CharField(max_length=500, blank=True, null=True)
    transpact_update_datetime = models.DateTimeField(blank=True, null=True)
    transpact_scraped_datetime = models.DateTimeField(blank=True, null=True)

    rental_start_date = models.DateField(blank=True, null=True)
    rental_end_date = models.DateField(blank=True, null=True)
    enquiry_message = models.TextField(blank=True, max_length=1000)

    checkout_condition_video_url = models.URLField(blank=True, max_length=500)
    return_condition_video_url = models.URLField(blank=True, max_length=500)

    payment_collected_placeholder = models.BooleanField(default=False)
    deposit_collected_placeholder = models.BooleanField(default=False)
    payment_placeholder_notes = models.TextField(blank=True, max_length=1000)
    deposit_placeholder_notes = models.TextField(blank=True, max_length=1000)
    deposit_resolution_notes = models.TextField(blank=True, max_length=1000)
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
