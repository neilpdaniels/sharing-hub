from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from common.models import Category, CategoryAttribute, Product


LEGACY_CATEGORY_MERGES = {
    'gardening': 'Garden',
    'landscaping': 'Garden',
    'vehicles': 'Vehicle and accessories',
    'sports and activities': 'Sports equipment',
    'building': 'Home improvement',
    'wood and metal work': 'DIY and power tools',
    'Carpet cleaner': 'Carpet and floor cleaning',
    'Compressors and air tools': 'Air tools and compressors',
    'Demolition and breakers': 'Masonry, concrete and demolition',
    'Masonry and concrete tools': 'Masonry, concrete and demolition',
}


def html_description(*paragraphs):
    parts = []
    for paragraph in paragraphs:
        paragraph = (paragraph or '').strip()
        if paragraph:
            parts.append(f'<p>{paragraph}</p>')
    return ''.join(parts)


def category_description(title, strapline, followup):
    return html_description(f'{title}. {strapline}', followup)


def product_item(name, description=None, attributes=None):
    return {
        'name': name,
        'description': description or f'{name}. Ready to hire.',
        'attributes': attributes or {},
    }


def make_products(names, suffix):
    return [product_item(name, f'{name}. Ready to hire.') for name in names]


def attributed_products(rows, suffix):
    products = []
    for row in rows:
        name = row[0]
        attrs = {}
        for index, value in enumerate(row[1:], start=1):
            if value:
                attrs[index] = value
        products.append(product_item(name, f'{name}. Ready to hire.', attrs))
    return products


def category_node(title, strapline, followup, *, attributes=None, products=None, children=None):
    return {
        'title': title,
        'description': category_description(title, strapline, followup),
        'attributes': attributes or [],
        'products': products or [],
        'children': children or [],
    }


def flatten_category_tree(nodes, parent_title=None):
    flattened = []
    for node in nodes:
        flattened.append(
            {
                'title': node['title'],
                'description': node['description'],
                'parent_title': parent_title,
                'attributes': node.get('attributes', []),
                'products': node.get('products', []),
            }
        )
        flattened.extend(flatten_category_tree(node.get('children', []), node['title']))
    return flattened


def attribute_defaults(attributes):
    defaults = {
        'attribute_one_name': '',
        'attribute_one_sortable': False,
        'attribute_one_filterable': False,
        'attribute_one_default_filtered_value': '',
        'attribute_two_name': '',
        'attribute_two_sortable': False,
        'attribute_two_filterable': False,
        'attribute_two_default_filtered_value': '',
        'attribute_three_name': '',
        'attribute_three_sortable': False,
        'attribute_three_filterable': False,
        'attribute_three_default_filtered_value': '',
        'attribute_four_name': '',
        'attribute_four_sortable': False,
        'attribute_four_filterable': False,
        'attribute_four_default_filtered_value': '',
        'attribute_five_name': '',
        'attribute_five_sortable': False,
        'attribute_five_filterable': False,
        'attribute_five_default_filtered_value': '',
        'default_sorted_attribute': 0,
        'default_sorted_direction_ascending': True,
    }
    suffix_map = {
        1: 'one',
        2: 'two',
        3: 'three',
        4: 'four',
        5: 'five',
    }
    first_sortable_order = 0
    for attribute in attributes:
        order = int(attribute.get('order') or 0)
        suffix = suffix_map.get(order)
        if not suffix:
            continue
        defaults[f'attribute_{suffix}_name'] = attribute.get('name', '')
        defaults[f'attribute_{suffix}_sortable'] = bool(attribute.get('sortable'))
        defaults[f'attribute_{suffix}_filterable'] = bool(attribute.get('filterable'))
        defaults[f'attribute_{suffix}_default_filtered_value'] = attribute.get('default_filtered_value', '')
        if not first_sortable_order and attribute.get('sortable'):
            first_sortable_order = order
    if first_sortable_order:
        defaults['default_sorted_attribute'] = first_sortable_order
    return defaults


def resolve_parent_category(category_data, top_category):
    parent_slug = category_data.get('parent_slug')
    parent_title = category_data.get('parent_title')

    if parent_slug == '':
        return None
    if parent_title == '':
        return None

    if parent_slug:
        return Category.objects.filter(slug=parent_slug).first()
    if parent_title:
        return Category.objects.filter(title=parent_title).first()

    return top_category


def merge_legacy_category(source_category, target_category):
    if source_category.id == target_category.id:
        return False

    Product.objects.filter(category_id=source_category).update(category_id=target_category)
    Category.objects.filter(parent_category=source_category).update(parent_category=target_category)
    source_category.delete()
    return True


def upsert_category(title, defaults):
    category = Category.objects.filter(title=title).first()
    created = False
    if category is None:
        category = Category.objects.create(title=title, **defaults)
        created = True
    else:
        for field_name, value in defaults.items():
            setattr(category, field_name, value)
        category.save()
    return category, created


def upsert_product(category, product_name, defaults):
    matching_products = list(
        Product.objects.filter(category_id=category, name=product_name).order_by('id')
    )
    if matching_products:
        product = matching_products[0]
        for duplicate in matching_products[1:]:
            duplicate.delete()
        created = False
    else:
        product = Product(category_id=category, name=product_name)
        created = True

    for field_name, value in defaults.items():
        setattr(product, field_name, value)
    product.save()
    return product, created


def delete_obsolete_products(category, desired_names):
    deleted = 0
    skipped = 0
    desired_names = set(desired_names)
    obsolete_products = Product.objects.filter(category_id=category).exclude(name__in=desired_names)
    for product in obsolete_products:
        if product.order_set.exists():
            skipped += 1
            continue
        product.delete()
        deleted += 1
    return deleted, skipped


def _descendant_categories(root_category):
    descendants = []
    frontier = [(root_category, 0)]

    while frontier:
        current, depth = frontier.pop(0)
        children = list(Category.objects.filter(parent_category=current).order_by('title', 'id'))
        for child in children:
            descendants.append((child, depth + 1))
            frontier.append((child, depth + 1))

    return descendants


def delete_obsolete_categories(top_category, desired_titles):
    deleted = 0
    skipped = 0
    desired_titles = set(desired_titles)
    descendants = _descendant_categories(top_category)
    descendants.sort(key=lambda item: item[1], reverse=True)

    for category, _depth in descendants:
        if category.slug == 'top' or category.title in desired_titles:
            continue
        if Product.objects.filter(category_id=category, order__isnull=False).exists():
            skipped += 1
            continue
        category.delete()
        deleted += 1

    return deleted, skipped


