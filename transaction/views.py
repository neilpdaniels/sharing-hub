# Standard library
import json
import hashlib
import logging
import random
from datetime import datetime, timedelta, time as dt_time
from operator import attrgetter
from urllib.parse import quote
from zoneinfo import ZoneInfo

# Django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db import models
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# Local apps
from account.models import PaymentMethod, Profile
from common.decorators import ajax_required
from common.helpers import is_profile_kyc_verified
from common.models import Category, Order, OrderBlockedDate, OrderImage, Product, TransactionFee
from common.security import verify_turnstile_token
from common.failures import record_site_failure
from .forms import (
    LetPriceBandFormSet,
    OrderAddForm,
    OrderExpireForm,
    OrderImageForm,
    RentalEnquiryForm,
    TransactionMessageAddForm,
    TransactionMessageImageForm,
)
from .helpers import (
    get_transaction_pricing,
    get_user_feedback_breakdown_map,
    getTransactionStepAndAction,
    returnFeeValue,
    sync_transaction_fee_charges,
    sync_transaction_pricing,
)
from .models import (
    DisputeCase,
    PaymentAttempt,
    Transaction,
    TransactionFeedback,
    TransactionImage,
    TransactionMessage,
    TransactionMessageImage,
)
from .stripe_connect import stripe_connect_service
from .tasks import (
    async_collect_deposit_hold,
    async_confirm_card_setup,
    async_resolve_deposit_hold,
    async_setup_deposit_card_and_test_hold,
)




def _generate_txn_pin(length=6):
    digits = '0123456789'
    return ''.join(digits[random.randrange(0, 10)] for _ in range(length))


def _iter_rental_dates(start_date, end_date):
    if not start_date or not end_date:
        return
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def _holding_statuses():
    return (
        Transaction.RENTAL_ENQUIRY,
        Transaction.RENTAL_AGREED,
        Transaction.RENTAL_DAY_AWAITING_VERIFICATION,
        Transaction.RENTAL_ONGOING,
        Transaction.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        Transaction.RENTAL_RETURNED_DEPOSIT_PENDING,
        Transaction.RENTAL_RETURNED_DEPOSIT_RETURNED,
        Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED,
        Transaction.AWAITING_FEEDBACK,
        Transaction.FEEDBACK_ONE_SIDED,
    )


def _reserve_transaction_dates(txn):
    if not txn.order_passive_id:
        return
    for date_value in _iter_rental_dates(txn.rental_start_date, txn.rental_end_date):
        OrderBlockedDate.objects.get_or_create(
            order_id=txn.order_passive_id,
            date=date_value,
            defaults={'reason': OrderBlockedDate.BOOKED},
        )


def _release_transaction_dates(txn):
    if not txn.order_passive_id:
        return

    active_holds = Transaction.objects.filter(
        order_passive_id=txn.order_passive_id,
        transaction_status__in=_holding_statuses(),
    ).exclude(id=txn.id)

    for date_value in _iter_rental_dates(txn.rental_start_date, txn.rental_end_date):
        held_elsewhere = active_holds.filter(
            rental_start_date__lte=date_value,
            rental_end_date__gte=date_value,
        ).exists()
        if not held_elsewhere:
            OrderBlockedDate.objects.filter(
                order_id=txn.order_passive_id,
                date=date_value,
                reason=OrderBlockedDate.BOOKED,
            ).delete()


def _friendly_message_title(message):
    transaction = message.transaction
    product_name = ''
    if transaction and transaction.order_passive and transaction.order_passive.product:
        product_name = transaction.order_passive.product.name

    rental_window = ''
    if transaction:
        start = transaction.rental_start_date
        end = transaction.rental_end_date
        if start and end:
            rental_window = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"
        elif start:
            rental_window = f"from {start.strftime('%d %b %Y')}"
        elif end:
            rental_window = f"until {end.strftime('%d %b %Y')}"

    if product_name and rental_window:
        return f"Rental: {product_name} ({rental_window})"
    if product_name:
        return f"Rental: {product_name}"
    if rental_window:
        return f"Rental ({rental_window})"
    return (message.subject or 'Message').strip() or 'Message'


def _message_preview_text(message, max_lines=2, max_chars=180):
    body = (message.description or '').strip()
    if not body:
        return ''
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    preview = ' '.join(lines[:max_lines]) if lines else body
    preview = ' '.join(preview.split())
    if len(preview) > max_chars:
        preview = preview[:max_chars].rsplit(' ', 1)[0].rstrip() + '...'
    return preview


def _message_alignment_class(message, user):
    if message.is_system_generated:
        return 'message-card--center'
    if message.user_from_id == user.id:
        return 'message-card--outgoing'
    if message.user_to_id == user.id:
        return 'message-card--incoming'
    return 'message-card--center'


def _message_order_thumbnail_url(message):
    transaction = message.transaction
    if not transaction or not transaction.order_passive:
        return ''

    order = transaction.order_passive
    order_images = list(order.images.all())
    if order_images:
        preferred = next((img for img in order_images if img.is_main and img.active), None)
        if not preferred:
            preferred = next((img for img in order_images if img.first_image and img.active), None)
        if not preferred:
            preferred = next((img for img in order_images if img.active), None)
        if not preferred:
            preferred = order_images[0]
        return preferred.image.url if preferred and preferred.image else ''

    if order.product and order.product.image:
        return order.product.image.url
    return ''


def _require_mobile_verification(request):
    if not getattr(settings, 'MOBILE_VERIFICATION_ENABLED', True):
        return None

    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, 'Please complete your profile before continuing.')
        return redirect(reverse('edit'))
    if profile.mobile_verified:
        return None
    verify_url = reverse('mobile_verify')
    next_url = request.get_full_path()
    messages.warning(request, 'Please verify your mobile number before placing a listing or sending an enquiry.')
    return redirect(f'{verify_url}?next={quote(next_url)}')


def _infer_uploader_role(txn, user):
    if user == txn.user_passive:
        return TransactionMessageImage.ROLE_LENDER
    if user == txn.user_aggressive:
        return TransactionMessageImage.ROLE_BORROWER
    return TransactionMessageImage.ROLE_SYSTEM


def _capture_device_from_request(request):
    return (request.POST.get('capture_device') or request.META.get('HTTP_USER_AGENT') or '')[:120]


def _checksum_for_uploaded_file(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return digest.hexdigest()


def _captured_at_from_request(request):
    raw_value = (request.POST.get('captured_at') or '').strip()
    if not raw_value:
        return timezone.now()
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return timezone.now()

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _save_transaction_evidence(request, txn, *, evidence_stage, video_file_field, video_url_field):
    uploader_role = _infer_uploader_role(txn, request.user)
    capture_device = _capture_device_from_request(request)
    captured_at = _captured_at_from_request(request)

    uploaded_video = request.FILES.get(video_file_field)
    if uploaded_video:
        evidence = TransactionMessageImage(
            txn_message=None,
            user=request.user,
            video=uploaded_video,
            video_raw=uploaded_video,
            first_image=False,
            active=True,
            captured_at=captured_at,
            capture_device=capture_device,
            checksum_sha256=_checksum_for_uploaded_file(uploaded_video),
            uploader_role=uploader_role,
            evidence_stage=evidence_stage,
        )
        evidence.full_clean()
        evidence.save()
        return evidence.video.url

    external_url = (request.POST.get(video_url_field) or '').strip()
    if external_url:
        evidence = TransactionMessageImage(
            txn_message=None,
            user=request.user,
            first_image=False,
            active=True,
            captured_at=captured_at,
            capture_device=capture_device,
            checksum_sha256=hashlib.sha256(external_url.encode('utf-8')).hexdigest(),
            uploader_role=uploader_role,
            evidence_stage=evidence_stage,
            external_video_url=external_url,
        )
        evidence.full_clean()
        evidence.save()
        return external_url

    return ''


def _build_transaction_live_state(txn):
    latest_message = txn.transactionmessage_set.order_by('-created').values('id', 'created').first()
    latest_msg_id = latest_message['id'] if latest_message else 0
    latest_msg_ts = latest_message['created'].isoformat() if latest_message and latest_message['created'] else ''
    message_count = txn.transactionmessage_set.count()

    signature_parts = [
        str(txn.id),
        txn.transaction_status or '',
        txn.payment_status or '',
        txn.deposit_status or '',
        txn.product_status or '',
        txn.amended.isoformat() if txn.amended else '',
        str(message_count),
        str(latest_msg_id),
        latest_msg_ts,
        txn.checkout_handover_pin or '',
        txn.return_handover_pin or '',
        str(getattr(txn, 'deposit_proposal_iteration_count', 0) or 0),
    ]

    return {
        'state_signature': '|'.join(signature_parts),
        'message_count': message_count,
        'latest_message_id': latest_msg_id,
        'transaction_status': txn.transaction_status,
        'updated_at': txn.amended.isoformat() if txn.amended else '',
    }


def _dispute_case_reason_from_transaction(txn):
    summary = (txn.deposit_resolution_notes or '').lower()
    if '[missing_rental_voided]' in summary:
        return DisputeCase.REASON_MISSING_RENTAL
    if 'missing return' in summary:
        return DisputeCase.REASON_MISSING_RETURN
    if 'deposit' in summary:
        return DisputeCase.REASON_DEPOSIT_CONTEST
    return DisputeCase.REASON_DISPUTE_TEAM


def _ensure_dispute_case(txn):
    case, _ = DisputeCase.objects.get_or_create(
        transaction=txn,
        reason_code=_dispute_case_reason_from_transaction(txn),
        defaults={
            'raised_by': txn.transaction_status_raised_by,
            'summary': (txn.deposit_resolution_notes or '').strip() or f'Dispute opened for {txn.transaction_reference}.',
            'evidence_bundle': {
                'transaction_reference': txn.transaction_reference,
                'transaction_status': txn.transaction_status,
                'deposit_status': txn.deposit_status,
                'notes': (txn.deposit_resolution_notes or '').strip(),
            },
        },
    )
    return case


def _apply_dispute_outcome(case, *, outcome, status, resolution_notes, resolved_by, owner=None):
    case.outcome = outcome
    case.status = status
    case.resolution_notes = resolution_notes
    case.resolved_by = resolved_by
    case.resolved_at = timezone.now()
    case.closed_at = timezone.now() if status in (DisputeCase.STATUS_RESOLVED, DisputeCase.STATUS_CLOSED) else None
    if owner is not None:
        case.owner = owner
    case.save(update_fields=[
        'outcome',
        'status',
        'resolution_notes',
        'resolved_by',
        'resolved_at',
        'closed_at',
        'owner',
        'amended',
    ])
    return case


def _can_submit_dispute_final_statement(txn, user):
    case = txn.dispute_cases.order_by('-created').first()
    if case is None:
        return None
    if case.status not in {DisputeCase.STATUS_OPEN, DisputeCase.STATUS_NEEDS_INFO, DisputeCase.STATUS_UNDER_REVIEW, DisputeCase.STATUS_ESCALATED}:
        return None
    if user == txn.user_passive and not case.lender_final_statement_at:
        return case
    if user == txn.user_aggressive and not case.borrower_final_statement_at:
        return case
    return None


def _dispute_final_statement_deadline(case):
    if case is None or not case.created:
        return None
    return case.created + timedelta(hours=24)


@staff_member_required
def dispute_case_review(request, case_number):
    case = get_object_or_404(
        DisputeCase.objects.select_related(
            'transaction',
            'transaction__user_passive',
            'transaction__user_aggressive',
            'raised_by',
            'owner',
            'resolved_by',
        ),
        case_number=case_number,
    )

    txn = case.transaction
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        internal_notes = (request.POST.get('internal_resolution_notes') or '').strip()
        external_notes = (request.POST.get('external_resolution_notes') or '').strip()
        owner_id = request.POST.get('owner_id') or ''
        deposit_return_amount_raw = (request.POST.get('deposit_return_amount') or '').strip()
        resolution_decision = (request.POST.get('resolution_decision') or '').strip()
        owner = None
        if owner_id:
            owner = get_object_or_404(User, id=owner_id, is_staff=True)

        if internal_notes:
            case.internal_resolution_notes = internal_notes
        if external_notes:
            case.external_resolution_notes = external_notes

        if action == 'mark_under_review':
            case.status = DisputeCase.STATUS_UNDER_REVIEW
            if owner is not None:
                case.owner = owner
            update_fields = ['status', 'owner', 'amended']
            if internal_notes:
                update_fields.append('internal_resolution_notes')
            if external_notes:
                update_fields.append('external_resolution_notes')
            case.save(update_fields=update_fields)
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_passive,
                transaction=txn,
                subject=f'Dispute under review {txn.transaction_reference}',
                description='Your dispute has been accepted for review by the dispute team. Please keep evidence and messages on-platform.',
                include_admin=True,
                is_system_generated=True,
            )
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Dispute under review {txn.transaction_reference}',
                description='Your dispute has been accepted for review by the dispute team. Please keep evidence and messages on-platform.',
                include_admin=True,
                is_system_generated=True,
            )
            messages.success(request, 'Dispute marked as under review.')
            return redirect('transaction:dispute_case_review', case_number=case.case_number)

        if action == 'submit_final_statement':
            statement = (request.POST.get('final_statement') or '').strip()
            statement_amount = (request.POST.get('requested_amount') or '').strip()
            try:
                requested_amount = max(0.0, round(float(statement_amount or 0), 2))
            except ValueError:
                requested_amount = 0.0
            deadline = _dispute_final_statement_deadline(case)
            if deadline and timezone.now() > deadline:
                messages.error(request, 'The 24-hour dispute statement window has closed.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)
            if request.user == txn.user_passive:
                if case.lender_final_statement_at:
                    messages.error(request, 'Lender final statement has already been submitted.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)
                case.lender_final_statement_at = timezone.now()
                side_label = 'Lender'
            elif request.user == txn.user_aggressive:
                if case.borrower_final_statement_at:
                    messages.error(request, 'Borrower final statement has already been submitted.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)
                case.borrower_final_statement_at = timezone.now()
                side_label = 'Borrower'
            else:
                messages.error(request, 'Only the lender or borrower can submit a final statement.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not statement:
                messages.error(request, 'Please add your final statement before submitting.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            statement_text = (
                f'{side_label} final dispute statement\n'
                f'Requested amount: £{requested_amount:.2f}\n\n'
                f'{statement}'
            )
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=request.user,
                transaction=txn,
                subject=f'Final dispute statement {txn.transaction_reference}',
                description=statement_text,
                include_admin=True,
                private_to_sender=True,
                is_system_generated=False,
            )
            case.save(update_fields=[
                'lender_final_statement_at',
                'borrower_final_statement_at',
                'amended',
            ])
            messages.success(request, 'Final statement submitted to admin.')
            return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

        if action in {'resolve_lender', 'resolve_borrower', 'resolve_split', 'resolve_void', 'resolve_refund', 'resolve_other', 'mark_under_review'} or resolution_decision:
            previous_status = txn.transaction_status
            outcome_map = {
                'resolve_lender': DisputeCase.OUTCOME_LENDER,
                'resolve_borrower': DisputeCase.OUTCOME_BORROWER,
                'resolve_split': DisputeCase.OUTCOME_SPLIT,
                'resolve_void': DisputeCase.OUTCOME_VOID,
                'resolve_refund': DisputeCase.OUTCOME_REFUND,
                'resolve_other': DisputeCase.OUTCOME_OTHER,
                'lender': DisputeCase.OUTCOME_LENDER,
                'borrower': DisputeCase.OUTCOME_BORROWER,
                'split': DisputeCase.OUTCOME_SPLIT,
                'void': DisputeCase.OUTCOME_VOID,
                'refund': DisputeCase.OUTCOME_REFUND,
                'other': DisputeCase.OUTCOME_OTHER,
            }
            decision_key = resolution_decision or action
            if decision_key == 'mark_under_review':
                case.status = DisputeCase.STATUS_UNDER_REVIEW
                update_fields = ['status', 'resolution_notes', 'amended']
                case.resolution_notes = external_notes or internal_notes or case.resolution_notes
                if owner is not None:
                    case.owner = owner
                    update_fields.append('owner')
                if internal_notes:
                    update_fields.append('internal_resolution_notes')
                if external_notes:
                    update_fields.append('external_resolution_notes')
                case.save(update_fields=update_fields)
                messages.success(request, 'Dispute marked as under review.')
                return redirect('transaction:dispute_case_review', case_number=case.case_number)

            outcome = outcome_map.get(decision_key, DisputeCase.OUTCOME_OTHER)
            case = _apply_dispute_outcome(
                case,
                outcome=outcome,
                status=DisputeCase.STATUS_RESOLVED,
                resolution_notes=external_notes or case.external_resolution_notes or case.internal_resolution_notes or case.resolution_notes,
                resolved_by=request.user,
                owner=owner or case.owner,
            )

            try:
                deposit_return_amount = max(0.0, float(deposit_return_amount_raw or 0))
            except ValueError:
                deposit_return_amount = 0.0

            lender_share_ratio = max(0.0, min(100.0, float(request.POST.get('settlement_ratio') or 50))) / 100.0
            borrower_share_ratio = 1.0 - lender_share_ratio

            if outcome in (DisputeCase.OUTCOME_LENDER, DisputeCase.OUTCOME_SPLIT, DisputeCase.OUTCOME_REFUND):
                txn.deposit_status = txn.DEPOSIT_RETURNED_FULL if deposit_return_amount >= (txn.deposit or 0) else txn.DEPOSIT_RETURNED_REDUCED
                txn.transaction_status = txn.DISPUTE_DECIDED
            elif outcome in (DisputeCase.OUTCOME_BORROWER, DisputeCase.OUTCOME_VOID):
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.transaction_status = txn.DISPUTE_DECIDED
                deposit_return_amount = 0.0
            else:
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.transaction_status = txn.DISPUTE_DECIDED

            settlement_notes = txn.deposit_resolution_notes
            if external_notes:
                settlement_notes = f'{settlement_notes}\n\nExternal resolution notes:\n{external_notes}'.strip()
            if internal_notes:
                settlement_notes = f'{settlement_notes}\n\nInternal resolution notes:\n{internal_notes}'.strip()
            txn.deposit_resolution_notes = settlement_notes
            txn.transaction_status_raised_by = request.user
            txn.prev_transaction_status = previous_status
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'deposit_status',
                'deposit_resolution_notes',
                'transaction_status_raised_by',
                'amended',
            ])

            case.deposit_return_amount = deposit_return_amount
            case.payment_offset_amount = 0
            case.save(update_fields=['deposit_return_amount', 'payment_offset_amount', 'amended'])

            if deposit_return_amount > 0:
                async_resolve_deposit_hold.delay(
                    transaction_id=txn.id,
                    return_amount=deposit_return_amount,
                )

            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_passive,
                transaction=txn,
                subject=f'Dispute resolved {txn.transaction_reference}',
                description=(
                    f'The dispute team has resolved this case. Outcome: {case.get_outcome_display()}. '
                    f'Deposit return: £{deposit_return_amount:.2f}. '
                    f'Transaction closed. Notes: {external_notes or case.external_resolution_notes or case.internal_resolution_notes or "See dispute record."}'
                ),
                include_admin=True,
                is_system_generated=True,
            )
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Dispute resolved {txn.transaction_reference}',
                description=(
                    f'The dispute team has resolved this case. Outcome: {case.get_outcome_display()}. '
                    f'Deposit return: £{deposit_return_amount:.2f}. '
                    f'Transaction closed. Notes: {external_notes or case.external_resolution_notes or case.internal_resolution_notes or "See dispute record."}'
                ),
                include_admin=True,
                is_system_generated=True,
            )
            messages.success(request, 'Dispute resolved and users notified.')
            return redirect('transaction:dispute_case_review', case_number=case.case_number)

    context = {
        'case': case,
        'transaction': txn,
        'evidence_bundle': case.evidence_bundle or {},
        'staff_users': User.objects.filter(is_staff=True).order_by('username'),
        'resolution_choices': [
            ('under_review', 'Mark under review'),
            ('lender', 'In favour of lender'),
            ('borrower', 'In favour of borrower'),
            ('split', 'Split outcome'),
            ('void', 'Void / no payout'),
            ('refund', 'Refund / release'),
            ('other', 'Other outcome'),
        ],
    }
    return render(request, 'transaction/dispute_case_review.html', context)


