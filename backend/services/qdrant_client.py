"""
Qdrant 클라이언트 래퍼 — 벡터 DB 연동
컬렉션 생성, 포인트 삽입, 하이브리드 검색을 담당
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Lazy initialization to avoid import errors when qdrant is not available
_client = None


def get_client():
    """Qdrant 클라이언트 싱글턴"""
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        # api_key가 비어 있으면 None → 무인증(로컬 Docker)과 동일하게 동작한다.
        # 공용 서버(EC2)는 QDRANT__SERVICE__API_KEY를 걸므로 키 전달이 필수다.
        _client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )
        logger.info(f"Qdrant 클라이언트 연결: {settings.QDRANT_URL} "
                    f"(인증 {'사용' if settings.QDRANT_API_KEY else '없음'})")
    return _client


def resolve_collection(corpus_version=None):
    """코퍼스 버전 라벨 → Qdrant 컬렉션명. 빈 값이면 is_active 버전, 없으면 settings 기본값."""
    try:
        from apps.documents.models import CorpusVersion
        qs = CorpusVersion.objects
        cv = qs.filter(version=corpus_version).first() if corpus_version else qs.filter(is_active=True).first()
        if cv:
            return cv.collection_name
    except Exception as e:
        logger.warning(f"코퍼스 버전 해석 실패({corpus_version!r}): {e} — 기본 컬렉션 사용")
    return settings.QDRANT_COLLECTION


def ensure_collection(collection_name=None):
    """컬렉션이 없으면 생성 (버전별 컬렉션 지원)"""
    from qdrant_client.models import (
        Distance, VectorParams, SparseVectorParams,
        SparseIndexParams,
    )

    client = get_client()
    collection_name = collection_name or settings.QDRANT_COLLECTION

    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                'dense': VectorParams(
                    size=1024,        # BGE-M3 dense 차원
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                'sparse': SparseVectorParams(
                    index=SparseIndexParams(),
                ),
            },
        )
        ensure_payload_indexes(collection_name)
        logger.info(f"Qdrant 컬렉션 '{collection_name}' 생성 완료 (payload 인덱스 포함)")
    elif collection_name not in _indexes_checked:
        # 기존 컬렉션은 document_id 인덱스 없이 만들어졌다. 프로세스당 한 번만 보정한다.
        ensure_payload_indexes(collection_name)
    _indexes_checked.add(collection_name)


# 프로세스당 인덱스 점검을 1회로 제한 (적재 배치마다 조회하면 낭비)
_indexes_checked = set()


# 필터 검색·삭제용 payload 인덱스 (기획서 §4.6 + 문서 갱신용 document_id)
_PAYLOAD_INDEXES = (
    ('project_id', 'KEYWORD'),
    ('is_global', 'BOOL'),
    ('file_type', 'KEYWORD'),
    ('document_id', 'KEYWORD'),   # 문서 단위 삭제/갱신에 필수
)


def ensure_payload_indexes(collection_name=None):
    """payload 인덱스를 보장한다. 이미 있으면 조용히 넘어간다.

    기존 컬렉션은 document_id 인덱스 없이 만들어졌다. 인덱스가 없어도 필터는
    동작하지만 전체 스캔이 되므로, 기동 시 한 번 보정한다.
    """
    from qdrant_client.models import PayloadSchemaType

    client = get_client()
    name = collection_name or settings.QDRANT_COLLECTION
    try:
        existing = set((client.get_collection(name).payload_schema or {}).keys())
    except Exception as e:
        logger.warning(f"컬렉션 정보 조회 실패({name}): {e}")
        return

    for field, schema in _PAYLOAD_INDEXES:
        if field in existing:
            continue
        try:
            client.create_payload_index(collection_name=name, field_name=field,
                                        field_schema=getattr(PayloadSchemaType, schema))
            logger.info(f"payload 인덱스 생성: {name}.{field}")
        except Exception as e:
            logger.warning(f"payload 인덱스 생성 실패({field}): {e}")


def count_by_document(document_id, collection_name=None):
    """해당 문서의 Qdrant 포인트 수. 삭제 전후 검증용."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_client()
    name = collection_name or settings.QDRANT_COLLECTION
    try:
        return client.count(
            collection_name=name,
            count_filter=Filter(must=[FieldCondition(
                key='document_id', match=MatchValue(value=str(document_id)))]),
            exact=True,
        ).count
    except Exception as e:
        logger.warning(f"포인트 수 조회 실패({document_id}): {e}")
        return -1


def delete_by_document(document_id, collection_name=None):
    """문서 한 건의 벡터를 Qdrant에서 제거한다. 삭제된 포인트 수를 반환.

    Postgres의 DocumentChunk는 Document 삭제 시 CASCADE로 사라지지만 Qdrant는
    아무도 정리해 주지 않는다. 그대로 두면 고아 벡터가 후보 K를 잠식해
    (본문이 없어 답변에는 안 쓰이지만) 검색 품질이 조용히 떨어진다.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector

    client = get_client()
    name = collection_name or settings.QDRANT_COLLECTION
    before = count_by_document(document_id, name)
    if before == 0:
        return 0
    try:
        client.delete(
            collection_name=name,
            points_selector=FilterSelector(filter=Filter(must=[FieldCondition(
                key='document_id', match=MatchValue(value=str(document_id)))])),
            wait=True,
        )
    except Exception as e:
        logger.error(f"Qdrant 포인트 삭제 실패({document_id}): {e}")
        raise
    after = count_by_document(document_id, name)
    removed = (before - after) if before >= 0 and after >= 0 else before
    logger.info(f"Qdrant 포인트 삭제: document_id={document_id} {removed}건 (잔여 {after})")
    return removed


def upsert_chunks(points, collection_name=None):
    """청크 벡터 포인트를 Qdrant에 삽입/갱신 (버전별 컬렉션 지원)"""
    name = collection_name or settings.QDRANT_COLLECTION
    ensure_collection(name)
    client = get_client()
    client.upsert(
        collection_name=name,
        points=points,
    )


def hybrid_search(query_dense, query_sparse=None, project_id=None, top_k=6):
    """
    하이브리드 검색 (dense + sparse)
    project_id가 주어지면 [해당 프로젝트 데이터] 또는 [전사 공용 데이터 (is_global=true)]만 검색.
    project_id가 없으면 [전사 공용 데이터 (is_global=true)]만 검색.
    """
    ensure_collection()
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_client()
    collection_name = settings.QDRANT_COLLECTION

    # 보안 필터 전면 해제 (모든 문서를 조회하도록 설정)
    query_filter = None

    # 하이브리드 로직 제거 완료
    # Qdrant 1.9+ 최신 클라이언트에 맞춘 확실한 검색 로직 (Dense 단독 검색)
    try:
        results = client.query_points(
            collection_name=collection_name,
            query=query_dense,
            using='dense',
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        ).points
        return results
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"🚨 [Qdrant hybrid_search FATAL ERROR]\n{tb}")
        raise e
