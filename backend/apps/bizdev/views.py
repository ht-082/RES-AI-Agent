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

from . import registry, snapshots
from .constants import (
    CAPEX_PARTS, FACT_DEFS, FACT_SECTIONS, INVESTMENT_PARTS, STAGE_DEFS,
    STAGE_TO_LIFECYCLE, fact_spec,
)
from .models import (
    BudgetApproval, BudgetEntry, CommunityIssue, Contract, PermitDocument,
    PermitStage, Site, SiteEvent, SiteFact,
)
from .permissions import IsAdminOrSitePM, check_site_editable
from .serializers import (
    BudgetApprovalSerializer, BudgetEntrySerializer, CommunityIssueSerializer,
    ContractSerializer,
    PermitDocumentSerializer, PermitStageSerializer, SiteEventSerializer,
    SiteFactSerializer, SiteListSerializer, SiteWriteSerializer,
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
            # 인허가 골격(법정절차 7 + 개별법 3)
            PermitStage.objects.bulk_create([
                PermitStage(
                    site=site, stage_no=d['stage_no'], name=d['name'],
                    agency=d['agency'], category=d['category'],
                    doc_label=d['doc_label'], status='idle', progress_pct=0,
                    tier=d['tier'],
                ) for d in STAGE_DEFS
            ])
            # 사업개요 항목 골격 — 빈칸으로 만들어 두고 담당자가 채운다
            SiteFact.objects.bulk_create([
                SiteFact(site=site, section=d['section'], key=d['key'],
                         label=d['label'], sort_order=i)
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
        m = re.search(r'(\S+[시군구])', value)
        if m:
            site.sido = m.group(1)
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
