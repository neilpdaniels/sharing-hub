from datetime import datetime, time as dt_time, timedelta

from django.contrib.auth import authenticate
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import PaymentMethod, Profile
from common.models import Category, FavouriteOrder, LetPriceBand, Order, OrderBlockedDate, Product
from mobile_api.models import MobileDevice
from transaction.models import Transaction, TransactionFeedback, TransactionMessage, TransactionMessageImage


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class NearbyUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    display_name = serializers.CharField()
    distance_km = serializers.FloatField()
    town = serializers.CharField(allow_blank=True, allow_null=True)
    postcode = serializers.CharField(allow_blank=True, allow_null=True)
    avatar_url = serializers.CharField(allow_blank=True)
    rating = serializers.FloatField()
    successful_txns = serializers.IntegerField()
    address_verified = serializers.BooleanField()


class FriendSummarySerializer(serializers.Serializer):
    friendship_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    town = serializers.CharField(allow_blank=True, allow_null=True)
    postcode = serializers.CharField(allow_blank=True, allow_null=True)
    avatar_url = serializers.CharField(allow_blank=True)
    status = serializers.CharField()


class BlockedUserSerializer(serializers.Serializer):
    block_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()


class ProfileSummarySerializer(serializers.Serializer):
    email_confirmed = serializers.BooleanField()
    mobile_verified = serializers.BooleanField()
    address_verified = serializers.BooleanField()
    postcode = serializers.CharField(allow_blank=True, allow_null=True)


class MobileDeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=[
            MobileDevice.PLATFORM_ANDROID,
            MobileDevice.PLATFORM_IOS,
            MobileDevice.PLATFORM_WEB,
            MobileDevice.PLATFORM_OTHER,
        ],
        required=False,
        default=MobileDevice.PLATFORM_OTHER,
    )
    device_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    app_version = serializers.CharField(max_length=32, required=False, allow_blank=True)
    notify_transaction_enquiry = serializers.BooleanField(required=False, default=True)
    notify_transaction_messages = serializers.BooleanField(required=False, default=True)
    notify_in_app_alerts = serializers.BooleanField(required=False, default=True)


class MobileDeviceUnregisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255, required=False, allow_blank=True)


