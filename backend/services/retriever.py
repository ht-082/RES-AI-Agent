"""Qdrant 하이브리드 검색 + BGE 리랭커.

리랭커는 **순위 결정에만** 사용한다. 필터 기준 점수(AdapterHit.score)로는 Qdrant
하이브리드 점수를 그대로 넘긴다. 리랭커 점수는 코사인 유사도와 분포가 달라
RAG_SIMILARITY_THRESHOLD(코사인 기준으로 튜닝된 값)와 호환되지 않기 때문이다.
"""
import hashlib
import logging
import math
import os
import re
from typing import List

from django.conf import settings
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from services.embedding import embed_text

logger = logging.getLogger(__name__)

# HuggingFace 전용 사내망 SSL 인증서 우회
os.environ['HF_HUB_DISABLE_SSL_VERIFICATION'] = '1'

_reranker = None


class AdapterHit:
    """views.py가 기대하는 ScoredPoint 형태(score, payload)를 모방하는 래퍼 클래스.

    score        : Qdrant 하이브리드 점수 (기존 호출부 호환)
    rerank_score : 리랭커 확률(0~1). 리랭킹을 건너뛴 경우 None.
    """

    def __init__(self, score, payload, rerank_score=None):
        self.score = score
        self.payload = payload
        self.rerank_score = rerank_score


class ExistingQdrantRetriever(BaseRetriever):
    """Qdrant 하이브리드 검색(Prefetch API) 래퍼"""

    project_id: str | None = None
    top_k: int = 20
    collection_name: str | None = None  # None이면 settings 기본 컬렉션

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        # 1. 임베딩 (인덱싱과 동일한 BGE-M3 경로 재사용)
        vectors = embed_text(query)
        dense = vectors['dense']
        sparse = vectors['sparse']

        from qdrant_client.models import (FieldCondition, Filter, MatchValue,
                                          Prefetch, SparseVector)

        from services.qdrant_client import get_client

        client = get_client()
        collection_name = self.collection_name or getattr(settings, 'QDRANT_COLLECTION', 're_documents')

        # 보안 필터 적용
        #
        # should = OR. "그 사업의 문서" **또는** "사업 무관 공통 문서(법령·지침)"를 뽑는다.
        # must로 project_id만 걸면 사업을 지정하는 순간 법령이 통째로 배제된다 —
        # 그런데 실제 질문의 상당수가 "당진 부지가 농지인데 개발행위허가 뭐 필요해?"처럼
        # 사내 문서와 법령 근거를 **같이** 요구한다.
        query_filter = None
        if self.project_id:
            query_filter = Filter(should=[
                FieldCondition(key="project_id", match=MatchValue(value=self.project_id)),
                FieldCondition(key="is_global", match=MatchValue(value=True)),
            ])

        # Pydantic이 {int: float} 딕셔너리를 거부하므로 공식 SparseVector로 변환한다.
        sparse_query = None
        if sparse:
            sparse_query = SparseVector(
                indices=list(sparse.keys()),
                values=list(sparse.values()),
            )

        try:
            hits = client.query_points(
                collection_name=collection_name,
                prefetch=[
                    Prefetch(
                        query=sparse_query,
                        using="sparse",
                        limit=self.top_k,
                        filter=query_filter,
                    )
                ] if sparse_query else None,
                query=dense,
                using="dense",
                limit=self.top_k,
                query_filter=query_filter,
                with_payload=True,
            ).points
        except Exception as e:
            logger.error(f"🚨 리트리버 내 하이브리드 검색 실패: {e}")
            raise e

        return self._to_documents(hits)

    def _to_documents(self, hits) -> List[Document]:
        """Qdrant 결과를 Document로 변환한다.

        본문은 Qdrant payload에 저장하지 않으므로 Postgres에서 채운다.
        (payload에 넣으면 포인트가 무거워져 Qdrant 메모리 사용량이 커진다.)
        """
        from apps.documents.models import DocumentChunk

        metas = []
        for hit in hits:
            meta = dict(getattr(hit, 'payload', {}) or {})
            meta['qdrant_score'] = getattr(hit, 'score', 0.0)
            metas.append(meta)

        # 본문 일괄 조회 (건별 조회 시 N+1이 된다)
        chunk_ids = [m.get('chunk_id') for m in metas if m.get('chunk_id')]
        contents = {
            str(pid): text
            for pid, text in DocumentChunk.objects
            .filter(qdrant_point_id__in=chunk_ids)
            .values_list('qdrant_point_id', 'content')
        }

        docs = []
        orphans = 0
        for meta in metas:
            content = contents.get(str(meta.get('chunk_id'))) or ''
            if not content:
                orphans += 1
            docs.append(Document(page_content=content, metadata=meta))

        if orphans:
            logger.warning(
                f"본문 없는 후보 {orphans}/{len(docs)}건 — Qdrant 포인트에 대응하는 "
                f"DocumentChunk가 없습니다(재적재 잔여물 가능성)."
            )
        return docs


