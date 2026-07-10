import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from catalog_workflow.models import ProductDraft
from catalog_workflow.services import publish_draft
from common.models import Category


class Command(BaseCommand):
    help = 'Import a portable product draft bundle and recreate drafts on this environment.'

    def add_arguments(self, parser):
        parser.add_argument('bundle_dir')
        parser.add_argument('--media-root', default='/app/media')
        parser.add_argument('--publish', action='store_true')

    def handle(self, *args, **options):
        bundle_dir = Path(options['bundle_dir'])
        manifest_path = bundle_dir / 'product-drafts.json'
        if not manifest_path.exists():
            raise CommandError(f'Manifest not found: {manifest_path}')

        media_root = Path(options['media_root'])
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))

        created = 0
        updated = 0
        published = 0

        for item in payload:
            category = Category.objects.filter(slug=item.get('parent_category_slug')).first()
            if not category:
                raise CommandError(f"Parent category not found: {item.get('parent_category_slug')}")

            draft, created_flag = ProductDraft.objects.get_or_create(
                slug=item.get('slug'),
                defaults={
                    'title': item.get('title') or '',
                    'parent_category': category,
                    'description': item.get('description') or '',
                    'prompt': item.get('prompt') or '',
                    'status': item.get('status') or ProductDraft.STATUS_DRAFT,
                },
            )
            draft.title = item.get('title') or draft.title
            draft.parent_category = category
            draft.description = item.get('description') or ''
            draft.prompt = item.get('prompt') or ''
            draft.status = item.get('status') or draft.status
            draft.save()

            image_name = (item.get('image') or '').strip()
            if image_name:
                image_path = media_root / image_name
                if not image_path.exists():
                    raise CommandError(f'Image file missing: {image_path}')
                with image_path.open('rb') as handle:
                    draft.image.save(image_name, File(handle), save=False)
                draft.save(update_fields=['image', 'updated_at'])

            if options['publish']:
                product = publish_draft(draft)
                draft.published_product = product
                draft.status = ProductDraft.STATUS_PUBLISHED
                draft.save(update_fields=['published_product', 'status', 'updated_at'])
                published += 1

            if created_flag:
                created += 1
            else:
                updated += 1

        message = f'Imported {created} draft(s), updated {updated} draft(s).'
        if options['publish']:
            message += f' Published {published} draft(s).'
        self.stdout.write(self.style.SUCCESS(message))
