import json
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_workflow.models import ProductDraft


class Command(BaseCommand):
    help = 'Export one or more product drafts into a portable bundle with metadata and media.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--draft',
            action='append',
            default=[],
            help='ProductDraft id to export. May be repeated.',
        )
        parser.add_argument(
            '--output-dir',
            default='catalog-draft-bundle',
            help='Directory to write the bundle into.',
        )

    def handle(self, *args, **options):
        draft_ids = [value for value in options['draft'] if str(value).strip()]
        if not draft_ids:
            raise CommandError('Provide at least one --draft id.')

        drafts = ProductDraft.objects.select_related('parent_category').filter(id__in=draft_ids)
        found_ids = {str(draft.id) for draft in drafts}
        missing = [draft_id for draft_id in draft_ids if str(draft_id) not in found_ids]
        if missing:
            raise CommandError(f'Draft(s) not found: {", ".join(missing)}')

        output_dir = Path(options['output_dir'])
        media_dir = output_dir / 'media'
        media_dir.mkdir(parents=True, exist_ok=True)

        payload = []
        copied = 0

        for draft in drafts:
            image_name = ''
            if draft.image:
                source_path = Path(draft.image.path)
                if not source_path.exists():
                    raise CommandError(f'Image file missing for draft {draft.id}: {source_path}')
                image_name = draft.image.name
                destination = media_dir / image_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination)
                copied += 1

            payload.append(
                {
                    'title': draft.title,
                    'slug': draft.slug,
                    'parent_category_slug': draft.parent_category.slug,
                    'description': draft.description,
                    'prompt': draft.prompt,
                    'status': draft.status,
                    'image': image_name,
                }
            )

        manifest_path = output_dir / 'product-drafts.json'
        with manifest_path.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
            handle.write('\n')

        self.stdout.write(self.style.SUCCESS(f'Wrote {manifest_path} with {copied} images.'))