RERANK_MODEL_ID = "BAAI/bge-reranker-v2-m3"


class _CrossEncoderAdapter:
    """sentence-transformers CrossEncoder를 기존 호출부(.score / .client)와 맞춰주는 래퍼."""

    def __init__(self, cross_encoder):
        self.client = cross_encoder

    def score(self, pairs):
        if not pairs:
            return []
        return self.client.predict(pairs, batch_size=len(pairs))


def _load_openvino_reranker(backend):
    """OpenVINO 백엔드 리랭커 로드. 실패 시 None을 반환해 호출측이 폴백하게 한다."""
    from sentence_transformers import CrossEncoder

    max_len = getattr(settings, 'RERANK_MAX_LENGTH', 384)
    if backend == 'openvino_int8':
        path = getattr(settings, 'RERANK_OV_INT8_DIR', '')
        if not path or not os.path.exists(os.path.join(path, 'openvino_model.xml')):
            logger.warning(f"OpenVINO INT8 IR이 없습니다({path}) — 생성: "
                           f"python bench_openvino.py c")
            return None
    else:
        path = RERANK_MODEL_ID

    logger.info(f"리랭커 로드 중 (backend={backend}, path={path})...")
    ce = CrossEncoder(path, max_length=max_len, backend='openvino')
    logger.info(f"리랭커 로드 완료 (backend={backend}, max_length={max_len})")
    return _CrossEncoderAdapter(ce)


def get_reranker():
    """BGE 리랭커 (프로세스당 1회 지연 로드).

    백엔드는 settings.RERANK_BACKEND로 고른다. OpenVINO 경로가 실패하면
    기존 torch 경로로 조용히 폴백해 서비스가 멈추지 않게 한다.
    """
    global _reranker
    if _reranker is not None:
        return _reranker

    backend = getattr(settings, 'RERANK_BACKEND', 'torch')
    if backend in ('openvino_int8', 'openvino'):
        try:
            model = _load_openvino_reranker(backend)
            if model is not None:
                _reranker = model
                return _reranker
        except Exception as e:
            logger.warning(f"OpenVINO 리랭커 로드 실패, torch로 폴백합니다: {e}")

    from langchain_community.cross_encoders import HuggingFaceCrossEncoder
    logger.info(f"리랭커 모델 로드 중 (torch, {RERANK_MODEL_ID})...")
    model = HuggingFaceCrossEncoder(model_name=RERANK_MODEL_ID)

    # 입력 토큰 상한. 모델 기본값(8192)을 그대로 두면 배치가 최장 청크에 맞춰
    # 패딩되어 대부분의 연산이 빈 칸에 쓰인다. (CPU 실측 46.8초 → 14.9초)
    max_len = getattr(settings, 'RERANK_MAX_LENGTH', 384)
    try:
        model.client.max_seq_length = max_len
        logger.info(f"리랭커 max_seq_length={max_len} 적용")
    except Exception as e:
        logger.warning(f"리랭커 max_seq_length 설정 실패, 모델 기본값 사용: {e}")

    _reranker = model
    logger.info("리랭커 모델 로드 완료 (torch)")
    return _reranker


