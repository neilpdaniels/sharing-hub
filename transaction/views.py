from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from .forms import OrderEditForm, OrderExpireForm
from .forms import OrderAddForm, OrderImageForm, LetPriceBandFormSet, RentalEnquiryForm
from .forms import TransactionMessageImageForm, TransactionMessageAddForm
from django.contrib.auth.decorators import login_required
from common.models import Order, Product, OrderImage, TransactionFee, OrderBlockedDate
from .models import Transaction, TransactionMessage, TransactionMessageImage, TransactionCharge, TransactionImage, TransactionFeedback
from django.contrib import messages
from datetime import datetime, timedelta, time as dt_time
from django.urls import reverse
from django.http import JsonResponse
from django.views import View
from common.decorators import ajax_required
import logging
from django.conf import settings
from operator import attrgetter
from django.utils import timezone
import common.helpers
from .helpers import (
    returnFeeValue,
    getTransactionStepAndAction,
    get_user_feedback_breakdown_map,
)
import os
import json
import random
from django.core.files import File
from account.models import Profile
from urllib.parse import quote
from django.views.decorators.csrf import csrf_exempt
import urllib.request
import urllib.parse

from account.models import PaymentMethod

from .stripe_connect import stripe_connect_service

def _verify_turnstile(token, remote_ip=''):
    """Verify Cloudflare Turnstile token."""
    turnstile_secret = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', None)
    if not turnstile_secret:
        return True  # Skip validation if secret key not configured

    try:
        payload = urllib.parse.urlencode({
            'secret': turnstile_secret,
            'response': token,
            'remoteip': remote_ip,
        }).encode()
        req = urllib.request.Request(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=payload,
        )
        result = json.loads(urllib.request.urlopen(req, timeout=5).read())
        return result.get('success', False)
    except Exception as e:
        logging.error(f'Turnstile verification error: {e}')
        return False
from .tasks import (
    async_setup_deposit_card_and_test_hold,
    async_collect_deposit_hold,
)


def _generate_txn_pin(length=6):
    digits = '0123456789'
    return ''.join(digits[random.randrange(0, 10)] for _ in range(length))


def _require_mobile_verification(request):
    if not getattr(settings, 'MOBILE_VERIFICATION_ENABLED', True):
        return None
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, 'Please complete your profile before continuing.')
        return redirect(reverse('edit'))
    if profile.mobile_verified:
        return None
    verify_url = reverse('mobile_verify')
    next_url = request.get_full_path()
    messages.warning(request, 'Please verify your mobile number before placing a listing or sending an enquiry.')
    return redirect(f'{verify_url}?next={quote(next_url)}')


def _is_profile_kyc_verified(profile):
    """Determine whether a profile satisfies current KYC requirements."""
    stripe_verified = getattr(profile, 'stripe_identity_verified', False)
    baseline_verified = (
        profile.email_confirmed
        and profile.mobile_verified
        and profile.address_verified
    )
    return bool(stripe_verified or baseline_verified)


@login_required
def add_order(request, product_id=None):
    verify_redirect = _require_mobile_verification(request)
    if verify_redirect is not None:
        return verify_redirect

    product = None
    order = Order()
    order_image_form = None

    # submitted
    if request.method == 'POST':
        product = get_object_or_404(Product, id=request.POST['product_id'])

        order_form = OrderAddForm(data=request.POST, files=request.FILES, instance=order)
        band_formset = LetPriceBandFormSet(data=request.POST, instance=order)

        if order_form.is_valid() and band_formset.is_valid():
            order = order_form.save(commit=False)
            order.user = request.user
            order.product_id = request.POST['product_id']
            order.direction = Order.TO_LET
            order.quantity = 1
            order.status = Order.ACTIVE
            # expiry_date comes in as a date — set to end of that day
            from datetime import datetime, time
            expiry_date = order_form.cleaned_data['expiry_date']
            order.expiry_date = datetime.combine(expiry_date, time(23, 59, 59))
            order.save()

            band_formset.instance = order
            band_formset.save()

            # Save blocked dates from calendar
            blocked_raw = request.POST.get('blocked_dates', '')
            blocked_handover_raw = request.POST.get('blocked_handover_dates', '')
            if blocked_raw:
                import datetime
                for ds in blocked_raw.split(','):
                    ds = ds.strip()
                    if ds:
                        try:
                            d = datetime.date.fromisoformat(ds)
                            OrderBlockedDate.objects.get_or_create(
                                order=order, date=d,
                                defaults={'reason': OrderBlockedDate.MANUAL}
                            )
                        except ValueError:
                            pass
            if blocked_handover_raw:
                import datetime
                for ds in blocked_handover_raw.split(','):
                    ds = ds.strip()
                    if ds:
                        try:
                            d = datetime.date.fromisoformat(ds)
                            if not OrderBlockedDate.objects.filter(order=order, date=d, reason=OrderBlockedDate.BOOKED).exists() \
                               and not OrderBlockedDate.objects.filter(order=order, date=d, reason=OrderBlockedDate.MANUAL).exists():
                                OrderBlockedDate.objects.get_or_create(
                                    order=order,
                                    date=d,
                                    defaults={'reason': OrderBlockedDate.HANDOVER_UNAVAILABLE},
                                )
                        except ValueError:
                            pass

            orderImage_ids = request.POST['order_image_id'].split()
            main_image_id = request.POST.get('main_image_id', '').strip()
            count = len(order.images.filter(active=True))
            for orderImage_id in orderImage_ids:
                try:
                    orderImage = OrderImage.objects.get(pk=orderImage_id)
                    if request.user == orderImage.user:
                        if count < 5:
                            orderImage.order = order
                            orderImage.is_main = (str(orderImage_id) == main_image_id)
                            orderImage.saveNoImageModification()
                            count += 1
                except OrderImage.DoesNotExist:
                    raise Http404("OrderImage does not exist")
            # If no main was explicitly chosen, mark the first image as main
            if not main_image_id:
                first = order.images.filter(active=True).first()
                if first:
                    first.is_main = True
                    first.saveNoImageModification()

            messages.success(request, 'Your listing has been added')
            product_url = request.build_absolute_uri(
                reverse('navigation:productPage', kwargs={'product_slug': product.slug})
            )
            return redirect(product_url)
    else:
        product = get_object_or_404(Product, id=product_id)
        order_form = OrderAddForm(instance=order)
        band_formset = LetPriceBandFormSet(instance=order)
        order_image_form = OrderImageForm(instance=order)

    context = {
        'order_form': order_form,
        'band_formset': band_formset,
        'order_image_form': order_image_form,
        'product': product,
        'blocked_dates_json': '[]',
        'booked_dates_json': '[]',
        'blocked_handover_dates_json': '[]',
    }
    return render(request, 'transaction/add_order.html', context)


