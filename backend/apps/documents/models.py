"""
문서 / 청크 모델 — schema.sql documents, document_chunks 테이블 기반
"""
import uuid
from django.db import models


class CorpusVersion(models.Model):
    """코퍼스 버전 레지스트리 (메이저 버전당 1행)

    사용자 정의 버전 체계 (2026-07-18):
    - 마이너 올림(1.0→1.1): 같은 청킹으로 문서만 추가 — 같은 컬렉션에 누적, version 라벨만 갱신
    - 메이저 올림(1.x→2.0): 청킹 방식 변경 — 새 행 + 새 Qdrant 컬렉션, 이전 버전은 유지되어
      프론트에서 선택·비교 가능
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.CharField(max_length=20, unique=True, help_text="표시 라벨 (예: '1.2')")
    major = models.PositiveIntegerField(unique=True, help_text='메이저 번호 = 청킹 세대')
    collection_name = models.CharField(max_length=100, unique=True, help_text='Qdrant 컬렉션명')
    description = models.TextField(blank=True, default='', help_text='청킹 방식 요약')
    is_active = models.BooleanField(default=False, help_text='기본 질의 대상 버전')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'corpus_versions'
        ordering = ['-major']

    def __str__(self):
        return f"v{self.version} ({self.collection_name})"


class Document(models.Model):
    """사내 자료 원본 메타데이터"""
    STATUS_CHOICES = [
        ('uploaded', '업로드 완료'),
        ('parsing', '파싱 중'),
        ('embedding', '임베딩 중'),
        ('indexed', '인덱싱 완료'),
        ('failed', '실패'),
    ]
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'Word'),
        ('xlsx', 'Excel'),
        ('pptx', 'PowerPoint'),
    ]
    DOC_TYPE_CHOICES = [
        ('contract', '계약서'),
        ('report', '보고자료'),
        ('law', '법령/규정'),
        ('spec', '시방서/기술문서'),
        ('admin', '공문/행정문서'),
        ('general', '일반문서')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus = models.ForeignKey(
        CorpusVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name='documents', help_text='소속 코퍼스 버전 (NULL=버전 도입 전 데이터)'
    )
    project = models.ForeignKey(
        'workspaces.Project', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documents',
        help_text='NULL이면 전사 공용 코퍼스'
    )
    title = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=500)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    storage_uri = models.CharField(max_length=1000, help_text='원문 열람 경로')
    file_size = models.BigIntegerField(null=True, blank=True)
    page_count = models.IntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=128, blank=True, default='', help_text='중복 적재 방지')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default='general', help_text='문서 분류 유형')
    metadata = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_documents',
        db_column='uploaded_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
        verbose_name = '문서'
        verbose_name_plural = '문서'

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """청크 메타데이터 — 벡터 본체는 Qdrant에 저장"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.IntegerField(help_text='문서 내 순서')
    content = models.TextField(help_text='청크 원문(스니펫/재정렬용)')
    page_number = models.IntegerField(null=True, blank=True, help_text='출처 위치(페이지)')
    section_title = models.CharField(max_length=300, blank=True, default='', help_text='조항/제목')
    char_start = models.IntegerField(null=True, blank=True)
    char_end = models.IntegerField(null=True, blank=True)
    bbox = models.JSONField(null=True, blank=True, help_text='PDF 좌표(뷰어 하이라이트)')
    sheet_name = models.CharField(max_length=200, blank=True, default='', help_text='Excel 시트명')
    cell_range = models.CharField(max_length=100, blank=True, default='', help_text='Excel 셀 범위')
    token_count = models.IntegerField(null=True, blank=True)
    qdrant_point_id = models.UUIDField(unique=True, help_text='Qdrant 포인트 매핑')
    metadata = models.JSONField(default=dict, blank=True, help_text='유형별 맞춤 메타데이터')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'document_chunks'
        ordering = ['document', 'chunk_index']
        verbose_name = '문서 청크'
        verbose_name_plural = '문서 청크'

    def __str__(self):
        return f'{self.document.title} - chunk {self.chunk_index}'
