from django.contrib import admin
from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'file_type', 'status', 'project', 'file_size', 'created_at']
    list_filter = ['status', 'file_type']
    search_fields = ['title', 'original_filename']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'page_number', 'section_title', 'token_count']
    list_filter = ['document__file_type']
    search_fields = ['content', 'section_title']
