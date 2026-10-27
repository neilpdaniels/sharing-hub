from django.test import TestCase
from django.urls import resolve

# Create your tests here.


class MyDetailsRouteTests(TestCase):
	def test_legacy_my_details_url_remains_routed(self):
		match = resolve('/my_rentalution/my_details/')
		self.assertEqual(match.view_name, 'my_rentalution:my_details')
