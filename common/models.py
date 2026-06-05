from django.db import models
from datetime import datetime
from django.utils import timezone
from django.template.defaultfilters import slugify
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from common.helpers import RandomFileName 
from .validators import MaxOrderPriceValidator
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from simple_history.models import HistoricalRecords
from django.urls import reverse
import random
import string
from common.tasks import updateSummaryPrices

def unique_order_ref_generator():
    new_order_ref= ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(14))
    qs_exists= Order.objects.filter(order_reference = new_order_ref).exists()
    if qs_exists:
        return unique_order_ref_generator()
    return new_order_ref


class CategoryTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(CategoryTag, self).save(*args, **kwargs)

class Category(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, blank=True )
    image = models.ImageField(upload_to=RandomFileName('images/categories/'), blank=True, null=True)
    create_date = models.DateTimeField('date created', auto_now_add=True)
    # parent_category_id = models.PositiveIntegerField() # perhaps need to be foreign key - what about root category though?
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)
    tags = models.ManyToManyField(CategoryTag, blank=True, related_name='categories')
    description = models.TextField(null=True, blank=True)
    virtual_depth = models.BooleanField(default=False)

    # secondary table may have been nicer if not using mongodb
    # TODO: currently mandated in browse that sortable / filterable attributes must use first names
    # not possible to have 1 and 2 filterable, 3 sortable without changes to browse
    attribute_one_name = models.CharField(max_length=200, null=True, blank=True)
    attribute_one_sortable = models.BooleanField(default=False)
    attribute_one_filterable = models.BooleanField(default=False)
    attribute_one_default_filtered_value = models.CharField(max_length=200, null=True, blank=True)
    
    attribute_two_name = models.CharField(max_length=200, null=True, blank=True)
    attribute_two_sortable = models.BooleanField(default=False)
    attribute_two_filterable = models.BooleanField(default=False)
    attribute_two_default_filtered_value = models.CharField(max_length=200, null=True, blank=True)

    attribute_three_name = models.CharField(max_length=200, null=True, blank=True)
    attribute_three_sortable = models.BooleanField(default=False)
    attribute_three_filterable = models.BooleanField(default=False)
    attribute_three_default_filtered_value = models.CharField(max_length=200, null=True, blank=True)

    attribute_four_name = models.CharField(max_length=200, null=True, blank=True)
    attribute_four_sortable = models.BooleanField(default=False)
    attribute_four_filterable = models.BooleanField(default=False)
    attribute_four_default_filtered_value = models.CharField(max_length=200, null=True, blank=True)

    attribute_five_name = models.CharField(max_length=200, null=True, blank=True)
    attribute_five_sortable = models.BooleanField(default=False)
    attribute_five_filterable = models.BooleanField(default=False)
    attribute_five_default_filtered_value = models.CharField(max_length=200, null=True, blank=True)
    
    default_sorted_attribute = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)], default=1)
    default_sorted_direction_ascending = models.BooleanField(default=True)
    
    # Risk rating for products in this category (0-100)
    # 0-25: Low risk, 26-50: Medium risk, 51-75: High risk, 76-100: Very high risk
    risk_rating = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Risk rating: 0-25 Low, 26-50 Medium, 51-75 High, 76-100 Very High. Products >75 require KYC verification'
    )

    class Meta:
        verbose_name_plural = "categories"
    def __str__(self):
        return self.title 

    def get_absolute_url(self):
        return reverse('navigation:browseCategory',
                        args=[self.slug])

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(Category, self).save(*args, **kwargs)
        bestPrices, created = BestPricedForCategory.objects.get_or_create(category_id=self)

    def get_attribute_definitions(self):
        """
        Return a normalized list of category attribute definitions.

        This keeps legacy behavior (attribute_one_* ... attribute_five_*) while allowing
        new rows from CategoryAttribute to overlay/extend definitions.
        """
        attributes = []
        for order in range(1, 6):
            suffix = {
                1: 'one',
                2: 'two',
                3: 'three',
                4: 'four',
                5: 'five',
            }[order]
            attributes.append(
                {
                    'order': order,
                    'name': getattr(self, f'attribute_{suffix}_name'),
                    'sortable': getattr(self, f'attribute_{suffix}_sortable'),
                    'filterable': getattr(self, f'attribute_{suffix}_filterable'),
                    'default_filtered_value': getattr(
                        self,
                        f'attribute_{suffix}_default_filtered_value',
                    ),
                }
            )

        # Overlay with row-based definitions where present.
        for attr in self.category_attributes.all():
            index = attr.order - 1
            if 0 <= index < len(attributes):
                attributes[index] = {
                    'order': attr.order,
                    'name': attr.name,
                    'sortable': attr.sortable,
                    'filterable': attr.filterable,
                    'default_filtered_value': attr.default_filtered_value,
                }
            else:
                attributes.append(
                    {
                        'order': attr.order,
                        'name': attr.name,
                        'sortable': attr.sortable,
                        'filterable': attr.filterable,
                        'default_filtered_value': attr.default_filtered_value,
                    }
                )

        return sorted(attributes, key=lambda item: item['order'])


