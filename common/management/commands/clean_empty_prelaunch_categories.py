"""Remove the empty category leaves verified in the 12 November 2026 snapshot.

This is deliberately narrow and preview-first.  It does not prune a parent
merely because that parent has no direct products: parents can be useful browse
groups whose products live in their child categories.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Category, Product


# ``documents/catalogue-taxonomy.json`` exported 12 November 2026 verified that
# every one of these is an empty leaf with no listings or rental history.
EMPTY_LEAVES = {
    194: 'Bed rails',
    195: 'Shower chairs',
    196: 'Grabbers and reachers',
    207: 'Bath aids',
    208: 'Raised toilet seats',
    209: 'Bed wedges',
    210: 'Overbed tables',
    211: 'Mobility ramps',
}


class Command(BaseCommand):
    help = 'Preview or remove the eight empty pre-launch category leaves verified on 12 November 2026.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Delete the verified empty leaves. Without this flag, only show the proposed scope.',
        )

    def handle(self, *args, **options):
        categories = Category.objects.in_bulk(EMPTY_LEAVES)
        missing = sorted(set(EMPTY_LEAVES) - set(categories))
        if missing:
            raise CommandError(
                f'Expected category IDs are missing: {missing}. It may already have been applied; nothing was changed.'
            )

        invalid = []
        for category_id, expected_title in EMPTY_LEAVES.items():
            category = categories[category_id]
            if category.title != expected_title:
                invalid.append(
                    f'#{category_id} is {category.title!r}, expected {expected_title!r}'
                )
            if Product.objects.filter(category_id=category).exists():
                invalid.append(f'#{category_id} {category.title!r} now has product templates')
            if Category.objects.filter(parent_category=category).exists():
                invalid.append(f'#{category_id} {category.title!r} is no longer a leaf category')
        if invalid:
            raise CommandError('Refusing to delete: ' + '; '.join(invalid))

        self.stdout.write('Verified empty category leaves:')
        for category in categories.values():
            self.stdout.write(f'  - #{category.id} {category.title} ({category.parent_category.title})')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Preview only. Nothing has changed. Rerun with --apply to delete these eight empty leaves.'))
            return

        with transaction.atomic():
            Category.objects.filter(pk__in=EMPTY_LEAVES).delete()
        self.stdout.write(self.style.SUCCESS('Deleted 8 verified-empty pre-launch category leaves.'))
