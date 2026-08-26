import os
import re
import json
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

# 청크 ID 네임스페이스 [C-4]. uuid5의 씨앗이 되는 고정 상수라 값 자체는 무의미하지만
# **절대 바꾸면 안 된다** — 바뀌는 순간 기존 청크 ID가 전부 달라진다.
CHUNK_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, 'chunk.re-ai-agent.local')

# 헤더를 붙이지 않는 포맷. 마크다운(사업개요)은 헤딩이 이미 본문에 포함돼 있어
# 사업명이 청크 안에 살아 있다. 중복해서 붙이면 짧은 청크가 헤더에 지배된다.
HEADER_SKIP_EXTS = ('md', 'markdown', 'txt')

# 적재를 중단시킬 만큼 치명적인 불변조건 위반 [H-4]. '위치정보 없음'은 여기 없다 —
# 출처 라벨 품질 문제일 뿐 데이터 오염이 아니라서 경고로만 남긴다.
FATAL_INVARIANT_KEYS = ('크기 초과', '제어문자', '내용 중복', 'doc_type 없음', '길이 부족')

_NUM_PREFIX = re.compile(r'^\s*\d+\s*[.)]\s*')
# 청크 ID 씨앗의 공백 정규화 — chunkers.normalize_chunks의 중복 제거 키와 동일해야 한다
_WS = re.compile(r'\s+')
_alias_cache = None


def project_aliases():
    """폴더명 → 사업명 매핑을 읽는다(1회 캐시). 파일이 없으면 빈 표로 동작한다."""
    global _alias_cache
    if _alias_cache is None:
        path = getattr(settings, 'PROJECT_ALIAS_FILE', '')
        try:
            with open(path, encoding='utf-8') as f:
                raw = json.load(f)
            _alias_cache = {k: v for k, v in raw.items() if not k.startswith('_')}
        except (OSError, ValueError) as e:
            logger.warning(f"프로젝트 별칭 파일을 읽지 못했습니다({path}): {e} — 폴더명을 그대로 씁니다.")
            _alias_cache = {}
    return _alias_cache


def project_label(project):
    """수집 폴더명을 사용자가 실제로 질문에 쓰는 사업명으로 바꾼다.

    폴더는 '2. 당진1PJT'인데 질의는 '당진행복솔라 PF 대주단…'으로 들어온다.
    폴더명을 그대로 헤더에 넣으면 헤더를 붙이는 의미가 없다.
    매핑값이 None이면 '사업 소속 없음'(법령·지침)이라는 뜻이라 빈 문자열을 준다.
    """
    if project is None:
        return ''
    aliases = project_aliases()
    name = project.name or ''
    if name in aliases:
        return (aliases[name] or '').strip()
    # 폴더명을 바꾸면 별칭표 키가 어긋나 폴더명이 그대로 헤더에 박힌다.
    # (실측: '4. 임자'→'4. 임자 PJT' 개명으로 '임자도태양광'이 '임자 PJT'가 됐다)
    # 조용히 품질만 떨어지는 종류의 사고라 적재 로그에 남긴다.
    fallback = _NUM_PREFIX.sub('', name).strip()
    logger.warning(f"별칭표에 없는 프로젝트 폴더: {name!r} → 헤더에 {fallback!r}를 씁니다. "
                   f"project_aliases.json 확인 필요.")
    return fallback


def is_global_folder(name):
    """별칭표에 값이 null로 등록된 폴더 = 특정 사업 소속이 아닌 공통 문서(법령·지침).

    '헤더에 사업명을 안 붙인다'와 '프로젝트에 묶지 않는다'는 같은 판단이라
    표 하나로 관리한다. 프로젝트에 묶이면 payload의 `is_global`이 False가 되고,
    프로젝트를 지정해 질문하는 순간 법령이 통째로 필터에서 배제된다.
    """
    aliases = project_aliases()
    return name in aliases and not (aliases[name] or '').strip()