_PROJECT_LABEL_CACHE = None


def _project_label_map():
    """project_id -> 사업명. 적재 때 헤더에 쓴 이름과 같아야 하므로 같은 함수를 쓴다.

    임포트를 함수 안에서 하는 이유: apps.rag.tasks가 services.*를 임포트하므로
    모듈 상단에서 부르면 순환 임포트가 된다.
    """
    global _PROJECT_LABEL_CACHE
    if _PROJECT_LABEL_CACHE is None:
        try:
            from apps.rag.tasks import project_label
            from apps.workspaces.models import Project
            _PROJECT_LABEL_CACHE = {
                str(p.id): project_label(p) for p in Project.objects.all()
            }
        except Exception as e:
            logger.warning(f"사업명 매핑 로드 실패 — 리랭커 헤더에서 사업명을 생략한다: {e}")
            _PROJECT_LABEL_CACHE = {}
    return _PROJECT_LABEL_CACHE


def _rerank_context_header(meta: dict) -> str:
    """리랭커 입력 앞에 붙일 컨텍스트 헤더 [C-2 보완].

    임베딩 입력에는 '[사업: X] [문서: Y]'가 붙는데(tasks.build_embed_header)
    리랭커에는 본문만 들어가고 있었다. 그래서 **문서명이 신호를 다 가진 청크**가
    본문에 질의어가 없다는 이유로 밀렸다. 실측(2026-08-26):
    '계약서_설계용역_251231.docx'의 계약 당사자 조항이 질의
    '홍성 설계 인허가 용역 어떤 업체에서 하는데?'에 대해 0.116 -> 0.830.

    md/txt는 임베딩과 같은 이유로 건너뛴다(헤딩에 사업명이 이미 들어 있다).
    어떤 이유로든 실패하면 빈 문자열을 돌려 기존 동작(본문만)으로 폴백한다.
    """
    try:
        from apps.rag.tasks import HEADER_SKIP_EXTS  # 적재 쪽과 규칙을 공유한다
        if (meta.get('file_type') or '').lower() in HEADER_SKIP_EXTS:
            return ''
        title = os.path.splitext(meta.get('document_title') or '')[0].strip()
        proj = ''
        pid = meta.get('project_id')
        if pid and not meta.get('is_global'):
            proj = _project_label_map().get(str(pid), '')
        parts = []
        if proj:
            parts.append(f'[사업: {proj}]')
        if title:
            parts.append(f'[문서: {title}]')
        return ' '.join(parts)
    except Exception as e:
        logger.debug(f"리랭커 헤더 생성 실패(본문만 사용): {e}")
        return ''


def rerank_documents(query: str, docs: List[Document]) -> List[Document]:
    """리랭커 점수 내림차순으로 재정렬한다.

    bge-reranker-v2-m3의 출력은 로짓(대략 -12 ~ +12)이라 그대로는 컷 기준으로 쓰기
    어렵다. 시그모이드를 씌운 확률(0~1)을 metadata['rerank_score']에 함께 남겨
    관련성 게이트가 해석 가능한 값으로 판단하게 한다.

    입력에는 임베딩과 동일한 컨텍스트 헤더를 붙인다(_rerank_context_header).
    """
    if not docs:
        return docs
    pairs = []
    for d in docs:
        head = _rerank_context_header(d.metadata or {})
        joined = (head + chr(10) + d.page_content) if head else d.page_content
        pairs.append((query, joined))
    scores = get_reranker().score(pairs)
    for doc, score in zip(docs, scores):
        logit = float(score)
        doc.metadata['rerank_logit'] = logit
        # 로짓이 극단값일 때 math.exp 오버플로를 피한다.
        doc.metadata['rerank_score'] = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, logit))))
    return sorted(docs, key=lambda d: d.metadata['rerank_score'], reverse=True)