@login_required
def edit_order(request, order_id=None):
    order = get_object_or_404(Order, id=order_id)
    if request.user != order.user:
        messages.error(request, 'Incorrect user credentials')
        return redirect('/')

    order_image_form = None

    if request.method == 'POST':
        order_form = OrderAddForm(data=request.POST, files=request.FILES, instance=order)
        band_formset = LetPriceBandFormSet(data=request.POST, instance=order)

        if order_form.is_valid() and band_formset.is_valid():
            order = order_form.save(commit=False)
            order.user = request.user
            order.product = order.product
            order.direction = Order.TO_LET
            order.quantity = 1
            order.status = Order.ACTIVE

            # expiry_date comes in as a date — set to end of that day
            from datetime import datetime, time
            expiry_date = order_form.cleaned_data['expiry_date']
            order.expiry_date = datetime.combine(expiry_date, time(23, 59, 59))
            order.save()

            band_formset.instance = order
            band_formset.save()

            # Replace manually blocked dates from calendar selections.
            OrderBlockedDate.objects.filter(
                order=order,
                reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.HANDOVER_UNAVAILABLE],
            ).delete()
            blocked_raw = request.POST.get('blocked_dates', '')
            blocked_handover_raw = request.POST.get('blocked_handover_dates', '')
            if blocked_raw:
                import datetime
                for ds in blocked_raw.split(','):
                    ds = ds.strip()
                    if ds:
                        try:
                            d = datetime.date.fromisoformat(ds)
                            OrderBlockedDate.objects.get_or_create(
                                order=order,
                                date=d,
                                defaults={'reason': OrderBlockedDate.MANUAL},
                            )
                        except ValueError:
                            pass
            if blocked_handover_raw:
                import datetime
                for ds in blocked_handover_raw.split(','):
                    ds = ds.strip()
                    if ds:
                        try:
                            d = datetime.date.fromisoformat(ds)
                            if not OrderBlockedDate.objects.filter(order=order, date=d, reason=OrderBlockedDate.BOOKED).exists() \
                               and not OrderBlockedDate.objects.filter(order=order, date=d, reason=OrderBlockedDate.MANUAL).exists():
                                OrderBlockedDate.objects.get_or_create(
                                    order=order,
                                    date=d,
                                    defaults={'reason': OrderBlockedDate.HANDOVER_UNAVAILABLE},
                                )
                        except ValueError:
                            pass

            # Sync selected images (max 5) and main image.
            selected_ids = []
            order_image_ids_raw = request.POST.get('order_image_id', '')
            for oid in order_image_ids_raw.split():
                if oid not in selected_ids:
                    selected_ids.append(oid)
            selected_ids = selected_ids[:5]
            main_image_id = request.POST.get('main_image_id', '').strip()

            for img in order.images.filter(active=True):
                if str(img.id) not in selected_ids:
                    img.active = False
                    img.is_main = False
                    img.saveNoImageModification()

            for order_image_id in selected_ids:
                try:
                    order_image = OrderImage.objects.get(pk=order_image_id)
                    if request.user == order_image.user:
                        order_image.order = order
                        order_image.active = True
                        order_image.is_main = (str(order_image_id) == main_image_id)
                        order_image.saveNoImageModification()
                except OrderImage.DoesNotExist:
                    raise Http404('OrderImage does not exist')

            if not main_image_id:
                first = order.images.filter(active=True).first()
                if first:
                    first.is_main = True
                    first.saveNoImageModification()

            messages.success(request, 'Order updated')
            product_url = request.build_absolute_uri(
                reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})
            )
            return redirect(product_url)
    else:
        order_form = OrderAddForm(instance=order)
        band_formset = LetPriceBandFormSet(instance=order)
        order_image_form = OrderImageForm(instance=order)

    order_images = list(order.images.filter(active=True))
    order_image_ids_str = ' '.join(str(img.id) for img in order_images)
    main_image = next((img for img in order_images if img.is_main), None)
    if not main_image and order_images:
        main_image = order_images[0]
    manual_blocked_dates = [
        bd.date.isoformat()
        for bd in order.blocked_dates.filter(reason=OrderBlockedDate.MANUAL)
    ]
    booked_dates = [
        bd.date.isoformat()
        for bd in order.blocked_dates.filter(reason=OrderBlockedDate.BOOKED)
    ]
    blocked_handover_dates = [
        bd.date.isoformat()
        for bd in order.blocked_dates.filter(reason=OrderBlockedDate.HANDOVER_UNAVAILABLE)
    ]

    context = {
        'order_form': order_form,
        'band_formset': band_formset,
        'order_image_form': order_image_form,
        'product': order.product,
        'order': order,
        'edit_mode': True,
        'existing_order_images': order_images,
        'order_image_ids_str': order_image_ids_str,
        'main_image_id': str(main_image.id) if main_image else '',
        'blocked_dates_json': json.dumps(manual_blocked_dates),
        'booked_dates_json': json.dumps(booked_dates),
        'blocked_handover_dates_json': json.dumps(blocked_handover_dates),
    }
    return render(request, 'transaction/add_order.html', context)


@login_required
def expire_order(request, order_id=None, next=None):
    # submitted
    order = None
    if request.method=='POST':
        #if request.user == instance.user
        order = get_object_or_404(Order, id=request.POST['order_id'])
        order_form = OrderExpireForm(instance=order,
                                        data=request.POST)
                                        # files=request.FILES)
        if request.user == order.user:
            if order_form.is_valid():
                order.expiry_date = timezone.now()
                order.status = order.EXPIRED
                # product = get_object_or_404(Product, id=order.id)
                order_form.save()
                messages.success(request, 'Order expired')

                product_url = request.build_absolute_uri(reverse('navigation:productPage' ,
                     kwargs={'product_slug': order.product.slug}))

                return redirect(product_url)
            else:
                messages.error(request, 'Error in validation')
        else:
            messages.error(request, 'Incorrect user credentials')
            return redirect('/')
    else:
        # order_form = OrderEditForm(instance=request.order_id)
        order = get_object_or_404(Order, id=order_id)
        if request.user == order.user:
            order_form = OrderExpireForm(instance=order)
        else:
            messages.error(request, 'Incorrect user credentials')
            return redirect('/')
    context = {
        'order_form' : order_form,
        'order' : order,
        'next' : next,
        'back_url': request.META.get('HTTP_REFERER', '/'),
    }
    return render(request, 'transaction/expire_order.html', context)

class OrderImageUpload(View):
    def post(self, request):
        data = {'is_valid': False}
        form = OrderImageForm(self.request.POST, self.request.FILES)
        if form.is_valid() and request.user is not None:
            image = form.save(commit=False)
            image.user = request.user
            image.save()
            data = {'is_valid': True, 'order_image_id': image.id ,
                    'image_name': image.image.name, 
                    'image_url': image.image.url}
        else:
            data = {'is_valid': False}
        return JsonResponse(data)


@login_required
@ajax_required
def remove_order_image(request):
    status = 'NOK'
    order_id = request.GET.get('order_id', None)
    image_id = request.GET.get('image_id', None)
    order = get_object_or_404(Order, id=order_id)
    if request.user == order.user:
        orderImage = get_object_or_404(OrderImage, id=image_id)
        if orderImage.order == order:
            orderImage.active = False
            orderImage.save()
            status = 'OK'
            logging.error("blah lbal blah")
    content = {
        'status' : status
    }
    return JsonResponse(content)

@login_required
@ajax_required
def get_fee(request):
    fee_slug = request.POST.get('fee_slug', None)
    fee = get_object_or_404(TransactionFee, slug=fee_slug)
    qty = int(request.POST.get('quantity', None))
    order_required_price = float(request.POST.get('order_required_price', None))
    order_id = request.POST.get('order_id', None)
    order = get_object_or_404(Order, id=order_id)
    price_calculated = returnFeeValue(fee, qty, order_required_price, order)
    content = {
        'status' : 'OK',
        'price_calculated': price_calculated,
    }
    return JsonResponse(content)

