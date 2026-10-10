"""Durable, review-first automation for member category suggestions.

No result from this module publishes a category.  The pipeline prepares a
well-documented recommendation and stops at ``ADMIN_REVIEW`` for a person to
edit, promote or reject it in Django admin.
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal, TypedDict

from crewai import Agent, Crew, LLM, Process, Task
from django.conf import settings
from django.core.files import File
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from common.management.commands.manage_midjourney_catalog_images import (
    build_openai_prompt,
    generate_openai_images,
)
from common.models import Category

from .models import CategorySuggestion, CategorySuggestionImage


DEFAULT_TEXT_MODEL = os.environ.get('CATEGORY_AI_TEXT_MODEL', 'gpt-4.1-mini')
DEFAULT_IMAGE_MODEL = os.environ.get('CATEGORY_AI_IMAGE_MODEL', 'gpt-image-1')

# This is a deterministic backstop.  The policy model also receives the rules,
# but clear-cut prohibited requests must not depend on a model call succeeding.
DISALLOWED_TERMS = (
    'camera', 'webcam', 'laptop', 'tablet', 'mobile phone', 'smartphone',
    'television', 'tv ', 'drone', 'game console', 'vape', 'weapon', 'gun',
    'knife', 'ammunition', 'adult toy', 'sex toy', 'porn', 'drug',
)
SINGLE_USE_TERMS = (
    'party balloon', 'disposable', 'single-use', 'single use', 'confetti',
    'cake', 'food', 'drink', 'consumable',
)


class DuplicateDecision(BaseModel):
    is_duplicate: bool
    confidence: float = Field(ge=0, le=1)
    matching_category_ids: list[int] = Field(default_factory=list)
    rationale: str = Field(max_length=600)


class SuitabilityDecision(BaseModel):
    approved: bool
    parent_category_id: int | None = None
    rationale: str = Field(max_length=700)
    concerns: list[str] = Field(default_factory=list)


class DescriptionDraft(BaseModel):
    description: str = Field(min_length=25, max_length=360)


class QualityReview(BaseModel):
    approved: bool
    score: int = Field(ge=0, le=10)
    revision_notes: list[str] = Field(default_factory=list)
    summary: str = Field(max_length=700)


class ReviewState(TypedDict, total=False):
    suggestion_id: int
    duplicate: bool
    policy_approved: bool
    ready_for_images: bool


class CategoryAIImageBudgetExceeded(RuntimeError):
    """Raised before an image API call when the month’s allowance is spent."""


def _api_key() -> str:
    key = os.environ.get('OPEN_AI_API_SECRET')
    if not key:
        raise RuntimeError('OPEN_AI_API_SECRET is not configured for the category AI worker.')
    return key


def _chat_model() -> ChatOpenAI:
    return ChatOpenAI(model=DEFAULT_TEXT_MODEL, api_key=_api_key(), temperature=0)


def _clean(value: str) -> str:
    return ' '.join((value or '').split())


def _category_context() -> list[dict[str, Any]]:
    return [
        {
            'id': category.id,
            'title': _clean(category.title),
            'parent': _clean(category.parent_category.title) if category.parent_category else None,
            'description': _clean(category.description or '')[:240],
        }
        for category in Category.objects.select_related('parent_category').order_by('title', 'id')
    ]


def _root_categories() -> list[dict[str, Any]]:
    return [item for item in _category_context() if not item['parent'] and item['title'].lower() != 'top']


def _shortlist(name: str, categories: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    needle = _clean(name).lower()
    ranked = sorted(
        categories,
        key=lambda item: max(
            SequenceMatcher(None, needle, item['title'].lower()).ratio(),
            1.0 if needle in item['title'].lower() or item['title'].lower() in needle else 0,
        ),
        reverse=True,
    )
    return ranked[:limit]


def _suggestion(suggestion_id: int) -> CategorySuggestion:
    return CategorySuggestion.objects.select_related('category', 'user').get(pk=suggestion_id)


def _save_stage(suggestion: CategorySuggestion, status: str, **values: Any) -> None:
    suggestion.status = status
    suggestion.pipeline_error = ''
    for key, value in values.items():
        setattr(suggestion, key, value)
    suggestion.save()


def check_duplicate(state: ReviewState) -> ReviewState:
    suggestion = _suggestion(state['suggestion_id'])
    categories = _category_context()
    candidates = _shortlist(suggestion.name, categories)
    name = _clean(suggestion.name)
    exact = [item for item in candidates if item['title'].casefold() == name.casefold()]
    if exact:
        decision = DuplicateDecision(
            is_duplicate=True, confidence=1, matching_category_ids=[item['id'] for item in exact],
            rationale='An existing category has the same title.',
        )
    else:
        decision = _chat_model().with_structured_output(DuplicateDecision).invoke(
            'You review a UK peer-to-peer rental catalogue. Decide whether the requested '
            'category is substantially the same as one already present. Similar wording is '
            'not enough if users would reasonably browse them separately.\n\n'
            f'Requested category: {name}\nMember context: {_clean(suggestion.description)[:700]}\n'
            f'Likely existing matches: {candidates}'
        )
    data = decision.model_dump()
    _save_stage(suggestion, CategorySuggestion.STATUS_DUPLICATE if decision.is_duplicate else CategorySuggestion.STATUS_SCREENING,
                normalized_name=name, duplicate_matches=data,
                pipeline_state={**suggestion.pipeline_state, 'duplicate_checked_at': timezone.now().isoformat()})
    return {**state, 'duplicate': decision.is_duplicate}


def route_after_duplicate(state: ReviewState) -> Literal['end', 'policy']:
    return 'end' if state.get('duplicate') else 'policy'


def check_policy(state: ReviewState) -> ReviewState:
    suggestion = _suggestion(state['suggestion_id'])
    text = f'{suggestion.name} {suggestion.description}'.lower()
    hard_stop = [term for term in (*DISALLOWED_TERMS, *SINGLE_USE_TERMS) if term in text]
    roots = _root_categories()
    if hard_stop:
        decision = SuitabilityDecision(
            approved=False, rationale='The request triggered the catalogue safety/suitability rules.',
            concerns=[f'Contains disallowed or unsuitable term: {term}' for term in hard_stop],
        )
    else:
        decision = _chat_model().with_structured_output(SuitabilityDecision).invoke(
            'You enforce Rentalution category policy for a UK peer-to-peer rental marketplace. '
            'Approve only reusable, lawful, practical items that a neighbour could reasonably lend. '
            'Reject adult/inappropriate material, weapons, drugs, disposable or single-use items, '
            'and consumer electronic products such as cameras, phones, laptops, TVs, drones or consoles. '
            'If approved, choose exactly one fitting root category ID from the provided list.\n\n'
            f'Requested category: {_clean(suggestion.name)}\n'
            f'Member context: {_clean(suggestion.description)[:900]}\n'
            f'Permitted root categories: {roots}'
        )
    root_ids = {item['id'] for item in roots}
    if decision.approved and decision.parent_category_id not in root_ids:
        decision.approved = False
        decision.concerns.append('The selected parent was not a permitted root category.')
    parent = Category.objects.filter(pk=decision.parent_category_id).first() if decision.approved else None
    data = decision.model_dump()
    _save_stage(
        suggestion,
        CategorySuggestion.STATUS_SCREENING if decision.approved else CategorySuggestion.STATUS_POLICY_REJECTED,
        proposed_parent=parent,
        policy_result=data,
        pipeline_state={**suggestion.pipeline_state, 'policy_checked_at': timezone.now().isoformat()},
    )
    return {**state, 'policy_approved': decision.approved}


def route_after_policy(state: ReviewState) -> Literal['end', 'description']:
    return 'description' if state.get('policy_approved') else 'end'


def draft_description(state: ReviewState) -> ReviewState:
    suggestion = _suggestion(state['suggestion_id'])
    parent = suggestion.proposed_parent
    draft = _chat_model().with_structured_output(DescriptionDraft).invoke(
        'Write a factual 1–2 sentence category description for Rentalution, a UK neighbour-to-neighbour '
        'rental marketplace. Describe the kinds of durable items users will find in the category and the '
        'typical use. Use plain British English. Do not mention AI, Rentalution, safety claims, prices, '
        'marketing language, calls to action, or generic filler.\n\n'
        f'Category: {_clean(suggestion.name)}\nParent heading: {parent.title if parent else ""}\n'
        f'Member context (only if useful): {_clean(suggestion.description)[:700]}'
    )
    _save_stage(
        suggestion,
        CategorySuggestion.STATUS_GENERATING,
        proposed_description=_clean(draft.description),
        pipeline_state={**suggestion.pipeline_state, 'description_drafted_at': timezone.now().isoformat()},
    )
    return {**state, 'ready_for_images': True}


def build_category_review_graph():
    graph = StateGraph(ReviewState)
    graph.add_node('duplicate', check_duplicate)
    graph.add_node('policy', check_policy)
    graph.add_node('description', draft_description)
    graph.add_edge(START, 'duplicate')
    graph.add_conditional_edges('duplicate', route_after_duplicate, {'end': END, 'policy': 'policy'})
    graph.add_conditional_edges('policy', route_after_policy, {'end': END, 'description': 'description'})
    graph.add_edge('description', END)
    return graph.compile()


def generate_image_candidates(
    suggestion: CategorySuggestion, *, revision_notes: list[str] | None = None,
) -> list[CategorySuggestionImage]:
    """Reuse the existing OpenAI catalogue-image generator without its GUI."""
    parent_title = suggestion.proposed_parent.title if suggestion.proposed_parent else ''
    prompt = build_openai_prompt({
        'type': 'category',
        'title': suggestion.normalized_name or _clean(suggestion.name),
        'category_title': parent_title,
        'parent_title': parent_title,
    })
    if revision_notes:
        prompt += ' Additional art-direction corrections: ' + ' '.join(_clean(note) for note in revision_notes[:5])
    paths = generate_openai_images(prompt, count=2, model=DEFAULT_IMAGE_MODEL)
    candidates: list[CategorySuggestionImage] = []
    for path in paths:
        source = Path(path)
        with source.open('rb') as image_file:
            candidate = CategorySuggestionImage(suggestion=suggestion, prompt=prompt)
            candidate.image.save(source.name, File(image_file), save=True)
            candidates.append(candidate)
    suggestion.proposed_image_prompt = prompt
    suggestion.pipeline_state = {**suggestion.pipeline_state, 'images_generated_at': timezone.now().isoformat()}
    suggestion.save(update_fields=['proposed_image_prompt', 'pipeline_state', 'updated_at'])
    return candidates


def _check_image_budget(candidate_count: int = 2) -> None:
    limit = settings.CATEGORY_AI_MONTHLY_IMAGE_LIMIT
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = CategorySuggestionImage.objects.filter(created_at__gte=month_start).count()
    if limit <= 0 or used + candidate_count > limit:
        raise CategoryAIImageBudgetExceeded(
            f'Monthly catalogue image budget reached ({used}/{limit} image candidates used).'
        )


def revise_description_for_quality(suggestion: CategorySuggestion, review: QualityReview) -> None:
    """Feed the quality crew's concrete notes back to the writing stage once."""
    revision_notes = '; '.join(_clean(note) for note in review.revision_notes[:8])
    draft = _chat_model().with_structured_output(DescriptionDraft).invoke(
        'Revise this factual UK peer-to-peer rental category description using the editor notes. '
        'Keep it to one or two plain-English sentences. Do not add marketing, safety claims, AI references, '
        'prices, a call to action or vague filler.\n\n'
        f'Category: {suggestion.normalized_name or suggestion.name}\n'
        f'Current description: {suggestion.proposed_description}\n'
        f'Editor notes: {revision_notes}'
    )
    suggestion.proposed_description = _clean(draft.description)
    suggestion.pipeline_state = {
        **suggestion.pipeline_state,
        'quality_revision_notes': review.revision_notes,
        'quality_copy_revised_at': timezone.now().isoformat(),
    }
    suggestion.save(update_fields=['proposed_description', 'pipeline_state', 'updated_at'])