@staff_member_required
def admin_transaction_browser(request):
    transactions = Transaction.objects.select_related(
        'user_passive',
        'user_aggressive',
        'order_passive',
        'transaction_status_raised_by',
    ).order_by('-amended', '-created')[:200]
    dispute_transactions = Transaction.objects.select_related(
        'user_passive',
        'user_aggressive',
        'order_passive',
    ).filter(
        models.Q(transaction_status=Transaction.DISPUTE_REQUESTED)
        | models.Q(deposit_status=Transaction.DEPOSIT_MEDIATION)
        | models.Q(transaction_status=Transaction.RENTAL_RETURNED_DEPOSIT_CONTESTED)
    ).order_by('-amended', '-created')[:100]
    dispute_cases = DisputeCase.objects.select_related(
        'transaction',
        'transaction__user_passive',
        'transaction__user_aggressive',
        'owner',
        'raised_by',
    ).order_by('-amended', '-created')[:100]

    case_map = {case.transaction_id: case for case in dispute_cases}
    for txn in dispute_transactions:
        if txn.id not in case_map:
            case = _ensure_dispute_case(txn)
            if case is not None:
                case_map[txn.id] = case
    dispute_cases = sorted(case_map.values(), key=lambda case: case.amended or case.created, reverse=True)

    if request.method == 'POST':
        transaction_reference = (request.POST.get('transaction_reference') or '').strip()
        new_status = (request.POST.get('new_status') or '').strip()
        note = (request.POST.get('note') or '').strip()
        txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)

        valid_statuses = {choice[0] for choice in Transaction.TRANSACTION_STATUS_CHOICES}
        if new_status not in valid_statuses:
            messages.error(request, 'Choose a valid transaction status.')
        else:
            previous_status = txn.transaction_status
            previous_label = txn.get_transaction_status_display()
            txn.prev_transaction_status = previous_status
            txn.transaction_status = new_status
            txn.transaction_status_raised_by = request.user
            if note:
                txn.deposit_resolution_notes = (
                    f'{txn.deposit_resolution_notes}\n[ADMIN_STATE_CHANGE] {note}'
                ).strip()
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'transaction_status_raised_by',
                'deposit_resolution_notes',
                'amended',
            ])
            if txn.transaction_status in {Transaction.DISPUTE_REQUESTED, Transaction.CANCEL_ACCEPTED} or txn.deposit_status == txn.DEPOSIT_MEDIATION:
                _ensure_dispute_case(txn)
            messages.success(
                request,
                f'Transaction {txn.transaction_reference} moved from '
                f'{previous_label} to {txn.get_transaction_status_display()}.'
            )
        return redirect('transaction:admin_transaction_browser')

    context = {
        'transactions': transactions,
        'dispute_cases': dispute_cases,
        'transaction_status_choices': Transaction.TRANSACTION_STATUS_CHOICES,
    }
    return render(request, 'transaction/admin_transaction_browser.html', context)


class OrderFormHandler:
    @staticmethod
    def apply_common_order_fields(order, user, product=None):
        order.user = user
        if product is not None:
            order.product = product
        order.direction = Order.TO_LET
        order.quantity = 1
        order.status = Order.ACTIVE
        return order

    @staticmethod
    def set_order_expiry(order, expiry_date):
        order.expiry_date = datetime.combine(expiry_date, dt_time(23, 59, 59))

    @staticmethod
    def save_order_and_bands(order_form, band_formset, user, product=None):
        order = order_form.save(commit=False)
        OrderFormHandler.apply_common_order_fields(order, user, product=product)
        OrderFormHandler.set_order_expiry(order, order_form.cleaned_data['expiry_date'])
        order.save()

        band_formset.instance = order
        band_formset.save()
        return order

    @staticmethod
    def sync_blocked_dates(order, blocked_raw, blocked_handover_raw, clear_existing=False):
        if clear_existing:
            OrderBlockedDate.objects.filter(
                order=order,
                reason__in=[OrderBlockedDate.MANUAL, OrderBlockedDate.HANDOVER_UNAVAILABLE],
            ).delete()

        for ds in (blocked_raw or '').split(','):
            ds = ds.strip()
            if not ds:
                continue
            try:
                date_value = datetime.fromisoformat(ds).date()
            except ValueError:
                continue
            OrderBlockedDate.objects.get_or_create(
                order=order,
                date=date_value,
                defaults={'reason': OrderBlockedDate.MANUAL},
            )

        for ds in (blocked_handover_raw or '').split(','):
            ds = ds.strip()
            if not ds:
                continue
            try:
                date_value = datetime.fromisoformat(ds).date()
            except ValueError:
                continue
            if OrderBlockedDate.objects.filter(
                order=order,
                date=date_value,
                reason=OrderBlockedDate.BOOKED,
            ).exists():
                continue
            if OrderBlockedDate.objects.filter(
                order=order,
                date=date_value,
                reason=OrderBlockedDate.MANUAL,
            ).exists():
                continue
            OrderBlockedDate.objects.get_or_create(
                order=order,
                date=date_value,
                defaults={'reason': OrderBlockedDate.HANDOVER_UNAVAILABLE},
            )

    @staticmethod
    def sync_add_images(order, request):
        order_image_ids = request.POST.get('order_image_id', '').split()
        main_image_id = request.POST.get('main_image_id', '').strip()
        count = len(order.images.filter(active=True))

        for order_image_id in order_image_ids:
            try:
                order_image = OrderImage.objects.get(pk=order_image_id)
            except OrderImage.DoesNotExist as exc:
                raise Http404('OrderImage does not exist') from exc

            if request.user != order_image.user:
                continue
            if count >= 5:
                continue

            order_image.order = order
            order_image.is_main = str(order_image_id) == main_image_id
            order_image.saveNoImageModification()
            count += 1

        if not main_image_id:
            first = order.images.filter(active=True).first()
            if first:
                first.is_main = True
                first.saveNoImageModification()

    @staticmethod
    def sync_edit_images(order, request):
        selected_ids = []
        for oid in request.POST.get('order_image_id', '').split():
            if oid not in selected_ids:
                selected_ids.append(oid)
        selected_ids = selected_ids[:5]
        main_image_id = request.POST.get('main_image_id', '').strip()

        for img in order.images.filter(active=True):
            if str(img.id) not in selected_ids:
                img.active = False
                img.is_main = False
                img.saveNoImageModification()

        for order_image_id in selected_ids:
            try:
                order_image = OrderImage.objects.get(pk=order_image_id)
            except OrderImage.DoesNotExist as exc:
                raise Http404('OrderImage does not exist') from exc

            if request.user != order_image.user:
                continue

            order_image.order = order
            order_image.active = True
            order_image.is_main = str(order_image_id) == main_image_id
            order_image.saveNoImageModification()

        if not main_image_id:
            first = order.images.filter(active=True).first()
            if first:
                first.is_main = True
                first.saveNoImageModification()

    @staticmethod
    def build_edit_order_context(order):
        order_images = list(order.images.filter(active=True))
        order_image_ids_str = ' '.join(str(img.id) for img in order_images)
        main_image = next((img for img in order_images if img.is_main), None)
        if not main_image and order_images:
            main_image = order_images[0]

        manual_blocked_dates = [
            bd.date.isoformat()
            for bd in order.blocked_dates.filter(reason=OrderBlockedDate.MANUAL)
        ]
        booked_dates = [
            bd.date.isoformat()
            for bd in order.blocked_dates.filter(reason=OrderBlockedDate.BOOKED)
        ]
        blocked_handover_dates = [
            bd.date.isoformat()
            for bd in order.blocked_dates.filter(reason=OrderBlockedDate.HANDOVER_UNAVAILABLE)
        ]

        return {
            'existing_order_images': order_images,
            'order_image_ids_str': order_image_ids_str,
            'main_image_id': str(main_image.id) if main_image else '',
            'blocked_dates_json': json.dumps(manual_blocked_dates),
            'booked_dates_json': json.dumps(booked_dates),
            'blocked_handover_dates_json': json.dumps(blocked_handover_dates),
        }





