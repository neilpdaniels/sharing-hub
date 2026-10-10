from django.contrib import admin
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CategorySuggestion,
    CategorySuggestionImage,
    CategoryTaxonomyRecommendation,
    CategoryTaxonomyReview,
    SearchHistory,
)
from .services import (
    TaxonomyApplicationError,
    apply_taxonomy_recommendation,
    promote_category_suggestion,
    reject_category_suggestion,
)
from .tasks import (
    generate_category_suggestion_assets_task,
    review_category_suggestion,
    run_catalogue_taxonomy_review,
)

# Register your models here.


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
	list_display = ('search_term', 'location', 'user', 'searched_at')
	list_filter = ('searched_at',)
	search_fields = ('search_term', 'location', 'user__username')
	readonly_fields = ('searched_at',)


@admin.register(CategorySuggestion)
class CategorySuggestionAdmin(admin.ModelAdmin):
    change_list_template = 'admin/navigation/categorysuggestion/change_list.html'
    list_display = ('name', 'user', 'category', 'proposed_parent', 'status', 'processing_attempts', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description', 'user__username', 'user__email')
    readonly_fields = (
        'created_at', 'updated_at', 'normalized_name', 'duplicate_matches',
        'policy_result', 'quality_review', 'pipeline_state', 'pipeline_error',
        'processed_at', 'processing_attempts', 'reviewed_by', 'reviewed_at',
        'published_category', 'promoted_at', 'proposed_image_prompt',
    )
    fields = (
        'user', 'category', 'name', 'description', 'photo', 'status', 'admin_notes',
        'normalized_name', 'proposed_parent', 'proposed_description', 'proposed_image_prompt',
        'duplicate_matches', 'policy_result', 'quality_review', 'pipeline_state', 'pipeline_error',
        'processing_attempts', 'processed_at', 'reviewed_by', 'reviewed_at',
        'published_category', 'promoted_at', 'created_at', 'updated_at',
    )
    actions = ('queue_for_review', 'generate_image_candidates', 'promote_selected', 'reject_selected')

    @admin.action(description='Queue selected suggestions for AI review')
    def queue_for_review(self, request, queryset):
        if not settings.CATEGORY_AI_ENABLED:
            self.message_user(request, 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before queueing work.', messages.ERROR)
            return
        queued = 0
        for suggestion in queryset.exclude(status=CategorySuggestion.STATUS_APPROVED):
            suggestion.status = CategorySuggestion.STATUS_NEW
            suggestion.pipeline_error = ''
            suggestion.save(update_fields=['status', 'pipeline_error', 'updated_at'])
            review_category_suggestion.delay(suggestion.pk)
            queued += 1
        self.message_user(request, f'{queued} suggestion(s) queued for review.', messages.SUCCESS)

    @admin.action(description='Generate image candidates for selected screened suggestions')
    def generate_image_candidates(self, request, queryset):
        if not settings.CATEGORY_AI_ENABLED:
            self.message_user(request, 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before generating images.', messages.ERROR)
            return
        queued = 0
        for suggestion in queryset.filter(status=CategorySuggestion.STATUS_ASSET_REVIEW):
            generate_category_suggestion_assets_task.delay(suggestion.pk)
            queued += 1
        if queued:
            self.message_user(request, f'{queued} image job(s) queued. Monthly budget is checked by the worker.', messages.SUCCESS)
        else:
            self.message_user(request, 'Select suggestion(s) marked “Ready for staff image generation”.', messages.WARNING)

    @admin.action(description='Promote selected ready suggestions')
    def promote_selected(self, request, queryset):
        promoted = 0
        for suggestion in queryset:
            try:
                promote_category_suggestion(suggestion, request.user)
            except ValueError as exc:
                self.message_user(request, f'{suggestion.name}: {exc}', messages.ERROR)
            else:
                promoted += 1
        if promoted:
            self.message_user(request, f'{promoted} category suggestion(s) promoted and requester notified.', messages.SUCCESS)

    @admin.action(description='Reject selected suggestions and notify requester')
    def reject_selected(self, request, queryset):
        rejected = 0
        for suggestion in queryset.exclude(status=CategorySuggestion.STATUS_APPROVED):
            reject_category_suggestion(suggestion, request.user)
            rejected += 1
        if rejected:
            self.message_user(request, f'{rejected} requester(s) notified of the decision.', messages.SUCCESS)


@admin.register(CategorySuggestionImage)
class CategorySuggestionImageAdmin(admin.ModelAdmin):
    list_display = ('suggestion', 'is_selected', 'created_at')
    list_filter = ('is_selected', 'created_at')
    search_fields = ('suggestion__name',)
    readonly_fields = ('created_at',)

    def save_model(self, request, obj, form, change):
        # Selecting an image candidate should replace any older selection for
        # that suggestion, keeping the publish action unambiguous.
        super().save_model(request, obj, form, change)
        if obj.is_selected:
            CategorySuggestionImage.objects.filter(suggestion=obj.suggestion).exclude(pk=obj.pk).update(is_selected=False)


@admin.register(CategoryTaxonomyReview)
class CategoryTaxonomyReviewAdmin(admin.ModelAdmin):
    change_list_template = 'admin/navigation/categorytaxonomyreview/change_list.html'
    list_display = ('id', 'status', 'requested_by', 'created_at', 'completed_at', 'recommendation_count')
    list_filter = ('status', 'created_at')
    search_fields = ('error',)
    readonly_fields = ('requested_by', 'status', 'recommendations_link', 'snapshot', 'llm_analysis', 'crew_critique', 'error', 'started_at', 'completed_at', 'created_at')
    fields = ('requested_by', 'status', 'recommendations_link', 'snapshot', 'llm_analysis', 'crew_critique', 'error', 'started_at', 'completed_at', 'created_at')
    actions = ('apply_all_approved_recommendations', 'ignore_all_pending_recommendations')

    def has_add_permission(self, request):
        return False

    def recommendation_count(self, obj):
        return obj.recommendations.count()
    recommendation_count.short_description = 'Recommendations'

    def recommendations_link(self, obj):
        if not obj or not obj.pk:
            return 'Available after the review has been created.'
        url = reverse('admin:navigation_categorytaxonomyrecommendation_changelist')
        return format_html(
            '<a class="button" href="{}?review__id__exact={}">View {} recommendation(s)</a>',
            url,
            obj.pk,
            obj.recommendations.count(),
        )
    recommendations_link.short_description = 'Recommendations'

    def get_urls(self):
        return [
            path('run-now/', self.admin_site.admin_view(self.run_now), name='navigation_categorytaxonomyreview_run_now'),
        ] + super().get_urls()

    def run_now(self, request):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not settings.CATEGORY_AI_ENABLED:
            self.message_user(request, 'Category AI is disabled. Set CATEGORY_AI_ENABLED=1 before running a review.', messages.ERROR)
            return redirect(reverse('admin:navigation_categorytaxonomyreview_changelist'))
        review = CategoryTaxonomyReview.objects.create(requested_by=request.user)
        transaction.on_commit(lambda: run_catalogue_taxonomy_review.delay(review.pk))
        self.message_user(request, 'Catalogue review queued. Refresh this list shortly to see its recommendations.', messages.SUCCESS)
        return redirect(reverse('admin:navigation_categorytaxonomyreview_changelist'))

    @admin.action(description='Apply all approved recommendations in selected review(s)')
    def apply_all_approved_recommendations(self, request, queryset):
        applied = 0
        errors = []
        for review in queryset:
            for recommendation in review.recommendations.filter(status=CategoryTaxonomyRecommendation.STATUS_APPROVED):
                try:
                    apply_taxonomy_recommendation(recommendation, request.user)
                except TaxonomyApplicationError as exc:
                    errors.append(f'{recommendation.title}: {exc}')
                else:
                    applied += 1
        if applied:
            self.message_user(request, f'Applied {applied} category-tree change(s).', messages.SUCCESS)
        for error in errors:
            self.message_user(request, error, messages.ERROR)

    @admin.action(description='Ignore all pending recommendations in selected review(s)')
    def ignore_all_pending_recommendations(self, request, queryset):
        count = 0
        for review in queryset:
            count += review.recommendations.filter(
                status__in=[
                    CategoryTaxonomyRecommendation.STATUS_PENDING,
                    CategoryTaxonomyRecommendation.STATUS_NEEDS_HUMAN,
                ]
            ).update(
                status=CategoryTaxonomyRecommendation.STATUS_REJECTED,
                reviewed_by=request.user,
                reviewed_at=timezone.now(),
            )
        self.message_user(request, f'Ignored {count} pending recommendation(s).', messages.SUCCESS)


@admin.register(CategoryTaxonomyRecommendation)
class CategoryTaxonomyRecommendationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recommendation_type', 'status', 'review', 'position', 'reviewed_by', 'created_at')
    list_filter = ('recommendation_type', 'status', 'review__created_at')
    search_fields = ('title', 'rationale', 'admin_notes')
    readonly_fields = ('review', 'position', 'recommendation_type', 'title', 'rationale', 'evidence', 'ai_critique', 'implementation_result', 'created_at')
    fields = ('review', 'position', 'recommendation_type', 'title', 'rationale', 'evidence', 'proposed_action', 'ai_critique', 'implementation_result', 'status', 'admin_notes', 'reviewed_by', 'reviewed_at', 'created_at')
    actions = ('apply_selected_changes', 'approve_for_manual_implementation', 'reject_recommendations')

    def _set_status(self, request, queryset, status):
        queryset.update(status=status, reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description='Approve selected recommendations for manual implementation')
    def approve_for_manual_implementation(self, request, queryset):
        self._set_status(request, queryset, CategoryTaxonomyRecommendation.STATUS_APPROVED)
        self.message_user(request, 'Approved. Use “Apply all approved” on the review, or “Apply selected” here, to change the tree.', messages.SUCCESS)

    @admin.action(description='Apply selected approved catalogue changes now')
    def apply_selected_changes(self, request, queryset):
        applied = 0
        errors = []
        for recommendation in queryset.exclude(status=CategoryTaxonomyRecommendation.STATUS_IMPLEMENTED):
            try:
                apply_taxonomy_recommendation(recommendation, request.user)
            except TaxonomyApplicationError as exc:
                errors.append(f'{recommendation.title}: {exc}')
            else:
                applied += 1
        if applied:
            self.message_user(request, f'Applied {applied} catalogue change(s).', messages.SUCCESS)
        for error in errors:
            self.message_user(request, error, messages.ERROR)

    @admin.action(description='Reject selected recommendations')
    def reject_recommendations(self, request, queryset):
        self._set_status(request, queryset, CategoryTaxonomyRecommendation.STATUS_REJECTED)
        self.message_user(request, 'Recommendations rejected; no catalogue data was changed.', messages.SUCCESS)
