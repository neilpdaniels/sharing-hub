from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.forms import AvatarEditForm, UserRegistrationStartForm
from account.models import Profile


class UserRegistrationStartFormTests(TestCase):
	def _valid_payload(self):
		adult_dob = (date.today() - timedelta(days=365 * 25)).strftime('%d-%m-%Y')
		return {
			'first_name': 'Neil',
			'last_name': 'Daniels',
			'username': 'neil_123',
			'email': 'neil@example.com',
			'date_of_birth': adult_dob,
			'mobile_number': '+44 7700 900123',
			'house_name_number': '10',
			'address_line_1': 'Main Street',
			'address_line_2': '',
			'town': 'London',
			'county': 'Greater London',
			'postcode': 'SW1A1AA',
		}

	def test_normalizes_mobile_number_to_domestic(self):
		form = UserRegistrationStartForm(data=self._valid_payload())

		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data['mobile_number'], '07700900123')

	def test_rejects_duplicate_username(self):
		User.objects.create_user(username='neil_123', email='a@example.com', password='x')
		form = UserRegistrationStartForm(data=self._valid_payload())

		self.assertFalse(form.is_valid())
		self.assertIn('username', form.errors)

	def test_rejects_blocked_username(self):
		payload = self._valid_payload()
		payload['username'] = 'shit_head'
		form = UserRegistrationStartForm(data=payload)

		self.assertFalse(form.is_valid())
		self.assertIn('username', form.errors)

	def test_rejects_duplicate_email_case_insensitive(self):
		User.objects.create_user(username='other_user', email='NEIL@example.com', password='x')
		form = UserRegistrationStartForm(data=self._valid_payload())

		self.assertFalse(form.is_valid())
		self.assertIn('email', form.errors)

	def test_rejects_underage_user(self):
		payload = self._valid_payload()
		underage_dob = (date.today() - timedelta(days=365 * 16)).strftime('%d-%m-%Y')
		payload['date_of_birth'] = underage_dob
		form = UserRegistrationStartForm(data=payload)

		self.assertFalse(form.is_valid())
		self.assertIn('date_of_birth', form.errors)

	def test_rejects_invalid_avatar_hair_color(self):
		payload = self._valid_payload()
		payload['avatar_hair_color'] = 'nothex'
		form = UserRegistrationStartForm(data=payload)

		self.assertFalse(form.is_valid())
		self.assertIn('__all__', form.errors)


class AvatarEditFormTests(TestCase):
	def test_rejects_invalid_avatar_hair_length(self):
		form = AvatarEditForm(data={'avatar_hair_length': 'sideways'})

		self.assertFalse(form.is_valid())
		self.assertIn('avatar_hair_length', form.errors)


class UsernameCheckTests(TestCase):
	def test_rejects_blocked_username(self):
		from django.test import Client

		client = Client()
		response = client.get('/account/register/check-username/', {'username': 'shit_head'})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json()['available'])
		self.assertEqual(response.json()['error'], 'Username not available.')


class StripeIdentityVerificationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='kyc-user',
			email='kyc-user@example.com',
			password='secret',
			first_name='Kyc',
			last_name='User',
		)
		self.profile = Profile.objects.create(
			user=self.user,
			email_confirmed=True,
			mobile_verified=True,
			address_verified=True,
			date_of_birth=date(1990, 1, 1),
			mobile_number='07123456789',
			address_line_1='1 Old Street',
			address_line_2='',
			town='London',
			county='',
			postcode='SW1A1AA',
			stripe_identity_verified=False,
		)

	def test_address_change_resets_stripe_identity_verification(self):
		self.profile.stripe_identity_verified = True
		self.profile.stripe_identity_verified_at = timezone.now()
		self.profile.stripe_identity_verification_id = 'verif_123'
		self.profile.save(update_fields=[
			'stripe_identity_verified',
			'stripe_identity_verified_at',
			'stripe_identity_verification_id',
		])

		self.client.force_login(self.user)
		response = self.client.post(
			reverse('edit'),
			{
				'first_name': 'Kyc',
				'last_name': 'User',
				'date_of_birth': '01/01/1990',
				'mobile_number': '07123456789',
				'address_line_1': '2 New Street',
				'address_line_2': '',
				'town': 'London',
				'county': '',
				'postcode': 'SW1A1AA',
			},
		)

		self.assertEqual(response.status_code, 302)
		self.profile.refresh_from_db()
		self.assertFalse(self.profile.stripe_identity_verified)
		self.assertFalse(bool(self.profile.stripe_identity_verification_id))
