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
from datetime import datetime
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


@login_required
def add_order(request, product_id=None):
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
    blocked_dates = [
        bd.date.isoformat()
        for bd in order.blocked_dates.filter(reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.BOOKED])
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
        'blocked_dates_json': json.dumps(blocked_dates),
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
    order = get_object_or_404(Order, id=order_id)
    blocked_dates = set(
        order.blocked_dates.filter(reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.BOOKED]).values_list('date', flat=True)
    )
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
    blocked_dates_json = json.dumps(sorted([d.isoformat() for d in blocked_dates]))
    handover_dates_json = json.dumps(sorted([d.isoformat() for d in handover_dates]))
    price_bands_json = json.dumps(price_bands)

    context = {
        'order': order,
        'order_hit_form': order_hit_form,
        'blocked_dates_json': blocked_dates_json,
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

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'agree_rental' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_AGREED
            txn.save()
            messages.success(request, 'Rental agreed.')

        elif action == 'initiate_rental' and is_lender and txn.transaction_status == txn.RENTAL_AGREED:
            checkout_video = request.POST.get('checkout_video_url', '').strip()
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_INITIATED
            txn.checkout_condition_video_url = checkout_video
            if checkout_video:
                txn.product_status = txn.CHECKOUT_VIDEO_ADDED

            payment_collected = bool(request.POST.get('payment_collected_placeholder'))
            deposit_collected = bool(request.POST.get('deposit_collected_placeholder'))
            txn.payment_collected_placeholder = payment_collected
            txn.deposit_collected_placeholder = deposit_collected
            txn.payment_status = txn.PAYMENT_CAPTURED_PLACEHOLDER if payment_collected else txn.PAYMENT_PENDING
            txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER if deposit_collected else txn.DEPOSIT_PENDING
            txn.payment_placeholder_notes = request.POST.get('payment_placeholder_notes', '').strip()
            txn.deposit_placeholder_notes = request.POST.get('deposit_placeholder_notes', '').strip()
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
