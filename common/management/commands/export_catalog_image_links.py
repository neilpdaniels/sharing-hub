import json
from django.core.management.base import BaseCommand

from common.models import Category, Product


class Command(BaseCommand):
    help = 'Export category and product image paths keyed by slug.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='catalog-image-links.json')

    def handle(self, *args, **options):
        payload = {
            'categories': [],
            'products': [],
        }

        for category in Category.objects.exclude(image='').order_by('slug'):
            payload['categories'].append({
                'slug': category.slug,
                'title': category.title,
                'image': category.image.name,
            })

        for product in Product.objects.exclude(image='').order_by('slug'):
            payload['products'].append({
                'slug': product.slug,
                'name': product.name,
                'image': product.image.name,
            })

        with open(options['output'], 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
            handle.write('\n')

        self.stdout.write(self.style.SUCCESS(f"Wrote {options['output']}"))
