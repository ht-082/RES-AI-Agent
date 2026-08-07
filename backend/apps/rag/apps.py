"""RAG 앱 설정 — 서버 기동 시 모델 예열

임베딩(BGE-M3)과 리랭커는 첫 호출 때 로드되어 2~3분이 걸린다. 그 비용을 사용자의
첫 질문이 치르지 않도록, 서버가 뜰 때 백그라운드 스레드에서 미리 로드한다.
"""
import logging
import os
import threading

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)

_warmup_started = False


def _warmup():
    try:
        from services.embedding import embed_text
        from services.retriever import get_reranker

        t = __import__('time').time
        t0 = t()
        embed_text('예열')
        logger.info(f"[예열] 임베딩 모델 준비 완료 ({t()-t0:.0f}초)")

        if getattr(settings, 'RERANK_ENABLED', True):
            t1 = t()
            get_reranker().score([('예열', '예열용 문서')])
            logger.info(f"[예열] 리랭커 준비 완료 ({t()-t1:.0f}초)")
        logger.info(f"[예열] 전체 완료 ({t()-t0:.0f}초) — 첫 질의부터 정상 속도")
    except Exception as e:
        logger.warning(f"[예열] 실패(서비스는 정상 동작, 첫 질의가 느려질 수 있음): {e}")


class RagConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rag'

    def ready(self):
        global _warmup_started
        if _warmup_started or not getattr(settings, 'RAG_WARMUP_ON_START', True):
            return
        # 관리 명령에서는 불필요하게 모델을 메모리에 올리지 않는다.
        # 차단 목록 방식은 새 명령(check 등)이 늘 때마다 새는 것이 확인돼,
        # '서버를 띄우는 경우에만 허용'하는 화이트리스트로 바꿨다.
        import sys
        argv = ' '.join(sys.argv)
        is_server = ('runserver' in argv
                     or any(s in argv for s in ('gunicorn', 'uvicorn', 'daphne')))
        if not is_server:
            return
        # runserver 자동 리로더는 부모(감시)와 자식(실제 서버) 양쪽에서 ready()를 부른다.
        # 자식에서만 예열해야 모델이 두 번 로드되지 않는다(메모리 2배 낭비).
        # 자식 프로세스에는 RUN_MAIN=true가 설정된다. gunicorn 등에서는 이 변수가
        # 아예 없으므로, runserver일 때만 이 가드를 적용한다.
        if 'runserver' in argv and os.environ.get('RUN_MAIN') != 'true':
            return
        _warmup_started = True
        threading.Thread(target=_warmup, name='rag-warmup', daemon=True).start()
        logger.info('[예열] 백그라운드 모델 로드 시작')
