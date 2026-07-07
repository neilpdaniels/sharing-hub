import json
import mimetypes
import os
import re
import subprocess
import shutil
import time
from base64 import b64decode
from pathlib import Path

import requests
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from common.models import (
    Category,
    Product,
    IMAGE_REVIEW_AWAITING,
    IMAGE_REVIEW_DONE_ELSEWHERE,
    IMAGE_REVIEW_PENDING,
    IMAGE_REVIEW_REVIEWED,
    IMAGE_REVIEW_SKIPPED,
)


STATE_VERSION = 1
OPENAI_IMAGE_SIZE = '1024x1024'
DEFAULT_OPENAI_IMAGE_MODEL = 'gpt-image-1'
DEFAULT_OPENAI_IMAGE_QUALITY = 'medium'

OPENAI_IMAGE_MODELS = {
    'gpt-image-1': {
        'label': 'gpt-image-1',
        'model': 'gpt-image-1',
    },
    'gpt-image-1.5': {
        'label': 'gpt-image-1.5',
        'model': 'gpt-image-1.5',
    },
    'gpt-image-1-mini': {
        'label': 'gpt-image-1-mini',
        'model': 'gpt-image-1-mini',
    },
    'gpt-image-2': {
        'label': 'gpt-image-2',
        'model': 'gpt-image-2',
    },
}

OPENAI_IMAGE_QUALITIES = ('low', 'medium', 'high')

SAFE_CATEGORY_TITLES = {
    'Home improvement',
    'DIY and power tools',
    'Air tools and compressors',
    'Garden',
    'Event hire',
    'Home and furniture',
    'Moving and storage',
    'Sports equipment',
    'Vehicle and accessories',
    'Costumes and fancy dress',
    'Masonry, concrete and demolition',
}

LIKELY_HARD_KEYWORDS = (
    'acrow',
    'breaker',
    'compactor',
    'compressor',
    'core drill',
    'drywall screw gun',
    'hog roast',
    'log splitter',
    'magnetic drill',
    'mini digger',
    'mitre saw stand',
    'plate compactor',
    'post rammer',
    'rotovator',
    'sack truck',
    'scarifier',
    'sds',
    'stump grinder',
    'tile saw',
    'track saw',
    'trencher',
    'wallpaper steamer',
    'wacker',
)

DO_NOT_BOTHER_KEYWORDS = (
    'acrow',
    'breaker',
    'core drill',
    'drywall screw gun',
    'magnetic drill',
    'mini digger',
    'post rammer',
    'stump grinder',
    'trencher',
)

BACKGROUND_MAP = {
    'Home improvement': 'simple softly blurred modern home interior background',
    'DIY and power tools': 'simple softly blurred workshop background',
    'Air tools and compressors': 'simple softly blurred garage workshop background',
    'Masonry, concrete and demolition': 'simple softly blurred construction site background',
    'Garden': 'simple softly blurred garden yard background',
    'Event hire': 'simple softly blurred outdoor event lawn background',
    'Home and furniture': 'simple softly blurred clean home interior background',
    'Moving and storage': 'simple softly blurred warehouse background',
    'Sports equipment': 'simple softly blurred sport-specific outdoor background',
    'Vehicle and accessories': 'simple softly blurred driveway background',
    'Costumes and fancy dress': 'simple softly blurred plain event backdrop background',
}

