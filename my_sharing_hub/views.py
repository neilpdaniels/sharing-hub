from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
# from .models import Profile
from django.contrib import messages
import logging
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage,\
                        PageNotAnInteger
from transaction.models import Transaction, TransactionMessage
from itertools import chain
from operator import attrgetter
from common.decorators import ajax_required
from django.db.models import Q
from transaction.tasks import getUserTransactions
from common.models import Order, OrderImage, OrderBlockedDate, LetPriceBand
from django.utils import timezone
from datetime import timedelta
import calendar
from datetime import date

from account.models import PaymentMethod


@login_required
def dashboard(request):    
    context = {
    }
    return render(request, 'my_sharing_hub/dashboard.html', context)

@login_required
def messages_received(request):    
    user = request.user
    # object_from_list = user.message_user_from.filter()
    object_to_list = user.message_user_to.filter()
    # object_list =  sorted(
    # (chain(object_from_list, object_to_list)),
    # key=attrgetter('created'), reverse=True)

    object_list = sorted(sorted((object_to_list),
    key=attrgetter('created'),reverse=True),
    key=attrgetter('read_by_user_to'))

    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    try:
        messages_ = paginator.page(page)
    except PageNotAnInteger:
        messages_ = paginator.page(1)
    except EmptyPage:
        messages_ = paginator.page(paginator.num_pages)
    context = {
        'messages_': messages_,
        'type' : 'received',
    }
    return render(request, 'my_sharing_hub/x_messages.html', context)


@login_required
def payment_methods(request):
    """List all payment methods for the logged-in user."""
    user = request.user
    user_payment_methods = user.payment_methods.all()
    
    # Handle POST for setting default payment method
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        payment_method_id = request.POST.get('payment_method_id', '').strip()
        
        if action == 'set_default' and payment_method_id:
            try:
                # Set all to non-default first
                user.payment_methods.update(is_default=False)
                # Set this one as default
                pm = user.payment_methods.get(id=payment_method_id)
                pm.is_default = True
                pm.save()
                messages.success(request, f'Default payment method set to {pm.card_brand} ending {pm.card_last4}.')
            except PaymentMethod.DoesNotExist:
                messages.error(request, 'Payment method not found.')
        elif action == 'delete' and payment_method_id:
            try:
                pm = user.payment_methods.get(id=payment_method_id)
                card_display = f'{pm.card_brand} ending {pm.card_last4}'
                pm.delete()
                messages.success(request, f'{card_display} has been deleted.')
            except PaymentMethod.DoesNotExist:
                messages.error(request, 'Payment method not found.')
        
        return redirect('my_sharing_hub:payment_methods')
    
    context = {
        'payment_methods': user_payment_methods,
    }
    return render(request, 'my_sharing_hub/payment_methods.html', context)


@login_required
def messages_sent(request):    
    user = request.user
    object_from_list = user.message_user_from.filter()
    # object_to_list = user.message_user_to.filter()
    # object_list =  sorted(
    # (chain(object_from_list, object_to_list)),
    # key=attrgetter('created'), reverse=True)

    object_list = sorted(sorted((object_from_list),
    key=attrgetter('created'),reverse=True),
    key=attrgetter('read_by_user_to'))

    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    try:
        messages_ = paginator.page(page)
    except PageNotAnInteger:
        messages_ = paginator.page(1)
    except EmptyPage:
        messages_ = paginator.page(paginator.num_pages)
    context = {
        'messages_': messages_,
        'type' : 'sent',
    }
    return render(request, 'my_sharing_hub/x_messages.html', context)


def _decorate_inbox_message(message, user):
    message.inbox_direction = 'Sent' if message.user_from_id == user.id else 'Received'
    message.inbox_is_unread = message.user_to_id == user.id and not message.read_by_user_to
    if message.is_system_generated:
        message.inbox_counterparty = 'System'
    elif message.user_from_id == user.id:
        message.inbox_counterparty = message.user_to.get_full_name().strip() or message.user_to.username
    else:
        message.inbox_counterparty = message.user_from.get_full_name().strip() or message.user_from.username
    if message.transaction and message.transaction.order_passive and message.transaction.order_passive.product:
        message.inbox_item_name = message.transaction.order_passive.product.name
    else:
        message.inbox_item_name = ''
    message.inbox_transaction_reference = message.transaction.transaction_reference if message.transaction else ''
    message.inbox_preview = (message.description or '').strip() or (message.subject or 'Message')
    return message


