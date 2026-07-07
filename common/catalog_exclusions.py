import json
from pathlib import Path

from django.conf import settings


def exclusions_path():
    return Path(settings.BASE_DIR) / 'tmp' / 'catalog_exclusions.json'


def load_catalog_exclusions():
    path = exclusions_path()
    if not path.exists():
        return {'categories': [], 'products': []}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {'categories': [], 'products': []}
    if not isinstance(data, dict):
        return {'categories': [], 'products': []}
    return {
        'categories': list(data.get('categories') or []),
        'products': list(data.get('products') or []),
    }


def save_catalog_exclusions(exclusions):
    path = exclusions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(exclusions, indent=2, sort_keys=True))


def exclude_category_slug(slug):
    exclusions = load_catalog_exclusions()
    if slug not in exclusions['categories']:
        exclusions['categories'].append(slug)
        save_catalog_exclusions(exclusions)


def exclude_product(category_slug, product_name):
    exclusions = load_catalog_exclusions()
    key = {'category_slug': category_slug, 'name': product_name}
    if key not in exclusions['products']:
        exclusions['products'].append(key)
        save_catalog_exclusions(exclusions)
