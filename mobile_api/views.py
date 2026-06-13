from datetime import timedelta
import random
import re

from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User
from django.db.models import BooleanField, Q, Value
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from account.forms import UserRegistrationStartForm, UserRegistrationVerifyForm
from account.models import PaymentMethod, Profile
from account.services import RegistrationService
from account.tasks import send_registration_verification_email
from common.geocoding import PostcodeGeocoder
from common.models import Category, FavouriteOrder, Order, OrderBlockedDate, OrderImage, Product
from friends.models import BlockedUser, Friendship, FriendsHelper
from mobile_api.models import MobileDevice
from transaction.forms import RentalEnquiryForm
from transaction.models import Transaction, TransactionFeedback, TransactionImage, TransactionMessage, TransactionMessageImage
from transaction.helpers import (
    get_transaction_pricing,
    sync_transaction_fee_charges,
    sync_transaction_pricing,
)
from transaction.stripe_connect import stripe_connect_service
from transaction.tasks import (
    async_collect_deposit_hold,
    async_confirm_card_setup,
    async_resolve_deposit_hold,
    async_setup_deposit_card_and_test_hold,
)

from .serializers import (
    CategorySummarySerializer,
    MobileTokenObtainSerializer,
    MobileDeviceRegisterSerializer,
    MobileNotificationPreferencesSerializer,
    MobileDeviceUnregisterSerializer,
    OrderCreateSerializer,
    OrderAmendSerializer,
    OrderSummarySerializer,
    PaymentMethodSerializer,
    NearbyUserSerializer,
    FriendSummarySerializer,
    BlockedUserSerializer,
    ProfileSummarySerializer,
    ProductDetailSerializer,
    ProductSummarySerializer,
    TransactionActionSerializer,
    TransactionDetailSerializer,
    TransactionListSerializer,
    TransactionMessageSerializer,
    UserSummarySerializer,
)


def _generate_txn_pin(length=6):
    digits = '0123456789'
    return ''.join(digits[random.randrange(0, 10)] for _ in range(length))


def _parse_qr_payload(payload):
    value = (payload or '').strip()
    # Expected: SHARINGHUB:CHECKOUT_PIN:<ref>:<pin> or SHARINGHUB:RETURN_PIN:<ref>:<pin>
    if not value.startswith('SHARINGHUB:'):
        return '', ''
    parts = value.split(':')
    if len(parts) != 4:
        return '', ''
    return parts[1], parts[3]


def _parse_amount(raw):
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _category_descendant_ids(category):
    descendant_ids = []
    frontier = [category.id]

    while frontier:
        descendant_ids.extend(frontier)
        frontier = list(
            Category.objects.filter(parent_category_id__in=frontier)
            .values_list('id', flat=True)
        )

    return descendant_ids


def _parse_distance_km(distance_raw):
    if not distance_raw or distance_raw.lower() == 'any':
        return None
    try:
        return int(distance_raw)
    except (TypeError, ValueError):
        return None


def _resolve_origin_coordinates(location):
    if not location:
        return None, None

    # Accept direct coordinate input from mobile, e.g. "51.50740, -0.12780".
    coordinate_match = re.match(
        r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$',
        location,
    )
    if coordinate_match:
        try:
            lat = float(coordinate_match.group(1))
            lon = float(coordinate_match.group(2))
        except (TypeError, ValueError):
            lat = None
            lon = None
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon

    coords = PostcodeGeocoder.geocode_location(location)
    if not coords:
        return None, None
    return coords.get('latitude'), coords.get('longitude')


def _price_per_day_for_days(order, rental_days):
    bands = list(order.price_bands.all().order_by('duration_days'))
    for band in bands:
        if rental_days <= band.duration_days:
            return float(band.price_per_day)
    if bands:
        return float(bands[-1].price_per_day)
    return float(order.price or 0)


def _filter_orders_by_distance(orders, origin_lat, origin_lon, max_distance_km=None):
    filtered_orders = []
    nearest_distance = None

    for order in orders:
        distance_km = None
        if (
            origin_lat is not None and
            origin_lon is not None and
            order.latitude is not None and
            order.longitude is not None
        ):
            distance_km = PostcodeGeocoder.calculate_distance(
                float(origin_lat),
                float(origin_lon),
                float(order.latitude),
                float(order.longitude),
            )

        if max_distance_km is not None and (distance_km is None or distance_km > max_distance_km):
            continue

        order.distance_km = distance_km
        filtered_orders.append(order)

        if distance_km is not None and (
            nearest_distance is None or distance_km < nearest_distance
        ):
            nearest_distance = distance_km

    return filtered_orders, nearest_distance


def _apply_favourite_flags_for_user(user, orders):
    if not orders:
        return

    if user is None or not user.is_authenticated:
        for order in orders:
            order.is_favourite = False
        return

    order_ids = [order.id for order in orders]
    favourite_ids = set(
        FavouriteOrder.objects.filter(
            user=user,
            order_id__in=order_ids,
        ).values_list('order_id', flat=True)
    )
    for order in orders:
        order.is_favourite = order.id in favourite_ids


def _serialize_nearby_user(request, profile, distance_km):
    user = profile.user
    full_name = f'{user.first_name} {user.last_name}'.strip()
    display_name = full_name or user.username
    avatar_url = ''
    if profile.image:
        avatar_url = request.build_absolute_uri(profile.image.url)
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'display_name': display_name,
        'distance_km': round(float(distance_km), 2),
        'town': profile.town,
        'postcode': profile.postcode,
        'avatar_url': avatar_url,
        'rating': profile.user_rating,
        'successful_txns': profile.user_successful_txns,
        'address_verified': profile.address_verified,
    }


def _serialize_friendship_profile(request, friendship, current_user):
    other = friendship.user_to if friendship.user_from_id == current_user.id else friendship.user_from
    try:
        profile = other.profile
    except Profile.DoesNotExist:
        profile = None

    full_name = f'{other.first_name} {other.last_name}'.strip()
    display_name = full_name or other.username
    avatar_url = ''
    if profile is not None and profile.image:
        avatar_url = request.build_absolute_uri(profile.image.url)

    return {
        'friendship_id': friendship.id,
        'user_id': other.id,
        'username': other.username,
        'display_name': display_name,
        'town': profile.town if profile is not None else '',
        'postcode': profile.postcode if profile is not None else '',
        'avatar_url': avatar_url,
        'status': friendship.status,
    }


def _serialize_blocked_user(block):
    user = block.blocked_user
    full_name = f'{user.first_name} {user.last_name}'.strip()
    display_name = full_name or user.username
    return {
        'block_id': block.id,
        'user_id': user.id,
        'username': user.username,
        'display_name': display_name,
    }


def _iter_rental_dates(start_date, end_date):
    if not start_date or not end_date:
        return
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def _holding_statuses():
    return (
        Transaction.RENTAL_ENQUIRY,
        Transaction.RENTAL_AGREED,
        Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
        Transaction.RENTAL_ONGOING,
        Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
        Transaction.RENTAL_RETURNED_DEPOSIT_RETURNED,
        Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED,
        Transaction.AWAITING_FEEDBACK,
        Transaction.FEEDBACK_ONE_SIDED,
    )


def _reserve_transaction_dates(txn):
    if not txn.order_passive_id:
        return
    for date_value in _iter_rental_dates(txn.rental_start_date, txn.rental_end_date):
        OrderBlockedDate.objects.get_or_create(
            order_id=txn.order_passive_id,
            date=date_value,
            defaults={'reason': OrderBlockedDate.BOOKED},
        )


def _release_transaction_dates(txn):
    if not txn.order_passive_id:
        return

    active_holds = Transaction.objects.filter(
        order_passive_id=txn.order_passive_id,
        transaction_status__in=_holding_statuses(),
    ).exclude(id=txn.id)

    for date_value in _iter_rental_dates(txn.rental_start_date, txn.rental_end_date):
        held_elsewhere = active_holds.filter(
            rental_start_date__lte=date_value,
            rental_end_date__gte=date_value,
        ).exists()
        if not held_elsewhere:
            OrderBlockedDate.objects.filter(
                order_id=txn.order_passive_id,
                date=date_value,
                reason=OrderBlockedDate.BOOKED,
            ).delete()


def _first_form_error(form):
    for field_errors in form.errors.get_json_data().values():
        if field_errors:
            message = field_errors[0].get('message')
            if message:
                return str(message)
    return 'Please check the submitted fields.'