def _content_key(text: str) -> str | None:
    """중복 판정용 정규화 해시. 공백 차이만 있는 청크를 같은 것으로 본다."""
    norm = re.sub(r'\s+', ' ', text or '').strip()
    if not norm:
        return None
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()


def dedupe_documents(docs: List[Document]) -> List[Document]:
    """[H-2] 내용이 동일한 청크를 제거한다 (순위가 높은 쪽을 남긴다).

    코퍼스에 같은 내용 청크가 568종 존재한다(같은 문서 내 285 + 문서 간 1,359).
    이것이 컨텍스트 8칸 중 4칸을 잠식해, 실제로 비교 질문이 "자료에 없습니다"로
    실패한 사례가 확인됐다. 정렬 이후·컷 이전에 제거해야 상위 칸이 고유 내용으로 찬다.

    판정은 '완전 일치(공백 정규화 후)'만 한다. 근사 중복까지 묶으면 서로 다른
    사업의 유사 조항이 하나로 합쳐질 위험이 있다.
    """
    seen, kept, dropped = set(), [], []
    for doc in docs:
        key = _content_key(doc.page_content)
        if key is None:
            kept.append(doc)          # 본문 없는 후보는 판정 불가 — 그대로 둔다
            continue
        if key in seen:
            dropped.append(doc)
            continue
        seen.add(key)
        kept.append(doc)

    if dropped:
        titles = {d.metadata.get('document_title', '?') for d in dropped}
        logger.info(f"[중복제거] {len(dropped)}건 제거 → {len(kept)}건 "
                    f"(문서: {', '.join(list(titles)[:3])})")
    return kept


def should_rerank(docs: List[Document]) -> tuple[bool, str]:
    """조건부 리랭킹 판정 — 리랭킹이 결과를 바꿀 여지가 있을 때만 실행한다.

    리랭커는 질의당 수 초를 쓰는 가장 비싼 단계다. 그런데 Qdrant 점수만으로도
    '어떤 문서가 컨텍스트에 들어갈지'가 이미 명확한 질의가 있다. 컨텍스트 경계
    (MAX_CONTEXT_K번째와 그 다음 문서) 사이 점수 차가 전체 점수 폭에서 충분히 크면
    선택이 뒤집힐 가능성이 낮으므로 건너뛴다.

    반환: (실행 여부, 사유)
    """
    if not getattr(settings, 'RERANK_ENABLED', True):
        return False, 'disabled'

    ctx_k = getattr(settings, 'RAG_MAX_CONTEXT_K', 8)
    margin = getattr(settings, 'RERANK_SKIP_MARGIN', 0.0)
    if margin <= 0:
        return True, 'always'
    if len(docs) <= ctx_k:
        # 후보가 컨텍스트 정원 이하면 '선택'이 없다. 다만 순서는 답변 품질에
        # 영향을 주므로 후보가 매우 적을 때만 건너뛴다.
        if len(docs) <= 2:
            return False, f'candidates<=2({len(docs)})'
        return True, f'no-selection-but-order({len(docs)})'

    scores = sorted((float(d.metadata.get('qdrant_score', 0.0)) for d in docs), reverse=True)
    span = scores[0] - scores[-1]
    if span <= 1e-9:
        return True, 'flat-scores'
    gap = scores[ctx_k - 1] - scores[ctx_k]
    ratio = gap / span
    if ratio >= margin:
        return False, f'clear-boundary(gap={ratio:.2f}>={margin})'
    return True, f'ambiguous(gap={ratio:.2f}<{margin})'