@login_required
def list_item(request):
    """Step 1: search for the product you want to list, then continue to add_order."""
    try:
        root = Category.objects.get(parent_category__isnull=True)
        categories = Category.objects.filter(parent_category=root).order_by('title')
    except Category.DoesNotExist:
        categories = Category.objects.none()
    return render(request, 'transaction/list_item.html', {'categories': categories})


@login_required
def product_search_ajax(request):
    """AJAX: search products by name, optionally filtered by category."""
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    qs = Product.objects.select_related('category_id').order_by('name')
    if q:
        qs = qs.filter(name__icontains=q)
    if category_id:
        try:
            # include the chosen category AND all its children
            cat_ids = list(
                Category.objects.filter(
                    pk=int(category_id)
                ).values_list('pk', flat=True)
            ) + list(
                Category.objects.filter(
                    parent_category_id=int(category_id)
                ).values_list('pk', flat=True)
            )
            qs = qs.filter(category_id__in=cat_ids)
        except (ValueError, TypeError):
            pass

    results = [
        {
            'id': p.id,
            'name': p.name,
            'category': p.category_id.title if p.category_id else '',
            'category_id': p.category_id.id if p.category_id else None,
            'image_url': p.image.url if p.image else None,
        }
        for p in qs[:24]
    ]
    return JsonResponse({'results': results})


@login_required
def add_order(request, product_id=None):
    verify_redirect = _require_mobile_verification(request)
    if verify_redirect is not None:
        return verify_redirect

    product = None
    order = Order()
    order_image_form = None

    # submitted
    if request.method == 'POST':
        product = get_object_or_404(Product, id=request.POST['product_id'])

        order_form = OrderAddForm(data=request.POST, files=request.FILES, instance=order)
        band_formset = LetPriceBandFormSet(data=request.POST, instance=order)

        if order_form.is_valid() and band_formset.is_valid():
            order = OrderFormHandler.save_order_and_bands(
                order_form,
                band_formset,
                request.user,
                product=product,
            )
            OrderFormHandler.sync_blocked_dates(
                order,
                request.POST.get('blocked_dates', ''),
                request.POST.get('blocked_handover_dates', ''),
                clear_existing=False,
            )
            OrderFormHandler.sync_add_images(order, request)

            messages.success(request, 'Your listing has been added')
            product_url = request.build_absolute_uri(
                reverse('navigation:productPage', kwargs={'product_slug': product.slug})
            )
            return redirect(product_url)
    else:
        product = get_object_or_404(Product, id=product_id)
        order_form = OrderAddForm(instance=order)
        band_formset = LetPriceBandFormSet(instance=order)
        order_image_form = OrderImageForm(instance=order)

    context = {
        'order_form': order_form,
        'band_formset': band_formset,
        'order_image_form': order_image_form,
        'product': product,
        'blocked_dates_json': '[]',
        'booked_dates_json': '[]',
        'blocked_handover_dates_json': '[]',
    }
    return render(request, 'transaction/add_order.html', context)


@login_required
def edit_order(request, order_id=None):
    order = get_object_or_404(Order, id=order_id)
    if request.user != order.user:
        messages.error(request, 'Incorrect user credentials')
        return redirect('/')

    order_image_form = None

    if request.method == 'POST':
        order_form = OrderAddForm(data=request.POST, files=request.FILES, instance=order)
        band_formset = LetPriceBandFormSet(data=request.POST, instance=order)

        if order_form.is_valid() and band_formset.is_valid():
            order = OrderFormHandler.save_order_and_bands(
                order_form,
                band_formset,
                request.user,
            )
            OrderFormHandler.sync_blocked_dates(
                order,
                request.POST.get('blocked_dates', ''),
                request.POST.get('blocked_handover_dates', ''),
                clear_existing=True,
            )
            OrderFormHandler.sync_edit_images(order, request)

            messages.success(request, 'Order updated')
            product_url = request.build_absolute_uri(
                reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})
            )
            return redirect(product_url)
    else:
        order_form = OrderAddForm(instance=order)
        band_formset = LetPriceBandFormSet(instance=order)
        order_image_form = OrderImageForm(instance=order)

    edit_context = OrderFormHandler.build_edit_order_context(order)

    context = {
        'order_form': order_form,
        'band_formset': band_formset,
        'order_image_form': order_image_form,
        'product': order.product,
        'order': order,
        'edit_mode': True,
        **edit_context,
    }
    return render(request, 'transaction/add_order.html', context)


@login_required
def expire_order(request, order_id=None, next=None):
    # submitted
    order = None
    if request.method=='POST':
        #if request.user == instance.user
        order = get_object_or_404(Order, id=request.POST['order_id'])
        order_form = OrderExpireForm(instance=order,
                                        data=request.POST)
                                        # files=request.FILES)
        if request.user == order.user:
            if order_form.is_valid():
                order.expiry_date = timezone.now()
                order.status = order.EXPIRED
                # product = get_object_or_404(Product, id=order.id)
                order_form.save()
                messages.success(request, 'Order expired')

                product_url = request.build_absolute_uri(reverse('navigation:productPage' ,
                     kwargs={'product_slug': order.product.slug}))

                return redirect(product_url)
            else:
                messages.error(request, 'Error in validation')
        else:
            messages.error(request, 'Incorrect user credentials')
            return redirect('/')
    else:
        # order_form = OrderEditForm(instance=request.order_id)
        order = get_object_or_404(Order, id=order_id)
        if request.user == order.user:
            order_form = OrderExpireForm(instance=order)
        else:
            messages.error(request, 'Incorrect user credentials')
            return redirect('/')
    context = {
        'order_form' : order_form,
        'order' : order,
        'next' : next,
        'back_url': request.META.get('HTTP_REFERER', '/'),
    }
    return render(request, 'transaction/expire_order.html', context)

class OrderImageUpload(View):
    def post(self, request):
        data = {'is_valid': False}
        form = OrderImageForm(self.request.POST, self.request.FILES)
        if form.is_valid() and request.user is not None:
            image = form.save(commit=False)
            image.user = request.user
            image.save()
            data = {'is_valid': True, 'order_image_id': image.id ,
                    'image_name': image.image.name, 
                    'image_url': image.image.url}
        else:
            data = {'is_valid': False}
        return JsonResponse(data)


@login_required
@ajax_required
def remove_order_image(request):
    status = 'NOK'
    order_id = request.GET.get('order_id', None)
    image_id = request.GET.get('image_id', None)
    order = get_object_or_404(Order, id=order_id)
    if request.user == order.user:
        orderImage = get_object_or_404(OrderImage, id=image_id)
        if orderImage.order == order:
            orderImage.active = False
            orderImage.save()
            status = 'OK'
            logging.error("blah lbal blah")
    content = {
        'status' : status
    }
    return JsonResponse(content)



@login_required
def transaction_live_state_json(request, transaction_reference):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user:
        raise Http404

    return JsonResponse(_build_transaction_live_state(txn))
@login_required
@ajax_required
def get_fee(request):
    fee_slug = request.POST.get('fee_slug', None)
    fee = get_object_or_404(TransactionFee, slug=fee_slug)
    qty = int(request.POST.get('quantity', None))
    order_required_price = float(request.POST.get('order_required_price', None))
    order_id = request.POST.get('order_id', None)
    order = get_object_or_404(Order, id=order_id)
    price_calculated = returnFeeValue(fee, qty, order_required_price, order)
    content = {
        'status' : 'OK',
        'price_calculated': price_calculated,
    }
    return JsonResponse(content)

@login_required
def hit_order(request, order_id=None):
    verify_redirect = _require_mobile_verification(request)
    if verify_redirect is not None:
        return verify_redirect

    order = get_object_or_404(Order, id=order_id)
    manual_blocked_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.MANUAL).values_list('date', flat=True)
    )
    booked_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.BOOKED).values_list('date', flat=True)
    )
    blocked_dates = set(manual_blocked_dates) | set(booked_dates)
    handover_dates = set(
        order.blocked_dates.filter(reason=OrderBlockedDate.HANDOVER_UNAVAILABLE).values_list('date', flat=True)
    )

    def _price_per_day_for_days(rental_days):
        bands = list(order.price_bands.all().order_by('duration_days'))
        for band in bands:
            if rental_days <= int(band.duration_days):
                return float(band.price_per_day)
        return float(order.price)

    if request.user == order.user:
        messages.error(request, "You can't rent your own listing")
        return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

    if request.method == 'POST':
        order_hit_form = RentalEnquiryForm(
            data=request.POST,
            blocked_dates=blocked_dates,
            handover_dates=handover_dates,
            expiry_date=order.expiry_date.date() if order.expiry_date else None,
            max_rental_days=order.max_rental_days,
        )
        if order_hit_form.is_valid():
            turnstile_token = request.POST.get('cf-turnstile-response', '')
            if not verify_turnstile_token(turnstile_token, request.META.get('REMOTE_ADDR', '')):
                messages.error(request, 'Human verification failed. Please try again.')
                # Re-render form without proceeding
                context = {
                    'order': order,
                    'order_hit_form': order_hit_form,
                    'captcha_error': 'Human verification failed',
                    'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
                }
                return render(request, 'transaction/hit_order.html', context)

            if order.expiry_date <= timezone.now() or order.status != Order.ACTIVE:
                messages.error(request, 'This listing is no longer available.')
                return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))
            if order.verified_users_only:
                renter_profile = getattr(request.user, 'profile', None)
                if not is_profile_kyc_verified(renter_profile):
                    messages.error(
                        request,
                        'This listing is for verified users only. Complete Stripe identity verification first. '
                        'That is an identity check, not a payment-card check.',
                    )
                    return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

            start_date = order_hit_form.cleaned_data['rental_start_date']
            end_date = order_hit_form.cleaned_data['rental_end_date']
            rental_days = (end_date - start_date).days + 1
            price_per_day = _price_per_day_for_days(rental_days)

            # Validate rental length for high deposits
            product = order.product
            deposit = getattr(order, 'deposit', 0) or 0  # Get deposit from price band if available
            
            if deposit > 100 and rental_days > 5:
                messages.error(
                    request, 
                    f'Rentals with deposits over £100 are limited to 5 days maximum. '
                    f'Your requested rental is {rental_days} days. Please adjust your dates. '
                    f'(Deposit will be taken and returned at the end for longer rentals.)'
                )
                return redirect(request.build_absolute_uri(reverse('navigation:productPage', kwargs={'product_slug': order.product.slug})))

            txn = Transaction.objects.create(
                price=price_per_day,
                quantity=1,
                order_passive=order,
                order_passive_description=order.description,
                product=order.product,
                user_aggressive=request.user,
                user_passive=order.user,
                current_spot_value=0,
                price_as_pct_spot_value=0,
                transaction_status=Transaction.RENTAL_ENQUIRY,
                prev_transaction_status=Transaction.RENTAL_ENQUIRY,
                payment_status=Transaction.PAYMENT_PENDING,
                deposit_status=Transaction.DEPOSIT_PENDING,
                product_status=Transaction.CONDITION_PENDING,
                rental_start_date=start_date,
                rental_end_date=end_date,
                enquiry_message=order_hit_form.cleaned_data.get('enquiry_message', ''),
            )

            pricing = get_transaction_pricing(txn)
            sync_transaction_pricing(txn, pricing)
            txn.save(update_fields=[
                'delivery_distance_km',
                'delivery_cost',
                'rentalution_fee',
                'amended',
            ])
            sync_transaction_fee_charges(txn, pricing)
            
            # Calculate deposit handling based on rental length and amount
            txn.deposit_handling = txn.calculate_deposit_handling()
            
            # Check if high-risk product and set KYC requirements
            if product.is_high_risk():
                from account.models import Profile
                renter_profile = Profile.objects.get(user=request.user)
                lender_profile = Profile.objects.get(user=order.user)
                
                requires_kyc = False
                kyc_message = f'This is a high-risk product (risk rating: {product.get_effective_risk_rating()}/100). '
                
                # Check if borrower needs KYC
                if not is_profile_kyc_verified(renter_profile):
                    requires_kyc = True
                    kyc_message += 'As the person who is borrowing, you must complete KYC verification. '
                
                # Check if lender needs KYC
                if not is_profile_kyc_verified(lender_profile):
                    requires_kyc = True
                    kyc_message += 'The lender must also complete KYC verification before this rental can proceed. '
                
                if requires_kyc:
                    txn.requires_kyc = True
                    txn.requires_kyc_message = kyc_message
            
            txn.save()
            _reserve_transaction_dates(txn)

            enquiry_message = (order_hit_form.cleaned_data.get('enquiry_message', '') or '').strip()
            if enquiry_message:
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=order.user,
                    transaction=txn,
                    subject=f'Transaction {txn.transaction_reference}',
                    description=enquiry_message,
                )
            else:
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=order.user,
                    transaction=txn,
                    subject=f'New enquiry {txn.transaction_reference}',
                    description='You have a new enquiry on your listing.',
                    is_system_generated=True,
                )

            for ord_image in order.images.filter(active=True):
                txn_image = TransactionImage()
                txn_image.image = File(ord_image.image, ord_image.image.name)
                txn_image.transaction = txn
                txn_image.save()

            messages.success(request, 'Rental enquiry sent.')
            return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)
    else:
        order_hit_form = RentalEnquiryForm(
            blocked_dates=blocked_dates,
            handover_dates=handover_dates,
            expiry_date=order.expiry_date.date() if order.expiry_date else None,
            max_rental_days=order.max_rental_days,
        )

    price_bands = list(order.price_bands.all().order_by('duration_days').values('duration_days', 'price_per_day'))
    blocked_dates_json = json.dumps(sorted([d.isoformat() for d in manual_blocked_dates]))
    booked_dates_json = json.dumps(sorted([d.isoformat() for d in booked_dates]))
    handover_dates_json = json.dumps(sorted([d.isoformat() for d in handover_dates]))
    price_bands_json = json.dumps(price_bands)

    context = {
        'order': order,
        'order_hit_form': order_hit_form,
        'blocked_dates_json': blocked_dates_json,
        'booked_dates_json': booked_dates_json,
        'handover_dates_json': handover_dates_json,
        'price_bands_json': price_bands_json,
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
    }
    return render(request, 'transaction/hit_order.html', context)