CATEGORY_SUBJECT_HINTS = {
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

ITEM_VISUAL_HINTS = {
    'log splitter': 'a horizontal hydraulic firewood splitter with a long steel beam, splitting wedge, hydraulic ram, support legs, and transport wheels',
    'rotovator': 'a walk-behind garden tiller with a compact engine, tall handles, wheels, and rotating tines underneath for turning soil',
    'scarifier': 'a walk-behind lawn machine with a compact engine, folding handle, four wheels, and a rotating drum underneath for lifting moss and thatch',
    'plate compactor': 'a compact groundworks machine with a heavy flat steel base plate, engine on top, protective frame, and upright folding handle',
    'wacker plate': 'a compact groundworks machine with a heavy flat steel base plate, engine on top, protective frame, and upright folding handle',
    'post rammer': 'a handheld cylindrical steel tool with side handles used to drive fence posts into the ground',
    'acrow props': 'adjustable steel support props with threaded collars and square end plates used as temporary building supports',
    'mini digger': 'a compact tracked excavator with a cab, boom arm, dipper arm, and digging bucket',
    'stump grinder': 'a compact machine with wheels, handlebars, engine, and a front cutting wheel used for grinding down tree stumps',
    'hog roast machine': 'a stainless steel outdoor catering spit-roast machine with a roasting chamber, frame, and wheels',
}

POWERED_KEYWORDS = (
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
)


def is_powered_text(value):
    text = (value or '').lower()
    return any(keyword in text for keyword in POWERED_KEYWORDS)


def power_hint_for_item(item):
    text = ' '.join(
        [
            item.get('title', ''),
            item.get('category_title', ''),
            item.get('parent_title', ''),
        ]
    ).lower()
    if 'air tools' in text or 'compressor' in text or 'pneumatic' in text:
        return 'air-powered or pneumatic where relevant'
    if is_powered_text(text):
        return 'electric, battery-powered, corded, or petrol-powered where relevant'
    return ''


def workflow_root():
    return Path(settings.BASE_DIR) / 'tmp' / 'midjourney_catalog_workflow'


def state_path():
    return workflow_root() / 'state.json'


def downloads_default_dir():
    return Path.home() / 'Downloads'


def archive_dir():
    return workflow_root() / 'uploaded'


def now_iso():
    return timezone.now().isoformat()


def detect_item_kind(item):
    return 'category' if item['type'] == 'category' else 'product'


def classify_item(item):
    haystack = ' '.join(
        [
            item.get('title', ''),
            item.get('parent_title', ''),
            item.get('category_title', ''),
        ]
    ).lower()
    if any(keyword in haystack for keyword in DO_NOT_BOTHER_KEYWORDS):
        return 'use_elsewhere'
    if item['type'] == 'category':
        return 'safe' if item['title'] in SAFE_CATEGORY_TITLES else 'maybe'
    if any(keyword in haystack for keyword in LIKELY_HARD_KEYWORDS):
        return 'maybe'
    return 'safe'


def clean_name(value):
    return ' '.join((value or '').strip().split())


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


def sample_category_products(category_title, limit=3):
    category = Category.objects.filter(title=category_title).first()
    if not category:
        return []

    product_names = list(
        Product.objects.filter(category_id=category).order_by('name').values_list('name', flat=True)[:limit]
    )
    if product_names:
        return product_names

    child_categories = list(Category.objects.filter(parent_category=category).order_by('title', 'id'))
    for child in child_categories:
        for name in Product.objects.filter(category_id=child).order_by('name').values_list('name', flat=True)[:limit]:
            product_names.append(name)
            if len(product_names) >= limit:
                return product_names
    return product_names


def describe_category(title):
    examples = sample_category_products(title)
    if examples:
        powered = any(is_powered_text(example) for example in examples)
        if len(examples) == 1:
            subject = dedupe_title_prefix(title, f'{examples[0]}')
        if len(examples) == 2:
            subject = dedupe_title_prefix(title, f'{examples[0]} and {examples[1]}')
        if len(examples) >= 3:
            subject = dedupe_title_prefix(title, f'{examples[0]}, {examples[1]}, and {examples[2]}')
        if powered and subject and not subject.lower().startswith(('electric ', 'powered ')):
            return f'electric {subject}'
        return subject
    return title


def describe_product(item):
    product_title = item['title']
    lower_name = product_title.lower()
    powered = any(keyword in lower_name for keyword in POWERED_KEYWORDS)
    for keyword, hint in ITEM_VISUAL_HINTS.items():
        if keyword in lower_name:
            return f'electric {product_title.lower()}' if powered else product_title.lower()
    if powered:
        return f'electric {product_title.lower()}'
    return product_title.lower()


def build_category_prompt(item):
    title = item['title']
    background = BACKGROUND_MAP.get(title, 'simple softly blurred relevant background')
    subject = describe_category(title)
    power_hint = power_hint_for_item(item)
    power_clause = f'{power_hint}, ' if power_hint else ''
    return (
        f'{title}: {subject}. '
        f'Retail-ready product photo with {background}, {power_clause}'
        'if multiple products appear in the same image, use different appropriate colours for each product only where the item would naturally have a colour variation in real life, '
        'realistic natural wear where appropriate, '
        'if there are cable or pipe ends, do not show connectors, plugs, fittings, or couplings, '
        'natural daylight, realistic materials, soft shadows, clean composition, '
        'no people, no text, no readable product logos, keep them small and illegible, no watermark --ar 1:1 --v 7'
    )


def build_product_prompt(item):
    product_title = item['title']
    category_title = item.get('category_title') or ''
    background = BACKGROUND_MAP.get(category_title, 'simple softly blurred relevant background')
    visual_hint = describe_product(item)
    power_hint = power_hint_for_item(item)
    power_clause = f'{power_hint}, ' if power_hint else ''
    return (
        f'{product_title}: {visual_hint}. '
        f'Retail-ready product photo with {background}, {power_clause}'
        'if multiple products appear in the same image, use different appropriate colours for each product only where the item would naturally have a colour variation in real life, '
        'realistic natural wear where appropriate, '
        'if there are cable or pipe ends, do not show connectors, plugs, fittings, or couplings, '
        'natural daylight, realistic materials, soft shadows, clean composition, '
        'no people, no text, no readable product logos, keep them small and illegible, no watermark --ar 1:1 --v 7'
    )


def build_midjourney_prompt(item):
    return build_product_prompt(item) if item['type'] == 'product' else build_category_prompt(item)


def build_openai_prompt(item):
    title = item['title']
    background = BACKGROUND_MAP.get(item.get('category_title') or title, 'simple softly blurred relevant background')
    power_hint = power_hint_for_item(item)
    power_clause = f'{power_hint}, ' if power_hint else ''
    if item['type'] == 'category':
        subject = describe_category(title)
    else:
        subject = describe_product(item)
    return (
        f'UK rental catalogue retail-ready product photo of {subject}, with {background}, '
        f'{power_clause}'
        'if multiple products appear in the same image, use different appropriate colours for each product only where the item would naturally have a colour variation in real life, '
        'realistic natural wear where appropriate, '
        'if there are cable or pipe ends, do not show connectors, plugs, fittings, or couplings, '
        'natural daylight, realistic materials, soft shadows, clean composition, '
        'no people, no text, no readable product logos, keep them small and illegible, no watermark'
    )


def get_item_model(item):
    if item['type'] == 'category':
        return Category.objects.filter(id=item.get('id')).only(
            'image_review_status',
            'image_review_notes',
            'image_reviewed_at',
        ).first()
    return Product.objects.filter(id=item.get('id')).only(
        'image_review_status',
        'image_review_notes',
        'image_reviewed_at',
    ).first()


def sync_item_status_to_model(item, *, status=None, notes=None):
    obj = get_item_model(item)
    if not obj:
        return False

    changed = False
    if status is not None and getattr(obj, 'image_review_status', None) != status:
        obj.image_review_status = status
        changed = True
    if notes is not None and getattr(obj, 'image_review_notes', '') != notes:
        obj.image_review_notes = notes
        changed = True
    if changed:
        if status in {IMAGE_REVIEW_REVIEWED, IMAGE_REVIEW_SKIPPED, IMAGE_REVIEW_DONE_ELSEWHERE}:
            obj.image_reviewed_at = timezone.now()
        obj.save()
    return changed


def get_openai_image_model(name=None):
    model_name = name or DEFAULT_OPENAI_IMAGE_MODEL
    return OPENAI_IMAGE_MODELS.get(model_name, OPENAI_IMAGE_MODELS[DEFAULT_OPENAI_IMAGE_MODEL])


def _openai_debug_line(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)


def generate_openai_images(prompt, *, count=2, model=None, quality=None, debug=False, debug_log=None):
    api_key = os.environ.get('OPEN_AI_API_SECRET')
    if not api_key:
        raise CommandError('OPEN_AI_API_SECRET is not set.')
    image_model_name = model or DEFAULT_OPENAI_IMAGE_MODEL
    if image_model_name not in OPENAI_IMAGE_MODELS:
        image_model_name = DEFAULT_OPENAI_IMAGE_MODEL
    image_model = get_openai_image_model(image_model_name)
    size = OPENAI_IMAGE_SIZE
    image_quality = quality or DEFAULT_OPENAI_IMAGE_QUALITY

    payload = {
        'model': image_model['model'],
        'prompt': prompt,
        'size': size,
        'n': count,
    }
    if image_quality:
        payload['quality'] = image_quality
    if debug:
        message = _openai_debug_line(
            {
                'event': 'openai_image_request',
                'url': 'https://api.openai.com/v1/images/generations',
                'payload': payload,
            }
        )
        if debug_log:
            debug_log(message)
        else:
            print(message)

    url = 'https://api.openai.com/v1/images/generations'
    response = requests.post(
        url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=120,
    )
    if debug:
        message = _openai_debug_line(
            {
                'event': 'openai_image_response',
                'status_code': response.status_code,
                'reason': response.reason,
                'body': response.text,
            }
        )
        if debug_log:
            debug_log(message)
        else:
            print(message)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text.strip()
        payload_summary = f"model={image_model['model']}, size={size}, quality={image_quality}, n={count}"
        if detail:
            raise CommandError(
                f'OpenAI image generation failed: {response.status_code} {detail} '
                f'[{payload_summary}]'
            ) from exc
        raise CommandError(
            f'OpenAI image generation failed: {response.status_code} {response.reason} '
            f'[{payload_summary}]'
        ) from exc
    data = response.json().get('data') or []
    if not data:
        raise CommandError('OpenAI image generation returned no images.')

    out_dir = workflow_root() / 'openai_images'
    out_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    stamp = int(time.time())
    for index, item in enumerate(data, start=1):
        out_path = out_dir / f'{stamp}-{index}.png'
        if item.get('b64_json'):
            out_path.write_bytes(b64decode(item['b64_json']))
        elif item.get('url'):
            img = requests.get(item['url'], timeout=120)
            img.raise_for_status()
            out_path.write_bytes(img.content)
        else:
            continue
        saved_paths.append(out_path)
    return saved_paths


def normalize_prompt(prompt):
    prompt = (prompt or '').lstrip()
    if prompt.startswith('/'):
        return prompt[1:].lstrip()
    return prompt


def make_queue_items():
    items = []
    for category in Category.objects.exclude(slug='top').order_by('parent_category__title', 'title', 'id'):
        items.append(
            {
                'type': 'category',
                'id': category.id,
                'title': clean_name(category.title),
                'slug': category.slug,
                'parent_title': clean_name(category.parent_category.title) if category.parent_category else '',
                'category_title': clean_name(category.title),
                'status': category.image_review_status or IMAGE_REVIEW_PENDING,
                'route': classify_item(
                    {
                        'type': 'category',
                        'title': clean_name(category.title),
                        'parent_title': clean_name(category.parent_category.title) if category.parent_category else '',
                        'category_title': clean_name(category.title),
                    }
                ),
                'prompt': build_category_prompt(
                    {
                        'type': 'category',
                        'title': clean_name(category.title),
                    }
                ),
                'updated_at': now_iso(),
                'notes': category.image_review_notes or '',
            }
        )
    for product in Product.objects.select_related('category_id').order_by('category_id__title', 'name', 'id'):
        category_title = clean_name(product.category_id.title) if product.category_id else ''
        item = {
            'type': 'product',
            'id': product.id,
            'title': clean_name(product.name),
            'slug': product.slug,
            'parent_title': category_title,
            'category_title': category_title,
        }
        items.append(
            {
                **item,
                'status': product.image_review_status or IMAGE_REVIEW_PENDING,
                'route': classify_item(item),
                'prompt': build_product_prompt(item),
                'updated_at': now_iso(),
                'notes': product.image_review_notes or '',
            }
        )
    return items


def refresh_state_prompts(state):
    changed = False
    for item in state.get('items', []):
        if item.get('type') == 'category':
            category = Category.objects.filter(id=item.get('id')).first()
            if not category:
                continue
            new_prompt = build_category_prompt(
                {
                    'type': 'category',
                    'title': clean_name(category.title),
                }
            )
        else:
            product = Product.objects.select_related('category_id').filter(id=item.get('id')).first()
            if not product:
                continue
            category_title = clean_name(product.category_id.title) if product.category_id else ''
            new_prompt = build_product_prompt(
                {
                    'type': 'product',
                    'title': clean_name(product.name),
                    'category_title': category_title,
                }
            )
        if item.get('prompt') != new_prompt:
            item['prompt'] = new_prompt
            item['updated_at'] = now_iso()
            changed = True
    if changed:
        save_state(state)
    return changed


def refresh_state_statuses(state):
    changed = False
    for item in state.get('items', []):
        obj = get_item_model(item)
        if not obj:
            continue
        model_status = getattr(obj, 'image_review_status', IMAGE_REVIEW_PENDING) or IMAGE_REVIEW_PENDING
        model_notes = getattr(obj, 'image_review_notes', '') or ''
        item_status = item.get('status') or IMAGE_REVIEW_PENDING
        item_notes = item.get('notes') or ''

        if item_status != model_status:
            if model_status == IMAGE_REVIEW_PENDING and item_status != IMAGE_REVIEW_PENDING:
                sync_item_status_to_model(item, status=item_status, notes=item_notes)
                model_status = item_status
                model_notes = item_notes
            else:
                item['status'] = model_status
                changed = True

        if item_notes != model_notes:
            item['notes'] = model_notes
            changed = True

    if changed:
        save_state(state)
    return changed


def load_state():
    path = state_path()
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding='utf-8'))
    for item in state.get('items', []):
        if 'prompt' in item:
            item['prompt'] = normalize_prompt(item['prompt'])
    return state


