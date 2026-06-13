from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

from .validators import MinAgeValidator
from common.helpers import RandomFileName

# make email address unique
User._meta.get_field('email').__dict__['_unique'] = True

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)
    mobile_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(validators=[MinAgeValidator])
    mobile_number = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    town = models.CharField('Town/City', max_length=255)
    county = models.CharField(max_length=255, blank=True, null=True)
    postcode = models.CharField(max_length=8)
    
    # Cached GPS coordinates for postcode (to avoid repeated geocoding)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Cached latitude from postcode lookup'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Cached longitude from postcode lookup'
    )

    image = models.ImageField(upload_to=RandomFileName('users/'),
                            blank=True)
    image_original = models.ImageField(upload_to=RandomFileName('users/raw/'), blank=True)
    image_generated = models.ImageField(upload_to=RandomFileName('users/generated/'), blank=True)
    avatar_provider = models.CharField(max_length=50, blank=True)
    user_rating = models.FloatField(default=0)
    user_successful_txns = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999999)], default=0)
    user_failed_txns = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999999)], default=0)
    user_bookings_pending_other_party = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        default=0,
    )
    user_bookings_pending_my_action = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999999)],
        default=0,
    )
    create_date = models.DateTimeField('date created', auto_now_add=True)

    def __str__(self):
        return 'Profile for user {}'.format(self.user.username)

    def saveWithImage(self, *args, **kwargs):
        """Save profile and queue async image processing."""
        # Save the profile first
        super(Profile, self).save(*args, **kwargs)
        # Queue async image processing
        from account.tasks import process_profile_image
        process_profile_image.delay(self.id)

class RegistrationVerification(models.Model):
    email = models.EmailField(db_index=True)
    username = models.CharField(max_length=150, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(validators=[MinAgeValidator])
    mobile_number = models.CharField(max_length=20)
    house_name_number = models.CharField(max_length=255, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    town = models.CharField(max_length=255)
    county = models.CharField(max_length=255, blank=True, null=True)
    postcode = models.CharField(max_length=8)
    image = models.ImageField(upload_to=RandomFileName('users/'), blank=True)
    avatar_preset = models.CharField(max_length=32, blank=True)
    avatar_style = models.CharField(max_length=40, blank=True, default='auto')
    avatar_hair_color = models.CharField(max_length=40, blank=True, default='')
    avatar_gender_vibe = models.CharField(max_length=20, blank=True, default='neutral')
    avatar_hair_length = models.CharField(max_length=10, blank=True, default='any')
    avatar_glasses = models.BooleanField(default=False)
    avatar_facial_hair = models.PositiveSmallIntegerField(default=25)
    avatar_facial_hair_color = models.CharField(max_length=40, blank=True, default='')
    avatar_skin_tone = models.CharField(max_length=2, blank=True, default='4')
    avatar_clothes_color = models.CharField(max_length=40, blank=True, default='')
    avatar_eyes = models.CharField(max_length=20, blank=True, default='default')
    avatar_mouth = models.CharField(max_length=20, blank=True, default='smile')
    avatar_clothing = models.CharField(max_length=30, blank=True, default='hoodie')
    avatar_accessories = models.CharField(max_length=20, blank=True, default='round')
    avatar_accessories_color = models.CharField(max_length=40, blank=True, default='')
    avatar_age_vibe = models.CharField(max_length=2, blank=True, default='3')
    generated_image = models.ImageField(upload_to=RandomFileName('users/generated/'), blank=True)
    avatar_generation_consent = models.BooleanField(default=False)

    verification_code = models.CharField(max_length=6, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['email', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Verification for {self.email}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class PaymentMethod(models.Model):
    """
    Stored payment methods for users (e.g., Stripe cards).
    Sensitive data is not stored here - only references to Stripe PaymentMethod IDs.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    
    # Stripe references (no sensitive card data stored)
    stripe_payment_method_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='Stripe PaymentMethod ID'
    )
    stripe_setup_intent_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Stripe SetupIntent ID used to create this payment method'
    )
    
    # Card display info (last 4 digits only, brand)
    card_brand = models.CharField(
        max_length=20,
        default='Card',
        help_text='Card brand (Visa, Mastercard, etc.)'
    )
    card_funding = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='Card funding type from Stripe (credit, debit, prepaid, etc.)'
    )
    card_last4 = models.CharField(
        max_length=4,
        help_text='Last 4 digits of card'
    )
    
    # Metadata
    is_default = models.BooleanField(
        default=False,
        help_text='Use this card by default for deposits'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        funding = f' {self.card_funding}' if self.card_funding else ''
        return f'{self.card_brand}{funding} ****{self.card_last4} for {self.user.username}'
