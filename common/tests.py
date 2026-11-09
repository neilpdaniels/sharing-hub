from types import SimpleNamespace
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

from common.helpers import is_profile_kyc_verified
from common.phone_utils import (
	format_to_e164,
	is_valid_uk_phone,
	mask_mobile_number,
	normalize_to_domestic,
)
from common.log_review import LogEvent, build_report, normalise_signature, report_as_text
from common.security import verify_turnstile_token
from common.models import Category, ModerationReport, Order, Product
from common.moderation import create_report, notify_staff_of_report, resolve_report
from account.profanity import contains_blocked_word
from transaction.models import Transaction, TransactionMessage


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


class ModerationTests(TestCase):
	def setUp(self):
		self.reporter = User.objects.create_user(username='reporter', email='reporter@example.test', password='x')
		self.owner = User.objects.create_user(username='owner', email='owner@example.test', password='x')
		self.moderator = User.objects.create_user(username='moderator', email='mod@example.test', password='x', is_staff=True)
		category = Category.objects.create(title='Tools')
		product = Product.objects.create(category_id=category, name='Drill')
		with patch('common.models.updateSummaryPrices.delay'):
			self.order = Order.objects.create(
				product=product, user=self.owner, direction=Order.TO_LET,
				expiry_date=django_timezone.now() + timedelta(days=30),
				status=Order.ACTIVE, price=10, description='A drill',
			)

	@patch('common.moderation.notify_staff_of_report')
	def test_serious_listing_report_hides_then_dismiss_restores(self, _notify):
		report = create_report(
			reporter=self.reporter, target_type='listing', target_id=self.order.id,
			reason=ModerationReport.REASON_ILLEGAL, details='Unsafe item',
		)
		self.order.refresh_from_db()
		self.assertEqual(self.order.status, Order.EXPIRED)
		self.assertTrue(report.content_hidden_pending_review)

		resolve_report(report, outcome=ModerationReport.OUTCOME_DISMISS, moderator=self.moderator)
		self.order.refresh_from_db()
		self.assertEqual(self.order.status, Order.ACTIVE)

	@patch('common.moderation.notify_staff_of_report')
	def test_confirmed_report_removes_listing_and_blocks_owner(self, _notify):
		report = create_report(
			reporter=self.reporter, target_type='listing', target_id=self.order.id,
			reason=ModerationReport.REASON_SCAM,
		)
		resolve_report(report, outcome=ModerationReport.OUTCOME_REMOVE_AND_BLOCK, moderator=self.moderator)
		self.owner.refresh_from_db(); self.order.refresh_from_db()
		self.assertFalse(self.owner.is_active)
		self.assertEqual(self.order.status, Order.EXPIRED)

	@patch('common.moderation.notify_staff_of_report')
	def test_user_report_does_not_preemptively_disable_user(self, _notify):
		report = create_report(
			reporter=self.reporter, target_type='user', target_id=self.owner.id,
			reason=ModerationReport.REASON_THREAT,
		)
		self.owner.refresh_from_db()
		self.assertTrue(self.owner.is_active)
		self.assertFalse(report.content_hidden_pending_review)

	@patch('common.moderation.notify_staff_of_report')
	def test_transaction_message_report_hides_then_dismiss_restores(self, _notify):
		transaction = Transaction.objects.create(
			user_passive=self.owner,
			user_aggressive=self.reporter,
			order_passive=self.order,
			product=self.order.product,
			rental_start_date=django_timezone.localdate() + timedelta(days=1),
			rental_end_date=django_timezone.localdate() + timedelta(days=2),
			price=10,
			deposit=0,
			current_spot_value=10,
			price_as_pct_spot_value=100,
		)
		message = TransactionMessage.objects.create(
			user_from=self.owner,
			user_to=self.reporter,
			transaction=transaction,
			description='Threatening message',
		)

		report = create_report(
			reporter=self.reporter,
			target_type='message',
			target_id=message.id,
			reason=ModerationReport.REASON_THREAT,
		)
		message.refresh_from_db()
		self.assertTrue(message.moderation_hidden)

		self.client.force_login(self.reporter)
		response = self.client.get(reverse('my_rentalution:expand_message'), {'message_id': message.id})
		self.assertEqual(response.status_code, 404)

		resolve_report(report, outcome=ModerationReport.OUTCOME_DISMISS, moderator=self.moderator)
		message.refresh_from_db()
		self.assertFalse(message.moderation_hidden)
		response = self.client.get(reverse('my_rentalution:expand_message'), {'message_id': message.id})
		self.assertTrue(response.json()['can_report'])

		message.is_system_generated = True
		message.save(update_fields=('is_system_generated',))
		response = self.client.get(reverse('my_rentalution:expand_message'), {'message_id': message.id})
		self.assertFalse(response.json()['can_report'])
		with self.assertRaisesRegex(ValueError, 'system messages cannot be reported'):
			create_report(
				reporter=self.reporter,
				target_type='message',
				target_id=message.id,
				reason=ModerationReport.REASON_THREAT,
			)

	@override_settings(ADMINS=(), DISCORD_MODERATION_WEBHOOK_URL='')
	@patch('common.moderation.send_mail')
	def test_active_staff_receive_report_email(self, send_mail):
		report = ModerationReport.objects.create(
			reporter=self.reporter, target_owner=self.owner, target_type='user',
			target_id=self.owner.id, reason=ModerationReport.REASON_OTHER,
		)
		notify_staff_of_report(report)
		self.assertEqual(send_mail.call_args.args[3], ['mod@example.test'])

	def test_web_report_form_is_available_and_creates_report(self):
		self.client.force_login(self.reporter)
		url = reverse('report_content')
		response = self.client.get(url, {'target_type': 'listing', 'target_id': self.order.id, 'next': '/'})
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'cf-turnstile')
		with patch('common.moderation.notify_staff_of_report'):
			response = self.client.post(url, {
				'target_type': 'listing', 'target_id': self.order.id,
				'reason': ModerationReport.REASON_SCAM, 'details': 'Looks fake', 'next': '/',
			})
		self.assertEqual(response.status_code, 302)
		self.assertTrue(ModerationReport.objects.filter(reporter=self.reporter, target_id=self.order.id).exists())

	def test_anonymous_report_requires_turnstile(self):
		url = reverse('report_content')
		response = self.client.get(url, {'target_type': 'listing', 'target_id': self.order.id, 'next': '/'})
		self.assertContains(response, 'cf-turnstile')

		with patch('common.views.verify_turnstile_token', return_value=False):
			response = self.client.post(url, {
				'target_type': 'listing', 'target_id': self.order.id,
				'reason': ModerationReport.REASON_SCAM, 'next': '/',
			})
		self.assertEqual(response.status_code, 400)
		self.assertFalse(ModerationReport.objects.exists())

	def test_verified_anonymous_visitor_can_report_public_listing(self):
		url = reverse('report_content')
		with (
			patch('common.views.verify_turnstile_token', return_value=True),
			patch('common.moderation.notify_staff_of_report'),
		):
			response = self.client.post(url, {
				'target_type': 'listing', 'target_id': self.order.id,
				'reason': ModerationReport.REASON_SCAM,
				'details': 'Anonymous concern', 'next': '/',
				'cf-turnstile-response': 'verified-token',
			}, REMOTE_ADDR='203.0.113.8')

		self.assertEqual(response.status_code, 302)
		report = ModerationReport.objects.get()
		self.assertIsNone(report.reporter)
		self.assertEqual(len(report.anonymous_fingerprint), 40)
		self.assertNotIn('203.0.113.8', report.anonymous_fingerprint)

	def test_anonymous_visitor_must_sign_in_to_report_private_message(self):
		response = self.client.get(reverse('report_content'), {
			'target_type': 'message', 'target_id': 1, 'next': '/',
		})
		self.assertEqual(response.status_code, 302)
		self.assertIn('/account/login/', response.url)

	def test_inbox_redirects_to_received_messages(self):
		self.client.force_login(self.reporter)
		response = self.client.get(reverse('my_rentalution:inbox'))
		self.assertRedirects(
			response,
			reverse('my_rentalution:messages_received'),
			fetch_redirect_response=False,
		)
		response = self.client.get(reverse('my_rentalution:messages_received'))
		self.assertEqual(response.status_code, 200)

	def test_message_profanity_filter_has_local_fallback(self):
		self.assertTrue(contains_blocked_word('This is bullshit'))
		self.assertFalse(contains_blocked_word('Can I collect this tomorrow?'))