@login_required
def hit_order(request, order_id=None):
    verify_redirect = _require_mobile_verification(request)
    if verify_redirect is not None:
        return verify_redirect

    order = get_object_or_404(Order, id=order_id)
    manual_blocked_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.MANUAL).values_list('date', flat=True)
    )
    booked_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.BOOKED).values_list('date', flat=True)
    )
    blocked_dates = set(manual_blocked_dates) | set(booked_dates)
    handover_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.HANDOVER_UNAVAILABLE).values_list('date', flat=True)
    )

    def _price_per_day_for_days(rental_days):
        bands = list(order.price_bands.all().order_by('duration_days'))
        for band in bands:
            if rental_days <= int(band.duration_days):
                return float(band.price_per_day)
        return float(order.price)

    if request.user == order.user:
        messages.error(request, "You can't rent your own listing")
        return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

    if request.method == 'POST':
        order_hit_form = RentalEnquiryForm(
            data=request.POST,
            blocked_dates=blocked_dates,
            handover_dates=handover_dates,
            expiry_date=order.expiry_date.date() if order.expiry_date else None,
            max_rental_days=order.max_rental_days,
        )
        if order_hit_form.is_valid():
            turnstile_token = request.POST.get('cf-turnstile-response', '')
            if not _verify_turnstile(turnstile_token, request.META.get('REMOTE_ADDR', '')):
                messages.error(request, 'Human verification failed. Please try again.')
                # Re-render form without proceeding
                context = {
                    'order': order,
                    'order_hit_form': order_hit_form,
                    'captcha_error': 'Human verification failed',
                    'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
                }
                return render(request, 'transaction/hit_order.html', context)

            if order.expiry_date <= timezone.now() or order.status != Order.ACTIVE:
                messages.error(request, 'This listing is no longer available.')
                return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

            start_date = order_hit_form.cleaned_data['rental_start_date']
            end_date = order_hit_form.cleaned_data['rental_end_date']
            rental_days = (end_date - start_date).days + 1
            price_per_day = _price_per_day_for_days(rental_days)

            # Validate rental length for high deposits
            product = order.product
            deposit = getattr(order, 'deposit', 0) or 0  # Get deposit from price band if available
            
            if deposit > 100 and rental_days > 5:
                messages.error(
                    request, 
                    f'Rentals with deposits over £100 are limited to 5 days maximum. '
                    f'Your requested rental is {rental_days} days. Please adjust your dates. '
                    f'(Deposit will be taken and returned at the end for longer rentals.)'
                )
                return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

            txn = Transaction.objects.create(
                price=price_per_day,
                quantity=1,
                order_passive=order,
                order_passive_description=order.description,
                product=order.product,
                user_aggressive=request.user,
                user_passive=order.user,
                current_spot_value=0,
                price_as_pct_spot_value=0,
                transaction_status=Transaction.RENTAL_ENQUIRY,
                prev_transaction_status=Transaction.RENTAL_ENQUIRY,
                payment_status=Transaction.PAYMENT_PENDING,
                deposit_status=Transaction.DEPOSIT_PENDING,
                product_status=Transaction.CONDITION_PENDING,
                rental_start_date=start_date,
                rental_end_date=end_date,
                enquiry_message=order_hit_form.cleaned_data.get('enquiry_message', ''),
            )
            
            # Calculate deposit handling based on rental length and amount
            txn.deposit_handling = txn.calculate_deposit_handling()
            
            # Check if high-risk product and set KYC requirements
            if product.is_high_risk():
                from account.models import Profile
                renter_profile = Profile.objects.get(user=request.user)
                lender_profile = Profile.objects.get(user=order.user)
                
                requires_kyc = False
                kyc_message = f'This is a high-risk product (risk rating: {product.get_effective_risk_rating()}/100). '
                
                # Check if borrower needs KYC
                if not _is_profile_kyc_verified(renter_profile):
                    requires_kyc = True
                    kyc_message += 'As the person who is borrowing, you must complete KYC verification. '
                
                # Check if lender needs KYC
                if not _is_profile_kyc_verified(lender_profile):
                    requires_kyc = True
                    kyc_message += 'The lender must also complete KYC verification before this rental can proceed. '
                
                if requires_kyc:
                    txn.requires_kyc = True
                    txn.requires_kyc_message = kyc_message
            
            txn.save()

            for ord_image in order.images.filter(active=True):
                txn_image = TransactionImage()
                txn_image.image = File(ord_image.image, ord_image.image.name)
                txn_image.transaction = txn
                txn_image.save()

            messages.success(request, 'Rental enquiry sent.')
            return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)
    else:
        order_hit_form = RentalEnquiryForm(
            blocked_dates=blocked_dates,
            handover_dates=handover_dates,
            expiry_date=order.expiry_date.date() if order.expiry_date else None,
            max_rental_days=order.max_rental_days,
        )

    price_bands = list(order.price_bands.all().order_by('duration_days').values('duration_days', 'price_per_day'))
    blocked_dates_json = json.dumps(sorted([d.isoformat() for d in manual_blocked_dates]))
    booked_dates_json = json.dumps(sorted([d.isoformat() for d in booked_dates]))
    handover_dates_json = json.dumps(sorted([d.isoformat() for d in handover_dates]))
    price_bands_json = json.dumps(price_bands)

    context = {
        'order': order,
        'order_hit_form': order_hit_form,
        'blocked_dates_json': blocked_dates_json,
        'booked_dates_json': booked_dates_json,
        'handover_dates_json': handover_dates_json,
        'price_bands_json': price_bands_json,
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
    }
    return render(request, 'transaction/hit_order.html', context)


