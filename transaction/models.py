from django.db import models
from datetime import timedelta
from common.models import Order, Product, TransactionFee
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
import random
import string
from common.helpers import RandomFileName 
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from django.conf import settings

# File size limits (in bytes)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB

def validate_image_size(file_obj):
    """Validate image file size (max 5 MB)."""
    if file_obj.size > MAX_IMAGE_SIZE:
        raise ValidationError(f'Image file too large. Max size is 5 MB, got {file_obj.size / (1024*1024):.1f} MB.')

def validate_video_size(file_obj):
    """Validate video file size (max 50 MB)."""
    if file_obj.size > MAX_VIDEO_SIZE:
        raise ValidationError(f'Video file too large. Max size is 50 MB, got {file_obj.size / (1024*1024):.1f} MB.')
from django.utils import timezone
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
    WORKFLOW_STAGE_LABELS = {
        1: 'Discussion',
        2: 'Lender confirms contract',
        3: 'Borrower confirms contract',
        4: 'Borrower card setup',
        5: 'Checkout evidence + confirmation/counter + borrower PIN to lender',
        6: 'Return evidence + confirmation/counter + deposit proposal cycle + lender PIN to borrower',
        7: 'Feedback (both parties): star ratings + commentary',
    }

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
    RENTAL_DAY_AWAITING_VERIFICATION = 'RDAYAWV'
    RENTAL_ONGOING = 'RONG'
    RENTAL_RETURN_DAY_AWAITING_VERIFICATION = 'RRTDAYAWV'
    RENTAL_RETURNED_DEPOSIT_PENDING = 'RRTDPEND'
    RENTAL_RETURNED_DEPOSIT_RETURNED = 'RRTDRET'
    RENTAL_RETURNED_DEPOSIT_CONTESTED = 'RRTDCON'
    AWAITING_FEEDBACK = 'AWFB'
    FEEDBACK_ONE_SIDED = 'FB1SIDE'
    RENTAL_PROCESS_COMPLETED = 'RCOMP'
    RENTAL_PROCESS_COMPLETED_ONE_SIDED = 'RCOMP1S'
    RENTAL_PROCESS_COMPLETED_NO_FEEDBACK = 'RCMPNFB'
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
        (RENTAL_ENQUIRY, 'Discussion'),
        (RENTAL_AGREED, 'Agreement'),
        (RENTAL_DAY_AWAITING_VERIFICATION, 'Checkout verification'),
        (RENTAL_ONGOING, 'Ongoing'),
        (RENTAL_RETURN_DAY_AWAITING_VERIFICATION, 'Return verification'),
        (RENTAL_RETURNED_DEPOSIT_PENDING, 'Deposit review'),
        (RENTAL_RETURNED_DEPOSIT_RETURNED, 'Deposit returned'),
        (RENTAL_RETURNED_DEPOSIT_CONTESTED, 'Deposit contested'),
        (AWAITING_FEEDBACK, 'Feedback'),
        (FEEDBACK_ONE_SIDED, 'Feedback'),
        (RENTAL_PROCESS_COMPLETED, 'Completed'),
        (RENTAL_PROCESS_COMPLETED_ONE_SIDED, 'Completed'),
        (RENTAL_PROCESS_COMPLETED_NO_FEEDBACK, 'Closed'),
        (CANCEL_REQUESTED, 'Cancellation requested'),
        (CANCEL_ACCEPTED, 'Cancelled'),
        (DISPUTE_REQUESTED, 'Mediation'),
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
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_CAPTURED_PLACEHOLDER, 'Captured'),
        (PAYMENT_NOT_REQUIRED, 'Not required'),
    )
    payment_status = models.CharField(
        'payment status',
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )

    DEPOSIT_STATUS_CHOICES = (
        (DEPOSIT_PENDING, 'Pending'),
        (DEPOSIT_HELD_PLACEHOLDER, 'Held'),
        (DEPOSIT_RETURNED_FULL, 'Returned in full'),
        (DEPOSIT_RETURNED_REDUCED, 'Returned with reduction'),
        (DEPOSIT_MEDIATION, 'Mediation'),
    )
    deposit_status = models.CharField(
        'deposit status',
        max_length=20,
        choices=DEPOSIT_STATUS_CHOICES,
        default=DEPOSIT_PENDING,
    )


    PRODUCT_STATUS_CHOICES = (
        (CONDITION_PENDING, 'Condition pending'),
        (CHECKOUT_VIDEO_ADDED, 'Checkout video added'),
        (RETURN_VIDEO_ADDED, 'Return video added'),
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

    # Rental-start (checkout) workflow evidence and handover verification
    checkout_borrower_video_url = models.URLField(blank=True, max_length=500)
    checkout_borrower_confirmed = models.BooleanField(default=False)
    checkout_handover_pin = models.CharField(max_length=8, blank=True)
    checkout_handover_pin_generated_at = models.DateTimeField(blank=True, null=True)
    checkout_handover_verified_at = models.DateTimeField(blank=True, null=True)

    # Return-day workflow evidence and handover verification
    return_borrower_video_url = models.URLField(blank=True, max_length=500)
    return_lender_video_url = models.URLField(blank=True, max_length=500)
    return_lender_confirmed = models.BooleanField(default=False)
    return_handover_pin = models.CharField(max_length=8, blank=True)
    return_handover_pin_generated_at = models.DateTimeField(blank=True, null=True)
    return_handover_verified_at = models.DateTimeField(blank=True, null=True)

    payment_collected_placeholder = models.BooleanField(default=False)
    deposit_collected_placeholder = models.BooleanField(default=False)
    payment_collection_requested_at = models.DateTimeField(blank=True, null=True)
    payment_collection_reference = models.CharField(max_length=120, blank=True)
    payment_placeholder_notes = models.TextField(blank=True, max_length=1000)
    deposit_placeholder_notes = models.TextField(blank=True, max_length=1000)
    deposit_resolution_notes = models.TextField(blank=True, max_length=1000)
    feedback_window_expires_at = models.DateTimeField(blank=True, null=True)
    contract_first_signer_reminder_at = models.DateTimeField(blank=True, null=True)
    contract_counterparty_reminder_at = models.DateTimeField(blank=True, null=True)
    return_verification_reminder_at = models.DateTimeField(blank=True, null=True)
    feedback_reminder_at = models.DateTimeField(blank=True, null=True)
    deposit_proposed_return_amount = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        help_text='Current lender proposal for deposit amount to return',
    )
    deposit_proposed_by_lender_at = models.DateTimeField(blank=True, null=True)
    deposit_proposal_contested_at = models.DateTimeField(blank=True, null=True)
    deposit_proposal_accepted_at = models.DateTimeField(blank=True, null=True)
    deposit_proposal_iteration_count = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text='Number of lender deposit proposal iterations used (max 5)',
    )

    # Placeholder Stripe Connect deposit setup/collection states
    CARD_NONE = 'NONE'
    CARD_READY = 'READY'
    CARD_FAILED = 'FAILED'
    CARD_SETUP_CHOICES = (
        (CARD_NONE, 'No deposit card on file'),
        (CARD_READY, 'Deposit card ready'),
        (CARD_FAILED, 'Card setup failed'),
    )
    deposit_card_setup_status = models.CharField(
        max_length=10,
        choices=CARD_SETUP_CHOICES,
        default=CARD_NONE,
        help_text='Placeholder status for borrower deposit card setup via Stripe Connect'
    )
    deposit_cardholder_name = models.CharField(max_length=120, blank=True)
    deposit_card_brand = models.CharField(max_length=20, blank=True)
    deposit_card_last4 = models.CharField(max_length=4, blank=True)

    TEST_HOLD_NOT_RUN = 'NOT_RUN'
    TEST_HOLD_SUCCESS = 'SUCCESS'
    TEST_HOLD_FAILED = 'FAILED'
    TEST_HOLD_STATUS_CHOICES = (
        (TEST_HOLD_NOT_RUN, 'Not run'),
        (TEST_HOLD_SUCCESS, 'Successful'),
        (TEST_HOLD_FAILED, 'Failed'),
    )
    deposit_test_hold_status = models.CharField(
        max_length=10,
        choices=TEST_HOLD_STATUS_CHOICES,
        default=TEST_HOLD_NOT_RUN,
    )
    deposit_test_hold_amount = models.FloatField(default=0)
    deposit_test_hold_reference = models.CharField(max_length=120, blank=True)
    deposit_test_hold_at = models.DateTimeField(blank=True, null=True)

    COLLECT_NOT_RUN = 'NOT_RUN'
    COLLECT_SUCCESS = 'SUCCESS'
    COLLECT_FAILED = 'FAILED'
    COLLECT_STATUS_CHOICES = (
        (COLLECT_NOT_RUN, 'Not run'),
        (COLLECT_SUCCESS, 'Successful'),
        (COLLECT_FAILED, 'Failed'),
    )
    deposit_collection_status = models.CharField(
        max_length=10,
        choices=COLLECT_STATUS_CHOICES,
        default=COLLECT_NOT_RUN,
    )
    deposit_collection_requested_at = models.DateTimeField(blank=True, null=True)
    deposit_collection_reference = models.CharField(max_length=120, blank=True)
    
    # Stripe Connect fields for secure card handling
    stripe_setup_intent_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Stripe SetupIntent ID for card tokenization'
    )
    stripe_payment_method_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Stripe PaymentMethod ID for stored card'
    )
    stripe_customer_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Stripe Customer ID for reusable payment methods'
    )
    
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
    delivery_cost = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        help_text='Computed delivery cost charged for this transaction'
    )
    rentalution_fee = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        help_text='Computed Rentalution fee charged for this transaction'
    )
    
    total_weight = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])

    # TODO: add
    current_spot_value = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price_as_pct_spot_value = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])

    # Contract confirmation tracking
    lender_agreement_pending_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When lender initiated agreement; awaiting their confirmation'
    )
    lender_agreed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When lender confirmed the contract'
    )
    renter_agreed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When borrower confirmed the contract'
    )
    
    # Deposit handling type
    DEPOSIT_HELD = 'HELD'
    DEPOSIT_HELD_AND_RETURNED = 'HELD_RTRN'
    DEPOSIT_TAKEN_AND_HELD = 'TAKEN_HELD'
    DEPOSIT_TAKEN_AND_RETURNED = 'TAKEN_RTRN'
    
    DEPOSIT_HANDLING_CHOICES = (
        (DEPOSIT_HELD, 'Held (no collection)'),
        (DEPOSIT_HELD_AND_RETURNED, 'Held (to be collected)'),
        (DEPOSIT_TAKEN_AND_HELD, 'Taken and held'),
        (DEPOSIT_TAKEN_AND_RETURNED, 'Taken and returned at end'),
    )
    
    deposit_handling = models.CharField(
        max_length=20,
        choices=DEPOSIT_HANDLING_CHOICES,
        default=DEPOSIT_HELD,
        help_text='How deposit is collected and managed'
    )
    
    # KYC verification tracking
    requires_kyc = models.BooleanField(
        default=False,
        help_text='Whether KYC verification is required for this high-risk rental'
    )
    requires_kyc_message = models.TextField(
        blank=True,
        max_length=500,
        help_text='Message about why KYC is required'
    )
    lender_kyc_verified = models.BooleanField(
        default=False,
        help_text='Whether lender has completed required KYC verification'
    )
    renter_kyc_verified = models.BooleanField(
        default=False,
        help_text='Whether borrower has completed required KYC verification'
    )

    created = models.DateField(auto_now_add=True)
    amended = models.DateField(auto_now=True)
    history = HistoricalRecords()
    
    def get_rental_length_days(self):
        """Calculate rental length in days"""
        if self.rental_start_date and self.rental_end_date:
            delta = self.rental_end_date - self.rental_start_date
            return delta.days + 1  # inclusive
        return 0

    @staticmethod
    def feedback_window_days():
        raw_days = getattr(settings, 'TRANSACTION_FEEDBACK_WINDOW_DAYS', 30)
        try:
            return max(1, int(raw_days))
        except (TypeError, ValueError):
            return 30

    def refresh_feedback_deadline(self, *, from_dt=None):
        base_dt = from_dt or timezone.now()
        self.feedback_window_expires_at = base_dt + timedelta(days=self.feedback_window_days())
        return self.feedback_window_expires_at
    
    def calculate_deposit_handling(self):
        """Determine deposit handling based on rental length and amount"""
        rental_days = self.get_rental_length_days()
        
        # If deposit > £100 and rental > 5 days, must take and return
        if self.deposit > 100 and rental_days > 5:
            return self.DEPOSIT_TAKEN_AND_RETURNED
        # If deposit > £100 and rental <= 5 days, take and hold
        elif self.deposit > 100 and rental_days <= 5:
            return self.DEPOSIT_TAKEN_AND_HELD
        # Otherwise, hold only
        else:
            return self.DEPOSIT_HELD
    
    def validate_rental_length(self):
        """Validate rental length constraints"""
        rental_days = self.get_rental_length_days()
        errors = []
        
        # Max 5 days rental for deposits over £100
        if self.deposit > 100 and rental_days > 5:
            errors.append(
                f'Maximum rental length for deposits over £100 is 5 days. '
                f'Your rental is {rental_days} days. '
                f'For longer rentals, deposit will be taken and returned at the end.'
            )
        
        return errors

    def get_status_display_verbose(self):
        """Return richer user-facing status text for key workflow milestones."""
        if self.transaction_status == self.RENTAL_AGREED:
            has_lender_confirmed = bool(self.lender_agreed_at)
            has_borrower_confirmed = bool(self.renter_agreed_at)
            payment_method_not_required = (self.deposit <= 0 and self.price <= 0)
            has_card_ready = (
                self.deposit_card_setup_status == self.CARD_READY
                or payment_method_not_required
            )

            if has_lender_confirmed and has_borrower_confirmed and has_card_ready:
                return 'All pre-rental actions completed - awaiting rental start date'

        return self.get_transaction_status_display()

    def get_workflow_stage_number(self):
        status = self.transaction_status
        missing_rental_voided = (
            status == self.CANCEL_ACCEPTED
            and '[MISSING_RENTAL_VOIDED]' in (self.deposit_resolution_notes or '')
        )
        if status == self.RENTAL_ENQUIRY:
            return 1
        if status == self.RENTAL_AGREED:
            if self.renter_agreed_at:
                return 4
            if self.lender_agreed_at:
                return 3
            return 2
        if status in (
            self.RENTAL_DAY_AWAITING_VERIFICATION,
            self.RENTAL_ONGOING,
        ):
            return 5
        if status in (
            self.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
            self.RENTAL_RETURNED_DEPOSIT_PENDING,
            self.RENTAL_RETURNED_DEPOSIT_RETURNED,
            self.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            self.DISPUTE_REQUESTED,
            self.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
        ):
            return 6
        if status in (
            self.AWAITING_FEEDBACK,
            self.FEEDBACK_ONE_SIDED,
            self.RENTAL_PROCESS_COMPLETED,
            self.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
        ) or missing_rental_voided:
            return 7
        return 1

    def get_workflow_stage_label(self):
        return self.WORKFLOW_STAGE_LABELS.get(self.get_workflow_stage_number(), 'Workflow step')

    def get_workflow_payload(self):
        current = self.get_workflow_stage_number()
        timeline = [
            {
                'step': step,
                'label': self.WORKFLOW_STAGE_LABELS.get(step, 'Workflow step'),
                'current': step == current,
                'done': step < current,
            }
            for step in range(1, 8)
        ]
        return {
            'current_stage': current,
            'current_label': self.get_workflow_stage_label(),
            'timeline': timeline,
        }

    def get_workflow_timeline(self):
        return self.get_workflow_payload()['timeline']

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
    is_system_generated = models.BooleanField(default=False)
    history = HistoricalRecords()


