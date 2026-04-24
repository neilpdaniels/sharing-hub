from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth import authenticate, login
from .forms import OrderEditForm, OrderExpireForm
from .forms import OrderAddForm, OrderImageForm, OrderHitForm, LetPriceBandFormSet
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
from transaction.tasks import createNewTransaction, getUserTransactions


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
            OrderBlockedDate.objects.filter(order=order, reason=OrderBlockedDate.MANUAL).delete()
            blocked_raw = request.POST.get('blocked_dates', '')
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
    blocked_dates = [bd.date.isoformat() for bd in order.blocked_dates.all()]

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
    order = None
    hit_direction = None
    fees = {}
    all_fees = TransactionFee.objects.all()
    for fee in all_fees:
        fees[fee] = fee.transactionfeeband_set.all().order_by('-price')

    if request.method=='POST':
        order = get_object_or_404(Order, id=order_id)
        error = False
        if request.user != order.user:
            if float(request.POST['order_required_price']) == float(order.price):
                if int(order.quantity) >= int(request.POST['quantity']) and order.expiry_date > timezone.now():
                    for fee in all_fees:
                        # check each fee is as expected
                        if fee.slug in request.POST:
                            price_supplied = float(request.POST[fee.slug])
                            price_calculated = returnFeeValue(fee, int(request.POST['quantity']), float(request.POST['order_required_price']) , order)
                            if price_supplied != price_calculated:
                                error = True    
                                messages.error(request, 'Fee supplied value does not match calculated: {}, {}:{} '.format(fee.name, price_supplied, price_calculated))                            
                        elif order.direction == Order.TO_LET:
                            # easy at present as all fees on buyer
                            error = True
                            messages.error(request, 'Missing fee: {}'.format(fee.name))                            
                            messages.error(request, 'Missing fee: {}'.format(request.POST))                            

                    if error is not True: 
                        txn = Transaction()
                        txn.price = order.price
                        txn.quantity = int(request.POST['quantity'])
                        txn.order_passive = order
                        txn.order_passive_description = order.description # snapshot in case changed
                        txn.product = order.product
                        txn.user_aggressive = request.user
                        txn.user_passive = order.user
                        
                        current_spot_value = 0
                        price_as_pct_spot_value = 0
                        txn.current_spot_value = current_spot_value
                        txn.price_as_pct_spot_value = price_as_pct_spot_value
                        txn.save()
                        
                        # save txn images
                        for ordImage in order.images.filter(active=True):
                            txn_image = TransactionImage()
                            txn_image.image = File(ordImage.image, ordImage.image.name)
                            txn_image.transaction = txn
                            txn_image.save()

                        # save txn charges
                        for fee in all_fees:
                            # check each fee is as expected
                            if fee.name in request.POST:
                                txn_charge = TransactionCharge()
                                txn_charge.transaction = txn
                                txn_charge.transaction_fee = fee
                                txn_charge.user_to_pay = request.user
                                txn_charge.price = round(float(request.POST[fee.name]),2)
                                txn_charge.save()
                            else:
                                # can really just use this without the "POST" values, maybe this is a touch more lightweight
                                txn_charge = TransactionCharge()
                                txn_charge.transaction = txn
                                txn_charge.transaction_fee = fee
                                txn_charge.user_to_pay = request.user
                                fee_price = returnFeeValue(fee, int(request.POST['quantity']), float(request.POST['order_required_price']), order)
                                txn_charge.price = round(float(fee_price),2)
                                txn_charge.save()

                        # reduce order and expire if 0 qty
                        order.quantity = order.quantity - txn.quantity
                        if order.quantity == 0:
                            order.expiry_date = timezone.now()
                        order.save()

                        # context = {
                        #     'order' : order,
                        #     'transaction' : txn,
                        # }

                        # messages.success(request, 'Order hit successfully')
                        #return render(request, 'transaction/hit_order_done.html', context)``
                        messages_ = None
                        charges = None
                        txnImages = None
                        total_px = 0
                        total_fees = 0
                        total_items = 0
                        step, next_action = getTransactionStepAndAction(txn, request)
                        
                        if txn.user_passive == request.user or txn.user_aggressive == request.user:
                            transaction = txn
                            messages_ = sorted(sorted((txn.transactionmessage_set.all()),
                            key=attrgetter('created'),reverse=True),
                            key=attrgetter('read_by_user_to'))
                            charges = txn.transactioncharge_set.all()
                            total_px = txn.quantity * txn.price
                            total_items = txn.quantity * txn.price
                            for charge in charges:
                                total_px += charge.price
                                total_fees += charge.price
                            txnImages = txn.transactionimage_set.all()


                        context = {
                            'transaction' : transaction,
                            'charges' : charges,
                            'messages_' : messages_,
                            'total_px' : total_px,
                            'txnImages' : txnImages,
                            'total_items' : total_items,
                            'total_fees' : total_fees,
                            'step' : step,
                            'next_action' : next_action
                        }
                        messages.success(request, 'Order hit successfully - transaction created')
                        createNewTransaction.delay(int(transaction.id))
                        getUserTransactions.delay(int(request.user.id))

                        return render(request, 'transaction/view_transaction.html', context)
                else:
                    messages.error(request, 'Order is no longer available')
                    error = True
            else:
                messages.error(request, 'Order price has changed - please review/retry')
                error = True
        else:
            messages.error(request, 'You can\'t buy/sell from yourself')
            error = True

        if error:
            product_url = request.build_absolute_uri(reverse('navigation:productPage' ,
                kwargs={'product_slug': order.product.slug}))
            return redirect(product_url)
    else:
        order = get_object_or_404(Order, id=order_id)
        order_hit_form = OrderHitForm(instance=order)

        sharing_hub_tooltip = "SharingHub charges a small fee on all tranactions"
        # fees2 = {
            # 'sharing_hub' : [1, sharing_hub_tooltip]
        # }
        # postage = Postage.objects.all().order_by('-price')

        if order.direction == 'S':
            hit_direction = "Buy"
            # postage_tooltip = "Postage is paid by the buyer.  Postage is always insured royal mail special delivery, insured to the correct value"
            # fees2['postage'] = [0, postage_tooltip]
            # escrow_tooltip = "Escrow is mandatory. We've search for the best value FCA regulated escrow client whose rates are very competative"
            # fees2['escrow'] = [5.98, escrow_tooltip]
        else:
            hit_direction = "Sell"
        
        
        context = {
            'order' : order,
            'order_hit_form' : order_hit_form,
            'hit_direction' : hit_direction,
            'fees' : fees,
            'item_weight' : order.product.weight,
        }
        return render(request, 'transaction/hit_order.html', context)


