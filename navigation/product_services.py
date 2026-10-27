"""Guarded application of staff-approved product catalogue recommendations."""

from django.db import transaction
from django.utils import timezone

from common.models import Order, Product
from transaction.models import Transaction

from .models import CatalogueProductRecommendation


class ProductRecommendationApplicationError(ValueError):
    """A product recommendation cannot be applied without risking live data."""


def _positive_integer_ids(value, label):
    if not isinstance(value, list) or not value:
        raise ProductRecommendationApplicationError(f'{label} must contain at least one product ID.')
    if any(not isinstance(pk, int) or pk <= 0 for pk in value):
        raise ProductRecommendationApplicationError(f'{label} contains an invalid product ID.')
    if len(set(value)) != len(value):
        raise ProductRecommendationApplicationError(f'{label} contains the same product more than once.')
    return value


def apply_product_recommendation(recommendation, reviewer):
    """Delete only unused products selected by a staff-reviewed AI proposal.

    We intentionally do not migrate or delete any listing/order history. A
    recommendation touching even one active or historical order is refused.
    """
    if recommendation.status == CatalogueProductRecommendation.STATUS_APPLIED:
        return recommendation.application_result
    if recommendation.recommendation_type not in {
        CatalogueProductRecommendation.TYPE_DUPLICATE,
        CatalogueProductRecommendation.TYPE_LOW_VALUE,
    }:
        raise ProductRecommendationApplicationError('Only duplicate or low-value product recommendations can be applied.')

    action = recommendation.proposed_action or {}
    operation = action.get('operation')
    retire_ids = _positive_integer_ids(action.get('retire_product_ids'), 'Products to retire')
    canonical_id = action.get('canonical_product_id')

    if recommendation.recommendation_type == CatalogueProductRecommendation.TYPE_DUPLICATE:
        if operation != 'consolidate' or not isinstance(canonical_id, int) or canonical_id <= 0:
            raise ProductRecommendationApplicationError('A duplicate recommendation needs one valid canonical product to retain.')
        if canonical_id in retire_ids:
            raise ProductRecommendationApplicationError('The canonical product cannot also be retired.')
        affected_ids = set(retire_ids) | {canonical_id}
    else:
        if operation != 'retire' or canonical_id is not None:
            raise ProductRecommendationApplicationError('A low-value recommendation must only retire the selected products.')
        affected_ids = set(retire_ids)

    declared_ids = set(recommendation.affected_product_ids or [])
    if not affected_ids.issubset(declared_ids):
        raise ProductRecommendationApplicationError('The proposed action does not match the reviewed affected-product list.')

    with transaction.atomic():
        recommendation = CatalogueProductRecommendation.objects.select_for_update().get(pk=recommendation.pk)
        products = list(Product.objects.select_for_update().filter(pk__in=affected_ids))
        found_ids = {product.pk for product in products}
        if found_ids != affected_ids:
            missing = ', '.join(str(pk) for pk in sorted(affected_ids - found_ids))
            raise ProductRecommendationApplicationError(f'Product {missing} no longer exists; rerun the review.')

        order_count = Order.objects.filter(product_id__in=affected_ids).count()
        if order_count:
            raise ProductRecommendationApplicationError(
                f'Not applied: {order_count} active or historical order(s) reference these products.'
            )
        transaction_count = Transaction.objects.filter(product_id__in=affected_ids).count()
        if transaction_count:
            raise ProductRecommendationApplicationError(
                f'Not applied: {transaction_count} transaction record(s) reference these products.'
            )

        Product.objects.filter(pk__in=retire_ids).delete()
        result = {
            'operation': operation,
            'canonical_product_id': canonical_id,
            'retired_product_ids': sorted(retire_ids),
        }
        recommendation.status = CatalogueProductRecommendation.STATUS_APPLIED
        recommendation.reviewed_by = reviewer
        recommendation.reviewed_at = timezone.now()
        recommendation.application_result = result
        recommendation.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'application_result'])
        return result
