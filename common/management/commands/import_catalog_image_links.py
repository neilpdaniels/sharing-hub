import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from common.models import Category, Product


class Command(BaseCommand):
    help = 'Apply category and product image paths from a slug-keyed JSON mapping.'

    def add_arguments(self, parser):
        parser.add_argument('mapping_file')
        parser.add_argument('--media-root', default='/app/media')

    def handle(self, *args, **options):
        mapping_path = Path(options['mapping_file'])
        if not mapping_path.exists():
            raise CommandError(f'Mapping file not found: {mapping_path}')

        media_root = Path(options['media_root'])
        payload = json.loads(mapping_path.read_text(encoding='utf-8'))
        updated_categories = 0
        updated_products = 0

        for item in payload.get('categories', []):
            image_name = (item.get('image') or '').strip()
            if not image_name:
                continue
            category = Category.objects.filter(slug=item.get('slug')).first()
            if not category:
                continue
            if not (media_root / image_name).exists():
                self.stdout.write(self.style.WARNING(f'Missing category file: {image_name}'))
                continue
            category.image.name = image_name
            category.save(update_fields=['image'])
            updated_categories += 1

        for item in payload.get('products', []):
            image_name = (item.get('image') or '').strip()
            if not image_name:
                continue
            product = Product.objects.filter(slug=item.get('slug')).first()
            if not product:
                continue
            if not (media_root / image_name).exists():
                self.stdout.write(self.style.WARNING(f'Missing product file: {image_name}'))
                continue
            product.image.name = image_name
            product.save(update_fields=['image'])
            updated_products += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Image links applied: {updated_categories} categories, {updated_products} products.'
            )
        )