def apply_relevance_gate(hits) -> tuple[list, str]:
    """[C-3] 관련성 게이트 — '자료에 없다'를 판정할 수 있게 만든다.

    기존에는 청크별로 Qdrant 점수 >= 0.5 만 봤는데, 실제 출처 197건 중 탈락은 1건뿐
    이었다. 즉 질문이 코퍼스와 무관해도 항상 8칸이 채워졌고, LLM은 무관한 자료를
    받아 "정보가 없습니다"라고 답하거나 지어낼 위험에 놓였다.

    실측(질의 10건: 코퍼스에 답이 있는 6건 / 전혀 없는 4건)으로 1위 점수가
    두 그룹을 깨끗하게 가른다는 것을 확인했다.

        리랭커 확률  답있음 0.6019~0.7310  vs  답없음 0.5001~0.5179
        Qdrant 점수  답있음 0.6464~0.8115  vs  답없음 0.3949~0.4715

    두 지표 모두 빈 구간 한가운데인 0.55를 기준으로 삼는다.

    2단 구성:
      ① 질의 게이트 — 1위가 바닥값 미만이면 전부 버리고 '자료 없음'으로 분기
      ② 상대 컷    — 1위에서 일정 폭 이상 떨어진 꼬리를 버려 노이즈가 칸을 먹지 않게

    표본이 10건뿐이므로 값은 모두 settings로 조정 가능하게 둔다.
    """
    if not hits:
        return [], 'empty'

    use_rerank = hits[0].rerank_score is not None
    if use_rerank:
        key = lambda h: h.rerank_score
        floor = getattr(settings, 'RAG_GATE_MIN_TOP1_RERANK', 0.55)
        margin = getattr(settings, 'RAG_GATE_REL_MARGIN_RERANK', 0.12)
        label = 'rerank'
    else:
        # 리랭킹을 건너뛴 경우(should_rerank가 False) Qdrant 점수로 같은 판정을 한다.
        key = lambda h: h.score
        floor = getattr(settings, 'RAG_GATE_MIN_TOP1_QDRANT', 0.55)
        margin = getattr(settings, 'RAG_GATE_REL_MARGIN_QDRANT', 0.15)
        label = 'qdrant'

    top1 = max(key(h) for h in hits)
    if top1 < floor:
        return [], f'{label}-top1={top1:.4f}<{floor} (관련 자료 없음)'

    cut = top1 - margin
    kept = [h for h in hits if key(h) >= cut]
    return kept, f'{label}-top1={top1:.4f} cut>={cut:.4f} {len(kept)}/{len(hits)}'


def retrieve_for_views(query: str, project_id: str | None = None,
                       corpus_version: str | None = None):
    """views.py 진입점.

    반환 순서는 리랭커 순위이며, AdapterHit.score에는 Qdrant 점수가 담긴다.
    호출측은 이 순서를 유지해야 리랭킹이 반영된다(재정렬 금지).
    corpus_version: 코퍼스 버전 라벨('1.0' 등). 빈 값/None이면 is_active 버전.
    """
    from services.qdrant_client import resolve_collection
    retriever = ExistingQdrantRetriever(
        project_id=str(project_id) if project_id else None,
        top_k=getattr(settings, 'RAG_RETRIEVE_K', 20),
        collection_name=resolve_collection(corpus_version),
    )
    docs = retriever.invoke(query)

    do_rerank, reason = should_rerank(docs)
    if do_rerank:
        try:
            docs = rerank_documents(query, docs)
        except Exception as e:
            logger.error(f"🚨 리랭킹 실패, Qdrant 순위로 폴백합니다: {e}")
    else:
        logger.info(f"리랭킹 건너뜀 ({reason}) — Qdrant 순위 사용")

    # [H-2] 정렬 뒤·컷 앞에서 중복 제거 — 상위 칸이 고유 내용으로 차게 한다.
    docs = dedupe_documents(docs)

    return [
        AdapterHit(
            score=doc.metadata.get('qdrant_score', 0.0),
            payload=doc.metadata,
            rerank_score=doc.metadata.get('rerank_score'),
        )
        for doc in docs
    ]
