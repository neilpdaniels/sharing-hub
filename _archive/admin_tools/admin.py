from django.contrib import admin

from .models import ProductListingRequest


@admin.register(ProductListingRequest)
class ProductListingRequestAdmin(admin.ModelAdmin):
    list_display = (
        'product_name',
        'requested_by',
        'category_title',
        'status',
        'created_at',
    )
    list_filter = ('status', 'created_at', 'category_title')
    search_fields = ('product_name', 'request_details', 'requested_by__username', 'requested_by__email')
    readonly_fields = ('created_at', 'updated_at')