class CategoryAttribute(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_attributes',
    )
    order = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text='Display order for the attribute (starts at 1)',
    )
    name = models.CharField(max_length=200, null=True, blank=True)
    sortable = models.BooleanField(default=False)
    filterable = models.BooleanField(default=False)
    default_filtered_value = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ('order',)
        unique_together = ('category', 'order')

    def __str__(self):
        label = self.name or f'Attribute {self.order}'
        return f'{self.category.title}: {label}'

class Product(models.Model):
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE)
    tags = models.ManyToManyField(CategoryTag, blank=True, related_name='products')
    image = models.ImageField(upload_to=RandomFileName('images/products/'), blank=True, null=True)
    description = models.TextField(null=True, blank=True)
    name = models.CharField(max_length=400)
    short_name = models.CharField(max_length=200, null=True, blank=True)

    create_date = models.DateTimeField('date created', auto_now_add=True)

    slug = models.SlugField(max_length=400, blank=True )

    attribute_one_value = models.CharField(max_length=200, null=True, blank=True)
    attribute_two_value = models.CharField(max_length=200, null=True, blank=True)
    attribute_three_value = models.CharField(max_length=200, null=True, blank=True)
    attribute_four_value = models.CharField(max_length=200, null=True, blank=True)
    attribute_five_value = models.CharField(max_length=200, null=True, blank=True)
    
    # Risk rating for this product (0-100, inherited from category but can be overridden)
    risk_rating = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text='Override category risk rating for this product. Leave blank to inherit from category.'
    )

    def __str__(self):
        return self.name
    
    def get_effective_risk_rating(self):
        """Return the effective risk rating (product override or category default)"""
        if self.risk_rating is not None:
            return self.risk_rating
        return self.category_id.risk_rating if self.category_id else 0
    
    def is_high_risk(self):
        """Check if product is high risk (>75)"""
        return self.get_effective_risk_rating() > 75

    def get_absolute_url(self):
        return reverse('navigation:productPage',
            args=[self.slug])

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Product, self).save(*args, **kwargs)
        bestPrices, created = BestPricedForProduct.objects.get_or_create(product=self)

