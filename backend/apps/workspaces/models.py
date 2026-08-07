"""
워크스페이스 / 프로젝트 모델 — schema.sql workspaces, projects 테이블 기반
"""
import uuid
from django.db import models


class Workspace(models.Model):
    """워크스페이스 — 최상위 컨테이너"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True, default='')
    settings = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='workspaces',
        db_column='created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces'
        ordering = ['-created_at']
        verbose_name = '워크스페이스'
        verbose_name_plural = '워크스페이스'

    def __str__(self):
        return self.name


class Project(models.Model):
    """프로젝트 — PJT/주제 단위 (공용 방 포함)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='projects'
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    is_shared = models.BooleanField(default=False, help_text='공용 프로젝트(반출 목적지)')
    icon = models.CharField(max_length=50, blank=True, default='')
    color = models.CharField(max_length=20, blank=True, default='')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='projects',
        db_column='created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']
        verbose_name = '프로젝트'
        verbose_name_plural = '프로젝트'

    def __str__(self):
        return f'{self.workspace.name} / {self.name}'
