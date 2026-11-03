from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from django.utils.http import url_has_allowed_host_and_scheme

from common.moderation import create_report
from common.models import ModerationReport
from rentalution.context_processors import get_transaction_notification_payload

# Create your views here.


@require_GET
def healthcheck(request):
	"""Minimal unauthenticated liveness probe for external uptime monitoring."""
	return JsonResponse({'status': 'ok'})


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


@login_required
@require_http_methods(['GET', 'POST'])
def report_content(request):
	"""Shared, deliberately low-key report form for website content."""
	target_type = request.POST.get('target_type') or request.GET.get('target_type', '')
	target_id = request.POST.get('target_id') or request.GET.get('target_id', '')
	next_url = request.POST.get('next') or request.GET.get('next') or '/'
	if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
		next_url = '/'
	if target_type not in dict(ModerationReport.TARGET_CHOICES):
		return JsonResponse({'detail': 'Invalid report target.'}, status=400)
	try:
		target_id = int(target_id)
	except (TypeError, ValueError):
		return JsonResponse({'detail': 'Invalid report target.'}, status=400)

	if request.method == 'POST':
		try:
			create_report(
				reporter=request.user,
				target_type=target_type,
				target_id=target_id,
				reason=request.POST.get('reason', ''),
				details=request.POST.get('details', ''),
			)
		except (ValueError, PermissionError) as exc:
			messages.error(request, str(exc))
		else:
			messages.success(request, 'Thank you. Your report has been sent to the Rentalution moderation team.')
		return redirect(next_url)

	return render(request, 'common/report_content.html', {
		'target_type': target_type,
		'target_id': target_id,
		'next': next_url,
		'reasons': ModerationReport.REASON_CHOICES,
	})
