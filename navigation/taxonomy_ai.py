"""Read-only, human-in-the-loop catalogue taxonomy reviews."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, Literal, TypedDict

from crewai import Agent, Crew, LLM, Process, Task
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from common.models import Category, Order, Product
from transaction.models import Transaction

from .category_ai import DEFAULT_TEXT_MODEL, _api_key, _chat_model
from .models import (
    CategorySuggestion,
    CategoryTaxonomyRecommendation,
    CategoryTaxonomyReview,
    SearchHistory,
)


class TaxonomyProposal(BaseModel):
    recommendation_type: Literal['MISSING', 'DUPLICATE', 'MOVE', 'SPLIT', 'RETIRE', 'ATTRIBUTE', 'KEEP']
    title: str = Field(min_length=8, max_length=255)
    rationale: str = Field(min_length=30, max_length=900)
    evidence: list[str] = Field(min_length=1, max_length=6)
    affected_category_ids: list[int] = Field(default_factory=list, max_length=20)
    proposed_action: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)


class TaxonomyAssessment(BaseModel):
    executive_summary: str = Field(min_length=30, max_length=1200)
    strengths: list[str] = Field(default_factory=list, max_length=6)
    recommendations: list[TaxonomyProposal] = Field(default_factory=list, max_length=20)


class TaxonomyCritique(BaseModel):
    approved_indexes: list[int] = Field(default_factory=list)
    concern_indexes: list[int] = Field(default_factory=list)
    summary: str = Field(max_length=900)
    concerns: list[str] = Field(default_factory=list, max_length=12)


class TaxonomyState(TypedDict, total=False):
    review_id: int
    assessment: dict[str, Any]


def catalogue_snapshot() -> dict[str, Any]:
    """Compact, evidence-rich snapshot. It never exposes member data to the LLM."""
    product_counts = {
        row['category_id']: row['count']
        for row in Product.objects.values('category_id').annotate(count=Count('id'))
    }
    active_listing_counts = {
        row['product__category_id']: row['count']
        for row in Order.objects.filter(
            status=Order.ACTIVE, direction=Order.TO_LET,
        ).values('product__category_id').annotate(count=Count('id'))
    }
    historical_listing_stats = {
        row['product__category_id']: row
        for row in Order.objects.filter(direction=Order.TO_LET).values('product__category_id').annotate(
            historical_lend_listing_count=Count('id'),
            first_lend_listing_at=Min('create_date'),
            last_lend_listing_at=Max('amended'),
        )
    }
    completed_transaction_statuses = (
        Transaction.RENTAL_PROCESS_COMPLETED,
        Transaction.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
        Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
    )
    transaction_stats = {
        row['order_passive__product__category_id']: row
        for row in Transaction.objects.filter(order_passive__isnull=False).values(
            'order_passive__product__category_id'
        ).annotate(
            transaction_count=Count('id'),
            completed_rental_count=Count(
                'id',
                filter=Q(transaction_status__in=completed_transaction_statuses),
            ),
            last_completed_rental_at=Max(
                'amended',
                filter=Q(transaction_status__in=completed_transaction_statuses),
            ),
        )
    }
    samples: dict[int, list[str]] = defaultdict(list)
    for product in Product.objects.order_by('category_id', 'name').values('category_id', 'name'):
        bucket = samples[product['category_id']]
        if len(bucket) < 5:
            bucket.append(product['name'])

    # Give the reviewers evidence for an attribute recommendation without
    # exposing member details. Values are aggregated, capped examples only.
    product_value_counts: dict[int, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for product in Product.objects.values(
        'category_id', 'attribute_one_value', 'attribute_two_value',
        'attribute_three_value', 'attribute_four_value', 'attribute_five_value',
    ):
        for order, field in enumerate((
            'attribute_one_value', 'attribute_two_value', 'attribute_three_value',
            'attribute_four_value', 'attribute_five_value',
        ), start=1):
            value = (product[field] or '').strip()
            if value:
                product_value_counts[product['category_id']][order][value] += 1
    listing_value_counts: dict[int, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for listing in Order.objects.filter(
        direction=Order.TO_LET, status=Order.ACTIVE,
    ).values(
        'product__category_id', 'attribute_one_value', 'attribute_two_value',
        'attribute_three_value', 'attribute_four_value', 'attribute_five_value',
    ):
        category_id = listing['product__category_id']
        for order, field in enumerate((
            'attribute_one_value', 'attribute_two_value', 'attribute_three_value',
            'attribute_four_value', 'attribute_five_value',
        ), start=1):
            value = (listing[field] or '').strip()
            if value:
                listing_value_counts[category_id][order][value] += 1

    categories = []
    valid_ids = set()
    category_rows = list(
        Category.objects.select_related('parent_category').prefetch_related('category_attributes')
        .order_by('parent_category__title', 'title', 'id')
    )
    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for category in category_rows:
        children_by_parent[category.parent_category_id].append(category.id)

    def subtree_counts(category_id: int) -> tuple[int, int]:
        product_total = product_counts.get(category_id, 0)
        active_listing_total = active_listing_counts.get(category_id, 0)
        for child_id in children_by_parent.get(category_id, []):
            child_products, child_active_listings = subtree_counts(child_id)
            product_total += child_products
            active_listing_total += child_active_listings
        return product_total, active_listing_total

    for category in category_rows:
        valid_ids.add(category.id)
        stats = historical_listing_stats.get(category.id, {})
        category_transaction_stats = transaction_stats.get(category.id, {})
        subtree_product_count, subtree_active_listing_count = subtree_counts(category.id)
        attributes = []
        for definition in category.get_attribute_definitions():
            name = (definition.get('name') or '').strip()
            if not name:
                continue
            source = definition.get('value_source') or 'product'
            values = (
                listing_value_counts[category.id][definition['order']]
                if source == 'listing'
                else product_value_counts[category.id][definition['order']]
            )
            attributes.append({
                'order': definition['order'],
                'name': name,
                'value_source': source,
                'filterable': bool(definition.get('filterable')),
                'allowed_values': (definition.get('allowed_values') or [])[:12],
                'top_observed_values': [
                    {'value': value, 'count': count}
                    for value, count in values.most_common(8)
                ],
            })
        categories.append({
            'id': category.id,
            'title': category.title,
            'parent_id': category.parent_category_id,
            'parent_title': category.parent_category.title if category.parent_category else '',
            'description': (category.description or '').strip()[:280],
            'product_count': product_counts.get(category.id, 0),
            'active_listing_count': active_listing_counts.get(category.id, 0),
            'historical_lend_listing_count': stats.get('historical_lend_listing_count', 0),
            'first_lend_listing_at': stats.get('first_lend_listing_at').isoformat() if stats.get('first_lend_listing_at') else None,
            'last_lend_listing_at': stats.get('last_lend_listing_at').isoformat() if stats.get('last_lend_listing_at') else None,
            'transaction_count': category_transaction_stats.get('transaction_count', 0),
            'completed_rental_count': category_transaction_stats.get('completed_rental_count', 0),
            'last_completed_rental_at': (
                category_transaction_stats.get('last_completed_rental_at').isoformat()
                if category_transaction_stats.get('last_completed_rental_at') else None
            ),
            'subtree_product_count': subtree_product_count,
            'subtree_active_listing_count': subtree_active_listing_count,
            'attribute_definitions': attributes,
            'product_examples': samples.get(category.id, []),
        })

    since = timezone.now() - timedelta(days=365)
    searches = list(
        SearchHistory.objects.filter(searched_at__gte=since).exclude(search_term='')
        .values('search_term').annotate(count=Count('id')).order_by('-count')[:40]
    )
    suggestion_names = list(
        CategorySuggestion.objects.filter(created_at__gte=since)
        .exclude(status=CategorySuggestion.STATUS_APPROVED)
        .values_list('name', flat=True)[:40]
    )
    return {
        'generated_at': timezone.now().isoformat(),
        'categories': categories,
        'top_searches_last_365_days': searches,
        'unpublished_category_suggestions_last_365_days': suggestion_names,
        'category_id_set': sorted(valid_ids),
    }


def _assessment_prompt(snapshot: dict[str, Any]) -> str:
    return (
        'You are reviewing the Rentalution UK peer-to-peer rental catalogue taxonomy. '
        'Use only the supplied evidence. Recommend changes only where material, specific and practical. '
        'Do not recommend electronics, cameras, phones, laptops, TVs, drones, adult content, disposable goods, '
        'or categories that have no evidence of a reusable rental use. Do not invent metrics or product names. '
        'A missing category needs evidence from repeated searches, suggestions, products or a clear gap in the tree. '
        'Use direct and subtree counts correctly: a parent with few direct products may be healthy because its children '
        'hold the listings. Treat completed_rental_count as the best signal of actual rental demand and transaction_count '
        'as interest; listings alone are weaker evidence. Treat a thin category as a possible prune only when it has very '
        'low historical as well as current lending activity, low rental demand, its last lending activity is old, and there '
        'is a clearly better existing target. Do '
        'not prune a new, seasonal, specialist or merely quiet category. A merge/move/split/retire recommendation must '
        'name category IDs and explain likely product/listing impact. Consider a split only for a category with enough '
        'evidence of two durable, meaningful rental groups. If a distinction is better used to filter comparable products '
        '(for example power source), recommend an ATTRIBUTE instead of a split. '
        'Every proposed_action must use exactly one operation: create, move, merge, retire, split, add_attribute, or none. '
        'For create use {operation:"create", title, parent_category_id, description}. '
        'For move use {operation:"move", category_id, parent_category_id}. '
        'For merge/retire use {operation:"merge"|"retire", source_category_id, target_category_id}; the target '
        'must be an existing category and all source products/children will move to it. '
        'For split use {operation:"split", source_category_id, new_categories:[{title,description}]}; only use '
        'split when the source has no products, otherwise say none because product assignment needs human review. '
        'For add_attribute use {operation:"add_attribute", category_id, order, name, value_source, allowed_values}; '
        'order must be an unused whole number from 1 to 5, value_source must be product or listing, and allowed_values '
        'must be 2-12 concise customer-facing choices. Prefer product for inherent characteristics such as petrol, '
        'battery or corded. Never overwrite an existing attribute. '
        'For none use {operation:"none", reason}. '
        'It is valid to return few or no recommendations. Recommendations are advisory only and will be reviewed '
        'by a human; never phrase an action as already completed.\n\n'
        f'Catalogue snapshot:\n{snapshot}'
    )


def draft_taxonomy_assessment(state: TaxonomyState) -> TaxonomyState:
    review = CategoryTaxonomyReview.objects.get(pk=state['review_id'])
    snapshot = catalogue_snapshot()
    review.snapshot = snapshot
    review.status = CategoryTaxonomyReview.STATUS_RUNNING
    review.started_at = timezone.now()
    review.error = ''
    review.save(update_fields=['snapshot', 'status', 'started_at', 'error'])
    assessment = _chat_model().with_structured_output(TaxonomyAssessment).invoke(_assessment_prompt(snapshot))
    data = assessment.model_dump()
    review.llm_analysis = data
    review.save(update_fields=['llm_analysis'])
    return {**state, 'assessment': data}


def build_taxonomy_review_graph():
    graph = StateGraph(TaxonomyState)
    graph.add_node('draft_assessment', draft_taxonomy_assessment)
    graph.add_edge(START, 'draft_assessment')
    graph.add_edge('draft_assessment', END)
    return graph.compile()


def critique_taxonomy_assessment(snapshot: dict[str, Any], assessment: TaxonomyAssessment) -> tuple[TaxonomyCritique, TaxonomyCritique]:
    """Use independent CrewAI reviewers; agreement is required for normal priority."""
    llm = LLM(model=f'openai/{DEFAULT_TEXT_MODEL}', api_key=_api_key(), temperature=0)
    context = (
        f'Catalogue evidence: {snapshot}\n\n'
        f'Proposed assessment: {assessment.model_dump()}'
    )
    operator = Agent(
        role='Marketplace taxonomy operator',
        goal='Keep only changes that improve real customer browsing and can be implemented safely by staff.',
        backstory='You run a practical UK rental catalogue and require evidence before changing its structure.',
        llm=llm, allow_delegation=False, verbose=False,
    )
    skeptic = Agent(
        role='Sceptical taxonomy reviewer',
        goal='Find generic, unsupported, overly broad or misleading AI recommendations.',
        backstory='You challenge catalogue proposals that do not have concrete evidence or clear product impact.',
        llm=llm, allow_delegation=False, verbose=False,
    )
    instruction = (
        context + '\nReview every recommendation by zero-based index. Approve only recommendations with '
        'specific evidence and a sensible, human-implementable action. Flag uncertain or generic suggestions. '
        'Return structured critique.'
    )
    operator_task = Task(
        description=instruction,
        expected_output='Structured approved and concern indexes with concise reasons.',
        agent=operator,
        output_pydantic=TaxonomyCritique,
    )
    skeptic_task = Task(
        description=instruction,
        expected_output='Structured approved and concern indexes with concise reasons.',
        agent=skeptic,
        output_pydantic=TaxonomyCritique,
    )
    crew = Crew(agents=[operator, skeptic], tasks=[operator_task, skeptic_task], process=Process.sequential, verbose=False)
    crew.kickoff()
    first = operator_task.output.pydantic
    second = skeptic_task.output.pydantic
    if not isinstance(first, TaxonomyCritique) or not isinstance(second, TaxonomyCritique):
        raise RuntimeError('CrewAI taxonomy critique returned an invalid structured response.')
    return first, second


def process_taxonomy_review(review_id: int) -> str:
    review = CategoryTaxonomyReview.objects.get(pk=review_id)
    try:
        result = build_taxonomy_review_graph().invoke({'review_id': review_id})
        assessment = TaxonomyAssessment.model_validate(result['assessment'])
        review.refresh_from_db()
        operator, skeptic = critique_taxonomy_assessment(review.snapshot, assessment)
        normal_priority = set(operator.approved_indexes) & set(skeptic.approved_indexes)
        concern_indexes = set(operator.concern_indexes) | set(skeptic.concern_indexes)
        review.crew_critique = {
            'operator': operator.model_dump(),
            'skeptic': skeptic.model_dump(),
            'normal_priority_indexes': sorted(normal_priority),
        }
        review.recommendations.all().delete()
        valid_category_ids = set(review.snapshot.get('category_id_set', []))
        for index, proposal in enumerate(assessment.recommendations):
            affected = [category_id for category_id in proposal.affected_category_ids if category_id in valid_category_ids]
            CategoryTaxonomyRecommendation.objects.create(
                review=review,
                position=index,
                recommendation_type=proposal.recommendation_type,
                title=proposal.title,
                rationale=proposal.rationale,
                evidence=proposal.evidence,
                proposed_action={**proposal.proposed_action, 'affected_category_ids': affected, 'confidence': proposal.confidence},
                ai_critique={
                    'operator_approved': index in operator.approved_indexes,
                    'skeptic_approved': index in skeptic.approved_indexes,
                    'operator_concerns': operator.concerns if index in operator.concern_indexes else [],
                    'skeptic_concerns': skeptic.concerns if index in skeptic.concern_indexes else [],
                },
                status=(
                    CategoryTaxonomyRecommendation.STATUS_PENDING
                    if index in normal_priority and index not in concern_indexes
                    else CategoryTaxonomyRecommendation.STATUS_NEEDS_HUMAN
                ),
            )
        review.status = CategoryTaxonomyReview.STATUS_READY
        review.completed_at = timezone.now()
        review.error = ''
        review.save(update_fields=['crew_critique', 'status', 'completed_at', 'error'])
        return review.status
    except Exception as exc:
        review.status = CategoryTaxonomyReview.STATUS_FAILED
        review.error = str(exc)[:4000]
        review.completed_at = timezone.now()
        review.save(update_fields=['status', 'error', 'completed_at'])
        raise
