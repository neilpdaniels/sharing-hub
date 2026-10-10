from django.db import models
from django.conf import settings

from common.models import Category

# Create your models here.


class SearchHistory(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='search_history',
	)
	search_term = models.CharField(max_length=255, blank=True, default='')
	location = models.CharField(max_length=255, blank=True, default='')
	ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
	searched_at = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		ordering = ['-searched_at']

	def __str__(self):
		parts = [self.search_term or '(no term)', self.location or '(no location)']
		return f'{" | ".join(parts)} @ {self.searched_at:%Y-%m-%d %H:%M}'


class CategorySuggestion(models.Model):
	STATUS_NEW = 'NEW'
	STATUS_SCREENING = 'SCREENING'
	STATUS_DUPLICATE = 'DUPLICATE'
	STATUS_POLICY_REJECTED = 'POLICY_REJECTED'
	STATUS_MANUAL_REVIEW = 'MANUAL_REVIEW'
	STATUS_ASSET_REVIEW = 'ASSET_REVIEW'
	STATUS_GENERATING = 'GENERATING'
	STATUS_QUALITY_REVIEW = 'QUALITY_REVIEW'
	STATUS_ADMIN_REVIEW = 'ADMIN_REVIEW'
	STATUS_FAILED = 'FAILED'
	STATUS_REVIEWED = 'REVIEWED'
	STATUS_APPROVED = 'APPROVED'
	STATUS_REJECTED = 'REJECTED'
	STATUS_CHOICES = [
		(STATUS_NEW, 'Queued'),
		(STATUS_SCREENING, 'AI screening'),
		(STATUS_DUPLICATE, 'Possible duplicate'),
		(STATUS_POLICY_REJECTED, 'Not suitable'),
		(STATUS_MANUAL_REVIEW, 'Needs manual AI review'),
		(STATUS_ASSET_REVIEW, 'Ready for staff image generation'),
		(STATUS_GENERATING, 'Generating catalogue image'),
		(STATUS_QUALITY_REVIEW, 'AI quality review'),
		(STATUS_ADMIN_REVIEW, 'Ready for admin review'),
		(STATUS_FAILED, 'Automation failed'),
		(STATUS_REVIEWED, 'Reviewed'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_REJECTED, 'Rejected'),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='category_suggestions')
	category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='suggestions')
	name = models.CharField(max_length=120)
	description = models.TextField()
	photo = models.ImageField(upload_to='category_suggestions/', null=True, blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
	admin_notes = models.TextField(blank=True)
	# The source suggestion is intentionally retained separately from AI output so
	# an administrator can always see exactly what a member requested.
	normalized_name = models.CharField(max_length=120, blank=True, default='')
	proposed_parent = models.ForeignKey(
		Category,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='proposed_category_suggestions',
	)
	proposed_description = models.TextField(blank=True, default='')
	proposed_image_prompt = models.TextField(blank=True, default='')
	duplicate_matches = models.JSONField(default=list, blank=True)
	policy_result = models.JSONField(default=dict, blank=True)
	quality_review = models.JSONField(default=dict, blank=True)
	pipeline_state = models.JSONField(default=dict, blank=True)
	pipeline_error = models.TextField(blank=True, default='')
	processing_attempts = models.PositiveSmallIntegerField(default=0)
	processed_at = models.DateTimeField(null=True, blank=True)
	reviewed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='reviewed_category_suggestions',
	)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	published_category = models.ForeignKey(
		Category,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='published_from_suggestions',
	)
	promoted_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.name} ({self.get_status_display()})'


class CategorySuggestionImage(models.Model):
	"""An auditable image candidate generated for a category suggestion."""

	suggestion = models.ForeignKey(
		CategorySuggestion,
		on_delete=models.CASCADE,
		related_name='generated_images',
	)
	image = models.ImageField(upload_to='category_suggestions/generated/')
	prompt = models.TextField(blank=True, default='')
	review = models.JSONField(default=dict, blank=True)
	is_selected = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at', 'id']

	def __str__(self):
		return f'Generated image {self.pk} for {self.suggestion.name}'


class CategoryTaxonomyReview(models.Model):
	"""A read-only AI assessment of the live catalogue taxonomy."""

	STATUS_QUEUED = 'QUEUED'
	STATUS_RUNNING = 'RUNNING'
	STATUS_READY = 'READY'
	STATUS_FAILED = 'FAILED'
	STATUS_CHOICES = (
		(STATUS_QUEUED, 'Queued'),
		(STATUS_RUNNING, 'Running'),
		(STATUS_READY, 'Ready for human review'),
		(STATUS_FAILED, 'Failed'),
	)

	requested_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='requested_taxonomy_reviews',
	)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
	snapshot = models.JSONField(default=dict, blank=True)
	llm_analysis = models.JSONField(default=dict, blank=True)
	crew_critique = models.JSONField(default=dict, blank=True)
	error = models.TextField(blank=True, default='')
	started_at = models.DateTimeField(null=True, blank=True)
	completed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'Catalogue review {self.pk} ({self.get_status_display()})'


class CategoryTaxonomyRecommendation(models.Model):
	"""A human-approved-only recommendation from a taxonomy review."""

	TYPE_MISSING = 'MISSING'
	TYPE_DUPLICATE = 'DUPLICATE'
	TYPE_MOVE = 'MOVE'
	TYPE_SPLIT = 'SPLIT'
	TYPE_RETIRE = 'RETIRE'
	TYPE_ATTRIBUTE = 'ATTRIBUTE'
	TYPE_KEEP = 'KEEP'
	TYPE_CHOICES = (
		(TYPE_MISSING, 'Missing category'),
		(TYPE_DUPLICATE, 'Possible duplicate / merge'),
		(TYPE_MOVE, 'Move in tree'),
		(TYPE_SPLIT, 'Split broad category'),
		(TYPE_RETIRE, 'Retire thin category'),
		(TYPE_ATTRIBUTE, 'Add a browse attribute'),
		(TYPE_KEEP, 'Keep as-is observation'),
	)
	STATUS_PENDING = 'PENDING'
	STATUS_NEEDS_HUMAN = 'NEEDS_HUMAN'
	STATUS_APPROVED = 'APPROVED'
	STATUS_REJECTED = 'REJECTED'
	STATUS_IMPLEMENTED = 'IMPLEMENTED'
	STATUS_CHOICES = (
		(STATUS_PENDING, 'Pending human review'),
		(STATUS_NEEDS_HUMAN, 'Needs extra human scrutiny'),
		(STATUS_APPROVED, 'Approved for manual implementation'),
		(STATUS_REJECTED, 'Rejected'),
		(STATUS_IMPLEMENTED, 'Implemented manually'),
	)

	review = models.ForeignKey(CategoryTaxonomyReview, on_delete=models.CASCADE, related_name='recommendations')
	position = models.PositiveSmallIntegerField()
	recommendation_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
	title = models.CharField(max_length=255)
	rationale = models.TextField()
	evidence = models.JSONField(default=list, blank=True)
	proposed_action = models.JSONField(default=dict, blank=True)
	ai_critique = models.JSONField(default=dict, blank=True)
	implementation_result = models.JSONField(default=dict, blank=True)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
	admin_notes = models.TextField(blank=True, default='')
	reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['review', 'position']
		unique_together = ('review', 'position')

	def __str__(self):
		return f'{self.get_recommendation_type_display()}: {self.title}'
