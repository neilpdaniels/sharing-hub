from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from rentalution.context_processors import get_transaction_notification_payload

# Create your views here.


@login_required
def transaction_notifications_json(request):
	payload = get_transaction_notification_payload(request.user)
	return JsonResponse({
		'txn_notice_count': payload['txn_notice_count'],
		'txn_notice_items': payload['txn_notice_items'],
	})
