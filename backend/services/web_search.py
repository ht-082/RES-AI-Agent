"""Tavily 웹 검색 — 사내 문서가 담지 못하는 정보(법령 개정·시세·정책)를 보완한다.

설계 원칙
---------
1. **기본은 꺼짐.** `TAVILY_ENABLED`가 False면 키가 있어도 호출하지 않는다.
   웹 검색을 켜면 질문 내용이 외부 서버로 전송되기 때문이다.

2. **도메인 화이트리스트를 두지 않는다.** 출처 신뢰도 판단은 사용자 몫이다.
   대신 ① 관련성 점수로 거르고 ② 도메인·날짜를 반드시 노출해 판단 재료를 준다.

3. **Tavily의 자동 요약(include_answer)을 쓰지 않는다.** 출처가 흐려진 요약이
   한 겹 끼면 근거 추적이 불가능해진다. 원본 결과만 받아 우리 LLM이 인용한다.

4. **Django 없이도 동작한다.** 임계값 실측을 파이프라인과 분리해서 하기 위함이다.
   settings가 없으면 환경변수로 폴백한다.
"""
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = 'https://api.tavily.com/search'

_DEFAULTS = {
    'TAVILY_API_KEY': '',
    'TAVILY_ENABLED': False,
    'TAVILY_SEARCH_DEPTH': 'basic',
    'TAVILY_MAX_RESULTS': 5,
    'TAVILY_TIMEOUT': 8.0,
    'TAVILY_MIN_SCORE': 0.5,
    'TAVILY_REL_MARGIN': 0.3,
    'TAVILY_CONTEXT_CHAR_BUDGET': 6000,
}


class WebSearchError(Exception):
    """웹 검색 실패. 호출측은 이걸 잡아 '웹 근거 없음'으로 진행해야 한다."""


_dotenv_loaded = False


def _load_dotenv_once():
    """Django 없이 실행될 때 backend/.env 를 직접 읽는다.

    settings.py 가 하던 일을 대신한다. 이게 없으면 단독 실행 시 키를 못 찾아
    "TAVILY_API_KEY가 설정되지 않았습니다"로 끝난다.
    """
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(base, '.env'))
    except Exception as e:
        logger.debug(f'.env 로드 생략: {e}')


def _conf(name):
    """설정값 조회 — Django settings 우선, 없으면 .env/환경변수, 없으면 기본값."""
    try:
        from django.conf import settings
        if settings.configured:
            return getattr(settings, name, _DEFAULTS[name])
    except Exception:
        pass
    _load_dotenv_once()
    raw = os.getenv(name)
    if raw is None:
        return _DEFAULTS[name]
    default = _DEFAULTS[name]
    if isinstance(default, bool):
        return raw.lower() in ('true', '1', 'yes')
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


def is_available():
    """웹 검색을 쓸 수 있는 상태인가. (가능 여부, 사유)"""
    if not _conf('TAVILY_ENABLED'):
        return False, 'disabled(TAVILY_ENABLED=False)'
    if not _conf('TAVILY_API_KEY'):
        return False, 'no-api-key'
    return True, 'ok'


def _domain(url):
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith('www.') else host
    except Exception:
        return ''


def _post(payload, timeout, api_key):
    """Tavily 호출. 사내망 SSL 가로채기 환경을 고려해 검증 실패 시 1회 재시도한다."""
    import httpx

    headers = {'Content-Type': 'application/json',
               'Authorization': f'Bearer {api_key}'}
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.post(TAVILY_ENDPOINT, json=payload, headers=headers)
    except httpx.ConnectError as e:
        if 'certificate' not in str(e).lower() and 'ssl' not in str(e).lower():
            raise
        logger.warning('Tavily SSL 검증 실패 — 사내망 인증서로 보고 verify=False 재시도')
        with httpx.Client(timeout=timeout, verify=False) as client:
            return client.post(TAVILY_ENDPOINT, json=payload, headers=headers)


