from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import PaymentMethod, Profile
from common.models import Category, LetPriceBand, Order, OrderBlockedDate, Product
from transaction.models import Transaction, TransactionMessage, TransactionMessageImage


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class ProfileSummarySerializer(serializers.Serializer):
    email_confirmed = serializers.BooleanField()
    mobile_verified = serializers.BooleanField()
    address_verified = serializers.BooleanField()
    postcode = serializers.CharField(allow_blank=True, allow_null=True)


class MobileTokenObtainSerializer(serializers.Serializer):
    login = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        user = authenticate(
            request=request,
            username=attrs['login'],
            password=attrs['password'],
        )

        if user is None or not user.is_active:
            raise AuthenticationFailed('Invalid credentials.')

        refresh = RefreshToken.for_user(user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSummarySerializer(user).data,
            'profile': None,
        }

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = None

        if profile is not None:
            data['profile'] = ProfileSummarySerializer(profile).data

        return data


class TransactionListSerializer(serializers.ModelSerializer):
    passive_user_id = serializers.IntegerField(source='user_passive_id')
    aggressive_user_id = serializers.IntegerField(source='user_aggressive_id')
    order_id = serializers.IntegerField(source='order_passive_id', allow_null=True)
    item_name = serializers.CharField(source='product.name', read_only=True, allow_blank=True)
    counterparty_name = serializers.SerializerMethodField()
    parties_summary = serializers.SerializerMethodField()

    def get_counterparty_name(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return ''

        counterparty = obj.user_passive if obj.user_aggressive_id == request.user.id else obj.user_aggressive
        full_name = f'{counterparty.first_name} {counterparty.last_name}'.strip()
        return full_name or counterparty.username

    def get_parties_summary(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return ''

        counterparty = self.get_counterparty_name(obj)
        if obj.user_aggressive_id == request.user.id:
            return f'You are borrowing from {counterparty}'
        return f'You are lending to {counterparty}'

    class Meta:
        model = Transaction
        fields = (
            'transaction_reference',
            'transaction_status',
            'payment_status',
            'deposit_status',
            'item_name',
            'counterparty_name',
            'parties_summary',
            'price',
            'friend_price',
            'deposit',
            'friend_deposit',
            'quantity',
            'rental_start_date',
            'rental_end_date',
            'passive_user_id',
            'aggressive_user_id',
            'order_id',
            'created',
            'amended',
        )


class TransactionDetailSerializer(TransactionListSerializer):
    enquiry_message = serializers.CharField()
    order_passive_description = serializers.CharField(allow_blank=True)
    product_status = serializers.CharField()
    checkout_condition_video_url = serializers.CharField(allow_blank=True)
    checkout_borrower_video_url = serializers.CharField(allow_blank=True)
    return_condition_video_url = serializers.CharField(allow_blank=True)
    return_borrower_video_url = serializers.CharField(allow_blank=True)
    return_lender_video_url = serializers.CharField(allow_blank=True)
    checkout_handover_verified_at = serializers.DateTimeField(allow_null=True)
    return_handover_verified_at = serializers.DateTimeField(allow_null=True)
    lender_agreed_at = serializers.DateTimeField(allow_null=True)
    renter_agreed_at = serializers.DateTimeField(allow_null=True)
    lender_agreement_pending_at = serializers.DateTimeField(allow_null=True)
    checkout_handover_pin_generated_at = serializers.DateTimeField(allow_null=True)
    return_handover_pin_generated_at = serializers.DateTimeField(allow_null=True)
    deposit_card_setup_status = serializers.CharField()
    deposit_test_hold_status = serializers.CharField()
    deposit_test_hold_at = serializers.DateTimeField(allow_null=True)
    deposit_collection_status = serializers.CharField()
    deposit_collection_requested_at = serializers.DateTimeField(allow_null=True)
    deposit_proposed_return_amount = serializers.FloatField()
    deposit_proposed_by_lender_at = serializers.DateTimeField(allow_null=True)
    deposit_proposal_contested_at = serializers.DateTimeField(allow_null=True)
    deposit_resolution_notes = serializers.CharField(allow_blank=True)
    listing_image_url = serializers.SerializerMethodField()
    listing_image_urls = serializers.SerializerMethodField()
    me_is_lender = serializers.SerializerMethodField()
    me_is_renter = serializers.SerializerMethodField()

    class Meta(TransactionListSerializer.Meta):
        fields = TransactionListSerializer.Meta.fields + (
            'enquiry_message',
            'order_passive_description',
            'product_status',
            'checkout_condition_video_url',
            'checkout_borrower_video_url',
            'return_condition_video_url',
            'return_borrower_video_url',
            'return_lender_video_url',
            'checkout_handover_verified_at',
            'return_handover_verified_at',
            'lender_agreed_at',
            'renter_agreed_at',
            'lender_agreement_pending_at',
            'checkout_handover_pin_generated_at',
            'return_handover_pin_generated_at',
            'deposit_card_setup_status',
            'deposit_test_hold_status',
            'deposit_test_hold_at',
            'deposit_collection_status',
            'deposit_collection_requested_at',
            'deposit_proposed_return_amount',
            'deposit_proposed_by_lender_at',
            'deposit_proposal_contested_at',
            'deposit_resolution_notes',
            'listing_image_url',
            'listing_image_urls',
            'me_is_lender',
            'me_is_renter',
        )

    def get_listing_image_url(self, obj):
        urls = self.get_listing_image_urls(obj)
        return urls[0] if urls else ''

    def get_listing_image_urls(self, obj):
        order = obj.order_passive
        if order is None:
            return []

        request = self.context.get('request')
        image_objs = order.images.filter(active=True).order_by('-is_main', '-first_image', '-uploaded_at')[:8]
        urls = []
        for image_obj in image_objs:
            if not image_obj.image:
                continue
            if request is None:
                urls.append(image_obj.image.url)
            else:
                urls.append(request.build_absolute_uri(image_obj.image.url))
        return urls

    def get_me_is_lender(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.user_passive_id == request.user.id

    def get_me_is_renter(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.user_aggressive_id == request.user.id


class TransactionMessageAttachmentSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = TransactionMessageImage
        fields = (
            'id',
            'image_url',
            'video_url',
            'uploaded_at',
        )

    def get_image_url(self, obj):
        request = self.context.get('request')
        if not obj.image:
            return ''
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)

    def get_video_url(self, obj):
        request = self.context.get('request')
        if not obj.video:
            return ''
        if request is None:
            return obj.video.url
        return request.build_absolute_uri(obj.video.url)


class TransactionMessageSerializer(serializers.ModelSerializer):
    attachments = serializers.SerializerMethodField()
    transaction_reference = serializers.SerializerMethodField()
    transaction_status = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    counterparty_name = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()

    class Meta:
        model = TransactionMessage
        fields = (
            'id',
            'user_from_id',
            'user_to_id',
            'subject',
            'description',
            'created',
            'read_by_user_to',
            'include_admin',
            'is_system_generated',
            'transaction_reference',
            'transaction_status',
            'item_name',
            'counterparty_name',
            'direction',
            'unread',
            'attachments',
        )

    def get_attachments(self, obj):
        queryset = obj.txn_msg_img.filter(active=True).order_by('uploaded_at')
        return TransactionMessageAttachmentSerializer(
            queryset,
            many=True,
            context=self.context,
        ).data

    def get_transaction_reference(self, obj):
        return obj.transaction.transaction_reference if obj.transaction else ''

    def get_transaction_status(self, obj):
        return obj.transaction.transaction_status if obj.transaction else ''

    def get_item_name(self, obj):
        transaction = obj.transaction
        if transaction is None or transaction.order_passive is None or transaction.order_passive.product is None:
            return ''
        return transaction.order_passive.product.name

    def get_counterparty_name(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return ''

        if obj.user_from_id == request.user.id:
            counterparty = obj.user_to
        else:
            counterparty = obj.user_from
        full_name = f'{counterparty.first_name} {counterparty.last_name}'.strip()
        return full_name or counterparty.username

    def get_direction(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return 'sent'
        return 'sent' if obj.user_from_id == request.user.id else 'received'

    def get_unread(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.user_to_id == request.user.id and not obj.read_by_user_to


class TransactionActionSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=64)
    reason = serializers.CharField(required=False, allow_blank=True)
    message_body = serializers.CharField(required=False, allow_blank=True)
    checkout_video_url = serializers.CharField(required=False, allow_blank=True)
    checkout_borrower_video_url = serializers.CharField(required=False, allow_blank=True)
    return_video_url = serializers.CharField(required=False, allow_blank=True)
    lender_return_video_url = serializers.CharField(required=False, allow_blank=True)
    pin = serializers.CharField(required=False, allow_blank=True)
    qr_payload = serializers.CharField(required=False, allow_blank=True)
    deposit_proposed_return_amount = serializers.FloatField(required=False)
    deposit_resolution_notes = serializers.CharField(required=False, allow_blank=True)
    payment_collected_placeholder = serializers.BooleanField(required=False)
    communication_rating = serializers.IntegerField(required=False, min_value=0, max_value=5)
    delivery_return_rating = serializers.IntegerField(required=False, min_value=0, max_value=5)
    overall_rating = serializers.IntegerField(required=False, min_value=0, max_value=5)
    feedback_comment = serializers.CharField(required=False, allow_blank=True)
    cardholder_name = serializers.CharField(required=False, allow_blank=True)
    card_brand = serializers.CharField(required=False, allow_blank=True)
    card_last4 = serializers.CharField(required=False, allow_blank=True)
    payment_method_id = serializers.IntegerField(required=False)
    setup_intent_id = serializers.CharField(required=False, allow_blank=True)


class LetPriceBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = LetPriceBand
        fields = (
            'duration_days',
            'price_per_day',
        )


class OrderSummarySerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    category_slug = serializers.CharField(source='product.category_id.slug', read_only=True)
    listing_image_url = serializers.SerializerMethodField()
    listing_image_urls = serializers.SerializerMethodField()
    blocked_dates = serializers.SerializerMethodField()
    handover_unavailable_dates = serializers.SerializerMethodField()
    price_bands = LetPriceBandSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'order_reference',
            'product_id',
            'product_name',
            'product_slug',
            'category_slug',
            'listing_image_url',
            'listing_image_urls',
            'blocked_dates',
            'handover_unavailable_dates',
            'direction',
            'status',
            'price',
            'currency',
            'quantity',
            'description',
            'additional_comments',
            'postcode',
            'latitude',
            'longitude',
            'radius_km',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'let_visibility',
            'collection_policy',
            'delivery_cost',
            'collection_details',
            'max_rental_days',
            'expiry_date',
            'create_date',
            'amended',
            'price_bands',
        )

    def get_listing_image_url(self, obj):
        urls = self.get_listing_image_urls(obj)
        return urls[0] if urls else ''

    def get_listing_image_urls(self, obj):
        request = self.context.get('request')
        image_objs = obj.images.filter(active=True).order_by('-is_main', '-first_image', '-uploaded_at')[:8]
        urls = []
        for image_obj in image_objs:
            if not image_obj.image:
                continue
            if request is None:
                urls.append(image_obj.image.url)
            else:
                urls.append(request.build_absolute_uri(image_obj.image.url))
        return urls

    def get_blocked_dates(self, obj):
        return [
            blocked_date.date.isoformat()
            for blocked_date in obj.blocked_dates.all()
            if blocked_date.reason in (OrderBlockedDate.MANUAL, OrderBlockedDate.BOOKED)
        ]

    def get_handover_unavailable_dates(self, obj):
        return [
            blocked_date.date.isoformat()
            for blocked_date in obj.blocked_dates.all()
            if blocked_date.reason == OrderBlockedDate.HANDOVER_UNAVAILABLE
        ]


class OrderAmendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            'price',
            'quantity',
            'description',
            'additional_comments',
            'postcode',
            'latitude',
            'longitude',
            'radius_km',
            'guaranteed',
            'let_visibility',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'collection_policy',
            'delivery_cost',
            'collection_details',
            'max_rental_days',
            'expiry_date',
        )


class CategorySummarySerializer(serializers.ModelSerializer):
    parent_slug = serializers.CharField(source='parent_category.slug', allow_null=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            'id',
            'title',
            'slug',
            'parent_slug',
            'description',
            'image_url',
        )

    def get_image_url(self, obj):
        request = self.context.get('request')
        if not obj.image:
            return ''
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)


class ProductSummarySerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source='category_id.slug', read_only=True)
    category_title = serializers.CharField(source='category_id.title', read_only=True)
    category_description = serializers.CharField(source='category_id.description', read_only=True, allow_null=True)
    active_order_count = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    attribute_one_value = serializers.CharField(read_only=True, allow_blank=True)
    attribute_two_value = serializers.CharField(read_only=True, allow_blank=True)
    attribute_three_value = serializers.CharField(read_only=True, allow_blank=True)
    attribute_four_value = serializers.CharField(read_only=True, allow_blank=True)
    attribute_five_value = serializers.CharField(read_only=True, allow_blank=True)
    risk_rating = serializers.IntegerField(read_only=True, allow_null=True)
    nearest_distance_km = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'short_name',
            'slug',
            'description',
            'category_slug',
            'category_title',
            'category_description',
            'image_url',
            'tags',
            'attribute_one_value',
            'attribute_two_value',
            'attribute_three_value',
            'attribute_four_value',
            'attribute_five_value',
            'risk_rating',
            'nearest_distance_km',
            'active_order_count',
        )

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            if request is None:
                return obj.image.url
            return request.build_absolute_uri(obj.image.url)
        return ''

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))


class ProductDetailSerializer(ProductSummarySerializer):
    active_orders = serializers.SerializerMethodField()

    class Meta(ProductSummarySerializer.Meta):
        fields = ProductSummarySerializer.Meta.fields + (
            'active_orders',
        )

    def get_active_orders(self, obj):
        orders = (
            obj.order_set.filter(status=Order.ACTIVE)
            .select_related('user')
            .prefetch_related('images')
            .order_by('-amended')[:20]
        )
        return OrderSummarySerializer(orders, many=True, context=self.context).data


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            'id',
            'card_brand',
            'card_last4',
            'is_default',
            'created_at',
            'updated_at',
        )
