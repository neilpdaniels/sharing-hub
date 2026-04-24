from django.contrib import admin
from .models import ReferencePrice

@admin.register(ReferencePrice)
class ReferencePrice(admin.ModelAdmin):
    list_display = ['title', 'price', 'primary_url']