@login_required
def view_transaction(request, transaction_reference=None):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user and not request.user.is_staff:
        raise Http404

    message_turnstile_required = txn.transactionmessage_set.count() > 20

    is_lender = (request.user == txn.user_passive)
    is_renter = (request.user == txn.user_aggressive)
    card_setup_allowed_statuses = (txn.RENTAL_ENQUIRY, txn.RENTAL_AGREED)

    def _get_contract_deadline(transaction):
        """Deadline is min(lender confirmation + 24h, end of rental start day)."""
        if not transaction.lender_agreed_at:
            return None

        deadline_24h = transaction.lender_agreed_at + timedelta(hours=24)
        candidates = [deadline_24h]

        if transaction.rental_start_date:
            london_tz = ZoneInfo('Europe/London')
            end_of_day_naive = (
                datetime.combine(transaction.rental_start_date + timedelta(days=1), dt_time.min)
                - timedelta(seconds=1)
            )
            end_of_day = timezone.make_aware(end_of_day_naive, london_tz)
            candidates.append(end_of_day)

        return min(candidates)

    def _can_collect_deposit(transaction):
        if transaction.deposit <= 0:
            return False
        if transaction.deposit_collected_placeholder:
            return False
        if transaction.deposit_card_setup_status != transaction.CARD_READY:
            return False
        if transaction.deposit_test_hold_status != transaction.TEST_HOLD_SUCCESS:
            return False
        if not transaction.rental_start_date:
            return False
        return timezone.now().date() >= transaction.rental_start_date

    def _transaction_needs_payment_card(transaction):
        return any(
            (
                transaction.deposit > 0,
                transaction.price > 0,
                (transaction.delivery_cost or 0) > 0,
                (transaction.rentalution_fee or 0) > 0,
            )
        )

    def _has_verified_payment_card(transaction):
        if not _transaction_needs_payment_card(transaction):
            return True
        return (
            transaction.deposit_card_setup_status == transaction.CARD_READY
            and transaction.deposit_test_hold_status == transaction.TEST_HOLD_SUCCESS
        )

    def _rental_payment_required(transaction):
        total_due = ((transaction.quantity or 0) * (transaction.price or 0)) + (transaction.delivery_cost or 0) + (transaction.rentalution_fee or 0)
        return total_due > 0

    def _is_rental_payment_collected(transaction):
        if not _rental_payment_required(transaction):
            return True
        return transaction.payment_status == transaction.PAYMENT_CAPTURED_PLACEHOLDER

    def _is_deposit_funds_held(transaction):
        if transaction.deposit <= 0:
            return True
        return bool(
            transaction.deposit_collected_placeholder
            or transaction.deposit_collection_status == transaction.COLLECT_SUCCESS
            or transaction.deposit_status == transaction.DEPOSIT_HELD_PLACEHOLDER
        )

    def _parse_deposit_amount(raw_value):
        try:
            return round(float((raw_value or '').strip()), 2)
        except (TypeError, ValueError):
            return None

    def _deposit_proposal_iterations(transaction):
        raw_value = getattr(transaction, 'deposit_proposal_iteration_count', 0) or 0
        return max(0, min(5, int(raw_value)))

    def _deposit_iteration_warning_text(iteration_count):
        if iteration_count < 3:
            return ''
        return (
            f'Iteration {iteration_count}/5: if you do not reach agreement, this will be escalated to a dispute '
            'and may incur a fee.'
        )

    def _is_missing_rental_voided(transaction):
        return '[MISSING_RENTAL_VOIDED]' in (transaction.deposit_resolution_notes or '')

    def _refresh_feedback_deadline(transaction):
        transaction.refresh_feedback_deadline()

    if request.method == 'POST':
        if not (is_lender or is_renter):
            raise Http404
        action = request.POST.get('action', '').strip()

        if action == 'agree_rental' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_AGREED
            txn.lender_agreement_pending_at = timezone.now()
            txn.save()
            _reserve_transaction_dates(txn)

            messages.success(request, 'Rental agreement generated. Please confirm the contract terms.')

        elif action == 'reject_enquiry' and is_lender and txn.transaction_status == txn.RENTAL_ENQUIRY:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            _release_transaction_dates(txn)
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Enquiry declined {txn.transaction_reference}',
                description='Your rental enquiry was declined.',
                is_system_generated=True,
            )
            messages.info(request, 'Rental enquiry rejected.')

        elif action == 'request_cancellation' and txn.transaction_status == txn.RENTAL_ENQUIRY:
            reason = (request.POST.get('cancellation_reason') or '').strip()
            if not reason:
                messages.error(request, 'Please provide a reason for cancellation.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.CANCEL_ACCEPTED
                txn.transaction_status_raised_by = request.user
                txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
                _release_transaction_dates(txn)
                
                # Notify the other party
                other_user = txn.user_aggressive if request.user == txn.user_passive else txn.user_passive
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=other_user,
                    transaction=txn,
                    subject=f'Transaction Cancelled - {txn.transaction_reference}',
                    description=f"The transaction has been cancelled.\n\nReason: {reason}",
                )
                messages.success(request, 'Transaction cancelled.')

        elif action == 'confirm_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and not txn.lender_agreed_at:
            if not txn.lender_agreement_pending_at:
                txn.lender_agreement_pending_at = timezone.now()
            txn.lender_agreed_at = timezone.now()
            txn.save()
            # Send contract confirmation request to borrower
            contract_msg = f"""Lender has agreed to the rental.

Rental Terms:
- Product: {txn.order_passive.product.name}
- Dates: {txn.rental_start_date} to {txn.rental_end_date}
- Price: £{txn.price}/day
- Deposit: £{txn.deposit}

Please confirm to proceed with this rental. You have 24 hours to confirm, or until the rental start date, whichever is sooner.

Transaction Ref: {txn.transaction_reference}"""
            TransactionMessage.objects.create(
                user_from=txn.user_passive,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Rental Agreement - Please Confirm {txn.transaction_reference}',
                description=contract_msg,
            )
            messages.success(request, 'Contract confirmed. Borrower has been sent a confirmation request.')

        elif action == 'reinitiate_lender_contract' and is_lender and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            contract_deadline = _get_contract_deadline(txn)
            if contract_deadline and timezone.now() <= contract_deadline:
                messages.info(request, 'Borrower still has time to confirm. You can re-send once the window expires.')
            else:
                # Extend the deadline by resetting lender_agreed_at to now
                txn.lender_agreed_at = timezone.now()
                txn.save()
                # Send a fresh confirmation request to borrower
                contract_msg = f"""Lender has re-sent the rental confirmation request.

Rental Terms:
- Product: {txn.order_passive.product.name}
- Dates: {txn.rental_start_date} to {txn.rental_end_date}
- Price: £{txn.price}/day
- Deposit: £{txn.deposit}

Please confirm to proceed with this rental. You have 24 hours to confirm, or until the rental start date, whichever is sooner.

Transaction Ref: {txn.transaction_reference}"""
                TransactionMessage.objects.create(
                    user_from=txn.user_passive,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Rental Agreement - Re-sent (Please Confirm) {txn.transaction_reference}',
                    description=contract_msg,
                )
                messages.success(request, 'Confirmation request re-sent to borrower. 24-hour window restarted.')

        elif action == 'confirm_renter_contract' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and txn.lender_agreed_at and not txn.renter_agreed_at:
            contract_deadline = _get_contract_deadline(txn)
            if contract_deadline and timezone.now() > contract_deadline:
                messages.error(
                    request,
                    'Contract confirmation window has expired. This rental can no longer be confirmed.'
                )
            else:
                txn.renter_agreed_at = timezone.now()
                txn.save()
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Rental confirmed {txn.transaction_reference}',
                    description='The borrower confirmed the rental agreement.',
                    is_system_generated=True,
                )
                messages.success(request, 'Rental confirmed! Proceeding to next stage.')

        elif action == 'reject_rental_agreement' and is_renter and txn.transaction_status == txn.RENTAL_AGREED and not txn.renter_agreed_at:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.CANCEL_ACCEPTED
            txn.transaction_status_raised_by = request.user
            txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'transaction_status_raised_by', 'amended'])
            _release_transaction_dates(txn)

            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_passive,
                transaction=txn,
                subject=f'Rental Agreement Rejected {txn.transaction_reference}',
                description='Borrower has rejected the rental agreement.',
            )
            messages.info(request, 'Rental agreement rejected and the lender has been notified.')

        elif action == 'report_missing_rental' and is_renter and txn.transaction_status in (
            txn.RENTAL_ENQUIRY,
            txn.RENTAL_AGREED,
        ):
            if not txn.rental_start_date or timezone.now().date() <= txn.rental_start_date:
                messages.error(request, 'Missing rental can only be reported after the rental start date has passed.')
            elif txn.checkout_handover_verified_at:
                messages.error(request, 'Rental handover is already verified, so missing rental cannot be reported.')
            else:
                reason = (request.POST.get('missing_rental_reason') or '').strip()
                marker = '[MISSING_RENTAL_VOIDED]'
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.CANCEL_ACCEPTED
                txn.transaction_status_raised_by = request.user
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_resolution_notes = f'{marker} Borrower reported missing rental. {reason}'.strip()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'transaction_status_raised_by',
                    'deposit_status',
                    'deposit_resolution_notes',
                    'amended',
                ])
                _release_transaction_dates(txn)
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Missing rental reported {txn.transaction_reference}',
                    description='Borrower reported missing rental after rental start date. Transaction voided; dispute/admin review required.',
                    include_admin=True,
                    is_system_generated=True,
                )
                messages.warning(request, 'Missing rental reported. Transaction voided and routed to dispute review. Borrower can now leave final feedback.')

        elif action == 'report_missing_return' and is_lender and txn.transaction_status in (
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        ):
            if not txn.rental_end_date or timezone.now().date() <= txn.rental_end_date:
                messages.error(request, 'Missing return can only be reported after the rental return date has passed.')
            else:
                reason = (request.POST.get('missing_return_reason') or '').strip()
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_resolution_notes = f'Lender reported missing return. {reason}'.strip()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Missing return reported {txn.transaction_reference}',
                    description='Lender reported missing return after return date. Dispute workflow has been opened for admin review.',
                    include_admin=True,
                    is_system_generated=True,
                )
                messages.warning(request, 'Missing return reported and dispute review opened.')

        elif action == 'add_deposit_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            cardholder_name = (request.POST.get('deposit_cardholder_name') or '').strip()
            card_brand = (request.POST.get('deposit_card_brand') or '').strip()
            card_last4 = (request.POST.get('deposit_card_last4') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif int(getattr(txn, 'max_rental_days', 0) or 0) > 5:
                messages.error(
                    request,
                    'Long rentals require a Visa or Mastercard credit card for the deposit. Please use the Stripe card flow instead.',
                )
            elif not cardholder_name:
                messages.error(request, 'Please enter the cardholder name.')
            elif len(card_last4) != 4 or not card_last4.isdigit():
                messages.error(request, 'Please enter a valid last 4 digits for the card.')
            else:
                # Trigger async task for card setup
                async_setup_deposit_card_and_test_hold.delay(
                    transaction_id=txn.id,
                    cardholder_name=cardholder_name,
                    card_brand=card_brand,
                    card_last4=card_last4,
                )
                # Mark as processing
                txn.deposit_card_setup_status = txn.CARD_NONE
                txn.save()

        elif action == 'use_existing_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif not payment_method_id:
                messages.error(request, 'Please select a payment method.')
            else:
                try:
                    pm = request.user.payment_methods.get(id=payment_method_id)
                    if int(getattr(txn, 'max_rental_days', 0) or 0) > 5:
                        card_brand = (pm.card_brand or '').strip().lower()
                        card_funding = (pm.card_funding or '').strip().lower()
                        if card_brand not in ('visa', 'mastercard') or card_funding not in ('credit', 'charge'):
                            messages.error(
                                request,
                                'Long rentals require a Visa or Mastercard credit card for the deposit. Choose a different card.',
                            )
                            return redirect('transaction:view_transaction', txn.transaction_reference)
                    txn.deposit_card_setup_status = txn.CARD_READY
                    txn.deposit_cardholder_name = 'Stripe'
                    txn.deposit_card_brand = pm.card_brand
                    txn.deposit_card_funding = pm.card_funding
                    txn.deposit_card_last4 = pm.card_last4
                    txn.deposit_test_hold_status = txn.TEST_HOLD_SUCCESS
                    txn.deposit_test_hold_amount = 0.30
                    txn.deposit_test_hold_at = timezone.now()
                    txn.stripe_setup_intent_id = pm.stripe_setup_intent_id
                    txn.stripe_payment_method_id = pm.stripe_payment_method_id
                    txn.save()
                except PaymentMethod.DoesNotExist:
                    messages.error(request, 'Payment method not found.')

        elif action == 'confirm_stripe_card' and is_renter and txn.transaction_status in card_setup_allowed_statuses:
            payment_method_id = (request.POST.get('payment_method_id') or '').strip()
            setup_intent_id = (request.POST.get('setup_intent_id') or '').strip()

            if txn.deposit <= 0 and txn.price <= 0:
                messages.info(request, 'No payment method is required for this transaction.')
            elif not payment_method_id:
                messages.error(request, 'Card details were not submitted successfully. Please try again.')
            else:
                # Mark as processing and kick off confirmation immediately.
                # Webhooks can still reconcile later, but local/test flows should not stall waiting for one.
                txn.deposit_card_setup_status = txn.CARD_NONE
                txn.deposit_test_hold_status = txn.TEST_HOLD_NOT_RUN
                txn.stripe_setup_intent_id = setup_intent_id
                txn.stripe_payment_method_id = payment_method_id
                txn.save(update_fields=[
                    'deposit_card_setup_status',
                    'deposit_test_hold_status',
                    'stripe_setup_intent_id',
                    'stripe_payment_method_id',
                    'amended',
                ])
                async_confirm_card_setup.delay(
                    transaction_id=txn.id,
                    setup_intent_id=setup_intent_id,
                    payment_method_id=payment_method_id,
                )

        elif action == 'collect_deposit' and is_lender and txn.transaction_status in (
            txn.RENTAL_AGREED, 
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
        ):
            if not _can_collect_deposit(txn):
                messages.error(
                    request,
                    'Deposit cannot be collected yet. Ensure card setup/test hold is complete and rental start date has been reached.'
                )
            else:
                # Trigger async task for deposit collection
                async_collect_deposit_hold.delay(transaction_id=txn.id)
                # Mark as processing
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.save()
                messages.info(
                    request,
                    'Deposit collection in progress. You will receive email confirmation when complete.'
                )

        elif action == 'send_message' and (is_lender or is_renter):
            body = (request.POST.get('message_body') or '').strip()
            image_files = request.FILES.getlist('message_images')
            video_files = request.FILES.getlist('message_videos')
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            if message_turnstile_required:
                turnstile_token = request.POST.get('cf-turnstile-response', '')
                if not verify_turnstile_token(turnstile_token, request.META.get('REMOTE_ADDR', '')):
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': 'Human verification failed. Please complete the checkbox and try again.'}, status=400)
                    messages.error(request, 'Human verification failed. Please try again.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not body and not image_files and not video_files:
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': 'Please enter a message or attach at least one file before sending.'}, status=400)
                messages.error(request, 'Please enter a message or attach at least one file before sending.')
            else:
                invalid_video = next((f for f in video_files if not (getattr(f, 'content_type', '') or '').startswith('video/')), None)
                if invalid_video is not None:
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': f'{invalid_video.name} is not a valid video file.'}, status=400)
                    messages.error(request, f'{invalid_video.name} is not a valid video file.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                txn_message = TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=(txn.user_aggressive if is_lender else txn.user_passive),
                    transaction=txn,
                    subject=f'Transaction {txn.transaction_reference}',
                    description=body,
                )

                for idx, image_file in enumerate(image_files):
                    try:
                        TransactionMessageImage.objects.create(
                            txn_message=txn_message,
                            user=request.user,
                            image=image_file,
                            first_image=(idx == 0),
                            active=True,
                        )
                    except ValidationError as e:
                        if is_ajax:
                            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
                        messages.error(request, f'Image upload error: {str(e)}')
                        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                for video_file in video_files:
                    try:
                        # Save video with both display version and raw archive for verification
                        txn_msg_image = TransactionMessageImage(
                            txn_message=txn_message,
                            user=request.user,
                            video=video_file,
                            video_raw=video_file,  # Keep raw copy for verification chain of custody
                            first_image=False,
                            active=True,
                        )
                        txn_msg_image.full_clean()  # Validate before saving
                        txn_msg_image.save()
                    except ValidationError as e:
                        if is_ajax:
                            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
                        messages.error(request, f'Video upload error: {str(e)}')
                        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

                attachment_count = len(image_files) + len(video_files)
                if is_ajax:
                    if attachment_count:
                        msg = f'Message sent with {attachment_count} attachment(s).'
                    else:
                        msg = 'Message sent.'
                    return JsonResponse({'ok': True, 'message': msg})
                if attachment_count:
                    messages.info(request, f'Message sent with {attachment_count} attachment(s).')
                else:
                    messages.info(request, 'Message sent.')

        elif action == 'send_dispute_private_message' and (is_lender or is_renter):
            body = (request.POST.get('message_body') or '').strip()
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if message_turnstile_required:
                turnstile_token = request.POST.get('cf-turnstile-response', '')
                if not verify_turnstile_token(turnstile_token, request.META.get('REMOTE_ADDR', '')):
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': 'Human verification failed. Please complete the checkbox and try again.'}, status=400)
                    messages.error(request, 'Human verification failed. Please try again.')
                    return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not body:
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': 'Please enter a message before sending.'}, status=400)
                messages.error(request, 'Please enter a message before sending.')
            else:
                txn_message = TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=request.user,
                    transaction=txn,
                    subject=f'Private dispute message {txn.transaction_reference}',
                    description=body,
                    include_admin=True,
                    private_to_sender=True,
                    is_system_generated=False,
                )
                if is_ajax:
                    return JsonResponse({'ok': True, 'message': 'Private message sent.'})
                messages.info(request, 'Private message sent to the dispute team.')

        elif action == 'initiate_rental' and is_lender and txn.transaction_status == txn.RENTAL_AGREED:
            if not _has_verified_payment_card(txn):
                messages.error(
                    request,
                    'Rental is due to begin but cannot be initiated until the borrower has provided a payment card and verification hold has succeeded.'
                )
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            try:
                checkout_video = _save_transaction_evidence(
                    request,
                    txn,
                    evidence_stage='checkout_lender',
                    video_file_field='checkout_video_file',
                    video_url_field='checkout_video_url',
                )
            except ValidationError as exc:
                messages.error(request, f'Checkout evidence upload failed: {exc}')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not checkout_video:
                messages.error(request, 'Please provide checkout video evidence as a file upload or URL.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_DAY_AWAITING_VERIFICATION
            txn.checkout_condition_video_url = checkout_video
            txn.checkout_borrower_confirmed = False
            txn.checkout_borrower_video_url = ''
            txn.checkout_handover_pin = ''
            txn.checkout_handover_pin_generated_at = None
            txn.checkout_handover_verified_at = None
            if checkout_video:
                txn.product_status = txn.CHECKOUT_VIDEO_ADDED

            txn.payment_collected_placeholder = True
            txn.payment_status = txn.PAYMENT_CAPTURED_PLACEHOLDER
            txn.deposit_status = txn.DEPOSIT_HELD_PLACEHOLDER if txn.deposit_collected_placeholder else txn.DEPOSIT_PENDING
            rental_amount = round((txn.quantity or 0) * (txn.price or 0), 2)
            total_before_deposit = round(rental_amount + (txn.delivery_cost or 0) + (txn.rentalution_fee or 0), 2)
            default_payment_note = (
                f'Rental £{rental_amount:.2f}; '
                f'Delivery £{(txn.delivery_cost or 0):.2f}; '
                f'Rentalution fee £{(txn.rentalution_fee or 0):.2f}; '
                f'Total before deposit £{total_before_deposit:.2f}'
            )
            txn.payment_placeholder_notes = (request.POST.get('payment_placeholder_notes', '').strip() or default_payment_note)

            payment_capture_result = stripe_connect_service.collect_rental_payment(transaction=txn)
            if not payment_capture_result.get('ok'):
                record_site_failure(
                    'Rental payment capture failed',
                    details=f'Rental payment capture failed for transaction {txn.transaction_reference}. Handover PIN withheld.',
                    context={
                        'transaction_id': txn.id,
                        'transaction_reference': txn.transaction_reference,
                        'error': payment_capture_result.get('error', ''),
                        'provider': payment_capture_result.get('provider', 'stripe'),
                    },
                )
                try:
                    request.user.email_user(
                        f'Payment retry needed for {txn.transaction_reference}',
                        (
                            f'We could not capture the rental payment for transaction {txn.transaction_reference}.\n\n'
                            f'Error: {payment_capture_result.get("error") or ""}\n\n'
                            'Please retry the payment before the PIN is released.'
                        ),
                    )
                except Exception:
                    logger.exception('Failed to email rental payment retry notice to user %s', request.user.id)
                messages.error(
                    request,
                    f'Rental payment capture failed. Handover PIN will not be shown until payment succeeds. {payment_capture_result.get("error") or ""}'.strip(),
                )
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            txn.payment_collected_placeholder = True
            txn.payment_status = payment_capture_result.get('payment_status', txn.PAYMENT_CAPTURED_PLACEHOLDER)
            txn.payment_collection_requested_at = payment_capture_result.get('collection_requested_at', timezone.now())
            txn.payment_collection_reference = payment_capture_result.get('collection_reference', '')
            charged_amount = float(payment_capture_result.get('charged_amount') or 0)
            capture_note = (
                f'[STRIPE_RENTAL_CAPTURE] charged={charged_amount:.2f} '
                f'status={payment_capture_result.get("payment_intent_status") or ""} '
                f'ref={txn.payment_collection_reference}'
            ).strip()
            if capture_note:
                existing_payment_notes = (txn.payment_placeholder_notes or '').strip()
                if capture_note not in existing_payment_notes:
                    txn.payment_placeholder_notes = f'{existing_payment_notes}\n{capture_note}'.strip()

            should_collect_deposit_now = (
                txn.deposit > 0
                and _can_collect_deposit(txn)
                and txn.deposit_collection_status != txn.COLLECT_SUCCESS
            )
            if should_collect_deposit_now:
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.deposit_collection_requested_at = timezone.now()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'checkout_condition_video_url',
                    'checkout_borrower_confirmed',
                    'checkout_borrower_video_url',
                    'checkout_handover_pin',
                    'checkout_handover_pin_generated_at',
                    'checkout_handover_verified_at',
                    'product_status',
                    'payment_collected_placeholder',
                    'payment_status',
                    'payment_collection_requested_at',
                    'payment_collection_reference',
                    'deposit_status',
                    'payment_placeholder_notes',
                    'deposit_collection_status',
                    'deposit_collection_requested_at',
                    'amended',
                ])
            else:
                txn.save()
            TransactionMessage.objects.create(
                user_from=request.user,
                user_to=txn.user_aggressive,
                transaction=txn,
                subject=f'Checkout evidence submitted {txn.transaction_reference}',
                description='Lender submitted rental-start evidence. Borrower should confirm agreement or submit counter-evidence.',
                is_system_generated=True,
            )
            if should_collect_deposit_now:
                async_collect_deposit_hold.delay(transaction_id=txn.id)
            messages.success(request, 'Checkout evidence submitted. Waiting for borrower confirmation/counter-evidence and handover PIN verification.')

        elif action == 'confirm_checkout_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            if not txn.checkout_condition_video_url:
                messages.error(request, 'Lender checkout evidence is missing.')
            else:
                txn.checkout_borrower_confirmed = True
                if not _is_rental_payment_collected(txn):
                    txn.save(update_fields=['checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Evidence confirmed, but PIN cannot be generated until rental payment is captured.')
                elif _is_deposit_funds_held(txn):
                    if not txn.checkout_handover_pin:
                        txn.checkout_handover_pin = _generate_txn_pin(6)
                        txn.checkout_handover_pin_generated_at = timezone.now()
                    txn.save(update_fields=[
                        'checkout_borrower_confirmed',
                        'checkout_handover_pin',
                        'checkout_handover_pin_generated_at',
                        'amended',
                    ])
                    messages.success(request, 'Checkout evidence confirmed. PIN generated for handover verification.')
                else:
                    txn.save(update_fields=['checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Evidence confirmed, but PIN cannot be generated until deposit funds are held.')

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Checkout evidence confirmed {txn.transaction_reference}',
                    description='Borrower confirmed lender checkout evidence. Complete handover PIN verification to start rental.',
                    is_system_generated=True,
                )

        elif action == 'submit_checkout_borrower_evidence' and is_renter and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            try:
                borrower_checkout_video = _save_transaction_evidence(
                    request,
                    txn,
                    evidence_stage='checkout_borrower',
                    video_file_field='checkout_borrower_video_file',
                    video_url_field='checkout_borrower_video_url',
                )
            except ValidationError as exc:
                messages.error(request, f'Counter-evidence upload failed: {exc}')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not borrower_checkout_video:
                messages.error(request, 'Please provide borrower checkout evidence as a file upload or URL.')
            else:
                txn.checkout_borrower_video_url = borrower_checkout_video
                txn.checkout_borrower_confirmed = False
                if not _is_rental_payment_collected(txn):
                    txn.save(update_fields=['checkout_borrower_video_url', 'checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Counter-evidence saved, but PIN cannot be generated until rental payment is captured.')
                elif _is_deposit_funds_held(txn):
                    if not txn.checkout_handover_pin:
                        txn.checkout_handover_pin = _generate_txn_pin(6)
                        txn.checkout_handover_pin_generated_at = timezone.now()
                    txn.save(update_fields=[
                        'checkout_borrower_video_url',
                        'checkout_borrower_confirmed',
                        'checkout_handover_pin',
                        'checkout_handover_pin_generated_at',
                        'amended',
                    ])
                    messages.success(request, 'Counter-evidence submitted. PIN generated for handover verification.')
                else:
                    txn.save(update_fields=['checkout_borrower_video_url', 'checkout_borrower_confirmed', 'amended'])
                    messages.warning(request, 'Counter-evidence saved, but PIN cannot be generated until deposit funds are held.')

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Borrower checkout counter-evidence {txn.transaction_reference}',
                    description='Borrower submitted checkout counter-evidence. Lender should review and complete handover PIN verification.',
                    is_system_generated=True,
                )

        elif action == 'verify_checkout_handover_pin' and is_lender and txn.transaction_status == txn.RENTAL_DAY_AWAITING_VERIFICATION:
            entered_pin = (request.POST.get('checkout_handover_pin') or '').strip()
            if not _is_rental_payment_collected(txn):
                messages.error(request, 'Rental payment must be captured before handover PIN verification.')
            elif not _is_deposit_funds_held(txn):
                messages.error(request, 'Deposit funds must be held before rental handover PIN verification.')
            elif not txn.checkout_handover_pin:
                messages.error(request, 'Borrower has not reached the PIN step yet.')
            elif entered_pin != txn.checkout_handover_pin:
                messages.error(request, 'Invalid checkout handover PIN. Please try again.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_ONGOING
                txn.checkout_handover_verified_at = timezone.now()
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'checkout_handover_verified_at',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Rental handover verified {txn.transaction_reference}',
                    description='Checkout handover PIN verified by lender. Rental is now officially ongoing.',
                    is_system_generated=True,
                )
                messages.success(request, 'Handover verified. You are good to lend - rental is now active.')

        elif action == 'submit_return_borrower_evidence' and is_renter and txn.transaction_status in (
            txn.RENTAL_DAY_AWAITING_VERIFICATION,
            txn.RENTAL_ONGOING,
            txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION,
        ):
            try:
                return_video = _save_transaction_evidence(
                    request,
                    txn,
                    evidence_stage='return_borrower',
                    video_file_field='return_video_file',
                    video_url_field='return_video_url',
                )
            except ValidationError as exc:
                messages.error(request, f'Return evidence upload failed: {exc}')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not return_video:
                messages.error(request, 'Please provide borrower return evidence as a file upload or URL.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION
                txn.return_condition_video_url = return_video
                txn.return_borrower_video_url = return_video
                txn.return_lender_confirmed = False
                txn.return_lender_video_url = ''
                txn.return_handover_pin = ''
                txn.return_handover_pin_generated_at = None
                txn.return_handover_verified_at = None
                txn.product_status = txn.RETURN_VIDEO_ADDED
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'return_condition_video_url',
                    'return_borrower_video_url',
                    'return_lender_confirmed',
                    'return_lender_video_url',
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_handover_verified_at',
                    'product_status',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Return evidence submitted {txn.transaction_reference}',
                    description='Borrower has submitted return-day evidence. Lender should confirm agreement or submit counter-evidence.',
                    is_system_generated=True,
                )
                messages.success(request, 'Return evidence submitted. Waiting for lender confirmation/counter-evidence.')

        elif action == 'confirm_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            if not txn.return_borrower_video_url:
                messages.error(request, 'Borrower evidence is required before confirmation.')
            else:
                if not txn.return_handover_pin:
                    txn.return_handover_pin = _generate_txn_pin(6)
                    txn.return_handover_pin_generated_at = timezone.now()
                txn.return_lender_confirmed = True
                txn.save(update_fields=[
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_lender_confirmed',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Return verification code ready {txn.transaction_reference}',
                    description='Lender has reviewed return evidence. Please ask lender for the return verification PIN and submit it to complete return handover.',
                    is_system_generated=True,
                )
                messages.success(request, 'Evidence confirmed. Return PIN generated and ready for borrower verification.')

        elif action == 'submit_lender_return_evidence' and is_lender and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            try:
                lender_return_video = _save_transaction_evidence(
                    request,
                    txn,
                    evidence_stage='return_lender',
                    video_file_field='lender_return_video_file',
                    video_url_field='lender_return_video_url',
                )
            except ValidationError as exc:
                messages.error(request, f'Counter-evidence upload failed: {exc}')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            if not lender_return_video:
                messages.error(request, 'Please provide lender return evidence as a file upload or URL.')
            else:
                if not txn.return_handover_pin:
                    txn.return_handover_pin = _generate_txn_pin(6)
                    txn.return_handover_pin_generated_at = timezone.now()
                txn.return_lender_video_url = lender_return_video
                txn.return_lender_confirmed = False
                txn.save(update_fields=[
                    'return_handover_pin',
                    'return_handover_pin_generated_at',
                    'return_lender_video_url',
                    'return_lender_confirmed',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Lender counter-evidence submitted {txn.transaction_reference}',
                    description='Lender has submitted return-day counter-evidence. Please review and then submit the return verification PIN to complete handover.',
                    is_system_generated=True,
                )
                messages.warning(request, 'Counter-evidence saved. Return PIN generated for final handover verification.')

        elif action == 'verify_return_handover_pin' and is_renter and txn.transaction_status == txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION:
            entered_pin = (request.POST.get('return_handover_pin') or '').strip()
            if not txn.return_handover_pin:
                messages.error(request, 'Lender has not completed return review yet, so no PIN is available.')
            elif entered_pin != txn.return_handover_pin:
                messages.error(request, 'Invalid return verification PIN. Please try again.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.AWAITING_FEEDBACK if (txn.deposit or 0) <= 0 else txn.RENTAL_RETURNED_DEPOSIT_PENDING
                txn.return_handover_verified_at = timezone.now()
                if (txn.deposit or 0) <= 0:
                    txn.deposit_status = txn.DEPOSIT_RETURNED_FULL
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'return_handover_verified_at',
                    'deposit_status',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Return handover verified {txn.transaction_reference}',
                    description='Borrower completed return PIN verification. Return is confirmed and deposit resolution can now proceed.',
                    is_system_generated=True,
                )
                if (txn.deposit or 0) <= 0:
                    messages.success(request, 'Return verification complete. No deposit is held, so the transaction has moved straight to feedback.')
                else:
                    messages.success(request, 'Return verification complete. Rental marked as returned and ready for deposit resolution.')

        elif action == 'propose_deposit_return' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
        ):
            proposed_amount = _parse_deposit_amount(request.POST.get('deposit_proposed_return_amount'))
            resolution_notes = (request.POST.get('deposit_resolution_notes') or '').strip()
            proposal_iterations = _deposit_proposal_iterations(txn)

            if proposed_amount is None:
                messages.error(request, 'Please enter a valid deposit return amount.')
            elif proposed_amount < 0:
                messages.error(request, 'Deposit return amount cannot be negative.')
            elif proposed_amount > txn.deposit:
                messages.error(request, 'Deposit return amount cannot exceed the original deposit.')
            elif proposed_amount < txn.deposit and not resolution_notes:
                messages.error(request, 'Please provide a reason when returning less than the full deposit.')
            elif proposal_iterations >= 5:
                messages.error(request, 'Maximum deposit proposal iterations reached (5). Please raise a dispute to continue; disputes may incur a fee.')
            else:
                previous_status = txn.transaction_status
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_PENDING
                txn.deposit_status = txn.DEPOSIT_PENDING
                txn.deposit_proposed_return_amount = proposed_amount
                txn.deposit_proposed_by_lender_at = timezone.now()
                txn.deposit_proposal_accepted_at = None
                txn.deposit_proposal_iteration_count = proposal_iterations + 1
                txn.deposit_resolution_notes = resolution_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposed_return_amount',
                    'deposit_proposed_by_lender_at',
                    'deposit_proposal_accepted_at',
                    'deposit_proposal_iteration_count',
                    'deposit_resolution_notes',
                    'amended',
                ])

                if previous_status == txn.RENTAL_RETURNED_DEPOSIT_CONTESTED:
                    description = (
                        f'Lender updated deposit proposal to £{proposed_amount:.2f}. '
                        'Please review and either agree or contest.'
                    )
                else:
                    description = (
                        f'Lender proposed returning £{proposed_amount:.2f} from deposit. '
                        'Please review and either agree or contest.'
                    )

                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_aggressive,
                    transaction=txn,
                    subject=f'Deposit return proposal {txn.transaction_reference}',
                    description=description,
                    is_system_generated=True,
                )
                new_iteration_count = proposal_iterations + 1
                warning_text = _deposit_iteration_warning_text(new_iteration_count)
                if warning_text:
                    messages.warning(
                        request,
                        f'Deposit proposal sent: £{proposed_amount:.2f}. {warning_text}',
                    )
                else:
                    messages.success(request, f'Deposit proposal sent: £{proposed_amount:.2f}. Iteration {new_iteration_count}/5.')

        elif action == 'agree_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            proposed_amount = txn.deposit_proposed_return_amount
            if txn.deposit_proposed_by_lender_at is None:
                messages.error(request, 'There is no lender proposal to accept yet.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.AWAITING_FEEDBACK
                _refresh_feedback_deadline(txn)
                txn.deposit_status = (
                    txn.DEPOSIT_RETURNED_FULL
                    if abs(proposed_amount - txn.deposit) < 0.01
                    else txn.DEPOSIT_RETURNED_REDUCED
                )
                txn.deposit_proposal_accepted_at = timezone.now()
                if not txn.deposit_resolution_notes:
                    txn.deposit_resolution_notes = f'Borrower accepted lender proposal of £{proposed_amount:.2f}.'
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'feedback_window_expires_at',
                    'deposit_status',
                    'deposit_proposal_accepted_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Deposit proposal accepted {txn.transaction_reference}',
                    description=f'Borrower accepted deposit return proposal of £{proposed_amount:.2f}.',
                    is_system_generated=True,
                )
                async_resolve_deposit_hold.delay(
                    transaction_id=txn.id,
                    return_amount=proposed_amount,
                )
                messages.success(request, 'Deposit proposal accepted. Please leave feedback to close the transaction.')

        elif action == 'contest_deposit_return' and is_renter and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            contest_notes = (request.POST.get('deposit_resolution_notes') or '').strip()
            proposal_iterations = _deposit_proposal_iterations(txn)
            if txn.deposit_proposed_by_lender_at is None:
                messages.error(request, 'There is no lender proposal to contest yet.')
            elif not contest_notes:
                messages.error(request, 'Please add a reason for contesting the proposal.')
            elif proposal_iterations >= 5:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_proposal_contested_at = timezone.now()
                txn.deposit_resolution_notes = contest_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposal_contested_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Deposit dispute auto-escalated {txn.transaction_reference}',
                    description='Max proposal iterations reached (5). Deposit dispute was automatically escalated to admin review.',
                    include_admin=True,
                    is_system_generated=True,
                )
                messages.warning(request, 'Max proposal iterations reached. Dispute has been escalated to admin and may incur a fee depending on outcome.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_CONTESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_proposal_contested_at = timezone.now()
                txn.deposit_resolution_notes = contest_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_proposal_contested_at',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=txn.user_passive,
                    transaction=txn,
                    subject=f'Deposit proposal contested {txn.transaction_reference}',
                    description='Borrower contested the lender deposit proposal. Lender can revise proposal or escalate to admin dispute.',
                    is_system_generated=True,
                )
                messages.warning(request, 'Deposit proposal contested. Lender can update proposal or escalate dispute to admin.')

        elif action == 'raise_deposit_dispute_admin' and (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_PENDING,
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            dispute_notes = (request.POST.get('deposit_resolution_notes') or '').strip()
            if not dispute_notes:
                messages.error(request, 'Please include dispute details for admin review.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.deposit_status = txn.DEPOSIT_MEDIATION
                txn.deposit_resolution_notes = dispute_notes
                txn.save(update_fields=[
                    'prev_transaction_status',
                    'transaction_status',
                    'deposit_status',
                    'deposit_resolution_notes',
                    'amended',
                ])
                TransactionMessage.objects.create(
                    user_from=request.user,
                    user_to=(txn.user_aggressive if is_lender else txn.user_passive),
                    transaction=txn,
                    subject=f'Deposit dispute raised to admin {txn.transaction_reference}',
                    description='Deposit dispute has been escalated to admin. Further evidence/messages can be added while review is ongoing.',
                    include_admin=True,
                    is_system_generated=True,
                )
                messages.warning(request, 'Deposit dispute raised to admin team.')

        elif action == 'secure_dispute_funds' and is_lender and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_CONTESTED,
            txn.DISPUTE_REQUESTED,
        ):
            if txn.deposit_collection_status == txn.COLLECT_SUCCESS:
                messages.info(request, 'Deposit funds are already secured.')
            elif not _can_collect_deposit(txn):
                messages.error(request, 'Deposit cannot be secured yet. Verify card setup/hold and rental start timing.')
            else:
                async_collect_deposit_hold.delay(transaction_id=txn.id)
                txn.deposit_collection_status = txn.COLLECT_NOT_RUN
                txn.deposit_collection_requested_at = timezone.now()
                txn.save(update_fields=['deposit_collection_status', 'deposit_collection_requested_at', 'amended'])
                messages.success(request, 'Deposit securing initiated due to dispute status.')

        elif action == 'deposit_full' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.AWAITING_FEEDBACK
            _refresh_feedback_deadline(txn)
            txn.deposit_status = txn.DEPOSIT_RETURNED_FULL
            txn.deposit_proposed_return_amount = txn.deposit
            txn.deposit_proposed_by_lender_at = timezone.now()
            txn.deposit_proposal_accepted_at = timezone.now()
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'feedback_window_expires_at',
                'deposit_status',
                'deposit_proposed_return_amount',
                'deposit_proposed_by_lender_at',
                'deposit_proposal_accepted_at',
                'deposit_resolution_notes',
                'amended',
            ])
            async_resolve_deposit_hold.delay(
                transaction_id=txn.id,
                return_amount=txn.deposit,
            )
            messages.success(request, 'Deposit returned in full. Please leave feedback to close the transaction.')

        elif action == 'deposit_reduced' and is_lender and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            reduced_amount = _parse_deposit_amount(request.POST.get('deposit_proposed_return_amount'))
            if reduced_amount is None:
                reduced_amount = 0
            reduced_amount = max(0, min(reduced_amount, txn.deposit))
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.AWAITING_FEEDBACK
            _refresh_feedback_deadline(txn)
            txn.deposit_status = txn.DEPOSIT_RETURNED_REDUCED
            txn.deposit_proposed_return_amount = reduced_amount
            txn.deposit_proposed_by_lender_at = timezone.now()
            txn.deposit_proposal_accepted_at = timezone.now()
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save(update_fields=[
                'prev_transaction_status',
                'transaction_status',
                'feedback_window_expires_at',
                'deposit_status',
                'deposit_proposed_return_amount',
                'deposit_proposed_by_lender_at',
                'deposit_proposal_accepted_at',
                'deposit_resolution_notes',
                'amended',
            ])
            async_resolve_deposit_hold.delay(
                transaction_id=txn.id,
                return_amount=reduced_amount,
            )
            messages.success(request, f'Reduced deposit return recorded (£{reduced_amount:.2f}). Please leave feedback to close the transaction.')

        elif action == 'mediation_required' and (is_lender or is_renter) and txn.transaction_status == txn.RENTAL_RETURNED_DEPOSIT_PENDING:
            txn.prev_transaction_status = txn.transaction_status
            txn.transaction_status = txn.RENTAL_RETURNED_DEPOSIT_CONTESTED
            txn.deposit_status = txn.DEPOSIT_MEDIATION
            txn.deposit_resolution_notes = request.POST.get('deposit_resolution_notes', '').strip()
            txn.save()
            messages.warning(request, 'Mediation required has been recorded.')

        elif action == 'submit_feedback' and (is_lender or is_renter) and txn.transaction_status in (
            txn.RENTAL_RETURNED_DEPOSIT_RETURNED,
            txn.AWAITING_FEEDBACK,
            txn.FEEDBACK_ONE_SIDED,
            txn.RENTAL_PROCESS_COMPLETED,
        ) or (
            action == 'submit_feedback'
            and is_renter
            and txn.transaction_status == txn.CANCEL_ACCEPTED
            and _is_missing_rental_voided(txn)
        ):
            communication_rating = request.POST.get('communication_rating', '').strip()
            delivery_return_rating = request.POST.get('delivery_return_rating', '').strip()
            overall_rating = request.POST.get('overall_rating', '').strip()
            feedback_comment = (request.POST.get('feedback_comment') or '').strip()

            if txn.transaction_status == txn.CANCEL_ACCEPTED and _is_missing_rental_voided(txn) and not is_renter:
                messages.error(request, 'Only the borrower can leave feedback for a voided missing-rental transaction.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            try:
                communication_rating = int(communication_rating)
                delivery_return_rating = int(delivery_return_rating)
                overall_rating = int(overall_rating)
            except ValueError:
                messages.error(request, 'Feedback ratings must be whole numbers between 0 and 5.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            ratings = [communication_rating, delivery_return_rating, overall_rating]
            if any(r < 0 or r > 5 for r in ratings):
                messages.error(request, 'All feedback ratings must be between 0 and 5.')
                return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

            left_for = txn.user_aggressive if is_lender else txn.user_passive
            feedback_obj, created = TransactionFeedback.objects.get_or_create(
                transaction=txn,
                left_by=request.user,
                left_for=left_for,
                defaults={
                    'rating': overall_rating,
                    'communication_rating': communication_rating,
                    'delivery_return_rating': delivery_return_rating,
                    'overall_rating': overall_rating,
                    'comment': feedback_comment,
                    'is_negative': overall_rating <= 2,
                },
            )

            if not created:
                feedback_obj.rating = overall_rating
                feedback_obj.communication_rating = communication_rating
                feedback_obj.delivery_return_rating = delivery_return_rating
                feedback_obj.overall_rating = overall_rating
                feedback_obj.comment = feedback_comment
                feedback_obj.is_negative = (overall_rating <= 2)
                feedback_obj.save(update_fields=[
                    'rating',
                    'communication_rating',
                    'delivery_return_rating',
                    'overall_rating',
                    'comment',
                    'is_negative',
                ])

            other_user = txn.user_passive if request.user == txn.user_aggressive else txn.user_aggressive
            other_feedback_exists = TransactionFeedback.objects.filter(
                transaction=txn,
                left_by=other_user,
                left_for=request.user,
            ).exists()

            if txn.transaction_status == txn.CANCEL_ACCEPTED and _is_missing_rental_voided(txn):
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.FEEDBACK_ONE_SIDED
                _refresh_feedback_deadline(txn)
                txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'feedback_window_expires_at', 'amended'])
                messages.success(request, 'Feedback submitted for missing-rental report. This will auto-close after the feedback window if no counter-feedback is added.')
            else:
                txn.prev_transaction_status = txn.transaction_status
                txn.transaction_status = txn.RENTAL_PROCESS_COMPLETED if other_feedback_exists else txn.FEEDBACK_ONE_SIDED
                if other_feedback_exists:
                    txn.feedback_window_expires_at = None
                else:
                    _refresh_feedback_deadline(txn)
                txn.save(update_fields=['prev_transaction_status', 'transaction_status', 'feedback_window_expires_at', 'amended'])

                if other_feedback_exists:
                    messages.success(request, 'Feedback submitted. Both parties have now completed feedback, and the transaction is closed.')
                else:
                    messages.success(request, 'Feedback submitted. Waiting for the other party, and this will auto-close after the feedback window.')

        else:
            messages.error(request, 'That action is not available for the current state.')

        return redirect('transaction:view_transaction', transaction_reference=txn.transaction_reference)

    messages_qs = txn.transactionmessage_set.all()
    messages_ = sorted(
        sorted(
            messages_qs.filter(
                models.Q(private_to_sender=False) |
                models.Q(user_to=request.user) |
                models.Q(include_admin=True, user_to=request.user)
            ),
            key=attrgetter('created'),
            reverse=True,
        ),
        key=attrgetter('read_by_user_to')
    )
    for message in messages_:
        message.display_subject = _friendly_message_title(message)
        message.order_thumbnail_url = _message_order_thumbnail_url(message)
        message.preview_text = _message_preview_text(message)
        message.message_alignment_class = _message_alignment_class(message, request.user)
    charges = txn.transactioncharge_set.all()
    txn_images = txn.transactionimage_set.all()
    total_items = txn.quantity * txn.price
    total_fees = sum(charge.price for charge in charges)
    total_px = total_items + total_fees
    step, next_action = getTransactionStepAndAction(txn, request)
    now_ts = timezone.now()
    today = now_ts.date()
    contract_deadline = _get_contract_deadline(txn)
    contract_seconds_remaining = None
    if contract_deadline:
        contract_seconds_remaining = int((contract_deadline - now_ts).total_seconds())
    lender_contract_resend_available = bool(
        is_lender
        and txn.transaction_status == txn.RENTAL_AGREED
        and txn.lender_agreed_at
        and not txn.renter_agreed_at
        and contract_deadline
        and now_ts > contract_deadline
    )

    def _format_seconds(total_seconds):
        if total_seconds is None:
            return '--:--:--'
        total_seconds = max(0, int(total_seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'

    can_collect_deposit = _can_collect_deposit(txn)
    has_verified_payment_card = _has_verified_payment_card(txn)
    needs_payment_card = _transaction_needs_payment_card(txn)
    rental_start_blocked_by_missing_card = (
        is_lender
        and txn.transaction_status == txn.RENTAL_AGREED
        and bool(txn.lender_agreed_at)
        and bool(txn.renter_agreed_at)
        and needs_payment_card
        and not has_verified_payment_card
    )

    # Generate Stripe SetupIntent for card collection if needed
    setup_intent_client_secret = None
    setup_intent_id = None
    if (
        is_renter
        and txn.transaction_status in card_setup_allowed_statuses
        and needs_payment_card
        and txn.deposit_card_setup_status != txn.CARD_READY
        and not txn.deposit_collected_placeholder
    ):
        setup_result = stripe_connect_service.create_setup_intent(transaction=txn)
        if setup_result.get('ok'):
            setup_intent_client_secret = setup_result.get('client_secret')
            setup_intent_id = setup_result.get('setup_intent_id')

    can_setup_deposit_card = (
        is_renter
        and txn.transaction_status in card_setup_allowed_statuses
        and needs_payment_card
        and not txn.deposit_collected_placeholder
    )

    dispute_statuses = (txn.RENTAL_RETURNED_DEPOSIT_CONTESTED, txn.DISPUTE_REQUESTED)
    dispute_in_progress = txn.transaction_status in dispute_statuses
    dispute_hold_deadline = None
    dispute_hold_seconds_remaining = None
    if txn.deposit_test_hold_at:
        dispute_hold_deadline = txn.deposit_test_hold_at + timedelta(days=7)
        dispute_hold_seconds_remaining = int((dispute_hold_deadline - now_ts).total_seconds())

    urgent_dispute_funds_action = (
        is_lender
        and dispute_in_progress
        and txn.deposit_collection_status != txn.COLLECT_SUCCESS
        and can_collect_deposit
        and dispute_hold_seconds_remaining is not None
        and dispute_hold_seconds_remaining <= (48 * 60 * 60)
    )

    return_review_completed = bool(txn.return_lender_confirmed or txn.return_lender_video_url)
    return_pin_available = bool(txn.return_handover_pin)
    checkout_pin_available = bool(txn.checkout_handover_pin)
    deposit_funds_held = _is_deposit_funds_held(txn)
    deposit_proposal_iteration_count = _deposit_proposal_iterations(txn)
    deposit_proposal_iteration_limit = 5
    deposit_proposal_progress_pct = int((deposit_proposal_iteration_count / deposit_proposal_iteration_limit) * 100)
    deposit_proposal_warning_text = _deposit_iteration_warning_text(deposit_proposal_iteration_count)

    missing_rental_voided = _is_missing_rental_voided(txn)

    feedback_statuses = (
        txn.RENTAL_RETURNED_DEPOSIT_RETURNED,
        txn.AWAITING_FEEDBACK,
        txn.RENTAL_PROCESS_COMPLETED,
        txn.FEEDBACK_ONE_SIDED,
        txn.RENTAL_PROCESS_COMPLETED_ONE_SIDED,
        txn.RENTAL_PROCESS_COMPLETED_NO_FEEDBACK,
    )
    feedback_stage = txn.transaction_status in feedback_statuses or (
        missing_rental_voided and txn.transaction_status == txn.CANCEL_ACCEPTED and is_renter
    )
    feedback_left_by_me = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=request.user,
    ).exists()
    feedback_from_lender = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=txn.user_passive,
        left_for=txn.user_aggressive,
    ).first()
    feedback_from_renter = TransactionFeedback.objects.filter(
        transaction=txn,
        left_by=txn.user_aggressive,
        left_for=txn.user_passive,
    ).first()
    feedback_prompt_required = feedback_stage and not feedback_left_by_me
    feedback_both_complete = bool(feedback_from_lender and feedback_from_renter)
    active_dispute_case = txn.dispute_cases.order_by('-created').first()
    dispute_final_statement_deadline = _dispute_final_statement_deadline(active_dispute_case)
    dispute_final_statement_seconds_remaining = None
    if dispute_final_statement_deadline:
        dispute_final_statement_seconds_remaining = int((dispute_final_statement_deadline - now_ts).total_seconds())
    dispute_final_statement_open = bool(
        active_dispute_case
        and dispute_final_statement_deadline
        and timezone.now() <= dispute_final_statement_deadline
        and (
            (is_lender and not active_dispute_case.lender_final_statement_at)
            or (is_renter and not active_dispute_case.borrower_final_statement_at)
        )
    )

    user_feedback_breakdowns = get_user_feedback_breakdown_map([
        txn.user_passive_id,
        txn.user_aggressive_id,
    ])
    lender_feedback_stats = user_feedback_breakdowns.get(txn.user_passive_id, {})
    renter_feedback_stats = user_feedback_breakdowns.get(txn.user_aggressive_id, {})

    # Get user's saved payment methods
    user_payment_methods = []
    if is_renter:
        user_payment_methods = request.user.payment_methods.all()

    workflow_payload = txn.get_workflow_payload()
    user_allowed_actions = txn.get_allowed_actions_for_user(request.user)

    context = {
        'transaction': txn,
        'charges': charges,
        'messages_': messages_,
        'show_message_subject': False,
        'total_px': total_px,
        'txnImages': txn_images,
        'total_items': total_items,
        'total_fees': total_fees,
        'step': step,
        'next_action': next_action,
        'workflow_stage': workflow_payload['current_stage'],
        'workflow_stage_label': workflow_payload['current_label'],
        'workflow_timeline': workflow_payload['timeline'],
        'workflow_payload': workflow_payload,
        'allowed_actions': user_allowed_actions,
        'workflow_allowed_actions': workflow_payload.get('allowed_actions', []),
        'is_lender': is_lender,
        'is_renter': is_renter,
        'today': today,
        'now_ts': now_ts,
        'contract_deadline': contract_deadline,
        'contract_deadline_iso': contract_deadline.isoformat() if contract_deadline else '',
        'contract_seconds_remaining': contract_seconds_remaining,
        'contract_seconds_remaining_display': _format_seconds(contract_seconds_remaining),
        'lender_contract_resend_available': lender_contract_resend_available,
        'can_collect_deposit': can_collect_deposit,
        'has_verified_payment_card': has_verified_payment_card,
        'needs_payment_card': needs_payment_card,
        'rental_start_blocked_by_missing_card': rental_start_blocked_by_missing_card,
        'setup_intent_client_secret': setup_intent_client_secret,
        'setup_intent_id': setup_intent_id,
        'can_setup_deposit_card': can_setup_deposit_card,
        'dispute_in_progress': dispute_in_progress,
        'dispute_hold_deadline': dispute_hold_deadline,
        'dispute_hold_seconds_remaining': dispute_hold_seconds_remaining,
        'urgent_dispute_funds_action': urgent_dispute_funds_action,
        'return_review_completed': return_review_completed,
        'return_pin_available': return_pin_available,
        'checkout_pin_available': checkout_pin_available,
        'deposit_funds_held': deposit_funds_held,
        'deposit_proposal_iteration_count': deposit_proposal_iteration_count,
        'deposit_proposal_iteration_limit': deposit_proposal_iteration_limit,
        'deposit_proposal_progress_pct': deposit_proposal_progress_pct,
        'deposit_proposal_warning_text': deposit_proposal_warning_text,
        'feedback_stage': feedback_stage,
        'feedback_left_by_me': feedback_left_by_me,
        'feedback_prompt_required': feedback_prompt_required,
        'feedback_both_complete': feedback_both_complete,
        'feedback_from_lender': feedback_from_lender,
        'feedback_from_renter': feedback_from_renter,
        'missing_rental_voided': missing_rental_voided,
        'active_dispute_case': active_dispute_case,
        'dispute_final_statement_deadline': dispute_final_statement_deadline,
        'dispute_final_statement_seconds_remaining': dispute_final_statement_seconds_remaining,
        'dispute_final_statement_seconds_display': _format_seconds(dispute_final_statement_seconds_remaining),
        'dispute_final_statement_open': dispute_final_statement_open,
        'lender_feedback_stats': lender_feedback_stats,
        'renter_feedback_stats': renter_feedback_stats,
        'stripe_publishable_key': getattr(settings, 'STRIPE_CONNECT_PUBLIC_KEY', ''),
        'user_payment_methods': user_payment_methods,
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
        'message_turnstile_required': message_turnstile_required,
        'txn_live_state_signature': _build_transaction_live_state(txn)['state_signature'],
        'txn_live_poll_interval_ms': int(getattr(settings, 'TRANSACTION_LIVE_POLL_SECONDS', 3)) * 1000,
    }
    return render(request, 'transaction/view_transaction.html', context)


