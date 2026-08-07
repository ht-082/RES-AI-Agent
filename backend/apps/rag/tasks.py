import os
import uuid
import bisect
import logging
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from apps.documents.models import Document, DocumentChunk
from services.parser import parse_file
from services.embedding import embed_text
from apps.rag.chunkers import (chunk_admin, chunk_general, chunk_law,
                               chunk_markdown, chunk_paged, chunk_sheets,
                               chunk_structured, chunk_tables, normalize_chunks,
                               verify_chunk_invariants)
from services.qdrant_client import upsert_chunks

logger = logging.getLogger(__name__)

PAGE_JOIN_SEP = "\n"


def build_text_and_page_map(parsed_items, sep=PAGE_JOIN_SEP):
    """parsed_items를 한 덩어리 텍스트로 합치면서 (시작 오프셋 → 페이지) 지도를 만든다.

    계약서·법령의 조항은 페이지를 넘나들기 때문에 청킹 자체를 페이지 단위로 할 수 없다.
    대신 합칠 때 경계를 기록해 두고, 청크의 char_start로 페이지를 역산한다.
    반환: (full_text, page_starts, page_numbers)
    """
    parts, page_starts, page_numbers = [], [], []
    cursor = 0
    for item in parsed_items:
        text = item.get('text', '') or ''
        parts.append(text)
        page_starts.append(cursor)
        page_numbers.append(item.get('page_number'))
        cursor += len(text) + len(sep)
    return sep.join(parts), page_starts, page_numbers


def page_at_offset(page_starts, page_numbers, offset):
    """문자 오프셋이 속한 페이지 번호를 돌려준다."""
    if not page_starts or offset is None:
        return None
    idx = bisect.bisect_right(page_starts, offset) - 1
    return page_numbers[max(0, idx)]


def resolve_section_title(meta):
    """출처 표기용 위치 라벨(예: '제3조(계약기간)', 슬라이드 제목, 표/시트 라벨)"""
    title = (meta.get('article_no') or meta.get('slide_title')
             or meta.get('table_title') or meta.get('sheet_title')
             # 청커가 직접 붙인 섹션명(마크다운 헤딩 등). 이 키를 빠뜨려
             # 사업개요 섹션 제목이 출처 라벨에 나오지 않는 문제가 있었다.
             or meta.get('section_title') or '')
    article_title = meta.get('article_title')
    if title and article_title:
        title = f"{title}({article_title})"
    return title[:300]

def split_text_into_chunks(text, max_chars=800, overlap=150):
    """
    텍스트를 max_chars 크기로 자르고 overlap 만큼 겹치게 만듭니다.
    """
    if len(text) <= max_chars:
        return [text]
        
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start += (max_chars - overlap)
    return chunks