@login_required
def view_transaction(request, transaction_reference=None):
    transaction = None
    messages_ = None
    charges = None
    txnImages = None
    total_px = 0
    total_fees = 0
    total_items = 0
    step = -1
    next_action = False
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)

    step, next_action = getTransactionStepAndAction(txn, request)

    # # work out step 
    # if txn.transaction_status != txn.CANCEL_ACCEPTED and txn.transaction_status != txn.COMPLETED_ACK \
    #     and txn.transaction_status != txn.CANCEL_REQUESTED and txn.transaction_status != txn.DISPUTE_REQUESTED:
    #     if txn.payment_status == txn.PAYMENT_NOT_SENT or txn.payment_status == txn.PAYMENT_TIMEOUT:
    #         step = 1
    #         if (txn.user_passive == request.user and txn.order_passive.direction == "B") \
    #             or (txn.user_aggressive == request.user and txn.order_passive.direction == "S"):
    #             next_action = True
    #     elif txn.payment_status == txn.PAYMENT_SENT:
    #         step = 2
    #         if (txn.user_passive == request.user and txn.order_passive.direction == "S") \
    #         or (txn.user_aggressive == request.user and txn.order_passive.direction == "B"):
    #             next_action = True
    # if txn.transaction_status != txn.CANCEL_ACCEPTED and txn.transaction_status != txn.COMPLETED_ACK \
    #     and txn.transaction_status != txn.DISPUTE_REQUESTED:
    #     if txn.payment_status == txn.PAYMENT_SENT or txn.payment_status == txn.PAYMENT_ACKED:
    #         if txn.product_status == txn.PRODUCT_NOT_SENT or txn.product_status == txn.PRODUCT_NOT_SENT_TIMEOUT:
    #             step = 3
    #             if (txn.user_passive == request.user and txn.order_passive.direction == "S") \
    #             or (txn.user_aggressive == request.user and txn.order_passive.direction == "B"):
    #                 next_action = True
    #         elif txn.product_status == txn.PRODUCT_SENT:
    #             step = 4
    #             if (txn.user_passive == request.user and txn.order_passive.direction == "B") \
    #             or (txn.user_aggressive == request.user and txn.order_passive.direction == "S"):    
    #                 next_action = True
    #         elif txn.product_status == txn.PRODUCT_RECEIVED:
    #             step = 5
    #             if (txn.user_passive == request.user and txn.order_passive.direction == "B") \
    #             or (txn.user_aggressive == request.user and txn.order_passive.direction == "S"):
    #                 next_action = True
    
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        transaction = txn
        messages_ = sorted(sorted((txn.transactionmessage_set.all()),
        key=attrgetter('created'),reverse=True),
        key=attrgetter('read_by_user_to'))
        charges = txn.transactioncharge_set.all()
        total_px = txn.quantity * txn.price
        total_items = txn.quantity * txn.price
        for charge in charges:
            total_px += charge.price
            total_fees += charge.price
        txnImages = txn.transactionimage_set.all()


    context = {
        'transaction' : transaction,
        'charges' : charges,
        'messages_' : messages_,
        'total_px' : total_px,
        'txnImages' : txnImages,
        'total_items' : total_items,
        'total_fees' : total_fees,
        'step' : step,
        'next_action' : next_action
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
    transaction_ref = request.GET.get('transaction_ref', None)
    newState = request.GET.get('newState', None)
    message = request.GET.get('message', None)
    status = 'NOK'

    txn = get_object_or_404(Transaction, transaction_reference=transaction_ref)
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        if txn.transaction_status != txn.DISPUTE_REQUESTED:
            # BUYER TASKS
            if (txn.user_passive == request.user and txn.order_passive.direction == "B") \
                or (txn.user_aggressive == request.user and txn.order_passive.direction == "S"):

                if newState == txn.PAYMENT_SENT:
                    if txn.payment_status == txn.PAYMENT_NOT_SENT or txn.payment_status == txn.PAYMENT_TIMEOUT:
                        txn.payment_status = newState
                        txn.transaction_status = txn.PAYMENT_PROCESSING
                        txn.save()
                        messages.success(request, 'Payment Status Updated')
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
                            txn_message.subject = txn.get_payment_status_display()
                            txn_message.save()
            
            # SELLER TASKS
            if (txn.user_passive == request.user and txn.order_passive.direction == "S") \
                or (txn.user_aggressive == request.user and txn.order_passive.direction == "B"):
                if newState == txn.PAYMENT_ACKED:
                    if txn.payment_status == txn.PAYMENT_SENT:
                        txn.payment_status = newState
                        txn.save()
                        messages.success(request, 'Payment Status Updated')
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
                            txn_message.subject = txn.get_payment_status_display()
                            txn_message.save()

    content = {
        'status' : status
    }
    return JsonResponse(content)

@login_required
@ajax_required
def set_product_state(request):
    transaction_ref = request.GET.get('transaction_ref', None)
    newState = request.GET.get('newState', None)
    message = request.GET.get('message', None)

    status = 'NOK'

    txn = get_object_or_404(Transaction, transaction_reference=transaction_ref)
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        if txn.transaction_status != txn.DISPUTE_REQUESTED:

            # SELLER TASKS
            if (txn.user_passive == request.user and txn.order_passive.direction == "S") \
                or (txn.user_aggressive == request.user and txn.order_passive.direction == "B"):
                if newState == txn.PRODUCT_SENT:
                    if txn.payment_status == txn.FUNDS_IN_ESCROW or txn.payment_status == txn.FUNDS_RELEASED:
                        if txn.product_status == txn.PRODUCT_NOT_SENT or txn.product_status == txn.PRODUCT_NOT_SENT_TIMEOUT:
                            txn.product_status = newState
                            if txn.payment_status == txn.PAYMENT_SENT:  
                                txn.payment_status = txn.PAYMENT_ACKED
                            txn.transaction_status = txn.DELIVERY_PROCESSING
                            txn.save()
                            messages.success(request, 'Delivery Status Updated')
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
                                txn_message.subject = txn.get_product_status_display()
                                txn_message.save()


            # BUYER TASKS
            if (txn.user_passive == request.user and txn.order_passive.direction == "B") \
                or (txn.user_aggressive == request.user and txn.order_passive.direction == "S"):
                if newState == txn.PRODUCT_RECEIVED:
                    if txn.payment_status == txn.FUNDS_IN_ESCROW or txn.payment_status == txn.FUNDS_RELEASED:
                        if txn.product_status == txn.PRODUCT_SENT:
                            txn.product_status = newState
                            txn.save()
                            messages.success(request, 'Delivery Status Updated')
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
                                txn_message.subject = txn.get_product_status_display()
                                txn_message.save()

                if newState == txn.PRODUCT_VERIFIED_OK:
                    if txn.payment_status == txn.FUNDS_IN_ESCROW or txn.payment_status == txn.FUNDS_RELEASED:
                        if txn.product_status == txn.PRODUCT_RECEIVED or txn.product_status == txn.PRODUCT_NOT_AS_SHOWN:
                            txn.product_status = newState
                            txn.save()
                            messages.success(request, 'Delivery Status Updated - Transaction now complete')
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
                                txn_message.subject = txn.get_product_status_display()
                                txn_message.save()

                if newState == txn.PRODUCT_NOT_AS_SHOWN:
                    if txn.payment_status == txn.FUNDS_IN_ESCROW or txn.payment_status == txn.FUNDS_RELEASED:
                        if txn.product_status == txn.PRODUCT_RECEIVED or txn.product_status == txn.PRODUCT_VERIFIED_OK:
                            txn.product_status = newState
                            txn.save()
                            messages.success(request, 'Delivery Status Updated - Transaction now complete')
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
                                txn_message.subject = txn.get_product_status_display()
                                txn_message.save()

        
    content = {
        'status' : status
    }
    return JsonResponse(content)

    
@login_required
@ajax_required
def set_transaction_state(request):
    transaction_ref = request.GET.get('transaction_ref', None)
    newState = request.GET.get('newState', None)
    message = request.GET.get('message', None)
    status = 'NOK'

    txn = get_object_or_404(Transaction, transaction_reference=transaction_ref)
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        if newState == txn.CANCEL_CANCELLED:
            if txn.transaction_status == txn.CANCEL_REQUESTED:
                if txn.transaction_status_raised_by == request.user:
                    txn.transaction_status = txn.NEW
                    txn.transaction_status_raised_by = request.user
                    txn.save()
                    messages.success(request, 'Cancellation request reversed - Transaction set to {}'.format(txn.get_transaction_status_display()))
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
                        txn_message.subject = "Cancellation request reversed"
                        txn_message.save()

        if newState == txn.CANCEL_REQUESTED:
            if txn.transaction_status == txn.NEW \
                or txn.transaction_status == txn.NEW_TIMEOUT \
                or txn.transaction_status == txn.CANCEL_REFUSED:
                if txn.payment_status == txn.PAYMENT_NOT_SENT or txn.payment_status == txn.PAYMENT_TIMEOUT:
                    txn.transaction_status = newState
                    txn.transaction_status_raised_by = request.user
                    txn.save()
                    messages.success(request, 'Cancel Requested')
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
                        txn_message.subject = txn.get_transaction_status_display()
                        txn_message.save()

        if newState == txn.CANCEL_ACCEPTED:
            if txn.transaction_status_raised_by != request.user and txn.transaction_status == txn.CANCEL_REQUESTED:
                txn.transaction_status = newState
                txn.transaction_status_raised_by = request.user
                txn.save()
                messages.success(request, 'Cancel Accepted')
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
                    txn_message.subject = txn.get_transaction_status_display()
                    txn_message.save()

        if newState == txn.CANCEL_REFUSED:
            if txn.transaction_status_raised_by != request.user and txn.transaction_status == txn.CANCEL_REQUESTED:
                txn.transaction_status = newState
                txn.transaction_status_raised_by = request.user
                txn.save()
                messages.success(request, txn.get_transaction_status_display())
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
                    txn_message.subject = txn.get_transaction_status_display()
                    txn_message.save()

    content = {
        'status' : status
    }
    return JsonResponse(content)

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
    transaction_id = request.POST.get('transaction_id', None)
    getUserTransactions.delay(int(request.user.id))
    content = {
        'status' : 'OK',
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
