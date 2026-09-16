"""Derived video previews; the uploaded evidence file is never modified."""
import logging
import shutil
import subprocess
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.files import File
from django.utils import timezone

logger = logging.getLogger(__name__)


def queue_video_preview(evidence_id):
    from celery import current_app
    from celery.exceptions import AlwaysEagerIgnored
    # send_task deliberately bypasses local CELERY_TASK_ALWAYS_EAGER: a web
    # request must never run an encoder, even in development.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', AlwaysEagerIgnored)
        return current_app.send_task('transaction.tasks.generate_video_preview',
                                     args=[evidence_id], queue='video', retry=False)


def generate_preview(evidence_id):
    from .models import TransactionMessageImage

    rows = TransactionMessageImage.objects
    if not rows.filter(pk=evidence_id, preview_status='pending').update(
            preview_status='processing', preview_updated_at=timezone.now()):
        return False
    item = rows.get(pk=evidence_id)
    try:
        source = item.video_raw or item.video
        if not source:
            raise ValueError('No uploaded video')
        with TemporaryDirectory(prefix='rental-video-') as directory:
            original = Path(directory) / ('input' + Path(source.name).suffix)
            output = Path(directory) / 'preview.mp4'
            with source.open('rb') as incoming, original.open('wb') as target:
                shutil.copyfileobj(incoming, target)
            subprocess.run([
                getattr(settings, 'FFMPEG_BINARY', 'ffmpeg'), '-nostdin', '-y',
                '-protocol_whitelist', 'file,pipe',
                '-format_whitelist', 'mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,avi',
                '-i', str(original), '-map', '0:v:0', '-map', '0:a:0?',
                '-vf', "scale=w='if(gte(iw,ih),min(854,iw),min(480,iw))':h='if(gte(iw,ih),min(480,ih),min(854,ih))':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
                '-r', '24', '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
                '-maxrate', '1200k', '-bufsize', '2400k', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart',
                '-threads', '2', str(output),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
            with output.open('rb') as preview:
                item.video_preview.save('preview.mp4', File(preview), save=False)
            rows.filter(pk=item.pk).update(video_preview=item.video_preview.name,
                                          preview_status='ready', preview_updated_at=timezone.now())
        return True
    except Exception:
        logger.exception('Video preview failed for evidence %s', evidence_id)
        rows.filter(pk=evidence_id).update(preview_status='failed', preview_updated_at=timezone.now())
        return False
