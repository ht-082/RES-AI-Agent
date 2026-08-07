from django.contrib import admin
from .models import Conversation, Message, MessageSource, MessageAttachment, ConversationShare


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'use_internal_docs', 'is_shared', 'last_message_at', 'created_at']
    list_filter = ['use_internal_docs', 'is_shared']
    search_fields = ['title']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'used_internal_docs', 'status', 'created_at']
    list_filter = ['role', 'status']

    def content_preview(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    content_preview.short_description = '내용'


@admin.register(MessageSource)
class MessageSourceAdmin(admin.ModelAdmin):
    list_display = ['short_label', 'display_title', 'page_number', 'location_label', 'score', 'rank']
    search_fields = ['display_title']


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'file_type', 'file_size', 'created_at']


@admin.register(ConversationShare)
class ConversationShareAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'shared_to_project', 'share_type', 'shared_by', 'created_at']
