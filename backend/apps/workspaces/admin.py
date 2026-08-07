from django.contrib import admin
from .models import Workspace, Project


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_by', 'created_at']
    search_fields = ['name', 'slug']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'workspace', 'is_shared', 'created_by', 'created_at']
    list_filter = ['is_shared', 'workspace']
    search_fields = ['name']