@login_required
def card_setup_status(request, transaction_reference=None):
    txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
    if txn.user_passive != request.user and txn.user_aggressive != request.user:
        raise Http404

    if (
        txn.deposit_card_setup_status == txn.CARD_READY
        and txn.deposit_test_hold_status == txn.TEST_HOLD_SUCCESS
    ):
        state = 'completed'
        message = (
            f"Card ready: {txn.deposit_card_brand or 'Card'} ending {txn.deposit_card_last4 or 'xxxx'}. "
            "The £0.30 verification hold succeeded."
        )
    elif (
        txn.deposit_card_setup_status == txn.CARD_FAILED
        or txn.deposit_test_hold_status == txn.TEST_HOLD_FAILED
    ):
        state = 'failed'
        message = 'Card verification failed. Please try again or use a different card.'
    else:
        state = 'processing'
        message = 'Card verification in progress. This usually takes a few seconds.'

    return JsonResponse(
        {
            'state': state,
            'message': message,
            'card_setup_status': txn.deposit_card_setup_status,
            'test_hold_status': txn.deposit_test_hold_status,
            'card_brand': txn.deposit_card_brand,
            'card_last4': txn.deposit_card_last4,
            'updated': txn.amended.isoformat() if txn.amended else '',
        }
    )


@login_required
@ajax_required
def transaction_add_message(request):
    transaction_ref = request.GET.get('transaction_ref', None)
    message = request.GET.get('message', None)
    status = 'NOK'
    txn = get_object_or_404(Transaction, transaction_reference=transaction_ref)
    if txn.user_passive == request.user or txn.user_aggressive == request.user:
        messages.success(request, 'message added')
        status = 'OK'
        if message is not None and message != '':
            txn_message = TransactionMessage()
            txn_message.user_from = request.user
            if txn.user_passive == request.user:
                txn_message.user_to = txn.user_aggressive
            else:
                txn_message.user_to = txn.user_passive
            txn_message.transaction = txn
            txn_message.description = message
            # txn_message.subject = txn.get_payment_status_display()
            txn_message.save()

    content = {
        'status' : status
    }
    return JsonResponse(content)

