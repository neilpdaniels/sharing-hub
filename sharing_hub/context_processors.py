from django.conf import settings

def from_settings(request):
    return {
        'ENVIRONMENT_NAME': settings.ENVIRONMENT_NAME,
        'ENVIRONMENT_COLOR': settings.ENVIRONMENT_COLOR,
    }


def top_categories(request):
    from common.models import Category
    try:
        top_cat = Category.objects.get(slug='top')
        cats = list(Category.objects.filter(parent_category=top_cat).order_by('title'))
    except Category.DoesNotExist:
        cats = []
    return {'top_categories': cats}
