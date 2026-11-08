"""One-click, auditable application of a reviewed catalogue-cleanup run."""

from django.utils import timezone

from .models import (
    CatalogueCleanupReview,
    CatalogueProductRecommendation,
    CategoryTaxonomyRecommendation,
)
from .product_services import ProductRecommendationApplicationError, apply_product_recommendation
from .services import TaxonomyApplicationError, apply_taxonomy_recommendation


def apply_catalogue_cleanup_review(cleanup, reviewer):
    """Apply independently safe recommendations and report every outcome.

    Product changes run first so taxonomy cleanup can subsequently remove a
    category that has become empty. Each existing application service keeps its
    own transaction and history guards; one bad proposal never blocks review of
    the remainder.
    """
    if not cleanup.product_review and not cleanup.taxonomy_review:
        raise ValueError('This cleanup review has not produced any results yet.')

    result = {'product_applied': [], 'taxonomy_applied': [], 'errors': [], 'skipped_extra_scrutiny': []}
    if cleanup.product_review:
        product_recommendations = cleanup.product_review.recommendations.filter(
            status=CatalogueProductRecommendation.STATUS_PENDING,
            recommendation_type__in=(
                CatalogueProductRecommendation.TYPE_DUPLICATE,
                CatalogueProductRecommendation.TYPE_LOW_VALUE,
            ),
        )
        for recommendation in product_recommendations:
            try:
                apply_product_recommendation(recommendation, reviewer)
            except ProductRecommendationApplicationError as exc:
                result['errors'].append(f'{recommendation.title}: {exc}')
            else:
                result['product_applied'].append(recommendation.pk)

    if cleanup.taxonomy_review:
        taxonomy_recommendations = cleanup.taxonomy_review.recommendations.filter(
            status__in=(
                CategoryTaxonomyRecommendation.STATUS_PENDING,
                CategoryTaxonomyRecommendation.STATUS_APPROVED,
            ),
        ).exclude(recommendation_type=CategoryTaxonomyRecommendation.TYPE_KEEP)
        for recommendation in taxonomy_recommendations:
            try:
                apply_taxonomy_recommendation(recommendation, reviewer)
            except TaxonomyApplicationError as exc:
                result['errors'].append(f'{recommendation.title}: {exc}')
            else:
                result['taxonomy_applied'].append(recommendation.pk)
        result['skipped_extra_scrutiny'] = list(
            cleanup.taxonomy_review.recommendations.filter(
                status=CategoryTaxonomyRecommendation.STATUS_NEEDS_HUMAN,
            ).values_list('pk', flat=True)
        )

    cleanup.application_result = {**result, 'applied_at': timezone.now().isoformat()}
    cleanup.save(update_fields=['application_result'])
    return result
