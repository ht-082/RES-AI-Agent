"""
사업개발 API — Re-project-mng ver2.0 의 Supabase 직접 호출 + Express /api 를
DRF 로 통합 이관.
"""
import hashlib
import logging
import os
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.views import resolve_media_path

from . import snapshots
from .constants import STAGE_DEFS
from .models import BudgetEntry, CommunityIssue, PermitDocument, PermitStage, Site
from .permissions import IsAdminOrSitePM, check_site_editable
from .serializers import (
    BudgetEntrySerializer, CommunityIssueSerializer, PermitDocumentSerializer,
    PermitStageSerializer, SiteListSerializer, SiteWriteSerializer,
)

logger = logging.getLogger(__name__)

# 인허가 문서·증빙 업로드 허용 확장자 (문서/이미지/압축)
UPLOAD_EXTS = ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
               'hwp', 'hwpx', 'jpg', 'jpeg', 'png', 'zip')
UPLOAD_MAX_BYTES = 20 * 1024 * 1024  # 20MB


def make_slug(name):
    """원본 js/api.js makeSlug 이식 — ASCII 슬러그 + 이름 해시(충돌 방지)."""
    ascii_part = re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-')[:40]
    digest = int(hashlib.md5(str(name).encode('utf-8')).hexdigest()[:8], 16)
    base36 = ''
    n = digest
    while n:
        n, r = divmod(n, 36)
        base36 = '0123456789abcdefghijklmnopqrstuvwxyz'[r] + base36
    suffix = (base36 or '0')[-5:]
    return f'{ascii_part}-{suffix}' if ascii_part else f'site-{suffix}'


def _save_upload(uploaded, rel_dir):
    """업로드 파일을 media/bizdev/<rel_dir>/<uuid>.<ext> 로 저장하고
    (storage_uri, ext, size) 를 돌려준다. 사용자 파일명은 경로에 쓰지 않는다."""
    ext = os.path.splitext(uploaded.name)[1].lower().lstrip('.')
    if ext not in UPLOAD_EXTS:
        raise ValueError(f'지원하지 않는 형식입니다: .{ext} '
                         f'(가능: {", ".join(UPLOAD_EXTS)})')
    if uploaded.size and uploaded.size > UPLOAD_MAX_BYTES:
        raise ValueError('파일이 20MB 를 초과합니다.')
    file_id = uuid.uuid4()
    rel = f'bizdev/{rel_dir}'
    abs_dir = os.path.join(settings.MEDIA_ROOT, 'bizdev', rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    stored = f'{file_id}.{ext}'
    with open(os.path.join(abs_dir, stored), 'wb+') as f:
        for chunk in uploaded.chunks():
            f.write(chunk)
    return f'{settings.MEDIA_URL}{rel}/{stored}', ext, uploaded.size


def _delete_stored(storage_uri):
    """저장 파일 삭제(실패해도 무시 — DB 정합이 우선)."""
    path = resolve_media_path(storage_uri)
    if path:
        try:
            os.remove(path)
        except OSError:
            logger.warning(f'파일 삭제 실패: {storage_uri}')


def _file_response(storage_uri, file_name):
    path = resolve_media_path(storage_uri)
    if not path:
        return Response({'error': '파일을 찾을 수 없습니다.'},
                        status=status.HTTP_404_NOT_FOUND)
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=file_name)