def search(query, *, max_results=None, depth=None, timeout=None, force=False):
    """웹 검색 실행. 정규화된 결과 리스트를 반환한다.

    force=True면 TAVILY_ENABLED를 무시한다(임계값 실측 스크립트 전용).
    운영 경로에서는 절대 force를 쓰지 말 것 — 킬스위치가 무력화된다.
    """
    api_key = _conf('TAVILY_API_KEY')
    if not api_key:
        raise WebSearchError('TAVILY_API_KEY가 설정되지 않았습니다.')
    if not force and not _conf('TAVILY_ENABLED'):
        raise WebSearchError('TAVILY_ENABLED=False — 웹 검색이 꺼져 있습니다.')

    query = (query or '').strip()
    if not query:
        return []

    payload = {
        'query': query,
        'search_depth': depth or _conf('TAVILY_SEARCH_DEPTH'),
        'max_results': max_results or _conf('TAVILY_MAX_RESULTS'),
        'include_answer': False,        # 원칙 3
        'include_raw_content': False,   # 본문 전문은 컨텍스트를 폭발시킨다
    }

    try:
        resp = _post(payload, timeout or _conf('TAVILY_TIMEOUT'), api_key)
    except Exception as e:
        raise WebSearchError(f'Tavily 호출 실패: {type(e).__name__}: {e}') from e

    if resp.status_code == 401:
        raise WebSearchError('Tavily 인증 실패(401) — API 키를 확인하세요.')
    if resp.status_code == 429:
        raise WebSearchError('Tavily 사용량 초과(429) — 크레딧을 확인하세요.')
    if resp.status_code >= 400:
        raise WebSearchError(f'Tavily 오류 {resp.status_code}: {resp.text[:200]}')

    try:
        data = resp.json()
    except Exception as e:
        raise WebSearchError(f'Tavily 응답 파싱 실패: {e}') from e

    out = []
    for r in (data.get('results') or []):
        url = r.get('url') or ''
        out.append({
            'title': (r.get('title') or '').strip(),
            'url': url,
            'domain': _domain(url),
            'snippet': (r.get('content') or '').strip(),
            'score': float(r.get('score') or 0.0),
            'published': r.get('published_date') or '',
        })
    out.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"[웹검색] '{query[:40]}' → {len(out)}건 "
                f"(1위 {out[0]['score']:.3f})" if out else f"[웹검색] '{query[:40]}' → 0건")
    return out


def filter_results(results, *, min_score=None, rel_margin=None):
    """[품질 게이트] 관련성 점수로 거른다. (남은 결과, 사유)

    도메인 화이트리스트를 두지 않으므로 이 컷이 유일한 품질 장치다.
    사내 관련성 게이트와 같은 2단 구성:
      ① 1위가 바닥값 미만이면 전부 버린다 → '웹에도 자료 없음'
      ② 1위에서 일정 폭 이상 떨어진 꼬리를 버린다 → 노이즈가 컨텍스트를 먹지 않게
    """
    if not results:
        return [], 'empty'

    floor = _conf('TAVILY_MIN_SCORE') if min_score is None else min_score
    margin = _conf('TAVILY_REL_MARGIN') if rel_margin is None else rel_margin

    top = max(r['score'] for r in results)
    if top < floor:
        return [], f'top1={top:.3f}<{floor} (웹에도 관련 자료 없음)'

    cut = top - margin
    kept = [r for r in results if r['score'] >= cut]
    return kept, f'top1={top:.3f} cut>={cut:.3f} {len(kept)}/{len(results)}'


def build_web_context(results, *, budget=None):
    """LLM 프롬프트에 넣을 웹 근거 블록을 만든다.

    도메인과 날짜를 **반드시** 노출한다. 화이트리스트가 없으므로 신뢰도 판단은
    사용자 몫인데, 판단하려면 판단할 재료가 보여야 하기 때문이다.
    """
    if not results:
        return '', []

    budget = _conf('TAVILY_CONTEXT_CHAR_BUDGET') if budget is None else budget
    parts, used, cited = [], 0, []

    for idx, r in enumerate(results, start=1):
        head = f"[웹 {idx}] {r['domain']}"
        if r['published']:
            head += f" · {r['published']}"
        if r['title']:
            head += f" · \"{r['title']}\""
        body = r['snippet']
        block = f"{head}\n{body}"

        if used + len(block) > budget and parts:
            break
        used += len(block)
        parts.append(block)
        cited.append({**r, 'rank': idx})

    return '\n\n'.join(parts), cited