@login_required
def view_transaction(request, transaction_reference=None):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user:
        raise Http404

    message_turnstile_required = txn.transactionmessage_set.count() > 20

    is_lender = (request.user == txn.user_passive)
    is_renter = (request.user == txn.user_aggressive)
    card_setup_allowed_statuses = (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED)

    def _get_contract_deadline(transaction):
        """Deadline is min(lender confirmation + 24h, rental start datetime)."""
        if not transaction.lender_agreed_at:
            return None

        deadline_24h = transaction.lender_agreed_at + timedelta(hours=24)
        candidates = [deadline_24h]

        if transaction.rental_start_date:
            start_naive = datetime.combine(transaction.rental_start_date, dt_time.min)
            if timezone.is_naive(start_naive):
                start_dt = timezone.make_aware(start_naive, timezone.get_current_timezone())
            else:
                start_dt = start_naive
            candidates.append(start_dt)

        return min(candidates)

    def _can_collect_deposit(transaction):
        if transaction.deposit <= 0:
            return False
        if transaction.deposit_collected_placeholder:
            return False
        if transaction.deposit_card_setup_status != transaction.CARD_READY:
            return False
        if transaction.deposit_test_hold_status != transaction.TEST_HOLD_SUCCESS:
            return False
        if not transaction.rental_start_date:
            return False
        return timezone.now().date() >= transaction.rental_start_date

    def _has_verified_payment_card(transaction):
        payment_card_required = (transaction.deposit > 0 or transaction.price > 0)
        if not payment_card_required:
            return True
        return (
            transaction.deposit_card_setup_status == transaction.CARD_READY
            and transaction.deposit_test_hold_status == transaction.TEST_HOLD_SUCCESS
        )

    def _is_deposit_funds_held(transaction):
        if transaction.deposit <= 0:
            return True
        return bool(
            transaction.deposit_collected_placeholder
            or transaction.deposit_collection_status == transaction.COLLECT_SUCCESS
            or transaction.deposit_status == transaction.DEPOSIT_HELD_PLACEHOLDER
        )

    def _parse_deposit_amount(raw_value):
        try:
            return round(float((raw_value or '').strip()), 2)
        except (TypeError, ValueError):
            return None

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'agree_rental' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_AGREED
            txn.lender_agreement_pending_at = timezone.now()
            txn.save()

            # Block this booked range on the underlying listing as soon as rental is agreed.
            if txn.order_passive and txn.rental_start_date and txn.rental_end_date:
                current_date = txn.rental_start_date
                while current_date <= txn.rental_end_date:
                    OrderBlockedDate.objects.get_or_create(
                        order=txn.order_passive,
                        date=current_date,
                        defaults={'reason': OrderBlockedDate.BOOKED},
                    )
                    current_date += timedelta(days=1)

            messages.success(request, 'Rental agreement generated. Please confirm the contract terms.')

        elif action == 'reject_enquiry' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            messages.info(request, 'Rental enquiry rejected.')

        elif action == 'request_cancellation' and txn.transaction_status == txn.RENTAL_ENQUIRY:
            reason = (request.POST.get('cancellation_reason') or '').strip()
            if not reason:
                messages.error(request, 'Please provide a reason for cancellation.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.CANCEL_ACCEPTED
                txn.transaction_status_raised_by = request.user
                txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
                
                # Notify the other party
                other_user = txn.user_aggressive if request.user == txn.user_passive else txn.user_passive
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=other_user,
                    transaction=txn,
                    subject=f'Transaction Cancelled - {txn.transaction_reference}',
                    description=f"The transaction has been cancelled.\n\nReason: {reason}",
                )
                messages.success(request, 'Transaction cancelled.')

        elif action == 'confirm_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and not txn.lender_agreed_at:
            if not txn.lender_agreement_pending_at:
                txn.lender_agreement_pending_at = timezone.now()
            txn.lender_agreed_at = timezone.now()
            txn.save()
            # Send contract confirmation request to borrower
            contract_msg = f"""Lender has agreed to the rental.

Rental Terms:
- Product: {txn.order_passive.product.name}
- Dates: {txn.rental_start_date} to {txn.rental_end_date}
- Price: £{txn.price}/day
- Deposit: £{txn.deposit}

Please confirm to proceed with this rental. You have 24 hours to confirm, or until the rental start date, whichever is sooner.

Transaction Ref: {txn.transaction_reference}"""
            TransactionMessage.objects.create(
                user_from=txn.user_passive,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Rental Agreement - Please Confirm {txn.transaction_reference}',
                description=contract_msg,
            )
            messages.success(request, 'Contract confirmed. Borrower has been sent a confirmation request.')

        elif action == 'reinitiate_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            contract_deadline = _get_contract_deadline(txn)
            if contract_deadline and timezone.now() <= contract_deadline:
                messages.info(request, 'Borrower still has time to confirm. You can re-send once the window expires.')
            else:
                # Extend the deadline by resetting lender_agreed_at to now
                txn.lender_agreed_at = timezone.now()
                txn.save()
                # Send a fresh confirmation request to borrower
                contract_msg = f"""Lender has re-sent the rental confirmation request.

Rental Terms:
- Product: {txn.order_passive.product.name}
- Dates: {txn.rental_start_date} to {txn.rental_end_date}
- Price: £{txn.price}/day
- Deposit: £{txn.deposit}

Please confirm to proceed with this rental. You have 24 hours to confirm, or until the rental start date, whichever is sooner.

Transaction Ref: {txn.transaction_reference}"""
                TransactionMessage.objects.create(
                    user_from=txn.user_passive,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Rental Agreement - Re-sent (Please Confirm) {txn.transaction_reference}',
                    description=contract_msg,
                )
                messages.success(request, 'Confirmation request re-sent to borrower. 24-hour window restarted.')

        elif action == 'confirm_renter_contract' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            contract_deadline = _get_contract_deadline(txn)
            if contract_deadline and timezone.now() > contract_deadline:
                messages.error(
                    request,
                    'Contract confirmation window has expired. This rental can no longer be confirmed.'
                )
            else:
                txn.renter_agreed_at = timezone.now()
                txn.save()
                messages.success(request, 'Rental confirmed! Proceeding to next stage.')

        elif action == 'reject_rental_agreement' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and not txn.renter_agreed_at:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])

            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_passive,
                transaction=txn,
                subject=f'Rental Agreement Rejected {txn.transaction_reference}',
                description='Borrower has rejected the rental agreement.',
            )
            messages.info(request, 'Rental agreement rejected and the lender has been notified.')

        elif action == 'add_deposit_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            cardholder_name = (request.POST.get('deposit_cardholder_name') or '').strip()
            card_brand = (request.POST.get('deposit_card_brand') or '').strip()
            card_last4 = (request.POST.get('deposit_card_last4') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif not cardholder_name:
                messages.error(request, 'Please enter the cardholder name.')
            elif len(card_last4) != 4 or not card_last4.isdigit():
                messages.error(request, 'Please enter a valid last 4 digits for the card.')
            else:
                # Trigger async task for card setup
                async_setup_deposit_card_and_test_hold.delay(
                    transaction_id=txn.id,
                    cardholder_name=cardholder_name,
                    card_brand=card_brand,
                    card_last4=card_last4,
                )
                # Mark as processing
                txn.deposit_card_setup_status = txn.CARD_NONE
                txn.save()

        elif action == 'use_existing_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif not payment_method_id:
                messages.error(request, 'Please select a payment method.')
            else:
                try:
                    pm = request.user.payment_methods.get(id=payment_method_id)
                    txn.deposit_card_setup_status = txn.CARD_READY
                    txn.deposit_cardholder_name = 'Stripe'
                    txn.deposit_card_brand = pm.card_brand
                    txn.deposit_card_last4 = pm.card_last4
                    txn.deposit_test_hold_status = txn.TEST_HOLD_SUCCESS
                    txn.deposit_test_hold_amount = 0.30
                    txn.deposit_test_hold_at = timezone.now()
                    txn.stripe_setup_intent_id = pm.stripe_setup_intent_id
                    txn.stripe_payment_method_id = pm.stripe_payment_method_id
                    txn.save()
                except PaymentMethod.DoesNotExist:
                    messages.error(request, 'Payment method not found.')

        elif action == 'confirm_stripe_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()
            setup_intent_id = (request.POST.get('setup_intent_id') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif not payment_method_id:
                messages.error(request, 'Card details were not submitted successfully. Please try again.')
            else:
                # Mark as processing and persist submitted Stripe references.
                # Webhook handler will finalize verification status.
                txn.deposit_card_setup_status = txn.CARD_NONE
                txn.deposit_test_hold_status = txn.TEST_HOLD_NOT_RUN
                txn.stripe_setup_intent_id = setup_intent_id
                txn.stripe_payment_method_id = payment_method_id
                txn.save(update_fields=[
                    'deposit_card_setup_status',
                    'deposit_test_hold_status',
                    'stripe_setup_intent_id',
                    'stripe_payment_method_id',
                    'amended',
                ])

        elif action == 'collect_deposit' and is_lender and txn.transaction_status in (
            txn.RENTAL_AGREED, 
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
        ):
            if not _can_collect_deposit(txn):
                messages.error(
                    request,
                    'Deposit cannot be collected yet. Ensure card setup/test hold is complete and rental start date has been reached.'
                )
            else:
                # Trigger async task for deposit collection
                async_collect_deposit_hold.delay(transaction_id=txn.id)
                # Mark as processing
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.save()
                messages.info(
                    request,
                    'Deposit collection in progress. You will receive email confirmation when complete.'
                )

        elif action == 'send_message' and (is_lender or is_renter):
            body = (request.POST.get('message_body') or '').strip()
            image_files = request.FILES.getlist('message_images')
            video_files = request.FILES.getlist('message_videos')
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            if message_turnstile_required:
                turnstile_token = request.POST.get('cf-turnstile-response', '')
                if not _verify_turnstile(turnstile_token, request.META.get('REMOTE_ADDR', '')):
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': 'Human verification failed. Please complete the checkbox and try again.'}, status=400)
                    messages.error(request, 'Human verification failed. Please try again.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not body and not image_files and not video_files:
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': 'Please enter a message or attach at least one file before sending.'}, status=400)
                messages.error(request, 'Please enter a message or attach at least one file before sending.')
            else:
                invalid_video = next((f for f in video_files if not (getattr(f, 'content_type', '') or '').startswith('video/')), None)
                if invalid_video is not None:
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': f'{invalid_video.name} is not a valid video file.'}, status=400)
                    messages.error(request, f'{invalid_video.name} is not a valid video file.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                txn_message = TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=(txn.user_aggressive if is_lender else txn.user_passive),
                    transaction=txn,
                    subject=f'Transaction {txn.transaction_reference}',
                    description=body,
                )

                for idx, image_file in enumerate(image_files):
                    try:
                        TransactionMessageImage.objects.create(
                            txn_message=txn_message,
                            user=request.user,
                            image=image_file,
                            first_image=(idx == 0),
                            active=True,
                        )
                    except ValidationError as e:
                        if is_ajax:
                            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
                        messages.error(request, f'Image upload error: {str(e)}')
                        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                for video_file in video_files:
                    try:
                        # Save video with both display version and raw archive for verification
                        txn_msg_image = TransactionMessageImage(
                            txn_message=txn_message,
                            user=request.user,
                            video=video_file,
                            video_raw=video_file,  # Keep raw copy for verification chain of custody
                            first_image=False,
                            active=True,
                        )
                        txn_msg_image.full_clean()  # Validate before saving
                        txn_msg_image.save()
                    except ValidationError as e:
                        if is_ajax:
                            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
                        messages.error(request, f'Video upload error: {str(e)}')
                        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                attachment_count = len(image_files) + len(video_files)
                if is_ajax:
                    if attachment_count:
                        msg = f'Message sent with {attachment_count} attachment(s).'
                    else:
                        msg = 'Message sent.'
                    return JsonResponse({'ok': True, 'message': msg})
                if attachment_count:
                    messages.info(request, f'Message sent with {attachment_count} attachment(s).')
                else:
                    messages.info(request, 'Message sent.')

        elif action == 'initiate_rental' and is_lender and txn.transaction_status == txn.RENTAL_AGREED:
            if not _has_verified_payment_card(txn):
                messages.error(
                    request,
                    'Rental is due to begin but cannot be initiated until the borrower has provided a payment card and verification hold has succeeded.'
                )
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            checkout_video = request.POST.get('checkout_video_url', '').strip()
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

            payment_collected = bool(request.POST.get('payment_collected_placeholder'))
            txn.payment_collected_placeholder = payment_collected
            txn.payment_status = txn.PAYMENT_CAPTURED_PLACEHOLDER if payment_collected else txn.PAYMENT_PENDING
            txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER if txn.deposit_collected_placeholder else txn.DEPOSIT_PENDING
            txn.payment_placeholder_notes = request.POST.get('payment_placeholder_notes', '').strip()
            txn.save()
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Checkout evidence submitted {txn.transaction_reference}',
                description='Lender submitted rental-start evidence. Borrower should confirm agreement or submit counter-evidence.',
                is_system_generated=True,
            )
            messages.success(request, 'Checkout evidence submitted. Waiting for borrower confirmation/counter-evidence and handover PIN verification.')

        elif action == 'confirm_checkout_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            if not txn.checkout_condition_video_url:
                messages.error(request, 'Lender checkout evidence is missing.')
            else:
                txn.checkout_borrower_confirmed = True
                if _is_deposit_funds_held(txn):
                    if not txn.checkout_handover_pin:
                        txn.checkout_handover_pin = _generate_txn_pin(6)
                        txn.checkout_handover_pin_generated_at = timezone.now()
                    txn.save(update_fields=[
                        'checkout_borrower_confirmed',
                        'checkout_handover_pin',
                        'checkout_handover_pin_generated_at',
                        'amended',
                    ])
                    messages.success(request, 'Checkout evidence confirmed. PIN generated for handover verification.')
                else:
                    txn.save(update_fields=['checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Evidence confirmed, but PIN cannot be generated until deposit funds are held.')

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Checkout evidence confirmed {txn.transaction_reference}',
                    description='Borrower confirmed lender checkout evidence. Complete handover PIN verification to start rental.',
                    is_system_generated=True,
                )

        elif action == 'submit_checkout_borrower_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            borrower_checkout_video = (request.POST.get('checkout_borrower_video_url') or '').strip()
            if not borrower_checkout_video:
                messages.error(request, 'Please provide borrower checkout video evidence URL.')
            else:
                txn.checkout_borrower_video_url = borrower_checkout_video
                txn.checkout_borrower_confirmed = False
                if _is_deposit_funds_held(txn):
                    if not txn.checkout_handover_pin:
                        txn.checkout_handover_pin = _generate_txn_pin(6)
                        txn.checkout_handover_pin_generated_at = timezone.now()
                    txn.save(update_fields=[
                        'checkout_borrower_video_url',
                        'checkout_borrower_confirmed',
                        'checkout_handover_pin',
                        'checkout_handover_pin_generated_at',
                        'amended',
                    ])
                    messages.success(request, 'Counter-evidence submitted. PIN generated for handover verification.')
                else:
                    txn.save(update_fields=['checkout_borrower_video_url', 'checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Counter-evidence saved, but PIN cannot be generated until deposit funds are held.')

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Borrower checkout counter-evidence {txn.transaction_reference}',
                    description='Borrower submitted checkout counter-evidence. Lender should review and complete handover PIN verification.',
                    is_system_generated=True,
                )

        elif action == 'verify_checkout_handover_pin' and is_lender and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            entered_pin = (request.POST.get('checkout_handover_pin') or '').strip()
            if not _is_deposit_funds_held(txn):
                messages.error(request, 'Deposit funds must be held before rental handover PIN verification.')
            elif not txn.checkout_handover_pin:
                messages.error(request, 'Borrower has not reached the PIN step yet.')
            elif entered_pin != txn.checkout_handover_pin:
                messages.error(request, 'Invalid checkout handover PIN. Please try again.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_ONGOING
                txn.checkout_handover_verified_at = timezone.now()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'checkout_handover_verified_at',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Rental handover verified {txn.transaction_reference}',
                    description='Checkout handover PIN verified by lender. Rental is now officially ongoing.',
                    is_system_generated=True,
                )
                messages.success(request, 'Handover verified. You are good to lend - rental is now active.')

        elif action == 'submit_return_borrower_evidence' and is_renter and txn.transaction_status in (
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        ):
            return_video = (request.POST.get('return_video_url') or '').strip()
            if not return_video:
                messages.error(request, 'Please provide borrower return video evidence URL.')
            else:
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
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'return_condition_video_url',
                    'return_borrower_video_url',
                    'return_lender_confirmed',
                    'return_lender_video_url',
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_handover_verified_at',
                    'product_status',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Return evidence submitted {txn.transaction_reference}',
                    description='Borrower has submitted return-day evidence. Lender should confirm agreement or submit counter-evidence.',
                    is_system_generated=True,
                )
                messages.success(request, 'Return evidence submitted. Waiting for lender confirmation/counter-evidence.')

        elif action == 'confirm_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            if not txn.return_borrower_video_url:
                messages.error(request, 'Borrower evidence is required before confirmation.')
            else:
                if not txn.return_handover_pin:
                    txn.return_handover_pin = _generate_txn_pin(6)
                    txn.return_handover_pin_generated_at = timezone.now()
                txn.return_lender_confirmed = True
                txn.save(update_fields=[
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_lender_confirmed',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Return verification code ready {txn.transaction_reference}',
                    description='Lender has reviewed return evidence. Please ask lender for the return verification PIN and submit it to complete return handover.',
                    is_system_generated=True,
                )
                messages.success(request, 'Evidence confirmed. Return PIN generated and ready for borrower verification.')

        elif action == 'submit_lender_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            lender_return_video = (request.POST.get('lender_return_video_url') or '').strip()
            if not lender_return_video:
                messages.error(request, 'Please provide lender return video evidence URL.')
            else:
                if not txn.return_handover_pin:
                    txn.return_handover_pin = _generate_txn_pin(6)
                    txn.return_handover_pin_generated_at = timezone.now()
                txn.return_lender_video_url = lender_return_video
                txn.return_lender_confirmed = False
                txn.save(update_fields=[
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_lender_video_url',
                    'return_lender_confirmed',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Lender counter-evidence submitted {txn.transaction_reference}',
                    description='Lender has submitted return-day counter-evidence. Please review and then submit the return verification PIN to complete handover.',
                    is_system_generated=True,
                )
                messages.warning(request, 'Counter-evidence saved. Return PIN generated for final handover verification.')

        elif action == 'verify_return_handover_pin' and is_renter and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            entered_pin = (request.POST.get('return_handover_pin') or '').strip()
            if not txn.return_handover_pin:
                messages.error(request, 'Lender has not completed return review yet, so no PIN is available.')
            elif entered_pin != txn.return_handover_pin:
                messages.error(request, 'Invalid return verification PIN. Please try again.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_PENDING
                txn.return_handover_verified_at = timezone.now()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'return_handover_verified_at',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Return handover verified {txn.transaction_reference}',
                    description='Borrower completed return PIN verification. Return is confirmed and deposit resolution can now proceed.',
                    is_system_generated=True,
                )
                messages.success(request, 'Return verification complete. Rental marked as returned and ready for deposit resolution.')

        elif action == 'propose_deposit_return' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
        ):
            proposed_amount = _parse_deposit_amount(request.POST.get('deposit_proposed_return_amount'))
            resolution_notes = (request.POST.get('deposit_resolution_notes') or '').strip()

            if proposed_amount is None:
                messages.error(request, 'Please enter a valid deposit return amount.')
            elif proposed_amount < 0:
                messages.error(request, 'Deposit return amount cannot be negative.')
            elif proposed_amount > txn.deposit:
                messages.error(request, 'Deposit return amount cannot exceed the original deposit.')
            else:
                previous_status = txn.transaction_status
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_PENDING
                txn.deposit_status = txn.DEPOSIT_PENDING
                txn.deposit_proposed_return_amount = proposed_amount
                txn.deposit_proposed_by_lender_at = timezone.now()
                txn.deposit_proposal_accepted_at = None
                txn.deposit_resolution_notes = resolution_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposed_return_amount',
                    'deposit_proposed_by_lender_at',
                    'deposit_proposal_accepted_at',
                    'deposit_resolution_notes',
                    'amended',
                ])

                if previous_status == txn.RENTAL_RETURNED_DEPOSIT_CONTESTED:
                    description = (
                        f'Lender updated deposit proposal to £{proposed_amount:.2f}. '
                        'Please review and either agree or contest.'
                    )
                else:
                    description = (
                        f'Lender proposed returning £{proposed_amount:.2f} from deposit. '
                        'Please review and either agree or contest.'
                    )

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Deposit return proposal {txn.transaction_reference}',
                    description=description,
                    is_system_generated=True,
                )
                messages.success(request, f'Deposit proposal sent: £{proposed_amount:.2f}.')

        elif action == 'agree_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            proposed_amount = txn.deposit_proposed_return_amount
            if txn.deposit_proposed_by_lender_at is None:
                messages.error(request, 'There is no lender proposal to accept yet.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.AWAITING_FEEDBACK
                txn.deposit_status = (
                    txn.DEPOSIT_RETURNED_FULL
                    if abs(proposed_amount - txn.deposit) < 0.01
                    else txn.DEPOSIT_RETURNED_REDUCED
                )
                txn.deposit_proposal_accepted_at = timezone.now()
                if not txn.deposit_resolution_notes:
                    txn.deposit_resolution_notes = f'Borrower accepted lender proposal of £{proposed_amount:.2f}.'
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposal_accepted_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Deposit proposal accepted {txn.transaction_reference}',
                    description=f'Borrower accepted deposit return proposal of £{proposed_amount:.2f}.',
                    is_system_generated=True,
                )
                messages.success(request, 'Deposit proposal accepted. Please leave feedback to close the transaction.')

        elif action == 'contest_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            contest_notes = (request.POST.get('deposit_resolution_notes') or '').strip()
            if txn.deposit_proposed_by_lender_at is None:
                messages.error(request, 'There is no lender proposal to contest yet.')
            elif not contest_notes:
                messages.error(request, 'Please add a reason for contesting the proposal.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_CONTESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_proposal_contested_at = timezone.now()
                txn.deposit_resolution_notes = contest_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposal_contested_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Deposit proposal contested {txn.transaction_reference}',
                    description='Borrower contested the lender deposit proposal. Lender can revise proposal or escalate to admin dispute.',
                    is_system_generated=True,
                )
                messages.warning(request, 'Deposit proposal contested. Lender can update proposal or escalate dispute to admin.')

        elif action == 'raise_deposit_dispute_admin' and (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            dispute_notes = (request.POST.get('deposit_resolution_notes') or '').strip()
            if not dispute_notes:
                messages.error(request, 'Please include dispute details for admin review.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_resolution_notes = dispute_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=(txn.user_aggressive if is_lender else txn.user_passive),
                    transaction=txn,
                    subject=f'Deposit dispute raised to admin {txn.transaction_reference}',
                    description='Deposit dispute has been escalated to admin. Further evidence/messages can be added while review is ongoing.',
                    include_admin=True,
                    is_system_generated=True,
                )
                messages.warning(request, 'Deposit dispute raised to admin team.')

        elif action == 'secure_dispute_funds' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            if txn.deposit_collection_status == txn.COLLECT_SUCCESS:
                messages.info(request, 'Deposit funds are already secured.')
            elif not _can_collect_deposit(txn):
                messages.error(request, 'Deposit cannot be secured yet. Verify card setup/hold and rental start timing.')
            else:
                async_collect_deposit_hold.delay(transaction_id=txn.id)
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.deposit_collection_requested_at = timezone.now()
                txn.save(update_fields=['deposit_collection_status', 'deposit_collection_requested_at', 'amended'])
                messages.success(request, 'Deposit securing initiated due to dispute status.')

        elif action == 'deposit_full' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.AWAITING_FEEDBACK
            txn.deposit_status = txn.DEPOSIT_RETURNED_FULL
            txn.deposit_proposed_return_amount = txn.deposit
            txn.deposit_proposed_by_lender_at = timezone.now()
            txn.deposit_proposal_accepted_at = timezone.now()
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.success(request, 'Deposit returned in full. Please leave feedback to close the transaction.')

        elif action == 'deposit_reduced' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            reduced_amount = _parse_deposit_amount(request.POST.get('deposit_proposed_return_amount'))
            if reduced_amount is None:
                reduced_amount = 0
            reduced_amount = max(0, min(reduced_amount, txn.deposit))
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.AWAITING_FEEDBACK
            txn.deposit_status = txn.DEPOSIT_RETURNED_REDUCED
            txn.deposit_proposed_return_amount = reduced_amount
            txn.deposit_proposed_by_lender_at = timezone.now()
            txn.deposit_proposal_accepted_at = timezone.now()
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.success(request, f'Reduced deposit return recorded (£{reduced_amount:.2f}). Please leave feedback to close the transaction.')

        elif action == 'mediation_required' and (is_lender or is_renter) and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_CONTESTED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.warning(request, 'Mediation required has been recorded.')

        elif action == 'submit_feedback' and (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_RETURNED,
            txn.AWAITING_FEEDBACK,
            txn.RENTAL_PROCESS_COMPLETED,
        ):
            communication_rating = request.POST.get('communication_rating', '').strip()
            delivery_return_rating = request.POST.get('delivery_return_rating', '').strip()
            overall_rating = request.POST.get('overall_rating', '').strip()
            feedback_comment = (request.POST.get('feedback_comment') or '').strip()

            try:
                communication_rating = int(communication_rating)
                delivery_return_rating = int(delivery_return_rating)
                overall_rating = int(overall_rating)
            except ValueError:
                messages.error(request, 'Feedback ratings must be whole numbers between 0 and 5.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            ratings = [communication_rating, delivery_return_rating, overall_rating]
            if any(r < 0 or r > 5 for r in ratings):
                messages.error(request, 'All feedback ratings must be between 0 and 5.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            left_for = txn.user_aggressive if is_lender else txn.user_passive
            feedback_obj, created = TransactionFeedback.objects.get_or_create(
                transaction=txn,
                left_by=request.user,
                left_for=left_for,
                defaults={
                    'rating': overall_rating,
                    'communication_rating': communication_rating,
                    'delivery_return_rating': delivery_return_rating,
                    'overall_rating': overall_rating,
                    'comment': feedback_comment,
                    'is_negative': overall_rating <= 2,
                },
            )

            if not created:
                feedback_obj.rating = overall_rating
                feedback_obj.communication_rating = communication_rating
                feedback_obj.delivery_return_rating = delivery_return_rating
                feedback_obj.overall_rating = overall_rating
                feedback_obj.comment = feedback_comment
                feedback_obj.is_negative = (overall_rating <= 2)
                feedback_obj.save(update_fields=[
                    'rating',
                    'communication_rating',
                    'delivery_return_rating',
                    'overall_rating',
                    'comment',
                    'is_negative',
                ])

            other_user = txn.user_passive if request.user == txn.user_aggressive else txn.user_aggressive
            other_feedback_exists = TransactionFeedback.objects.filter(
                transaction=txn,
                left_by=other_user,
                left_for=request.user,
            ).exists()

            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_PROCESS_COMPLETED if other_feedback_exists else txn.AWAITING_FEEDBACK
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'amended'])

            if other_feedback_exists:
                messages.success(request, 'Feedback submitted. Both parties have now completed feedback, and the transaction is closed.')
            else:
                messages.success(request, 'Feedback submitted. Waiting for the other party to submit feedback.')

        else:
            messages.error(request, 'That action is not available for the current state.')

        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

    messages_ = sorted(
        sorted((txn.transactionmessage_set.all()), key=attrgetter('created'), reverse=True),
        key=attrgetter('read_by_user_to')
    )
    charges = txn.transactioncharge_set.all()
    txn_images = txn.transactionimage_set.all()
    total_items = txn.quantity * txn.price
    total_fees = sum(charge.price for charge in charges)
    total_px = total_items + total_fees
    step, next_action = getTransactionStepAndAction(txn, request)
    now_ts = timezone.now()
    today = now_ts.date()
    contract_deadline = _get_contract_deadline(txn)
    contract_seconds_remaining = None
    if contract_deadline:
        contract_seconds_remaining = int((contract_deadline - now_ts).total_seconds())

    can_collect_deposit = _can_collect_deposit(txn)
    has_verified_payment_card = _has_verified_payment_card(txn)
    rental_start_blocked_by_missing_card = (
        is_lender
        and txn.transaction_status == txn.RENTAL_AGREED
        and bool(txn.lender_agreed_at)
        and bool(txn.renter_agreed_at)
        and not has_verified_payment_card
    )

    # Generate Stripe SetupIntent for card collection if needed
    setup_intent_client_secret = None
    setup_intent_id = None
    if (
        is_renter
        and txn.transaction_status in card_setup_allowed_statuses
        and (txn.deposit > 0 or txn.price > 0)
        and txn.deposit_card_setup_status != txn.CARD_READY
        and not txn.deposit_collected_placeholder
    ):
        setup_result = stripe_connect_service.create_setup_intent(transaction=txn)
        if setup_result.get('ok'):
            setup_intent_client_secret = setup_result.get('client_secret')
            setup_intent_id = setup_result.get('setup_intent_id')

    can_setup_deposit_card = (
        is_renter
        and txn.transaction_status in card_setup_allowed_statuses
        and (txn.deposit > 0 or txn.price > 0)
        and not txn.deposit_collected_placeholder
    )

    dispute_statuses = (txn.RENTAL_RETURNED_DEPOSIT_CONTESTED, txn.DISPUTE_REQUESTED)
    dispute_in_progress = txn.transaction_status in dispute_statuses
    dispute_hold_deadline = None
    dispute_hold_seconds_remaining = None
    if txn.deposit_test_hold_at:
        dispute_hold_deadline = txn.deposit_test_hold_at + timedelta(days=7)
        dispute_hold_seconds_remaining = int((dispute_hold_deadline - now_ts).total_seconds())

    urgent_dispute_funds_action = (
        is_lender
        and dispute_in_progress
        and txn.deposit_collection_status != txn.COLLECT_SUCCESS
        and can_collect_deposit
        and dispute_hold_seconds_remaining is not None
        and dispute_hold_seconds_remaining <= (48 * 60 * 60)
    )

    return_review_completed = bool(txn.return_lender_confirmed or txn.return_lender_video_url)
    return_pin_available = bool(txn.return_handover_pin)
    checkout_pin_available = bool(txn.checkout_handover_pin)
    deposit_funds_held = _is_deposit_funds_held(txn)

    feedback_statuses = (
        txn.RENTAL_RETURNED_DEPOSIT_RETURNED,
        txn.AWAITING_FEEDBACK,
        txn.RENTAL_PROCESS_COMPLETED,
    )
    feedback_stage = txn.transaction_status in feedback_statuses
    feedback_left_by_me = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=request.user,
    ).exists()
    feedback_from_lender = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=txn.user_passive,
        left_for=txn.user_aggressive,
    ).first()
    feedback_from_renter = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=txn.user_aggressive,
        left_for=txn.user_passive,
    ).first()
    feedback_prompt_required = feedback_stage and not feedback_left_by_me
    feedback_both_complete = bool(feedback_from_lender and feedback_from_renter)

    user_feedback_breakdowns = get_user_feedback_breakdown_map([
        txn.user_passive_id,
        txn.user_aggressive_id,
    ])
    lender_feedback_stats = user_feedback_breakdowns.get(txn.user_passive_id, {})
    renter_feedback_stats = user_feedback_breakdowns.get(txn.user_aggressive_id, {})

    # Get user's saved payment methods
    user_payment_methods = []
    if is_renter:
        user_payment_methods = request.user.payment_methods.all()

    context = {
        'transaction': txn,
        'charges': charges,
        'messages_': messages_,
        'total_px': total_px,
        'txnImages': txn_images,
        'total_items': total_items,
        'total_fees': total_fees,
        'step': step,
        'next_action': next_action,
        'is_lender': is_lender,
        'is_renter': is_renter,
        'today': today,
        'now_ts': now_ts,
        'contract_deadline': contract_deadline,
        'contract_deadline_iso': contract_deadline.isoformat() if contract_deadline else '',
        'contract_seconds_remaining': contract_seconds_remaining,
        'can_collect_deposit': can_collect_deposit,
        'has_verified_payment_card': has_verified_payment_card,
        'rental_start_blocked_by_missing_card': rental_start_blocked_by_missing_card,
        'setup_intent_client_secret': setup_intent_client_secret,
        'setup_intent_id': setup_intent_id,
        'can_setup_deposit_card': can_setup_deposit_card,
        'dispute_in_progress': dispute_in_progress,
        'dispute_hold_deadline': dispute_hold_deadline,
        'dispute_hold_seconds_remaining': dispute_hold_seconds_remaining,
        'urgent_dispute_funds_action': urgent_dispute_funds_action,
        'return_review_completed': return_review_completed,
        'return_pin_available': return_pin_available,
        'checkout_pin_available': checkout_pin_available,
        'deposit_funds_held': deposit_funds_held,
        'feedback_stage': feedback_stage,
        'feedback_left_by_me': feedback_left_by_me,
        'feedback_prompt_required': feedback_prompt_required,
        'feedback_both_complete': feedback_both_complete,
        'feedback_from_lender': feedback_from_lender,
        'feedback_from_renter': feedback_from_renter,
        'lender_feedback_stats': lender_feedback_stats,
        'renter_feedback_stats': renter_feedback_stats,
        'stripe_publishable_key': getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''),
        'user_payment_methods': user_payment_methods,
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
        'message_turnstile_required': message_turnstile_required,
    }
    return render(request, 'transaction/view_transaction.html', context)