class ProductionLogReviewTests(SimpleTestCase):
	@patch('common.log_review._docker_command')
	def test_docker_source_collects_stderr_error_lines(self, docker_command):
		def docker_output(args, **_kwargs):
			if args[0] == 'ps':
				return 'container-id\n'
			return '2026-10-27T10:00:00Z ERROR failed to send email to alice@example.com\n'

		docker_command.side_effect = docker_output
		report = build_report(hours=1, source='docker')

		self.assertEqual(report['status'], 'ACTION_REQUIRED')
		self.assertEqual(report['issues'][0]['count'], 1)
		self.assertIn('[EMAIL]', report['issues'][0]['fingerprint'])
		self.assertEqual(docker_command.call_count, 10)

	@patch('common.log_review._docker_command')
	def test_docker_timeout_becomes_critical_issue_not_command_failure(self, docker_command):
		docker_command.side_effect = RuntimeError('Docker log source failed: command timed out')
		report = build_report(hours=1, source='docker')

		self.assertEqual(report['status'], 'CRITICAL')
		self.assertEqual(len(report['issues']), 5)
		self.assertTrue(all(issue['severity'] == 'CRITICAL' for issue in report['issues']))

	def test_groups_events_redacts_data_and_escalates_only_known_critical_failures(self):
		events = [
			LogEvent('2026-10-27T10:00:00+00:00', 'web', 'ERROR user=alice@example.com request=123456 failed'),
			LogEvent('2026-10-27T10:01:00+00:00', 'web', 'ERROR user=bob@example.com request=987654 failed'),
			LogEvent('2026-10-27T10:02:00+00:00', 'worker', 'CRITICAL no space left on device'),
		]
		with patch('common.log_review._loki_events', return_value=events):
			report = build_report(
				hours=6,
				now=datetime(2026, 10, 27, 12, tzinfo=timezone.utc),
				suppressions_path='/tmp/non-existent-log-review-suppressions.json',
				query_chunk_minutes=360,
				source='loki',
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
			with patch('common.log_review._loki_events', return_value=[event]):
				report = build_report(hours=1, suppressions_path=path, query_chunk_minutes=60, source='loki')

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


class ListingTitleTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='listing-title', password='x')
		self.category = Category.objects.create(title='Fancy dress')
		self.product = Product.objects.create(
			category_id=self.category,
			name='Adult fancy dress',
		)

	def test_listing_title_is_used_in_preference_to_generic_product_name(self):
		order = Order.objects.create(
			product=self.product,
			user=self.user,
			direction=Order.TO_LET,
			expiry_date=django_timezone.now() + timedelta(days=7),
			status=Order.ACTIVE,
			price=10,
			listing_title='Cow costume',
		)
		self.assertEqual(order.display_name, 'Cow costume')

	def test_legacy_listing_falls_back_to_its_product_name(self):
		order = Order.objects.create(
			product=self.product,
			user=self.user,
			direction=Order.TO_LET,
			expiry_date=django_timezone.now() + timedelta(days=7),
			status=Order.ACTIVE,
			price=10,
		)
		self.assertEqual(order.display_name, 'Adult fancy dress')
