"""
계약 관련 모델 — contract_templates, contract_drafts,
                 contract_reviews, contract_review_findings
"""
import uuid
from django.db import models


class ContractTemplate(models.Model):
    """표준 계약서 종류(마스터)"""
    CATEGORY_CHOICES = [
        ('개발', '개발'),
        ('인수', '인수'),
        ('지배구조', '지배구조'),
        ('건설', '건설'),
        ('운영', '운영'),
        ('금융', '금융'),
        ('금융/운영', '금융/운영'),
        ('자문', '자문'),
        ('경영관리', '경영관리'),
        ('매출', '매출'),
        ('공통', '공통'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, help_text='JDA, SPA, SHA 등')
    name_ko = models.CharField(max_length=150)
    name_en = models.CharField(max_length=200, blank=True, default='')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, default='')
    description = models.TextField(blank=True, default='')
    template_body = models.TextField(blank=True, default='', help_text='표준 양식(placeholder 포함)')
    key_term_schema = models.JSONField(default=list, blank=True, help_text='입력 필드 정의(라벨/타입/필수)')
    standard_clauses = models.JSONField(default=list, blank=True)
    review_checklist = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=20, default='v1')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contract_templates'
        ordering = ['code']
        verbose_name = '표준 계약서'
        verbose_name_plural = '표준 계약서'

    def __str__(self):
        return f'[{self.code}] {self.name_ko}'


class ContractDraft(models.Model):
    """계약서 신규 생성 (K-1)"""
    STATUS_CHOICES = [
        ('draft', '초안'),
        ('generating', '생성 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'workspaces.Project', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_drafts'
    )
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.CASCADE, related_name='drafts',
        null=True, blank=True
    )
    title = models.CharField(max_length=300, blank=True, default='')
    key_terms = models.JSONField(default=dict, blank=True, help_text='사용자 입력 Key-term')
    
    # 신규 구조화 필드 (ver 1.0)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='new_contract_drafts'
    )
    type_id = models.CharField(max_length=100, blank=True, default='', help_text='계약 유형 ID (PPA 등)')
    inputs = models.JSONField(default=dict, blank=True, help_text='사용자 동적 입력값')
    generated_articles = models.JSONField(default=list, blank=True, help_text='생성된 조항들')

    generated_content = models.TextField(blank=True, default='')
    output_file_uri = models.CharField(max_length=1000, blank=True, default='', help_text='Word 산출물')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contract_drafts'
        ordering = ['-created_at']
        verbose_name = '계약 초안'
        verbose_name_plural = '계약 초안'

    def __str__(self):
        return self.title or f'{self.template.name_ko} 초안'


class ContractReview(models.Model):
    """계약서 검토 (K-2)"""
    STATUS_CHOICES = [
        ('pending', '대기'),
        ('reviewing', '검토 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'workspaces.Project', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_reviews'
    )
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviews',
        help_text='추정 유형'
    )
    title = models.CharField(max_length=300, blank=True, default='')
    source_document_uri = models.CharField(max_length=1000, blank=True, default='', help_text='검토 대상 원본')
    review_instruction = models.TextField(blank=True, default='')
    summary = models.TextField(blank=True, default='')
    output_file_uri = models.CharField(max_length=1000, blank=True, default='', help_text='Word 산출물')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_reviews'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contract_reviews'
        ordering = ['-created_at']
        verbose_name = '계약 검토'
        verbose_name_plural = '계약 검토'

    def __str__(self):
        return self.title or f'계약 검토 {str(self.id)[:8]}'


class ContractReviewFinding(models.Model):
    """검토 결과 항목"""
    SEVERITY_CHOICES = [
        ('high', '독소'),
        ('mid', '불리'),
        ('low', '경고'),
    ]
    CATEGORY_CHOICES = [
        ('독소조항', '독소조항'),
        ('불리조항', '불리조항'),
        ('누락', '누락'),
        ('오류', '오류'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        ContractReview, on_delete=models.CASCADE, related_name='findings'
    )
    clause_ref = models.CharField(max_length=100, blank=True, default='', help_text='조항 위치')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='mid')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, blank=True, default='')
    finding = models.TextField(help_text='지적 내용')
    suggestion = models.TextField(blank=True, default='', help_text='수정 방향')
    source_clause_ref = models.CharField(max_length=100, blank=True, default='', help_text='표준양식 근거')
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_review_findings'
        ordering = ['order_index']
        verbose_name = '검토 결과'
        verbose_name_plural = '검토 결과'

    def __str__(self):
        return f'[{self.severity}] {self.clause_ref}: {self.finding[:50]}'