def quality_review(suggestion: CategorySuggestion, candidates: list[CategorySuggestionImage]) -> QualityReview:
    """Use two specialised CrewAI reviewers and require agreement before admin review.

    The reviewers assess whether the copy/image brief is specific, catalogue-ready and free of
    obvious generative clichés. The administrator still makes the final publication decision.
    """
    llm = LLM(model=f'openai/{DEFAULT_TEXT_MODEL}', api_key=_api_key(), temperature=0)
    context = (
        f'Category: {suggestion.normalized_name or suggestion.name}\n'
        f'Parent: {suggestion.proposed_parent.title if suggestion.proposed_parent else ""}\n'
        f'Description: {suggestion.proposed_description}\n'
        f'Image brief: {suggestion.proposed_image_prompt}\n'
        f'Generated candidate count: {len(candidates)}'
    )
    copy_editor = Agent(
        role='Rental catalogue copy editor',
        goal='Reject generic, promotional, inaccurate or AI-sounding category copy.',
        backstory='You edit concise UK marketplace catalogue copy for clarity and accuracy.',
        llm=llm, allow_delegation=False, verbose=False,
    )
    art_director = Agent(
        role='Rental catalogue art director',
        goal='Reject vague or unsafe image briefs that would create an unhelpful catalogue image.',
        backstory='You set practical, realistic product-photo briefs for a UK rental catalogue.',
        llm=llm, allow_delegation=False, verbose=False,
    )
    copy_task = Task(
        description=(context + '\nAssess only the category description. Approve it only if factual, '
                     'specific, natural and useful. Return structured review.'),
        expected_output='A structured quality decision with score and revision notes.',
        agent=copy_editor, output_pydantic=QualityReview,
    )
    image_task = Task(
        description=(context + '\nAssess only the image brief and generated-image plan. Approve only if it '
                     'would yield a recognisable, realistic, text-free catalogue image and does not rely on '
                     'AI-style clichés. Inspect the attached generated candidates where available; reject '
                     'visible text, impossible geometry, plastic-looking materials, or an unclear subject. '
                     'Return structured review.'),
        expected_output='A structured quality decision with score and revision notes.',
        agent=art_director,
        input_files={
            f'candidate_{candidate.pk}': candidate.image.path
            for candidate in candidates if candidate.image
        },
        output_pydantic=QualityReview,
    )
    crew = Crew(agents=[copy_editor, art_director], tasks=[copy_task, image_task], process=Process.sequential, verbose=False)
    crew.kickoff()
    copy_result = copy_task.output.pydantic
    image_result = image_task.output.pydantic
    if not isinstance(copy_result, QualityReview) or not isinstance(image_result, QualityReview):
        raise RuntimeError('CrewAI quality review returned an invalid structured response.')
    notes = [*copy_result.revision_notes, *image_result.revision_notes]
    return QualityReview(
        approved=copy_result.approved and image_result.approved and copy_result.score >= 7 and image_result.score >= 7,
        score=min(copy_result.score, image_result.score),
        revision_notes=notes,
        summary=f'Copy: {copy_result.summary} Image: {image_result.summary}',
    )


