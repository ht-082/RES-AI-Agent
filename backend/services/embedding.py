"""
임베딩 서비스 레이어 — 로컬 (FlagEmbedding) 및 외부 API (OpenRouter 등) 지원
BGE-M3 Dense / Sparse 임베딩 벡터 생성
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# 로컬 임베딩 모델 인스턴스 (Lazy Loading)
_model = None


def get_local_model():
    """로컬 BGE-M3 모델 로드"""
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel
        logger.info(f"로컬 BGE-M3 모델 로드 중 (Device: {settings.EMBEDDING_DEVICE})...")
        _model = BGEM3FlagModel(
            settings.EMBEDDING_MODEL,
            use_fp16=(settings.EMBEDDING_DEVICE == 'cuda')
        )
        logger.info("로컬 BGE-M3 모델 로드 완료")
    return _model


def embed_text(text: str):
    """
    단일 텍스트 임베딩 수행
    반환값: {"dense": list, "sparse": dict or None}
    """
    if settings.EMBEDDING_DEVICE == 'api':
        return _embed_via_api(text)
    else:
        return _embed_locally(text)


def _embed_locally(text: str):
    """로컬 CPU/GPU 연산 기반 BGE-M3 임베딩"""
    try:
        model = get_local_model()
        # BGE-M3 output format
        output = model.encode(
            [text],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )
        dense_vector = output['dense_vecs'][0].tolist()
        # sparse dict format: {token_id: weight}
        sparse_vector = {int(k): float(v) for k, v in output['lexical_weights'][0].items()}

        return {
            'dense': dense_vector,
            'sparse': sparse_vector
        }
    except Exception as e:
        logger.error(f"로컬 임베딩 연산 실패: {e}")
        raise


def _embed_via_api(text: str):
    """외부 API (OpenRouter 등) 기반 임베딩"""
    if not settings.EMBEDDING_API_KEY:
        raise ValueError("EMBEDDING_API_KEY 환경변수가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": text
    }

    try:
        url = f"{settings.EMBEDDING_API_BASE}/embeddings"
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        res_data = response.json()

        # OpenAI 호환 response parsing
        dense_vector = res_data['data'][0]['embedding']

        # API는 통상 dense 벡터만 반환하므로 sparse는 빈 딕셔너리 처리
        return {
            'dense': dense_vector,
            'sparse': {}
        }
    except Exception as e:
        logger.error(f"외부 임베딩 API 호출 실패: {e}")
        # API 오류 시 로컬 CPU 백업으로 대체 시도
        logger.warning("로컬 CPU 임베딩 백업으로 대체를 시도합니다...")
        try:
            return _embed_locally(text)
        except Exception as local_err:
            logger.error(f"로컬 백업 임베딩 또한 실패: {local_err}")
            raise e
