import hashlib
import logging
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count, Q
from rest_framework.views import APIView

from .models import CorpusVersion, Document, DocumentChunk
from .serializers import DocumentSerializer, DocumentChunkSerializer, DocumentUploadSerializer


class CorpusVersionListView(APIView):
    """GET /api/corpus-versions/ — 프론트 코퍼스 선택 드롭다운용"""

    def get(self, request):
        rows = (CorpusVersion.objects
                .annotate(doc_count=Count('documents', filter=Q(documents__status='indexed')))
                .order_by('-major'))
        return Response([{
            'version': cv.version,
            'major': cv.major,
            'is_active': cv.is_active,
            'description': cv.description,
            'doc_count': cv.doc_count,
            'created_at': cv.created_at,
        } for cv in rows])

logger = logging.getLogger(__name__)

# 업로드 허용 확장자 — services/parser.parse_file 이 다룰 수 있는 것과 일치시킨다.
# (md/txt: 사업개요처럼 사람이 직접 관리하는 정리본)
UPLOADABLE_EXTS = ('pdf', 'docx', 'xlsx', 'pptx', 'hwp', 'hwpx', 'md', 'txt')

# 원문 열람 시 브라우저에 알려줄 MIME 타입
CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'hwpx': 'application/haansofthwpx',
    'hwp': 'application/x-hwp',
    'md': 'text/markdown; charset=utf-8',
    'txt': 'text/plain; charset=utf-8',
}


def resolve_media_path(storage_uri):
    """storage_uri('/media/documents/x.pdf')를 MEDIA_ROOT 내 실제 파일 경로로 환원한다.

    storage_uri는 DB 값이므로 그대로 신뢰하지 않는다. '..' 등으로 MEDIA_ROOT 바깥을
    가리키면 None을 반환해 임의 파일 읽기를 차단한다.
    파일이 없을 때도 None.
    """
    if not storage_uri:
        return None

    rel = storage_uri
    if rel.startswith(settings.MEDIA_URL):
        rel = rel[len(settings.MEDIA_URL):]
    rel = rel.lstrip('/')

    base = os.path.realpath(settings.MEDIA_ROOT)
    target = os.path.realpath(os.path.join(base, rel))

    # MEDIA_ROOT 하위인지 검증 (경로 탈출 차단)
    if target != base and not target.startswith(base + os.sep):
        logger.warning(f"MEDIA_ROOT 밖을 가리키는 storage_uri 차단: {storage_uri!r}")
        return None

    return target if os.path.isfile(target) else None


