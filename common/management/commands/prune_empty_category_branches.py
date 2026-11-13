"""Preview or remove category branches which contain no product templates."""

from django.core.management.base import BaseCommand
from django.db import transaction

from common.models import Category, Product


class Command(BaseCommand):
    help = (
        'Preview or remove all empty category branches bottom-up. A category is removed only when it and every '
        'remaining descendant have zero product templates; the Top root is always retained.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Delete the previewed empty branches. Without this flag nothing is changed.',
        )

    @staticmethod
    def _empty_leaves():
        """Return current empty leaves, excluding the structural Top category."""
        category_rows = list(Category.objects.values_list('id', 'slug', 'title', 'parent_category_id'))
        product_category_ids = set(Product.objects.values_list('category_id', flat=True))
        children_by_parent = {}
        for category_id, _slug, _title, parent_id in category_rows:
            children_by_parent.setdefault(parent_id, set()).add(category_id)

        remaining = {row[0]: row for row in category_rows}
        deletable = []
        while True:
            leaves = [
                category_id
                for category_id, (_id, slug, _title, _parent_id) in remaining.items()
                if slug != 'top'
                and category_id not in product_category_ids
                and not (children_by_parent.get(category_id, set()) & remaining.keys())
            ]
            if not leaves:
                break
            deletable.extend(leaves)
            for category_id in leaves:
                remaining.pop(category_id)
        return deletable

    def handle(self, *args, **options):
        category_ids = self._empty_leaves()
        categories = Category.objects.in_bulk(category_ids)
        ordered = sorted(categories.values(), key=lambda category: (category.title.lower(), category.id))

        if not ordered:
            self.stdout.write(self.style.SUCCESS('No wholly empty category branches found.'))
            return

        self.stdout.write(f'Empty category records eligible for removal: {len(ordered)}')
        for category in ordered:
            self.stdout.write(f'  - #{category.id} {category.title}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                'Preview only. Nothing has changed. Rerun with --apply to delete only these empty branches.'
            ))
            return

        # Deleting the explicit set inside one transaction prevents a partially
        # cleaned tree. Every selected category was verified product-free above.
        with transaction.atomic():
            Category.objects.filter(pk__in=category_ids).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {len(category_ids)} wholly empty category records.'))