def category_payload():
    diy_children = [
        category_node(
            'Drills and drivers',
            'Hole-making, screw-driving, shelf-saving heroes.',
            'From neat pilot holes to bigger weekend ambitions.',
            products=make_products(
                [
                    'Combi drill',
                    'Hammer drill',
                    'SDS drill',
                    'Impact driver',
                    'Drill driver set',
                    'Right-angle drill',
                    'Magnetic drill',
                    'Core drill',
                    'Drywall screw gun',
                    'Collated screw gun',
                    'Cordless screwdriver',
                    'Stud and joist drill',
                ],
                'Built for proper progress without buying another tool you only need twice a year.',
            ),
        ),
        category_node(
            'Saws and cutting',
            'Straight cuts, plunge cuts, quick trims and satisfying sawdust.',
            'A tidy line starts here.',
            products=make_products(
                [
                    'Mitre saw',
                    'Sliding mitre saw',
                    'Circular saw',
                    'Track saw',
                    'Jigsaw',
                    'Reciprocating saw',
                    'Table saw',
                    'Bandsaw',
                    'Tile saw',
                    'Cut-off saw',
                    'Chainsaw mill',
                    'Oscillating multi-tool',
                    'Pole saw',
                ],
                'Ready for crisp cuts and fewer wonky surprises.',
            ),
        ),
        category_node(
            'Sanders',
            'From rough timber to paint-ready smooth.',
            'Small dust clouds, big satisfaction.',
            attributes=[
                {
                    'order': 1,
                    'name': 'Power source',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Air/compressor', 'Battery', 'Corded'],
                },
                {
                    'order': 2,
                    'name': 'Sander type',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Belt', 'Detail', 'Drywall', 'Floor', 'Orbital', 'Random orbital', 'Sheet'],
                },
                {
                    'order': 3,
                    'name': 'Duty',
                    'filterable': True,
                    'allowed_values': ['Fine finish', 'General prep', 'Heavy stock removal', 'Large area'],
                },
            ],
            products=attributed_products(
                [
                    ('Palm sander', 'Corded', 'Sheet', 'Fine finish'),
                    ('Half-sheet sander', 'Corded', 'Sheet', 'General prep'),
                    ('Random orbital sander', 'Corded', 'Random orbital', 'General prep'),
                    ('Cordless random orbital sander', 'Battery', 'Random orbital', 'General prep'),
                    ('Detail mouse sander', 'Corded', 'Detail', 'Fine finish'),
                    ('Belt sander', 'Corded', 'Belt', 'Heavy stock removal'),
                    ('File belt sander', 'Corded', 'Belt', 'Fine finish'),
                    ('Drywall pole sander', 'Corded', 'Drywall', 'Large area'),
                    ('Air orbital sander', 'Air/compressor', 'Orbital', 'Fine finish'),
                    ('Floor edging sander', 'Corded', 'Floor', 'Large area'),
                    ('Drum floor sander', 'Corded', 'Floor', 'Large area'),
                ],
                'Leaves rough edges with nowhere to hide.',
            ),
        ),
        category_node(
            'Nail guns and staplers',
            'From stud walls to skirting boards and all the trim in between.',
            'First fix, second fix and the fussy finishing bits too.',
            attributes=[
                {
                    'order': 1,
                    'name': 'Drive type',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Air/compressor', 'Battery', 'Electric', 'Gas cartridge'],
                },
                {
                    'order': 2,
                    'name': 'Fixing style',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Brad', 'Finish', 'First fix', 'Flooring', 'Pin', 'Roofing', 'Second fix', 'Staple'],
                },
            ],
            products=attributed_products(
                [
                    ('First fix framing nailer', 'Air/compressor', 'First fix'),
                    ('Gas framing nailer', 'Gas cartridge', 'First fix'),
                    ('Battery framing nailer', 'Battery', 'First fix'),
                    ('Second fix finish nailer', 'Air/compressor', 'Second fix'),
                    ('16 gauge finish nailer', 'Air/compressor', 'Finish'),
                    ('18 gauge brad nailer', 'Air/compressor', 'Brad'),
                    ('Battery brad nailer', 'Battery', 'Brad'),
                    ('23 gauge pin nailer', 'Air/compressor', 'Pin'),
                    ('Roofing nailer', 'Air/compressor', 'Roofing'),
                    ('Flooring nailer', 'Air/compressor', 'Flooring'),
                    ('Crown stapler', 'Air/compressor', 'Staple'),
                    ('Electric stapler and nailer', 'Electric', 'Staple'),
                    ('Upholstery stapler', 'Air/compressor', 'Staple'),
                ],
                'Fastens things quickly and makes hand-nailing feel gloriously optional.',
            ),
        ),
        category_node(
            'Grinders and metalwork',
            'Cutting, grinding, polishing and sparks in a mostly controlled manner.',
            'A solid friend for steel, masonry and tidy prep.',
            products=make_products(
                [
                    '4.5 inch angle grinder',
                    '9 inch angle grinder',
                    'Cordless angle grinder',
                    'Bench grinder',
                    'Die grinder',
                    'Metal chop saw',
                    'Plasma cutter',
                    'Rotary tool kit',
                    'Pipe notcher',
                    'Burnishing polisher',
                    'Bench linisher',
                ],
                'Ready for sparks, prep and a satisfyingly cleaner edge.',
            ),
        ),
        category_node(
            'Site access and support',
            'For reaching higher, holding steady and keeping things where they should be.',
            'Less wobble, more confidence.',
            products=make_products(
                [
                    'Acro props',
                    'Prop support plate set',
                    'Step ladder',
                    'Extension ladder',
                    'Platform ladder',
                    'Hop-up work platform',
                    'Trestles and staging boards',
                    'Pipe support stand',
                    'Material support rollers',
                    'Plasterboard lift',
                ],
                'Handy when gravity and awkward angles are being unhelpful.',
            ),
        ),
        category_node(
            'Measuring and layout tools',
            'For cuts that fit and holes that land where intended.',
            'Measure twice, brag quietly later.',
            products=make_products(
                [
                    'Laser level',
                    'Rotary laser level',
                    'Cross-line laser',
                    'Digital angle finder',
                    'Stud detector',
                    'Cable detector',
                    'Moisture meter',
                    'Measuring wheel',
                    'Chalk line set',
                    'Tile levelling system kit',
                    'Roofing square set',
                    'Inspection camera',
                ],
                'Helps turn “that looks about right” into something far more convincing.',
            ),
        ),
        category_node(
            'Routing and woodworking benches',
            'Joinery, shaping and the neat finishing touches.',
            'For the bits that make projects look properly thought through.',
            products=make_products(
                [
                    'Router',
                    'Plunge router',
                    'Laminate trimmer',
                    'Router table',
                    'Biscuit jointer',
                    'Planer thicknesser',
                    'Electric planer',
                    'Domino joiner',
                    'Workbench',
                    'Mitre saw stand',
                ],
                'Helps timber behave itself in public.',
            ),
        ),
        category_node(
            'Fastening and fixings tools',
            'Clamp it, rivet it, bolt it and keep everything from wandering off.',
            'A happy home for the hardware-heavy jobs.',
            products=make_products(
                [
                    'Rivnut tool',
                    'Hand riveter',
                    'Battery rivet gun',
                    'Torque wrench set',
                    'Impact socket set',
                    'Stud extractor kit',
                    'Bolt cropper',
                    'Cable tie tension tool',
                    'Nut splitter',
                    'Thread repair kit',
                    'Tap and die set',
                    'Portable vice',
                ],
                'Built for jobs where “that will probably hold” is not a serious strategy.',
            ),
        ),
        category_node(
            'Dust extraction and workshop cleanup',
            'Because the job is only half done when the dust is still winning.',
            'Cleaner benches, calmer lungs, better exits.',
            products=make_products(
                [
                    'Dust extractor',
                    'M class dust extractor',
                    'Workshop vacuum',
                    'Chip extractor',
                    'Cyclone separator',
                    'Vacuum hose kit',
                    'Bench sweep vacuum',
                    'Air filtration unit',
                    'Magnetic floor sweeper',
                    'Dust shroud for grinder',
                    'Worksite broom set',
                    'Vacuum power tool adaptor kit',
                ],
                'Useful when sawdust has started acting like a personality trait.',
            ),
        ),
        category_node(
            'Air tools and compressors',
            'Compressed-air kit for spraying, inflating and fastening with a satisfying snap.',
            'A very practical corner of noisy optimism.',
            attributes=[
                {
                    'order': 1,
                    'name': 'Power type',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Air/compressor', 'Battery', 'Corded', 'Gas cartridge'],
                },
                {
                    'order': 2,
                    'name': 'Use case',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Finish work', 'Framing', 'Inflation', 'Painting', 'Workshop'],
                },
            ],
            products=attributed_products(
                [
                    ('Direct drive air compressor', 'Corded', 'Workshop'),
                    ('Quiet workshop compressor', 'Corded', 'Workshop'),
                    ('Twin tank compressor', 'Corded', 'Workshop'),
                    ('Pancake compressor', 'Corded', 'Workshop'),
                    ('Air hose and reel kit', 'Air/compressor', 'Workshop'),
                    ('Brad nailer', 'Air/compressor', 'Finish work'),
                    ('Second fix nail gun', 'Air/compressor', 'Finish work'),
                    ('First fix framing nail gun', 'Air/compressor', 'Framing'),
                    ('Gas first fix nail gun', 'Gas cartridge', 'Framing'),
                    ('Gas second fix nail gun', 'Gas cartridge', 'Finish work'),
                    ('Crown stapler', 'Air/compressor', 'Finish work'),
                    ('Air blow gun kit', 'Air/compressor', 'Workshop'),
                    ('Air impact wrench', 'Air/compressor', 'Workshop'),
                    ('Tyre inflator gun', 'Air/compressor', 'Inflation'),
                    ('Air spray gun', 'Air/compressor', 'Painting'),
                    ('Texture spray gun', 'Air/compressor', 'Painting'),
                ],
                'For cleaner finishes, quicker fastening and a mildly professional soundtrack.',
            ),
        ),
        category_node(
            'Masonry, concrete and demolition',
            'Heavy-duty kit for drilling, breaking and persuading stubborn materials to move.',
            'This is where the loud weekend lives.',
            products=make_products(
                [
                    'Breaker',
                    'Heavy demolition hammer',
                    'Concrete grinder',
                    'Wall chaser',
                    'Diamond core drill',
                    'Masonry saw',
                    'Rebar cutter bender',
                    'Concrete mixer',
                    'Compactor plate',
                    'Floor scabbler',
                    'Needle scaler',
                    'Block splitter',
                    'Tile breaker',
                    'Dust shroud grinder kit',
                ],
                'Ideal for the serious stuff that ordinary tools would simply resent.',
            ),
        ),
        category_node(
            'Welding, soldering and heat tools',
            'Hot work, neat joins and sparks best kept intentional.',
            'A niche corner, but a very useful one.',
            products=make_products(
                [
                    'MIG welder',
                    'TIG welder',
                    'Arc welder',
                    'Plasma cutter',
                    'Soldering station',
                    'Pipe soldering torch',
                    'Hot air rework gun',
                    'Propane roofing torch',
                    'Metal cutting torch kit',
                    'Welding screen',
                    'Auto-darkening welding helmet',
                    'Magnetic welding clamp set',
                    'Welding table',
                    'Spot weld drill kit',
                    'Stud welder kit',
                    'Brazing torch set',
                ],
                'For joining, cutting and heating jobs that need a little more nerve.',
            ),
        ),
        category_node(
            'Generators and site power',
            'Portable power for the places where sockets are only a rumour.',
            'Handy for jobsites, events and determined optimism.',
            products=make_products(
                [
                    'Petrol generator',
                    'Quiet inverter generator',
                    'Towable generator',
                    'Battery power station',
                    'Site transformer',
                    '110v extension lead',
                    'Cable reel',
                    'Temporary site lighting tower',
                    'Floodlight tripod pair',
                    'Portable heater',
                    'Site fan',
                    'Distribution board',
                    'Cable protector ramp',
                    'Work light string set',
                    'Portable EV charger',
                    'Jump pack and power unit',
                ],
                'Keeps work moving when the nearest plug is feeling uncooperative.',
            ),
        ),
        category_node(
            'Workshop metalworking tools',
            'For cutting, shaping and tidying metal with a bit more precision.',
            'Small fabrication energy lives here.',
            products=make_products(
                [
                    'Bench grinder',
                    'Metal bandsaw',
                    'Chop saw for metal',
                    'Sheet metal folder',
                    'English wheel',
                    'Bead roller',
                    'Bench vice',
                    'Pillar drill',
                    'Metal lathe',
                    'Tube notcher',
                    'Tube bender',
                    'Hydraulic press',
                    'Arbor press',
                    'Sheet nibbling tool',
                    'Deburring machine',
                    'Magnetic welding square set',
                ],
                'Built for cleaner lines, tidier edges and workshop satisfaction.',
            ),
        ),
        category_node(
            'Lifting and material handling',
            'The practical kit that saves backs, time and awkward apologies.',
            'Heavy things, meet mechanical advantage.',
            products=make_products(
                [
                    'Engine crane',
                    'Chain hoist',
                    'Lever hoist',
                    'Pallet truck',
                    'Scissor lift table',
                    'Material lift',
                    'Glass lifter trolley',
                    'Panel carrier',
                    'Plasterboard lifter',
                    'Beam trolley',
                    'Genie lift',
                    'Heavy-duty dolly pair',
                    'Toe jack',
                    'Machine roller set',
                    'Suction slab lifter',
                    'Kerb stone lifter',
                ],
                'Makes awkward loads feel much less personal.',
            ),
        ),
    ]

    garden_children = [
        category_node(
            'Lawn care and aeration',
            'Grass, stripes and very satisfying before-and-after photos.',
            'For lawns that need a little encouragement.',
            products=make_products(
                [
                    'Scarifier / aerator',
                    'Plug aerator',
                    'Lawn roller',
                    'Broadcast spreader',
                    'Drop spreader',
                    'Overseeder',
                    'Cylinder mower',
                    'Ride-on mower',
                    'Pedestrian flail mower',
                    'Lawn sweeper',
                    'Leaf vacuum shredder',
                    'Turf cutter',
                ],
                'Gets the grass looking more proud of itself.',
            ),
        ),
        category_node(
            'Soil cultivation and tilling',
            'Beds, borders and veggie patches that need a proper turning over.',
            'A shortcut to crumbly, workable soil.',
            products=make_products(
                [
                    'Rotovator / tiller',
                    'Rear tine cultivator',
                    'Mini tiller',
                    'Garden cultivator',
                    'Broadfork',
                    'Power harrow',
                    'Potato planter',
                    'Garden roller cultivator',
                    'Seed drill',
                    'Compost shredder',
                ],
                'Turns compacted ground into something a lot more cooperative.',
            ),
        ),
        category_node(
            'Groundworks and compaction',
            'Paths, patios, driveways and other things that need to sit properly.',
            'A solid base beats a hopeful one every time.',
            products=make_products(
                [
                    'Plate wacker',
                    'Forward plate compactor',
                    'Reversible plate compactor',
                    'Trench rammer',
                    'Vibrating roller',
                    'Paver block splitter',
                    'Floor saw',
                    'Petrol cut-off saw',
                    'Line marker',
                    'Submersible site pump',
                ],
                'Helps heavy jobs feel a little less heroic.',
            ),
        ),
        category_node(
            'Tree and hedge care',
            'Branches in, tidy shapes out.',
            'For hedges that got ideas above their station.',
            products=make_products(
                [
                    'Hedge trimmer',
                    'Long-reach hedge trimmer',
                    'Pole pruner',
                    'Chainsaw',
                    'Top-handle chainsaw',
                    'Chainsaw sharpening kit',
                    'Wood chipper',
                    'Stump grinder',
                    'Brush cutter',
                    'Strimmer',
                    'Leaf blower',
                    'Leaf blower vacuum',
                ],
                'Keeps greenery under control without too much muttering.',
            ),
        ),
        category_node(
            'Log splitting and firewood',
            'Cold weather prep, but with fewer sore shoulders.',
            'Chunky timber made a bit more civilised.',
            products=make_products(
                [
                    'Log splitter',
                    'Horizontal log splitter',
                    'Vertical log splitter',
                    'Firewood processor',
                    'Kindling splitter',
                    'Log saw horse',
                    'Timber trolley',
                    'Moisture meter for logs',
                ],
                'Turns serious logs into fireside-friendly pieces.',
            ),
        ),
        category_node(
            'Digging and site clearance',
            'When a spade is technically possible but not especially appealing.',
            'Good for holes, trenches and moving the awkward stuff.',
            products=make_products(
                [
                    'Mini digger',
                    'Micro digger',
                    'Trencher',
                    'Powered wheelbarrow',
                    'Tracked dumper',
                    'Post hole borer',
                    'Earth auger',
                    'Skid steer loader',
                    'Weed burner',
                    'Garden shredder',
                ],
                'Helps big garden plans happen with fewer regrets.',
            ),
        ),
        category_node(
            'Watering and washdown',
            'For muddy kit, thirsty plants and patio rescue missions.',
            'A little pressure goes a long way.',
            products=make_products(
                [
                    'Pressure washer',
                    'Hot water pressure washer',
                    'Patio cleaner attachment',
                    'Water butt pump',
                    'Irrigation hose kit',
                    'Sprinkler set',
                    'Water bowser trailer',
                    'Fogger mister',
                    'Gutter vacuum',
                    'Window cleaning pole kit',
                ],
                'Useful when dirt and dry spells are both getting a bit cheeky.',
            ),
        ),
        category_node(
            'Fencing and postwork',
            'Straight posts, tidy lines and fewer wonky panels.',
            'Fence day, but less dramatic.',
            products=make_products(
                [
                    'Post rammer',
                    'Hydraulic post driver',
                    'Fence wire tensioner',
                    'Fence stapler',
                    'Post puller',
                    'Panel carrier clamps',
                    'Gate hanging kit',
                    'String line kit',
                ],
                'Makes boundary work feel much more under control.',
            ),
        ),
        category_node(
            'Pruning and orchard tools',
            'Fruit trees, long branches and the bits that need a cleaner cut.',
            'A calmer route to controlled growth.',
            products=make_products(
                [
                    'Bypass lopper',
                    'Anvil lopper',
                    'Telescopic pruner',
                    'Orchard ladder',
                    'Fruit picker',
                    'Pruning saw',
                    'Grafting kit',
                    'Pole hedge saw',
                    'Tree tie tensioner',
                    'Orchard sprayer',
                ],
                'Helps trees behave a little more politely.',
            ),
        ),
        category_node(
            'Greenhouse and propagation',
            'Seedlings, trays and tiny plants with big expectations.',
            'For growers who like getting a head start.',
            products=make_products(
                [
                    'Heated propagator',
                    'Greenhouse shelving',
                    'Potting bench',
                    'Seed tray kit',
                    'Grow light stand',
                    'Mini greenhouse',
                    'Compost sieve',
                    'Watering lance set',
                    'Capillary matting roll',
                    'Greenhouse heater',
                ],
                'Gives little plants a much better first impression.',
            ),
        ),
        category_node(
            'Pest control and spraying',
            'For weeds, moss and garden invaders that have overstayed their welcome.',
            'A tidy, targeted answer to outdoor nuisance.',
            products=make_products(
                [
                    'Backpack sprayer',
                    'Tow-behind sprayer',
                    'Spot weed sprayer',
                    'Moss treatment spreader',
                    'Slug barrier kit',
                    'Netting support hoops',
                    'Fruit cage frame',
                    'Bird scarer kite',
                    'Ultrasonic pest deterrent',
                    'Wasp trap station',
                    'Rat bait station box',
                    'Weed burner wand',
                    'Long-reach spray lance',
                    'Granule applicator',
                ],
                'Useful when the garden has welcomed a few too many guests.',
            ),
        ),
        category_node(
            'Estate maintenance and paddock care',
            'For larger plots, rougher ground and outdoor spaces with proper acreage energy.',
            'A step up from everyday garden jobs.',
            products=make_products(
                [
                    'ATV trailer',
                    'ATV flail mower',
                    'Chain harrow',
                    'Paddock roller',
                    'Field topper mower',
                    'Post and rail driver',
                    'Electric fence tester',
                    'Water trough bowser',
                    'Seed broadcaster for paddocks',
                    'Heavy-duty wheelbarrow',
                    'Stock fencing unroller',
                    'Brash drag mat',
                    'Ride-on weed wiper',
                    'Field gate lifter',
                ],
                'Handy for land that politely refuses to count as a normal garden.',
            ),
        ),
        category_node(
            'Composting and waste handling',
            'For clippings, leaves and the inevitable mountain of garden leftovers.',
            'The tidier end of outdoor ambition.',
            products=make_products(
                [
                    'Garden incinerator',
                    'Compost tumbler',
                    'Wheelie bin mover',
                    'Leaf collection tarp',
                    'Green waste sack stand',
                    'Branch bundling frame',
                    'Chip collection bag set',
                    'Compost thermometer',
                    'Wood ash vacuum',
                    'Garden cart tipper',
                    'Bagging chute kit',
                    'Debris grabber tool',
                ],
                'Helps the aftermath feel a bit more manageable.',
            ),
        ),
    ]

    sports_children = [
        category_node(
            'Ball sports',
            'Kick, pass, shoot and try not to lose the cones.',
            'Training kit and matchday helpers in one tidy corner.',
            products=make_products(
                [
                    'Football goals',
                    'Pop-up football goals',
                    'Rebound board',
                    'Ball launcher',
                    'Cricket bowling machine',
                    'Cricket net',
                    'Rugby tackle bag',
                    'Netball post set',
                    'Basketball hoop',
                    'Portable basketball stand',
                    'American football sled',
                    'Volleyball net set',
                    'Handball goal',
                ],
                'Brings the training session with it.',
            ),
        ),
        category_node(
            'Racquet sports',
            'Courts, serves and the occasional glorious excuse for new grips.',
            'Good for practice without the full pro-shop commitment.',
            products=make_products(
                [
                    'Tennis machine',
                    'Ball hopper',
                    'Portable tennis net',
                    'Padel net set',
                    'Badminton net',
                    'Stringing machine',
                    'Racquet tuning machine',
                    'Target training screens',
                    'Table tennis table',
                    'Ball collection tube',
                ],
                'Handy for extra reps and fewer excuses.',
            ),
        ),
        category_node(
            'Watersports',
            'Paddles up, dry bags packed, weather checked at least once.',
            'For peaceful drifting or slightly soggy heroics.',
            products=make_products(
                [
                    'Kayak',
                    'Touring kayak',
                    'Sit-on-top kayak',
                    'Canoe',
                    'Paddleboard',
                    'Inflatable paddleboard',
                    'Bodyboard',
                    'Towable tube',
                    'Dry bag set',
                    'Life jacket set',
                    'Roof bar kayak carrier',
                    'Paddleboard electric pump',
                ],
                'Ready for the water without needing your own shed full of kit.',
            ),
        ),
        category_node(
            'Camping and hiking gear',
            'Sleep outside, but do it with decent kit and a functioning zip.',
            'Borrow the adventure, not the long-term storage problem.',
            products=make_products(
                [
                    'Camping kit',
                    'Family tent',
                    'Bell tent',
                    'Lightweight backpacking tent',
                    'Double sleeping bag',
                    'Camping stove',
                    'Cool box',
                    'Rucksack carrier',
                    'Hiking poles',
                    'Headtorch pack',
                    'Portable toilet',
                    'Camp kitchen stand',
                    'Roof tent',
                ],
                'Keeps outdoor plans feeling more exciting than exhausting.',
            ),
        ),
        category_node(
            'Fitness and training',
            'Garage gym dreams without the permanent floor sacrifice.',
            'Train hard, return tidy.',
            products=make_products(
                [
                    'Spin bike',
                    'Rowing machine',
                    'Treadmill',
                    'Adjustable bench',
                    'Barbell set',
                    'Kettlebell set',
                    'Battle ropes',
                    'Ski erg',
                    'Plyo box set',
                    'Punch bag stand',
                    'Resistance sled',
                    'Agility ladder set',
                    'Recovery massage gun',
                ],
                'Brings the workout without filling a spare room forever.',
            ),
        ),
        category_node(
            'Winter sports',
            'Cold air, decent kit and fewer expensive impulse purchases.',
            'For slopes, sledges and chilly ambition.',
            products=make_products(
                [
                    'Adult skis',
                    'Kids skis',
                    'Snowboard',
                    'Ski boot bag',
                    'Avalanche safety pack',
                    'Snowshoe set',
                    'Sledge',
                    'Toboggan',
                    'Heated glove pack',
                    'Ski tuning bench',
                ],
                'Useful when the forecast finally behaves itself.',
            ),
        ),
        category_node(
            'Cycling and bike gear',
            'Pedals, pumps and all the practical extras around the ride itself.',
            'Good for commuting, weekends and muddy optimism.',
            products=make_products(
                [
                    'Road bike',
                    'Mountain bike',
                    'Kids bike',
                    'Bike repair stand',
                    'Turbo trainer',
                    'Bikepacking bag set',
                    'Wheel truing stand',
                    'Hydration pack',
                    'Track pump',
                    'Helmet and lights bundle',
                    'Electric bike rack stand',
                    'Bike wash stand',
                ],
                'Keeps the cycling plans rolling nicely.',
            ),
        ),
        category_node(
            'Recovery and physio gear',
            'The slightly less glamorous kit that keeps people moving happily.',
            'Stretchy, squishy and surprisingly welcome.',
            products=make_products(
                [
                    'Foam roller set',
                    'Compression boots',
                    'Massage table',
                    'Ice bath tub',
                    'Recovery massage gun',
                    'Cupping therapy kit',
                    'Stretch strap set',
                    'Balance board',
                    'Wobble cushion',
                    'Shoulder pulley rehab kit',
                ],
                'Useful when the body would appreciate a better apology.',
            ),
        ),
        category_node(
            'Matchday and coaching equipment',
            'For drills, fixtures and the organised side of competitive chaos.',
            'Coaches and captains tend to love this corner.',
            products=make_products(
                [
                    'Tactics whiteboard',
                    'Substitution board',
                    'Timing gate set',
                    'Sprint parachute set',
                    'Coaching cone mega pack',
                    'Hurdle training set',
                    'Corner flags',
                    'Scoreboard stand',
                    'Whistle and card set',
                    'Team shelter bench',
                    'Ball pump station',
                    'Kit hamper trolley',
                ],
                'Helps practices run smoother and matchdays look a bit more official.',
            ),
        ),
        category_node(
            'Climbing and adventure training',
            'Harnesses, grips and training kit for the more vertical hobbies.',
            'Equal parts effort and fun.',
            products=make_products(
                [
                    'Bouldering mat',
                    'Climbing hangboard',
                    'Grip training block set',
                    'Climbing rope bag',
                    'Helmet and harness bundle',
                    'Slackline trainer kit',
                    'Cargo net climb frame',
                    'Assault course wall module',
                    'Rope climb anchor kit',
                    'Adventure race checkpoint flags',
                    'Outdoor belay glove pack',
                    'Monkey bar trainer rig',
                ],
                'Useful when training plans involve a little more height and grit.',
            ),
        ),
    ]

    vehicle_children = [
        category_node(
            'Roof storage and roof racks',
            'Because the boot was optimistic at best.',
            'Extra space, same driveway footprint.',
            products=make_products(
                [
                    'Roof box',
                    'Slim roof box',
                    'Large family roof box',
                    'Roof bars',
                    'Locking roof rack system',
                    'Ski roof carrier',
                    'Surfboard roof carrier',
                    'Ladder roof rack',
                    'Roof basket',
                    'Roof bag',
                    'Awning side carrier',
                    'Kayak roof cradle',
                ],
                'Creates luggage space with suspicious ease.',
            ),
        ),
        category_node(
            'Bike transport',
            'Take the bikes, keep the cabin civilised.',
            'From one quick ride to a full family day out.',
            products=make_products(
                [
                    'Single bike rack',
                    'Two bike rack',
                    'Three bike rack',
                    'Tow bar bike rack',
                    'Hitch platform rack',
                    'Roof bike carrier',
                    'Van fork mount',
                    'E-bike rack',
                    'Boot-mounted bike rack',
                    'Bike repair stand',
                ],
                'Keeps wheels rolling and seat space free.',
            ),
        ),
        category_node(
            'Trailers and towing',
            'For loads that absolutely were not fitting “if we pack carefully”.',
            'Small towing help with very big energy.',
            products=make_products(
                [
                    'General purpose trailer',
                    'Caged trailer',
                    'Tipping trailer',
                    'Motorbike trailer',
                    'Car transporter trailer',
                    'Plant trailer',
                    'Box trailer',
                    'Trailer board and light kit',
                    'Trailer lock kit',
                    'Tow dolly',
                    'Tow bar carrier',
                    'Recovery strop kit',
                ],
                'Useful when wishful thinking has officially left the chat.',
            ),
        ),
        category_node(
            'Car maintenance and tools',
            'The useful car-care kit for breakdowns, flat batteries and keeping things moving.',
            'A sensible place for the bits you actually borrow from time to time.',
            products=make_products(
                [
                    'Jump leads',
                    'Jump starter pack',
                    'Battery charger',
                    'Battery tester',
                    'Tyre inflator',
                    'Oil drain pan',
                    'Brake caliper piston rewind tool',
                    'Brake fluid bleeder kit',
                    'Brake cleaner spray kit',
                    'Socket set',
                    'Oil filter wrench',
                    'Trim removal tool set',
                    'Valve core tool',
                    'Wheel ramp pair',
                    'Axle stands',
                    'Hydraulic trolley jack',
                    'Mechanics creeper',
                    'OBD diagnostic reader',
                    'Wheel brace kit',
                    'Torque wrench for wheels',
                    'Tyre pressure kit',
                    'Puncture repair kit',
                    'Portable work light',
                ],
                'Handy for roadside rescue, driveway jobs and the odd “please start” moment.',
            ),
        ),
        category_node(
            'Van and load management',
            'The bits that stop vans becoming loud, rolling puzzles.',
            'Secure loads, calmer journeys.',
            products=make_products(
                [
                    'Van roof rack',
                    'Van shelf module',
                    'Load restraint poles',
                    'Parcel cage',
                    'Van bulkhead protector',
                    'Van lining panel set',
                    'Tool vault box',
                    'Roof ladder roller',
                    'Pipe tube carrier',
                    'Load securing track kit',
                    'Beacon light bar',
                    'Tow hitch step',
                ],
                'Useful when a van needs to work a bit harder.',
            ),
        ),
        category_node(
            'Winter and touring accessories',
            'Seasonal bits for road trips, cold mornings and longer adventures.',
            'The cheerful side of being prepared.',
            products=make_products(
                [
                    'Snow chains',
                    'Snow socks',
                    'Roof tent ladder extension',
                    'Portable awning room',
                    'Vehicle levelling ramps',
                    'Tow bar storage box',
                    '12v heated blanket',
                    'Portable diesel heater',
                    'Wheel snow shovel kit',
                    'Portable toilet for camper use',
                    'Drive-away awning',
                    'Camping power hook-up lead',
                ],
                'Useful when the vehicle is part transport, part mini expedition.',
            ),
        ),
        category_node(
            'Cleaning and detailing gear',
            'For the satisfying side of vehicle care and handover-ready shine.',
            'Buckets, brushes and a bit of pride.',
            products=make_products(
                [
                    'Snow foam lance',
                    'Pressure washer detailing kit',
                    'Vacuum and blower duo',
                    'Carpet extractor for vehicles',
                    'Polisher',
                    'Paint depth gauge',
                    'Wheel stand cleaning rack',
                    'Drying blower',
                    'Interior detailing brush set',
                    'Seat shampoo machine',
                    'Waterless wash kit',
                    'Canopy wash stand',
                ],
                'Handy when the car deserves better than a hurried sponge.',
            ),
        ),
    ]

    event_children = [
        category_node(
            'Marquees and shelters',
            'Weather insurance with poles, fabric and a decent entrance.',
            'For garden parties, weddings and hopeful British optimism.',
            products=make_products(
                [
                    'Marquee',
                    'Pop-up gazebo',
                    'Clearspan marquee',
                    'Stretch tent',
                    'Pagoda tent',
                    'Market stall gazebo',
                    'Walkway canopy',
                    'Sidewall set',
                    'Marquee heater',
                    'Event flooring',
                    'Entrance matting',
                ],
                'Keeps guests dry and plans on speaking terms.',
            ),
        ),
        category_node(
            'Catering equipment',
            'Feed the crowd without buying a warehouse of kit.',
            'Hot, cold, carved or poured.',
            products=make_products(
                [
                    'Hog roast',
                    'Spit roast machine',
                    'Hot holding cabinet',
                    'Chafing dish set',
                    'Soup kettle',
                    'Popcorn machine',
                    'Candy floss machine',
                    'Crepe maker',
                    'Coffee urn',
                    'Portable bar fridge',
                    'Glasswasher',
                    'Cutlery and crockery pack',
                ],
                'Ready to help you feed people and collect compliments.',
            ),
        ),
        category_node(
            'Event lighting and decor',
            'The bit that makes “a gathering” look like “an occasion”.',
            'Mood, sparkle and the flattering end of lighting.',
            products=make_products(
                [
                    'Bistro lighting',
                    'Festoon lighting',
                    'Uplighters',
                    'LED dance floor',
                    'Backdrop frame',
                    'Flower arch frame',
                    'Mirror ball kit',
                    'Neon sign stand',
                    'Red carpet runner',
                    'Lantern bundle',
                    'Table centrepiece set',
                ],
                'Adds atmosphere without a week of storing decorations afterwards.',
            ),
        ),
        category_node(
            'Audio, music and AV',
            'Make the speeches audible and the playlists properly unapologetic.',
            'Sound, screens and a touch of showmanship.',
            products=make_products(
                [
                    'PA system',
                    'Portable speaker pair',
                    'Subwoofer package',
                    'Wedding speech microphone set',
                    'DJ controller',
                    'Lighting bar',
                    'Projector and screen',
                    'Stage monitor pair',
                    'Mixer desk',
                    'Karaoke machine',
                    'Photo booth shell',
                    'Outdoor cinema pack',
                ],
                'Makes the quiet bits clearer and the loud bits a lot more fun.',
            ),
        ),
        category_node(
            'Stages and crowd control',
            'The practical event backbone that quietly stops everything feeling improvised.',
            'Useful for queues, speeches and large groups with opinions.',
            products=make_products(
                [
                    'Portable stage deck',
                    'Low riser stage',
                    'Stage steps',
                    'Stage skirt kit',
                    'Lectern',
                    'Queue barrier set',
                    'Rope and post barrier set',
                    'Crowd control fencing',
                    'Pedestrian barrier',
                    'Cable ramp set',
                    'Backstage screen divider',
                    'Wayfinding sign stand pack',
                ],
                'Keeps events safer, neater and a lot more official-looking.',
            ),
        ),
        category_node(
            'Toilet and welfare hire',
            'The practical event bits nobody posts about but everybody absolutely needs.',
            'Quietly essential, deeply appreciated.',
            products=make_products(
                [
                    'Portable toilet',
                    'Luxury toilet trailer',
                    'Accessible toilet unit',
                    'Baby changing station',
                    'Hand wash stand',
                    'Water bowser',
                    'Waste tank',
                    'Site cabin heater',
                    'Welfare cabin',
                    'Generator for welfare unit',
                    'Smoking shelter',
                    'Queue sign pack',
                ],
                'Keeps guests comfortable and event planners noticeably calmer.',
            ),
        ),
    ]

    costume_children = [
        category_node(
            'Adult fancy dress',
            'Party-ready looks for grown-ups with excellent or terrible ideas.',
            'Big entrances welcomed.',
            attributes=[
                {
                    'order': 1,
                    'name': 'Theme',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Animals', 'Fantasy', 'Halloween', 'History', 'Superhero', 'Uniform'],
                    'value_source': 'product',
                },
                {
                    'order': 2,
                    'name': 'Listing size',
                    'filterable': False,
                    'sortable': False,
                    'allowed_values': ['Adult XS', 'Adult S', 'Adult M', 'Adult L', 'Adult XL', 'One size'],
                    'value_source': 'listing',
                },
            ],
            products=attributed_products(
                [
                    ('Superhero bodysuit', 'Superhero'),
                    ('Superhero cape set', 'Superhero'),
                    ('Roman gladiator costume', 'History'),
                    ('Medieval knight costume', 'History'),
                    ('Viking costume', 'History'),
                    ('Pirate captain costume', 'Fantasy'),
                    ('Wizard robe set', 'Fantasy'),
                    ('Witch costume', 'Halloween'),
                    ('Zombie costume', 'Halloween'),
                    ('Skeleton morph suit', 'Halloween'),
                    ('Inflatable dinosaur suit', 'Animals'),
                    ('Banana costume', 'Animals'),
                    ('Cow costume', 'Animals'),
                    ('Pilot costume', 'Uniform'),
                    ('Police costume', 'Uniform'),
                    ('Firefighter costume', 'Uniform'),
                    ('Chef costume', 'Uniform'),
                    ('1920s flapper costume', 'History'),
                    ('Disco jumpsuit', 'Fantasy'),
                    ('Grease-style leather look costume', 'Fantasy'),
                ],
                'Built for parties, laughs and at least one unexpectedly good photo.',
            ),
        ),
        category_node(
            'Kids fancy dress',
            'Tiny capes, big commitment and excellent photo potential.',
            'For birthdays, school events and heroic living room adventures.',
            attributes=[
                {
                    'order': 1,
                    'name': 'Theme',
                    'filterable': True,
                    'sortable': True,
                    'allowed_values': ['Animals', 'Fantasy', 'Halloween', 'History', 'Superhero', 'Uniform'],
                    'value_source': 'product',
                },
                {
                    'order': 2,
                    'name': 'Listing size',
                    'filterable': False,
                    'sortable': False,
                    'allowed_values': ['Age 2-3', 'Age 3-4', 'Age 5-6', 'Age 7-8', 'Age 9-10', 'Age 11-12'],
                    'value_source': 'listing',
                },
            ],
            products=attributed_products(
                [
                    ('Mini superhero cape set', 'Superhero'),
                    ('Superhero jumpsuit', 'Superhero'),
                    ('Princess gown', 'Fantasy'),
                    ('Dragon costume', 'Fantasy'),
                    ('Knight costume', 'History'),
                    ('Pharaoh costume', 'History'),
                    ('Astronaut costume', 'Uniform'),
                    ('Doctor costume', 'Uniform'),
                    ('Police costume', 'Uniform'),
                    ('Lion costume', 'Animals'),
                    ('Shark costume', 'Animals'),
                    ('Unicorn costume', 'Fantasy'),
                    ('Pumpkin costume', 'Halloween'),
                    ('Little witch costume', 'Halloween'),
                    ('Little vampire costume', 'Halloween'),
                    ('Skeleton costume', 'Halloween'),
                    ('Robin Hood costume', 'History'),
                    ('Fairy costume', 'Fantasy'),
                    ('Pirate costume', 'Fantasy'),
                    ('Dinosaur costume', 'Animals'),
                ],
                'Designed for maximum imagination and minimum wardrobe commitment.',
            ),
        ),
        category_node(
            'Mascots and character suits',
            'Larger-than-life costumes for clubs, schools and gloriously silly entrances.',
            'High impact, occasionally warm, always memorable.',
            products=make_products(
                [
                    'Mascot suit',
                    'Bear mascot suit',
                    'Lion mascot suit',
                    'Panda mascot suit',
                    'Dinosaur mascot suit',
                    'Chicken mascot suit',
                    'Rabbit mascot suit',
                    'Dog mascot suit',
                    'Character head and paws set',
                    'Inflatable mascot blower costume',
                    'Sports team mascot outfit',
                    'Walkabout parade costume',
                ],
                'Made to charm crowds and test your step count.',
            ),
        ),
        category_node(
            'Themed group costumes',
            'For coordinated entrances, office teams and friendship groups who really commit.',
            'Better together, usually louder too.',
            products=make_products(
                [
                    'ABBA tribute group costume set',
                    'Superhero squad costume set',
                    'Prisoner and police costume set',
                    'Safari explorer group costume set',
                    'Construction crew costume set',
                    'Circus troupe costume set',
                    'Wizard school costume set',
                    'Zombie school group costume set',
                    'Greek gods costume set',
                    'Festival glitter gang costume set',
                    'Toy soldiers costume set',
                    'Wild west posse costume set',
                ],
                'Perfect when one costume simply is not enough teamwork.',
            ),
        ),
    ]

    carpet_children = [
        category_node(
            'Upright carpet cleaners',
            'For whole-room refreshes and the smug feeling afterwards.',
            'Good when the carpet has seen things.',
            products=make_products(
                [
                    'Upright carpet cleaner',
                    'Wide-head carpet cleaner',
                    'Pet stain carpet cleaner',
                    'Dual-tank carpet washer',
                    'Heated carpet extractor',
                    'Commercial carpet cleaner',
                    'Carpet brush agitator',
                ],
                'Brings the fibres back to life and the room back to decency.',
            ),
        ),
        category_node(
            'Spot and upholstery cleaners',
            'Quick rescue missions for sofas, stairs and suspicious patches.',
            'Small machine, big redemption arc.',
            products=make_products(
                [
                    'Spot cleaner',
                    'Upholstery extractor',
                    'Handheld stain remover',
                    'Mattress cleaner',
                    'Car seat upholstery cleaner',
                    'Pet spot washer',
                    'Stair tool kit',
                    'Fabric drying fan',
                ],
                'Perfect for local disasters and tidy recoveries.',
            ),
        ),
        category_node(
            'Hard floor and extractor cleaners',
            'Because the spill ignored the carpet entirely.',
            'Useful for tile, vinyl and the murkier corners of life.',
            products=make_products(
                [
                    'Hard floor scrubber',
                    'Tile and grout cleaner',
                    'Spray extraction cleaner',
                    'Wet and dry vacuum',
                    'Commercial floor dryer',
                    'Steam mop and scrubber',
                    'Rotary floor polisher',
                ],
                'Helps hard floors stop looking quite so hard done by.',
            ),
        ),
        category_node(
            'Drying, deodorising and restoration',
            'The backup crew for floods, deep cleans and things that need properly sorting.',
            'Less glamorous, deeply useful.',
            products=make_products(
                [
                    'Air mover fan',
                    'Commercial dehumidifier',
                    'Odour neutraliser fogger',
                    'Turbo dryer',
                    'Moisture meter',
                    'Water extraction vacuum',
                    'Floor drying mat system',
                    'Ozone treatment machine',
                    'Fabric deodorising sprayer',
                    'Restoration blower heater',
                ],
                'For the jobs that need more than a quick once-over and crossed fingers.',
            ),
        ),
    ]

    moving_children = [
        category_node(
            'Boxes, crates and totes',
            'Pack it, stack it, label it and hope future-you is grateful.',
            'Moving day starts with containers that behave.',
            products=make_products(
                [
                    'Packing crates',
                    'Heavy-duty moving boxes',
                    'Wardrobe box',
                    'Archive box bundle',
                    'Lidded tote boxes',
                    'Reusable moving crates',
                    'Bottle divider boxes',
                    'Book boxes',
                    'Small parts organiser bins',
                    'Label pack and marker kit',
                ],
                'Keeps belongings together and stress just slightly lower.',
            ),
        ),
        category_node(
            'Dollies, skates and lifters',
            'For shifting the impossible-looking stuff without medieval techniques.',
            'Bulky things, meet wheels.',
            products=make_products(
                [
                    'Furniture dolly',
                    'Appliance trolley',
                    'Sack truck',
                    'Piano dolly',
                    'Machine skate set',
                    'Glass suction lifter',
                    'Panel lifter',
                    'Door lifter',
                    'Shoulder moving straps',
                    'Hydraulic table trolley',
                ],
                'Turns grim lifting into something a bit more sensible.',
            ),
        ),
        category_node(
            'Wrapping, covers and protection',
            'Because chips and scratches are a terrible moving souvenir.',
            'Soft layers, calmer hearts.',
            products=make_products(
                [
                    'Removal blankets',
                    'Bubble wrap bundle',
                    'Mattress bag',
                    'Sofa cover',
                    'TV moving cover',
                    'Floor protection roll',
                    'Door frame protector set',
                    'Corner foam pack',
                    'Mirror box kit',
                    'Shrink wrap dispenser',
                ],
                'Keeps furniture a little more dignified in transit.',
            ),
        ),
        category_node(
            'Ratchets, ropes and securing',
            'Tie it down once, trust it for the journey.',
            'Helpful when loads have their own ideas.',
            products=make_products(
                [
                    'Ratchet straps',
                    'Cargo net',
                    'Cam buckle strap set',
                    'Bungee cord pack',
                    'Rope bundle',
                    'Load bar',
                    'Corner protectors',
                    'Moving van lock bar',
                    'Wheel chock set',
                    'Lashing ring kit',
                ],
                'Stops cargo from developing an independent spirit.',
            ),
        ),
        category_node(
            'Temporary storage and organisation',
            'For overflow, staging areas and “we just need this sorted for a month”.',
            'Short-term order with long-term mental health benefits.',
            products=make_products(
                [
                    'Racking bay starter kit',
                    'Wire shelving unit',
                    'Hanging garment rail',
                    'Stackable archive crate set',
                    'Parts bin wall rack',
                    'Folding storage cage',
                    'Padlockable site box',
                    'Clear tote set',
                    'Under-stair organiser pack',
                    'Inventory label printer stand',
                ],
                'Handy when clutter needs a temporary boss.',
            ),
        ),
        category_node(
            'Appliance moving and install helpers',
            'The bits that make white goods and big furniture less terrifying to move.',
            'Not glamorous, extremely welcome.',
            products=make_products(
                [
                    'Fridge freezer trolley',
                    'Washing machine transit bolts kit',
                    'Appliance roller bars',
                    'Heavy-duty lifting straps',
                    'Levelling wedge pack',
                    'Worktop joining jig',
                    'Plumbing catch tray',
                    'Door removal trolley',
                    'Appliance slider pads',
                    'Worktop support stand pair',
                ],
                'Useful for shifting large household optimism into place.',
            ),
        ),
        category_node(
            'Event and exhibition transport gear',
            'For moving branded stands, stock and awkward display kit in a more civilised way.',
            'Temporary logistics with useful wheels.',
            products=make_products(
                [
                    'Exhibition case trolley',
                    'Fold-flat platform trolley',
                    'Roll cage',
                    'Merchandise rail transporter',
                    'Poster tube carrier',
                    'Pipe and drape road case',
                    'Tool chest on wheels',
                    'Loading ramp pair',
                    'Cable trunk case',
                    'Stackable flight case set',
                    'Trade stand crate pack',
                    'Padded monitor transport case',
                ],
                'Great when an event comes with more gear than dignity.',
            ),
        ),
        category_node(
            'Cleaning and handover kit',
            'For the last sweep, wipe-down and “please let the deposit come back” stage.',
            'Small helpers with big emotional upside.',
            products=make_products(
                [
                    'End-of-tenancy cleaning kit',
                    'Microfibre trolley bundle',
                    'Window blade set',
                    'Skirting board mop',
                    'Hard floor pad set',
                    'Touch-up filler kit',
                    'Label remover and scraper',
                    'Adhesive residue wheel',
                    'Waste sack trolley',
                    'Dustpan contractor set',
                    'Odour absorber bucket',
                    'Final snag checklist board',
                ],
                'Useful when the finish line is mostly cleaning supplies and determination.',
            ),
        ),
    ]

    outdoor_children = [
        category_node(
            'Gazebos, awnings and shade',
            'A quick patch of shelter and a big boost in “we planned this”.',
            'Sunny days, drizzly evenings and everything in between.',
            products=make_products(
                [
                    'Gazebo',
                    'Pop-up gazebo',
                    'Sail shade',
                    'Garden pergola',
                    'Patio awning',
                    'Parasol set',
                    'Beach shelter',
                    'Windbreak set',
                    'Camping awning',
                    'Outdoor screen divider',
                ],
                'Adds shade, shelter and a little extra composure.',
            ),
        ),
        category_node(
            'Fire pits and outdoor heat',
            'Late evenings made warmer and far more inviting.',
            'Cosy kit for chilly air and good conversation.',
            products=make_products(
                [
                    'Fire pit',
                    'Smokeless fire pit',
                    'Chiminea',
                    'Patio heater',
                    'Tabletop heater',
                    'Pizza oven',
                    'Log rack',
                    'Outdoor lantern heater',
                    'Marshmallow roasting kit',
                    'Fire bowl grill combo',
                ],
                'Excellent for warmth, atmosphere and slightly longer evenings.',
            ),
        ),
        category_node(
            'Hot tubs and celebration extras',
            'For weekends that need just a little more theatre.',
            'A splash of indulgence without the lifetime commitment.',
            products=make_products(
                [
                    'Inflatable hot tub',
                    'Ice bath tub',
                    'Outdoor speaker tripod',
                    'Garden projector screen',
                    'Confetti cannon stand',
                    'Sparkler safe bucket kit',
                    'Outdoor cocktail station',
                    'Champagne wall',
                    'LED cube seating',
                    'Photo backdrop frame',
                ],
                'Useful when “nice weekend” needs a little more sparkle.',
            ),
        ),
        category_node(
            'BBQs and outdoor cooking',
            'Feed people outside and instantly look more organised than you feel.',
            'Smoke, sizzle and polite queueing for burgers.',
            products=make_products(
                [
                    'Gas BBQ',
                    'Charcoal BBQ',
                    'Smoker BBQ',
                    'Flat top griddle',
                    'Rotisserie BBQ kit',
                    'Paella burner stand',
                    'Tandoor oven',
                    'Camping cook station',
                    'Prep table with wind guard',
                    'Cool chest and serving station',
                    'BBQ tool bundle',
                    'Outdoor sink station',
                ],
                'Great for garden feasts and people suddenly offering to help.',
            ),
        ),
        category_node(
            'Adventure and beach gear',
            'For sandy days, breezy afternoons and ambitious family outings.',
            'Practical kit with a strong holiday mood.',
            products=make_products(
                [
                    'Beach trolley',
                    'Beach shelter',
                    'Paddle bat set',
                    'Family bodyboard set',
                    'Snorkel set',
                    'Fishing shelter',
                    'Portable changing tent',
                    'Sand anchor umbrella kit',
                    'Cooler backpack',
                    'Beach wagon',
                    'Rock pooling kit',
                    'Portable rinse shower',
                ],
                'Built for seaside plans and a little less carrying misery.',
            ),
        ),
        category_node(
            'Play equipment and family fun',
            'Short-term big fun without permanently living around giant plastic things.',
            'Useful for holidays, birthdays and school breaks.',
            products=make_products(
                [
                    'Trampoline',
                    'Garden slide',
                    'Climbing dome',
                    'Soft archery set',
                    'Kids obstacle course',
                    'Splash mat',
                    'Ball game target wall',
                    'Mini football goal set',
                    'Giant chalkboard easel',
                    'Mud kitchen',
                    'Ride-on toy track set',
                    'Pop-up play tent village',
                ],
                'Turns spare outdoor space into a much louder success story.',
            ),
        ),
        category_node(
            'Water play and pool gear',
            'Splashy extras for hot days, garden parties and enthusiastic kids.',
            'Seasonal fun without year-round storage guilt.',
            products=make_products(
                [
                    'Paddling pool',
                    'Pool pump set',
                    'Inflatable water slide',
                    'Slip and slide lane',
                    'Pool vacuum',
                    'Chlorine floater kit',
                    'Inflatable lounger pack',
                    'Garden mist arch',
                    'Water blaster game set',
                    'Poolside towel stand',
                    'Shade umbrella for pool',
                    'Floating drinks cooler',
                    'Pool thermometer',
                    'Inflatable ring bundle',
                ],
                'Made for sunny chaos and a bit of welcome splashing.',
            ),
        ),
    ]

    home_improvement_children = [
        category_node(
            'Carpet and floor cleaning',
            'Carpet, upholstery and hard floor cleaning.',
            'Cleaning and drying kit for floors and soft furnishings.',
            children=carpet_children,
        ),
        category_node(
            'Decorating and painting',
            'From quick refreshes to full room reinventions.',
            'Colour, coverage and fewer streaky regrets.',
            products=make_products(
                [
                    'Paint sprayer',
                    'Airless paint sprayer',
                    'Wallpaper steamer',
                    'Mixing paddle',
                    'Dustless sander for decorating',
                    'Extension roller pole set',
                    'Paint scuttle and tray kit',
                    'Detail spray gun',
                    'Caulking gun set',
                    'Heat gun',
                    'Plaster smoothing kit',
                    'Door painting stand',
                ],
                'Helps rooms change personality with less faff.',
            ),
        ),
        category_node(
            'Flooring and wallpaper tools',
            'Straight lines, tidy joins and a lot less kneeling guesswork.',
            'For the finish that people actually notice.',
            products=make_products(
                [
                    'Floor roller',
                    'Laminate cutter',
                    'Flooring pull bar kit',
                    'Vinyl floor welding kit',
                    'Carpet knee kicker',
                    'Carpet stretcher',
                    'Tile levelling kit',
                    'Grout removal tool',
                    'Wallpaper pasting table',
                    'Wallpaper seam roller',
                ],
                'Keeps the neat bits neat and the awkward bits shorter-lived.',
            ),
        ),
        category_node(
            'Cleaning and restoration',
            'For those “we need to sort this out properly” weekends.',
            'A little rescue, a little revival.',
            products=make_products(
                [
                    'Wet and dry vacuum',
                    'Dehumidifier',
                    'Air mover fan',
                    'Mould fogger',
                    'Steam cleaner',
                    'Hard floor polisher',
                    'Pressure washer for patios',
                    'Gutter vacuum',
                    'Window vacuum',
                    'Drain camera',
                ],
                'Useful when a room or surface needs a proper comeback story.',
            ),
        ),
        category_node(
            'Plumbing and drain tools',
            'Leaks, blockages and mildly alarming noises handled more calmly.',
            'Small fixes and grubby victories live here.',
            products=make_products(
                [
                    'Drain rods',
                    'Drain auger',
                    'Pipe freezing kit',
                    'Pipe press tool',
                    'PEX crimp tool',
                    'Pipe bender',
                    'Wet tile drill set',
                    'Stopcock key set',
                    'Radiator bleed and flush kit',
                    'Submersible clean water pump',
                ],
                'Handy for the jobs no one brags about but everyone needs.',
            ),
        ),
        category_node(
            'General access and ladders',
            'Reach the awkward spot without balancing on anything regrettable.',
            'Basic, brilliant and always unexpectedly useful.',
            products=make_products(
                [
                    'Ladder',
                    'Extension ladder',
                    'Multi-position ladder',
                    'Step stool set',
                    'Decorators platform',
                    'Roof ladder',
                    'Loft ladder',
                    'Stairwell platform',
                    'Safety barrier set',
                    'Tool belt and bucket hook kit',
                ],
                'Makes high-up jobs feel much less improvised.',
            ),
        ),
        category_node(
            'Electrical test and install tools',
            'For chasing faults, checking safety and making the fiddly bits more manageable.',
            'Useful kit for the tidy-minded sparks jobs.',
            products=make_products(
                [
                    'Socket tester',
                    'Multimeter',
                    'Cable detector',
                    'Insulation resistance tester',
                    'RCD tester',
                    'Voltage tester',
                    'Cable pull rods',
                    'Conduit bender',
                    'Wire stripper set',
                    'Crimping tool kit',
                    'Label printer for circuits',
                    'Portable site light kit',
                ],
                'Helps electrical work feel more measured and less guessy.',
            ),
        ),
        category_node(
            'Windows, doors and glazing tools',
            'For hanging, trimming, adjusting and handling the awkward fragile stuff.',
            'A niche corner, but a very useful one.',
            products=make_products(
                [
                    'Door trimming stand',
                    'Door lifter',
                    'Hinge jig kit',
                    'Lock fitting jig',
                    'Glazing suction lifters',
                    'Bead removal tool',
                    'Window handle installer kit',
                    'Glass carrying frame',
                    'Mitre clamp for frames',
                    'Sealant finishing kit',
                    'Window film application set',
                    'Packer shim box',
                ],
                'Built for neater fits and fewer stressful wobbles.',
            ),
        ),
        category_node(
            'Tiling and finishing tools',
            'For crisp edges, neat grout lines and rooms that look properly done.',
            'The detail-loving side of home improvement.',
            products=make_products(
                [
                    'Large format tile cutter',
                    'Wet tile saw',
                    'Tile hole cutter set',
                    'Tile suction handle pair',
                    'Grout float kit',
                    'Tile polishing pad set',
                    'Knee pads and trolley seat',
                    'Corner finishing trowel',
                    'Skimming spatula set',
                    'Jointing knife set',
                    'Texture roller kit',
                    'Sealant smoothing set',
                ],
                'Useful when the final look matters as much as the messy middle.',
            ),
        ),
        category_node(
            'Joinery installation tools',
            'For fitting kitchens, hanging doors and making timber line up properly.',
            'The precise side of practical progress.',
            products=make_products(
                [
                    'Pocket hole jig',
                    'Cabinet clamp set',
                    'Worktop router jig',
                    'Hinge recess jig',
                    'Laminate trimming set',
                    'Door lining clamp pair',
                    'Cabinet lift jack',
                    'Shelf pin drilling jig',
                    'Dowelling jig',
                    'Scribe tool set',
                    'Countertop seam setter',
                    'Mitre bond activator kit',
                ],
                'Helps joinery jobs land cleaner and faster.',
            ),
        ),
    ]

    tree = [
        category_node(
            'Costumes and fancy dress',
            'Play the part, steal the night.',
            'From school dress-up days to full-throttle party entrances.',
            children=costume_children,
        ),
        category_node(
            'Event hire',
            'Everything you need to turn a gathering into a proper occasion.',
            'Big days, smaller storage problems.',
            children=event_children,
        ),
        category_node(
            'Garden',
            'For lawns, borders, timber piles and outdoor plans with ambition.',
            'A proper toolbox for the great outdoors.',
            children=garden_children,
        ),
        category_node(
            'Sports equipment',
            'For fitness sessions, weekends away and competitive nonsense.',
            'Borrow the gear, keep the good stories.',
            children=sports_children,
        ),
        category_node(
            'Vehicle and accessories',
            'Handy extras for moving, towing and loading.',
            'The useful bits that make the car feel far more capable.',
            children=vehicle_children,
        ),
        category_node(
            'DIY and power tools',
            'Proper tools for proper jobs, from trim work to dusty mayhem.',
            'This is the one that grows legs very quickly.',
            children=diy_children,
        ),
        category_node(
            'Moving and storage',
            'For moving day, clear-outs and taming the clutter mountain.',
            'Less heavy lifting, more getting it sorted.',
            children=moving_children,
        ),
        category_node(
            'Outdoor and leisure',
            'Sunny-day kit, cosy-evening extras and things that make gardens more fun.',
            'A cheerful mix of practical and playful.',
            children=outdoor_children,
        ),
        category_node(
            'Home improvement',
            'For refreshes, repairs and “we may as well do it properly” weekends.',
            'Decorating, fixing and restoring without buying everything outright.',
            children=home_improvement_children,
        ),
    ]
    return flatten_category_tree(tree)


