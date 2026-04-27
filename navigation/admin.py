from django.contrib import admin

from .models import CategorySuggestion

# Register your models here.


@admin.register(CategorySuggestion)
class CategorySuggestionAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'category', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('name', 'description', 'user__username', 'user__email')
	readonly_fields = ('created_at', 'updated_at')
