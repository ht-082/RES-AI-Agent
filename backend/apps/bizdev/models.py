"""
사업개발 포트폴리오 모델 — Re-project-mng ver2.0 Supabase 스키마 이관.

원본 supabase/01_schema.sql + 05_migration_v2.sql 의 sites/permit_stages/
permit_documents/budget_entries/community_issues 를 Django 로 옮겼다.
2차 범위 테이블(policy_advice, ordinance_alerts 등)은 만들지 않는다.
"""
import uuid

from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q

from .constants import (
    BUDGET_CATEGORY_CHOICES, ENERGY_CHOICES, ISSUE_STATUS_CHOICES,
    ISSUE_TYPE_CHOICES, LIFECYCLE_CHOICES, RISK_LEVEL_CHOICES,
    STATUS_CHOICES, TIER_CHOICES,
)


class Site(models.Model):
    """사업지 — 개발/운영 재생에너지 자산"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=150)
    capacity_mw = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    location = models.CharField(max_length=100, blank=True, default='')
    sido = models.CharField(max_length=30, blank=True, default='',
                            help_text='지자체(시·군) — 계통/조례 조회 키')
    facility_type = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    risk_tag = models.CharField(max_length=50, blank=True, default='')
    risk_level = models.CharField(max_length=2, choices=RISK_LEVEL_CHOICES,
                                  blank=True, default='')
    pm = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bizdev_sites', db_column='pm_id')
    pm_name = models.CharField(max_length=50, blank=True, default='',
                               help_text='표시용 비정규화 — pm 미연결 시드 대비')
    target_ntp = models.CharField(max_length=20, blank=True, default='')
    approved_budget_krw = models.BigIntegerField(default=0)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    energy_type = models.CharField(max_length=10, choices=ENERGY_CHOICES, default='solar')
    lifecycle = models.CharField(max_length=5, choices=LIFECYCLE_CHOICES, default='dev')
    annual_gwh = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    cod = models.CharField(max_length=20, blank=True, default='')
    address_detail = models.TextField(blank=True, default='',
                                      help_text='백데이터 — 목록 응답에는 내보내지 않는다')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_sites'
        ordering = ['created_at']
        indexes = [models.Index(fields=['lifecycle'])]
        verbose_name = '사업지'
        verbose_name_plural = '사업지'

    def __str__(self):
        return f'{self.name} ({self.capacity_mw}MW)'


class PermitStage(models.Model):
    """인허가 단계 — 12단계 기본 + 사용자 추가 단계"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='stages')
    stage_no = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    agency = models.CharField(max_length=100, blank=True, default='')
    tier = models.CharField(max_length=5, choices=TIER_CHOICES, default='minor')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='idle')
    progress_pct = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)])
    received_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    detail = models.TextField(blank=True, default='')
    dday_label = models.CharField(max_length=30, blank=True, default='',
                                  help_text='deadline 없을 때 표시 문구(종결/예정/순번 등)')
    doc_label = models.CharField(max_length=30, default='문서')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bizdev_permit_stages'
        ordering = ['stage_no']
        constraints = [
            models.UniqueConstraint(fields=['site', 'stage_no'],
                                    name='uniq_bizdev_stage_no_per_site'),
        ]
        verbose_name = '인허가 단계'
        verbose_name_plural = '인허가 단계'

    def __str__(self):
        return f'{self.site.name} · {self.stage_no}. {self.name}'


class PermitDocument(models.Model):
    """인허가 문서 버전 — 단계당 최신본(is_current) 1개"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(PermitStage, on_delete=models.CASCADE,
                              related_name='documents')
    version = models.PositiveIntegerField()
    file_name = models.CharField(max_length=300, help_text='업로드 당시 원본 파일명')
    storage_uri = models.CharField(max_length=1000,
                                   help_text='/media/bizdev/permit_docs/<uuid>.<ext>')
    file_size = models.BigIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=True)
    note = models.TextField(blank=True, default='')
    uploaded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='bizdev_uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bizdev_permit_documents'
        ordering = ['-version']
        constraints = [
            models.UniqueConstraint(fields=['stage', 'version'],
                                    name='uniq_bizdev_doc_version_per_stage'),
            # 원본 Supabase 의 trg_single_current_doc 트리거 대체 —
            # "같은 단계에 최신본은 하나"를 DB 수준에서 보장한다.
            models.UniqueConstraint(fields=['stage'], condition=Q(is_current=True),
                                    name='uniq_bizdev_current_doc_per_stage'),
        ]
        verbose_name = '인허가 문서'
        verbose_name_plural = '인허가 문서'

    def __str__(self):
        return f'{self.file_name} v{self.version}'


class BudgetEntry(models.Model):
    """예산 집행 내역"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE,
                             related_name='budget_entries')
    category = models.CharField(max_length=10, choices=BUDGET_CATEGORY_CHOICES)
    amount_krw = models.BigIntegerField()
    exec_date = models.DateField()
    memo = models.TextField(blank=True, default='')
    receipt_uri = models.CharField(max_length=1000, blank=True, default='')
    receipt_name = models.CharField(max_length=300, blank=True, default='')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='bizdev_budget_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bizdev_budget_entries'
        ordering = ['-exec_date', '-created_at']
        indexes = [models.Index(fields=['site', '-exec_date'])]
        constraints = [
            models.CheckConstraint(check=Q(amount_krw__gt=0),
                                   name='bizdev_budget_amount_positive'),
        ]
        verbose_name = '예산 집행'
        verbose_name_plural = '예산 집행'

    def __str__(self):
        return f'{self.site.name} · {self.get_category_display()} {self.amount_krw:,}원'


class CommunityIssue(models.Model):
    """지역수용성 이슈"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='issues')
    issue_date = models.DateField()
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=ISSUE_STATUS_CHOICES,
                              default='open')
    issue_type = models.CharField(max_length=10, choices=ISSUE_TYPE_CHOICES,
                                  default='complaint')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bizdev_community_issues'
        ordering = ['-issue_date']
        indexes = [models.Index(fields=['site', '-issue_date'])]
        verbose_name = '지역수용성 이슈'
        verbose_name_plural = '지역수용성 이슈'

    def __str__(self):
        return f'{self.site.name} · {self.title}'