class Command(BaseCommand):
    help = 'Seed or update catalog categories and products.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune-categories',
            action='store_true',
            help='Delete categories under the managed top-level tree that are not part of the seed payload. Categories with ordered products are skipped.',
        )

    def handle(self, *args, **options):
        created_categories = 0
        updated_categories = 0
        created_products = 0
        updated_products = 0
        merged_categories = 0
        deleted_products = 0
        skipped_product_deletes = 0
        deleted_categories = 0
        skipped_category_deletes = 0
        prune_categories = bool(options.get('prune_categories'))

        with db_transaction.atomic():
            top_category, _ = Category.objects.get_or_create(
                slug='top',
                defaults={'title': 'top'},
            )

            managed_categories = {}
            desired_products_by_category_id = {}

            for category_data in category_payload():
                category_attributes = category_data.get('attributes', [])
                parent_category = resolve_parent_category(category_data, top_category)
                category, created = upsert_category(
                    category_data['title'],
                    {
                        'description': category_data['description'],
                        'parent_category': parent_category,
                        **attribute_defaults(category_attributes),
                    },
                )
                managed_categories[category.title] = category
                if created:
                    created_categories += 1
                else:
                    updated_categories += 1

                for attribute in category_attributes:
                    CategoryAttribute.objects.update_or_create(
                        category=category,
                        order=attribute['order'],
                        defaults={
                            'name': attribute.get('name', ''),
                            'value_source': attribute.get('value_source', 'product'),
                            'sortable': bool(attribute.get('sortable')),
                            'filterable': bool(attribute.get('filterable')),
                            'default_filtered_value': attribute.get('default_filtered_value', ''),
                            'allowed_values_text': '\n'.join(attribute.get('allowed_values', [])),
                        },
                    )

                desired_names = []
                for product_data in category_data['products']:
                    if isinstance(product_data, tuple):
                        product_name, product_description = product_data
                        product_attributes = {}
                    else:
                        product_name = product_data['name']
                        product_description = product_data['description']
                        product_attributes = product_data.get('attributes', {})
                    desired_names.append(product_name)
                    _, product_created = upsert_product(
                        category,
                        product_name,
                        {
                            'description': html_description(product_description),
                            'attribute_one_value': product_attributes.get(1, ''),
                            'attribute_two_value': product_attributes.get(2, ''),
                            'attribute_three_value': product_attributes.get(3, ''),
                            'attribute_four_value': product_attributes.get(4, ''),
                            'attribute_five_value': product_attributes.get(5, ''),
                        },
                    )
                    if product_created:
                        created_products += 1
                    else:
                        updated_products += 1
                desired_products_by_category_id[category.id] = desired_names

            for legacy_title, canonical_title in LEGACY_CATEGORY_MERGES.items():
                source_category = Category.objects.filter(title__iexact=legacy_title).first()
                target_category = Category.objects.filter(title=canonical_title).first()
                if source_category is None or target_category is None:
                    continue
                if merge_legacy_category(source_category, target_category):
                    merged_categories += 1

            for category in managed_categories.values():
                deleted_count, skipped_count = delete_obsolete_products(
                    category,
                    desired_products_by_category_id.get(category.id, []),
                )
                deleted_products += deleted_count
                skipped_product_deletes += skipped_count

            if prune_categories:
                deleted_categories, skipped_category_deletes = delete_obsolete_categories(
                    top_category,
                    managed_categories.keys(),
                )

        self.stdout.write(
            self.style.SUCCESS(
                'Catalog sync complete: '
                f'{created_categories} categories created, {updated_categories} updated, '
                f'{created_products} products created, {updated_products} updated, '
                f'{merged_categories} legacy categories merged, '
                f'{deleted_products} obsolete products deleted, '
                f'{skipped_product_deletes} product deletes skipped because they already have orders, '
                f'{deleted_categories} obsolete categories deleted, '
                f'{skipped_category_deletes} category deletes skipped because they contain ordered products.'
            )
        )
