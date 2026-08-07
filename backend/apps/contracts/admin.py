from django.contrib import admin
from .models import ContractTemplate, ContractDraft, ContractReview, ContractReviewFinding


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ['code', 'name_ko', 'category', 'is_active', 'version']
    list_filter = ['category', 'is_active']
    search_fields = ['code', 'name_ko', 'name_en']


@admin.register(ContractDraft)
class ContractDraftAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'status', 'user', 'created_at']
    list_filter = ['status']
    search_fields = ['title']


@admin.register(ContractReview)
class ContractReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'status', 'created_by', 'created_at']
    list_filter = ['status']
    search_fields = ['title']


@admin.register(ContractReviewFinding)
class ContractReviewFindingAdmin(admin.ModelAdmin):
    list_display = ['review', 'clause_ref', 'severity', 'category', 'order_index']
    list_filter = ['severity', 'category']