class Order(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    create_date = models.DateTimeField('date created', auto_now_add=True)

    WANTED = 'W'
    TO_LET = 'L'
    DIRECTION_CHOICES = (
        (WANTED, 'Wanted'),
        (TO_LET, 'To Lend')
    )
    direction = models.CharField(
        db_index=True,
        max_length=1,
        choices = DIRECTION_CHOICES,
    )
    expiry_date = models.DateTimeField('datetime of order expiry (UK time)', db_index=True) # remove default=timezone.now
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(9999)], default=1)
    productIsNew = models.BooleanField('New product', default=False)

    MARKET = 'MKT'
    LIMIT = 'LMT'
    IMMEDIATE_OR_CANCEL = 'IOC'
    ICEBERG = 'ICE'
    PRICE_CHOICES = (
        (MARKET, 'Market'),
        (LIMIT, 'Limit'),
        (ICEBERG, 'Iceberg'),
        (IMMEDIATE_OR_CANCEL, 'Immediate Or Cancel'),
    )
    price_type = models.CharField(
        'price type',
        max_length=3,
        choices=PRICE_CHOICES,
        default=LIMIT,
    )



    ACTIVE = 'A'
    EXPIRED = 'X'
    STATUS_CHOICES = (
        (ACTIVE, 'Active'),
        (EXPIRED, 'Expired')
    )
    status = models.CharField(
        db_index=True,
        max_length=1,
        choices = STATUS_CHOICES,
        default=EXPIRED
    )

    # had to move from decimal field as mongodb is storing as text and sorting isnt working
    price = models.FloatField(validators=[MinValueValidator(0), MaxOrderPriceValidator])
    currency = models.CharField(max_length=3, default='GBP')
    
    # Location-based fields
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitude of the order location'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitude of the order location'
    )
    # Postcode of the order location
    postcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_index=True,
        help_text='UK Postcode for order location'
    )
    # Radius in kilometers within which the order is available
    radius_km = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text='Radius in kilometers within which this order is available'
    )
    # hidden_order = models.BooleanField(default=False)
    guaranteed = models.BooleanField(default=True)
    description = models.TextField(blank=True, max_length=500)
    additional_comments = models.TextField(blank=True, max_length=500)

    FRIENDS_ONLY = 'FRIENDS'
    PUBLIC_ONLY = 'PUBLIC'
    FRIENDS_AND_PUBLIC = 'BOTH'
    LET_VISIBILITY_CHOICES = (
        (FRIENDS_ONLY, 'Let to friends only'),
        (PUBLIC_ONLY, 'Let to public only'),
        (FRIENDS_AND_PUBLIC, 'Let to both'),
    )
    let_visibility = models.CharField(
        max_length=8,
        choices=LET_VISIBILITY_CHOICES,
        default=FRIENDS_AND_PUBLIC,
        db_index=True,
        help_text='Who can see and rent this listing'
    )

    # Letting-specific fields
    deposit = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text='Refundable deposit amount (£)'
    )
    mates_rates = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text='Discounted price per day for friends'
    )
    mates_deposit = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text='Reduced deposit for friends'
    )

    MUST_COLLECT = 'MC'
    WILL_DELIVER = 'WD'
    EITHER = 'EI'
    COLLECTION_CHOICES = (
        (MUST_COLLECT, 'You must collect'),
        (WILL_DELIVER, 'Lender will deliver'),
        (EITHER, 'Collection or delivery - To be discussed'),
    )
    collection_policy = models.CharField(
        max_length=2,
        choices=COLLECTION_CHOICES,
        default=MUST_COLLECT,
    )
    delivery_cost = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text='Flat delivery fee (£) when the delivery distance is beyond the included range'
    )
    delivery_within_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text='Delivery is charged per km up to this distance'
    )
    delivery_cost_per_km = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Delivery cost per km (£) within the included distance'
    )
    collection_details = models.CharField(
        max_length=200, blank=True, default='',
        help_text='e.g. times of collection, address note'
    )
    collection_is_home_address = models.BooleanField(
        default=True,
        help_text='Set this to false if collection happens somewhere other than your home address.',
    )
    collection_address = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text='Collection address if different from the home address',
    )
    collection_postcode = models.CharField(
        max_length=10,
        blank=True,
        default='',
        db_index=True,
        help_text='Collection postcode if different from the home address',
    )
    max_rental_days = models.PositiveIntegerField(
        null=True, blank=True, default=7,
        help_text='Maximum number of days a borrower can rent this item in one booking'
    )

    # public view of transaction ref to avoid sequential numbers
    order_reference = models.CharField(max_length=25, default=unique_order_ref_generator, db_index=True)

    history = HistoricalRecords()
    amended = models.DateTimeField(auto_now=True, db_index=True)

    def save(self, *args, **kwargs):
        self.price = round(self.price, 2)
        
        # Geocode postcode to lat/lon if not already done
        if self.postcode and (not self.latitude or not self.longitude):
            from common.geocoding import PostcodeGeocoder
            coords = PostcodeGeocoder.get_coordinates(self.postcode)
            if coords:
                self.latitude = coords['latitude']
                self.longitude = coords['longitude']
        
        super(Order, self).save(*args, **kwargs)
        updateSummaryPrices.delay(self.pk)

    def get_delivery_price_summary(self):
        if self.collection_policy == self.MUST_COLLECT:
            return ''

        per_km = self.delivery_cost_per_km or 0
        within_km = self.delivery_within_km or 0
        flat_fee = self.delivery_cost or 0

        if per_km > 0 and within_km > 0 and flat_fee > 0:
            return f'£{per_km:.2f}/km within {within_km} km, then £{flat_fee:.2f} flat'
        if per_km > 0 and within_km > 0:
            return f'£{per_km:.2f}/km within {within_km} km'
        if flat_fee > 0:
            return f'Flat delivery fee £{flat_fee:.2f}'
        return ''


class FavouriteOrder(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favourite_orders',
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='favourited_by',
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'order')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.user} -> {self.order_id}'


class OrderImage(models.Model):
    order = models.ForeignKey(Order, related_name='images', on_delete=models.CASCADE, blank=True, null=True)
    image = models.ImageField(upload_to=RandomFileName('images/orders/'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    first_image = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False, help_text='Main image shown in listing thumbnail')

    def saveNoImageModification(self, *args, **kwargs):
        super(OrderImage, self).save(*args, **kwargs)

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
        super(OrderImage, self).save(*args, **kwargs)


class LetPriceBand(models.Model):
    """Dynamic price bands for a to-let order. Price decreases for longer rental periods."""
    order = models.ForeignKey(Order, related_name='price_bands', on_delete=models.CASCADE)
    duration_days = models.PositiveIntegerField(
        help_text='Rental duration in days this rate applies to (e.g. 1, 5, 7, 30)'
    )
    price_per_day = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text='Price per day (£) for this duration band'
    )

    class Meta:
        ordering = ['duration_days']

    def __str__(self):
        return f"{self.duration_days} day(s) @ £{self.price_per_day:.2f}/day"


