from django.contrib import admin
from .models import Friendship
from simple_history.admin import SimpleHistoryAdmin


@admin.register(Friendship)
class FriendshipAdmin(SimpleHistoryAdmin):
    list_display = ('user_from', 'user_to', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('user_from__username', 'user_to__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Users', {
            'fields': ('user_from', 'user_to')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