@shared_task(name='apps.rag.tasks.process_document')
def process_document(document_id):
    """
    Celery 태스크: 문서 파싱 → 청킹 → 임베딩 → Qdrant 적재 및 DB 저장
    """
    logger.info(f"문서 인덱싱 비동기 작업 시작: {document_id}")
    try:
        doc = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"인덱싱 대상 문서가 존재하지 않습니다: {document_id}")
        return {'success': False, 'chunk_count': 0, 'doc_type': 'unknown', 'error': 'Document Does Not Exist', 'fallback': False, 'scan_issue': False}

    doc.status = 'parsing'
    doc.save(update_fields=['status'])

    # 1. 파일의 절대경로 획득
    # storage_uri 가 '/media/documents/...' 형식이므로 MEDIA_ROOT와 결합
    filename = os.path.basename(doc.storage_uri)
    file_path = os.path.join(settings.MEDIA_ROOT, 'documents', filename)

    if not os.path.exists(file_path):
        # 만약 initial_docs 경로에서 복사되지 않았거나 로컬 경로에 없는 경우 fallback 검사
        initial_path = os.path.join(settings.MEDIA_ROOT, 'initial_docs', filename)
        if os.path.exists(initial_path):
            file_path = initial_path
        else:
            # 서브디렉토리까지 샅샅이 뒤지기
            found = False
            initial_docs_dir = os.path.join(settings.MEDIA_ROOT, 'initial_docs')
            for root_dir, _, files in os.walk(initial_docs_dir):
                if filename in files:
                    file_path = os.path.join(root_dir, filename)
                    found = True
                    break
            
            if not found:
                logger.error(f"원본 파일이 존재하지 않습니다: {filename}")
                doc.status = 'failed'
                doc.save(update_fields=['status'])
                return {'success': False, 'chunk_count': 0, 'doc_type': doc.doc_type, 'error': '원본 파일 부재', 'fallback': False, 'scan_issue': False}

    # 2. 문서 파싱 실행 (매직바이트 게이트 포함 — 전략 §3.0)
    from services.parser import ParserGateError
    try:
        parsed_items = parse_file(file_path)
    except ParserGateError as e:
        logger.warning(f"파싱 게이트 차단 ({e.reason}): {file_path}")
        doc.status = 'failed'
        doc.metadata = {**(doc.metadata or {}), 'fail_reason': e.reason}
        doc.save(update_fields=['status', 'metadata'])
        return {'success': False, 'chunk_count': 0, 'doc_type': doc.doc_type,
                'error': e.reason, 'fallback': False, 'scan_issue': False}

    if not parsed_items:
        logger.warning(f"문서 파싱 결과가 비어있습니다(스캔본 의심): {file_path}")
        doc.status = 'failed'
        doc.metadata = {**(doc.metadata or {}), 'fail_reason': 'empty-extract'}
        doc.save(update_fields=['status', 'metadata'])
        return {'success': False, 'chunk_count': 0, 'doc_type': doc.doc_type, 'error': '텍스트 0글자 (파싱 실패/스캔본)', 'fallback': False, 'scan_issue': True}

    doc.status = 'embedding'
    doc.save(update_fields=['status'])

    points = []
    chunk_objs = []
    chunk_index = 0

    try:
        from qdrant_client.models import PointStruct

        doc_type = getattr(doc, 'doc_type', 'general')
        final_chunks = []

        # 표 항목(kind='table')은 유형과 무관하게 독립 청크가 된다 (전략 §3.6)
        table_items = [i for i in parsed_items if i.get('kind') == 'table']
        body_items = [i for i in parsed_items if i.get('kind') != 'table']
        is_ocr = any(i.get('ocr') for i in parsed_items)

        # ── 라우팅 (v2) ────────────────────────────────────────────────
        # 판단 순서: ① 포맷이 구조를 정하는가 → ② doc_type
        #
        # 핵심 원칙: **페이지 단위 청킹은 페이지가 실재하는 포맷에서만** 한다.
        # page_number의 실체가 포맷마다 다르기 때문이다.
        #   pdf  = 진짜 페이지 / pptx = 슬라이드      → 페이지 단위 타당
        #   docx = 단락 5개마다 끊은 인위적 순번       → 무의미
        #   hwp  = 전부 1 (hwp5txt가 페이지를 안 준다) → 통짜 청크가 된다
        # v1은 이 구분 없이 doc_type만 보고 라우팅해, report/admin으로 분류된
        # hwp 문서가 조용히 문서 전체 1청크가 되고 있었다.
        page_starts, page_numbers = [], []
        ext = (doc.file_type or '').lower()
        has_real_pages = ext in ('pdf', 'pptx')

        if ext == 'xlsx':
            final_chunks = chunk_sheets(body_items, doc_type=doc_type)
        elif ext in ('md', 'markdown', 'txt'):
            # 마크다운은 분류와 무관하게 헤딩 구조를 존중한다
            # (사업개요처럼 사람이 관리하는 정리본 — 헤딩에 사업명이 들어 있다)
            final_chunks = chunk_markdown(body_items, filename=doc.title)
        elif doc_type == 'report' and has_real_pages:
            final_chunks = chunk_paged(body_items, filename=doc.title, doc_type='report')
        elif doc_type == 'admin':
            final_chunks = chunk_admin(body_items, filename=doc.title, paged=has_real_pages)
        else:
            full_text, page_starts, page_numbers = build_text_and_page_map(body_items)
            if doc_type == 'law':
                final_chunks = chunk_law(full_text, filename=doc.title)
            elif doc_type in ('contract', 'spec'):
                # spec은 폐지된 분류 — 구조형 청커가 경계 패턴을 자동 선택한다
                final_chunks = chunk_structured(full_text, filename=doc.title,
                                                doc_type='contract')
            elif doc_type == 'report':
                # 페이지가 없는 포맷의 보고서 — 구조를 먼저 시도한다
                final_chunks = chunk_structured(full_text, filename=doc.title,
                                                doc_type='report')
            else:
                final_chunks = chunk_general(full_text, doc_type=doc_type or 'general')

        # 표 청크 부착 (페이지 번호는 표가 있던 페이지 그대로)
        final_chunks = list(final_chunks) + chunk_tables(table_items, doc_type=doc_type)

        # ── 단일 출구 ──────────────────────────────────────────────────
        # 어떤 경로로 왔든 여기서 크기 상한·최소 길이·제어문자·중복을 강제한다.
        # v1은 xlsx·표·전문 세 경로가 이 검증을 우회해 초과 청크 301개(최대 138,570자)와
        # 같은 표 22회 반복 같은 중복 285건이 생겼다.
        final_chunks = normalize_chunks(final_chunks, doc_type=doc_type,
                                        source=doc.title[:40])

        # 출구를 거쳤어도 한 번 더 검사한다. v1의 사고는 "규칙이 없어서"가 아니라
        # "규칙을 우회하는 경로가 생겨서"였다. 새 경로가 추가돼도 여기서 잡힌다.
        violations = verify_chunk_invariants(final_chunks)
        if violations:
            logger.error(f"🚨 불변조건 위반 {len(violations)}건 — {doc.title}\n  "
                         + "\n  ".join(violations[:10]))

        for chunk_data in final_chunks:
            sub_text = chunk_data.get('text', '')
            meta = chunk_data.get('metadata', {})

            # 3-1. 출처 위치 확정 (page_number / section_title / char 오프셋)
            # report는 청커가 page_no를 직접 넣어주고, 그 외는 char_start로 역산한다.
            char_start = meta.get('char_start')
            page_no = meta.get('page_no')
            if page_no is None:
                page_no = page_at_offset(page_starts, page_numbers, char_start)
                if page_no is not None:
                    meta['page_no'] = page_no
            section_title = resolve_section_title(meta)
            char_end = char_start + len(sub_text) if char_start is not None else None

            # 4. BGE-M3 임베딩 생성 (dense + sparse)
            vectors = embed_text(sub_text)
            dense_vec = vectors['dense']
            sparse_vec = vectors['sparse']

            # 5. Qdrant 포인트 및 UUID 매핑
            point_id = uuid.uuid4()
            
            qdrant_vectors = {'dense': dense_vec}
            if sparse_vec and len(sparse_vec) > 0:
                from qdrant_client.models import SparseVector
                qdrant_vectors['sparse'] = SparseVector(
                    indices=[int(k) for k in sparse_vec.keys()],
                    values=[float(v) for v in sparse_vec.values()]
                )

            # 본문(content)은 payload에 넣지 않는다. 포인트가 무거워져 Qdrant 메모리가
            # 급증하며, 본문은 Postgres에서 조회한다(services/retriever.py 참조).
            payload = {
                'chunk_id': str(point_id),
                'document_id': str(doc.id),
                'project_id': str(doc.project.id) if doc.project else None,
                'is_global': doc.project is None,
                'document_title': doc.title,
                'file_type': doc.file_type,
                'page_number': page_no,
                'section_title': section_title,
                'metadata': meta
            }

            points.append(PointStruct(
                id=str(point_id),
                vector=qdrant_vectors,
                payload=payload
            ))

            # 6. PostgreSQL 저장을 위한 chunk 레코드 인스턴스화
            chunk_objs.append(DocumentChunk(
                document=doc,
                chunk_index=chunk_index,
                content=sub_text,
                page_number=page_no,
                section_title=section_title,
                char_start=char_start,
                char_end=char_end,
                # 시트/셀 범위는 xlsx 출처 라벨("시트: 운영비예산 (1-250행)")에 쓰인다.
                # 메타에는 담기면서 전용 컬럼에는 넘기지 않아 채움률이 0%였다.
                sheet_name=meta.get('sheet_name', '') or '',
                cell_range=meta.get('cell_range', '') or '',
                metadata=meta,
                token_count=len(sub_text),
                qdrant_point_id=point_id
            ))
            chunk_index += 1

        # 7. Qdrant 및 PostgreSQL 일괄 업로드 실행 (문서의 코퍼스 버전 컬렉션으로)
        if points:
            collection = doc.corpus.collection_name if doc.corpus_id and doc.corpus else None
            upsert_chunks(points, collection_name=collection)
            DocumentChunk.objects.bulk_create(chunk_objs)

        # 8. 청킹 폴백 여부 판정
        # law/contract인데 '제N조' 패턴을 못 찾으면 청커가 general(기계 분할)로 떨어진다.
        # 로그로만 알리면 나중에 어느 문서가 그랬는지 추적할 수 없으므로 문서에 기록한다.
        fallback_occurred = bool(
            doc_type in ('contract', 'law', 'spec') and final_chunks
            and final_chunks[0].get('metadata', {}).get('boundary') == 'none'
        )
        if fallback_occurred:
            logger.warning(
                f"⚠️ 청킹 폴백: {doc.title} (유형={doc_type}) — 조항 패턴을 찾지 못해 "
                f"general 기계 분할로 처리됨. 분류 오류이거나 조항 서식이 다를 수 있음."
            )

        # 9. 최종 문서 상태 저장
        doc.status = 'indexed'
        doc.indexed_at = timezone.now()
        doc.page_count = len(parsed_items)
        doc.metadata = {**(doc.metadata or {}), 'chunking_fallback': fallback_occurred,
                        'ocr': is_ocr}
        doc.save(update_fields=['status', 'indexed_at', 'page_count', 'metadata'])
        logger.info(f"문서 인덱싱 성공 완료 ({len(points)}개 청크 적재): {doc.title}")


        return {
            'success': True,
            'chunk_count': len(points),
            'doc_type': doc_type,
            'error': None,
            'fallback': fallback_occurred,
            'scan_issue': False
        }

    except Exception as e:
        logger.error(f"문서 인덱싱 중 예외 발생 ({doc.title}): {e}", exc_info=True)
        doc.status = 'failed'
        doc.save(update_fields=['status'])
        return {
            'success': False,
            'chunk_count': 0,
            'doc_type': getattr(doc, 'doc_type', 'unknown'),
            'error': str(e),
            'fallback': False,
            'scan_issue': False
        }
