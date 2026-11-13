"""Read-only product catalogue quality and short-hire rental-worthiness review."""

from math import ceil
from typing import Literal

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from common.models import Category, LetPriceBand, Order, Product
from transaction.models import Transaction

from .category_ai import _chat_model
from .models import CatalogueProductRecommendation, CatalogueProductReview


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ConsumerAssessment(StrictModel):
    likely_use_frequency: Literal['rare', 'occasional', 'recurring']
    estimated_replacement_cost_band: Literal['under_15', '15_to_50', '50_to_150', 'over_150', 'unknown']
    transport_storage_burden: Literal['low', 'medium', 'high']
    wear_damage_risk: Literal['low', 'medium', 'high']
    one_week_rental_suitability: Literal['poor', 'borderline', 'good', 'strong']
    two_week_rental_suitability: Literal['poor', 'borderline', 'good', 'strong']
    four_week_rental_suitability: Literal['poor', 'borderline', 'good', 'strong']
    estimate_note: str = Field(max_length=500)


class ProductAction(StrictModel):
    """A plan that can be validated before staff apply it."""
    operation: Literal['retire', 'consolidate', 'listing_variants', 'none']
    canonical_product_id: int | None = None
    retire_product_ids: list[int] = Field(default_factory=list, max_length=30)
    target_category_title: str = Field(default='', max_length=200)
    replacement_product_titles: list[str] = Field(default_factory=list, max_length=4)
    listing_attribute_names: list[str] = Field(default_factory=list, max_length=5)


class ProductProposal(StrictModel):
    recommendation_type: Literal['DUPLICATE', 'LOW_VALUE', 'LISTING_VARIANTS', 'KEEP']
    title: str = Field(max_length=255)
    rationale: str = Field(max_length=900)
    evidence: list[str] = Field(max_length=6)
    recommended_action: str = Field(max_length=700)
    affected_product_ids: list[int] = Field(max_length=30)
    proposed_action: ProductAction
    consumer_assessment: ConsumerAssessment


class ProductAssessment(StrictModel):
    executive_summary: str = Field(max_length=1200)
    recommendations: list[ProductProposal] = Field(max_length=80)


def _strength_instruction(strength: str) -> str:
    instructions = {
        CatalogueProductReview.STRENGTH_LIGHT: (
            'Requested review strength: LIGHT. Recommend only near-certain duplicates or clearly disposable, low-value products with no meaningful rental evidence.'
        ),
        CatalogueProductReview.STRENGTH_HEAVY: (
            'Requested review strength: HEAVY / lean pre-launch launch. The marketplace must start deliberately small and '
            'build up from proven demand, not publish speculative coverage. Proactively identify entire low-fit product families, '
            'near-duplicate names and consumer-buy items for removal. Group up to 30 products in one recommendation when the '
            'same specific rationale genuinely applies. Recommend more candidates than a medium review, but never invent evidence.'
        ),
    }
    return instructions.get(
        strength,
        'Requested review strength: MEDIUM. Recommend practical duplicate consolidation and low-value cleanup where evidence supports it.',
    )


def _prune_target_instruction(prune_target_percent: int, product_count: int) -> str:
    if not prune_target_percent:
        return (
            'There is no numerical pruning target for this review. Recommend only genuinely worthwhile cleanup; '
            'it is valid to return few or no retirement candidates.'
        )
    target_count = ceil(product_count * prune_target_percent / 100)
    return (
        f'Staff have set an advisory pruning target of {prune_target_percent}% ({target_count} of {product_count} product templates). '
        'Rank and include enough well-supported retirement or consolidation candidates to approach that target where possible. '
        'Group similar items where one clear rationale applies, rather than spending one recommendation on each variant. '
        'This is a discovery target, not a quota: never invent evidence or recommend a weak removal merely to reach it.'
    )


def _category_scope_ids(scope_category: Category | None) -> set[int] | None:
    if scope_category is None:
        return None
    children_by_parent: dict[int | None, list[int]] = {}
    for category_id, parent_id in Category.objects.values_list('id', 'parent_category_id'):
        children_by_parent.setdefault(parent_id, []).append(category_id)
    category_ids: set[int] = set()
    pending = [scope_category.id]
    while pending:
        category_id = pending.pop()
        if category_id in category_ids:
            continue
        category_ids.add(category_id)
        pending.extend(children_by_parent.get(category_id, []))
    return category_ids