class OrderBlockedDate(models.Model):
    """Dates on which a to-let order is unavailable."""
    order = models.ForeignKey(Order, related_name='blocked_dates', on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    MANUAL = 'M'
    BOOKED = 'B'
    HANDOVER_UNAVAILABLE = 'H'
    REASON_CHOICES = (
        (MANUAL, 'Manual'),
        (BOOKED, 'Booked'),
        (HANDOVER_UNAVAILABLE, 'Unavailable for collection/drop-off'),
    )
    reason = models.CharField(max_length=1, choices=REASON_CHOICES, default=MANUAL)

    class Meta:
        unique_together = ('order', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.date} – {self.get_reason_display()}"


class TransactionFee(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=250, blank=True )
    tooltip = models.CharField(max_length=150, blank=True, null=True)
    popover = models.CharField(max_length=500, blank=True, null=True)
    FLAT = 'F'
    VALUE = 'V'
    WEIGHT = 'W'
    WEIGHT_AND_VALUE = 'WV'
    FEE_TYPE_CHOICES = (
        (FLAT, 'Flat fee'),
        (VALUE, 'Value'),
        (WEIGHT, 'Weight'),
        (WEIGHT_AND_VALUE, 'Weight and Value'),
    )
    fee_type = models.CharField(
        'price type',
        max_length=2,
        choices=FEE_TYPE_CHOICES,
        default=FLAT,
    )
    url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name 

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name).replace("-", "_") # not a true slug, used for functino names too
        super(TransactionFee, self).save(*args, **kwargs)

class TransactionFeeBand(models.Model):
    transaction_fee = models.ForeignKey(TransactionFee, on_delete=models.CASCADE, blank=True, null=True)
    price = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])
    max_weight = models.FloatField('max weight (kg)', default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])
    max_price = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999999)])
    PERCENTAGE = 'P'
    ABSOLUTE = 'A'
    PRICE_STYLE_CHOICES = (
        (PERCENTAGE, '%'),
        (ABSOLUTE, 'price')
    )
    price_style = models.CharField('absolute or relative pricing', 
        max_length=1, 
        choices=PRICE_STYLE_CHOICES,
        default=ABSOLUTE)

class BestPricedForCategory(models.Model):
    # would like to be 1-to-1 but currently breaking with djongo
    # https://github.com/nesdis/djongo/issues/188
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='best_prices')
    bestPricedBid = models.ForeignKey(Order, related_name='catBestBid', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid2 = models.ForeignKey(Order, related_name='catBestBid2', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid3 = models.ForeignKey(Order, related_name='catBestBid3', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid4 = models.ForeignKey(Order, related_name='catBestBid4', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid5 = models.ForeignKey(Order, related_name='catBestBid5', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer = models.ForeignKey(Order, related_name='catBestOffer', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer2 = models.ForeignKey(Order, related_name='catBestOffer2', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer3 = models.ForeignKey(Order, related_name='catBestOffer3', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer4 = models.ForeignKey(Order, related_name='catBestOffer4', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer5 = models.ForeignKey(Order, related_name='catBestOffer5', on_delete=models.CASCADE, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    

    class Meta:
        verbose_name_plural = "best priced for categories"

class BestPricedForProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='best_prices')
    bestPricedBid = models.ForeignKey(Order, related_name='productBestBid', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid2 = models.ForeignKey(Order, related_name='productBestBid2', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid3 = models.ForeignKey(Order, related_name='productBestBid3', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid4 = models.ForeignKey(Order, related_name='productBestBid4', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedBid5 = models.ForeignKey(Order, related_name='productBestBid5', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer = models.ForeignKey(Order, related_name='productBestOffer', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer2 = models.ForeignKey(Order, related_name='productBestOffer2', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer3 = models.ForeignKey(Order, related_name='productBestOffer3', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer4 = models.ForeignKey(Order, related_name='productBestOffer4', on_delete=models.CASCADE, blank=True, null=True)
    bestPricedOffer5 = models.ForeignKey(Order, related_name='productBestOffer5', on_delete=models.CASCADE, blank=True, null=True)
    numberActiveOrders = models.PositiveIntegerField(default=0)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

class System(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    value = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    amended = models.DateTimeField(auto_now=True)
