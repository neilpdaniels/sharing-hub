from django.utils.text import slugify
import logging 

def initialise_top_categories():
    """Initialize top-level categories for the rentalution."""
    from common.models import Category

    def ensure_category(title, parent=None):
        slug = slugify(title)
        category = Category.objects.filter(slug=slug).first()
        if category:
            if parent and category.parent_category_id != parent.id:
                category.parent_category = parent
                category.save(update_fields=['parent_category'])
            return category

        category = Category(title=title)
        category.parent_category = parent
        category.save()
        return category

    top = ensure_category('top')

    # Create main categories under 'top'
    categories = [
        'vehicles',
        'gardening',
        'landscaping',
        'building',
        'wood and metal work',
        'sports and activities',
        'health and wellbeing',
        'family',
    ]
    for category_name in categories:
        ensure_category(category_name, parent=top)

    health = Category.objects.filter(slug='health-and-wellbeing').first()
    if health:
        health_children = [
            'Mobility aids',
            'Daily living support',
            'Recovery and physio',
            'Wellbeing and self care',
            'Home care and accessibility',
            'Sleep and comfort',
            'Therapy and pain relief',
            'Pregnancy support',
        ]
        for subcategory_name in health_children:
            ensure_category(subcategory_name, parent=health)

        mobility = Category.objects.filter(slug='mobility-aids').first()
        if mobility:
            for subcategory_name in ['Crutches', 'Walking frames', 'Mobility scooters', 'Wheelchairs', 'Rollators']:
                ensure_category(subcategory_name, parent=mobility)

        daily_living = Category.objects.filter(slug='daily-living-support').first()
        if daily_living:
            for subcategory_name in ['Commodes', 'Bed rails', 'Shower chairs', 'Toilet aids', 'Grabbers and reachers']:
                ensure_category(subcategory_name, parent=daily_living)

        recovery = Category.objects.filter(slug='recovery-and-physio').first()
        if recovery:
            for subcategory_name in ['Massage guns', 'Foam rollers', 'Compression therapy', 'Balance and rehab', 'Stretching aids']:
                ensure_category(subcategory_name, parent=recovery)

        wellbeing = Category.objects.filter(slug='wellbeing-and-self-care').first()
        if wellbeing:
            for subcategory_name in ['LED face masks', 'Foot spas', 'Aromatherapy diffusers', 'Heat pads', 'Relaxation kits']:
                ensure_category(subcategory_name, parent=wellbeing)

        accessibility = Category.objects.filter(slug='home-care-and-accessibility').first()
        if accessibility:
            for subcategory_name in ['Bath aids', 'Raised toilet seats', 'Bed wedges', 'Overbed tables', 'Mobility ramps']:
                ensure_category(subcategory_name, parent=accessibility)

        comfort = Category.objects.filter(slug='sleep-and-comfort').first()
        if comfort:
            for subcategory_name in ['Pressure relief cushions', 'Anti-snore aids', 'Cooling blankets', 'Adjustable pillows']:
                ensure_category(subcategory_name, parent=comfort)

        therapy = Category.objects.filter(slug='therapy-and-pain-relief').first()
        if therapy:
            for subcategory_name in ['Hot/cold packs', 'TENS machines', 'Massage cushions', 'Heating pads', 'Foot massagers']:
                ensure_category(subcategory_name, parent=therapy)

        pregnancy = Category.objects.filter(slug='pregnancy-support').first()
        if pregnancy:
            ensure_category('Pregnancy and early years', parent=pregnancy)

        family = Category.objects.filter(slug='family').first()
        if family:
            ensure_category('Early years', parent=family)

        early_years = Category.objects.filter(slug='early-years').first()
        if early_years:
            for subcategory_name in [
                'Baby play aids',
                'White noise machines',
                'Baby swings and rockers',
                'Baby monitors',
                'Toddler toys and activity centres',
                'Travel cots',
                'Baby bouncers',
                'High chairs',
                'Baby carriers and slings',
                'Baby bath and changing aids',
                'Potty training aids',
                'Safety gates and stair guards',
            ]:
                ensure_category(subcategory_name, parent=early_years)
