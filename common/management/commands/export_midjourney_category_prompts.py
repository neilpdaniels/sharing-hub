import csv
import json
import re
from pathlib import Path

from common.models import Category, Product
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from common.management.commands.seed_catalog_items import category_payload

CATEGORY_ITEM_HINTS = {
    'Garden': 'a garden hedge trimmer or lawn mower',
    'DIY and power tools': 'a cordless drill, circular saw, or impact driver',
    'Air tools and compressors': 'an air compressor or pneumatic nail gun',
    'Masonry, concrete and demolition': 'a breaker, mixer, or concrete grinder',
    'Event hire': 'a marquee, table, chair, or lighting rig',
    'Home improvement': 'a wallpaper steamer, paint sprayer, or sander',
    'Home and furniture': 'a sofa, table, chair, or bed',
    'Moving and storage': 'a sack truck, trolley, or furniture dolly',
    'Sports equipment': 'a bicycle, goal, or sports training item',
    'Vehicle and accessories': 'a trailer, roof rack, or tow bar accessory',
    'Costumes and fancy dress': 'an adult fancy dress costume outfit or dress-up costume',
    'Costume accessories and props': 'an adult fancy dress costume, mask, wig, hat, cape, or prop',
}

POWERED_CATEGORY_HINTS = {
    'Air tools and compressors',
    'DIY and power tools',
    'Masonry, concrete and demolition',
    'Home improvement',
    'Garden',
    'Vehicle and accessories',
}


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


def html_to_plain_text(value):
    text = re.sub(r'<[^>]+>', ' ', value or '')
    return ' '.join(text.split())


def short_description(value):
    text = html_to_plain_text(value)
    if not text:
        return ''
    sentence = text.split('. ')[0].strip()
    if len(sentence) > 120:
        sentence = sentence[:117].rstrip() + '...'
    return sentence


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


def build_prompt(title, parent_title=None):
    category = Category.objects.filter(title=title).first()
    subject = None
    if category:
        product_names = list(
            Product.objects.filter(category_id=category).order_by('name').values_list('name', flat=True)[:3]
        )
        if not product_names:
            child_categories = list(Category.objects.filter(parent_category=category).order_by('title', 'id'))
            for child in child_categories:
                for name in Product.objects.filter(category_id=child).order_by('name').values_list('name', flat=True)[:3]:
                    product_names.append(name)
                    if len(product_names) >= 3:
                        break
                if len(product_names) >= 3:
                    break
        if product_names:
            powered = any(is_powered_text(name) for name in product_names)
            if len(product_names) == 1:
                subject = dedupe_title_prefix(title, product_names[0])
            elif len(product_names) == 2:
                subject = dedupe_title_prefix(title, f'{product_names[0]} and {product_names[1]}')
            else:
                subject = dedupe_title_prefix(title, f'{product_names[0]}, {product_names[1]}, and {product_names[2]}')
            if powered and subject and not subject.lower().startswith(('electric ', 'powered ')):
                subject = f'electric {subject}'
    if not subject:
        subject = title
    context = f' in the {parent_title.lower()} category' if parent_title else ''
    powered = 'electric ' if title in POWERED_CATEGORY_HINTS else ''
    return (
        f'{title}: {powered}{subject}{context}. '
        'Product photo with a plain light background, single subject or tight grouped scene, '
        'UK 240v mains where relevant, UK plug sockets where relevant, high detail, realistic, '
        'soft studio lighting, no text, no readable product logos, keep them small and illegible, '
        'no watermark, square composition'
    )


class Command(BaseCommand):
    help = 'Export Midjourney prompt packs for seeded catalog categories.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--roots-only',
            action='store_true',
            help='Export top-level categories only.',
        )
        parser.add_argument(
            '--output-dir',
            default='tmp/midjourney_category_prompts',
            help='Directory to write CSV and JSON prompt packs into.',
        )

    def handle(self, *args, **options):
        roots_only = bool(options.get('roots_only'))
        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        for item in category_payload():
            parent_title = item.get('parent_title')
            if roots_only and parent_title is not None:
                continue

            title = item['title']
            slug = slugify(title)
            parent_slug = slugify(parent_title) if parent_title else ''
            rows.append(
                {
                    'title': title,
                    'slug': slug,
                    'parent_title': parent_title or '',
                    'parent_slug': parent_slug,
                    'image_filename': f'{parent_slug + "-" if parent_slug else ""}{slug}.png',
                    'midjourney_prompt': build_prompt(title, parent_title=parent_title),
                }
            )

        csv_path = output_dir / 'midjourney_category_prompts.csv'
        json_path = output_dir / 'midjourney_category_prompts.json'

        with csv_path.open('w', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    'title',
                    'slug',
                    'parent_title',
                    'parent_slug',
                    'image_filename',
                    'midjourney_prompt',
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        json_path.write_text(json.dumps(rows, indent=2), encoding='utf-8')

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported {len(rows)} Midjourney prompts to {csv_path} and {json_path}.'
            )
        )
