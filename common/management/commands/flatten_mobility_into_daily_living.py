"""Convert agreed product-like mobility category leaves into Daily living products."""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Category, Order, Product
from transaction.models import Transaction


DAILY_LIVING_TITLE = 'Daily living support'
MOBILITY_TITLE = 'Mobility aids'
COMMODES_TITLE = 'Commodes'


class Command(BaseCommand):
    help = (
        'Preview or flatten the agreed Mobility aids and Commodes category nodes into product templates under '
        'Daily living support. It is designed for the pre-launch catalogue only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Create the product templates and retire the old category nodes. Without this flag, only preview.',
        )

    @staticmethod
    def _one_category(title, *, parent=None):
        categories = Category.objects.filter(title__iexact=title)
        if parent is not None:
            categories = categories.filter(parent_category=parent)
        matches = list(categories)
        if len(matches) != 1:
            location = f' beneath {parent.title!r}' if parent else ''
            raise CommandError(f'Expected exactly one {title!r}{location}; found {len(matches)}.')
        return matches[0]

    @staticmethod
    def _descendant_ids(root):
        children_by_parent = defaultdict(list)
        for category_id, parent_id in Category.objects.values_list('id', 'parent_category_id'):
            children_by_parent[parent_id].append(category_id)
        found = set()
        pending = [root.id]
        while pending:
            category_id = pending.pop()
            if category_id in found:
                continue
            found.add(category_id)
            pending.extend(children_by_parent.get(category_id, []))
        return found, children_by_parent

    @staticmethod
    def _attribute_names(category):
        return [
            definition['name'] for definition in category.get_attribute_definitions()
            if (definition.get('name') or '').strip()
        ]

    def handle(self, *args, **options):
        daily_living = self._one_category(DAILY_LIVING_TITLE)
        mobility = self._one_category(MOBILITY_TITLE)
        commodes = self._one_category(COMMODES_TITLE, parent=daily_living)
        mobility_ids, children_by_parent = self._descendant_ids(mobility)
        source_ids = mobility_ids | {commodes.id}

        # Each Mobility-aids leaf becomes one product. Commodes is itself one
        # product-like leaf under Daily living support.
        conversion_categories = [
            category for category in Category.objects.filter(pk__in=source_ids).order_by('title', 'id')
            if category.id == commodes.id or not (set(children_by_parent.get(category.id, [])) & source_ids)
        ]
        non_leaf_products = Product.objects.filter(category_id__in=source_ids).exclude(
            category_id__in=[category.id for category in conversion_categories]
        )
        if non_leaf_products.exists():
            raise CommandError(
                'Refusing to flatten: a non-leaf source category has product templates. Review it explicitly first: '
                + ', '.join(non_leaf_products.values_list('name', flat=True)[:10])
            )

        attribute_problems = []
        for category in Category.objects.filter(pk__in=source_ids):
            names = self._attribute_names(category)
            if names:
                attribute_problems.append(f'{category.title}: {", ".join(names)}')
        if attribute_problems:
            raise CommandError(
                'Refusing to flatten categories that define filters, because moving them could silently change how '
                'listing attribute values are interpreted. Review these first: ' + '; '.join(attribute_problems)
            )

        source_product_ids = list(Product.objects.filter(category_id__in=source_ids).values_list('id', flat=True))
        order_count = Order.objects.filter(product_id__in=source_product_ids).count()
        transaction_count = Transaction.objects.filter(product_id__in=source_product_ids).count()
        if order_count or transaction_count:
            raise CommandError(
                f'Refusing to flatten: source products have {order_count} order(s) and {transaction_count} transaction(s). '
                'No history will be reassigned automatically.'
            )

        self.stdout.write(f'Destination category: #{daily_living.id} {daily_living.title}')
        self.stdout.write('Category-to-product conversions:')
        for category in conversion_categories:
            product_count = Product.objects.filter(category_id=category).count()
            self.stdout.write(
                f'  - #{category.id} {category.title} -> product {category.title!r} '
                f'(replacing {product_count} existing template(s) in that node)'
            )
        self.stdout.write(f'Retire category records: {len(source_ids)} (Mobility aids subtree plus Commodes).')

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                'Preview only. Nothing has changed. Review this exact conversion, then rerun with --apply.'
            ))
            return

        with transaction.atomic():
            for category in conversion_categories:
                product, _created = Product.objects.get_or_create(
                    category_id=daily_living,
                    name=category.title,
                    defaults={
                        'description': category.description or '',
                        'risk_rating': category.risk_rating,
                    },
                )
                changed_fields = []
                if not product.description and category.description:
                    product.description = category.description
                    changed_fields.append('description')
                if not product.image and category.image:
                    product.image.name = category.image.name
                    changed_fields.append('image')
                if changed_fields:
                    product.save(update_fields=changed_fields)
                product.tags.add(*category.tags.all())

                # These have already been confirmed to have no order or
                # transaction history, so removing them cannot lose a live
                # listing or rental record.
                Product.objects.filter(category_id=category).delete()

            Category.objects.filter(pk__in=source_ids).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Flattened {len(conversion_categories)} category nodes into Daily living support products and retired '
            f'{len(source_ids)} old category records.'
        ))