class MobileNotificationPreferencesSerializer(serializers.Serializer):
    notify_transaction_enquiry = serializers.BooleanField(required=False)
    notify_transaction_messages = serializers.BooleanField(required=False)
    notify_in_app_alerts = serializers.BooleanField(required=False)


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
    counterparty = serializers.SerializerMethodField()
    parties_summary = serializers.SerializerMethodField()
    workflow_stage = serializers.SerializerMethodField()
    workflow_stage_label = serializers.SerializerMethodField()
    workflow_timeline = serializers.SerializerMethodField()
    workflow_payload = serializers.SerializerMethodField()
    feedback_left_by_me = serializers.SerializerMethodField()

    def get_counterparty_name(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return ''

        counterparty = obj.user_passive if obj.user_aggressive_id == request.user.id else obj.user_aggressive
        full_name = f'{counterparty.first_name} {counterparty.last_name}'.strip()
        return full_name or counterparty.username

    def get_counterparty(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return {}

        counterparty = obj.user_passive if obj.user_aggressive_id == request.user.id else obj.user_aggressive
        full_name = f'{counterparty.first_name} {counterparty.last_name}'.strip()
        display_name = full_name or counterparty.username

        try:
            profile = counterparty.profile
        except Profile.DoesNotExist:
            profile = None

        avatar_url = ''
        if profile is not None and profile.image:
            avatar_url = request.build_absolute_uri(profile.image.url)

        address_parts = []
        if profile is not None:
            if profile.address_line_1:
                address_parts.append(profile.address_line_1)
            if profile.address_line_2:
                address_parts.append(profile.address_line_2)
            locality = ', '.join(
                part for part in [profile.town, profile.county] if part
            )
            if locality:
                address_parts.append(locality)
            if profile.postcode:
                address_parts.append(profile.postcode)

        return {
            'id': counterparty.id,
            'display_name': display_name,
            'username': counterparty.username,
            'avatar_url': avatar_url,
            'mobile_number': profile.mobile_number if profile is not None else '',
            'address_line_1': profile.address_line_1 if profile is not None else '',
            'address_line_2': profile.address_line_2 if profile is not None else '',
            'town': profile.town if profile is not None else '',
            'county': profile.county if profile is not None else '',
            'postcode': profile.postcode if profile is not None else '',
            'address_display': '\n'.join(address_parts),
            'rating': profile.user_rating if profile is not None else 0,
            'successful_txns': profile.user_successful_txns if profile is not None else 0,
            'email_confirmed': profile.email_confirmed if profile is not None else False,
            'mobile_verified': profile.mobile_verified if profile is not None else False,
            'address_verified': profile.address_verified if profile is not None else False,
        }

    def get_parties_summary(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return ''

        counterparty = self.get_counterparty_name(obj)
        if obj.user_aggressive_id == request.user.id:
            return f'You are borrowing from {counterparty}'
        return f'You are lending to {counterparty}'

    def get_workflow_stage(self, obj):
        return obj.get_workflow_stage_number()

    def get_workflow_stage_label(self, obj):
        return obj.get_workflow_stage_label()

    def get_workflow_timeline(self, obj):
        return obj.get_workflow_timeline()

    def get_workflow_payload(self, obj):
        payload = obj.get_workflow_payload()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        payload['allowed_actions'] = obj.get_allowed_actions_for_user(user)
        return payload

    def get_feedback_left_by_me(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return TransactionFeedback.objects.filter(
            transaction=obj,
            left_by=request.user,
        ).exists()

    class Meta:
        model = Transaction
        fields = (
            'transaction_reference',
            'transaction_status',
            'payment_status',
            'deposit_status',
            'item_name',
            'counterparty_name',
            'counterparty',
            'parties_summary',
            'workflow_stage',
            'workflow_stage_label',
            'workflow_timeline',
            'workflow_payload',
            'feedback_left_by_me',
            'price',
            'friend_price',
            'deposit',
            'friend_deposit',
            'quantity',
            'rental_start_date',
            'rental_end_date',
            'delivery_distance_km',
            'delivery_cost',
            'rentalution_fee',
            'payment_collection_requested_at',
            'payment_collection_reference',
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
    deposit_proposal_iteration_count = serializers.IntegerField()
    deposit_proposal_iteration_limit = serializers.SerializerMethodField()
    deposit_proposal_warning_message = serializers.SerializerMethodField()
    deposit_resolution_notes = serializers.CharField(allow_blank=True)
    listing_image_url = serializers.SerializerMethodField()
    listing_image_urls = serializers.SerializerMethodField()
    me_is_lender = serializers.SerializerMethodField()
    me_is_renter = serializers.SerializerMethodField()
    active_dispute_case = serializers.SerializerMethodField()
    dispute_final_statement_deadline = serializers.SerializerMethodField()
    dispute_final_statement_seconds_remaining = serializers.SerializerMethodField()
    dispute_final_statement_open = serializers.SerializerMethodField()

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
            'deposit_proposal_iteration_count',
            'deposit_proposal_iteration_limit',
            'deposit_proposal_warning_message',
            'deposit_resolution_notes',
            'delivery_distance_km',
            'delivery_cost',
            'rentalution_fee',
            'listing_image_url',
            'listing_image_urls',
            'me_is_lender',
            'me_is_renter',
            'active_dispute_case',
            'dispute_final_statement_deadline',
            'dispute_final_statement_seconds_remaining',
            'dispute_final_statement_open',
        )

    def get_deposit_proposal_iteration_limit(self, obj):
        return 5

    def get_deposit_proposal_warning_message(self, obj):
        count = max(0, min(5, int(getattr(obj, 'deposit_proposal_iteration_count', 0) or 0)))
        if count < 3:
            return ''
        return (
            f'Iteration {count}/5: if you do not reach agreement, this will be escalated to a dispute '
            'and may incur a fee.'
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

    def get_active_dispute_case(self, obj):
        request = self.context.get('request')
        case = obj.dispute_cases.order_by('-created').first()
        if case is None:
            return None
        owner_name = ''
        if case.owner:
            owner_name = case.owner.get_full_name() or case.owner.username
        data = {
            'case_number': case.case_number,
            'reason_code': case.reason_code,
            'status': case.status,
            'outcome': case.outcome,
            'owner_name': owner_name,
        }
        if request is not None and getattr(request.user, 'is_staff', False):
            data['review_url'] = request.build_absolute_uri(
                reverse('transaction:dispute_case_review', kwargs={'case_number': case.case_number})
            )
        return data

    def _get_dispute_final_statement_deadline(self, obj):
        case = obj.dispute_cases.order_by('-created').first()
        if case is None or not case.created:
            return None
        return case.created + timedelta(hours=24)

    def get_dispute_final_statement_deadline(self, obj):
        deadline = self._get_dispute_final_statement_deadline(obj)
        return deadline.isoformat() if deadline else None

    def get_dispute_final_statement_seconds_remaining(self, obj):
        deadline = self._get_dispute_final_statement_deadline(obj)
        if deadline is None:
            return None
        seconds = int((deadline - timezone.now()).total_seconds())
        return max(0, seconds)

    def get_dispute_final_statement_open(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        case = obj.dispute_cases.order_by('-created').first()
        if case is None:
            return False
        deadline = self._get_dispute_final_statement_deadline(obj)
        if deadline is None or timezone.now() > deadline:
            return False
        if request.user == obj.user_passive:
            return not bool(case.lender_final_statement_at)
        if request.user == obj.user_aggressive:
            return not bool(case.borrower_final_statement_at)
        return False


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
    rental_start_date = serializers.SerializerMethodField()
    rental_end_date = serializers.SerializerMethodField()
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
            'rental_start_date',
            'rental_end_date',
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

    def get_rental_start_date(self, obj):
        transaction = obj.transaction
        if transaction is None or transaction.rental_start_date is None:
            return None
        return transaction.rental_start_date

    def get_rental_end_date(self, obj):
        transaction = obj.transaction
        if transaction is None or transaction.rental_end_date is None:
            return None
        return transaction.rental_end_date

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
    payment_method_id = serializers.CharField(required=False, allow_blank=True)
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
    distance_km = serializers.FloatField(read_only=True, allow_null=True)
    lender = serializers.SerializerMethodField()
    listing_image_url = serializers.SerializerMethodField()
    listing_image_urls = serializers.SerializerMethodField()
    blocked_dates = serializers.SerializerMethodField()
    handover_unavailable_dates = serializers.SerializerMethodField()
    price_bands = LetPriceBandSerializer(many=True, read_only=True)
    is_favourite = serializers.SerializerMethodField()
    money_earned = serializers.SerializerMethodField()
    money_pending = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id',
            'order_reference',
            'product_id',
            'product_name',
            'product_slug',
            'category_slug',
            'lender',
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
            'collection_is_home_address',
            'collection_address',
            'collection_postcode',
            'latitude',
            'longitude',
            'distance_km',
            'radius_km',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'let_visibility',
            'collection_policy',
            'delivery_cost',
            'delivery_within_km',
            'delivery_cost_per_km',
            'collection_details',
            'max_rental_days',
            'expiry_date',
            'create_date',
            'amended',
            'price_bands',
            'is_favourite',
            'money_earned',
            'money_pending',
        )

    def get_listing_image_url(self, obj):
        urls = self.get_listing_image_urls(obj)
        return urls[0] if urls else ''

    def get_lender(self, obj):
        lender = obj.user
        request = self.context.get('request')
        full_name = f'{lender.first_name} {lender.last_name}'.strip()

        profile = None
        try:
            profile = lender.profile
        except Profile.DoesNotExist:
            profile = None

        avatar_url = ''
        if profile is not None and profile.image:
            if request is None:
                avatar_url = profile.image.url
            else:
                avatar_url = request.build_absolute_uri(profile.image.url)

        return {
            'id': lender.id,
            'display_name': full_name or lender.username,
            'username': lender.username,
            'avatar_url': avatar_url,
            'rating': profile.user_rating if profile is not None else 0,
            'successful_txns': profile.user_successful_txns if profile is not None else 0,
            'postcode': profile.postcode if profile is not None else '',
            'email_confirmed': profile.email_confirmed if profile is not None else False,
            'mobile_verified': profile.mobile_verified if profile is not None else False,
            'address_verified': profile.address_verified if profile is not None else False,
        }

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

    def _order_transactions(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return []

        cached = getattr(self, '_transaction_cache', None)
        if cached is None:
            transaction_qs = Transaction.objects.filter(
                user_passive=request.user,
                order_passive__user=request.user,
            ).exclude(transaction_status=Transaction.CANCEL_ACCEPTED)
            cached = {}
            for txn in transaction_qs.select_related('order_passive').prefetch_related('transactioncharge_set'):
                cached.setdefault(txn.order_passive_id, []).append(txn)
            self._transaction_cache = cached

        return cached.get(obj.id, [])

    def get_money_earned(self, obj):
        earned = 0.0
        for txn in self._order_transactions(obj):
            if txn.payment_status == Transaction.PAYMENT_CAPTURED_PLACEHOLDER or txn.payment_collected_placeholder:
                earned += float(txn.price or 0)
        return round(earned, 2)

    def get_money_pending(self, obj):
        pending = 0.0
        for txn in self._order_transactions(obj):
            if txn.payment_status == Transaction.PAYMENT_PENDING and float(txn.price or 0) > 0:
                pending += float(txn.price or 0)
        return round(pending, 2)

    def get_is_favourite(self, obj):
        preset = getattr(obj, 'is_favourite', None)
        if preset is not None:
            return bool(preset)

        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False

        return FavouriteOrder.objects.filter(
            user=request.user,
            order_id=obj.id,
        ).exists()


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
            'delivery_within_km',
            'delivery_cost_per_km',
            'collection_details',
            'max_rental_days',
            'expiry_date',
        )


class OrderCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    expiry_date = serializers.DateField(write_only=True)
    price_bands = LetPriceBandSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = (
            'product_id',
            'expiry_date',
            'price',
            'radius_km',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'collection_policy',
            'delivery_cost',
            'delivery_within_km',
            'delivery_cost_per_km',
            'collection_details',
            'max_rental_days',
            'description',
            'additional_comments',
            'postcode',
            'latitude',
            'longitude',
            'let_visibility',
            'price_bands',
        )

    def validate(self, attrs):
        collection_policy = attrs.get('collection_policy', Order.MUST_COLLECT)
        radius_km = attrs.get('radius_km')
        delivery_within_km = attrs.get('delivery_within_km')
        delivery_cost_per_km = attrs.get('delivery_cost_per_km') or 0
        delivery_cost = attrs.get('delivery_cost') or 0

        if collection_policy == Order.MUST_COLLECT:
            attrs['delivery_within_km'] = None
            attrs['delivery_cost_per_km'] = None
            attrs['delivery_cost'] = None
        else:
            if delivery_cost_per_km > 0 and delivery_cost > 0:
                raise serializers.ValidationError(
                    'Choose one delivery pricing mode only: either price per km or flat delivery fee.'
                )

            if delivery_cost_per_km > 0 and not delivery_within_km:
                raise serializers.ValidationError(
                    {'delivery_within_km': 'Delivery up to (km) is required when using price per km.'}
                )

            if (
                collection_policy == Order.WILL_DELIVER
                and delivery_within_km
                and radius_km
                and delivery_within_km > radius_km
            ):
                raise serializers.ValidationError(
                    {
                        'delivery_within_km': (
                            'Delivery distance cannot be greater than Maximum let radius when lender will deliver.'
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError('Authenticated user is required.')

        product_id = validated_data.pop('product_id')
        expiry_date = validated_data.pop('expiry_date')
        price_bands = validated_data.pop('price_bands', [])

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist as exc:
            raise serializers.ValidationError({'product_id': 'Invalid product id.'}) from exc

        order = Order(
            product=product,
            user=request.user,
            direction=Order.TO_LET,
            quantity=1,
            status=Order.ACTIVE,
            expiry_date=datetime.combine(expiry_date, dt_time(23, 59, 59)),
            **validated_data,
        )
        order.save()

        for band in price_bands:
            duration_days = int(band.get('duration_days') or 0)
            price_per_day = float(band.get('price_per_day') or 0)
            if duration_days <= 0:
                continue
            if price_per_day < 0:
                continue
            LetPriceBand.objects.create(
                order=order,
                duration_days=duration_days,
                price_per_day=price_per_day,
            )

        return order


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
        orders = getattr(obj, 'filtered_active_orders', None)
        if orders is None:
            orders = (
                obj.order_set.filter(status=Order.ACTIVE)
                .select_related('user', 'product', 'product__category_id')
                .prefetch_related('images', 'blocked_dates', 'price_bands')
                .order_by('-amended')[:20]
            )
        return OrderSummarySerializer(orders, many=True, context=self.context).data


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            'id',
            'card_brand',
            'card_funding',
            'card_last4',
            'is_default',
            'created_at',
            'updated_at',
        )