def build_embed_header(doc, max_chars=None):
    """임베딩 입력 앞에 붙일 컨텍스트 헤더를 만든다 [C-2].

    형식: '[사업: 당진행복솔라] [문서: 대주별 선순위 인출금액]'
    - **사업명과 문서명만** 넣는다. 문서 종류(계약서·허가증…)는 넣지 않는다 —
      종류가 너무 많아 분류가 어렵고, 틀린 라벨을 벡터에 박으면 안 붙이는 것보다 나쁘다.
      doc_type은 payload에 그대로 남으므로 필요하면 검색 필터로 쓴다.
    - 상한을 넘으면 문서명 쪽을 줄인다(사업명이 검색 효과의 핵심이라 우선 보존).
    """
    if not getattr(settings, 'RAG_EMBED_CONTEXT_HEADER', True):
        return ''
    if (doc.file_type or '').lower() in HEADER_SKIP_EXTS:
        return ''

    limit = max_chars or getattr(settings, 'RAG_EMBED_HEADER_MAX_CHARS', 60)
    proj = project_label(doc.project)
    title = os.path.splitext(doc.title or '')[0].strip()

    prefix = f'[사업: {proj}] ' if proj else ''
    if not title:
        return prefix.strip()

    budget = limit - len(prefix) - len('[문서: ]')
    if budget < 8:
        # 사업명만으로 이미 상한이라 문서명은 포기한다(사업명 우선).
        return prefix.strip()
    if len(title) > budget:
        title = title[:budget - 1] + '…'
    return f'{prefix}[문서: {title}]'


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

        if ext in ('xlsx', 'xlsm'):
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

        # 위반을 로그로만 남기면 6~9시간짜리 배치가 끝난 뒤에야 알게 된다.
        # 치명적 위반이 있는 문서는 적재하지 않고 failed로 떨궈, 수집 리포트의
        # 실패 목록에 사유와 함께 올라오게 한다(배치 전체는 계속 진행된다).
        fatal = [v for v in violations if any(k in v for k in FATAL_INVARIANT_KEYS)]
        if fatal and getattr(settings, 'RAG_STRICT_INVARIANTS', True):
            doc.status = 'failed'
            doc.metadata = {**(doc.metadata or {}),
                            'fail_reason': 'invariant-violation',
                            'invariants': fatal[:20]}
            doc.save(update_fields=['status', 'metadata'])
            logger.error(f"⛔ 불변조건 위반으로 적재 중단 — {doc.title} (치명 {len(fatal)}건)")
            return {'success': False, 'chunk_count': 0, 'doc_type': doc_type,
                    'error': f'불변조건 위반 {len(fatal)}건 ({fatal[0]})',
                    'fallback': False, 'scan_issue': False}

        # 임베딩 입력용 컨텍스트 헤더 [C-2] — 문서당 1회 계산해 모든 청크에 공통 적용
        embed_header = build_embed_header(doc)
        # 결정적 청크 ID [C-4]의 씨앗.
        #   ① 코퍼스 버전 — 같은 파일을 2.0·3.0에 적재해도 ID가 겹치지 않게 한다
        #      (qdrant_point_id는 unique 제약이라 겹치면 적재가 터진다)
        #   ② 파일 슬롯(폴더+파일명) — checksum을 쓰면 파일을 한 글자만 고쳐도
        #      전 청크 ID가 바뀌어, 정작 노린 '교체해도 출처 유지'가 안 된다.
        #      사업개요처럼 계속 손보는 문서에서 그 차이가 그대로 드러난다.
        collection = doc.corpus.collection_name if doc.corpus_id and doc.corpus else None
        file_key = f"{(doc.metadata or {}).get('source_path', '')}/{doc.original_filename or doc.title}"
        id_seed = f"{collection or 'default'}:{file_key}"

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
            # 헤더는 **임베딩 입력에만** 붙는다. 아래 content/payload에는 들어가지
            # 않으므로 화면에 보이는 본문과 LLM이 읽는 본문은 원문 그대로다.
            embed_input = f'{embed_header}\n{sub_text}' if embed_header else sub_text
            vectors = embed_text(embed_input)
            dense_vec = vectors['dense']
            sparse_vec = vectors['sparse']

            # 5. Qdrant 포인트 및 UUID 매핑
            # 결정적 ID [C-4]: 같은 코퍼스·같은 파일 슬롯·같은 내용이면 몇 번을 다시
            # 적재해도 ID가 같다. 순번(chunk_index)이 아니라 **내용**을 씨앗으로 쓰는
            # 이유는, 문서 앞부분에 한 문단을 끼워 넣으면 순번이 통째로 밀려 뒤쪽
            # 청크가 전부 '다른 청크'가 돼버리기 때문이다.
            # 정규화식은 normalize_chunks의 중복 제거 키와 **일부러 똑같이** 맞췄다.
            # 그래야 "ID가 겹치는 두 청크"는 이미 중복으로 걸러진 것뿐이라
            # unique 제약 위반이 원리적으로 생기지 않는다.
            id_text = _WS.sub(' ', sub_text).strip()
            point_id = uuid.uuid5(CHUNK_ID_NAMESPACE, f'{id_seed}:{id_text}')

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
        # 헤더는 벡터에만 녹아 있어 나중에 눈으로 확인할 방법이 없다. 무엇이 붙었는지
        # 문서에 남겨 두면 검색이 이상할 때 '헤더가 틀렸나'를 즉시 확인할 수 있다.
        doc.metadata = {**(doc.metadata or {}), 'chunking_fallback': fallback_occurred,
                        'ocr': is_ocr, 'embed_header': embed_header,
                        'chunk_id_scheme': 'uuid5'}
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
