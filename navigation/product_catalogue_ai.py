"""Read-only product catalogue quality and consumer rental-worthiness review."""

from collections import defaultdict
from typing import Literal

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from common.models import LetPriceBand, Order, Product
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
    rental_suitability: Literal['poor', 'borderline', 'good', 'strong']
    estimate_note: str = Field(max_length=500)


class ProductProposal(StrictModel):
    recommendation_type: Literal['DUPLICATE', 'LOW_VALUE', 'KEEP']
    title: str = Field(max_length=255)
    rationale: str = Field(max_length=900)
    evidence: list[str] = Field(max_length=6)
    # Advisory for now; automatic application needs product-retirement support.
    recommended_action: str = Field(max_length=700)
    affected_product_ids: list[int] = Field(max_length=12)
    consumer_assessment: ConsumerAssessment


class ProductAssessment(StrictModel):
    executive_summary: str = Field(max_length=1200)
    recommendations: list[ProductProposal] = Field(max_length=40)


def product_catalogue_snapshot() -> dict:
    active = {
        row['product_id']: row['count'] for row in Order.objects.filter(status=Order.ACTIVE, direction=Order.TO_LET)
        .values('product_id').annotate(count=Count('id'))
    }
    historical = {
        row['product_id']: row['count'] for row in Order.objects.filter(direction=Order.TO_LET)
        .values('product_id').annotate(count=Count('id'))
    }
    completed = {
        row['order_passive__product_id']: row['count']
        for row in Transaction.objects.filter(order_passive__isnull=False, transaction_status__in=(
            Transaction.RENTAL_PROCESS_COMPLETED, Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
            Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
        )).values('order_passive__product_id').annotate(count=Count('id'))
    }
    prices = {
        row['order__product_id']: row for row in LetPriceBand.objects.filter(order__direction=Order.TO_LET)
        .values('order__product_id').annotate(min_daily_price=Min('price_per_day'), max_daily_price=Max('price_per_day'))
    }
    products = []
    for product in Product.objects.select_related('category_id').order_by('category_id__title', 'name', 'id'):
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
    return {'generated_at': timezone.now().isoformat(), 'products': products, 'product_id_set': [p['id'] for p in products]}


def _prompt(snapshot: dict) -> str:
    return (
        'You are conducting a read-only product catalogue-worthiness review for a UK peer-to-peer rental marketplace. '
        'Assess from the perspective of a general household consumer, not a trade business. Be usefully critical. '
        'Identify near-duplicate products that should be manually consolidated into one canonical product (for example, '
        'different names for the same plate compactor), and low-value generic products that consumers are more likely to buy. '
        'A £15–50 estimated replacement cost is a strong negative signal, not an automatic rejection: retain rare, one-off, '
        'specialist, hard-to-store, hard-to-transport, or costly-to-get-wrong tools. Treat model/brand variants as duplicates '
        'unless the supplied evidence shows a meaningful consumer-facing distinction. '
        'For every recommendation, score likely use frequency, estimated replacement-cost band (estimate only), transport/storage '
        'burden, rental wear/damage risk, and rental suitability. Use only supplied catalogue facts for listings/rentals/prices; '
        'your replacement-cost band is an explicitly labelled general estimate. Do not invent product IDs. '
        'Recommend only DUPLICATE, LOW_VALUE, or KEEP (for a specialist exception worth retaining). Never instruct automatic '
        'deletion or merging; all recommendations are for human review. Include a specific recommended_action: for a '
        'duplicate, name the proposed canonical product ID and which IDs staff should manually consolidate; for LOW_VALUE, '
        'say whether staff should retain, retire from future use, or request stronger rental evidence; for KEEP, explain why '
        'it should remain. It is valid to produce no recommendations.\n\n'
        f'Product snapshot:\n{snapshot}'
    )


def process_product_catalogue_review(review_id: int) -> str:
    review = CatalogueProductReview.objects.get(pk=review_id)
    try:
        snapshot = product_catalogue_snapshot()
        review.snapshot, review.status, review.started_at, review.error = snapshot, review.STATUS_RUNNING, timezone.now(), ''
        review.save(update_fields=['snapshot', 'status', 'started_at', 'error'])
        assessment = _chat_model().with_structured_output(ProductAssessment).invoke(_prompt(snapshot))
        review.llm_analysis = assessment.model_dump()
        review.recommendations.all().delete()
        valid_ids = set(snapshot['product_id_set'])
        for position, item in enumerate(assessment.recommendations):
            CatalogueProductRecommendation.objects.create(
                review=review, position=position, recommendation_type=item.recommendation_type,
                title=item.title, rationale=item.rationale, evidence=item.evidence,
                recommended_action=item.recommended_action,
                affected_product_ids=[pk for pk in item.affected_product_ids if pk in valid_ids],
                consumer_assessment=item.consumer_assessment.model_dump(),
            )
        review.status, review.completed_at, review.error = review.STATUS_READY, timezone.now(), ''
        review.save(update_fields=['llm_analysis', 'status', 'completed_at', 'error'])
        return review.status
    except Exception as exc:
        review.status, review.error, review.completed_at = review.STATUS_FAILED, str(exc)[:4000], timezone.now()
        review.save(update_fields=['status', 'error', 'completed_at'])
        raise
