from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from common.models import Category, Product
from transaction.models import DisputeCase, Transaction, TransactionMessageImage
from transaction.tasks import (
    archive_expired_condition_media,
    delete_expired_archived_condition_media,
    restore_archived_condition_media,
)


class ConditionMediaRetentionTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.overrides = override_settings(
            MEDIA_ROOT=self.directory.name,
            CONDITION_MEDIA_ARCHIVE_ROOT=f'{self.directory.name}/archive',
        )
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.lender = User.objects.create_user('media-lender')
        self.borrower = User.objects.create_user('media-borrower')
        category = Category.objects.create(title='Retention test category')
        self.product = Product.objects.create(
            category_id=category,
            name='Retention test product',
        )

    def _transaction(self, status=Transaction.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK):
        return Transaction.objects.create(
            user_passive=self.lender,
            user_aggressive=self.borrower,
            transaction_status=status,
            prev_transaction_status=Transaction.RENTAL_ONGOING,
            rental_start_date=timezone.localdate() - timedelta(days=100),
            rental_end_date=timezone.localdate() - timedelta(days=95),
            product=self.product,
            price=10,
            current_spot_value=10,
            price_as_pct_spot_value=100,
        )

    def _evidence(self, transaction):
        upload = SimpleUploadedFile('condition.mp4', b'condition-video', content_type='video/mp4')
        evidence = TransactionMessageImage.objects.create(
            transaction=transaction,
            user=self.lender,
            video=upload,
            video_raw=upload,
            evidence_stage='checkout_lender',
            active=True,
        )
        TransactionMessageImage.objects.filter(pk=evidence.pk).update(
            uploaded_at=timezone.now() - timedelta(days=91),
        )
        evidence.refresh_from_db()
        return evidence

    def test_archives_old_undisputed_completed_evidence_and_clears_its_url(self):
        transaction = self._transaction()
        evidence = self._evidence(transaction)
        transaction.checkout_condition_video_url = evidence.video.url
        transaction.save(update_fields=['checkout_condition_video_url', 'amended'])
        path = Path(evidence.video.path)

        result = archive_expired_condition_media()

        self.assertEqual(result['archived'], 1)
        self.assertTrue(TransactionMessageImage.objects.filter(pk=evidence.pk).exists())
        self.assertFalse(path.exists())
        transaction.refresh_from_db()
        self.assertEqual(transaction.checkout_condition_video_url, '')
        evidence.refresh_from_db()
        self.assertFalse(evidence.active)
        self.assertTrue(evidence.archived_at)
        self.assertTrue(Path(self.directory.name, 'archive', evidence.archive_manifest['files']['video']).exists())

    def test_archived_evidence_can_be_restored_before_permanent_deletion(self):
        transaction = self._transaction()
        evidence = self._evidence(transaction)
        transaction.checkout_condition_video_url = evidence.video.url
        transaction.save(update_fields=['checkout_condition_video_url', 'amended'])

        archive_expired_condition_media()
        evidence.refresh_from_db()
        self.assertTrue(restore_archived_condition_media(evidence))

        evidence.refresh_from_db()
        transaction.refresh_from_db()
        self.assertTrue(evidence.active)
        self.assertFalse(evidence.archived_at)
        self.assertTrue(Path(evidence.video.path).exists())
        self.assertTrue(transaction.checkout_condition_video_url)

    def test_permanently_deletes_after_archive_grace_period(self):
        transaction = self._transaction()
        evidence = self._evidence(transaction)
        archive_expired_condition_media()
        evidence.refresh_from_db()
        archive_file = Path(self.directory.name, 'archive', evidence.archive_manifest['files']['video'])
        TransactionMessageImage.objects.filter(pk=evidence.pk).update(
            archive_expires_at=timezone.now() - timedelta(seconds=1),
        )

        result = delete_expired_archived_condition_media()

        self.assertEqual(result['deleted'], 1)
        self.assertFalse(TransactionMessageImage.objects.filter(pk=evidence.pk).exists())
        self.assertFalse(archive_file.exists())

    def test_keeps_old_evidence_when_the_transaction_has_a_dispute(self):
        transaction = self._transaction()
        evidence = self._evidence(transaction)
        DisputeCase.objects.create(transaction=transaction)

        result = archive_expired_condition_media()

        self.assertEqual(result['archived'], 0)
        self.assertTrue(TransactionMessageImage.objects.filter(pk=evidence.pk).exists())
        self.assertTrue(Path(evidence.video.path).exists())

    def test_keeps_evidence_for_an_active_rental(self):
        transaction = self._transaction(status=Transaction.RENTAL_ONGOING)
        evidence = self._evidence(transaction)

        result = archive_expired_condition_media()

        self.assertEqual(result['archived'], 0)
        self.assertTrue(TransactionMessageImage.objects.filter(pk=evidence.pk).exists())
