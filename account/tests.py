from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from account.forms import AvatarEditForm, UserRegistrationStartForm


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
