from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.template.defaultfilters import slugify

from common.helpers import RandomFileName


class ProductDraft(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_GENERATED = 'generated'
    STATUS_READY = 'ready'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_GENERATED, 'Generated'),
        (STATUS_READY, 'Ready'),
        (STATUS_PUBLISHED, 'Published'),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, blank=True)
    parent_category = models.ForeignKey(
        'common.Category',
        on_delete=models.PROTECT,
        related_name='product_drafts',
    )
    description = models.TextField(blank=True, default='')
    prompt = models.TextField(blank=True, default='')
    image = models.ImageField(upload_to=RandomFileName('images/product_drafts/'), blank=True, null=True)
    published_product = models.ForeignKey(
        'common.Product',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='workflow_drafts',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at', '-created_at')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)

