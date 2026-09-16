from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand

from transaction.models import TransactionMessageImage
from transaction.video import queue_video_preview


class Command(BaseCommand):
    help = 'Queue existing video uploads for Celery preview processing.'

    def add_arguments(self, parser):
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **options):
        rows = TransactionMessageImage.objects.exclude(video='').exclude(video__isnull=True)
        if options['retry_failed']:
            rows.filter(preview_status='processing', preview_updated_at__lt=timezone.now() - timedelta(minutes=15)).update(preview_status='pending')
            rows.filter(preview_status='failed').update(preview_status='pending')
        count = 0
        for pk in rows.filter(preview_status='pending').values_list('pk', flat=True).iterator():
            queue_video_preview(pk)
            count += 1
        self.stdout.write(f'Queued {count} previews. Run the Celery worker to process them.')
