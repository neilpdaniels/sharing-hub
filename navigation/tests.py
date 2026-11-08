from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from common.models import Category, CategoryAttribute, Order, Product

from .category_ai import check_duplicate, check_policy, process_category_suggestion
from .models import (
    CatalogueProductRecommendation,
    CatalogueProductReview,
    CategorySuggestion,
    CategoryTaxonomyRecommendation,
    CategoryTaxonomyReview,
)
from .product_services import ProductRecommendationApplicationError, apply_product_recommendation
from .product_catalogue_ai import _prompt
from .rate_limits import consume_submission_quota
from .services import TaxonomyApplicationError, apply_taxonomy_recommendation, promote_category_suggestion


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

    @patch('navigation.services.send_category_suggestion_decision_email.delay')
    def test_admin_can_publish_a_product_proposal(self, send_email):
        category = Category.objects.create(title='Garden tools')
        suggestion = CategorySuggestion.objects.create(
            user=self.user,
            name='Electric hedge trimmer',
            normalized_name='Electric hedge trimmer',
            proposal_kind=CategorySuggestion.PROPOSAL_PRODUCT,
            proposed_parent=category,
            proposed_description='An electric hedge trimmer for maintaining garden hedges and shrubs.',
            status=CategorySuggestion.STATUS_ADMIN_REVIEW,
        )

        with self.captureOnCommitCallbacks(execute=True):
            product = promote_category_suggestion(suggestion, self.user)

        suggestion.refresh_from_db()
        self.assertIsInstance(product, Product)
        self.assertEqual(product.category_id, category)
        self.assertEqual(suggestion.published_product, product)
        self.assertEqual(suggestion.status, CategorySuggestion.STATUS_APPROVED)
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

    def test_merging_sibling_categories_into_a_new_name_retires_both_old_categories(self):
        root = Category.objects.create(title='Party')
        costumes = Category.objects.create(title='Children costumes', parent_category=root)
        dress_up = Category.objects.create(title='Kids dress-up', parent_category=root)
        costume_product = Product.objects.create(category_id=costumes, name='Pirate costume')
        dress_up_product = Product.objects.create(category_id=dress_up, name='Superhero cape')
        costumes_id, dress_up_id = costumes.pk, dress_up.pk
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_DUPLICATE,
            title='Combine children costume categories',
            rationale='Both sibling categories describe the same customer browsing area.',
            evidence=['Both categories contain children’s fancy-dress products.'],
            proposed_action={
                'operation': 'merge_new',
                'source_category_id': costumes.pk,
                'target_category_id': dress_up.pk,
                'parent_category_id': root.pk,
                'title': 'Children’s fancy dress',
                'description': 'Costumes and dress-up outfits for children.',
            },
        )

        result = apply_taxonomy_recommendation(recommendation, self.user)

        consolidated = Category.objects.get(pk=result['created_category_id'])
        costume_product.refresh_from_db()
        dress_up_product.refresh_from_db()
        self.assertEqual(consolidated.title, 'Children’s fancy dress')
        self.assertEqual(costume_product.category_id, consolidated)
        self.assertEqual(dress_up_product.category_id, consolidated)
        self.assertFalse(Category.objects.filter(pk=costumes_id).exists())
        self.assertFalse(Category.objects.filter(pk=dress_up_id).exists())

    def test_retiring_empty_category_subtree_removes_its_children(self):
        root = Category.objects.create(title='Baby equipment')
        source = Category.objects.create(title='Baby bouncers', parent_category=root)
        child = Category.objects.create(title='Baby bouncer accessories', parent_category=source)
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_RETIRE,
            title='Retire unused baby bouncer area',
            rationale='The whole subtree has no listings or rental history.',
            evidence=['No active or historical listings.', 'No completed rentals.'],
            proposed_action={
                'operation': 'retire',
                'source_category_id': source.pk,
                'target_category_id': None,
            },
        )

        result = apply_taxonomy_recommendation(recommendation, self.user)

        recommendation.refresh_from_db()
        self.assertEqual(result['retired_category_count'], 2)
        self.assertEqual(result['retired_product_count'], 0)
        self.assertFalse(Category.objects.filter(pk=source.pk).exists())
        self.assertFalse(Category.objects.filter(pk=child.pk).exists())
        self.assertEqual(recommendation.status, CategoryTaxonomyRecommendation.STATUS_IMPLEMENTED)

    @patch('common.models.updateSummaryPrices.delay')
    def test_retiring_category_subtree_refuses_when_it_contains_products(self, _update_prices):
        root = Category.objects.create(title='Baby equipment')
        source = Category.objects.create(title='Baby bouncers', parent_category=root)
        product = Product.objects.create(category_id=source, name='Baby bouncer')
        review = CategoryTaxonomyReview.objects.create(requested_by=self.user)
        recommendation = CategoryTaxonomyRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=CategoryTaxonomyRecommendation.TYPE_RETIRE,
            title='Retire unused baby bouncer area',
            rationale='The whole subtree has no active listings.',
            evidence=['No active listings.'],
            proposed_action={
                'operation': 'retire',
                'source_category_id': source.pk,
                'target_category_id': None,
            },
        )

        with self.assertRaisesMessage(TaxonomyApplicationError, 'only removes genuinely empty'):
            apply_taxonomy_recommendation(recommendation, self.user)

        self.assertTrue(Category.objects.filter(pk=source.pk).exists())
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

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


class ProductRecommendationApplicationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='catalogue-admin', email='catalogue-admin@example.test', password='test-password',
        )
        self.category = Category.objects.create(title='Garden tools')

    def _recommendation(self, *, recommendation_type, affected_ids, action):
        review = CatalogueProductReview.objects.create(requested_by=self.user)
        return CatalogueProductRecommendation.objects.create(
            review=review,
            position=0,
            recommendation_type=recommendation_type,
            title='Safe catalogue cleanup',
            rationale='No demand evidence exists.',
            evidence=['No listings or rentals.'],
            affected_product_ids=affected_ids,
            proposed_action=action,
        )

    def test_applies_low_value_retirement_when_product_has_no_orders(self):
        product = Product.objects.create(category_id=self.category, name='Disposable screwdriver')
        recommendation = self._recommendation(
            recommendation_type=CatalogueProductRecommendation.TYPE_LOW_VALUE,
            affected_ids=[product.pk],
            action={'operation': 'retire', 'canonical_product_id': None, 'retire_product_ids': [product.pk]},
        )

        result = apply_product_recommendation(recommendation, self.user)

        recommendation.refresh_from_db()
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertEqual(result['retired_product_ids'], [product.pk])
        self.assertEqual(recommendation.status, CatalogueProductRecommendation.STATUS_APPLIED)

    @patch('common.models.updateSummaryPrices.delay')
    def test_refuses_retirement_when_product_has_any_historical_order(self, _update_prices):
        product = Product.objects.create(category_id=self.category, name='Garden fork')
        Order.objects.create(
            product=product,
            user=self.user,
            direction=Order.TO_LET,
            expiry_date=timezone.now(),
            price=10,
            status=Order.EXPIRED,
        )
        recommendation = self._recommendation(
            recommendation_type=CatalogueProductRecommendation.TYPE_LOW_VALUE,
            affected_ids=[product.pk],
            action={'operation': 'retire', 'canonical_product_id': None, 'retire_product_ids': [product.pk]},
        )

        with self.assertRaisesMessage(ProductRecommendationApplicationError, 'active or historical order'):
            apply_product_recommendation(recommendation, self.user)

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_applies_duplicate_consolidation_only_when_all_affected_products_are_unused(self):
        canonical = Product.objects.create(category_id=self.category, name='Plate compactor')
        duplicate = Product.objects.create(category_id=self.category, name='Wacker plate')
        recommendation = self._recommendation(
            recommendation_type=CatalogueProductRecommendation.TYPE_DUPLICATE,
            affected_ids=[canonical.pk, duplicate.pk],
            action={
                'operation': 'consolidate',
                'canonical_product_id': canonical.pk,
                'retire_product_ids': [duplicate.pk],
            },
        )

        apply_product_recommendation(recommendation, self.user)

        self.assertTrue(Product.objects.filter(pk=canonical.pk).exists())
        self.assertFalse(Product.objects.filter(pk=duplicate.pk).exists())

    def test_repairs_an_ai_affected_id_omission_when_action_ids_are_in_review_snapshot(self):
        canonical = Product.objects.create(category_id=self.category, name='Costume set')
        duplicate = Product.objects.create(category_id=self.category, name='Costume accessory')
        recommendation = self._recommendation(
            recommendation_type=CatalogueProductRecommendation.TYPE_DUPLICATE,
            affected_ids=[canonical.pk],
            action={
                'operation': 'consolidate',
                'canonical_product_id': canonical.pk,
                'retire_product_ids': [duplicate.pk],
            },
        )
        recommendation.review.snapshot = {'product_id_set': [canonical.pk, duplicate.pk]}
        recommendation.review.save(update_fields=['snapshot'])

        apply_product_recommendation(recommendation, self.user)

        recommendation.refresh_from_db()
        self.assertEqual(recommendation.affected_product_ids, [canonical.pk, duplicate.pk])
        self.assertFalse(Product.objects.filter(pk=duplicate.pk).exists())


class ProductCataloguePromptTests(TestCase):
    def test_prompt_uses_one_week_hire_and_advisory_prune_target(self):
        prompt = _prompt(
            {'products': [{'id': index} for index in range(8)]},
            CatalogueProductReview.STRENGTH_HEAVY,
            25,
        )

        self.assertIn('up to seven consecutive days', prompt)
        self.assertIn('one_week_rental_suitability', prompt)
        self.assertIn('two_week_rental_suitability', prompt)
        self.assertIn('four_week_rental_suitability', prompt)
        self.assertIn('25% (2 of 8 product templates)', prompt)