@login_required
def card_setup_status(request, transaction_reference=None):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user:
        raise Http404

    if (
        txn.deposit_card_setup_status == txn.CARD_READY
        and txn.deposit_test_hold_status == txn.TEST_HOLD_SUCCESS
    ):
        state = 'completed'
        message = (
            f"Card ready: {txn.deposit_card_brand or 'Card'} ending {txn.deposit_card_last4 or 'xxxx'}. "
            "The £0.30 verification hold succeeded."
        )
    elif (
        txn.deposit_card_setup_status == txn.CARD_FAILED
        or txn.deposit_test_hold_status == txn.TEST_HOLD_FAILED
    ):
        state = 'failed'
        message = 'Card verification failed. Please try again or use a different card.'
    else:
        state = 'processing'
        message = 'Card verification in progress. This usually takes a few seconds.'

    return JsonResponse(
        {
            'state': state,
            'message': message,
            'card_setup_status': txn.deposit_card_setup_status,
            'test_hold_status': txn.deposit_test_hold_status,
            'card_brand': txn.deposit_card_brand,
            'card_last4': txn.deposit_card_last4,
            'updated': txn.amended.isoformat() if txn.amended else '',
        }
    )


@login_required
@ajax_required
def transaction_add_message(request):
    transaction_ref = request.GET.get('transaction_ref', None)
    message = request.GET.get('message', None)
    status = 'NOK'
    txn = get_object_or_404(Transaction, transaction_reference=transaction_ref)
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        messages.success(request, 'message added')
        status = 'OK'
        if message is not None and message != '':
            txn_message = TransactionMessage()
            txn_message.user_from = request.user
            if txn.user_passive == request.user:
                txn_message.user_to = txn.user_aggressive
            else:
                txn_message.user_to = txn.user_passive
            txn_message.transaction = txn
            txn_message.description = message
            # txn_message.subject = txn.get_payment_status_display()
            txn_message.save()

    content = {
        'status' : status
    }
    return JsonResponse(content)

