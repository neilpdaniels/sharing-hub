from types import SimpleNamespace
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from common.helpers import is_profile_kyc_verified
from common.phone_utils import (
	format_to_e164,
	is_valid_uk_phone,
	mask_mobile_number,
	normalize_to_domestic,
)
from common.log_review import LogEvent, build_report, normalise_signature, report_as_text
from common.security import verify_turnstile_token


class PhoneUtilsTests(TestCase):
	def test_format_to_e164_from_domestic(self):
		self.assertEqual(format_to_e164('07700 900123'), '+447700900123')

	def test_format_to_e164_from_international_00(self):
		self.assertEqual(format_to_e164('00447700900123'), '+447700900123')

	def test_normalize_to_domestic_from_e164(self):
		self.assertEqual(normalize_to_domestic('+44 7700 900123'), '07700900123')

	def test_mask_mobile_number(self):
		self.assertEqual(mask_mobile_number('07700 900123'), '******0123')

	def test_mask_mobile_number_for_short_input(self):
		self.assertEqual(mask_mobile_number('12'), 'your mobile number')

	def test_is_valid_uk_phone(self):
		self.assertTrue(is_valid_uk_phone('07700900123'))
		self.assertTrue(is_valid_uk_phone('+447700900123'))
		self.assertTrue(is_valid_uk_phone('00447700900123'))
		self.assertFalse(is_valid_uk_phone('+14155552671'))
		self.assertFalse(is_valid_uk_phone('02079460000'))
		self.assertFalse(is_valid_uk_phone('12345'))


class ProductionLogReviewTests(SimpleTestCase):
	def test_groups_events_redacts_data_and_escalates_only_known_critical_failures(self):
		events = [
			LogEvent('2026-10-27T10:00:00+00:00', 'web', 'ERROR user=alice@example.com request=123456 failed'),
			LogEvent('2026-10-27T10:01:00+00:00', 'web', 'ERROR user=bob@example.com request=987654 failed'),
			LogEvent('2026-10-27T10:02:00+00:00', 'worker', 'CRITICAL no space left on device'),
		]
		with patch('common.log_review._loki_events', side_effect=[events[:2], events[2:]]):
			report = build_report(
				hours=6,
				now=datetime(2026, 10, 27, 12, tzinfo=timezone.utc),
				suppressions_path='/tmp/non-existent-log-review-suppressions.json',
				query_chunk_minutes=360,
			)

		self.assertEqual(report['status'], 'CRITICAL')
		self.assertEqual(report['issues'][0]['severity'], 'CRITICAL')
		self.assertIn('[EMAIL]', report_as_text(report))
		self.assertNotIn('alice@example.com', report_as_text(report))

	def test_suppression_is_explicit_and_reported(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / 'suppressions.json'
			path.write_text(json.dumps([{
				'pattern': 'benign probe disconnect',
				'reason': 'Known harmless load-balancer disconnect',
			}]), encoding='utf-8')
			event = LogEvent('2026-10-27T10:00:00+00:00', 'nginx-error', 'benign probe disconnect')
			with patch('common.log_review._loki_events', side_effect=[[event], []]):
				report = build_report(hours=1, suppressions_path=path, query_chunk_minutes=60)

		self.assertEqual(report['status'], 'OK')
		self.assertEqual(report['suppressed'], [{
			'reason': 'Known harmless load-balancer disconnect', 'count': 1,
		}])

	def test_signature_redacts_secrets(self):
		signature = normalise_signature('2026-10-27 10:00:00 token=super-secret-value user@example.com')
		self.assertIn('[REDACTED]', signature)
		self.assertIn('[EMAIL]', signature)


class KycHelperTests(TestCase):
	def test_is_verified_when_stripe_verified(self):
		profile = SimpleNamespace(
			stripe_identity_verified=True,
			email_confirmed=False,
			mobile_verified=False,
			address_verified=False,
		)
		self.assertTrue(is_profile_kyc_verified(profile))

	def test_is_verified_when_baseline_complete(self):
		profile = SimpleNamespace(
			stripe_identity_verified=False,
			email_confirmed=True,
			mobile_verified=True,
			address_verified=True,
		)
		self.assertTrue(is_profile_kyc_verified(profile))

	def test_is_not_verified_when_incomplete(self):
		profile = SimpleNamespace(
			stripe_identity_verified=False,
			email_confirmed=True,
			mobile_verified=False,
			address_verified=True,
		)
		self.assertFalse(is_profile_kyc_verified(profile))


class SecurityUtilsTests(TestCase):
	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='', TURNSTILE_HOSTNAMES=frozenset({'rentalution.co.uk'}))
	def test_turnstile_rejects_when_secret_is_not_configured(self):
		self.assertFalse(verify_turnstile_token('any-token', expected_action='registration'))

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret', TURNSTILE_HOSTNAMES=frozenset({'rentalution.co.uk'}))
	def test_turnstile_rejects_empty_token(self):
		self.assertFalse(verify_turnstile_token('', expected_action='registration'))

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret', TURNSTILE_HOSTNAMES=frozenset({'rentalution.co.uk'}))
	@patch('common.security.requests.post')
	def test_turnstile_accepts_success_payload(self, mock_post):
		mock_response = Mock()
		mock_response.json.return_value = {
			'success': True,
			'action': 'registration',
			'hostname': 'rentalution.co.uk',
		}
		mock_post.return_value = mock_response

		self.assertTrue(verify_turnstile_token('token-123', '127.0.0.1', expected_action='registration'))
		mock_post.assert_called_once()

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret', TURNSTILE_HOSTNAMES=frozenset({'rentalution.co.uk'}))
	@patch('common.security.requests.post', side_effect=Exception('network down'))
	def test_turnstile_returns_false_on_exception(self, _mock_post):
		self.assertFalse(verify_turnstile_token('token-123', expected_action='registration'))

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret', TURNSTILE_HOSTNAMES=frozenset({'rentalution.co.uk'}))
	@patch('common.security.requests.post')
	def test_turnstile_rejects_wrong_action_or_hostname(self, mock_post):
		mock_response = Mock()
		mock_response.json.return_value = {
			'success': True,
			'action': 'login',
			'hostname': 'attacker.example',
		}
		mock_post.return_value = mock_response

		self.assertFalse(verify_turnstile_token('token-123', expected_action='registration'))


class MobilePayoutReturnLinkTests(SimpleTestCase):
	"""The public app-link files must never advertise unsigned app builds."""

	@override_settings(APPLE_APP_LINK_TEAM_ID='')
	def test_apple_association_is_unavailable_without_a_team_id(self):
		response = self.client.get(reverse('apple_app_site_association'))
		self.assertEqual(response.status_code, 404)

	@override_settings(APPLE_APP_LINK_TEAM_ID='ABCDE12345')
	def test_apple_association_contains_the_release_app_identifier(self):
		response = self.client.get(reverse('apple_app_site_association'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json()['applinks']['details'][0]['appID'],
			'ABCDE12345.com.rentalution.mobile',
		)

	@override_settings(ANDROID_APP_LINK_SHA256='AA:BB:CC')
	def test_android_association_contains_the_release_certificate(self):
		response = self.client.get(reverse('android_asset_links'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json()[0]['target']['sha256_cert_fingerprints'],
			['AA:BB:CC'],
		)

	def test_payout_return_has_a_safe_browser_fallback(self):
		response = self.client.get(reverse('mobile_payout_return'))
		self.assertRedirects(
			response,
			'/my_rentalution/my_details/?tab=payouts',
			fetch_redirect_response=False,
		)
