"""
사업개발 포트폴리오 모델 — Re-project-mng ver2.0 Supabase 스키마 이관.

원본 supabase/01_schema.sql + 05_migration_v2.sql 의 sites/permit_stages/
permit_documents/budget_entries/community_issues 를 Django 로 옮겼다.
2차 범위 테이블(policy_advice, ordinance_alerts 등)은 만들지 않는다.
"""
import uuid

from django.db import models
from django.db.models import Q

from .constants import (
    BUDGET_CATEGORY_CHOICES, CERTAINTY_CHOICES, CONTRACT_CATEGORY_CHOICES,
    CONTRACT_STATUS_CHOICES, ENERGY_CHOICES, EVENT_TYPE_CHOICES,
    EVENT_STATUS_CHOICES, ISSUE_STATUS_CHOICES, ISSUE_TYPE_CHOICES, LIFECYCLE_CHOICES,
    PERMIT_CATEGORY_CHOICES, PERMIT_STATE_CHOICES, RISK_LEVEL_CHOICES,
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
    """인허가 항목 — 사업개요 양식 §3 (법정절차 7 + 개별법 협의 3) + 사용자 추가"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='stages')
    stage_no = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    agency = models.CharField(max_length=100, blank=True, default='')
    tier = models.CharField(max_length=5, choices=TIER_CHOICES, default='minor')
    category = models.CharField(max_length=12, choices=PERMIT_CATEGORY_CHOICES,
                                default='statutory', help_text='법정절차 / 개별법 협의')
    status = models.CharField(max_length=10, choices=PERMIT_STATE_CHOICES, default='idle',
                              help_text='완료·진행중·미착수·미대상 (md 출력 시 진행중·미착수는 미완료로 합침)')
    content = models.TextField(blank=True, default='',
                               help_text='허가번호·용량·허가일자 등 (양식 §3 내용란)')
    certainty = models.CharField(max_length=12, choices=CERTAINTY_CHOICES,
                                 default='unconfirmed')
    remark = models.TextField(blank=True, default='',
                              help_text='허가/협의내용 특이사항 (양식 §3)')
    received_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    detail = models.TextField(blank=True, default='')
    dday_label = models.CharField(max_length=30, blank=True, default='',
                                  help_text='deadline 없을 때 표시 문구(종결/예정/순번 등)')
    doc_label = models.CharField(max_length=30, default='문서')
    is_custom = models.BooleanField(
        default=False, help_text='사용자가 직접 추가한 인허가 항목')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class BudgetApproval(models.Model):
    """예산 승인 내역 — 용도별로 여러 건을 쌓을 수 있다(최초 승인·증액 등).

    사업의 승인 예산은 이 행들의 합이다. Site.approved_budget_krw 는
    지도·KPI 가 쓰는 집계 사본이라 저장할 때 함께 맞춘다.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE,
                             related_name='budget_approvals')
    category = models.CharField(max_length=10, choices=BUDGET_CATEGORY_CHOICES)
    amount_krw = models.BigIntegerField()
    approved_date = models.DateField(null=True, blank=True)
    memo = models.TextField(blank=True, default='')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='bizdev_budget_approvals')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_budget_approvals'
        ordering = ['category', 'approved_date', 'created_at']
        indexes = [models.Index(fields=['site'])]
        constraints = [
            models.CheckConstraint(check=Q(amount_krw__gt=0),
                                   name='bizdev_approval_amount_positive'),
        ]
        verbose_name = '예산 승인'
        verbose_name_plural = '예산 승인'

    def __str__(self):
        return f'{self.site.name} · {self.get_category_display()} {self.amount_krw:,}원'


class BudgetEntry(models.Model):
    """예산 집행 내역 — 용도별 승인 항목에 대응해 집행한다"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE,
                             related_name='budget_entries')
    category = models.CharField(max_length=10, choices=BUDGET_CATEGORY_CHOICES)
    amount_krw = models.BigIntegerField()
    exec_date = models.DateField()
    payee = models.CharField(max_length=100, blank=True, default='',
                             help_text='지급 상대방(수취처)')
    memo = models.TextField(blank=True, default='')
    receipt_uri = models.CharField(max_length=1000, blank=True, default='')
    receipt_name = models.CharField(max_length=300, blank=True, default='')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='bizdev_budget_entries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class SiteFact(models.Model):
    """사업개요 항목 — 양식의 "구분 | 내용 | 확정도 | 근거·비고" 표 한 줄.

    항목을 컬럼으로 만들면 40개 항목 × 4속성 = 160컬럼이 되고 양식이 바뀔 때마다
    스키마를 고쳐야 한다. 행으로 두면 constants.FACT_DEFS 만 고치면 된다.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='facts')
    section = models.CharField(max_length=20, help_text='basic/spc/land/econ/pf')
    key = models.CharField(max_length=40)
    label = models.CharField(max_length=100)
    value = models.TextField(blank=True, default='')
    certainty = models.CharField(max_length=12, choices=CERTAINTY_CHOICES,
                                 default='unconfirmed')
    source = models.CharField(max_length=200, blank=True, default='', help_text='근거 문서')
    note = models.CharField(max_length=200, blank=True, default='', help_text='비고')
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_custom = models.BooleanField(
        default=False, help_text='사용자가 직접 추가한 항목(정의 골격 밖) — 시드가 지우지 않는다')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_site_facts'
        ordering = ['sort_order']
        constraints = [
            models.UniqueConstraint(fields=['site', 'section', 'key'],
                                    name='uniq_bizdev_fact_per_site'),
        ]
        verbose_name = '사업개요 항목'
        verbose_name_plural = '사업개요 항목'

    def __str__(self):
        return f'{self.site.name} · {self.label}'


