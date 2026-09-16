import hashlib
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings, RequestFactory

from mobile_api.serializers import TransactionEvidenceSerializer
from transaction.models import TransactionMessageImage
from transaction.video import generate_preview


class VideoPreviewTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.overrides = override_settings(MEDIA_ROOT=self.directory.name)
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.user = User.objects.create_user('video-tests')

    def upload(self, content=b'original-upload', name='evidence.mp4'):
        upload = SimpleUploadedFile(name, content, content_type='video/mp4')
        return TransactionMessageImage.objects.create(user=self.user, video=upload, video_raw=upload)

    def test_upload_stores_one_original_and_queues_only_after_commit(self):
        with patch('transaction.video.queue_video_preview') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                item = self.upload()
                queue.assert_not_called()
                self.assertFalse(item.video_preview)
                self.assertEqual(item.video.name, item.video_raw.name)
                self.assertEqual(len(list(Path(self.directory.name).rglob('*.mp4'))), 1)
            queue.assert_called_once_with(item.pk)
            with self.captureOnCommitCallbacks(execute=True):
                item.active = False
                item.save(update_fields=['active'])
            queue.assert_called_once()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_queue_bypasses_eager_mode(self):
        from celery import current_app
        from transaction.video import queue_video_preview
        with patch.object(current_app, 'send_task') as publish:
            queue_video_preview(123)
        publish.assert_called_once_with('transaction.tasks.generate_video_preview',
                                        args=[123], queue='video', retry=False)

    def test_failed_preview_keeps_full_upload_downloadable(self):
        item = self.upload()
        with patch('transaction.video.subprocess.run', side_effect=RuntimeError('encoder unavailable')):
            self.assertFalse(generate_preview(item.pk))
        item.refresh_from_db()
        self.assertEqual(item.preview_status, 'failed')
        self.assertFalse(item.video_preview)
        response = self.client.get(item.video_download_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'original-upload')
        response.close()

    def test_download_requires_valid_link_for_requested_file(self):
        item = self.upload()
        # Use the actual URL prefix from reverse rather than assuming project routing.
        url = item.video_download_url
        self.assertEqual(self.client.get(url.split('?')[0]).status_code, 403)
        with patch('django.core.signing.time.time', return_value=1):
            expired = item.video_download_url
        self.assertEqual(self.client.get(expired).status_code, 403)
        other = self.upload()
        self.assertEqual(self.client.get(url.replace(f'/{item.pk}/download/', f'/{other.pk}/download/')).status_code, 403)

    def test_api_separates_preview_from_full_download(self):
        item = self.upload()
        request = RequestFactory().get('/', HTTP_HOST='testserver')
        data = TransactionEvidenceSerializer(item, context={'request': request}).data
        self.assertEqual(data['preview_url'], '')
        self.assertIn('/download/?token=', data['download_url'])
        self.assertEqual(data['preview_status'], 'pending')
        item.video_preview.save('preview.mp4', SimpleUploadedFile('preview.mp4', b'preview'), save=False)
        item.preview_status = 'ready'
        data = TransactionEvidenceSerializer(item, context={'request': request}).data
        self.assertIn('/txn_preview/', data['preview_url'])
        self.assertNotEqual(data['preview_url'], data['video_url'])

    def test_real_encoder_preserves_uploaded_bytes_audio_and_orientation(self):
        binary = getattr(settings, 'FFMPEG_BINARY', 'ffmpeg')
        if not shutil.which(binary):
            self.skipTest('Install FFmpeg or set FFMPEG_BINARY to run encoding integration test.')
        for dimensions, expected in [('1920x1080', '854x480'), ('1080x1920', '480x854')]:
            with self.subTest(dimensions=dimensions):
                source = Path(self.directory.name) / 'source.mp4'
                subprocess.run([binary, '-nostdin', '-y', '-f', 'lavfi', '-i',
                                f'testsrc2=size={dimensions}:rate=30', '-f', 'lavfi', '-i',
                                'sine=frequency=440:sample_rate=44100', '-t', '2', '-c:v', 'libx264',
                                '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-threads', '2',
                                str(source)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                content = source.read_bytes()
                item = self.upload(content)
                self.assertTrue(generate_preview(item.pk))
                item.refresh_from_db()
                self.assertEqual(item.preview_status, 'ready')
                with item.video_raw.open('rb') as raw:
                    self.assertEqual(hashlib.sha256(raw.read()).digest(), hashlib.sha256(content).digest())
                self.assertLess(item.video_preview.size, len(content))
                metadata = subprocess.run([binary, '-i', item.video_preview.path, '-f', 'null', '-'],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True).stderr.decode()
                self.assertIn(expected, metadata)
                self.assertIn('Audio: aac', metadata)
                self.assertIn('Video: h264', metadata)
                name = item.video_preview.name
                self.assertFalse(generate_preview(item.pk))
                item.refresh_from_db()
                self.assertEqual(item.video_preview.name, name)
