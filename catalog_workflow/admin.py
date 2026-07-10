from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.defaultfilters import slugify

from common.management.commands.manage_midjourney_catalog_images import generate_openai_images
from common.management.commands.export_midjourney_category_prompts import (
    CATEGORY_ITEM_HINTS,
    POWERED_CATEGORY_HINTS,
)
from common.models import Product

from .models import ProductDraft


def is_powered_text(value):
    text = (value or '').lower()
    return any(keyword in text for keyword in (
        'electric',
        'electrical',
        'battery',
        'battery-powered',
        'corded',
        'cordless',
        'mains',
        'powered',
        'petrol',
        'diesel',
        'engine',
        'motor',
        'compressor',
        'vacuum',
        'washer',
        'cleaner',
        'spot cleaner',
        'steam cleaner',
    ))


def dedupe_title_prefix(title, subject):
    subject = ' '.join((subject or '').split())
    title = ' '.join((title or '').split())
    if not subject or not title:
        return subject
    subject_lower = subject.lower()
    title_lower = title.lower()
    if subject_lower == title_lower:
        return ''
    if subject_lower.startswith(title_lower + ':'):
        return subject[len(title) + 1 :].strip(' .:-')
    if subject_lower.startswith(title_lower + ','):
        return subject[len(title) + 1 :].strip(' .:-')
    if subject_lower.startswith(title_lower + ' '):
        return subject[len(title) :].strip(' .:-')
    return subject


def build_prompt(draft):
    parent_title = draft.parent_category.title
    subject = CATEGORY_ITEM_HINTS.get(parent_title, draft.title.lower())
    if is_powered_text(draft.title) and subject and not subject.lower().startswith(('electric ', 'powered ')):
        subject = f'electric {subject}'
    if draft.title in POWERED_CATEGORY_HINTS and not subject.lower().startswith('electric '):
        subject = f'electric {subject}'
    subject = dedupe_title_prefix(draft.title, subject)
    return (
        f'{draft.title}: {subject} in the {parent_title.lower()} category. '
        'Product photo with a plain light background, single subject or tight grouped scene, '
        'UK 240v mains where relevant, UK plug sockets where relevant, high detail, realistic, '
        'soft studio lighting, no text, no readable product logos, keep them small and illegible, '
        'no watermark, square composition'
    )


@admin.register(ProductDraft)
class ProductDraftAdmin(admin.ModelAdmin):
    list_display = ('title', 'parent_category', 'status', 'published_product', 'updated_at')
    list_filter = ('status', 'parent_category')
    search_fields = ('title', 'slug', 'description', 'prompt')
    fields = ('title', 'slug', 'parent_category', 'description', 'prompt', 'image', 'status', 'published_product')
    readonly_fields = ('slug', 'published_product')
    actions = ('generate_descriptions', 'generate_images', 'publish_selected')

    def generate_descriptions(self, request, queryset):
        for draft in queryset:
            if not draft.description.strip():
                draft.description = (
                    f"{draft.title} for hire. A practical item for {draft.parent_category.title.lower()} jobs."
                )
            draft.prompt = build_prompt(draft)
            draft.status = ProductDraft.STATUS_GENERATED
            draft.save(update_fields=['description', 'prompt', 'status', 'slug', 'updated_at'])
        self.message_user(request, f'Updated {queryset.count()} draft(s).', level=messages.SUCCESS)

    generate_descriptions.short_description = 'Generate draft descriptions and prompts'

    def generate_images(self, request, queryset):
        count = 0
        for draft in queryset:
            prompt = draft.prompt.strip() or build_prompt(draft)
            paths = generate_openai_images(prompt, count=1)
            if not paths:
                self.message_user(request, f'No image returned for {draft.title}.', level=messages.WARNING)
                continue
            image_path = paths[0]
            with image_path.open('rb') as handle:
                draft.image.save(f'{slugify(draft.title)}{image_path.suffix.lower()}', ContentFile(handle.read()), save=False)
            draft.status = ProductDraft.STATUS_READY
            draft.save(update_fields=['image', 'status', 'updated_at'])
            count += 1
        self.message_user(request, f'Generated {count} image(s).', level=messages.SUCCESS)

    generate_images.short_description = 'Generate OpenAI image for selected drafts'

    @transaction.atomic
    def publish_selected(self, request, queryset):
        published = 0
        for draft in queryset.select_related('parent_category'):
            product, created = Product.objects.get_or_create(
                category_id=draft.parent_category,
                slug=draft.slug,
                defaults={
                    'name': draft.title,
                    'description': draft.description,
                },
            )
            product.name = draft.title
            product.description = draft.description
            if draft.image:
                draft.image.open('rb')
                product.image.save(
                    draft.image.name,
                    ContentFile(draft.image.read()),
                    save=False,
                )
            product.save()
            draft.published_product = product
            draft.status = ProductDraft.STATUS_PUBLISHED
            draft.save(update_fields=['published_product', 'status', 'updated_at'])
            published += 1
        self.message_user(request, f'Published {published} draft(s).', level=messages.SUCCESS)

    publish_selected.short_description = 'Publish selected drafts to products'