def save_state(state):
    root = workflow_root()
    root.mkdir(parents=True, exist_ok=True)
    state['updated_at'] = now_iso()
    state_path().write_text(json.dumps(state, indent=2), encoding='utf-8')


def build_initial_state():
    items = make_queue_items()
    for item in items:
        item['prompt'] = normalize_prompt(item['prompt'])
    return {
        'version': STATE_VERSION,
        'created_at': now_iso(),
        'updated_at': now_iso(),
        'download_dir': str(downloads_default_dir()),
        'archive_dir': str(archive_dir()),
        'items': items,
    }


def item_refresh_key(item):
    return (
        item.get('type') or '',
        item.get('slug') or '',
        item.get('title') or '',
    )


def refresh_state_items(state):
    existing_items = {
        item_refresh_key(item): item
        for item in state.get('items', [])
    }
    refreshed_items = make_queue_items()
    changed = len(refreshed_items) != len(state.get('items', []))
    for item in refreshed_items:
        item['prompt'] = normalize_prompt(item['prompt'])
        previous = existing_items.get(item_refresh_key(item))
        if not previous:
            continue
        for field in ('status', 'notes', 'updated_at'):
            if previous.get(field) is not None:
                item[field] = previous.get(field)
        for field in ('route',):
            if previous.get(field):
                item[field] = previous.get(field)
    state['items'] = refreshed_items
    state['refreshed_at'] = now_iso()
    save_state(state)
    return changed or True


