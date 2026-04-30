from django.contrib import admin

from .models import CategorySuggestion, SearchHistory

# Register your models here.


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
	list_display = ('search_term', 'location', 'user', 'searched_at')
	list_filter = ('searched_at',)
	search_fields = ('search_term', 'location', 'user__username')
	readonly_fields = ('searched_at',)


@admin.register(CategorySuggestion)
class CategorySuggestionAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'category', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('name', 'description', 'user__username', 'user__email')
	readonly_fields = ('created_at', 'updated_at')
