from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render

from rentalution.context_processors import get_transaction_notification_payload

# Create your views here.


@login_required
def transaction_notifications_json(request):
	payload = get_transaction_notification_payload(request.user)
	return JsonResponse({
		'txn_notice_count': payload['txn_notice_count'],
		'txn_notice_items': payload['txn_notice_items'],
	})


def apple_app_site_association(request):
	"""Serve the iOS Universal Links association only when release signing is configured."""
	team_id = getattr(settings, 'APPLE_APP_LINK_TEAM_ID', '')
	if not team_id:
		return JsonResponse({'detail': 'Apple app-link association is not configured.'}, status=404)
	return JsonResponse({
		'applinks': {
			'apps': [],
			'details': [{
				'appID': f'{team_id}.com.rentalution.mobile',
				'paths': ['/app/payouts/*'],
			}],
		},
	})


def android_asset_links(request):
	"""Serve the Android App Links association only for the configured release certificate."""
	fingerprint = getattr(settings, 'ANDROID_APP_LINK_SHA256', '')
	if not fingerprint:
		return JsonResponse({'detail': 'Android app-link association is not configured.'}, status=404)
	return JsonResponse([{
		'relation': ['delegate_permission/common.handle_all_urls'],
		'target': {
			'namespace': 'android_app',
			'package_name': 'com.rentalution.mobile',
			'sha256_cert_fingerprints': [fingerprint],
		},
	},], safe=False)


def mobile_payout_return(request):
	"""Browser fallback for the verified app-link payout return URL."""
	return redirect('/my_rentalution/my_details/?tab=payouts')
