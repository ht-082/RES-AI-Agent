from django.contrib import admin

from .models import BudgetEntry, CommunityIssue, PermitDocument, PermitStage, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'capacity_mw', 'energy_type', 'lifecycle',
                    'status', 'sido', 'pm_name']
    list_filter = ['lifecycle', 'energy_type', 'status']
    search_fields = ['name', 'slug', 'location', 'sido']


@admin.register(PermitStage)
class PermitStageAdmin(admin.ModelAdmin):
    list_display = ['site', 'stage_no', 'name', 'tier', 'status', 'progress_pct']
    list_filter = ['status', 'tier']
    search_fields = ['name', 'site__name']


@admin.register(PermitDocument)
class PermitDocumentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'stage', 'version', 'is_current', 'uploaded_at']
    list_filter = ['is_current']
    search_fields = ['file_name']


@admin.register(BudgetEntry)
class BudgetEntryAdmin(admin.ModelAdmin):
    list_display = ['site', 'category', 'amount_krw', 'exec_date']
    list_filter = ['category']


@admin.register(CommunityIssue)
class CommunityIssueAdmin(admin.ModelAdmin):
    list_display = ['site', 'title', 'issue_type', 'status', 'issue_date']
    list_filter = ['status', 'issue_type']
    search_fields = ['title']
