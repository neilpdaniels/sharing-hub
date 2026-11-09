"""Turn Adult/Kids Fancy Dress catalogue branches into reusable product types.

This is deliberately a preview-first command.  It changes no records unless
``--apply`` is supplied, and it refuses to remove source categories that have
child categories.  It is meant for the small, reviewed conversion described in
the catalogue plan, not as a general taxonomy pruning tool.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from common.models import Category, CategoryAttribute, Order, Product
from transaction.models import Transaction


class Command(BaseCommand):
    help = (
        'Preview or apply the Fancy Dress catalogue conversion: generic Adult '
        'and Children\'s products with individually named listings.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--adult-category-id', required=True, type=int)
        parser.add_argument('--children-category-id', required=True, type=int)
        parser.add_argument(
            '--parent-category-id', type=int,
            help='Optional parent for the new “Fancy dress” category. Defaults to the shared source parent.',
        )
        parser.add_argument('--apply', action='store_true', help='Make the reviewed conversion. Default is preview only.')

    def handle(self, *args, **options):
        adult = self._category(options['adult_category_id'], 'adult')
        children = self._category(options['children_category_id'], 'children')
        sources = ((adult, 'Adult fancy dress'), (children, "Children's fancy dress"))
        parent = self._parent(options.get('parent_category_id'), adult, children)

        for source, product_title in sources:
            products = Product.objects.filter(category_id=source).order_by('id')
            orders = Order.objects.filter(product__in=products)
            transactions = Transaction.objects.filter(product__in=products)
            self.stdout.write(
                f'{source.title} (#{source.pk}) → {product_title}: '
                f'{products.count()} catalogue products, {orders.count()} listings, '
                f'{transactions.count()} transactions.'
            )
            if source.category_set.exists():
                raise CommandError(
                    f'{source.title} (#{source.pk}) has child categories. Refusing to delete it; '
                    'review or move those first.'
                )

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                'Preview only. No records changed. Review the counts, then rerun with --apply.'
            ))
            return

        with db_transaction.atomic():
            target, created = Category.objects.get_or_create(
                title='Fancy dress',
                parent_category=parent,
                defaults={
                    'description': 'Costumes for parties, events and dress-up.',
                    'risk_rating': max(adult.risk_rating, children.risk_rating),
                },
            )
            self._copy_listing_filters(target, (adult, children))

            moved_orders = 0
            moved_transactions = 0
            removed_products = 0
            for source, product_title in sources:
                target_product, _ = Product.objects.get_or_create(
                    category_id=target,
                    name=product_title,
                    defaults={
                        'description': f'Individual {product_title.lower()} listings.',
                    },
                )
                source_products = list(Product.objects.filter(category_id=source).order_by('id'))
                for product in source_products:
                    for order in Order.objects.filter(product=product).iterator():
                        if not order.listing_title.strip():
                            order.listing_title = product.name
                        order.product = target_product
                        order.save(update_fields=('listing_title', 'product', 'amended'))
                        moved_orders += 1
                    moved_transactions += Transaction.objects.filter(product=product).update(product=target_product)
                    product.delete()
                    removed_products += 1
                source.delete()

        verb = 'Created' if created else 'Used existing'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} Fancy dress category #{target.pk}; moved {moved_orders} listings and '
            f'{moved_transactions} transactions; removed {removed_products} old product templates and 2 source categories.'
        ))

    def _category(self, category_id, label):
        try:
            return Category.objects.get(pk=category_id)
        except Category.DoesNotExist as exc:
            raise CommandError(f'The {label} category #{category_id} does not exist.') from exc

    def _parent(self, explicit_parent_id, adult, children):
        if explicit_parent_id:
            return self._category(explicit_parent_id, 'parent')
        if adult.parent_category_id != children.parent_category_id:
            raise CommandError(
                'The two source categories have different parents. Supply --parent-category-id explicitly.'
            )
        return adult.parent_category

    def _copy_listing_filters(self, target, sources):
        """Carry Theme/Size (and any other named source attributes) onto listings."""
        merged = defaultdict(lambda: {'values': [], 'definition': None})
        for source in sources:
            for definition in source.get_attribute_definitions():
                name = (definition.get('name') or '').strip()
                if not name:
                    continue
                key = name.casefold()
                entry = merged[key]
                entry['definition'] = entry['definition'] or definition
                for value in definition.get('allowed_values') or []:
                    if value not in entry['values']:
                        entry['values'].append(value)

        if not merged:
            merged = {
                'theme': {'definition': {'order': 1, 'name': 'Theme', 'sortable': True, 'filterable': True}, 'values': []},
                'size': {'definition': {'order': 2, 'name': 'Size', 'sortable': False, 'filterable': True}, 'values': []},
            }

        used_orders = set()
        for entry in merged.values():
            definition = entry['definition']
            order = int(definition['order'])
            if order in used_orders:
                continue
            used_orders.add(order)
            CategoryAttribute.objects.update_or_create(
                category=target,
                order=order,
                defaults={
                    'name': definition['name'],
                    'value_source': CategoryAttribute.VALUE_SOURCE_LISTING,
                    'sortable': bool(definition.get('sortable')),
                    'filterable': bool(definition.get('filterable')),
                    'default_filtered_value': definition.get('default_filtered_value') or '',
                    'allowed_values_text': '\n'.join(entry['values']),
                },
            )
