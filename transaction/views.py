from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth import authenticate, login
from .forms import OrderEditForm, OrderExpireForm
from .forms import OrderAddForm, OrderImageForm, LetPriceBandFormSet, RentalEnquiryForm
from .forms import TransactionMessageImageForm, TransactionMessageAddForm
from django.contrib.auth.decorators import login_required
from common.models import Order, Product, OrderImage, TransactionFee, OrderBlockedDate
from .models import Transaction, TransactionMessage, TransactionMessageImage, TransactionCharge, TransactionImage
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
from .helpers import returnFeeValue, getTransactionStepAndAction
import os
import json
from django.core.files import File
from account.models import Profile
from urllib.parse import quote
from django.views.decorators.csrf import csrf_exempt

from account.models import PaymentMethod

from .stripe_connect import stripe_connect_service


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
                
                # Check if renter needs KYC
                if not renter_profile.stripe_identity_verified:
                    requires_kyc = True
                    kyc_message += 'As the renter, you must complete KYC verification. '
                
                # Check if lender needs KYC
                if not lender_profile.stripe_identity_verified:
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
    }
    return render(request, 'transaction/hit_order.html', context)


@login_required
def view_transaction(request, transaction_reference=None):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user:
        raise Http404

    is_lender = (request.user == txn.user_passive)
    is_renter = (request.user == txn.user_aggressive)

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

        elif action == 'confirm_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreement_pending_at:
            txn.lender_agreed_at = timezone.now()
            txn.save()
            # Send contract confirmation request to renter
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
            messages.success(request, 'Contract confirmed. Renter has been sent a confirmation request.')

        elif action == 'reinitiate_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            # Extend the deadline by resetting lender_agreed_at to now
            txn.lender_agreed_at = timezone.now()
            txn.save()
            # Send a fresh confirmation request to renter
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
            messages.success(request, 'Confirmation request re-sent to renter. 24-hour window restarted.')

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

        elif action == 'add_deposit_card' and is_renter and txn.transaction_status == txn.RENTAL_AGREED:
            cardholder_name = (request.POST.get('deposit_cardholder_name') or '').strip()
            card_brand = (request.POST.get('deposit_card_brand') or '').strip()
            card_last4 = (request.POST.get('deposit_card_last4') or '').strip()

            if txn.deposit <= 0:
                messages.info(request, 'No deposit is required for this transaction.')
            elif not cardholder_name:
                messages.error(request, 'Please enter the cardholder name.')
            elif len(card_last4) != 4 or not card_last4.isdigit():
                messages.error(request, 'Please enter a valid last 4 digits for the card.')
            else:
                setup_result = stripe_connect_service.setup_deposit_card_and_test_hold(
                    transaction=txn,
                    cardholder_name=cardholder_name,
                    card_brand=card_brand,
                    card_last4=card_last4,
                )
                if not setup_result.get('ok'):
                    txn.deposit_card_setup_status = txn.CARD_FAILED
                    txn.deposit_test_hold_status = txn.TEST_HOLD_FAILED
                    txn.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'amended'])
                    messages.error(request, setup_result.get('error', 'Card setup failed.'))
                else:
                    txn.deposit_card_setup_status = setup_result.get('card_setup_status', txn.CARD_READY)
                    txn.deposit_cardholder_name = setup_result.get('cardholder_name', cardholder_name)
                    txn.deposit_card_brand = setup_result.get('card_brand', card_brand.upper()[:20])
                    txn.deposit_card_last4 = setup_result.get('card_last4', card_last4)
                    txn.deposit_test_hold_status = setup_result.get('test_hold_status', txn.TEST_HOLD_SUCCESS)
                    txn.deposit_test_hold_amount = setup_result.get('test_hold_amount', 0.01)
                    txn.deposit_test_hold_at = setup_result.get('test_hold_at')
                    txn.deposit_test_hold_reference = setup_result.get('test_hold_reference', '')
                    txn.save()
                    provider_label = setup_result.get('provider', 'service')
                    messages.success(
                        request,
                        f'Deposit card saved. A £0.01 test hold succeeded via {provider_label}.'
                    )

        elif action == 'use_existing_card' and is_renter and txn.transaction_status == txn.RENTAL_AGREED:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()

            if txn.deposit <= 0:
                messages.info(request, 'No deposit is required for this transaction.')
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
                    txn.deposit_test_hold_amount = 0.01
                    txn.deposit_test_hold_at = timezone.now()
                    txn.stripe_setup_intent_id = pm.stripe_setup_intent_id
                    txn.stripe_payment_method_id = pm.stripe_payment_method_id
                    txn.save()
                    messages.success(request, f'Using {pm.card_brand} ending {pm.card_last4} for deposit.')
                except PaymentMethod.DoesNotExist:
                    messages.error(request, 'Payment method not found.')

        elif action == 'confirm_stripe_card' and is_renter and txn.transaction_status == txn.RENTAL_AGREED:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()
            setup_intent_id = (request.POST.get('setup_intent_id') or '').strip()

            if txn.deposit <= 0:
                messages.info(request, 'No deposit is required for this transaction.')
            elif not payment_method_id:
                messages.error(request, 'Card details were not submitted successfully. Please try again.')
            else:
                confirm_result = stripe_connect_service.confirm_card_setup(
                    transaction=txn,
                    setup_intent_id=setup_intent_id,
                    payment_method_id=payment_method_id,
                )
                if not confirm_result.get('ok'):
                    txn.deposit_card_setup_status = txn.CARD_FAILED
                    txn.deposit_test_hold_status = txn.TEST_HOLD_FAILED
                    txn.save(update_fields=['deposit_card_setup_status', 'deposit_test_hold_status', 'amended'])
                    messages.error(request, confirm_result.get('error', 'Card setup failed.'))
                else:
                    txn.deposit_card_setup_status = confirm_result.get('card_setup_status', txn.CARD_READY)
                    txn.deposit_cardholder_name = confirm_result.get('cardholder_name', 'Stripe')
                    txn.deposit_card_brand = confirm_result.get('card_brand', 'Card')
                    txn.deposit_card_last4 = confirm_result.get('card_last4', 'xxxx')
                    txn.deposit_test_hold_status = confirm_result.get('test_hold_status', txn.TEST_HOLD_SUCCESS)
                    txn.deposit_test_hold_amount = confirm_result.get('test_hold_amount', 0.01)
                    txn.deposit_test_hold_at = confirm_result.get('test_hold_at')
                    txn.deposit_test_hold_reference = confirm_result.get('test_hold_reference', '')
                    txn.stripe_setup_intent_id = setup_intent_id
                    txn.stripe_payment_method_id = payment_method_id
                    txn.save()

                    provider_label = confirm_result.get('provider', 'service')
                    messages.success(
                        request,
                        f'Deposit card saved securely. A £0.01 test hold succeeded via {provider_label}.'
                    )

                    try:
                        PaymentMethod.objects.update_or_create(
                            stripe_payment_method_id=payment_method_id,
                            defaults={
                                'user': request.user,
                                'stripe_setup_intent_id': setup_intent_id,
                                'card_brand': confirm_result.get('card_brand', 'Card'),
                                'card_last4': confirm_result.get('card_last4', 'xxxx'),
                            },
                        )
                    except Exception as exc:
                        logging.exception('Failed to save payment method: %s', exc)

        elif action == 'collect_deposit' and is_lender and txn.transaction_status in (txn.RENTAL_AGREED, txn.RENTAL_INITIATED):
            if not _can_collect_deposit(txn):
                messages.error(
                    request,
                    'Deposit cannot be collected yet. Ensure card setup/test hold is complete and rental start date has been reached.'
                )
            else:
                collect_result = stripe_connect_service.collect_deposit_hold(transaction=txn)
                if not collect_result.get('ok'):
                    txn.deposit_collection_status = txn.COLLECT_FAILED
                    txn.save(update_fields=['deposit_collection_status', 'amended'])
                    messages.error(request, collect_result.get('error', 'Deposit collection failed.'))
                else:
                    txn.deposit_collected_placeholder = True
                    txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER
                    txn.deposit_collection_status = collect_result.get('collection_status', txn.COLLECT_SUCCESS)
                    txn.deposit_collection_requested_at = collect_result.get('collection_requested_at')
                    txn.deposit_collection_reference = collect_result.get('collection_reference', '')
                    txn.save()
                    provider_label = collect_result.get('provider', 'service')
                    messages.success(
                        request,
                        f'Deposit collected via {provider_label}: full authorization hold/retrieval recorded.'
                    )

        elif action == 'send_message' and (is_lender or is_renter):
            body = (request.POST.get('message_body') or '').strip()
            if not body:
                messages.error(request, 'Please enter a message before sending.')
            else:
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=(txn.user_aggressive if is_lender else txn.user_passive),
                    transaction=txn,
                    subject=f'Transaction {txn.transaction_reference}',
                    description=body,
                )
                messages.success(request, 'Message sent.')

        elif action == 'initiate_rental' and is_lender and txn.transaction_status == txn.RENTAL_AGREED:
            checkout_video = request.POST.get('checkout_video_url', '').strip()
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_INITIATED
            txn.checkout_condition_video_url = checkout_video
            if checkout_video:
                txn.product_status = txn.CHECKOUT_VIDEO_ADDED

            payment_collected = bool(request.POST.get('payment_collected_placeholder'))
            txn.payment_collected_placeholder = payment_collected
            txn.payment_status = txn.PAYMENT_CAPTURED_PLACEHOLDER if payment_collected else txn.PAYMENT_PENDING
            txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER if txn.deposit_collected_placeholder else txn.DEPOSIT_PENDING
            txn.payment_placeholder_notes = request.POST.get('payment_placeholder_notes', '').strip()
            txn.save()
            messages.success(request, 'Rental initiated. Checkout evidence and placeholders saved.')

        elif action == 'mark_returned' and txn.transaction_status == txn.RENTAL_INITIATED and (is_lender or is_renter):
            return_video = request.POST.get('return_video_url', '').strip()
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED
            txn.return_condition_video_url = return_video
            if return_video:
                txn.product_status = txn.RETURN_VIDEO_ADDED
            txn.save()
            messages.success(request, 'Rental marked as returned.')

        elif action == 'deposit_full' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.DEPOSIT_RETURNED
            txn.deposit_status = txn.DEPOSIT_RETURNED_FULL
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.success(request, 'Deposit marked as returned in full.')

        elif action == 'deposit_reduced' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.DEPOSIT_REDUCED
            txn.deposit_status = txn.DEPOSIT_RETURNED_REDUCED
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.success(request, 'Reduced deposit return recorded.')

        elif action == 'mediation_required' and (is_lender or is_renter) and txn.transaction_status == txn.RENTAL_RETURNED:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.MEDIATION_REQUIRED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.warning(request, 'Mediation required has been recorded.')

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
    contract_deadline = _get_contract_deadline(txn)
    contract_seconds_remaining = None
    if contract_deadline:
        contract_seconds_remaining = int((contract_deadline - timezone.now()).total_seconds())

    can_collect_deposit = _can_collect_deposit(txn)

    # Generate Stripe SetupIntent for card collection if needed
    setup_intent_client_secret = None
    setup_intent_id = None
    if (is_renter and txn.transaction_status == txn.RENTAL_AGREED and 
        txn.lender_agreed_at and txn.deposit > 0 and 
        not txn.deposit_card_setup_status == txn.CARD_READY):
        setup_result = stripe_connect_service.create_setup_intent(transaction=txn)
        if setup_result.get('ok'):
            setup_intent_client_secret = setup_result.get('client_secret')
            setup_intent_id = setup_result.get('setup_intent_id')

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
        'contract_deadline_iso': contract_deadline.isoformat() if contract_deadline else '',
        'contract_seconds_remaining': contract_seconds_remaining,
        'can_collect_deposit': can_collect_deposit,
        'setup_intent_client_secret': setup_intent_client_secret,
        'setup_intent_id': setup_intent_id,
        'stripe_publishable_key': getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''),
        'user_payment_methods': user_payment_methods,
    }
    return render(request, 'transaction/view_transaction.html', context)


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
