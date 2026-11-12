"""Export the evidence snapshot used by taxonomy review without using an LLM."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from navigation.taxonomy_ai import catalogue_snapshot


class Command(BaseCommand):
    help = 'Write a database-only catalogue taxonomy snapshot as JSON (no AI request).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            required=True,
            help='Path inside the running web container for the JSON file.',
        )

    def handle(self, *args, **options):
        output = Path(options['output'])
        if not output.parent.exists():
            raise CommandError(f'Output directory does not exist: {output.parent}')

        with output.open('w', encoding='utf-8') as handle:
            json.dump(catalogue_snapshot(), handle, indent=2, default=str)
            handle.write('\n')

        self.stdout.write(self.style.SUCCESS(
            f'Wrote database-only taxonomy snapshot to {output}'
        ))