@login_required
@ajax_required
def set_payment_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy payment endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

@login_required
@ajax_required
def set_product_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy product endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

    
@login_required
@ajax_required
def set_transaction_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy transaction endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

@login_required
def raise_dispute(request, transaction_reference=None):
    transaction = None
    txn_message = TransactionMessage()
    if request.method=='POST':        
        # TODO: need to check txn belongs to user
        txn = get_object_or_404(Transaction, transaction_reference=request.POST['transaction_reference'])
        if txn.user_passive == request.user or txn.user_aggressive == request.user:
            txn_messsage_form = TransactionMessageAddForm(instance=txn_message,
                                                        data=request.POST,
                                                        files=request.FILES)
            if txn_messsage_form.is_valid():
                txn_message = txn_messsage_form.save(commit=False)
                txn_message.user_from = request.user
                if txn.user_passive == request.user:
                    txn_message.user_to =  txn.user_aggressive
                else:
                    txn_message.user_to =  txn.user_passive
                txn_message.include_admin = True
                txn_message.transaction = txn
                txn_message.save()
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.save()
                

                # Update all orderImage records with the new id
                txn_msg_image_ids = request.POST['txn_image_id'].split()
                for txn_msg_image_id in txn_msg_image_ids:
                    try:
                        txn_msg_image = TransactionMessageImage.objects.get(pk=txn_msg_image_id)
                        if request.user == txn_msg_image.user:
                            txn_msg_image.txn_message = txn_message
                            txn_msg_image.saveNoImageModification()
                    except TransactionMessageImage.DoesNotExist:
                        raise Http404("Transaction Message Image does not exist")

                messages.success(request, 'Dispute request raised to Admin team')
                product_url = request.build_absolute_uri(reverse('transaction:view_transaction' ,
                        kwargs={'transaction_reference': txn_message.transaction.transaction_reference}))
                return redirect(product_url)
            else:
                messages.error(request, 'Error in validation')
                txn_message_image_form = TransactionMessageImageForm(instance=transaction)
                context = {
                    'transaction' : transaction,
                    'txn_message_form' : txn_message_form,
                    'txn_message_image_form' : txn_message_image_form
                }
                return render(request, 'transaction/raise_dispute.html', context)
        else:
            return Http404
    else:
        txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
        if txn.user_passive == request.user or txn.user_aggressive == request.user:
            txn_message_form = TransactionMessageAddForm(instance=transaction)
            txn_message_image_form = TransactionMessageImageForm(instance=transaction)

            context = {
                'transaction' : txn,
                'txn_message_form' : txn_message_form,
                'txn_message_image_form' : txn_message_image_form
            }
            return render(request, 'transaction/raise_dispute.html', context)
        else:
            return Http404

