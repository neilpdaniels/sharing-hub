from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from common.models import Category, CategoryAttribute


class CategoryChecksumTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.parent = Category.objects.create(title='Top', slug='top')
        self.category = Category.objects.create(title='Tools', parent_category=self.parent)
        self.url = reverse('mobile_api:categories_list')

    def test_unchanged_returns_no_body_and_weak_etag_is_accepted(self):
        response = self.client.get(self.url, {'include_top': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        for etag in (response['ETag'], 'W/' + response['ETag']):
            unchanged = self.client.get(self.url, {'include_top': 'true'}, HTTP_IF_NONE_MATCH=etag)
            self.assertEqual(unchanged.status_code, 304)
            self.assertEqual(unchanged.content, b'')
            self.assertEqual(unchanged['ETag'], response['ETag'])

    def test_edit_attribute_and_delete_invalidate_checksum(self):
        previous = self.client.get(self.url)['ETag']
        self.category.title = 'Power tools'
        self.category.save()
        response = self.client.get(self.url, HTTP_IF_NONE_MATCH=previous)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response['ETag'], previous)
        previous = response['ETag']
        CategoryAttribute.objects.create(category=self.category, order=1, name='Power')
        response = self.client.get(self.url, HTTP_IF_NONE_MATCH=previous)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response['ETag'], previous)
        previous = response['ETag']
        self.category.delete()
        response = self.client.get(self.url, HTTP_IF_NONE_MATCH=previous)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_checksum_is_specific_to_requested_parent(self):
        response = self.client.get(self.url, {'parent_slug': 'top'})
        other = self.client.get(self.url, {'parent_slug': self.category.slug}, HTTP_IF_NONE_MATCH=response['ETag'])
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.json(), [])
