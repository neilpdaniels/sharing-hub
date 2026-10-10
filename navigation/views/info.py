from datetime import datetime
import logging
import urllib.parse

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction as db_transaction
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import cache_page
from haystack.forms import SearchForm
from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet

import common.helpers
from common.decorators import ajax_required
from common.geocoding import PostcodeGeocoder
from common.security import verify_turnstile_token
from common.models import (
    BestPricedForCategory, BestPricedForProduct, Category, CategoryTag,
    Order, Product, System,
)
from common.tasks import listEmptyCategories, runStaticMigration
from transaction.models import Transaction

from ..forms import CategorySuggestionForm
from ..models import SearchHistory
from ..rate_limits import consume_submission_quota
from ..tasks import review_category_suggestion


logger = logging.getLogger(__name__)


@login_required
def suggestCategory(request):
    current_category = None
    category_id = request.GET.get('category_id') or request.POST.get('category_id')
    if category_id:
        try:
            current_category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            current_category = None

    if request.method == 'POST':
        form = CategorySuggestionForm(request.POST, request.FILES)
        try:
            profile = request.user.profile
        except Exception:
            profile = None
        if not profile or not profile.email_confirmed or not profile.mobile_verified:
            form.add_error(
                None,
                'Please verify your email address and UK mobile number before suggesting a category.',
            )
        elif not settings.CATEGORY_AI_ENABLED:
            form.add_error(None, 'Category suggestions are temporarily unavailable while we update this service.')
        else:
            token = (request.POST.get('cf-turnstile-response') or '').strip()
            if not verify_turnstile_token(
                token,
                request.META.get('REMOTE_ADDR', ''),
                expected_action='category_suggestion',
            ):
                form.add_error(None, 'Human verification failed. Please complete the checkbox and try again.')
        if form.is_valid():
            name = ' '.join(form.cleaned_data['name'].split())
            if Category.objects.filter(title__iexact=name).exists():
                form.add_error('name', 'That category already exists. Please browse the existing categories first.')
            else:
                limit = consume_submission_quota(request)
                suggestion = form.save(commit=False)
                suggestion.name = name
                suggestion.user = request.user
                suggestion.category = current_category
                if not limit.allowed:
                    # Preserve potentially useful requests, but do not let a
                    # burst of submissions automatically consume AI credits.
                    suggestion.status = suggestion.STATUS_MANUAL_REVIEW
                    suggestion.pipeline_state = {
                        'requires_manual_ai_review': True,
                        'rate_limit_reason': limit.message,
                    }
                suggestion.save()
                if limit.allowed:
                    # Queue after the database commit: workers can never race ahead of
                    # the row they need to read.
                    db_transaction.on_commit(lambda: review_category_suggestion.delay(suggestion.pk))
                    messages.success(
                        request,
                        'Thanks. We are checking your category suggestion and will email you when an admin has decided.',
                    )
                else:
                    messages.success(
                        request,
                        'Thanks. Your suggestion has been saved for manual review before any automated checks are run.',
                    )

                next_url = request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('homepage')
    else:
        form = CategorySuggestionForm()

    context = {
        'form': form,
        'current_category': current_category,
        'next': request.GET.get('next', ''),
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
    }
    return render(request, 'navigation/suggest_category.html', context)