class DocumentViewSet(viewsets.ModelViewSet):
    """문서 CRUD + 업로드 API"""
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filterset_fields = ['project', 'file_type', 'status']

    def get_parsers(self):
        # get_parsers()는 initialize_request() 안에서 호출되므로 self.action이 아직 없다.
        # action_map과 request는 as_view()가 dispatch 전에 세팅하므로 이것으로 판별한다.
        action_map = getattr(self, 'action_map', None) or {}
        method = getattr(getattr(self, 'request', None), 'method', '') or ''
        if action_map.get(method.lower()) == 'create':
            return [MultiPartParser(), FormParser()]
        return super().get_parsers()

    def create(self, request, *args, **kwargs):
        """POST /api/documents/ — 문서 업로드 (비동기 수집 트리거)"""
        upload_serializer = DocumentUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        uploaded_file = upload_serializer.validated_data['file']
        project_id = upload_serializer.validated_data.get('project_id')
        title = upload_serializer.validated_data.get('title', uploaded_file.name)

        # 파일 타입 추출 (파서가 다룰 수 있는 형식과 일치시킨다)
        ext = os.path.splitext(uploaded_file.name)[1].lower().strip('.')
        if ext not in UPLOADABLE_EXTS:
            return Response(
                {'error': f'지원하지 않는 파일 형식입니다: .{ext}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 파일 저장
        media_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, uploaded_file.name)

        # checksum 계산
        md5 = hashlib.md5()
        with open(file_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
                md5.update(chunk)
        checksum = md5.hexdigest()

        # 문서 메타데이터 생성
        doc = Document.objects.create(
            project_id=project_id,
            title=title,
            original_filename=uploaded_file.name,
            file_type=ext,
            storage_uri=f'/media/documents/{uploaded_file.name}',
            file_size=uploaded_file.size,
            checksum=checksum,
            status='uploaded',
        )

        # Celery 비동기 태스크 구동
        from apps.rag.tasks import process_document
        process_document.delay(str(doc.id))

        serializer = self.get_serializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='replace',
            parser_classes=[MultiPartParser, FormParser],
            permission_classes=[IsAuthenticated])
    def replace(self, request, pk=None):
        """POST /api/documents/{id}/replace — 문서 내용 교체 (전체 재적재 없이)

        사업개요처럼 실무자가 계속 갱신하는 문서를 위한 경로다.
        같은 파일을 다시 올리면 checksum이 달라 '새 문서'가 하나 더 생기고,
        옛 수치와 새 수치가 동시에 검색되어 답변이 흔들린다.
        이 액션은 **옛 문서(및 Qdrant 벡터)를 지운 뒤** 새 파일을 같은 자리에 넣는다.
        프로젝트·doc_type·source_path 등 분류 정보는 그대로 승계한다.
        """
        old = self.get_object()
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'file 필드가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(uploaded_file.name)[1].lower().strip('.')
        if ext not in UPLOADABLE_EXTS:
            return Response({'error': f'지원하지 않는 파일 형식입니다: .{ext}'},
                            status=status.HTTP_400_BAD_REQUEST)

        # 승계할 정보를 삭제 전에 확보한다
        carried = {
            'project': old.project,
            'corpus': old.corpus,
            'doc_type': old.doc_type,
            'metadata': dict(old.metadata or {}),
            'title': request.data.get('title') or uploaded_file.name,
            'uploaded_by': old.uploaded_by,
        }
        old_chunk_count = old.chunks.count()

        media_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(media_dir, exist_ok=True)

        md5 = hashlib.md5()
        tmp_path = os.path.join(media_dir, f'.replace_{old.id}{os.path.splitext(uploaded_file.name)[1]}')
        with open(tmp_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
                md5.update(chunk)
        checksum = md5.hexdigest()

        stored_name = f'{checksum[:8]}_{uploaded_file.name}'
        final_path = os.path.join(media_dir, stored_name)
        os.replace(tmp_path, final_path)

        # 옛 문서 삭제 — post_delete 시그널이 Qdrant 벡터까지 정리한다
        old.delete()

        doc = Document.objects.create(
            original_filename=uploaded_file.name,
            file_type=ext,
            storage_uri=f'/media/documents/{stored_name}',
            file_size=uploaded_file.size,
            checksum=checksum,
            status='uploaded',
            **carried,
        )

        from apps.rag.tasks import process_document
        process_document.delay(str(doc.id))

        data = self.get_serializer(doc).data
        data['replaced'] = {'previous_chunks': old_chunk_count}
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def file(self, request, pk=None):
        """GET /api/documents/{id}/file — 원문 열람 (C-4, 출처 칩 클릭 대상)

        ?page= 파라미터는 표기용이며 서버는 파일 전체를 내려준다.
        페이지 이동은 프론트가 PDF 뷰어의 #page= 프래그먼트로 처리한다.
        """
        doc = self.get_object()

        path = resolve_media_path(doc.storage_uri)
        if path is None:
            return Response(
                {'error': '원본 파일을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type = CONTENT_TYPES.get(doc.file_type, 'application/octet-stream')
        # 브라우저가 바로 렌더링할 수 있는 형식만 inline, 나머지는 다운로드된다.
        disposition = 'inline' if doc.file_type == 'pdf' else 'attachment'
        filename = doc.original_filename or os.path.basename(path)

        response = FileResponse(open(path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f"{disposition}; filename*=utf-8''{quote(filename)}"
        return response

    @action(detail=True, methods=['get'])
    def status_detail(self, request, pk=None):
        """GET /api/documents/{id}/status — 수집 진행 상태"""
        doc = self.get_object()
        return Response({
            'id': str(doc.id),
            'status': doc.status,
            'chunk_count': doc.chunks.count(),
            'indexed_at': doc.indexed_at,
        })

    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """GET /api/documents/{id}/chunks — 청크 목록"""
        doc = self.get_object()
        chunks = doc.chunks.all()
        serializer = DocumentChunkSerializer(chunks, many=True)
        return Response(serializer.data)