def ensure_state(reset=False):
    state = None if reset else load_state()
    if state is None:
        state = build_initial_state()
        save_state(state)
    refresh_state_statuses(state)
    return state


def find_next_item(state, route=None):
    allowed_routes = {route} if route else {'safe', 'maybe'}
    for item in state['items']:
        if item.get('status') != 'pending':
            continue
        if item.get('route') not in allowed_routes:
            continue
        return item
    return None


def count_by(state, field):
    counts = {}
    for item in state['items']:
        key = item.get(field) or ''
        counts[key] = counts.get(key, 0) + 1
    return counts


def print_queue_summary(stdout, state):
    status_counts = count_by(state, 'status')
    route_counts = count_by(state, 'route')
    stdout.write('Queue summary')
    stdout.write(f"  Pending: {status_counts.get('pending', 0)}")
    stdout.write(f"  Ready elsewhere: {route_counts.get('use_elsewhere', 0)}")
    stdout.write(f"  Safe: {route_counts.get('safe', 0)}")
    stdout.write(f"  Maybe: {route_counts.get('maybe', 0)}")
    stdout.write(f"  Uploaded: {status_counts.get('uploaded', 0)}")
    stdout.write(f"  Skipped: {status_counts.get('skipped', 0)}")
    stdout.write(f"  Done elsewhere: {status_counts.get('done_elsewhere', 0)}")


