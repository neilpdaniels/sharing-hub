from django.contrib import admin
from .models import Friendship, BlockedUser
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


@admin.register(BlockedUser)
class BlockedUserAdmin(SimpleHistoryAdmin):
    list_display = ('blocked_by', 'blocked_user', 'report_flagged', 'created_at')
    list_filter = ('report_flagged', 'created_at')
    search_fields = ('blocked_by__username', 'blocked_user__username')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Users', {
            'fields': ('blocked_by', 'blocked_user')
        }),
        ('Report Status', {
            'fields': ('report_flagged',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