@login_required
def inbox(request):
    user = request.user
    object_list = list(
        TransactionMessage.objects.filter(Q(user_from=user) | Q(user_to=user))
        .select_related('transaction', 'transaction__order_passive__product', 'user_from', 'user_to')
        .prefetch_related('txn_msg_img')
    )
    object_list = sorted(sorted(object_list, key=attrgetter('created'), reverse=True), key=lambda message: 0 if message.user_to_id == user.id and not message.read_by_user_to else 1)
    object_list = [_decorate_inbox_message(message, user) for message in object_list]

    paginator = Paginator(object_list, 10)
    page = request.GET.get('page')
    try:
        messages_ = paginator.page(page)
    except PageNotAnInteger:
        messages_ = paginator.page(1)
    except EmptyPage:
        messages_ = paginator.page(paginator.num_pages)
    context = {
        'messages_': messages_,
        'type': 'inbox',
    }
    return render(request, 'my_sharing_hub/inbox.html', context)


@login_required
def pending_actions(request):    
    context = {
    }
    return render(request, 'my_sharing_hub/pending_actions.html', context)

@login_required
def open_orders(request):
    user = request.user
    object_list = user.order_set.filter(status='A').order_by('-amended')
    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    orderTransactions = {}
    orders = paginator.get_page(page)

    for order in orders:
        orderTransactions[order.id] = order.rel_order_passive.all()
    context = {
        'page' : page,
        'orders' : orders,
        'type' : 'open',
        'orderTransactions': orderTransactions,
    }
    # return redirect('/navigation/seeAll/')
    return render(request, 'my_sharing_hub/x_orders.html', context)

@login_required
def closed_orders(request):
    user = request.user
    object_list = user.order_set.filter(status='X').order_by('-amended')
    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    orderTransactions = {}
    orders = paginator.get_page(page)
    
    for order in orders:
        orderTransactions[order.id] = order.rel_order_passive.all()

    context = {
        'page' : page,
        'orders' : orders,
        'type' : 'closed',
        'orderTransactions': orderTransactions,
    }
    # return redirect('/navigation/seeAll/')
    return render(request, 'my_sharing_hub/x_orders.html', context)


@login_required
def copy_order_as_new(request, order_id):
    source_order = get_object_or_404(Order, id=order_id, user=request.user)

    copied_order = Order.objects.create(
        product=source_order.product,
        user=request.user,
        direction=source_order.direction,
        expiry_date=timezone.now() + timedelta(days=30),
        quantity=source_order.quantity,
        productIsNew=source_order.productIsNew,
        price_type=source_order.price_type,
        status=Order.ACTIVE,
        price=source_order.price,
        currency=source_order.currency,
        latitude=source_order.latitude,
        longitude=source_order.longitude,
        postcode=source_order.postcode,
        radius_km=source_order.radius_km,
        guaranteed=source_order.guaranteed,
        description=source_order.description,
        additional_comments=source_order.additional_comments,
        let_visibility=source_order.let_visibility,
        deposit=source_order.deposit,
        mates_rates=source_order.mates_rates,
        mates_deposit=source_order.mates_deposit,
        collection_policy=source_order.collection_policy,
        delivery_cost=source_order.delivery_cost,
        collection_details=source_order.collection_details,
        max_rental_days=source_order.max_rental_days,
    )

    source_images = source_order.images.filter(active=True)
    for image in source_images:
        OrderImage.objects.create(
            order=copied_order,
            image=image.image,
            user=request.user,
            active=True,
            first_image=image.first_image,
            is_main=image.is_main,
        )

    for band in source_order.price_bands.all():
        LetPriceBand.objects.create(
            order=copied_order,
            duration_days=band.duration_days,
            price_per_day=band.price_per_day,
        )

    source_blocked_dates = source_order.blocked_dates.filter(
        reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.HANDOVER_UNAVAILABLE]
    )
    for blocked_date in source_blocked_dates:
        OrderBlockedDate.objects.create(
            order=copied_order,
            date=blocked_date.date,
            reason=blocked_date.reason,
        )

    messages.success(request, 'Closed listing copied as a new open listing. You can amend it below.')
    return redirect('transaction:edit_order', order_id=copied_order.id)