def item_label(item):
    kind = detect_item_kind(item)
    category_title = item.get('category_title') or ''
    if kind == 'category':
        return f"Category: {item['title']}"
    return f"Product: {item['title']} [{category_title}]"


def item_existing_image(item):
    if item['type'] == 'category':
        obj = Category.objects.filter(id=item['id']).only('image').first()
    else:
        obj = Product.objects.filter(id=item['id']).only('image').first()
    if not obj or not obj.image:
        return ''
    return obj.image.name or ''


def item_existing_image_path(item):
    if item['type'] == 'category':
        obj = Category.objects.filter(id=item['id']).only('image').first()
    else:
        obj = Product.objects.filter(id=item['id']).only('image').first()
    if not obj or not obj.image:
        return None
    try:
        path = Path(obj.image.path)
    except (ValueError, OSError):
        return None
    return path if path.exists() else None


def find_item_or_error(state, item_id):
    for item in state['items']:
        if int(item['id']) == int(item_id):
            return item
    raise CommandError(f'No queue item found for id {item_id}.')


def current_or_next_item(state, item_id=None, route=None):
    if item_id:
        return find_item_or_error(state, item_id)
    item = find_next_item(state, route=route)
    if item is None:
        raise CommandError('No pending Midjourney item found for this route.')
    return item


