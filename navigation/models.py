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
	STATUS_REVIEWED = 'REVIEWED'
	STATUS_APPROVED = 'APPROVED'
	STATUS_REJECTED = 'REJECTED'
	STATUS_CHOICES = [
		(STATUS_NEW, 'New'),
		(STATUS_REVIEWED, 'Reviewed'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_REJECTED, 'Rejected'),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='category_suggestions')
	category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='suggestions')
	name = models.CharField(max_length=120)
	description = models.TextField()
	photo = models.ImageField(upload_to='category_suggestions/', null=True, blank=True)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
	admin_notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.name} ({self.get_status_display()})'


