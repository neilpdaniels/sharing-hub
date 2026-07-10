from django.core.files.base import ContentFile
from django.template.defaultfilters import slugify

from common.models import Product


def publish_draft(draft):
    product, _created = Product.objects.get_or_create(
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
            draft.image.name or f'{slugify(draft.title)}.png',
            ContentFile(draft.image.read()),
            save=False,
        )
    product.save()
    return product