@login_required
def open_transactions(request):
    user = request.user
    today = timezone.localdate()

    def _requires_my_action(txn_obj):
        """Return True only when the logged-in user is the next actor for this transaction AND the date is right."""
        is_lender_local = (txn_obj.user_passive_id == user.id)
        is_renter_local = (txn_obj.user_aggressive_id == user.id)
        status = txn_obj.transaction_status

        if status == txn_obj.RENTAL_ENQUIRY:
            # Pre-rental action; no date check needed
            return is_lender_local

        if status == txn_obj.RENTAL_AGREED:
            lender_done = bool(txn_obj.lender_agreed_at)
            renter_done = bool(txn_obj.renter_agreed_at)

            if not lender_done and not renter_done:
                # Both parties need to sign; no date restriction
                return is_lender_local or is_renter_local
            if lender_done and not renter_done:
                # Renter needs to sign; no date restriction
                return is_renter_local
            if renter_done and not lender_done:
                # Lender needs to sign; no date restriction
                return is_lender_local

            # Both signed; check card setup or rental start date
            if txn_obj.deposit_card_setup_status != txn_obj.CARD_READY:
                return is_renter_local
            
            # Lender ready to initiate: only red on or after rental_start_date
            if is_lender_local and txn_obj.rental_start_date:
                return today >= txn_obj.rental_start_date
            return False

        if status == txn_obj.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            # Renter marks as returned: only red on or after rental_end_date
            if is_renter_local and txn_obj.rental_end_date:
                return today >= txn_obj.rental_end_date
            return False

        if status == txn_obj.RENTAL_RETURNED_DEPOSIT_PENDING:
            # Lender resolves deposit; no date restriction
            return is_lender_local

        return False

    closed_statuses = [
        Transaction.CANCEL_ACCEPTED,
        Transaction.DEPOSIT_RETURNED,
        Transaction.DEPOSIT_REDUCED,
        Transaction.MEDIATION_REQUIRED,
    ]
    object_pass_list = user.rel_from_set.exclude(transaction_status__in=closed_statuses)
    object_agg_list = user.rel_to_set.exclude(transaction_status__in=closed_statuses)
    # object_list =  user.rel_to_set.filter()
    object_list = sorted(
    (chain(object_pass_list, object_agg_list)),
    key=attrgetter('amended'), reverse=True)

    active_view = request.GET.get('view', 'list')
    if active_view not in ('list', 'calendar'):
        active_view = 'list'

    month_param = (request.GET.get('month') or '').strip()
    day_param = (request.GET.get('day') or '').strip()
    today = timezone.localdate()
    try:
        if month_param:
            calendar_year, calendar_month = [int(part) for part in month_param.split('-', 1)]
            month_anchor = date(calendar_year, calendar_month, 1)
        else:
            month_anchor = date(today.year, today.month, 1)
    except Exception:
        month_anchor = date(today.year, today.month, 1)

    selected_date = None
    if day_param:
        try:
            selected_date = datetime.strptime(day_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date = None
    if selected_date is None and active_view == 'calendar':
        if today.month == month_anchor.month and today.year == month_anchor.year:
            selected_date = today
        else:
            selected_date = month_anchor

    cal = calendar.Calendar(firstweekday=0)
    month_days = list(cal.itermonthdates(month_anchor.year, month_anchor.month))
    month_start = month_anchor
    month_end = month_days[-1]

    day_map = {}
    for txn in object_list:
        txn.requires_my_action = _requires_my_action(txn)
        # Count unread messages for this transaction
        txn.unread_message_count = TransactionMessage.objects.filter(
            transaction=txn,
            user_to=user,
            read_by_user_to=False
        ).count()
        start_date = txn.rental_start_date
        end_date = txn.rental_end_date or start_date
        if not start_date:
            continue

        range_start = max(start_date, month_start)
        range_end = min(end_date, month_end)
        if range_end < range_start:
            continue

        is_lending = (txn.user_passive_id == user.id)
        current_day = range_start
        while current_day <= range_end:
            slot = day_map.setdefault(current_day, {'lending': 0, 'borrowing': 0, 'pending': False})
            if is_lending:
                slot['lending'] += 1
            else:
                slot['borrowing'] += 1
            if txn.requires_my_action:
                slot['pending'] = True
            current_day += timedelta(days=1)

    calendar_weeks = []
    for week in cal.monthdatescalendar(month_anchor.year, month_anchor.month):
        week_cells = []
        for day in week:
            slot = day_map.get(day, {'lending': 0, 'borrowing': 0, 'pending': False})
            week_cells.append({
                'date': day,
                'in_month': day.month == month_anchor.month,
                'is_today': day == today,
                'lending': slot['lending'],
                'borrowing': slot['borrowing'],
                'pending': slot['pending'],
            })
        calendar_weeks.append(week_cells)

    prev_month = (month_anchor.replace(day=1) - timedelta(days=1)).replace(day=1)
    if month_anchor.month == 12:
        next_month = date(month_anchor.year + 1, 1, 1)
    else:
        next_month = date(month_anchor.year, month_anchor.month + 1, 1)

    filtered_list = object_list
    if active_view == 'calendar' and selected_date is not None:
        filtered_list = [
            txn for txn in object_list
            if txn.rental_start_date
            and (txn.rental_start_date <= selected_date <= (txn.rental_end_date or txn.rental_start_date))
        ]

    paginator = Paginator(filtered_list, 10) # per page
    page = request.GET.get('page')
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    context = {
        'page' : page,
        'type' : 'open',
        'transactions' : transactions,
        'active_view': active_view,
        'calendar_weeks': calendar_weeks,
        'calendar_month_label': month_anchor.strftime('%B %Y'),
        'calendar_month_key': month_anchor.strftime('%Y-%m'),
        'calendar_prev_month_key': prev_month.strftime('%Y-%m'),
        'calendar_next_month_key': next_month.strftime('%Y-%m'),
        'selected_day_key': selected_date.strftime('%Y-%m-%d') if selected_date else '',
        'selected_day_label': selected_date.strftime('%b %d, %Y') if selected_date else '',
        'urlencode': (
            f'view=calendar&month={month_anchor.strftime("%Y-%m")}&day={selected_date.strftime("%Y-%m-%d")}'
            if active_view == 'calendar' and selected_date
            else 'view=list'
        ),
    }
    # return redirect('/navigation/seeAll/')
    getUserTransactions.delay(int(request.user.id))
    return render(request, 'my_sharing_hub/x_transactions.html', context)

# TODO
@login_required
def closed_transactions(request):
    user = request.user
    closed_statuses = [
        Transaction.CANCEL_ACCEPTED,
        Transaction.DEPOSIT_RETURNED,
        Transaction.DEPOSIT_REDUCED,
        Transaction.MEDIATION_REQUIRED,
    ]
    object_pass_list = user.rel_from_set.filter(transaction_status__in=closed_statuses)
    object_agg_list = user.rel_to_set.filter(transaction_status__in=closed_statuses)
    # object_list =  user.rel_to_set.filter()
    object_list =  sorted(
    (chain(object_pass_list, object_agg_list)),
    key=attrgetter('amended'), reverse=True)
    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    context = {
        'page' : page,
        'type' : 'closed',
        'transactions' : transactions,
    }
    # return redirect('/navigation/seeAll/')
    return render(request, 'my_sharing_hub/x_transactions.html', context)

@login_required
@ajax_required
def expand_message(request):
    message_id = request.GET.get('message_id', None)
    message = get_object_or_404(TransactionMessage, id=message_id)
    if request.user == message.user_to and message.read_by_user_to == False:
        message.read_by_user_to = True
        message.save()
    content = {
        'from': 'System' if message.is_system_generated else message.user_from.username,
        'to' : message.user_to.username,
        'subject': message.subject,
        'body' : message.description,
        'created' : message.created.strftime("%Y-%m-%d %H:%M"),
    }
    return JsonResponse(content)