def print_item(stdout, item):
    stdout.write(item_label(item))
    if item.get('parent_title'):
        stdout.write(f"Parent: {item['parent_title']}")
    stdout.write(f"Route: {item['route']}")
    stdout.write(f"Status: {item['status']}")
    existing_image = item_existing_image(item)
    if existing_image:
        stdout.write(f"Existing image: {existing_image}")
    else:
        stdout.write('Existing image: none')
    if item.get('notes'):
        stdout.write(f"Notes: {item['notes']}")
    stdout.write('')
    stdout.write('Run this prompt in Midjourney:')
    stdout.write(item['prompt'])


def update_item(item, *, status=None, notes=None):
    if status:
        item['status'] = status
    if notes is not None:
        item['notes'] = notes
    item['updated_at'] = now_iso()
    sync_item_status_to_model(item, status=status, notes=notes)


def valid_image_file(path):
    if not path.is_file():
        return False
    mime_type, _encoding = mimetypes.guess_type(str(path))
    if mime_type and mime_type.startswith('image/'):
        return True
    return path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}


def newest_image_file(download_dir):
    candidates = [path for path in download_dir.iterdir() if valid_image_file(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def attach_file_to_item(item, source_path):
    if item['type'] == 'category':
        obj = Category.objects.get(id=item['id'])
        field = obj.image
        target_name = f"{slugify(obj.title)}{source_path.suffix.lower() or '.png'}"
    else:
        obj = Product.objects.get(id=item['id'])
        field = obj.image
        target_name = f"{slugify(obj.name)}{source_path.suffix.lower() or '.png'}"

    with source_path.open('rb') as handle:
        field.save(target_name, File(handle), save=True)

    return obj


def attach_image_path_to_item(item, source_path):
    attach_file_to_item(item, source_path)
    return archive_uploaded_file(item, source_path)


def archive_uploaded_file(item, source_path):
    out_dir = archive_dir() / item['type']
    out_dir.mkdir(parents=True, exist_ok=True)
    archived_name = f"{item['id']}-{slugify(item['title'])}{source_path.suffix.lower()}"
    destination = out_dir / archived_name
    shutil.move(str(source_path), destination)
    return destination


def inject_prompt_into_firefox(prompt):
    prompt = normalize_prompt(prompt)

    subprocess.run(
        ['xclip', '-selection', 'clipboard'],
        input=prompt.encode('utf-8'),
        check=True,
    )
    return prompt


def choose_generated_image(stdout, paths):
    stdout.write('')
    stdout.write('Generated OpenAI images:')
    for index, path in enumerate(paths, start=1):
        stdout.write(f'  {index}) {path}')
    stdout.write('')
    while True:
        choice = input('Choose image 1/2, r to refine, m for Midjourney prompt: ').strip().lower()
        if choice in {'1', '2', 'r', 'm'}:
            return choice


def prompt_choice(stdout):
    stdout.write('')
    stdout.write('Next step:')
    stdout.write('  1) Generate OpenAI image')
    stdout.write('  2) Skip this item')
    stdout.write('  3) Mark done elsewhere')
    stdout.write('  4) Show Midjourney prompt')
    stdout.write('  5) Quit')
    stdout.write('')
    while True:
        choice = input('Choose 1-5: ').strip().lower()
        if choice:
            return choice


class Command(BaseCommand):
    help = 'Guide and track Midjourney catalogue image creation, with optional folder watching and upload.'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            nargs='?',
            default='next',
            choices=['init', 'summary', 'next', 'watch', 'skip', 'done'],
            help='Workflow action to run.',
        )
        parser.add_argument('--reset', action='store_true', help='Rebuild the workflow queue from the live database.')
        parser.add_argument('--item-id', type=int, help='Operate on a specific queue item id.')
        parser.add_argument(
            '--route',
            choices=['safe', 'maybe'],
            help='Limit next/watch to only safe or maybe items.',
        )
        parser.add_argument(
            '--download-dir',
            default=str(downloads_default_dir()),
            help='Directory to watch for downloaded images.',
        )
        parser.add_argument(
            '--poll-seconds',
            type=int,
            default=3,
            help='Polling interval while waiting for a downloaded image.',
        )
        parser.add_argument(
            '--timeout-seconds',
            type=int,
            default=1800,
            help='How long to keep watching before giving up.',
        )
        parser.add_argument(
            '--notes',
            default='',
            help='Optional note for skip or done actions.',
        )
        parser.add_argument(
            '--fill-firefox',
            action='store_true',
            help='When printing the next item, also inject its prompt into the active Firefox tab.',
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Loop through items interactively with numbered next-step prompts.',
        )

    def handle(self, *args, **options):
        action = options['action']
        reset = bool(options.get('reset'))
        state = ensure_state(reset=reset or action == 'init')

        if action == 'init':
            self.stdout.write(self.style.SUCCESS(f'Workflow initialised at {state_path()}'))
            print_queue_summary(self.stdout, state)
            return

        if action == 'summary':
            print_queue_summary(self.stdout, state)
            return

        if options.get('interactive') or action == 'next':
            download_dir = Path(options['download_dir']).expanduser()
            download_dir.mkdir(parents=True, exist_ok=True)
            route = options.get('route')
            poll_seconds = max(1, int(options['poll_seconds']))
            timeout_seconds = max(1, int(options['timeout_seconds']))

            while True:
                item = current_or_next_item(state, item_id=options.get('item_id'), route=route)
                print_item(self.stdout, item)
                if options.get('fill_firefox'):
                    inject_prompt_into_firefox(item['prompt'])
                    self.stdout.write(self.style.SUCCESS('Copied prompt to clipboard.'))
                else:
                    subprocess.run(['xclip', '-selection', 'clipboard'], input=normalize_prompt(item['prompt']).encode('utf-8'), check=True)
                    self.stdout.write(self.style.SUCCESS('Copied prompt to clipboard.'))
                choice = prompt_choice(self.stdout)

                if choice == '1':
                    openai_prompt = build_openai_prompt(item)
                    generated_paths = generate_openai_images(openai_prompt, count=2)
                    if not generated_paths:
                        self.stdout.write(self.style.WARNING('No OpenAI images were returned.'))
                        continue
                    image_choice = choose_generated_image(self.stdout, generated_paths)
                    if image_choice == 'm':
                        self.stdout.write('')
                        self.stdout.write('Midjourney prompt:')
                        self.stdout.write(build_midjourney_prompt(item))
                        continue
                    if image_choice == 'r':
                        self.stdout.write('')
                        self.stdout.write('Refine prompt:')
                        self.stdout.write(openai_prompt)
                        refined = input('Enter a refined OpenAI prompt, or press Enter to keep: ').strip()
                        if refined:
                            generated_paths = generate_openai_images(refined, count=2)
                            if not generated_paths:
                                self.stdout.write(self.style.WARNING('No OpenAI images were returned.'))
                                continue
                            image_choice = choose_generated_image(self.stdout, generated_paths)
                            if image_choice == 'm':
                                self.stdout.write('')
                                self.stdout.write('Midjourney prompt:')
                                self.stdout.write(build_midjourney_prompt(item))
                                continue
                            if image_choice == 'r':
                                continue
                            selected_path = generated_paths[0] if image_choice == '1' else generated_paths[min(1, len(generated_paths) - 1)]
                            archived = attach_image_path_to_item(item, selected_path)
                            update_item(item, status='uploaded', notes=f'Uploaded from {archived.name}')
                            save_state(state)
                            self.stdout.write(self.style.SUCCESS(f'Uploaded image for {item_label(item)}'))
                            self.stdout.write(f'Archived original as {archived}')
                            continue
                        continue
                    selected_path = generated_paths[0] if image_choice == '1' else generated_paths[min(1, len(generated_paths) - 1)]
                    archived = attach_image_path_to_item(item, selected_path)
                    update_item(item, status='uploaded', notes=f'Uploaded from {archived.name}')
                    save_state(state)
                    self.stdout.write(self.style.SUCCESS(f'Uploaded image for {item_label(item)}'))
                    self.stdout.write(f'Archived original as {archived}')
                    continue

                if choice == '2':
                    note = options.get('notes') or 'Not doing this one in Midjourney.'
                    update_item(item, status='skipped', notes=note)
                    save_state(state)
                    self.stdout.write(self.style.WARNING(f"Skipped {item_label(item)}"))
                    continue

                if choice == '3':
                    note = options.get('notes') or 'Handled outside Midjourney.'
                    update_item(item, status='done_elsewhere', notes=note)
                    save_state(state)
                    self.stdout.write(self.style.SUCCESS(f"Marked done elsewhere: {item_label(item)}"))
                    continue

                if choice == '4':
                    self.stdout.write('')
                    self.stdout.write('Midjourney prompt:')
                    self.stdout.write(build_midjourney_prompt(item))
                    continue

                if choice == '5':
                    return

                self.stdout.write(self.style.WARNING('Please choose 1, 2, 3, 4, or 5.'))
            return

        if action == 'next':
            item = current_or_next_item(state, item_id=options.get('item_id'), route=options.get('route'))
            print_item(self.stdout, item)
            if options.get('fill_firefox'):
                inject_prompt_into_firefox(item['prompt'])
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('Injected prompt into Firefox.'))
            return

        if action == 'skip':
            item = current_or_next_item(state, item_id=options.get('item_id'), route=options.get('route'))
            note = options.get('notes') or 'Not doing this one in Midjourney.'
            update_item(item, status='skipped', notes=note)
            save_state(state)
            self.stdout.write(self.style.WARNING(f"Skipped {item_label(item)}"))
            next_item = find_next_item(state, route=options.get('route'))
            if next_item:
                self.stdout.write('')
                print_item(self.stdout, next_item)
            return

        if action == 'done':
            item = current_or_next_item(state, item_id=options.get('item_id'), route=options.get('route'))
            note = options.get('notes') or 'Handled outside Midjourney.'
            update_item(item, status='done_elsewhere', notes=note)
            save_state(state)
            self.stdout.write(self.style.SUCCESS(f"Marked done elsewhere: {item_label(item)}"))
            return

        if action == 'watch':
            item = current_or_next_item(state, item_id=options.get('item_id'), route=options.get('route'))
            download_dir = Path(options['download_dir']).expanduser()
            download_dir.mkdir(parents=True, exist_ok=True)

            self.stdout.write(f'Watching {download_dir}')
            self.stdout.write('')
            print_item(self.stdout, item)
            self.stdout.write('')
            self.stdout.write('Save the downloaded image into that folder and I will attach it automatically.')

            start = time.time()
            seen_before = {
                path.name: path.stat().st_mtime
                for path in download_dir.iterdir()
                if valid_image_file(path)
            }
            poll_seconds = max(1, int(options['poll_seconds']))
            timeout_seconds = max(1, int(options['timeout_seconds']))

            while time.time() - start < timeout_seconds:
                candidate = newest_image_file(download_dir)
                if candidate:
                    previous_mtime = seen_before.get(candidate.name)
                    current_mtime = candidate.stat().st_mtime
                    if previous_mtime is None or current_mtime > previous_mtime:
                        attach_file_to_item(item, candidate)
                        archived = archive_uploaded_file(item, candidate)
                        update_item(item, status='uploaded', notes=f'Uploaded from {archived.name}')
                        save_state(state)
                        self.stdout.write(self.style.SUCCESS(f'Uploaded image for {item_label(item)}'))
                        self.stdout.write(f'Archived original as {archived}')
                        next_item = find_next_item(state, route=options.get('route'))
                        if next_item:
                            self.stdout.write('')
                            print_item(self.stdout, next_item)
                        return
                time.sleep(poll_seconds)

            raise CommandError(f'No new image appeared in {download_dir} within {timeout_seconds} seconds.')

        raise CommandError(f'Unsupported action: {action}')