class SiteViewSet(viewsets.ModelViewSet):
    """사업지 CRUD + 상세 1콜"""
    queryset = Site.objects.prefetch_related('stages')
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None          # 25건 규모 — 대시보드 단일 호출
    filterset_fields = ['lifecycle', 'energy_type']
    search_fields = ['name', 'location', 'sido']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return SiteWriteSerializer
        return SiteListSerializer

    def perform_create(self, serializer):
        user = self.request.user
        with transaction.atomic():
            site = serializer.save(
                pm=user,
                pm_name=getattr(user, 'name', '') or user.username,
                slug=make_slug(serializer.validated_data.get('name', '')),
            )
            # 원본 createSite: 12단계 STAGE_DEFS 자동 생성
            PermitStage.objects.bulk_create([
                PermitStage(site=site, status='idle', progress_pct=0, **d)
                for d in STAGE_DEFS
            ])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        site = serializer.instance
        out = SiteListSerializer(site, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        out = SiteListSerializer(instance, context=self.get_serializer_context())
        return Response(out.data)

    def destroy(self, request, *args, **kwargs):
        # 연쇄삭제(단계·문서·예산·이슈) 위험 — 원본보다 보수적으로 admin 전용
        if getattr(request.user, 'role', '') != 'admin':
            return Response({'error': '사업지 삭제는 관리자만 가능합니다.'},
                            status=status.HTTP_403_FORBIDDEN)
        site = self.get_object()
        for doc in PermitDocument.objects.filter(stage__site=site):
            _delete_stored(doc.storage_uri)
        for entry in site.budget_entries.exclude(receipt_uri=''):
            _delete_stored(entry.receipt_uri)
        return super().destroy(request, *args, **kwargs)

    # 메서드명을 detail 로 두면 DRF 가 dispatch 시 심는 self.detail(bool)과 충돌한다.
    @action(detail=True, methods=['get'], url_path='detail')
    def full_detail(self, request, pk=None):
        """상세 화면 1콜 — site + stages(documents) + budget + summary + issues"""
        site = self.get_object()
        stages = site.stages.prefetch_related('documents').order_by('stage_no')
        entries = site.budget_entries.all()
        by_cat = {}
        for e in entries:
            by_cat[e.category] = by_cat.get(e.category, 0) + e.amount_krw
        total = sum(by_cat.values())
        approved = site.approved_budget_krw or 0
        site_data = SiteListSerializer(site, context=self.get_serializer_context()).data
        # address_detail 은 편집 권한자(admin/PM)에게만 — 원본 "백데이터 비노출" 정책
        if site_data.get('can_edit'):
            site_data['address_detail'] = site.address_detail
        return Response({
            'site': site_data,
            'stages': PermitStageSerializer(stages, many=True).data,
            'budget_entries': BudgetEntrySerializer(entries, many=True).data,
            'budget_summary': {
                'by_category': by_cat,
                'total': total,
                'approved': approved,
                'exec_pct': round(total / approved * 100) if approved else 0,
            },
            'issues': CommunityIssueSerializer(site.issues.all(), many=True).data,
        })


class PermitStageViewSet(viewsets.ModelViewSet):
    queryset = PermitStage.objects.select_related('site').prefetch_related('documents')
    serializer_class = PermitStageSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site']

    def perform_create(self, serializer):
        site = serializer.validated_data['site']
        check_site_editable(self.request.user, site)
        with transaction.atomic():
            locked = PermitStage.objects.select_for_update().filter(site=site)
            next_no = (locked.aggregate(m=Max('stage_no'))['m'] or 0) + 1
            serializer.save(stage_no=next_no)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """{site, ordered_ids} — 2단계 재번호로 UNIQUE(site,stage_no) 충돌 회피."""
        site_id = request.data.get('site')
        ordered_ids = request.data.get('ordered_ids') or []
        try:
            site = Site.objects.get(pk=site_id)
        except (Site.DoesNotExist, ValueError, TypeError):
            return Response({'error': '사업지를 찾을 수 없습니다.'},
                            status=status.HTTP_404_NOT_FOUND)
        check_site_editable(request.user, site)
        with transaction.atomic():
            stages = {str(s.id): s
                      for s in PermitStage.objects.select_for_update().filter(site=site)}
            if set(map(str, ordered_ids)) != set(stages.keys()):
                return Response({'error': 'ordered_ids 가 사업지의 단계 목록과 일치하지 않습니다.'},
                                status=status.HTTP_400_BAD_REQUEST)
            # 1차: 충돌 없는 임시 번호대로 이동 → 2차: 최종 번호(1..n)
            for i, sid in enumerate(map(str, ordered_ids)):
                stages[sid].stage_no = 1000 + i
            PermitStage.objects.bulk_update(stages.values(), ['stage_no'])
            for i, sid in enumerate(map(str, ordered_ids)):
                stages[sid].stage_no = i + 1
            PermitStage.objects.bulk_update(stages.values(), ['stage_no'])
        qs = PermitStage.objects.filter(site=site).order_by('stage_no')
        return Response(PermitStageSerializer(qs, many=True).data)

    @action(detail=True, methods=['get', 'post'],
            parser_classes=[MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        """GET: 버전 목록 / POST: 새 버전 업로드(자동 최신본 지정)"""
        stage = self.get_object()
        if request.method == 'GET':
            return Response(PermitDocumentSerializer(
                stage.documents.all(), many=True).data)

        check_site_editable(request.user, stage.site)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'file 필드가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            storage_uri, _, size = _save_upload(uploaded, 'permit_docs')
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                locked = PermitDocument.objects.select_for_update().filter(stage=stage)
                next_ver = (locked.aggregate(m=Max('version'))['m'] or 0) + 1
                # demote-then-insert — 부분 유니크 제약이 최후 방어
                locked.filter(is_current=True).update(is_current=False)
                doc = PermitDocument.objects.create(
                    stage=stage, version=next_ver, file_name=uploaded.name,
                    storage_uri=storage_uri, file_size=size, is_current=True,
                    note=request.data.get('note', ''), uploaded_by=request.user)
        except Exception:
            _delete_stored(storage_uri)
            raise
        return Response(PermitDocumentSerializer(doc).data,
                        status=status.HTTP_201_CREATED)


class PermitDocumentViewSet(viewsets.GenericViewSet):
    """문서 버전 단건 조작 — 다운로드/최신 지정/삭제"""
    queryset = PermitDocument.objects.select_related('stage__site')
    serializer_class = PermitDocumentSerializer
    permission_classes = [IsAdminOrSitePM]

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        doc = self.get_object()
        return _file_response(doc.storage_uri, doc.file_name)

    @action(detail=True, methods=['post'], url_path='set-current')
    def set_current(self, request, pk=None):
        doc = self.get_object()
        check_site_editable(request.user, doc.stage.site)
        with transaction.atomic():
            PermitDocument.objects.select_for_update().filter(
                stage=doc.stage, is_current=True).update(is_current=False)
            doc.is_current = True
            doc.save(update_fields=['is_current'])
        return Response(PermitDocumentSerializer(doc).data)

    def destroy(self, request, pk=None):
        doc = self.get_object()
        check_site_editable(request.user, doc.stage.site)
        with transaction.atomic():
            stage = doc.stage
            was_current = doc.is_current
            _delete_stored(doc.storage_uri)
            doc.delete()
            if was_current:
                latest = stage.documents.order_by('-version').first()
                if latest:
                    latest.is_current = True
                    latest.save(update_fields=['is_current'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class BudgetEntryViewSet(viewsets.ModelViewSet):
    queryset = BudgetEntry.objects.select_related('site')
    serializer_class = BudgetEntrySerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'category']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        extra = {'created_by': self.request.user}
        receipt = self.request.FILES.get('receipt')
        if receipt:
            try:
                uri, _, _ = _save_upload(receipt, 'receipts')
            except ValueError as e:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'receipt': str(e)})
            extra.update(receipt_uri=uri, receipt_name=receipt.name)
        serializer.save(**extra)

    def perform_destroy(self, instance):
        if instance.receipt_uri:
            _delete_stored(instance.receipt_uri)
        instance.delete()

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        entry = self.get_object()
        if not entry.receipt_uri:
            return Response({'error': '증빙 파일이 없습니다.'},
                            status=status.HTTP_404_NOT_FOUND)
        return _file_response(entry.receipt_uri, entry.receipt_name or 'receipt')


class CommunityIssueViewSet(viewsets.ModelViewSet):
    queryset = CommunityIssue.objects.select_related('site')
    serializer_class = CommunityIssueSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'status', 'issue_type']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


# ── 집계·스냅샷 (원본 Express /api 이관) ─────────────────────────────

class SummaryView(APIView):
    """금월 Pending 이슈 집계 — 원본 countMonthlyPendingIssues 서버 이관"""
    def get(self, request):
        from datetime import date
        today = date.today()
        qs = CommunityIssue.objects.filter(
            issue_date__year=today.year, issue_date__month=today.month,
        ).exclude(status='closed')
        by = {'complaint': 0, 'grid': 0, 'etc': 0}
        for issue in qs:
            by[issue.issue_type] = by.get(issue.issue_type, 0) + 1
        return Response({'monthly_pending_issues': {'total': qs.count(), 'by': by}})


class GridCapacityView(APIView):
    def get(self, request):
        return Response(snapshots.grid_capacity_by_sido())


class GridNearbyView(APIView):
    def get(self, request):
        return Response(snapshots.grid_nearby(request.query_params.get('sido')))


class LawListView(APIView):
    def get(self, request):
        limit = request.query_params.get('limit')
        try:
            limit = int(limit) if limit else None
        except ValueError:
            limit = None
        return Response(snapshots.list_laws(limit))


class OrdinanceListView(APIView):
    def get(self, request):
        return Response(snapshots.list_ordinances(request.query_params.get('sido')))
