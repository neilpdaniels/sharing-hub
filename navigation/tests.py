from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from common.models import Category, CategoryAttribute, Product

from .category_ai import check_duplicate, check_policy, process_category_suggestion
from .models import CategorySuggestion, CategoryTaxonomyRecommendation, CategoryTaxonomyReview
from .rate_limits import consume_submission_quota
from .services import apply_taxonomy_recommendation, promote_category_suggestion


class CategorySuggestionPipelineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='category-member', email='category@example.test', password='test-password',
        )

    def test_exact_existing_category_stops_before_an_llm_call(self):
        Category.objects.create(title='Garden tools')
        suggestion = CategorySuggestion.objects.create(
            user=self.user, name='Garden tools', description='Tools for maintaining a garden.',
        )

        state = check_duplicate({'suggestion_id': suggestion.pk})

        suggestion.refresh_from_db()
        self.assertTrue(state['duplicate'])
        self.assertEqual(suggestion.status, CategorySuggestion.STATUS_DUPLICATE)
        self.assertEqual(suggestion.duplicate_matches['matching_category_ids'], [Category.objects.get(title='Garden tools').pk])

    def test_disallowed_electronics_are_rejected_without_an_llm_call(self):
        Category.objects.create(title='Garden')
        suggestion = CategorySuggestion.objects.create(
            user=self.user, name='Cameras', description='Digital camera equipment for a weekend away.',
        )

        state = check_policy({'suggestion_id': suggestion.pk})

        suggestion.refresh_from_db()
        self.assertFalse(state['policy_approved'])
        self.assertEqual(suggestion.status, CategorySuggestion.STATUS_POLICY_REJECTED)
        self.assertIn('camera', ' '.join(suggestion.policy_result['concerns']).lower())

    @patch('navigation.category_ai.build_category_review_graph')
    def test_screening_waits_for_staff_before_image_generation(self, build_graph):
        build_graph.return_value.invoke.return_value = {'duplicate': False, 'policy_approved': True}
        suggestion = CategorySuggestion.objects.create(
            user=self.user, name='Garden carts', description='Reusable carts for moving garden materials.',
        )

        status = process_category_suggestion(suggestion.pk)

        suggestion.refresh_from_db()
        self.assertEqual(status, CategorySuggestion.STATUS_ASSET_REVIEW)
        self.assertEqual(suggestion.status, CategorySuggestion.STATUS_ASSET_REVIEW)

    @patch('navigation.services.send_category_suggestion_decision_email.delay')
    def test_admin_can_promote_a_reviewed_suggestion(self, send_email):
        parent = Category.objects.create(title='Garden')
        suggestion = CategorySuggestion.objects.create(
            user=self.user,
            name='Wheelbarrows',
            normalized_name='Wheelbarrows',
            proposed_parent=parent,
            proposed_description='Wheelbarrows and garden carts for moving soil, plants and materials around a garden.',
            status=CategorySuggestion.STATUS_ADMIN_REVIEW,
        )

        with self.captureOnCommitCallbacks(execute=True):
            category = promote_category_suggestion(suggestion, self.user)

        suggestion.refresh_from_db()
        self.assertEqual(category.parent_category, parent)
        self.assertEqual(suggestion.status, CategorySuggestion.STATUS_APPROVED)
        self.assertEqual(suggestion.published_category, category)
        send_email.assert_called_once_with(suggestion.pk)

    @patch('navigation.rate_limits.record_site_failure')
    @override_settings(CATEGORY_AI_USER_WEEKLY_LIMIT=1, CATEGORY_AI_USER_MONTHLY_LIMIT=5, CATEGORY_AI_IP_DAILY_LIMIT=5)
    def test_submission_limit_stops_second_request(self, _record_failure):
        factory = RequestFactory()
        request = factory.post('/navigation/suggest_category/', REMOTE_ADDR='127.0.0.1')
        request.user = self.user

        self.assertTrue(consume_submission_quota(request).allowed)
        self.assertFalse(consume_submission_quota(request).allowed)

    def test_applying_merge_reassigns_products_then_removes_source_category(self):
        root = Category.objects.create(title='Garden')
        source = Category.objects.create(title='Garden hand tools', parent_category=root)
        target = Category.objects.create(title='DIY hand tools', parent_category=root)
        product = Product.objects.create(category_id=source, name='Garden spade')
        product.categories.add(source)
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_DUPLICATE,
            title='Merge garden hand tools into DIY hand tools',
            rationale='Both categories contain the same reusable hand tools.',
            evidence=['Both categories have the same product type.'],
            proposed_action={
                'operation': 'merge',
                'source_category_id': source.pk,
                'target_category_id': target.pk,
            },
        )

        result = apply_taxonomy_recommendation(recommendation, self.user)

        product.refresh_from_db()
        recommendation.refresh_from_db()
        self.assertEqual(result['primary_products_reassigned'], 1)
        self.assertEqual(product.category_id, target)
        self.assertTrue(product.categories.filter(pk=target.pk).exists())
        self.assertFalse(Category.objects.filter(pk=source.pk).exists())
        self.assertEqual(recommendation.status, CategoryTaxonomyRecommendation.STATUS_IMPLEMENTED)

    def test_applying_attribute_recommendation_creates_a_filterable_product_attribute(self):
        category = Category.objects.create(title='Garden appliances')
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_ATTRIBUTE,
            title='Add power source to garden appliances',
            rationale='The products span clear power-source types that are better filtered than split.',
            evidence=['Product names show petrol, battery and corded variants.'],
            proposed_action={
                'operation': 'add_attribute',
                'category_id': category.pk,
                'order': 1,
                'name': 'Power source',
                'value_source': 'product',
                'allowed_values': ['Petrol', 'Battery', 'Corded'],
            },
        )

        result = apply_taxonomy_recommendation(recommendation, self.user)

        attribute = CategoryAttribute.objects.get(pk=result['category_attribute_id'])
        self.assertTrue(attribute.filterable)
        self.assertEqual(attribute.name, 'Power source')
        self.assertEqual(attribute.get_allowed_values(), ['Petrol', 'Battery', 'Corded'])

    def test_attribute_recommendation_defaults_to_listing_values_when_source_is_omitted(self):
        category = Category.objects.create(title='Fancy dress')
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_ATTRIBUTE,
            title='Add an age range filter for fancy dress',
            rationale='Listings need an age-range choice without creating a separate catalogue product for every size.',
            evidence=['Listings include both children and adult fancy dress.'],
            proposed_action={
                'operation': 'add_attribute',
                'category_id': category.pk,
                'order': 1,
                'name': 'Age range',
                'allowed_values': ['Age 3-4', 'Age 5-6', 'Adult'],
            },
        )

        result = apply_taxonomy_recommendation(recommendation, self.user)

        attribute = CategoryAttribute.objects.get(pk=result['category_attribute_id'])
        self.assertEqual(attribute.value_source, CategoryAttribute.VALUE_SOURCE_LISTING)
