"""Shared moderation actions and staff notifications."""
from datetime import timedelta
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import models, transaction
from django.utils import timezone

from .models import ModerationReport, Order

logger = logging.getLogger(__name__)


def create_report(*, reporter, target_type, target_id, reason, details=''):
    """Validate, snapshot and create one report from either web or mobile."""
    User = get_user_model()
    daily_limit = getattr(settings, 'MODERATION_REPORT_DAILY_LIMIT', 20)
    if not reporter.is_staff and ModerationReport.objects.filter(
        reporter=reporter,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).count() >= daily_limit:
        raise ValueError('You have reached the daily report limit. Contact support if there is an urgent safety issue.')
    if target_type == ModerationReport.TARGET_LISTING:
        target = Order.objects.select_related('user', 'product').filter(pk=target_id).first()
        if target is None:
            raise ValueError('Listing not found.')
        owner = target.user
        snapshot = {
            'listing_id': target.pk,
            'product_name': target.product.name,
            'description': target.description,
            'additional_comments': target.additional_comments,
            'owner_username': owner.username,
            'previous_status': target.status,
        }
    elif target_type == ModerationReport.TARGET_USER:
        target = User.objects.filter(pk=target_id).first()
        if target is None:
            raise ValueError('User not found.')
        owner = target
        snapshot = {'user_id': target.pk, 'username': target.username}
    elif target_type == ModerationReport.TARGET_MESSAGE:
        from transaction.models import TransactionMessage
        target = TransactionMessage.objects.select_related('user_from', 'transaction').filter(pk=target_id).first()
        if target is None:
            raise ValueError('Message not found.')
        if reporter.id not in (target.user_from_id, target.user_to_id):
            raise PermissionError('You can only report a message in one of your transactions.')
        owner = target.user_from
        snapshot = {
            'message_id': target.pk,
            'transaction_reference': target.transaction.transaction_reference if target.transaction else '',
            'description': target.description,
            'author_username': owner.username,
            'previously_hidden': target.moderation_hidden,
        }
    else:
        raise ValueError('Invalid report target.')

    if reason not in dict(ModerationReport.REASON_CHOICES):
        raise ValueError('Choose a valid report reason.')
    if owner.id == reporter.id:
        raise ValueError('You cannot report your own content or account.')
    if ModerationReport.objects.filter(
        reporter=reporter, target_type=target_type, target_id=target_id,
        status__in=(ModerationReport.STATUS_OPEN, ModerationReport.STATUS_REVIEWING),
    ).exists():
        raise ValueError('You already have an open report for this content.')

    hide_pending = (
        target_type in (ModerationReport.TARGET_LISTING, ModerationReport.TARGET_MESSAGE)
        and reason in ModerationReport.IMMEDIATE_HIDE_REASONS
    )
    report = ModerationReport.objects.create(
        reporter=reporter,
        target_owner=owner,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        details=(details or '').strip()[:1500],
        target_snapshot=snapshot,
        content_hidden_pending_review=hide_pending,
    )
    if hide_pending:
        if target_type == ModerationReport.TARGET_LISTING:
            Order.objects.filter(pk=target_id).update(status=Order.EXPIRED)
        else:
            from transaction.models import TransactionMessage
            TransactionMessage.objects.filter(pk=target_id).update(moderation_hidden=True)
    notify_staff_of_report(report)
    return report


def _staff_emails():
    emails = set(
        get_user_model().objects.filter(is_active=True, is_staff=True)
        .exclude(email='').values_list('email', flat=True)
    )
    emails.update(email for _, email in getattr(settings, 'ADMINS', ()) if email)
    return sorted(emails)


