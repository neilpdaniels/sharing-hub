import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.text import slugify

from common.emails import send_branded_email
from common.failures import record_site_failure
from common.management.commands.manage_midjourney_catalog_images import generate_openai_images
from common.models import CatalogImageCandidate, CatalogImageGeneration, Product

from .category_ai import (
    CategoryAIImageBudgetExceeded,
    generate_category_suggestion_assets,
    process_category_suggestion,
)
from .models import CatalogueCleanupReview, CatalogueProductReview, CategorySuggestion, CategoryTaxonomyReview
from .product_catalogue_ai import process_product_catalogue_review
from .taxonomy_ai import process_taxonomy_review


logger = logging.getLogger(__name__)


@shared_task(queue='catalog_ai', soft_time_limit=180, time_limit=240)
def generate_catalogue_product_image(
    product_id: int,
    *,
    prompt_prefix: str = '',
    model: str,
    quality: str,
    candidate_count: int,
    skip_if_image_exists: bool,
    requested_by_id: int | None,
) -> str:
    """Generate review-only product image candidates from the category batch UI."""
    product = Product.objects.get(pk=product_id)
    if skip_if_image_exists and product.image:
        return 'skipped_existing_image'

    description = ' '.join((product.description or '').split())
    prompt = ' '.join(part for part in (
        prompt_prefix.strip(),
        product.name + (f'. {description}' if description else ''),
        'Create a realistic, trustworthy UK rental catalogue image: one clear subject, plain light background, '
        'soft studio lighting, square composition, no text, no watermark and no readable brand logos.',
    ) if part)
    generation = CatalogImageGeneration.objects.create(
        product=product,
        prompt=prompt,
        model=model,
        quality=quality,
        size='1024x1024',
        requested_count=candidate_count,
        created_by_id=requested_by_id,
    )
    try:
        paths = generate_openai_images(
            prompt,
            count=candidate_count,
            model=model,
            quality=quality,
            size=generation.size,
        )
        for position, image_path in enumerate(paths, start=1):
            with image_path.open('rb') as handle:
                candidate = CatalogImageCandidate(generation=generation, position=position)
                candidate.image.save(
                    f'{slugify(product.name)}-{generation.pk}-{position}{image_path.suffix.lower()}',
                    ContentFile(handle.read()),
                    save=True,
                )
    except (CommandError, OSError) as exc:
        generation.delete()
        logger.exception('Catalogue image generation failed for product %s', product_id)
        record_site_failure(
            'Batch catalogue image generation failed',
            details=f'Product {product_id} image generation failed: {exc}',
            exception=exc,
            context={'product_id': product_id, 'model': model, 'quality': quality},
        )
        return 'failed'
    return 'generated'


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


@shared_task(queue='catalog_ai', soft_time_limit=900, time_limit=960)
def run_catalogue_product_review(review_id: int) -> str:
    if not settings.CATEGORY_AI_ENABLED:
        review = CatalogueProductReview.objects.get(pk=review_id)
        review.status = CatalogueProductReview.STATUS_FAILED
        review.error = 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before running a product review.'
        review.save(update_fields=['status', 'error'])
        return review.status
    try:
        return process_product_catalogue_review(review_id)
    except Exception as exc:
        logger.exception('Catalogue product review %s failed', review_id)
        record_site_failure('Catalogue product review failed', details=f'Catalogue product review {review_id} could not be completed.', exception=exc, context={'review_id': review_id})
        return CatalogueProductReview.STATUS_FAILED


@shared_task(queue='catalog_ai', soft_time_limit=1800, time_limit=1860)
def run_catalogue_cleanup_review(cleanup_review_id: int) -> str:
    """Run product and category-tree analysis as one staff-requested review."""
    cleanup = CatalogueCleanupReview.objects.get(pk=cleanup_review_id)
    if not settings.CATEGORY_AI_ENABLED:
        cleanup.status = CatalogueCleanupReview.STATUS_FAILED
        cleanup.error = 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before running a catalogue cleanup review.'
        cleanup.completed_at = timezone.now()
        cleanup.save(update_fields=['status', 'error', 'completed_at'])
        return cleanup.status

    cleanup.status = CatalogueCleanupReview.STATUS_RUNNING
    cleanup.started_at = timezone.now()
    cleanup.error = ''
    cleanup.save(update_fields=['status', 'started_at', 'error'])
    product_review = CatalogueProductReview.objects.create(
        requested_by=cleanup.requested_by,
        review_strength=cleanup.review_strength,
        prune_target_percent=cleanup.prune_target_percent,
    )
    taxonomy_review = CategoryTaxonomyReview.objects.create(
        requested_by=cleanup.requested_by,
        review_strength=cleanup.review_strength,
    )
    cleanup.product_review = product_review
    cleanup.taxonomy_review = taxonomy_review
    cleanup.save(update_fields=['product_review', 'taxonomy_review'])

    errors = []
    try:
        process_product_catalogue_review(product_review.pk)
    except Exception as exc:
        logger.exception('Catalogue cleanup %s product review failed', cleanup.pk)
        errors.append(f'Product review: {exc}')
    try:
        process_taxonomy_review(taxonomy_review.pk)
    except Exception as exc:
        logger.exception('Catalogue cleanup %s taxonomy review failed', cleanup.pk)
        errors.append(f'Taxonomy review: {exc}')

    cleanup.status = (
        CatalogueCleanupReview.STATUS_READY if not errors
        else CatalogueCleanupReview.STATUS_PARTIAL
    )
    cleanup.error = '\n'.join(errors)[:4000]
    cleanup.completed_at = timezone.now()
    cleanup.save(update_fields=['status', 'error', 'completed_at'])
    return cleanup.status


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
            subject='Your Rentalution catalogue suggestion is live',
            recipient=suggestion.user.email,
            heading=f'Your {"product" if suggestion.proposal_kind == "PRODUCT" else "category"} suggestion has been approved',
            intro=(f'“{suggestion.normalized_name or suggestion.name}” is now available to browse '
                   'and use when listing items.'),
            cta_label='Browse categories',
            cta_url=getattr(settings, 'SITE_URL', 'https://rentalution.co.uk'),
        )
    if suggestion.status == CategorySuggestion.STATUS_REJECTED:
        return send_branded_email(
            subject='Update on your Rentalution item suggestion',
            recipient=suggestion.user.email,
            heading='We could not add this item',
            intro=(f'Thanks for suggesting “{suggestion.name}”. It was not added at this time.'),
            details=[suggestion.admin_notes] if suggestion.admin_notes else [],
            cta_label='Suggest another item',
            cta_url=getattr(settings, 'SITE_URL', 'https://rentalution.co.uk') + '/navigation/suggest_category/',
        )
    return 0