def _mobile_auth_payload(user):
    refresh = RefreshToken.for_user(user)
    payload = {
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
        payload['profile'] = ProfileSummarySerializer(profile).data

    return payload


def _send_mobile_registration_code_email(request, email, code):
    resume_link = request.build_absolute_uri(reverse('register'))
    send_registration_verification_email.delay(email, code, resume_link)


class TransactionAccessMixin:
    def _get_txn(self):
        txn = generics.get_object_or_404(
            Transaction,
            transaction_reference=self.kwargs['transaction_reference'],
        )
        user = self.request.user
        if txn.user_passive_id != user.id and txn.user_aggressive_id != user.id:
            raise PermissionDenied('You do not have access to this transaction.')
        return txn

    def _is_lender(self, txn):
        return txn.user_passive_id == self.request.user.id

    def _is_renter(self, txn):
        return txn.user_aggressive_id == self.request.user.id

    def _has_verified_payment_card(self, txn):
        payment_card_required = (
            txn.deposit > 0
            or txn.price > 0
            or (txn.delivery_cost or 0) > 0
            or (txn.rentalution_fee or 0) > 0
        )
        if not payment_card_required:
            return True
        return (
            txn.deposit_card_setup_status == txn.CARD_READY
            and txn.deposit_test_hold_status == txn.TEST_HOLD_SUCCESS
        )

    def _rental_payment_required(self, txn):
        total_due = ((txn.quantity or 0) * (txn.price or 0)) + (txn.delivery_cost or 0) + (txn.rentalution_fee or 0)
        return total_due > 0

    def _is_rental_payment_collected(self, txn):
        if not self._rental_payment_required(txn):
            return True
        return txn.payment_status == txn.PAYMENT_CAPTURED_PLACEHOLDER

    def _is_deposit_funds_held(self, txn):
        if txn.deposit <= 0:
            return True
        return bool(
            txn.deposit_collected_placeholder
            or txn.deposit_collection_status == txn.COLLECT_SUCCESS
            or txn.deposit_status == txn.DEPOSIT_HELD_PLACEHOLDER
        )

    def _can_collect_deposit(self, txn):
        if txn.deposit <= 0:
            return False
        if txn.deposit_collected_placeholder:
            return False
        if txn.deposit_card_setup_status != txn.CARD_READY:
            return False
        if txn.deposit_test_hold_status != txn.TEST_HOLD_SUCCESS:
            return False
        if not txn.rental_start_date:
            return False
        return timezone.now().date() >= txn.rental_start_date

    def _system_message(self, txn, user_from, user_to, subject, description):
        TransactionMessage.objects.create(
            user_from=user_from,
            user_to=user_to,
            transaction=txn,
            subject=subject,
            description=description,
            is_system_generated=True,
        )


class MobileLoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = MobileTokenObtainSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class NearbyPeopleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        radius_raw = request.query_params.get('radius_km') or '10'
        try:
            radius_km = max(1, min(int(radius_raw), 100))
        except (TypeError, ValueError):
            radius_km = 10

        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {'detail': 'Please complete your profile before browsing nearby people.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.latitude is None or profile.longitude is None:
            return Response(
                {'detail': 'Please set your postcode before browsing nearby people.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nearby_ids = set()
        blocked_ids = FriendsHelper.get_blocked_user_ids(request.user)
        blocked_by_ids = FriendsHelper.get_blocked_by_user_ids(request.user)
        excluded_ids = blocked_ids | blocked_by_ids | {request.user.id}
        relationship_ids = set(
            Friendship.objects.filter(
                Q(user_from=request.user) | Q(user_to=request.user)
            ).values_list('user_from_id', flat=True)
        ) | set(
            Friendship.objects.filter(
                Q(user_from=request.user) | Q(user_to=request.user)
            ).values_list('user_to_id', flat=True)
        )
        excluded_ids |= relationship_ids

        nearby_profiles = Profile.objects.select_related('user').exclude(
            user_id__in=excluded_ids,
        ).exclude(
            latitude__isnull=True,
        ).exclude(
            longitude__isnull=True,
        )

        for candidate in nearby_profiles:
            distance_km = PostcodeGeocoder.calculate_distance(
                float(profile.latitude),
                float(profile.longitude),
                float(candidate.latitude),
                float(candidate.longitude),
            )
            if distance_km <= radius_km:
                nearby_ids.add((distance_km, candidate))

        nearby = [
            _serialize_nearby_user(request, candidate, distance_km)
            for distance_km, candidate in sorted(nearby_ids, key=lambda item: item[0])
        ]
        return Response(
            {
                'radius_km': radius_km,
                'count': len(nearby),
                'results': NearbyUserSerializer(nearby, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class FriendsHubView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        current_user = request.user
        accepted = Friendship.objects.filter(
            status=Friendship.ACCEPTED,
        ).filter(
            Q(user_from=current_user) | Q(user_to=current_user)
        ).select_related('user_from', 'user_to')
        pending_received = Friendship.objects.filter(
            user_to=current_user,
            status=Friendship.PENDING,
        ).select_related('user_from', 'user_to')
        pending_sent = Friendship.objects.filter(
            user_from=current_user,
            status=Friendship.PENDING,
        ).select_related('user_from', 'user_to')
        blocked = BlockedUser.objects.filter(
            blocked_by=current_user,
        ).select_related('blocked_user')

        accepted_payload = [
            _serialize_friendship_profile(request, friendship, current_user)
            for friendship in accepted
        ]
        pending_received_payload = [
            _serialize_friendship_profile(request, friendship, current_user)
            for friendship in pending_received
        ]
        pending_sent_payload = [
            _serialize_friendship_profile(request, friendship, current_user)
            for friendship in pending_sent
        ]
        blocked_payload = [
            _serialize_blocked_user(block)
            for block in blocked
        ]

        payload = {
            'accepted_count': len(accepted_payload),
            'pending_received_count': len(pending_received_payload),
            'pending_sent_count': len(pending_sent_payload),
            'blocked_count': len(blocked_payload),
            'accepted': FriendSummarySerializer(accepted_payload, many=True).data,
            'pending_received': FriendSummarySerializer(pending_received_payload, many=True).data,
            'pending_sent': FriendSummarySerializer(pending_sent_payload, many=True).data,
            'blocked': BlockedUserSerializer(blocked_payload, many=True).data,
        }
        return Response(payload, status=status.HTTP_200_OK)


class FriendRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id, *args, **kwargs):
        try:
            target_user = get_object_or_404(User, id=user_id)
            if target_user == request.user:
                return Response({'detail': 'You cannot add yourself as a friend.'}, status=status.HTTP_400_BAD_REQUEST)

            friendship = Friendship.objects.get(
                Q(user_from=request.user, user_to=target_user) |
                Q(user_from=target_user, user_to=request.user)
            )
            if friendship.status == Friendship.ACCEPTED:
                return Response({'detail': 'You are already connected.'}, status=status.HTTP_200_OK)
            if friendship.status == Friendship.PAUSED:
                return Response({'detail': 'This connection is paused.'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'detail': 'A connection already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        except Friendship.DoesNotExist:
            friendship = Friendship.objects.create(user_from=request.user, user_to=target_user)
        except Exception as exc:
            return Response(
                {'detail': f'Could not create friend request: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'status': 'ok',
                'message': 'Friend request sent.',
                'friendship_status': friendship.status,
            },
            status=status.HTTP_201_CREATED,
        )


class FriendRequestAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, friendship_id, *args, **kwargs):
        friendship = get_object_or_404(Friendship, id=friendship_id)
        if friendship.user_to_id != request.user.id:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        if friendship.status != Friendship.PENDING:
            return Response({'detail': 'This request is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)
        friendship.accept()
        return Response({'status': 'ok', 'message': 'Friend request accepted.'}, status=status.HTTP_200_OK)


class FriendRequestRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, friendship_id, *args, **kwargs):
        friendship = get_object_or_404(Friendship, id=friendship_id)
        if friendship.user_to_id != request.user.id:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        if friendship.status != Friendship.PENDING:
            return Response({'detail': 'This request is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)
        friendship.reject()
        return Response({'status': 'ok', 'message': 'Friend request rejected.'}, status=status.HTTP_200_OK)


class FriendRequestCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, friendship_id, *args, **kwargs):
        friendship = get_object_or_404(Friendship, id=friendship_id)
        if friendship.user_from_id != request.user.id:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        if friendship.status != Friendship.PENDING:
            return Response({'detail': 'This request is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)
        friendship.reject()
        return Response({'status': 'ok', 'message': 'Friend request cancelled.'}, status=status.HTTP_200_OK)


class FriendRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, friendship_id, *args, **kwargs):
        friendship = get_object_or_404(Friendship, id=friendship_id)
        if friendship.user_from_id != request.user.id and friendship.user_to_id != request.user.id:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        friendship.delete()
        return Response({'status': 'ok', 'message': 'Friend removed.'}, status=status.HTTP_200_OK)


class FriendBlockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id, *args, **kwargs):
        target_user = get_object_or_404(User, id=user_id)
        if target_user == request.user:
            return Response({'detail': 'You cannot block yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        if BlockedUser.objects.filter(blocked_by=request.user, blocked_user=target_user).exists():
            return Response({'detail': 'This user is already blocked.'}, status=status.HTTP_400_BAD_REQUEST)

        BlockedUser.objects.create(
            blocked_by=request.user,
            blocked_user=target_user,
            report_flagged=False,
        )
        Friendship.objects.filter(
            Q(user_from=request.user, user_to=target_user) |
            Q(user_from=target_user, user_to=request.user)
        ).delete()
        return Response({'status': 'ok', 'message': 'User blocked.'}, status=status.HTTP_200_OK)


class FriendUnblockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id, *args, **kwargs):
        target_user = get_object_or_404(User, id=user_id)
        block = BlockedUser.objects.filter(blocked_by=request.user, blocked_user=target_user).first()
        if block is None:
            return Response({'detail': 'This user is not blocked.'}, status=status.HTTP_400_BAD_REQUEST)

        block.delete()
        return Response({'status': 'ok', 'message': 'User unblocked.'}, status=status.HTTP_200_OK)


class MobilePasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        form = PasswordResetForm(data={'email': email})
        if not form.is_valid():
            return Response({'detail': _first_form_error(form)}, status=status.HTTP_400_BAD_REQUEST)

        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        )
        return Response(
            {'status': 'ok', 'message': 'If the email exists, a reset link has been sent.'},
            status=status.HTTP_200_OK,
        )


class MobilePasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, data=request.data)
        if not form.is_valid():
            return Response({'detail': _first_form_error(form)}, status=status.HTTP_400_BAD_REQUEST)

        form.save()
        return Response(
            {'status': 'ok', 'message': 'Password updated successfully.'},
            status=status.HTTP_200_OK,
        )


class MobileRegisterStartView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        form = UserRegistrationStartForm(data=request.data)
        if not form.is_valid():
            return Response({'detail': _first_form_error(form)}, status=status.HTTP_400_BAD_REQUEST)

        cleaned = form.cleaned_data
        email = cleaned['email']
        avatar_data = RegistrationService.build_avatar_from_form(cleaned)
        verification = RegistrationService.create_verification_record(email, cleaned, avatar_data)
        _send_mobile_registration_code_email(request, email, verification.verification_code)

        return Response(
            {
                'message': 'Verification code sent to your email.',
                'email': email,
            },
            status=status.HTTP_200_OK,
        )


class MobileRegisterResendView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        verification = RegistrationService.get_pending_verification(email)
        if verification is None:
            return Response(
                {'detail': 'No pending verification found. Please start registration again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.is_expired:
            verification.delete()
            return Response(
                {'detail': 'Verification code expired. Please start registration again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_verification = RegistrationService.resend_verification_code(verification)
        _send_mobile_registration_code_email(request, email, new_verification.verification_code)

        return Response({'message': 'A new verification code has been sent.'}, status=status.HTTP_200_OK)


class MobileRegisterVerifyView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        form = UserRegistrationVerifyForm(data=request.data)
        if not form.is_valid():
            return Response({'detail': _first_form_error(form)}, status=status.HTTP_400_BAD_REQUEST)

        verification = RegistrationService.get_pending_verification(email)
        if verification is None:
            return Response(
                {'detail': 'No pending verification found. Please start registration again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.is_expired:
            verification.delete()
            return Response(
                {'detail': 'Verification code expired. Please request a new code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.verification_code != form.cleaned_data['verification_code']:
            return Response({'detail': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {'detail': 'This email address is already registered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_user, _ = RegistrationService.complete_registration(
                verification,
                form.cleaned_data['password'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payload = _mobile_auth_payload(new_user)
        payload['message'] = 'Registration complete.'
        return Response(payload, status=status.HTTP_200_OK)


class MobileMeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        payload = {
            'user': UserSummarySerializer(request.user).data,
            'profile': None,
        }

        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = None

        if profile is not None:
            payload['profile'] = ProfileSummarySerializer(profile).data

        return Response(payload, status=status.HTTP_200_OK)


class MobileDeviceRegisterView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = MobileDeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        token = data['token'].strip()
        if not token:
            raise ValidationError('Token is required.')

        defaults = {
            'user': request.user,
            'platform': data.get('platform') or MobileDevice.PLATFORM_OTHER,
            'device_id': data.get('device_id', ''),
            'app_version': data.get('app_version', ''),
            'notify_transaction_enquiry': data.get('notify_transaction_enquiry', True),
            'notify_transaction_messages': data.get('notify_transaction_messages', True),
            'notify_in_app_alerts': data.get('notify_in_app_alerts', True),
            'active': True,
        }
        device, created = MobileDevice.objects.update_or_create(
            token=token,
            defaults=defaults,
        )

        return Response(
            {
                'status': 'ok',
                'created': created,
                'device_id': device.id,
            },
            status=status.HTTP_200_OK,
        )


class MobileDeviceUnregisterView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = MobileDeviceUnregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = (serializer.validated_data.get('token') or '').strip()

        queryset = MobileDevice.objects.filter(user=request.user, active=True)
        if token:
            queryset = queryset.filter(token=token)
        updated = queryset.update(active=False)
        return Response({'status': 'ok', 'updated': updated}, status=status.HTTP_200_OK)


class MobileNotificationPreferencesView(APIView):
    permission_classes = (IsAuthenticated,)

    def _current_values(self, user):
        device = MobileDevice.objects.filter(user=user, active=True).order_by('-updated').first()
        if device is None:
            return {
                'notify_transaction_enquiry': True,
                'notify_transaction_messages': True,
                'notify_in_app_alerts': True,
            }
        return {
            'notify_transaction_enquiry': bool(device.notify_transaction_enquiry),
            'notify_transaction_messages': bool(device.notify_transaction_messages),
            'notify_in_app_alerts': bool(device.notify_in_app_alerts),
        }

    def get(self, request, *args, **kwargs):
        return Response(self._current_values(request.user), status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        serializer = MobileNotificationPreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data

        queryset = MobileDevice.objects.filter(user=request.user, active=True)
        if updates and queryset.exists():
            queryset.update(**updates)

        payload = self._current_values(request.user)
        payload['updated'] = bool(updates)
        payload['applied_to_active_devices'] = queryset.count() if updates else 0
        return Response(payload, status=status.HTTP_200_OK)


class MobileAccountDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = None

        return Response(
            {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'profile': {
                    'mobile_number': profile.mobile_number if profile else '',
                    'address_line_1': profile.address_line_1 if profile else '',
                    'address_line_2': profile.address_line_2 if profile else '',
                    'town': profile.town if profile else '',
                    'county': profile.county if profile else '',
                    'postcode': profile.postcode if profile else '',
                    'email_confirmed': profile.email_confirmed if profile else False,
                    'mobile_verified': profile.mobile_verified if profile else False,
                    'address_verified': profile.address_verified if profile else False,
                },
            },
            status=status.HTTP_200_OK,
        )


class MobileKycStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        baseline_verified = bool(
            profile.email_confirmed and profile.mobile_verified and profile.address_verified
        )
        is_verified = is_profile_kyc_verified(profile)
        return Response(
            {
                'is_verified': is_verified,
                'baseline_verified': baseline_verified,
                'email_confirmed': profile.email_confirmed,
                'mobile_verified': profile.mobile_verified,
                'address_verified': profile.address_verified,
                'verified_at': profile.create_date,
                'status_label': 'Verified' if is_verified else 'Verification pending',
                'web_url': request.build_absolute_uri(reverse('kyc_verify')),
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist as exc:
            raise ValidationError('Profile not found.') from exc

        user_fields = {
            'first_name': request.data.get('first_name'),
            'last_name': request.data.get('last_name'),
            'email': request.data.get('email'),
        }
        for field, value in user_fields.items():
            if value is not None:
                setattr(user, field, value)
        user.save()

        profile_fields = {
            'mobile_number': request.data.get('mobile_number'),
            'address_line_1': request.data.get('address_line_1'),
            'address_line_2': request.data.get('address_line_2'),
            'town': request.data.get('town'),
            'county': request.data.get('county'),
            'postcode': request.data.get('postcode'),
        }
        for field, value in profile_fields.items():
            if value is not None:
                setattr(profile, field, value)
        profile.save()

        return self.get(request, *args, **kwargs)


class MobilePaymentMethodListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentMethodSerializer

    def get_queryset(self):
        return request_user_payment_methods(self.request.user)


def request_user_payment_methods(user):
    return PaymentMethod.objects.filter(user=user).order_by('-is_default', '-created_at')


class MobilePaymentMethodSetDefaultView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        payment_method = generics.get_object_or_404(
            PaymentMethod,
            id=self.kwargs['payment_method_id'],
            user=request.user,
        )
        PaymentMethod.objects.filter(user=request.user).update(is_default=False)
        payment_method.is_default = True
        payment_method.save(update_fields=['is_default', 'updated_at'])
        return Response({'status': 'ok', 'message': 'Default payment method updated.'})


class MobilePaymentMethodDeleteView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        payment_method = generics.get_object_or_404(
            PaymentMethod,
            id=self.kwargs['payment_method_id'],
            user=request.user,
        )
        payment_method.delete()
        return Response({'status': 'ok', 'message': 'Payment method deleted.'})


class MobileAppConfigView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        return Response({
            'stripe_publishable_key': getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''),
        })


class MobilePaymentMethodSetupIntentView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        result = stripe_connect_service.create_user_setup_intent(user=request.user)
        if not result.get('ok'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class MobilePaymentMethodConfirmView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    def post(self, request, *args, **kwargs):
        setup_intent_id = (request.data.get('setup_intent_id') or '').strip()
        payment_method_id = (request.data.get('payment_method_id') or '').strip()
        if not setup_intent_id and not payment_method_id:
            raise ValidationError('Missing setup intent or payment method.')

        result = stripe_connect_service.confirm_user_payment_method(
            user=request.user,
            setup_intent_id=setup_intent_id,
            payment_method_id=payment_method_id,
        )
        if not result.get('ok'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class OrderAccessMixin:
    def _get_order(self):
        order = generics.get_object_or_404(Order, id=self.kwargs['order_id'])
        if order.user_id != self.request.user.id:
            raise PermissionDenied('You do not have access to this order.')
        return order


class OrderListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSummarySerializer

    def get_queryset(self):
        user = self.request.user
        status_filter = (self.request.GET.get('status') or 'active').strip().lower()
        queryset = (
            Order.objects.filter(user=user)
            .select_related('product', 'product__category_id')
            .prefetch_related('price_bands', 'images')
        )

        if status_filter == 'active':
            queryset = queryset.filter(status=Order.ACTIVE)
        elif status_filter == 'expired':
            queryset = queryset.filter(status=Order.EXPIRED)

        return queryset.order_by('-amended')


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSummarySerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'order_id'

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('product', 'product__category_id')
            .prefetch_related('price_bands', 'images')
        )


class OrderAmendView(OrderAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, *args, **kwargs):
        order = self._get_order()
        if order.status != Order.ACTIVE:
            raise ValidationError('Only active orders can be amended.')

        serializer = OrderAmendSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSummarySerializer(order, context={'request': request}).data, status=status.HTTP_200_OK)


class OrderCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        payload = OrderSummarySerializer(order, context={'request': request}).data
        return Response(payload, status=status.HTTP_201_CREATED)


class OrderImageUploadView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, order_id, *args, **kwargs):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.user_id != request.user.id:
            raise PermissionDenied('You can only upload images to your own listings.')

        images = request.FILES.getlist('images')
        if not images:
            return Response({'error': 'No image files provided.'}, status=status.HTTP_400_BAD_REQUEST)

        has_existing_images = order.images.filter(active=True).exists()
        for idx, uploaded in enumerate(images):
            mark_main = not has_existing_images and idx == 0
            OrderImage.objects.create(
                order=order,
                image=uploaded,
                user=request.user,
                first_image=mark_main,
                is_main=mark_main,
                active=True,
            )

        payload = OrderSummarySerializer(order, context={'request': request}).data
        return Response(payload, status=status.HTTP_201_CREATED)


class OrderCancelView(OrderAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        order = self._get_order()
        if order.status == Order.EXPIRED:
            return Response({'status': 'ok', 'message': 'Order already expired.'}, status=status.HTTP_200_OK)

        order.status = Order.EXPIRED
        order.expiry_date = timezone.now()
        order.save(update_fields=['status', 'expiry_date', 'amended'])
        return Response({'status': 'ok', 'message': 'Order cancelled.'}, status=status.HTTP_200_OK)


class CategoryListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategorySummarySerializer

    def get_queryset(self):
        parent_slug = (self.request.GET.get('parent_slug') or '').strip()
        include_top = (self.request.GET.get('include_top') or '').strip().lower() == 'true'
        queryset = Category.objects.select_related('parent_category').order_by('title')

        if parent_slug:
            queryset = queryset.filter(parent_category__slug=parent_slug)
        elif not include_top:
            queryset = queryset.exclude(slug='top')

        return queryset


class CategoryProductsView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ProductSummarySerializer

    def get_queryset(self):
        category = generics.get_object_or_404(Category, slug=self.kwargs['category_slug'])
        location = (self.request.GET.get('location') or '').strip()
        distance_raw = (self.request.GET.get('distance') or '').strip()
        sort_by = (self.request.GET.get('sort_by') or 'name').strip().lower()
        include_zero_listings = (self.request.GET.get('include_zero_listings') or '').strip().lower() == 'true'

        max_distance_km = None
        if distance_raw and distance_raw.lower() != 'any':
            try:
                max_distance_km = int(distance_raw)
            except (TypeError, ValueError):
                max_distance_km = None

        origin_lat, origin_lon = _resolve_origin_coordinates(location)

        queryset = (
            Product.objects.filter(category_id__in=_category_descendant_ids(category))
            .select_related('category_id')
            .prefetch_related('order_set', 'order_set__blocked_dates', 'tags')
            .order_by('name')
        )

        products = []
        for product in queryset:
            active_orders = list(product.order_set.filter(status=Order.ACTIVE))
            if not active_orders and not include_zero_listings:
                continue

            nearest_distance = None
            if origin_lat is not None and origin_lon is not None:
                for order in active_orders:
                    if order.latitude is None or order.longitude is None:
                        continue
                    distance = PostcodeGeocoder.calculate_distance(
                        float(origin_lat),
                        float(origin_lon),
                        float(order.latitude),
                        float(order.longitude),
                    )
                    if nearest_distance is None or distance < nearest_distance:
                        nearest_distance = distance

            if max_distance_km is not None:
                if nearest_distance is None or nearest_distance > max_distance_km:
                    continue

            product.active_order_count = len(active_orders)
            product.nearest_distance_km = nearest_distance
            products.append(product)

        if sort_by == 'nearest' and origin_lat is not None and origin_lon is not None:
            products.sort(key=lambda p: (p.nearest_distance_km is None, p.nearest_distance_km or 0))
        elif sort_by == 'newest':
            products.sort(key=lambda p: p.create_date, reverse=True)
        else:
            products.sort(key=lambda p: p.name.lower())

        return products


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'product_slug'

    def get_queryset(self):
        return Product.objects.select_related('category_id').prefetch_related(
            'tags',
            'order_set__images',
            'order_set__blocked_dates',
            'order_set__price_bands',
        ).all()

    def get_object(self):
        product = super().get_object()
        location = (self.request.GET.get('location') or '').strip()
        max_distance_km = _parse_distance_km(
            (self.request.GET.get('distance') or '').strip().lower()
        )
        origin_lat, origin_lon = _resolve_origin_coordinates(location)

        active_orders = list(
            product.order_set.filter(status=Order.ACTIVE)
            .select_related('user', 'product', 'product__category_id')
            .prefetch_related('images', 'blocked_dates', 'price_bands')
            .order_by('-amended')[:20]
        )

        filtered_orders, nearest_distance = _filter_orders_by_distance(
            active_orders,
            origin_lat,
            origin_lon,
            max_distance_km=max_distance_km,
        )

        product.filtered_active_orders = filtered_orders
        _apply_favourite_flags_for_user(self.request.user, product.filtered_active_orders)
        product.active_order_count = len(filtered_orders)
        product.nearest_distance_km = nearest_distance
        return product


class FavouriteOrderListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSummarySerializer

    def get_queryset(self):
        favourite_order_ids = FavouriteOrder.objects.filter(
            user=self.request.user,
        ).values_list('order_id', flat=True)

        return (
            Order.objects.filter(id__in=favourite_order_ids, status=Order.ACTIVE)
            .select_related('user', 'product', 'product__category_id')
            .prefetch_related('price_bands', 'images', 'blocked_dates')
            .annotate(is_favourite=Value(True, output_field=BooleanField()))
            .order_by('-amended')
        )


class FavouriteOrderToggleView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        order = generics.get_object_or_404(Order, id=self.kwargs['order_id'])

        favourite, created = FavouriteOrder.objects.get_or_create(
            user=request.user,
            order=order,
        )
        if created:
            return Response(
                {'status': 'ok', 'is_favourite': True, 'message': 'Added to favourites.'},
                status=status.HTTP_200_OK,
            )

        favourite.delete()
        return Response(
            {'status': 'ok', 'is_favourite': False, 'message': 'Removed from favourites.'},
            status=status.HTTP_200_OK,
        )


class LenderListingsView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = OrderSummarySerializer

    def get_queryset(self):
        generics.get_object_or_404(User, id=self.kwargs['lender_id'])
        return (
            Order.objects.filter(user_id=self.kwargs['lender_id'], status=Order.ACTIVE)
            .select_related('user', 'product', 'product__category_id')
            .prefetch_related('price_bands', 'images', 'blocked_dates')
            .order_by('-amended')
        )


class SearchProductsView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ProductSummarySerializer

    def get_queryset(self):
        q = (self.request.GET.get('q') or '').strip()
        category_slug = (self.request.GET.get('category') or '').strip()
        location = (self.request.GET.get('location') or '').strip()
        distance_raw = (self.request.GET.get('distance') or '').strip()
        include_zero_listings = (self.request.GET.get('include_zero_listings') or '').strip().lower() == 'true'
        sort_by = (self.request.GET.get('sort_by') or 'name').strip().lower()

        max_distance_km = None
        if distance_raw and distance_raw.lower() != 'any':
            try:
                max_distance_km = int(distance_raw)
            except (TypeError, ValueError):
                max_distance_km = None

        products = Product.objects.select_related('category_id').prefetch_related('order_set__blocked_dates').all()

        if category_slug:
            category = generics.get_object_or_404(Category, slug=category_slug)
            products = products.filter(category_id__in=_category_descendant_ids(category))

        if q:
            products = products.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(category_id__title__icontains=q)
            )

        origin_lat, origin_lon = _resolve_origin_coordinates(location)

        matched = []
        for product in products:
            active_orders = list(product.order_set.filter(status=Order.ACTIVE))
            if not active_orders and not include_zero_listings:
                continue

            nearest_distance = None
            if origin_lat is not None and origin_lon is not None:
                for order in active_orders:
                    if order.latitude is None or order.longitude is None:
                        continue
                    distance = PostcodeGeocoder.calculate_distance(
                        float(origin_lat),
                        float(origin_lon),
                        float(order.latitude),
                        float(order.longitude),
                    )
                    if nearest_distance is None or distance < nearest_distance:
                        nearest_distance = distance

            if origin_lat is not None and origin_lon is not None and max_distance_km is not None:
                if nearest_distance is None or nearest_distance > max_distance_km:
                    continue

            product.active_order_count = len(active_orders)
            product.nearest_distance_km = nearest_distance
            matched.append(product)

        if sort_by == 'nearest' and origin_lat is not None and origin_lon is not None:
            matched.sort(key=lambda p: (p.nearest_distance_km is None, p.nearest_distance_km or 0))
        elif sort_by == 'newest':
            matched.sort(key=lambda p: p.create_date, reverse=True)
        else:
            matched.sort(key=lambda p: p.name.lower())

        return matched


class TransactionListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TransactionListSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Transaction.objects.filter(Q(user_passive=user) | Q(user_aggressive=user))
            .select_related('order_passive', 'user_passive', 'user_aggressive')
            .order_by('-created')
        )

    def post(self, request, *args, **kwargs):
        """
        Create a new enquiry transaction for an order.
        Expects: order_reference (required), enquiry_message (optional),
        rental_start_date and rental_end_date (optional, but recommended).
        """
        user = request.user
        order_reference = request.data.get('order_reference', '').strip()
        enquiry_message = request.data.get('enquiry_message', '').strip()
        rental_start_date = request.data.get('rental_start_date', '').strip()
        rental_end_date = request.data.get('rental_end_date', '').strip()

        # Validate order_reference
        if not order_reference:
            return Response(
                {'error': 'order_reference is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the order
        try:
            order = Order.objects.prefetch_related('blocked_dates').get(order_reference=order_reference)
        except Order.DoesNotExist:
            return Response(
                {'error': f'Order with reference {order_reference} not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prevent user from creating transaction with themselves
        if order.user == user:
            return Response(
                {'error': 'Cannot create transaction for your own order'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocked_dates = set(
            order.blocked_dates.filter(reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.BOOKED]).values_list('date', flat=True)
        )
        handover_dates = set(
            order.blocked_dates.filter(reason=OrderBlockedDate.HANDOVER_UNAVAILABLE).values_list('date', flat=True)
        )

        enquiry_form = RentalEnquiryForm(
            data={
                'rental_start_date': rental_start_date,
                'rental_end_date': rental_end_date,
                'enquiry_message': enquiry_message,
            },
            blocked_dates=blocked_dates,
            handover_dates=handover_dates,
            expiry_date=order.expiry_date.date() if order.expiry_date else None,
            max_rental_days=order.max_rental_days,
        )

        if rental_start_date or rental_end_date:
            if not enquiry_form.is_valid():
                return Response(
                    {'error': enquiry_form.errors.as_text()},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        start_date = enquiry_form.cleaned_data.get('rental_start_date') if enquiry_form.is_valid() else None
        end_date = enquiry_form.cleaned_data.get('rental_end_date') if enquiry_form.is_valid() else None
        rental_days = (end_date - start_date).days + 1 if start_date and end_date else 1
        price_per_day = _price_per_day_for_days(order, rental_days)

        # Create new transaction
        try:
            transaction = Transaction.objects.create(
                user_passive=order.user,
                user_aggressive=user,
                order_passive=order,
                order_passive_description=order.description or '',
                transaction_status=Transaction.RENTAL_ENQUIRY,
                prev_transaction_status=Transaction.RENTAL_ENQUIRY,
                payment_status=Transaction.PAYMENT_PENDING,
                deposit_status=Transaction.DEPOSIT_PENDING,
                product_status=Transaction.CONDITION_PENDING,
                quantity=1,
                price=price_per_day,
                friend_price=order.mates_rates,
                deposit=float(order.deposit or 0),
                friend_deposit=order.mates_deposit,
                delivery_distance_km=max(1, int(order.radius_km or 10)),
                current_spot_value=0,
                product=order.product,
                price_as_pct_spot_value=0,
                rental_start_date=start_date,
                rental_end_date=end_date,
                enquiry_message=enquiry_message,
            )

            pricing = get_transaction_pricing(transaction)
            sync_transaction_pricing(transaction, pricing)
            transaction.save(update_fields=[
                'delivery_distance_km',
                'delivery_cost',
                'rentalution_fee',
                'amended',
            ])
            sync_transaction_fee_charges(transaction, pricing)

            transaction.deposit_handling = transaction.calculate_deposit_handling()

            if order.product.is_high_risk():
                renter_profile = Profile.objects.get(user=user)
                lender_profile = Profile.objects.get(user=order.user)

                requires_kyc = False
                kyc_message = f'This is a high-risk product (risk rating: {order.product.get_effective_risk_rating()}/100). '

                if not is_profile_kyc_verified(renter_profile):
                    requires_kyc = True
                    kyc_message += 'As the person who is borrowing, you must complete KYC verification. '

                if not is_profile_kyc_verified(lender_profile):
                    requires_kyc = True
                    kyc_message += 'The lender must also complete KYC verification before this rental can proceed. '

                if requires_kyc:
                    transaction.requires_kyc = True
                    transaction.requires_kyc_message = kyc_message

            transaction.save()

            _reserve_transaction_dates(transaction)

            # Add initial enquiry message if provided
            if enquiry_message:
                TransactionMessage.objects.create(
                    user_from=user,
                    user_to=order.user,
                    transaction=transaction,
                    subject=f'Transaction {transaction.transaction_reference}',
                    description=enquiry_message,
                )
            else:
                TransactionMessage.objects.create(
                    user_from=user,
                    user_to=order.user,
                    transaction=transaction,
                    subject=f'New enquiry {transaction.transaction_reference}',
                    description='You have a new enquiry on your listing.',
                    is_system_generated=True,
                )

            for ord_image in order.images.filter(active=True):
                txn_image = TransactionImage()
                txn_image.image = ord_image.image
                txn_image.transaction = transaction
                txn_image.save()

            # Return the created transaction
            serializer = TransactionDetailSerializer(
                transaction,
                context={'request': request},
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': f'Failed to create transaction: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TransactionDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TransactionDetailSerializer
    lookup_field = 'transaction_reference'

    def get_queryset(self):
        user = self.request.user
        return Transaction.objects.filter(Q(user_passive=user) | Q(user_aggressive=user)).select_related(
            'order_passive',
            'user_passive',
            'user_aggressive',
        )


class MobileTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)


class TransactionMessagesView(TransactionAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request, *args, **kwargs):
        txn = self._get_txn()
        queryset = (
            txn.transactionmessage_set.all()
            .prefetch_related('txn_msg_img')
            .order_by('-created')
        )
        serializer = TransactionMessageSerializer(
            queryset,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        txn = self._get_txn()
        user = request.user
        is_lender = self._is_lender(txn)
        is_renter = self._is_renter(txn)
        if not (is_lender or is_renter):
            raise PermissionDenied('Not allowed.')

        body = (request.data.get('message_body') or '').strip()
        image_files = request.FILES.getlist('images')
        video_files = request.FILES.getlist('videos')

        if not body and not image_files and not video_files:
            raise ValidationError('Please include a message body or attachment.')

        for video_file in video_files:
            content_type = (getattr(video_file, 'content_type', '') or '').lower()
            if not content_type.startswith('video/'):
                raise ValidationError(f'{video_file.name} is not a valid video file.')

        recipient = txn.user_aggressive if is_lender else txn.user_passive
        msg = TransactionMessage.objects.create(
            user_from=user,
            user_to=recipient,
            transaction=txn,
            subject=f'Transaction {txn.transaction_reference}',
            description=body,
        )

        for idx, image_file in enumerate(image_files):
            TransactionMessageImage.objects.create(
                txn_message=msg,
                user=user,
                image=image_file,
                first_image=(idx == 0),
                active=True,
            )

        for video_file in video_files:
            image_obj = TransactionMessageImage(
                txn_message=msg,
                user=user,
                video=video_file,
                video_raw=video_file,
                first_image=False,
                active=True,
            )
            image_obj.full_clean()
            image_obj.save()

        serializer = TransactionMessageSerializer(msg, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MobileInboxView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        queryset = list(
            TransactionMessage.objects.filter(Q(user_from=user) | Q(user_to=user))
            .select_related('transaction', 'transaction__order_passive__product', 'user_from', 'user_to')
            .prefetch_related('txn_msg_img')
        )
        queryset = sorted(sorted(queryset, key=lambda message: message.created, reverse=True), key=lambda message: 0 if message.user_to_id == user.id and not message.read_by_user_to else 1)
        serializer = TransactionMessageSerializer(
            queryset,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionCodesView(TransactionAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        txn = self._get_txn()
        is_lender = self._is_lender(txn)
        is_renter = self._is_renter(txn)

        payload = {
            'transaction_reference': txn.transaction_reference,
            'checkout_code': None,
            'return_code': None,
        }

        if is_renter and txn.checkout_handover_pin and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            payload['checkout_code'] = {
                'pin': txn.checkout_handover_pin,
                'qr_payload': f'SHARINGHUB:CHECKOUT_PIN:{txn.transaction_reference}:{txn.checkout_handover_pin}',
            }

        if is_lender and txn.return_handover_pin and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            payload['return_code'] = {
                'pin': txn.return_handover_pin,
                'qr_payload': f'SHARINGHUB:RETURN_PIN:{txn.transaction_reference}:{txn.return_handover_pin}',
            }

        return Response(payload, status=status.HTTP_200_OK)


class TransactionActionView(TransactionAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        txn = self._get_txn()
        is_lender = self._is_lender(txn)
        is_renter = self._is_renter(txn)
        serializer = TransactionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data['action']

        def notify_counterparty(subject, description):
            recipient = txn.user_aggressive if request.user == txn.user_passive else txn.user_passive
            self._system_message(txn, request.user, recipient, subject, description)

        def deposit_proposal_iterations():
            raw_value = getattr(txn, 'deposit_proposal_iteration_count', 0) or 0
            return max(0, min(5, int(raw_value)))

        def deposit_iteration_warning(iteration_count):
            if iteration_count < 3:
                return ''
            return (
                f'Iteration {iteration_count}/5: if you do not reach agreement, this will be escalated to a dispute '
                'and may incur a fee.'
            )

        def is_missing_rental_voided():
            return '[MISSING_RENTAL_VOIDED]' in (txn.deposit_resolution_notes or '')

        def refresh_feedback_deadline():
            txn.refresh_feedback_deadline()

        def uploaded_video_url(subject_prefix, description):
            video_files = request.FILES.getlist('videos')
            if not video_files:
                return ''

            video_file = video_files[0]
            txn_message = TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive if is_lender else txn.user_passive,
                transaction=txn,
                subject=f'{subject_prefix} {txn.transaction_reference}',
                description=description,
                is_system_generated=True,
            )
            txn_msg_image = TransactionMessageImage(
                txn_message=txn_message,
                user=request.user,
                video=video_file,
                video_raw=video_file,
                first_image=False,
                active=True,
            )
            txn_msg_image.save()
            return txn_msg_image.video.url if txn_msg_image.video else ''

        if action == 'agree_rental' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_AGREED
            txn.lender_agreement_pending_at = timezone.now()
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'lender_agreement_pending_at', 'amended'])
            _reserve_transaction_dates(txn)
            notify_counterparty(
                f'Rental agreement created {txn.transaction_reference}',
                'Your enquiry was accepted. Review the rental agreement and confirm to proceed.',
            )
            return Response({'status': 'ok', 'message': 'Rental agreement created.'})

        if action == 'reject_enquiry' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            _release_transaction_dates(txn)
            notify_counterparty(
                f'Enquiry declined {txn.transaction_reference}',
                'Your rental enquiry was declined.',
            )
            return Response({'status': 'ok', 'message': 'Enquiry rejected.'})

        if action == 'request_cancellation' and txn.transaction_status == txn.RENTAL_ENQUIRY:
            reason = (data.get('reason') or '').strip()
            if not reason:
                raise ValidationError('Please provide a cancellation reason.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            _release_transaction_dates(txn)
            other_user = txn.user_aggressive if is_lender else txn.user_passive
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=other_user,
                transaction=txn,
                subject=f'Transaction Cancelled - {txn.transaction_reference}',
                description=f'The transaction has been cancelled.\n\nReason: {reason}',
            )
            return Response({'status': 'ok', 'message': 'Transaction cancelled.'})

        if action == 'confirm_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and not txn.lender_agreed_at:
            if not txn.lender_agreement_pending_at:
                txn.lender_agreement_pending_at = timezone.now()
            txn.lender_agreed_at = timezone.now()
            txn.save(update_fields=['lender_agreed_at', 'lender_agreement_pending_at', 'amended'])
            self._system_message(
                txn,
                txn.user_passive,
                txn.user_aggressive,
                f'Rental Agreement - Please Confirm {txn.transaction_reference}',
                'Lender confirmed contract terms. Borrower should confirm to proceed.',
            )
            return Response({'status': 'ok', 'message': 'Contract confirmed by lender.'})

        if action == 'reinitiate_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            deadline_24h = txn.lender_agreed_at + timedelta(hours=24)
            if timezone.now() <= deadline_24h:
                raise ValidationError('Borrower still has time to confirm.')
            txn.lender_agreed_at = timezone.now()
            txn.save(update_fields=['lender_agreed_at', 'amended'])
            self._system_message(
                txn,
                txn.user_passive,
                txn.user_aggressive,
                f'Rental Agreement - Re-sent {txn.transaction_reference}',
                'Lender re-sent confirmation request. 24-hour confirmation window restarted.',
            )
            return Response({'status': 'ok', 'message': 'Confirmation request re-sent.'})

        if action == 'confirm_renter_contract' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            txn.renter_agreed_at = timezone.now()
            txn.save(update_fields=['renter_agreed_at', 'amended'])
            notify_counterparty(
                f'Rental confirmed {txn.transaction_reference}',
                'The borrower confirmed the rental agreement.',
            )
            return Response({'status': 'ok', 'message': 'Contract confirmed by renter.'})

        if action == 'reject_rental_agreement' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and not txn.renter_agreed_at:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            _release_transaction_dates(txn)
            notify_counterparty(
                f'Rental agreement rejected {txn.transaction_reference}',
                'The borrower rejected the rental agreement.',
            )
            return Response({'status': 'ok', 'message': 'Rental agreement rejected.'})

        if action == 'report_missing_rental' and is_renter and txn.transaction_status in (
            txn.RENTAL_ENQUIRY,
            txn.RENTAL_AGREED,
        ):
            if not txn.rental_start_date or timezone.now().date() <= txn.rental_start_date:
                raise ValidationError('Missing rental can only be reported after rental start date has passed.')
            if txn.checkout_handover_verified_at:
                raise ValidationError('Rental handover already verified, missing rental cannot be reported.')
            reason = (data.get('reason') or '').strip()
            marker = '[MISSING_RENTAL_VOIDED]'
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = f'{marker} Borrower reported missing rental. {reason}'.strip()
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'transaction_status_raised_by',
                'deposit_status',
                'deposit_resolution_notes',
                'amended',
            ])
            _release_transaction_dates(txn)
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_passive,
                transaction=txn,
                subject=f'Missing rental reported {txn.transaction_reference}',
                description='Borrower reported missing rental after start date. Transaction voided and marked for dispute review.',
                include_admin=True,
                is_system_generated=True,
            )
            return Response({'status': 'ok', 'message': 'Missing rental reported and transaction voided.'})

        if action == 'report_missing_return' and is_lender and txn.transaction_status in (
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        ):
            if not txn.rental_end_date or timezone.now().date() <= txn.rental_end_date:
                raise ValidationError('Missing return can only be reported after rental return date has passed.')
            reason = (data.get('reason') or '').strip()
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.DISPUTE_REQUESTED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = f'Lender reported missing return. {reason}'.strip()
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'deposit_status',
                'deposit_resolution_notes',
                'amended',
            ])
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Missing return reported {txn.transaction_reference}',
                description='Lender reported missing return after return date. Dispute workflow has been opened for admin review.',
                include_admin=True,
                is_system_generated=True,
            )
            return Response({'status': 'ok', 'message': 'Missing return reported and dispute opened.'})

        if action == 'use_existing_card' and is_renter and txn.transaction_status in (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED):
            method_id = data.get('payment_method_id')
            if not method_id:
                raise ValidationError('payment_method_id is required.')
            try:
                pm = PaymentMethod.objects.get(id=method_id, user=request.user)
            except PaymentMethod.DoesNotExist as exc:
                raise ValidationError('Payment method not found.') from exc
            txn.deposit_card_setup_status = txn.CARD_READY
            txn.deposit_cardholder_name = 'Stripe'
            txn.deposit_card_brand = pm.card_brand
            txn.deposit_card_funding = pm.card_funding
            txn.deposit_card_last4 = pm.card_last4
            txn.deposit_test_hold_status = txn.TEST_HOLD_SUCCESS
            txn.deposit_test_hold_amount = 0.30
            txn.deposit_test_hold_at = timezone.now()
            txn.stripe_setup_intent_id = pm.stripe_setup_intent_id
            txn.stripe_payment_method_id = pm.stripe_payment_method_id
            txn.save()
            return Response({'status': 'ok', 'message': 'Existing card linked.'})

        if action == 'add_deposit_card' and is_renter and txn.transaction_status in (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED):
            cardholder_name = (data.get('cardholder_name') or '').strip()
            card_brand = (data.get('card_brand') or '').strip()
            card_last4 = (data.get('card_last4') or '').strip()
            if not cardholder_name:
                raise ValidationError('cardholder_name is required.')
            if len(card_last4) != 4 or not card_last4.isdigit():
                raise ValidationError('card_last4 must be 4 digits.')
            async_setup_deposit_card_and_test_hold.delay(
                transaction_id=txn.id,
                cardholder_name=cardholder_name,
                card_brand=card_brand,
                card_last4=card_last4,
            )
            txn.deposit_card_setup_status = txn.CARD_NONE
            txn.save(update_fields=['deposit_card_setup_status', 'amended'])
            return Response({'status': 'ok', 'message': 'Card setup started.'})

        if action == 'create_stripe_setup_intent' and is_renter and txn.transaction_status in (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED):
            if txn.deposit_collected_placeholder:
                raise ValidationError('Card setup is no longer available once deposit is collected.')

            payment_card_required = (txn.deposit > 0 or txn.price > 0)
            if not payment_card_required:
                raise ValidationError('Card setup is not required for this transaction.')

            setup_result = stripe_connect_service.create_setup_intent(transaction=txn)
            if not setup_result.get('ok'):
                raise ValidationError(setup_result.get('error') or 'Failed to create setup intent.')

            setup_intent_id = (setup_result.get('setup_intent_id') or '').strip()
            if setup_intent_id:
                txn.stripe_setup_intent_id = setup_intent_id
                txn.save(update_fields=['stripe_setup_intent_id', 'amended'])

            return Response({
                'status': 'ok',
                'message': 'Stripe setup intent created.',
                'provider': setup_result.get('provider') or '',
                'setup_intent_id': setup_intent_id,
                'client_secret': setup_result.get('client_secret') or '',
            })

        if action == 'confirm_stripe_card' and is_renter and txn.transaction_status in (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED):
            payment_method_id = (request.data.get('payment_method_id') or '').strip()
            setup_intent_id = (data.get('setup_intent_id') or '').strip()
            if not payment_method_id:
                raise ValidationError('payment_method_id is required.')
            txn.deposit_card_setup_status = txn.CARD_NONE
            txn.deposit_test_hold_status = txn.TEST_HOLD_NOT_RUN
            txn.stripe_setup_intent_id = setup_intent_id
            txn.stripe_payment_method_id = payment_method_id
            txn.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'stripe_setup_intent_id', 'stripe_payment_method_id', 'amended'])
            async_confirm_card_setup.delay(
                transaction_id=txn.id,
                setup_intent_id=setup_intent_id,
                payment_method_id=payment_method_id,
            )
            return Response({'status': 'ok', 'message': 'Stripe card confirmation submitted.'})

        if action == 'collect_deposit' and is_lender and txn.transaction_status in (
            txn.RENTAL_AGREED,
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
        ):
            if not self._can_collect_deposit(txn):
                raise ValidationError('Deposit cannot be collected yet.')
            async_collect_deposit_hold.delay(transaction_id=txn.id)
            txn.deposit_collection_status = txn.COLLECT_NOT_RUN
            txn.save(update_fields=['deposit_collection_status', 'amended'])
            return Response({'status': 'ok', 'message': 'Deposit collection started.'})

        if action == 'initiate_rental' and is_lender and txn.transaction_status == txn.RENTAL_AGREED:
            if not self._has_verified_payment_card(txn):
                raise ValidationError('Borrower payment card must be verified first.')
            checkout_video = (data.get('checkout_video_url') or '').strip()
            if not checkout_video:
                checkout_video = uploaded_video_url(
                    'Checkout evidence submitted',
                    'Lender submitted rental-start evidence. Borrower should confirm or submit counter-evidence.',
                )
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_DAY_AWAITING_VERIFICATION
            txn.checkout_condition_video_url = checkout_video
            txn.checkout_borrower_confirmed = False
            txn.checkout_borrower_video_url = ''
            txn.checkout_handover_pin = ''
            txn.checkout_handover_pin_generated_at = None
            txn.checkout_handover_verified_at = None
            if checkout_video:
                txn.product_status = txn.CHECKOUT_VIDEO_ADDED
            txn.payment_collected_placeholder = True
            txn.payment_status = txn.PAYMENT_CAPTURED_PLACEHOLDER
            txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER if txn.deposit_collected_placeholder else txn.DEPOSIT_PENDING
            rental_amount = round((txn.quantity or 0) * (txn.price or 0), 2)
            total_before_deposit = round(rental_amount + (txn.delivery_cost or 0) + (txn.rentalution_fee or 0), 2)
            txn.payment_placeholder_notes = (
                f'Rental £{rental_amount:.2f}; '
                f'Delivery £{(txn.delivery_cost or 0):.2f}; '
                f'Rentalution fee £{(txn.rentalution_fee or 0):.2f}; '
                f'Total before deposit £{total_before_deposit:.2f}'
            )

            payment_capture_result = stripe_connect_service.collect_rental_payment(transaction=txn)
            if not payment_capture_result.get('ok'):
                raise ValidationError(
                    f'Rental payment capture failed. Handover PIN will not be shown until payment succeeds. {payment_capture_result.get("error") or ""}'.strip()
                )

            txn.payment_collected_placeholder = True
            txn.payment_status = payment_capture_result.get('payment_status', txn.PAYMENT_CAPTURED_PLACEHOLDER)
            txn.payment_collection_requested_at = payment_capture_result.get('collection_requested_at', timezone.now())
            txn.payment_collection_reference = payment_capture_result.get('collection_reference', '')
            charged_amount = float(payment_capture_result.get('charged_amount') or 0)
            capture_note = (
                f'[STRIPE_RENTAL_CAPTURE] charged={charged_amount:.2f} '
                f'status={payment_capture_result.get("payment_intent_status") or ""} '
                f'ref={txn.payment_collection_reference}'
            ).strip()
            if capture_note:
                existing_payment_notes = (txn.payment_placeholder_notes or '').strip()
                if capture_note not in existing_payment_notes:
                    txn.payment_placeholder_notes = f'{existing_payment_notes}\n{capture_note}'.strip()

            should_collect_deposit_now = (
                txn.deposit > 0
                and self._can_collect_deposit(txn)
                and txn.deposit_collection_status != txn.COLLECT_SUCCESS
            )
            if should_collect_deposit_now:
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.deposit_collection_requested_at = timezone.now()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'checkout_condition_video_url',
                    'checkout_borrower_confirmed',
                    'checkout_borrower_video_url',
                    'checkout_handover_pin',
                    'checkout_handover_pin_generated_at',
                    'checkout_handover_verified_at',
                    'product_status',
                    'payment_collected_placeholder',
                    'payment_status',
                    'payment_collection_requested_at',
                    'payment_collection_reference',
                    'deposit_status',
                    'payment_placeholder_notes',
                    'deposit_collection_status',
                    'deposit_collection_requested_at',
                    'amended',
                ])
            else:
                txn.save()
            self._system_message(
                txn,
                txn.user_passive,
                txn.user_aggressive,
                f'Checkout evidence submitted {txn.transaction_reference}',
                'Lender submitted rental-start evidence. Borrower should confirm or submit counter-evidence.',
            )
            if should_collect_deposit_now:
                async_collect_deposit_hold.delay(transaction_id=txn.id)
            return Response({'status': 'ok', 'message': 'Rental started and checkout evidence submitted.'})

        if action == 'confirm_checkout_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            if not txn.checkout_condition_video_url:
                raise ValidationError('Lender checkout evidence is missing.')
            txn.checkout_borrower_confirmed = True
            update_fields = ['checkout_borrower_confirmed', 'amended']
            if self._is_rental_payment_collected(txn) and self._is_deposit_funds_held(txn) and not txn.checkout_handover_pin:
                txn.checkout_handover_pin = _generate_txn_pin(6)
                txn.checkout_handover_pin_generated_at = timezone.now()
                update_fields.extend(['checkout_handover_pin', 'checkout_handover_pin_generated_at'])
            txn.save(update_fields=update_fields)
            if not self._is_rental_payment_collected(txn):
                return Response({'status': 'ok', 'message': 'Checkout evidence confirmed, but PIN is blocked until rental payment is captured.'})
            if not self._is_deposit_funds_held(txn):
                return Response({'status': 'ok', 'message': 'Checkout evidence confirmed, but PIN is blocked until deposit funds are held.'})
            return Response({'status': 'ok', 'message': 'Checkout evidence confirmed.'})

        if action == 'submit_checkout_borrower_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            borrower_video = (data.get('checkout_borrower_video_url') or '').strip()
            if not borrower_video:
                borrower_video = uploaded_video_url(
                    'Borrower checkout counter-evidence',
                    'Borrower submitted checkout counter-evidence. Lender should review and complete handover PIN verification.',
                )
            if not borrower_video:
                raise ValidationError('checkout_borrower_video_url is required.')
            txn.checkout_borrower_video_url = borrower_video
            txn.checkout_borrower_confirmed = False
            update_fields = ['checkout_borrower_video_url', 'checkout_borrower_confirmed', 'amended']
            if self._is_rental_payment_collected(txn) and self._is_deposit_funds_held(txn) and not txn.checkout_handover_pin:
                txn.checkout_handover_pin = _generate_txn_pin(6)
                txn.checkout_handover_pin_generated_at = timezone.now()
                update_fields.extend(['checkout_handover_pin', 'checkout_handover_pin_generated_at'])
            txn.save(update_fields=update_fields)
            if not self._is_rental_payment_collected(txn):
                return Response({'status': 'ok', 'message': 'Borrower checkout counter-evidence submitted, but PIN is blocked until rental payment is captured.'})
            if not self._is_deposit_funds_held(txn):
                return Response({'status': 'ok', 'message': 'Borrower checkout counter-evidence submitted, but PIN is blocked until deposit funds are held.'})
            return Response({'status': 'ok', 'message': 'Borrower checkout counter-evidence submitted.'})

        if action == 'verify_checkout_handover_pin' and is_lender and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            pin = (data.get('pin') or '').strip()
            if not pin:
                code_type, qr_pin = _parse_qr_payload(data.get('qr_payload'))
                if code_type == 'CHECKOUT_PIN':
                    pin = qr_pin
            if not self._is_rental_payment_collected(txn):
                raise ValidationError('Rental payment must be captured before handover verification.')
            if not self._is_deposit_funds_held(txn):
                raise ValidationError('Deposit funds must be held before handover verification.')
            if not txn.checkout_handover_pin:
                raise ValidationError('Checkout handover PIN is not generated yet.')
            if pin != txn.checkout_handover_pin:
                raise ValidationError('Invalid checkout handover PIN.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_ONGOING
            txn.checkout_handover_verified_at = timezone.now()
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'checkout_handover_verified_at', 'amended'])
            notify_counterparty(
                f'Rental handover verified {txn.transaction_reference}',
                'Handover was verified and the rental is now ongoing.',
            )
            return Response({'status': 'ok', 'message': 'Checkout handover verified. Rental is now ongoing.'})

        if action == 'submit_return_borrower_evidence' and is_renter and txn.transaction_status in (
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        ):
            return_video = (data.get('return_video_url') or '').strip()
            if not return_video:
                return_video = uploaded_video_url(
                    'Borrower return evidence',
                    'Borrower submitted return evidence. Lender should confirm or submit counter-evidence.',
                )
            if not return_video:
                raise ValidationError('return_video_url is required.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
            txn.return_condition_video_url = return_video
            txn.return_borrower_video_url = return_video
            txn.return_lender_confirmed = False
            txn.return_lender_video_url = ''
            txn.return_handover_pin = ''
            txn.return_handover_pin_generated_at = None
            txn.return_handover_verified_at = None
            txn.product_status = txn.RETURN_VIDEO_ADDED
            txn.save()
            if txn.prev_transaction_status != txn.transaction_status:
                notify_counterparty(
                    f'Return started {txn.transaction_reference}',
                    'The borrower started the return process and submitted return evidence.',
                )
            return Response({'status': 'ok', 'message': 'Return evidence submitted by borrower.'})

        if action == 'confirm_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            if not txn.return_borrower_video_url:
                raise ValidationError('Borrower return evidence is required first.')
            if not txn.return_handover_pin:
                txn.return_handover_pin = _generate_txn_pin(6)
                txn.return_handover_pin_generated_at = timezone.now()
            txn.return_lender_confirmed = True
            txn.save(update_fields=['return_handover_pin', 'return_handover_pin_generated_at', 'return_lender_confirmed', 'amended'])
            return Response({'status': 'ok', 'message': 'Return evidence confirmed. Return verification code generated.'})

        if action == 'submit_lender_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            lender_video = (data.get('lender_return_video_url') or '').strip()
            if not lender_video:
                lender_video = uploaded_video_url(
                    'Lender return counter-evidence',
                    'Lender submitted return counter-evidence.',
                )
            if not lender_video:
                raise ValidationError('lender_return_video_url is required.')
            if not txn.return_handover_pin:
                txn.return_handover_pin = _generate_txn_pin(6)
                txn.return_handover_pin_generated_at = timezone.now()
            txn.return_lender_video_url = lender_video
            txn.return_lender_confirmed = False
            txn.save(update_fields=['return_handover_pin', 'return_handover_pin_generated_at', 'return_lender_video_url', 'return_lender_confirmed', 'amended'])
            return Response({'status': 'ok', 'message': 'Lender return counter-evidence submitted.'})

        if action == 'verify_return_handover_pin' and is_renter and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            pin = (data.get('pin') or '').strip()
            if not pin:
                code_type, qr_pin = _parse_qr_payload(data.get('qr_payload'))
                if code_type == 'RETURN_PIN':
                    pin = qr_pin
            if not txn.return_handover_pin:
                raise ValidationError('Return handover PIN is not available yet.')
            if pin != txn.return_handover_pin:
                raise ValidationError('Invalid return handover PIN.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_PENDING
            txn.return_handover_verified_at = timezone.now()
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'return_handover_verified_at', 'amended'])
            notify_counterparty(
                f'Return verified {txn.transaction_reference}',
                'Return handover was verified. Deposit resolution can now begin.',
            )
            return Response({'status': 'ok', 'message': 'Return handover verified.'})

        if action == 'propose_deposit_return' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
        ):
            proposed_amount = _parse_amount(data.get('deposit_proposed_return_amount'))
            notes = (data.get('deposit_resolution_notes') or '').strip()
            iterations = deposit_proposal_iterations()
            if proposed_amount is None:
                raise ValidationError('deposit_proposed_return_amount is required.')
            if proposed_amount < 0 or proposed_amount > txn.deposit:
                raise ValidationError('Proposed amount must be between 0 and deposit value.')
            if proposed_amount < txn.deposit and not notes:
                raise ValidationError('deposit_resolution_notes is required when returning less than the full deposit.')
            if iterations >= 5:
                raise ValidationError('Maximum deposit proposal iterations reached (5). Raise dispute to continue; disputes may incur a fee.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_PENDING
            txn.deposit_status = txn.DEPOSIT_PENDING
            txn.deposit_proposed_return_amount = proposed_amount
            txn.deposit_proposed_by_lender_at = timezone.now()
            txn.deposit_proposal_accepted_at = None
            txn.deposit_proposal_iteration_count = iterations + 1
            txn.deposit_resolution_notes = notes
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'deposit_status',
                'deposit_proposed_return_amount',
                'deposit_proposed_by_lender_at',
                'deposit_proposal_accepted_at',
                'deposit_proposal_iteration_count',
                'deposit_resolution_notes',
                'amended',
            ])
            notify_counterparty(
                f'Deposit proposal updated {txn.transaction_reference}',
                f'The lender proposed returning {proposed_amount:.2f} from the deposit.',
            )
            next_iteration = iterations + 1
            warning = deposit_iteration_warning(next_iteration)
            if warning:
                return Response({'status': 'ok', 'message': f'Deposit proposal saved: {proposed_amount:.2f}. {warning}'})
            return Response({'status': 'ok', 'message': f'Deposit proposal saved: {proposed_amount:.2f}. Iteration {next_iteration}/5.'})

        if action == 'agree_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            if txn.deposit_proposed_by_lender_at is None:
                raise ValidationError('No lender proposal to accept yet.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.AWAITING_FEEDBACK
            refresh_feedback_deadline()
            txn.deposit_status = txn.DEPOSIT_RETURNED_FULL if abs(txn.deposit_proposed_return_amount - txn.deposit) < 0.01 else txn.DEPOSIT_RETURNED_REDUCED
            txn.deposit_proposal_accepted_at = timezone.now()
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'feedback_window_expires_at', 'deposit_status', 'deposit_proposal_accepted_at', 'amended'])
            notify_counterparty(
                f'Deposit proposal accepted {txn.transaction_reference}',
                'The renter accepted the deposit return proposal.',
            )
            async_resolve_deposit_hold.delay(
                transaction_id=txn.id,
                return_amount=txn.deposit_proposed_return_amount,
            )
            return Response({'status': 'ok', 'message': 'Deposit proposal accepted.'})

        if action == 'contest_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            notes = (data.get('deposit_resolution_notes') or '').strip()
            iterations = deposit_proposal_iterations()
            if not notes:
                raise ValidationError('deposit_resolution_notes is required when contesting.')
            if iterations >= 5:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_proposal_contested_at = timezone.now()
                txn.deposit_resolution_notes = notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposal_contested_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                notify_counterparty(
                    f'Deposit dispute auto-escalated {txn.transaction_reference}',
                    'Maximum proposal iterations reached (5). Deposit dispute auto-escalated to admin review.',
                )
                return Response({'status': 'ok', 'message': 'Max proposal iterations reached. Dispute auto-escalated and may incur a fee.'})
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_CONTESTED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_proposal_contested_at = timezone.now()
            txn.deposit_resolution_notes = notes
            txn.save()
            notify_counterparty(
                f'Deposit proposal contested {txn.transaction_reference}',
                'The renter contested the deposit return proposal.',
            )
            return Response({'status': 'ok', 'message': 'Deposit proposal contested.'})

        if action == 'raise_deposit_dispute_admin' and (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            notes = (data.get('deposit_resolution_notes') or '').strip()
            if not notes:
                raise ValidationError('deposit_resolution_notes is required for admin dispute escalation.')
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.DISPUTE_REQUESTED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = notes
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'deposit_status', 'deposit_resolution_notes', 'amended'])
            notify_counterparty(
                f'Deposit dispute raised {txn.transaction_reference}',
                'The transaction has been escalated for deposit dispute review.',
            )
            return Response({'status': 'ok', 'message': 'Deposit dispute raised to admin.'})

        if action == 'secure_dispute_funds' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            if txn.deposit_collection_status == txn.COLLECT_SUCCESS:
                return Response({'status': 'ok', 'message': 'Deposit funds already secured.'})
            if not self._can_collect_deposit(txn):
                raise ValidationError('Deposit cannot be secured yet.')
            async_collect_deposit_hold.delay(transaction_id=txn.id)
            txn.deposit_collection_status = txn.COLLECT_NOT_RUN
            txn.deposit_collection_requested_at = timezone.now()
            txn.save(update_fields=['deposit_collection_status', 'deposit_collection_requested_at', 'amended'])
            return Response({'status': 'ok', 'message': 'Deposit securing initiated.'})

        if action == 'submit_feedback' and (
            (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_RETURNED,
            txn.AWAITING_FEEDBACK,
            txn.FEEDBACK_ONE_SIDED,
            txn.RENTAL_PROCESS_COMPLETED,
            )
            or (is_renter and txn.transaction_status == txn.CANCEL_ACCEPTED and is_missing_rental_voided())
        ):
            communication_rating = data.get('communication_rating')
            delivery_rating = data.get('delivery_return_rating')
            overall_rating = data.get('overall_rating')
            feedback_comment = (data.get('feedback_comment') or '').strip()
            if communication_rating is None or delivery_rating is None or overall_rating is None:
                raise ValidationError('communication_rating, delivery_return_rating and overall_rating are required.')

            if txn.transaction_status == txn.CANCEL_ACCEPTED and is_missing_rental_voided() and not is_renter:
                raise ValidationError('Only borrower can leave feedback for voided missing-rental transactions.')

            left_for = txn.user_aggressive if is_lender else txn.user_passive
            feedback_obj, created = TransactionFeedback.objects.get_or_create(
                transaction=txn,
                left_by=request.user,
                left_for=left_for,
                defaults={
                    'rating': overall_rating,
                    'communication_rating': communication_rating,
                    'delivery_return_rating': delivery_rating,
                    'overall_rating': overall_rating,
                    'comment': feedback_comment,
                    'is_negative': overall_rating <= 2,
                },
            )
            if not created:
                feedback_obj.rating = overall_rating
                feedback_obj.communication_rating = communication_rating
                feedback_obj.delivery_return_rating = delivery_rating
                feedback_obj.overall_rating = overall_rating
                feedback_obj.comment = feedback_comment
                feedback_obj.is_negative = overall_rating <= 2
                feedback_obj.save()

            other_user = txn.user_passive if request.user == txn.user_aggressive else txn.user_aggressive
            other_feedback_exists = TransactionFeedback.objects.filter(
                transaction=txn,
                left_by=other_user,
                left_for=request.user,
            ).exists()
            if txn.transaction_status == txn.CANCEL_ACCEPTED and is_missing_rental_voided():
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.FEEDBACK_ONE_SIDED
                refresh_feedback_deadline()
                txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'feedback_window_expires_at', 'amended'])
                notify_counterparty(
                    f'Borrower feedback submitted {txn.transaction_reference}',
                    'Borrower submitted final feedback for missing-rental voided transaction.',
                )
                return Response({'status': 'ok', 'message': 'Feedback submitted.'})

            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_PROCESS_COMPLETED if other_feedback_exists else txn.FEEDBACK_ONE_SIDED
            if other_feedback_exists:
                txn.feedback_window_expires_at = None
            else:
                refresh_feedback_deadline()
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'feedback_window_expires_at', 'amended'])
            notify_counterparty(
                f'Feedback received {txn.transaction_reference}',
                'The other party left feedback on this transaction.',
            )
            return Response({'status': 'ok', 'message': 'Feedback submitted.'})

        raise ValidationError('Action is not available for the current transaction state or role.')
