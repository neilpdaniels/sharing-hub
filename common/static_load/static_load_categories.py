from django.utils.text import slugify
import logging 

def initialise_top_categories():
    """Initialize top-level categories for the sharing hub."""
    from common.models import Category

    # Create 'top' root category
    top = ['top']
    for t in top:
        title_ = t
        if Category.objects.filter(slug=slugify(title_)).count() == 0:
            cat = Category()
            cat.title = title_
            cat.save()

    # Create main categories under 'top'
    categories = ['vehicles', 'gardening', 'landscaping', 'building', 'wood and metal work', 'sports and activities']
    parent = Category.objects.get(slug='top')
    for category_name in categories:
        if Category.objects.filter(slug=slugify(category_name)).count() == 0:
            cat = Category()
            cat.parent_category = parent
            cat.title = category_name
            cat.save()
