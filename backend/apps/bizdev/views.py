"""
사업개발 API — Re-project-mng ver2.0 의 Supabase 직접 호출 + Express /api 를
DRF 로 통합 이관.
"""
import hashlib
from collections import Counter
import logging
import os
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import FileResponse
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.views import resolve_media_path

from . import lawapi, registry, snapshots
from .constants import (
    CAPEX_PARTS, FACT_DEFS, FACT_SECTIONS, INVESTMENT_PARTS, LIFECYCLE_TO_STAGE,
    STAGE_DEFS, STAGE_TO_LIFECYCLE, fact_spec,
)
from .models import (
    BudgetApproval, BudgetEntry, CommunityIssue, Contract, DefectItem, OpsDaily,
    OpsPlanItem, PermitDocument, PermitStage, PortfolioKpi, Site, SiteDocument,
    SiteEvent, SiteFact, WatchedLaw,
)
from .permissions import IsAdminOrSitePM, check_site_editable
from .serializers import (
    BudgetApprovalSerializer, BudgetEntrySerializer, CommunityIssueSerializer,
    ContractSerializer, DefectItemSerializer, OpsDailySerializer,
    OpsPlanItemSerializer, PortfolioKpiSerializer, SiteDocumentSerializer,
    PermitDocumentSerializer, PermitStageSerializer, SiteEventSerializer,
    SiteFactSerializer, SiteListSerializer, SiteWriteSerializer,
    WatchedLawSerializer,
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
            sigun = sigun_of(site.location)
            if sigun and not site.sido:
                site.sido = sigun
                site.save(update_fields=['sido'])
            # 인허가 골격(법정절차 7 + 개별법 3)
            PermitStage.objects.bulk_create([
                PermitStage(
                    site=site, stage_no=d['stage_no'], name=d['name'],
                    agency=d['agency'], category=d['category'],
                    doc_label=d['doc_label'], status='idle',
                    tier=d['tier'],
                ) for d in STAGE_DEFS
            ])
            # 사업개요 항목 골격 — 등록 폼에서 받은 값은 미리 채워 둔다.
            # 비워 두면 Site 컬럼에는 값이 있는데 사업 개요 표만 '미정'이 된다.
            seeded = bound_fact_values(site)
            SiteFact.objects.bulk_create([
                SiteFact(site=site, section=d['section'], key=d['key'],
                         label=d['label'], sort_order=i,
                         value=seeded.get((d['section'], d['key']), ''))
                for i, d in enumerate(FACT_DEFS)
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

    @action(detail=True, methods=['post'], url_path='import-registry',
            parser_classes=[MultiPartParser, FormParser])
    def import_registry(self, request, pk=None):
        """법인등기부등본 PDF 를 읽어 SPC 항목을 채운다.

        인터넷등기소 PDF 는 텍스트라 OCR 없이 읽힌다. 스캔본이면 텍스트가
        비어 나오므로 채우지 않고 그 사실을 알린다(잘못 채우는 것보다 낫다).
        """
        site = self.get_object()
        check_site_editable(request.user, site)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'file 필드가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            storage_uri, ext, _ = _save_upload(uploaded, 'registry')
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if ext != 'pdf':
            _delete_stored(storage_uri)
            return Response({'error': '등기부등본은 PDF 로 올려 주세요.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            text = registry.extract_pdf_text(resolve_media_path(storage_uri))
            parsed = registry.parse_registry(text)
        except Exception as e:
            logger.error(f'등기부등본 파싱 실패: {e}', exc_info=True)
            parsed, text = {}, ''
        finally:
            _delete_stored(storage_uri)   # 원본은 보관하지 않는다(개인정보 포함)

        if not parsed:
            reason = ('PDF 에서 글자를 찾지 못했습니다(스캔본일 수 있습니다).'
                      if len(text.strip()) < 50 else
                      '등본 서식에서 항목을 찾지 못했습니다.')
            return Response({'error': reason, 'filled': []},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        filled = []
        with transaction.atomic():
            for key, value in parsed.items():
                fact = site.facts.filter(section='spc', key=key).first()
                if not fact:
                    continue
                before = fact.value
                if before.strip() == value.strip():
                    continue
                fact.value = value
                fact.certainty = 'confirmed'
                fact.source = '법인등기부등본'
                fact.save(update_fields=['value', 'certainty', 'source', 'updated_at'])
                filled.append({'label': fact.label, 'before': before, 'after': value})
        return Response({'filled': filled, 'found': len(parsed)})

    # 메서드명을 detail 로 두면 DRF 가 dispatch 시 심는 self.detail(bool)과 충돌한다.
    @action(detail=True, methods=['get'], url_path='detail')
    def full_detail(self, request, pk=None):
        """상세 화면 1콜 — site + stages(documents) + budget + summary + issues"""
        site = self.get_object()
        stages = site.stages.prefetch_related('documents').order_by('stage_no')
        entries = site.budget_entries.all()
        approvals = site.budget_approvals.all()
        by_cat = {}
        for e in entries:
            by_cat[e.category] = by_cat.get(e.category, 0) + e.amount_krw
        approved_by_cat = {}
        for a in approvals:
            approved_by_cat[a.category] = approved_by_cat.get(a.category, 0) + a.amount_krw
        total = sum(by_cat.values())
        # 승인 내역이 있으면 그 합이 승인 예산이다(Site 컬럼은 집계 사본)
        approved = sum(approved_by_cat.values()) or (site.approved_budget_krw or 0)
        site_data = SiteListSerializer(site, context=self.get_serializer_context()).data
        # address_detail 은 편집 권한자(admin/PM)에게만 — 원본 "백데이터 비노출" 정책
        if site_data.get('can_edit'):
            site_data['address_detail'] = site.address_detail
        return Response({
            'site': site_data,
            'sections': [{'key': k, 'label': v} for k, v in FACT_SECTIONS],
            'facts': SiteFactSerializer(site.facts.all(), many=True).data,
            'contracts': ContractSerializer(site.contracts.all(), many=True).data,
            'events': SiteEventSerializer(site.events.all(), many=True).data,
            'stages': PermitStageSerializer(stages, many=True).data,
            'budget_entries': BudgetEntrySerializer(entries, many=True).data,
            'budget_approvals': BudgetApprovalSerializer(approvals, many=True).data,
            'budget_summary': {
                'by_category': by_cat,
                'approved_by_category': approved_by_cat,
                'total': total,
                'approved': approved,
                'exec_pct': round(total / approved * 100) if approved else 0,
            },
            'issues': CommunityIssueSerializer(site.issues.all(), many=True).data,
            'ops_daily': OpsDailySerializer(site.ops_daily.all()[:400], many=True).data,
            'ops_plans': OpsPlanItemSerializer(site.ops_plans.all(), many=True).data,
            'defects': DefectItemSerializer(site.defects.all(), many=True).data,
            'site_documents': SiteDocumentSerializer(site.documents.all(), many=True).data,
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
            serializer.save(stage_no=next_no, is_custom=True)

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

    def perform_update(self, serializer):
        """기존 집행 항목에 증빙을 붙이거나 갈아 끼운다(항목별 첨부)."""
        entry = serializer.save()
        receipt = self.request.FILES.get('receipt')
        if not receipt:
            return
        try:
            uri, _, _ = _save_upload(receipt, 'receipts')
        except ValueError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'receipt': str(e)})
        old_uri = entry.receipt_uri
        entry.receipt_uri = uri
        entry.receipt_name = receipt.name
        entry.save(update_fields=['receipt_uri', 'receipt_name', 'updated_at'])
        if old_uri:
            _delete_stored(old_uri)

    @action(detail=True, methods=['delete'], url_path='receipt-file')
    def receipt_file(self, request, pk=None):
        """증빙만 떼어 낸다(집행 내역 자체는 남긴다)."""
        entry = self.get_object()
        check_site_editable(request.user, entry.site)
        if entry.receipt_uri:
            _delete_stored(entry.receipt_uri)
            entry.receipt_uri = ''
            entry.receipt_name = ''
            entry.save(update_fields=['receipt_uri', 'receipt_name', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

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


class BudgetApprovalViewSet(viewsets.ModelViewSet):
    """예산 승인 내역 — 용도별로 여러 건"""
    queryset = BudgetApproval.objects.select_related('site')
    serializer_class = BudgetApprovalSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'category']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        sync_approved_total(serializer.save(created_by=self.request.user).site)

    def perform_update(self, serializer):
        sync_approved_total(serializer.save().site)

    def perform_destroy(self, instance):
        site = instance.site
        instance.delete()
        sync_approved_total(site)


def sync_approved_total(site):
    """승인 내역 합계를 Site.approved_budget_krw 에 반영한다.

    지도·KPI·운영 상세가 이 컬럼을 읽으므로 한 곳에서 맞춰 둔다.
    """
    total = sum(a.amount_krw for a in site.budget_approvals.all())
    if total and site.approved_budget_krw != total:
        site.approved_budget_krw = total
        site.save(update_fields=['approved_budget_krw', 'updated_at'])


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


def watched_law_rows():
    """관심 대상의 동향 — 법령명으로 담은 것과 키워드로 담은 것을 합친다.

    하나씩 따로 조회하므로 일부가 실패해도 나머지는 보인다(전부 실패하면
    스냅샷 결과와 같아진다). 두 방법이 같은 법을 물어올 수 있어 id 로 한 번만
    남긴다 — 화면에서는 법령명으로 걸렸는지 키워드로 걸렸는지 구분하지 않는다.
    시행일 내림차순.
    """
    watched = list(WatchedLaw.objects.all())
    if not watched:
        return [], False
    snap = None
    rows, seen, live_used = [], set(), False
    for item in watched:
        if item.kind == 'keyword':
            got = lawapi.rows_for_keyword(item.term) if lawapi.enabled() else None
            if got is None:
                got = snapshots.laws_matching(item.term)
            else:
                live_used = True
        else:
            got = lawapi.rows_for_family(item.term) if lawapi.enabled() else None
            if got:
                live_used = True
            else:
                if snap is None:
                    snap = snapshots.list_laws()
                got = [r for r in snap if r.get('family') == item.term]
        for row in got:
            if row['id'] in seen:
                continue
            seen.add(row['id'])
            rows.append(row)
    rows.sort(key=lambda r: r.get('date') or '', reverse=True)
    return rows, live_used


def find_law(law_id):
    """제언 프롬프트용 — 실시간 결과와 스냅샷 양쪽에서 찾는다."""
    rows, _ = watched_law_rows()
    hit = next((r for r in rows if str(r.get('id')) == law_id), None)
    if hit:
        return hit
    return next((r for r in snapshots.list_laws() if str(r.get('id')) == law_id), None)


class LawListView(APIView):
    """법령 동향 — '관심 법령' 으로 고른 것만.

    전부 늘어놓으면 우리 사업에 걸리는 개정이 묻히기 때문에, 담당자가 골라 둔
    법(과 그 시행령·시행규칙)만 돌려준다. 관심 목록이 비어 있으면 빈 배열 —
    임의로 전체를 보여 주면 '아무것도 안 골랐다' 와 '전부 본다' 를 화면이
    구분할 수 없다.
    """
    def get(self, request):
        limit = request.query_params.get('limit')
        try:
            limit = int(limit) if limit else None
        except ValueError:
            limit = None
        rows, _ = watched_law_rows()
        return Response(rows[:limit] if limit else rows)


class LawSearchView(APIView):
    """관심 대상 고르기 — 법령명 검색(mode=law)과 키워드 미리보기(mode=keyword).

    키워드는 고를 목록이 없다. 대신 그 말이 본문에 든 법을 몇 건 보여 줘,
    담기 전에 무엇이 딸려 올지 알 수 있게 한다.
    키가 없으면 스냅샷에서 같은 모양으로 찾아 돌려주고(source), 왜 그런지
    reason 에 적는다.
    """
    def get(self, request):
        query = (request.query_params.get('q') or '').strip()
        mode = request.query_params.get('mode') or 'law'
        fallback_reason = (
            '법제처 키(LAW_API_OC)가 없어 스냅샷에서 찾습니다'
            if not lawapi.enabled() else '법제처 조회에 실패해 스냅샷에서 찾습니다')

        if mode == 'keyword':
            live = lawapi.rows_for_keyword(query) if query else None
            if live is not None:
                return Response({'source': 'live', 'mode': mode, 'results': live})
            return Response({
                'source': 'snapshot', 'mode': mode, 'reason': fallback_reason,
                'results': snapshots.laws_matching(query) if query else [],
            })

        live = lawapi.search_families(query) if query else None
        if live is not None:
            return Response({'source': 'live', 'mode': 'law', 'results': live})
        pool = snapshots.law_catalog()
        if query:
            pool = [g for g in pool
                    if query in g['family'] or query in g['law_name']]
        return Response({
            'source': 'snapshot', 'mode': 'law', 'reason': fallback_reason,
            'results': pool[:20],
        })


class WatchedLawViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                        mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """관심 법령 — 목록 · 추가 · 제거. 사내 도구라 로그인 사용자면 고칠 수 있다.

    이름은 스냅샷 목록에 있는 것만 받는다(serializer.validate_family).
    """
    queryset = WatchedLaw.objects.all()
    serializer_class = WatchedLawSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def perform_create(self, serializer):
        last = WatchedLaw.objects.order_by('-sort_order').first()
        obj = serializer.save(added_by=self.request.user,
                              sort_order=(last.sort_order + 1) if last else 0)
        lawapi.forget(obj.term)

    def perform_destroy(self, instance):
        lawapi.forget(instance.term)
        instance.delete()


class OrdinanceListView(APIView):
    def get(self, request):
        return Response(snapshots.list_ordinances(request.query_params.get('sido')))


class SiteFactViewSet(viewsets.ModelViewSet):
    """사업개요 항목 — 값·확정도 수정 전용(항목 추가/삭제는 정의가 소유)"""
    queryset = SiteFact.objects.select_related('site')
    serializer_class = SiteFactSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'section']
    http_method_names = ['get', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        fact = serializer.save()
        sync_capex_totals(fact)
        sync_bound_field(fact)


def sigun_of(location):
    """주소에서 계통·조례 조회 키(시·군·구)를 뽑는다. 없으면 None."""
    m = re.search(r'(\S+[시군구])', location or '')
    return m.group(1) if m else None


def bound_fact_values(site):
    """Site 컬럼 값을 사업개요 항목 형식으로. 등록 직후 골격을 채우는 데 쓴다.

    sync_bound_field 의 반대 방향이다 — 등록 폼(이름·용량·위치·유형)과
    사업 개요 표가 처음부터 같은 값을 보게 한다.
    """
    out = {}
    for d in FACT_DEFS:
        bound = d.get('bound')
        if not bound:
            continue
        raw = getattr(site, bound, None)
        if raw in (None, ''):
            continue
        if bound == 'capacity_mw':
            value = f'{float(raw):g}'
        elif bound == 'lifecycle':
            value = LIFECYCLE_TO_STAGE.get(raw, '')
        elif bound == 'cod':
            value = raw.isoformat() if hasattr(raw, 'isoformat') else str(raw)
        else:
            value = str(raw)
        if value:
            out[(d['section'], d['key'])] = value
    return out


def _amount(facts, key):
    """'1,291' · '미정' 같은 값에서 숫자만. 못 읽으면 None(합계에서 뺀다)."""
    raw = (facts.get(key) or '').strip()
    try:
        return float(re.sub(r'[^0-9.\-]', '', raw))
    except ValueError:
        return None


def sync_capex_totals(fact):
    """사업비 구성 항목이 바뀌면 총사업비·총투자비를 다시 더한다.

    금융모델 [총투자비] 표와 같은 계산이다.
      총사업비 = 조사설계비 + 토지비 + 공사비 + 기타비용 + 금융비용
      총투자비 = 총사업비 + Overfunding + DSRA
    합계를 사람이 따로 입력하면 구성 항목과 어긋나므로 서버에서만 채운다.
    """
    if fact.section != 'econ' or fact.key not in CAPEX_PARTS + INVESTMENT_PARTS[1:]:
        return
    rows = {f.key: f for f in SiteFact.objects.filter(site=fact.site, section='econ')}
    values = {k: f.value for k, f in rows.items()}

    for key, parts in (('total_capex', CAPEX_PARTS), ('total_investment', INVESTMENT_PARTS)):
        target = rows.get(key)
        if not target:
            continue
        nums = [_amount(values, p) for p in parts]
        got = [n for n in nums if n is not None]
        total = f'{sum(got):,.10g}' if got else ''
        if target.value != total:
            target.value = total
            target.save(update_fields=['value', 'updated_at'])
            values[key] = total          # 총사업비 → 총투자비 로 이어서 반영
            sync_bound_field(target)


def sync_bound_field(fact):
    """항목 값을 Site 의 정규 컬럼에 반영한다.

    지도·KPI·사업 List 는 Site 컬럼을 쓰므로, 표에서 용량을 고쳤는데 지도가
    옛 값을 그대로 보여주는 일이 없도록 한 곳에서 맞춘다.
    """
    spec = fact_spec(fact.section, fact.key)
    bound = (spec or {}).get('bound')
    if not bound:
        return
    site, value = fact.site, (fact.value or '').strip()
    if bound == 'capacity_mw':
        num = re.search(r'[\d.]+', value)
        if not num:
            return
        site.capacity_mw = num.group()
    elif bound == 'lifecycle':
        site.lifecycle = STAGE_TO_LIFECYCLE.get(value, site.lifecycle)
    elif bound == 'facility_type':
        site.facility_type = value
        if '태양광' in value:
            site.energy_type = 'solar'
        elif '풍력' in value:
            site.energy_type = 'wind'
    elif bound == 'location':
        site.location = value
        # 계통·조례 조회 키(시·군)를 주소에서 뽑아 둔다
        sigun = sigun_of(value)
        if sigun:
            site.sido = sigun
    elif bound == 'name':
        if value:
            site.name = value
    else:
        setattr(site, bound, value)
    site.save()


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related('site')
    serializer_class = ContractSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'category', 'status']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


class SiteEventViewSet(viewsets.ModelViewSet):
    queryset = SiteEvent.objects.select_related('site')
    serializer_class = SiteEventSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'event_type']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


class SubstationSearchView(APIView):
    """연계점 선택용 변전소 검색 — KEPCO 스냅샷의 882개 변전소."""
    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        return Response(snapshots.search_substations(q))


class OpsDailyViewSet(viewsets.ModelViewSet):
    """운영 실적(일별) — 당일·1개월·누적은 화면에서 이 줄들로 계산한다."""
    queryset = OpsDaily.objects.select_related('site')
    serializer_class = OpsDailySerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


class OpsPlanItemViewSet(viewsets.ModelViewSet):
    queryset = OpsPlanItem.objects.select_related('site')
    serializer_class = OpsPlanItemSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


class DefectItemViewSet(viewsets.ModelViewSet):
    queryset = DefectItem.objects.select_related('site')
    serializer_class = DefectItemSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site']

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        serializer.save()


class SiteDocumentViewSet(viewsets.ModelViewSet):
    """문서 보관함 — 목록·메모는 JSON, 파일은 multipart 로 올린다."""
    queryset = SiteDocument.objects.select_related('site')
    serializer_class = SiteDocumentSerializer
    permission_classes = [IsAdminOrSitePM]
    pagination_class = None
    filterset_fields = ['site', 'category']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def perform_create(self, serializer):
        check_site_editable(self.request.user, serializer.validated_data['site'])
        doc = serializer.save(uploaded_by=self.request.user)
        self._attach(doc)

    def perform_update(self, serializer):
        doc = serializer.save()
        self._attach(doc)

    def _attach(self, doc):
        upload = self.request.FILES.get('file')
        if not upload:
            return
        if doc.storage_uri:                       # 갈아 끼울 때 이전 파일 정리
            _delete_stored(doc.storage_uri)
        uri, _ext, size = _save_upload(upload, 'site_docs')
        doc.file_name = upload.name
        doc.storage_uri = uri
        doc.file_size = size
        doc.save(update_fields=['file_name', 'storage_uri', 'file_size'])

    def perform_destroy(self, instance):
        if instance.storage_uri:
            _delete_stored(instance.storage_uri)
        instance.delete()

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        doc = self.get_object()
        if not doc.storage_uri:
            return Response({'error': '첨부된 파일이 없습니다.'},
                            status=status.HTTP_404_NOT_FOUND)
        return _file_response(doc.storage_uri, doc.file_name or 'document')


class PortfolioKpiViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin,
                          viewsets.GenericViewSet):
    """대시보드 상단 지표 — 목록과 수정만. 키는 정의가 소유한다.

    자동 집계가 붙기 전까지 담당자가 직접 넣는 값이라, 없으면 빈 줄을 만들어
    돌려준다(화면이 '아직 안 넣었음' 과 '0' 을 구분할 수 있게 value 는 null).
    """
    serializer_class = PortfolioKpiSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    lookup_field = 'key'

    def get_queryset(self):
        for key, _label in PortfolioKpi.KEYS:
            PortfolioKpi.objects.get_or_create(key=key)
        keys = [k for k, _ in PortfolioKpi.KEYS]
        rows = {o.key: o for o in PortfolioKpi.objects.filter(key__in=keys)}
        return [rows[k] for k in keys if k in rows]

    def get_object(self):
        return PortfolioKpi.objects.get_or_create(key=self.kwargs['key'])[0]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


# ── 법령 영향 제언 ────────────────────────────────────────────────
# 제언 자체는 사내 챗봇이 만든다. 여기서는 '무엇을 물을지'만 만들어 준다 —
# 검색·출처·리랭킹은 챗봇 파이프라인이 하고, 우리가 복제하지 않는다.


def portfolio_line():
    """포트폴리오를 한 줄로 — 사업이 늘어도 질문 길이가 늘지 않게 집계한다."""
    rows = list(Site.objects.values('energy_type', 'lifecycle', 'sido', 'capacity_mw'))
    if not rows:
        return '보유 사업 없음'
    solar = sum(1 for r in rows if r['energy_type'] == 'solar')
    wind = len(rows) - solar
    dev = sum(1 for r in rows if r['lifecycle'] == 'dev')
    gw = sum(float(r['capacity_mw'] or 0) for r in rows) / 1000
    regions = Counter(r['sido'] for r in rows if r['sido'])
    where = ' · '.join(f'{k} {v}' for k, v in regions.most_common(4)) or '지역 미상'
    return (f'보유 사업 {len(rows)}건 · 총 {gw:.2f}GW — '
            f'태양광 {solar} / 풍력 {wind} · 개발 {dev} / 운영 {len(rows) - dev} · {where}')


def advice_prompt(law):
    """법령 한 건에 대한 질문.

    두 가지를 지킨다.
    ① 사업을 하나씩 나열하지 않고 집계 한 줄만 넣는다 — 사업이 늘어도 길어지지 않게.
    ② 개정 조문 원문이 없다는 사실을 먼저 밝히고, 그 상태에서도 담당자가 쓸 수 있는
       것(접점·확인 항목·먼저 볼 사업)을 묻는다. 그냥 물으면 "조문이 없어 확인
       불가"만 돌아와 아무 쓸모가 없다. 법제처 조문이 붙으면 ②는 걷어낸다.
    """
    name = law.get('short_name') or law.get('law_name') or '법령'
    body = law.get('summary') or law.get('title') or ''
    return chr(10).join([
        f"[{law.get('date', '')}] [{name}] [{law.get('category', '')}] "
        f"· 소관 {law.get('ministry', '')}",
        f"확인된 정보: {body or '분류만 확인됨'}",
        '',
        '※ 개정 조문 원문은 아직 확보하지 못했습니다. "확인 불가"라고만 답하지 말고,',
        '   조문 없이 판단 가능한 범위에서 아래를 구체적으로 답해 주세요.',
        '',
        f'우리 포트폴리오: {portfolio_line()}',
        '',
        '1) 이 법령이 우리 사업과 맞닿는 지점 — 어떤 인허가 · 계약 · 부지 조건에 걸리는가',
        '2) 이번 개정에서 확인할 항목 — 어떤 조문 · 부칙을 찾아봐야 하는가',
        '3) 먼저 살펴야 할 사업 — 유형 · 지역 · 단계 기준으로, 이유와 함께',
        '4) 조문 확인 전까지 취할 조치',
        '사내 자료에 근거가 있으면 인용하고, 일반 지식이면 그렇다고 밝혀 주세요.',
    ])


class LawAdvicePromptView(APIView):
    """GET /api/bizdev/laws/<law_id>/advice-prompt/ — 챗봇에 넣을 질문을 만들어 준다."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, law_id):
        law = find_law(law_id)
        if not law:
            return Response({'error': '법령을 찾을 수 없습니다.'},
                            status=status.HTTP_404_NOT_FOUND)
        name = law.get('short_name') or law.get('law_name') or '법령'
        return Response({'title': f'법령 영향 — {name}', 'prompt': advice_prompt(law)})