def notify_staff_of_report(report):
    """Best-effort staff notification; reporting must not fail if mail/Discord does."""
    subject = '[Rentalution] New moderation report #%s' % report.pk
    message = (
        'A member reported %s #%s.\n\nReason: %s\nReporter: %s\n'
        'Target owner: %s\n\nDetails:\n%s\n\nReview in Django admin: %s/site_cfg_admin/common/moderationreport/%s/change/'
    ) % (
        report.get_target_type_display().lower(), report.target_id,
        report.get_reason_display(), report.reporter.username,
        report.target_owner.username if report.target_owner else 'unknown',
        report.details or '(none)', settings.SITE_URL.rstrip('/'), report.pk,
    )
    recipients = _staff_emails()
    if recipients:
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        except Exception:
            logger.exception('Could not email staff about moderation report %s', report.pk)

    webhook_url = getattr(settings, 'DISCORD_MODERATION_WEBHOOK_URL', '')
    if webhook_url:
        try:
            requests.post(webhook_url, json={'content': '%s\n%s' % (subject, message)}, timeout=8).raise_for_status()
        except Exception:
            logger.exception('Could not send Discord moderation alert for report %s', report.pk)


def resolve_report(report, *, outcome, moderator, notes=''):
    """Apply one of the three audited moderator outcomes exactly once."""
    if report.status == ModerationReport.STATUS_RESOLVED:
        raise ValueError('This report has already been resolved.')
    if outcome not in dict(ModerationReport.OUTCOME_CHOICES):
        raise ValueError('Invalid moderation outcome.')

    with transaction.atomic():
        if outcome == ModerationReport.OUTCOME_REMOVE_AND_BLOCK:
            if report.target_type == ModerationReport.TARGET_LISTING:
                Order.objects.filter(pk=report.target_id).update(status=Order.EXPIRED)
            elif report.target_type == ModerationReport.TARGET_MESSAGE:
                from transaction.models import TransactionMessage
                TransactionMessage.objects.filter(pk=report.target_id).update(moderation_hidden=True)
            if report.target_owner_id:
                get_user_model().objects.filter(pk=report.target_owner_id).update(is_active=False)
        elif outcome == ModerationReport.OUTCOME_DISMISS_AND_BLOCK_REPORTER:
            get_user_model().objects.filter(pk=report.reporter_id).update(is_active=False)

        if outcome in (
            ModerationReport.OUTCOME_DISMISS,
            ModerationReport.OUTCOME_DISMISS_AND_BLOCK_REPORTER,
        ) and report.content_hidden_pending_review:
            other_blocking_report_exists = ModerationReport.objects.filter(
                target_type=report.target_type,
                target_id=report.target_id,
            ).exclude(pk=report.pk).filter(
                models.Q(status__in=(ModerationReport.STATUS_OPEN, ModerationReport.STATUS_REVIEWING), content_hidden_pending_review=True)
                | models.Q(status=ModerationReport.STATUS_RESOLVED, outcome=ModerationReport.OUTCOME_REMOVE_AND_BLOCK)
            ).exists()
            if other_blocking_report_exists:
                report.status = ModerationReport.STATUS_RESOLVED
                report.outcome = outcome
                report.moderator_notes = notes.strip()
                report.reviewed_by = moderator
                report.reviewed_at = timezone.now()
                report.save(update_fields=('status', 'outcome', 'moderator_notes', 'reviewed_by', 'reviewed_at', 'updated_at'))
                return report
            if report.target_type == ModerationReport.TARGET_LISTING:
                previous_status = report.target_snapshot.get('previous_status', Order.ACTIVE)
                Order.objects.filter(pk=report.target_id).update(status=previous_status)
            elif report.target_type == ModerationReport.TARGET_MESSAGE:
                from transaction.models import TransactionMessage
                TransactionMessage.objects.filter(pk=report.target_id).update(
                    moderation_hidden=bool(report.target_snapshot.get('previously_hidden', False))
                )

        report.status = ModerationReport.STATUS_RESOLVED
        report.outcome = outcome
        report.moderator_notes = notes.strip()
        report.reviewed_by = moderator
        report.reviewed_at = timezone.now()
        report.save(update_fields=('status', 'outcome', 'moderator_notes', 'reviewed_by', 'reviewed_at', 'updated_at'))
    return report