class TransactionMessageImage(models.Model):
    ROLE_LENDER = 'lender'
    ROLE_BORROWER = 'borrower'
    ROLE_SYSTEM = 'system'
    UPLOADER_ROLE_CHOICES = (
        (ROLE_LENDER, 'Lender'),
        (ROLE_BORROWER, 'Borrower'),
        (ROLE_SYSTEM, 'System'),
    )

    txn_message = models.ForeignKey(TransactionMessage, related_name='txn_msg_img', on_delete=models.CASCADE, blank=True, null=True)
    image = models.ImageField(
        upload_to=RandomFileName('images/txn_msg/'),
        blank=True,
        null=True,
        validators=[validate_image_size],
        help_text='Max 5 MB'
    )
    video = models.FileField(
        upload_to=RandomFileName('videos/txn_msg/'),
        blank=True,
        null=True,
        validators=[validate_video_size],
        help_text='Max 50 MB. Optimized/display version.'
    )
    video_raw = models.FileField(
        upload_to=RandomFileName('videos/txn_msg_raw/'),
        blank=True,
        null=True,
        help_text='Raw/uncompressed video archive for verification purposes. Chain of custody.'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    captured_at = models.DateTimeField(blank=True, null=True)
    capture_device = models.CharField(max_length=120, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    uploader_role = models.CharField(max_length=12, choices=UPLOADER_ROLE_CHOICES, blank=True)
    evidence_stage = models.CharField(max_length=40, blank=True)
    external_video_url = models.URLField(blank=True, max_length=500)
    active = models.BooleanField(default=True)
    first_image = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def saveNoImageModification(self, *args, **kwargs):
        super(TransactionMessageImage, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Check if we should skip image processing (used by async task)
        skip_processing = getattr(self, '_skip_image_processing', False)
        
        if self.video and not self.image:
            super(TransactionMessageImage, self).save(*args, **kwargs)
            return

        if not self.image:
            super(TransactionMessageImage, self).save(*args, **kwargs)
            return
        
        # If image is new and we haven't already processed it, save it first then queue async processing
        if not skip_processing and self.pk is None:  # New object
            super(TransactionMessageImage, self).save(*args, **kwargs)
            # Queue async image processing task
            from .tasks import process_transaction_message_image
            process_transaction_message_image.delay(self.id)
            return
        
        if skip_processing:
            # Just save without processing (called from async task)
            super(TransactionMessageImage, self).save(*args, **kwargs)
            return

        # Existing object being updated - do processing synchronously for backward compatibility
        im = Image.open(self.image)
        output = BytesIO()
        fill_color = 'white'  # your background
        if im.mode in ('RGBA', 'LA'):
            background = Image.new(im.mode[:-1], im.size, fill_color)
            background.paste(im, im.split()[-1])
            im = background

# Resize/modify the image for web optimization (max 1920px width, 80% quality)
        max_width = 1920
        if im.size[0] > max_width:
            ratio = im.size[0] / max_width
            new_height = int(im.size[1] / ratio)
            im = im.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Also limit height to prevent extremely tall images
        max_height = 1920
        if im.size[1] > max_height:
            ratio = im.size[1] / max_height
            new_width = int(im.size[0] / ratio)
            im = im.resize((new_width, max_height), Image.Resampling.LANCZOS)
	
        # After modifications, save to output with 80% quality for web optimization
        im.save(output, format='JPEG', quality=80, optimize=True)
        output.seek(0)

        # Change the imagefield value to the optimized image
        self.image = InMemoryUploadedFile(
            output,
            'ImageField',
            "%s.jpg" % self.image.name.split('.')[0],
            'image/jpeg',
            sys.getsizeof(output),
            None
        )
        super(TransactionMessageImage, self).save(*args, **kwargs)


class TransactionFeedback(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='feedbacks')
    left_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='feedbacks_left')
    left_for = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='feedbacks_received')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    communication_rating = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    delivery_return_rating = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    overall_rating = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=1000, blank=True)
    is_negative = models.BooleanField(
        default=False,
        help_text='True if feedback is negative (for non-site payments)',
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['transaction', 'left_by', 'left_for'],
                name='uniq_feedback_per_direction_per_transaction',
            ),
        ]

    def __str__(self):
        return f"Feedback {self.rating} for {self.left_for} by {self.left_by} (txn {self.transaction_id})"
