from django.test import TestCase
from django.urls import reverse


class PublicLegalPagesTests(TestCase):
    def test_account_deletion_page_is_public_and_links_to_the_request_path(self):
        response = self.client.get(reverse('pages:accountDeletion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete your Rentalution account')
        self.assertContains(response, reverse('pages:helpAndSupport'))

    def test_help_page_prefills_a_deletion_request_subject(self):
        response = self.client.get(
            reverse('pages:helpAndSupport'),
            {'subject': 'Account deletion request'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Account deletion request"')