def product_catalogue_snapshot(scope_category: Category | None = None) -> dict:
    scope_ids = _category_scope_ids(scope_category)
    products_query = Product.objects.select_related('category_id')
    orders_query = Order.objects.all()
    transactions_query = Transaction.objects.filter(order_passive__isnull=False)
    price_bands_query = LetPriceBand.objects.filter(order__direction=Order.TO_LET)
    if scope_ids is not None:
        products_query = products_query.filter(category_id__in=scope_ids)
        orders_query = orders_query.filter(product__category_id__in=scope_ids)
        transactions_query = transactions_query.filter(order_passive__product__category_id__in=scope_ids)
        price_bands_query = price_bands_query.filter(order__product__category_id__in=scope_ids)
    active = {
        row['product_id']: row['count'] for row in orders_query.filter(status=Order.ACTIVE, direction=Order.TO_LET)
        .values('product_id').annotate(count=Count('id'))
    }
    historical = {
        row['product_id']: row['count'] for row in orders_query.filter(direction=Order.TO_LET)
        .values('product_id').annotate(count=Count('id'))
    }
    completed = {
        row['order_passive__product_id']: row['count']
        for row in transactions_query.filter(transaction_status__in=(
            Transaction.RENTAL_PROCESS_COMPLETED, Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
            Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
        )).values('order_passive__product_id').annotate(count=Count('id'))
    }
    prices = {
        row['order__product_id']: row for row in price_bands_query
        .values('order__product_id').annotate(min_daily_price=Min('price_per_day'), max_daily_price=Max('price_per_day'))
    }
    products = []
    for product in products_query.order_by('category_id__title', 'name', 'id'):
        price = prices.get(product.id, {})
        products.append({
            'id': product.id, 'name': product.name, 'category_id': product.category_id_id,
            'category': product.category_id.title if product.category_id else '',
            'description': (product.description or '').strip()[:280],
            'active_lend_listings': active.get(product.id, 0),
            'historical_lend_listings': historical.get(product.id, 0),
            'completed_rentals': completed.get(product.id, 0),
            'daily_rental_price_min': price.get('min_daily_price'),
            'daily_rental_price_max': price.get('max_daily_price'),
        })
    return {
        'generated_at': timezone.now().isoformat(),
        'scope': {'category_id': scope_category.id, 'category_title': scope_category.title} if scope_category else None,
        'products': products,
        'product_id_set': [p['id'] for p in products],
    }