class Contract(models.Model):
    """계약 정보 — 양식 §5"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='contracts')
    category = models.CharField(max_length=24, choices=CONTRACT_CATEGORY_CHOICES,
                                default='etc')
    counterparty = models.CharField(max_length=100, blank=True, default='', help_text='상대방')
    # 금액은 자유 입력이다. 계약마다 표현이 달라(총액 '12억원' · 단가 '평당 연 6,000원')
    # 한 숫자로 담으면 원문을 잃는다. 합산이 필요해지면 그때 숫자 칸을 따로 둔다.
    amount = models.CharField(max_length=80, blank=True, default='', help_text='계약 금액')
    summary = models.TextField(blank=True, default='', help_text='주요 내용')
    certainty = models.CharField(max_length=12, choices=CERTAINTY_CHOICES,
                                 default='unconfirmed')
    status = models.CharField(max_length=10, choices=CONTRACT_STATUS_CHOICES, default='none')
    note = models.CharField(max_length=200, blank=True, default='')
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_contracts'
        ordering = ['sort_order', 'created_at']
        indexes = [models.Index(fields=['site'])]
        verbose_name = '계약'
        verbose_name_plural = '계약'

    def __str__(self):
        return f'{self.site.name} · {self.get_category_display()}'


class SiteEvent(models.Model):
    """진행경과 및 이슈 — 양식 §6.

    event_date 는 등록 일자다. 진행 상태는 status 로 따로 관리한다
    (예전에는 날짜를 비워 "진행 중"을 나타냈는데, 그러면 언제 올라온 건인지
    알 수 없었다).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='events')
    event_date = models.DateField(null=True, blank=True, help_text='등록 일자')
    event_type = models.CharField(max_length=12, choices=EVENT_TYPE_CHOICES, default='etc')
    status = models.CharField(max_length=10, choices=EVENT_STATUS_CHOICES,
                              default='ongoing', help_text='진행중 / 보류 / 완료')
    summary = models.TextField(blank=True, default='', help_text='주요 내용')
    certainty = models.CharField(max_length=12, choices=CERTAINTY_CHOICES,
                                 default='confirmed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_site_events'
        # 날짜 있는 행이 최신순으로, "진행 중"(날짜 없음)이 맨 위에 오도록
        ordering = [models.F('event_date').desc(nulls_first=True), '-created_at']
        indexes = [models.Index(fields=['site'])]
        verbose_name = '진행경과'
        verbose_name_plural = '진행경과'

    @property
    def is_ongoing(self):
        return self.event_date is None

    def __str__(self):
        return f'{self.site.name} · {self.summary[:30]}'


class OpsDaily(models.Model):
    """운영 실적 — 하루치 한 줄(발전량·PR·매출).

    당일·1개월 평균·사업년도 누적은 이 줄들을 세어 만든다. 값을 세 벌로 저장하면
    반드시 어긋나므로, 담는 것은 '하루' 하나뿐이다(양식 §1-1·1-2).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='ops_daily')
    date = models.DateField()
    generation_mwh = models.DecimalField(max_digits=12, decimal_places=3, null=True,
                                         blank=True, help_text='발전량 (MWh)')
    pr_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                 help_text='PR (%)')
    revenue_krw = models.BigIntegerField(null=True, blank=True, help_text='매출 (원)')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_ops_daily'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['site', 'date'],
                                               name='uniq_bizdev_ops_daily')]
        indexes = [models.Index(fields=['site', 'date'])]
        verbose_name = '운영 실적(일별)'
        verbose_name_plural = '운영 실적(일별)'

    def __str__(self):
        return f'{self.site.name} · {self.date}'


class OpsPlanItem(models.Model):
    """정기 운영관리 계획 — 월 단위 점검·정비 항목 (양식 §1-3)"""
    STATUS = [('planned', '예정'), ('doing', '진행중'), ('done', '완료'),
              ('skip', '미실시')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='ops_plans')
    month = models.DateField(help_text='해당 월(1일로 저장)')
    title = models.CharField(max_length=120, help_text='점검·정비 항목')
    cycle = models.CharField(max_length=40, blank=True, default='',
                             help_text='주기 (월 1회 · 분기 등)')
    owner = models.CharField(max_length=60, blank=True, default='', help_text='담당')
    status = models.CharField(max_length=10, choices=STATUS, default='planned')
    done_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_ops_plans'
        ordering = ['-month', 'title']
        indexes = [models.Index(fields=['site', 'month'])]
        verbose_name = '운영관리 계획'
        verbose_name_plural = '운영관리 계획'

    def __str__(self):
        return f'{self.site.name} · {self.month:%Y-%m} {self.title}'


class DefectItem(models.Model):
    """하자 보수 현황 (양식 §1-4)"""
    STATUS = [('open', '접수'), ('doing', '조치중'), ('done', '완료'),
              ('hold', '보류')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='defects')
    found_date = models.DateField(null=True, blank=True, help_text='발생·접수일')
    part = models.CharField(max_length=80, blank=True, default='',
                            help_text='설비·부위 (모듈 · 인버터 등)')
    summary = models.TextField(blank=True, default='', help_text='내용')
    status = models.CharField(max_length=10, choices=STATUS, default='open')
    fixed_date = models.DateField(null=True, blank=True, help_text='조치 완료일')
    counterparty = models.CharField(max_length=80, blank=True, default='',
                                    help_text='조치 주체 (EPC · O&M 등)')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_defects'
        ordering = [models.F('found_date').desc(nulls_first=True), '-created_at']
        indexes = [models.Index(fields=['site'])]
        verbose_name = '하자 보수'
        verbose_name_plural = '하자 보수'

    def __str__(self):
        return f'{self.site.name} · {self.part} {self.summary[:20]}'


class SiteDocument(models.Model):
    """문서 보관함 (양식 §3) — 인허가 문서는 PermitDocument 가 따로 들고 있다."""
    CATEGORY = [('ops', '운영'), ('corp', '법인문서'), ('permit', '인허가'),
                ('fin', '재무')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='documents')
    category = models.CharField(max_length=10, choices=CATEGORY, default='ops')
    title = models.CharField(max_length=200, help_text='문서 이름')
    doc_date = models.DateField(null=True, blank=True, help_text='문서 일자')
    file_name = models.CharField(max_length=300, blank=True, default='')
    storage_uri = models.CharField(max_length=1000, blank=True, default='',
                                   help_text='/media/bizdev/site_docs/<uuid>.<ext>')
    file_size = models.BigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default='')
    uploaded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='bizdev_site_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_site_documents'
        ordering = ['category', '-doc_date', '-created_at']
        indexes = [models.Index(fields=['site', 'category'])]
        verbose_name = '문서 보관함'
        verbose_name_plural = '문서 보관함'

    def __str__(self):
        return f'{self.site.name} · {self.get_category_display()} {self.title}'


class PortfolioKpi(models.Model):
    """대시보드 상단 지표 — 아직 자동 집계가 없는 값을 담아 둔다.

    전체 등록 사업은 사업지 목록에서 바로 세므로 여기 두지 않는다. Pipeline 확보
    실적·당월 재무는 근거 데이터(계약·회계)가 붙기 전까지 담당자가 직접 넣는다.
    나중에 연동되면 이 표를 지우고 계산값으로 바꾼다.
    """
    KEYS = [
        ('pipeline_secured_mw', '올해 Pipeline 확보 실적 (MW)'),
        ('revenue_month_krw', '당월 총 매출 (원)'),
        ('profit_month_krw', '당월 영업이익 (원)'),
    ]

    key = models.CharField(max_length=40, primary_key=True, choices=KEYS)
    value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default='')
    updated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='bizdev_kpis')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bizdev_portfolio_kpis'
        verbose_name = '대시보드 지표'
        verbose_name_plural = '대시보드 지표'

    def __str__(self):
        return f'{self.get_key_display()} = {self.value}'


class WatchedLaw(models.Model):
    """법령 동향에서 지켜볼 법 — 우리 인허가에 걸리는 것만 골라 둔다.

    스냅샷에는 법령 40건(묶어서 21개)이 들어 있는데, 전부 늘어놓으면 정작
    우리 사업에 걸리는 개정이 그 사이에 묻힌다. 담당자가 고른 법만 표에
    올리고, 나머지는 편집 화면에서만 보인다.

    family 는 시행령·시행규칙까지 묶은 이름(snapshots.law_family). '농지법' 을
    담아 두면 '농지법 시행령' 개정도 함께 따라온다 — 실무에서 둘을 따로
    챙기는 일이 없기 때문이다. 스냅샷 밖의 이름은 서버가 받지 않는다.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.CharField('법령', max_length=120, unique=True)
    sort_order = models.IntegerField('순서', default=0)
    added_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='bizdev_watched_laws')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bizdev_watched_laws'
        ordering = ['sort_order', 'family']
        verbose_name = '관심 법령'
        verbose_name_plural = '관심 법령'

    def __str__(self):
        return self.family
