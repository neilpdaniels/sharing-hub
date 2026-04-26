from django.conf import settings
from django.db import models


class ProductListingRequest(models.Model):
    STATUS_NEW = 'NEW'
    STATUS_REVIEWED = 'REVIEWED'
    STATUS_FULFILLED = 'FULFILLED'

    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_FULFILLED, 'Fulfilled'),
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_listing_requests',
    )
    category_slug = models.SlugField(max_length=120, blank=True)
    category_title = models.CharField(max_length=255, blank=True)
    product_name = models.CharField(max_length=255)
    request_details = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        requester = self.requested_by.username if self.requested_by else 'anonymous'
        return f"{self.product_name} ({requester})"