def _prompt(snapshot: dict, strength: str, prune_target_percent: int = 0) -> str:
    scope_instruction = (
        'This is a scoped review: review and recommend actions only for the supplied category tree. '
        if snapshot.get('scope') else ''
    )
    return (
        'You are conducting a read-only product catalogue-worthiness review for a UK peer-to-peer rental marketplace. '
        f'{_strength_instruction(strength)} '
        f'{_prune_target_instruction(prune_target_percent, len(snapshot.get("products", [])))} '
        f'{scope_instruction}'
        'Assess from the perspective of a general household consumer, not a trade business. Be usefully critical. '
        'Identify near-duplicate products that can be consolidated into one canonical product (for example, '
        'different names for the same plate compactor), and low-value generic products that consumers are more likely to buy. '
        'Within a product family, treat several basic templates that solve the same household need (for example multiple '
        'commode templates) as consolidation candidates unless the supplied description shows a material rental distinction. '
        'Also identify a distinct LISTING_VARIANTS pattern: several sparse product templates are really individual '
        'variants of one rentable product type, where the useful differences should be chosen by the lender on each '
        'listing (for example, individual costumes under Adult fancy dress, filtered by Theme and Size). Only make this '
        'recommendation where it genuinely makes browsing simpler without hiding a meaningful hire distinction. '
        'Score three separate rental horizons: one_week_rental_suitability (up to seven consecutive days), '
        'two_week_rental_suitability (eight to fourteen consecutive days), and four_week_rental_suitability '
        '(fifteen to twenty-eight consecutive days). Do not treat a longer rental as automatically more suitable. '
        'For each horizon, consider whether a household is realistically likely to pay to borrow the item rather than '
        'buy it, borrow from family, or use an alternative. Give a poor score when a product is cheap, personal or '
        'hygiene-sensitive, safety-sensitive, or normally owned for ongoing use; give a strong score only when that '
        'specific hire period solves a clear, occasional problem. '
        'A £15–50 estimated replacement cost is a strong negative signal, not an automatic rejection: retain rare, one-off, '
        'specialist, hard-to-store, hard-to-transport, or costly-to-get-wrong tools. Treat model/brand variants as duplicates '
        'unless the supplied evidence shows a meaningful consumer-facing distinction. '
        'For every recommendation, score likely use frequency, estimated replacement-cost band (estimate only), transport/storage '
        'burden, rental wear/damage risk, and all three rental-suitability horizons. Use only supplied catalogue facts for listings/rentals/prices; '
        'your replacement-cost band is an explicitly labelled general estimate. Do not invent product IDs. '
        'Recommend only DUPLICATE, LOW_VALUE, LISTING_VARIANTS, or KEEP (for a specialist exception worth retaining). All '
        'recommendations are for human review. Include a proposed_action object: for DUPLICATE use operation "consolidate", set '
        'canonical_product_id to the one existing product ID to retain, and retire_product_ids to the duplicate IDs to remove. '
        'For LOW_VALUE use operation "retire", canonical_product_id null, and retire_product_ids to the IDs to remove. '
        'For LISTING_VARIANTS use operation "listing_variants", set target_category_title, replacement_product_titles, and '
        'listing_attribute_names; do not nominate a canonical ID or retire IDs because staff must inspect the data-conversion '
        'preview before applying it. For KEEP use operation "none", canonical_product_id null, and an empty retire_product_ids list. '
        'Every ID must come from the supplied snapshot and affected_product_ids must include every canonical or retired ID. A staff '
        'action will refuse ordinary retirement/consolidation if any affected product has active or historical orders; never propose '
        'moving orders except through a separately reviewed LISTING_VARIANTS conversion. '
        'It is valid to produce no recommendations.\n\n'
        f'Product snapshot:\n{snapshot}'
    )


def process_product_catalogue_review(review_id: int) -> str:
    review = CatalogueProductReview.objects.get(pk=review_id)
    try:
        snapshot = product_catalogue_snapshot(review.scope_category)
        review.snapshot, review.status, review.started_at, review.error = snapshot, review.STATUS_RUNNING, timezone.now(), ''
        review.save(update_fields=['snapshot', 'status', 'started_at', 'error'])
        assessment = _chat_model().with_structured_output(ProductAssessment).invoke(
            _prompt(snapshot, review.review_strength, review.prune_target_percent)
        )
        review.llm_analysis = assessment.model_dump()
        review.recommendations.all().delete()
        valid_ids = set(snapshot['product_id_set'])
        for position, item in enumerate(assessment.recommendations):
            action = item.proposed_action.model_dump()
            action['canonical_product_id'] = (
                action['canonical_product_id']
                if action['canonical_product_id'] in valid_ids else None
            )
            action['retire_product_ids'] = [
                pk for pk in action['retire_product_ids'] if pk in valid_ids
            ]
            action_ids = set(action['retire_product_ids'])
            if action['canonical_product_id']:
                action_ids.add(action['canonical_product_id'])
            # affected_product_ids is the review display/audit list. The
            # executable action is the authoritative source of the IDs it
            # needs, so retain any valid action ID the model accidentally
            # omitted from that list rather than creating an unusable review.
            affected_ids = sorted({
                *[pk for pk in item.affected_product_ids if pk in valid_ids],
                *action_ids,
            })
            CatalogueProductRecommendation.objects.create(
                review=review, position=position, recommendation_type=item.recommendation_type,
                title=item.title, rationale=item.rationale, evidence=item.evidence,
                recommended_action=item.recommended_action,
                affected_product_ids=affected_ids,
                proposed_action=action,
                consumer_assessment=item.consumer_assessment.model_dump(),
            )
        review.status, review.completed_at, review.error = review.STATUS_READY, timezone.now(), ''
        review.save(update_fields=['llm_analysis', 'status', 'completed_at', 'error'])
        return review.status
    except Exception as exc:
        review.status, review.error, review.completed_at = review.STATUS_FAILED, str(exc)[:4000], timezone.now()
        review.save(update_fields=['status', 'error', 'completed_at'])
        raise
