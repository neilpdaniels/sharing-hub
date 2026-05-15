from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from common.helpers import is_profile_kyc_verified
from common.phone_utils import (
	format_to_e164,
	is_valid_uk_phone,
	mask_mobile_number,
	normalize_to_domestic,
)
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
		self.assertFalse(is_valid_uk_phone('12345'))


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
	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='')
	def test_turnstile_skips_validation_without_secret(self):
		self.assertTrue(verify_turnstile_token('any-token'))

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret')
	def test_turnstile_rejects_empty_token(self):
		self.assertFalse(verify_turnstile_token(''))

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret')
	@patch('common.security.requests.post')
	def test_turnstile_accepts_success_payload(self, mock_post):
		mock_response = Mock()
		mock_response.json.return_value = {'success': True}
		mock_post.return_value = mock_response

		self.assertTrue(verify_turnstile_token('token-123', '127.0.0.1'))
		mock_post.assert_called_once()

	@override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='secret')
	@patch('common.security.requests.post', side_effect=Exception('network down'))
	def test_turnstile_returns_false_on_exception(self, _mock_post):
		self.assertFalse(verify_turnstile_token('token-123'))