@login_required
@ajax_required
def set_payment_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy payment endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

@login_required
@ajax_required
def set_product_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy product endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

    
@login_required
@ajax_required
def set_transaction_state(request):
    return JsonResponse({
        'status': 'NOK',
        'message': 'Legacy transaction endpoint disabled. Use the rental workflow actions on the transaction page.',
    })

@login_required
def raise_dispute(request, transaction_reference=None):
    transaction = None
    txn_message = TransactionMessage()
    if request.method=='POST':        
        # TODO: need to check txn belongs to user
        txn = get_object_or_404(Transaction, transaction_reference=request.POST['transaction_reference'])
        if txn.user_passive == request.user or txn.user_aggressive == request.user:
            txn_messsage_form = TransactionMessageAddForm(instance=txn_message,
                                                        data=request.POST,
                                                        files=request.FILES)
            if txn_messsage_form.is_valid():
                txn_message = txn_messsage_form.save(commit=False)
                txn_message.user_from = request.user
                if txn.user_passive == request.user:
                    txn_message.user_to =  txn.user_aggressive
                else:
                    txn_message.user_to =  txn.user_passive
                txn_message.include_admin = True
                txn_message.transaction = txn
                txn_message.save()
                txn.transaction_status = txn.DISPUTE_REQUESTED
                txn.save()
                

                # Update all orderImage records with the new id
                txn_msg_image_ids = request.POST['txn_image_id'].split()
                for txn_msg_image_id in txn_msg_image_ids:
                    try:
                        txn_msg_image = TransactionMessageImage.objects.get(pk=txn_msg_image_id)
                        if request.user == txn_msg_image.user:
                            txn_msg_image.txn_message = txn_message
                            txn_msg_image.saveNoImageModification()
                    except TransactionMessageImage.DoesNotExist:
                        raise Http404("Transaction Message Image does not exist")

                messages.success(request, 'Dispute request raised to Admin team')
                product_url = request.build_absolute_uri(reverse('transaction:view_transaction' ,
                        kwargs={'transaction_reference': txn_message.transaction.transaction_reference}))
                return redirect(product_url)
            else:
                messages.error(request, 'Error in validation')
                txn_message_image_form = TransactionMessageImageForm(instance=transaction)
                context = {
                    'transaction' : transaction,
                    'txn_message_form' : txn_message_form,
                    'txn_message_image_form' : txn_message_image_form
                }
                return render(request, 'transaction/raise_dispute.html', context)
        else:
            return Http404
    else:
        txn = get_object_or_404(Transaction, transaction_reference=transaction_reference)
        if txn.user_passive == request.user or txn.user_aggressive == request.user:
            txn_message_form = TransactionMessageAddForm(instance=transaction)
            txn_message_image_form = TransactionMessageImageForm(instance=transaction)

            context = {
                'transaction' : txn,
                'txn_message_form' : txn_message_form,
                'txn_message_image_form' : txn_message_image_form
            }
            return render(request, 'transaction/raise_dispute.html', context)
        else:
            return Http404

