"""One-time, reviewed reset of the speculative pre-launch catalogue.

This command implements the agreed initial launch shape, not a general-purpose
catalogue cleaner.  It is deliberately preview-first and checks the exact IDs
and titles from the 9 November 2026 taxonomy snapshot before doing anything.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from common.models import Category, CategoryAttribute, Order, Product
from transaction.models import Transaction


# Whole branches agreed to be out of scope for the initial, short-hire launch.
# Their child categories and products are removed together, but only after the
# history guard has confirmed that they have never been used.
REMOVE_SUBTREES = {
    110: 'Recovery and physio',
    116: 'Wellbeing and self care',
    128: 'Sleep and comfort',
    147: 'Therapy and pain relief',
    158: 'family',
}

# Low-rental-fit / consumable-like branches to remove while retaining their
# useful siblings under Moving and storage.
REMOVE_LEAVES = {
    66: 'Boxes, crates and totes',
    68: 'Wrapping, covers and protection',
    69: 'Ratchets, ropes and securing',
    70: 'Temporary storage and organisation',
    73: 'Cleaning and handover kit',
}

# These are safe housekeeping removals: a category must still be an empty leaf
# when the command runs.  Keeping this list explicit avoids removing a newly
# added empty category someone intends to populate.
REMOVE_EMPTY_LEAVES = {
    121: 'Personal care devices',
    129: 'Pressure relief',
    130: 'Positioning aids',
    137: 'Baby swings and rockers',
    141: 'Baby bouncers',
    145: 'Potty training aids',
    151: 'Massage and soft tissue',
    163: 'Foam rollers',
    164: 'Stretching aids',
    165: 'Aromatherapy diffusers',
    168: 'Bath aids',
    169: 'Raised toilet seats',
    170: 'Bed wedges',
    171: 'Overbed tables',
    172: 'Mobility ramps',
    173: 'Pressure relief cushions',
    180: 'Heating pads',
}

FANCY_DRESS = {
    2: 'Costumes and fancy dress',
    3: 'Adult fancy dress',
    4: 'Kids fancy dress',
    5: 'Mascots and character suits',
}


class Command(BaseCommand):
    help = (
        'Preview or apply the one-time pre-launch catalogue reset agreed from '
        'the 9 November 2026 taxonomy review.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Make the reviewed changes. Without this flag the command only reports its exact scope.',
        )

    def handle(self, *args, **options):
        categories = self._load_expected_categories()
        removal_roots = [categories[category_id] for category_id in REMOVE_SUBTREES]
        removal_roots.extend(categories[category_id] for category_id in REMOVE_LEAVES)
        removal_roots.extend(categories[category_id] for category_id in REMOVE_EMPTY_LEAVES)

        self._validate_empty_leaves(categories)
        removal_category_ids = self._descendant_ids(removal_roots)
        # The costume sources are converted rather than included in the
        # deletion scope, so their listing/transaction records are retained.
        removal_product_ids = set(
            Product.objects.filter(category_id__in=removal_category_ids).values_list('id', flat=True)
        )
        conversion_product_ids = set(
            Product.objects.filter(category_id__in=(3, 4, 5)).values_list('id', flat=True)
        )

        self._assert_unused(removal_product_ids, 'planned removal')
        self._report(removal_category_ids, removal_product_ids, conversion_product_ids)
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                'Preview only. Nothing has changed. Review the scope, back up the database, then rerun with --apply.'
            ))
            return

        with db_transaction.atomic():
            self._convert_fancy_dress(categories)
            # Delete deepest categories first. This makes the action clear in
            # history/admin logs and never relies on an unexpected broad cascade.
            for category in sorted(
                Category.objects.filter(pk__in=removal_category_ids),
                key=self._depth,
                reverse=True,
            ):
                category.delete()

        self.stdout.write(self.style.SUCCESS(
            'Pre-launch catalogue reset complete. Run a new heavy product review next; it will assess the remaining '
            'DIY, garden, event, vehicle and outdoor product templates against the lean-launch rules.'
        ))

    def _load_expected_categories(self):
        expected = {**REMOVE_SUBTREES, **REMOVE_LEAVES, **REMOVE_EMPTY_LEAVES, **FANCY_DRESS}
        categories = Category.objects.in_bulk(expected)
        missing = sorted(set(expected) - set(categories))
        if missing:
            raise CommandError(f'Expected category IDs are missing: {missing}. This reset is only valid for the reviewed snapshot.')
        mismatched = [
            f'#{category_id} is “{categories[category_id].title}”, expected “{title}”'
            for category_id, title in expected.items()
            if categories[category_id].title != title
        ]
        if mismatched:
            raise CommandError('Snapshot mismatch: ' + '; '.join(mismatched))
        return categories

    def _validate_empty_leaves(self, categories):
        failures = []
        for category_id, title in REMOVE_EMPTY_LEAVES.items():
            category = categories[category_id]
            if Product.objects.filter(category_id=category).exists() or Category.objects.filter(parent_category=category).exists():
                failures.append(f'#{category_id} {title} is no longer an empty leaf')
        if failures:
            raise CommandError('; '.join(failures))

    def _descendant_ids(self, roots):
        children = defaultdict(list)
        for category_id, parent_id in Category.objects.values_list('id', 'parent_category_id'):
            children[parent_id].append(category_id)
        found = set()
        pending = [category.pk for category in roots]
        while pending:
            category_id = pending.pop()
            if category_id in found:
                continue
            found.add(category_id)
            pending.extend(children[category_id])
        return found

    def _assert_unused(self, product_ids, label):
        if not product_ids:
            return
        order_count = Order.objects.filter(product_id__in=product_ids).count()
        transaction_count = Transaction.objects.filter(product_id__in=product_ids).count()
        if order_count or transaction_count:
            raise CommandError(
                f'Aborting: {label} would remove {order_count} order(s) and {transaction_count} transaction(s). '
                'Do not bypass this guard; review those records explicitly.'
            )

    def _report(self, removal_category_ids, removal_product_ids, conversion_product_ids):
        self.stdout.write('Pre-launch reset scope:')
        self.stdout.write(f'  - Remove {len(removal_category_ids)} category record(s) and {len(removal_product_ids)} product template(s).')
        self.stdout.write(
            f'  - Convert {len(conversion_product_ids)} costume template(s) into Adult fancy dress, '
            "Children's fancy dress and Mascot suit listings."
        )
        self.stdout.write('  - Retain the DIY, garden, event, vehicle and outdoor branches for a separately reviewed product prune.')

    def _convert_fancy_dress(self, categories):
        destination = categories[2]
        source_categories = (
            (categories[3], 'Adult fancy dress'),
            (categories[4], "Children's fancy dress"),
            (categories[5], 'Mascot suit'),
        )
        self._configure_costume_attributes(destination, [source for source, _ in source_categories])

        for source, template_name in source_categories:
            target, _ = Product.objects.get_or_create(
                category_id=destination,
                name=template_name,
                defaults={'description': f'Individual {template_name.lower()} listings.'},
            )
            for legacy_product in Product.objects.filter(category_id=source).order_by('id'):
                if not target.image and legacy_product.image:
                    target.image.name = legacy_product.image.name
                    target.save(update_fields=('image',))
                for order in Order.objects.filter(product=legacy_product).iterator():
                    if not order.listing_title.strip():
                        order.listing_title = legacy_product.name
                    order.product = target
                    order.save(update_fields=('listing_title', 'product', 'amended'))
                Transaction.objects.filter(product=legacy_product).update(product=target)
                legacy_product.delete()
            source.delete()

    def _configure_costume_attributes(self, destination, sources):
        values_by_name = defaultdict(list)
        for source in sources:
            for definition in source.get_attribute_definitions():
                name = (definition.get('name') or '').strip()
                if not name:
                    continue
                for value in definition.get('allowed_values') or []:
                    if value not in values_by_name[name]:
                        values_by_name[name].append(value)

        theme_values = values_by_name.get('Theme', [])
        size_values = values_by_name.get('Size', []) + values_by_name.get('Age range', [])
        size_values = list(dict.fromkeys(size_values))
        definitions = (
            (1, 'Theme', theme_values),
            (2, 'Size or age range', size_values),
        )
        for order, name, values in definitions:
            CategoryAttribute.objects.update_or_create(
                category=destination,
                order=order,
                defaults={
                    'name': name,
                    'value_source': CategoryAttribute.VALUE_SOURCE_LISTING,
                    'filterable': True,
                    'sortable': order == 1,
                    'default_filtered_value': '',
                    'allowed_values_text': '\n'.join(values),
                },
            )

    @staticmethod
    def _depth(category):
        depth = 0
        current = category
        seen = set()
        while current.parent_category_id and current.pk not in seen:
            seen.add(current.pk)
            depth += 1
            current = current.parent_category
        return depth
