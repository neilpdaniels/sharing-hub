import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from common.emails import send_branded_email
from common.failures import record_site_failure

from .category_ai import (
    CategoryAIImageBudgetExceeded,
    generate_category_suggestion_assets,
    process_category_suggestion,
)
from .models import CategorySuggestion, CategoryTaxonomyReview
from .taxonomy_ai import process_taxonomy_review


logger = logging.getLogger(__name__)


@shared_task(queue='catalog_ai', soft_time_limit=720, time_limit=780)
def review_category_suggestion(suggestion_id: int) -> str:
    """Run a suggestion on its isolated, deliberately low-concurrency queue."""
    if not settings.CATEGORY_AI_ENABLED:
        return CategorySuggestion.objects.only('status').get(pk=suggestion_id).status
    try:
        return process_category_suggestion(suggestion_id)
    except Exception as exc:
        logger.exception('Category suggestion %s automation failed', suggestion_id)
        record_site_failure(
            'Category suggestion automation failed',
            details=f'Category suggestion {suggestion_id} could not be processed.',
            exception=exc,
            context={'suggestion_id': suggestion_id},
        )
        # The pipeline has already persisted a useful failure state. Do not
        # retry blindly: image generation and moderation failures need a human
        # to inspect before another paid API call is made.
        return CategorySuggestion.STATUS_FAILED


@shared_task(queue='catalog_ai', soft_time_limit=900, time_limit=960)
def generate_category_suggestion_assets_task(suggestion_id: int) -> str:
    """Paid image work: queued only from an explicit Django-admin action."""
    if not settings.CATEGORY_AI_ENABLED:
        return CategorySuggestion.objects.only('status').get(pk=suggestion_id).status
    try:
        return generate_category_suggestion_assets(suggestion_id)
    except CategoryAIImageBudgetExceeded as exc:
        # This path deliberately leaves the suggestion ready for a later admin
        # retry. SiteFailure records it and emails configured admins.
        record_site_failure(
            'Category AI monthly image budget reached',
            details=str(exc),
            exception=exc,
            context={'suggestion_id': suggestion_id},
        )
        return CategorySuggestion.STATUS_ASSET_REVIEW
    except Exception as exc:
        logger.exception('Category assets for suggestion %s failed', suggestion_id)
        record_site_failure(
            'Category suggestion asset generation failed',
            details=f'Assets for category suggestion {suggestion_id} could not be generated.',
            exception=exc,
            context={'suggestion_id': suggestion_id},
        )
        return CategorySuggestion.STATUS_FAILED


@shared_task(queue='catalog_ai', soft_time_limit=900, time_limit=960)
def run_catalogue_taxonomy_review(review_id: int) -> str:
    """Run a read-only taxonomy assessment requested by an administrator."""
    if not settings.CATEGORY_AI_ENABLED:
        review = CategoryTaxonomyReview.objects.get(pk=review_id)
        review.status = CategoryTaxonomyReview.STATUS_FAILED
        review.error = 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before running a catalogue review.'
        review.save(update_fields=['status', 'error'])
        return review.status
    try:
        return process_taxonomy_review(review_id)
    except Exception as exc:
        logger.exception('Catalogue taxonomy review %s failed', review_id)
        record_site_failure(
            'Catalogue taxonomy review failed',
            details=f'Catalogue taxonomy review {review_id} could not be completed.',
            exception=exc,
            context={'review_id': review_id},
        )
        return CategoryTaxonomyReview.STATUS_FAILED


@shared_task(queue='celery')
def queue_monthly_catalogue_taxonomy_review() -> str:
    """Optional monthly scheduler; never runs more often than every 28 days."""
    if not settings.CATEGORY_TAXONOMY_REVIEW_SCHEDULED_ENABLED:
        return 'disabled'
    latest = CategoryTaxonomyReview.objects.order_by('-created_at').first()
    if latest and latest.created_at >= timezone.now() - timedelta(days=28):
        return 'recent-review-exists'
    review = CategoryTaxonomyReview.objects.create()
    run_catalogue_taxonomy_review.delay(review.pk)
    return f'queued:{review.pk}'


@shared_task(queue='celery')
def send_category_suggestion_decision_email(suggestion_id: int) -> int:
    """Tell a member about an administrator's final decision, once only."""
    suggestion = CategorySuggestion.objects.select_related('user', 'published_category').get(pk=suggestion_id)
    if suggestion.status == CategorySuggestion.STATUS_APPROVED:
        return send_branded_email(
            subject='Your Rentalution category suggestion is live',
            recipient=suggestion.user.email,
            heading='Your category suggestion has been approved',
            intro=(f'“{suggestion.normalized_name or suggestion.name}” is now available to browse '
                   'and use when listing items.'),
            cta_label='Browse categories',
            cta_url=getattr(settings, 'SITE_URL', 'https://rentalution.co.uk'),
        )
    if suggestion.status == CategorySuggestion.STATUS_REJECTED:
        return send_branded_email(
            subject='Update on your Rentalution category suggestion',
            recipient=suggestion.user.email,
            heading='We could not add this category',
            intro=(f'Thanks for suggesting “{suggestion.name}”. It was not added at this time.'),
            details=[suggestion.admin_notes] if suggestion.admin_notes else [],
            cta_label='Suggest another category',
            cta_url=getattr(settings, 'SITE_URL', 'https://rentalution.co.uk') + '/navigation/suggest_category/',
        )
    return 0
