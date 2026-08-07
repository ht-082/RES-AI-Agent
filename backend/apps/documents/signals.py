"""문서 삭제 시 Qdrant 정리.

Postgres는 Document → DocumentChunk를 CASCADE로 지우지만 Qdrant 벡터는 남는다.
그 고아 벡터는 본문이 없어 답변에는 쓰이지 않지만(run_rag가 걸러낸다),
검색 후보 K를 잠식해 실질 후보 수를 줄이고 리랭킹 비용을 낭비한다.
문서를 지우는 모든 경로(API·관리명령·admin·shell)에서 자동으로 정리되도록
모델 시그널에 건다.
"""
import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Document

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Document, dispatch_uid='documents.cleanup_qdrant')
def cleanup_qdrant_points(sender, instance, **kwargs):
    from services.qdrant_client import delete_by_document

    # 어느 컬렉션에 들어갔는지는 문서가 속한 코퍼스 버전이 정한다.
    collection = None
    try:
        if instance.corpus_id and instance.corpus:
            collection = instance.corpus.collection_name
    except Exception:
        pass   # 코퍼스가 함께 지워지는 중일 수 있다 → 기본 컬렉션으로 처리

    try:
        removed = delete_by_document(instance.id, collection_name=collection)
        if removed:
            logger.info(f"문서 삭제에 따른 Qdrant 정리: {instance.title} — {removed}건")
    except Exception as e:
        # 벡터 정리 실패로 문서 삭제 자체를 되돌리지는 않는다.
        # 대신 반드시 로그를 남겨 수동 정리가 가능하게 한다.
        logger.error(f"🚨 Qdrant 정리 실패 (고아 벡터가 남았습니다) "
                     f"document_id={instance.id} title={instance.title}: {e}")