@ajax_required
def transpact_refresh(request):
    content = {
        'status' : 'NOK',
        'message': 'Transpact refresh is disabled in the new rental workflow.',
    }
    return JsonResponse(content)


@csrf_exempt
def stripe_connect_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'NOK', 'message': 'POST required.'}, status=405)

    payload = request.body
    signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    result = stripe_connect_service.process_webhook(payload=payload, signature=signature)
    if not result.get('ok'):
        return JsonResponse({'status': 'NOK', 'message': result.get('error', 'Invalid webhook.')}, status=400)

    return JsonResponse({
        'status': 'OK',
        'event_type': result.get('event_type', 'unknown'),
        'provider': result.get('provider', 'unknown'),
    })

class TransactionMessageImageUpload(View):
    def post(self, request):
        # logger = logging.getLogger(__name__)
        data = {'is_valid': False}
        form = TransactionMessageImageForm(self.request.POST, self.request.FILES)
        transaction_reference = request.GET.get('transaction_reference', None)
        #TODO : add transaciton stuff
        if form.is_valid() and request.user is not None:
            image = form.save(commit=False)
            image.user = request.user
            image.save()
            data = {'is_valid': True, 
                    'txn_image_id': image.id ,
                    'image_name': image.image.name, 
                    'image_url': image.image.url}
        else:
            data = {'is_valid': False}
        return JsonResponse(data)