def process_category_suggestion(suggestion_id: int) -> str:
    """Run the inexpensive screening graph and wait for staff image approval."""
    with transaction.atomic():
        suggestion = CategorySuggestion.objects.select_for_update().get(pk=suggestion_id)
        if suggestion.status in {CategorySuggestion.STATUS_APPROVED, CategorySuggestion.STATUS_REJECTED}:
            return suggestion.status
        suggestion.processing_attempts += 1
        suggestion.status = CategorySuggestion.STATUS_SCREENING
        suggestion.pipeline_error = ''
        suggestion.save(update_fields=['processing_attempts', 'status', 'pipeline_error', 'updated_at'])

    try:
        result = build_category_review_graph().invoke({'suggestion_id': suggestion_id})
        if result.get('duplicate') or not result.get('policy_approved'):
            return _suggestion(suggestion_id).status
        suggestion = _suggestion(suggestion_id)
        _save_stage(
            suggestion,
            CategorySuggestion.STATUS_ASSET_REVIEW,
            processed_at=timezone.now(),
            pipeline_state={
                **suggestion.pipeline_state,
                'ready_for_staff_image_generation_at': timezone.now().isoformat(),
            },
        )
        return suggestion.status
    except Exception as exc:
        suggestion = _suggestion(suggestion_id)
        suggestion.status = CategorySuggestion.STATUS_FAILED
        suggestion.pipeline_error = str(exc)[:4000]
        suggestion.processed_at = timezone.now()
        suggestion.save(update_fields=['status', 'pipeline_error', 'processed_at', 'updated_at'])
        raise


