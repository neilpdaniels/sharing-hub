import json
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from common.models import Category, Product


class Command(BaseCommand):
    help = 'Export selected catalog image files plus a slug-keyed mapping into a bundle directory.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            action='append',
            default=[],
            help='Category slug to include. May be repeated.',
        )
        parser.add_argument(
            '--product',
            action='append',
            default=[],
            help='Product slug to include. May be repeated.',
        )
        parser.add_argument(
            '--output-dir',
            default='catalog-image-bundle',
            help='Directory to write the bundle into.',
        )

    def handle(self, *args, **options):
        category_slugs = [slug.strip() for slug in options['category'] if slug.strip()]
        product_slugs = [slug.strip() for slug in options['product'] if slug.strip()]
        if not category_slugs and not product_slugs:
            raise CommandError('Provide at least one --category or --product slug.')

        output_dir = Path(options['output_dir'])
        media_dir = output_dir / 'media'
        media_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            'categories': [],
            'products': [],
        }

        copied = 0

        for slug in category_slugs:
            category = Category.objects.filter(slug=slug).only('slug', 'title', 'image').first()
            if not category:
                raise CommandError(f'Category not found: {slug}')
            if not category.image:
                self.stdout.write(self.style.WARNING(f'Category has no image: {slug}'))
                continue
            source_path = Path(category.image.path)
            if not source_path.exists():
                raise CommandError(f'Category image file missing: {source_path}')
            relative_name = category.image.name
            destination = media_dir / relative_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            payload['categories'].append(
                {
                    'slug': category.slug,
                    'title': category.title,
                    'image': relative_name,
                }
            )
            copied += 1

        for slug in product_slugs:
            product = Product.objects.filter(slug=slug).only('slug', 'name', 'image').first()
            if not product:
                raise CommandError(f'Product not found: {slug}')
            if not product.image:
                self.stdout.write(self.style.WARNING(f'Product has no image: {slug}'))
                continue
            source_path = Path(product.image.path)
            if not source_path.exists():
                raise CommandError(f'Product image file missing: {source_path}')
            relative_name = product.image.name
            destination = media_dir / relative_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            payload['products'].append(
                {
                    'slug': product.slug,
                    'name': product.name,
                    'image': relative_name,
                }
            )
            copied += 1

        manifest_path = output_dir / 'catalog-image-links.json'
        with manifest_path.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
            handle.write('\n')

        self.stdout.write(self.style.SUCCESS(f'Wrote bundle to {output_dir} ({copied} images).'))
