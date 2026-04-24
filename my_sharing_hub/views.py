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

@login_required
def pending_actions(request):    
    context = {
    }
    return render(request, 'my_sharing_hub/pending_actions.html', context)

@login_required
def open_orders(request):
    user = request.user
    object_list = user.order_set.filter(status='A')
    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    orderTransactions = {}

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

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
    object_list = user.order_set.filter(status='X')
    paginator = Paginator(object_list, 10) # per page
    page = request.GET.get('page')
    orderTransactions = {}
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    
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
def open_transactions(request):
    user = request.user
    object_pass_list = user.rel_from_set.exclude(transaction_status='COMP').exclude(transaction_status='VOID')
    object_agg_list = user.rel_to_set.exclude(transaction_status='COMP').exclude(transaction_status='VOID')
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
        'type' : 'open',
        'transactions' : transactions,
    }
    # return redirect('/navigation/seeAll/')
    getUserTransactions.delay(int(request.user.id))
    return render(request, 'my_sharing_hub/x_transactions.html', context)

# TODO
@login_required
def closed_transactions(request):
    user = request.user
    object_pass_list = user.rel_from_set.filter(Q(transaction_status='COMP') | Q(transaction_status='VOID'))
    object_agg_list = user.rel_to_set.filter(Q(transaction_status='COMP') | Q(transaction_status='VOID'))
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
        'from': message.user_from.username,
        'to' : message.user_to.username,
        'subject': message.subject,
        'body' : message.description,
        'created' : message.created.strftime("%Y-%m-%d %H:%M"),
    }
    return JsonResponse(content)