def generate_category_suggestion_assets(suggestion_id: int) -> str:
    """Generate and quality-review assets only after an explicit admin action."""
    with transaction.atomic():
        suggestion = CategorySuggestion.objects.select_for_update().get(pk=suggestion_id)
        if suggestion.status not in {
            CategorySuggestion.STATUS_ASSET_REVIEW,
            CategorySuggestion.STATUS_GENERATING,
        }:
            return suggestion.status
        suggestion.status = CategorySuggestion.STATUS_GENERATING
        suggestion.pipeline_error = ''
        suggestion.save(update_fields=['status', 'pipeline_error', 'updated_at'])

    try:
        suggestion = _suggestion(suggestion_id)
        review: QualityReview | None = None
        revision_notes: list[str] | None = None
        # Two passes make quality feedback actionable without creating an
        # unbounded paid generation loop. Both sets of candidates remain in
        # admin for audit and manual selection.
        for attempt in range(2):
            _check_image_budget()
            candidates = generate_image_candidates(suggestion, revision_notes=revision_notes)
            if not candidates:
                raise RuntimeError('Image generation returned no usable candidates.')
            _save_stage(suggestion, CategorySuggestion.STATUS_QUALITY_REVIEW)
            review = quality_review(suggestion, candidates)
            if review.approved:
                break
            if attempt == 0:
                revise_description_for_quality(suggestion, review)
                suggestion = _suggestion(suggestion_id)
                revision_notes = review.revision_notes
                _save_stage(suggestion, CategorySuggestion.STATUS_GENERATING)
        assert review is not None
        suggestion = _suggestion(suggestion_id)
        suggestion.quality_review = review.model_dump()
        suggestion.processed_at = timezone.now()
        suggestion.status = (
            CategorySuggestion.STATUS_ADMIN_REVIEW
            if review.approved else CategorySuggestion.STATUS_ASSET_REVIEW
        )
        if not review.approved:
            suggestion.pipeline_state = {
                **suggestion.pipeline_state,
                'quality_revision_exhausted_at': timezone.now().isoformat(),
            }
        suggestion.save()
        return suggestion.status
    except CategoryAIImageBudgetExceeded as exc:
        suggestion = _suggestion(suggestion_id)
        suggestion.status = CategorySuggestion.STATUS_ASSET_REVIEW
        suggestion.pipeline_error = str(exc)
        suggestion.save(update_fields=['status', 'pipeline_error', 'updated_at'])
        raise
    except Exception as exc:
        suggestion = _suggestion(suggestion_id)
        suggestion.status = CategorySuggestion.STATUS_FAILED
        suggestion.pipeline_error = str(exc)[:4000]
        suggestion.processed_at = timezone.now()
        suggestion.save(update_fields=['status', 'pipeline_error', 'processed_at', 'updated_at'])
        raise