@ajax_required
def transpact_refresh(request):
    content = {
        'status' : 'NOK',
        'message': 'Transpact refresh is disabled in the new rental workflow.',
    }
    return JsonResponse(content)


@staff_member_required
def transaction_scenario_dashboard(request):
    if getattr(settings, 'ENVIRONMENT_NAME', '').lower() == 'production':
        raise Http404
    scenarios = (
        Transaction.objects.filter(transpact_text_status__startswith='SCENARIO:')
        .select_related('user_passive', 'user_aggressive', 'order_passive', 'product')
        .order_by('-amended', '-created')
    )
    payment_attempts = PaymentAttempt.objects.all()
    payment_totals = {
        'success': payment_attempts.filter(status=PaymentAttempt.STATUS_SUCCESS).count(),
        'failure': payment_attempts.filter(status=PaymentAttempt.STATUS_FAILURE).count(),
        'pending': payment_attempts.filter(status=PaymentAttempt.STATUS_PENDING).count(),
    }
    return render(request, 'transaction/scenario_dashboard.html', {
        'scenarios': scenarios,
        'payment_totals': payment_totals,
    })


@staff_member_required
def payment_summary(request):
    if getattr(settings, 'ENVIRONMENT_NAME', '').lower() == 'production':
        raise Http404
    attempts = PaymentAttempt.objects.all()
    totals = {
        'success': attempts.filter(status=PaymentAttempt.STATUS_SUCCESS).count(),
        'failure': attempts.filter(status=PaymentAttempt.STATUS_FAILURE).count(),
        'pending': attempts.filter(status=PaymentAttempt.STATUS_PENDING).count(),
    }
    by_point = (
        attempts.values('failure_point')
        .annotate(total=models.Count('id'))
        .order_by('failure_point')
    )
    latest = attempts.select_related('transaction').order_by('-created_at')[:100]
    return render(request, 'transaction/payment_summary.html', {
        'attempts': latest,
        'totals': totals,
        'by_point': by_point,
    })


@csrf_exempt
def stripe_connect_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'NOK', 'message': 'POST required.'}, status=405)

    payload = request.body
    signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    result = stripe_connect_service.process_webhook(payload=payload, signature=signature)
    if not result.get('ok'):
        return JsonResponse({'status': 'NOK', 'message': result.get('error', 'Invalid webhook.')}, status=400)

    return JsonResponse({
        'status': 'OK',
        'event_type': result.get('event_type', 'unknown'),
        'provider': result.get('provider', 'unknown'),
    })

class TransactionMessageImageUpload(View):
    def post(self, request):
        # logger = logging.getLogger(__name__)
        data = {'is_valid': False}
        form = TransactionMessageImageForm(self.request.POST, self.request.FILES)
        transaction_reference = request.GET.get('transaction_reference', None)
        #TODO : add transaciton stuff
        if form.is_valid() and request.user is not None:
            image = form.save(commit=False)
            image.user = request.user
            image.save()
            data = {'is_valid': True, 
                    'txn_image_id': image.id ,
                    'image_name': image.image.name, 
                    'image_url': image.image.url}
        else:
            data = {'is_valid': False}
        return JsonResponse(data)
