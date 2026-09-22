"""
법제처 Open API(DRF) 어댑터 — 법령 검색·동향 조회.

스냅샷(snapshots.py)은 파일에 박제된 40건이라 새 법을 담을 수 없고, 이름이
바뀐 법을 그대로 들고 있다(실측: 스냅샷의 '신에너지 및 재생에너지 개발ㆍ이용ㆍ
보급 촉진법'은 2026-09-18 시행으로 '재생에너지 개발ㆍ이용ㆍ보급 촉진법'으로
개칭됐다). 그래서 담당자가 지켜볼 법은 여기서 직접 찾아 고른다.

OC 키가 없으면 모든 함수가 None 을 돌려주고, 호출부는 스냅샷으로 되돌아간다
(키를 넣기 전에도 화면이 비지 않게).

실측(2026-09-22):
  · OC 는 법제처에 신청한 ID 여야 하고 **호출 서버의 IP·도메인까지 등록**해야
    한다. 아무 문자열이나 넣으면 '사용자 정보 검증에 실패' 로 막힌다.
  · query 는 법령명 부분일치다 — '전기사업법' 으로 찾으면 전기공사업법·
    전기통신사업법도 딸려 온다. 그래서 고르는 화면에서 사람이 집어야 한다.
  · 법령명으로 찾으면 그 법의 시행령·시행규칙이 함께 나온다('농지법' → 3건).
    관심 법령을 '묶음' 단위로 두는 근거다.
"""
import logging
import re
from datetime import date

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TIMEOUT = 10.0
SEARCH_TTL = 600      # 검색 결과 10분 — 고르는 동안만 쓰인다
FAMILY_TTL = 3600     # 동향 1시간 — 대시보드가 열릴 때마다 외부를 두드리지 않게
SUFFIXES = (' 시행규칙', ' 시행령')


def oc():
    return (getattr(settings, 'LAW_API_OC', '') or '').strip()


def base():
    return (getattr(settings, 'LAW_API_BASE', '') or 'http://www.law.go.kr/DRF').rstrip('/')


def enabled():
    return bool(oc())


def family_of(name):
    """시행령·시행규칙을 상위 법 이름으로 묶는다."""
    name = (name or '').strip()
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name


def _tag(block, name):
    m = re.search('<' + name + r'>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</' + name + '>', block)
    return m.group(1).strip() if m else ''


def _fmt(raw):
    return f'{raw[:4]}.{raw[4:6]}.{raw[6:8]}' if raw and len(raw) == 8 else (raw or '')


def _categorize(enforcement_raw, revision):
    """스냅샷과 같은 기준 — 아직 시행 전이면 입법예고, 그 외는 제·개정 구분."""
    if enforcement_raw and enforcement_raw > date.today().strftime('%Y%m%d'):
        return '입법예고'
    if '개정' in (revision or ''):
        return '개정'
    if '제정' in (revision or ''):
        return '시행'
    return '기타'


def _normalize(block):
    name = _tag(block, '법령명한글')
    mst = _tag(block, '법령일련번호')
    revision = _tag(block, '제개정구분명')
    eff = _tag(block, '시행일자')
    return {
        'id': f'X{mst}' if mst else f'X{name}',
        'family': family_of(name),
        'law_name': name,
        'short_name': _tag(block, '법령약칭명'),
        'law_type': _tag(block, '법령구분명'),
        'category': _categorize(eff, revision),
        'title': f'{name} · {revision}' if revision else name,
        'date': _fmt(eff),
        'ministry': _tag(block, '소관부처명'),
        # 상세링크에는 우리 OC 가 들어 있어 화면에 내보내지 않는다 — 법령명
        # 주소로 대신 건다(법제처가 최신 본을 찾아 준다).
        'source_url': 'https://www.law.go.kr/법령/' + name,
        'summary': ' · '.join(x for x in [revision, f'공포 {_fmt(_tag(block, "공포일자"))}'] if x.strip()),
        'categories': [],
        'ai': None,
        'law_id': _tag(block, '법령ID'),
        'mst': mst,
    }


def _search_raw(query, display=50):
    """법제처 lawSearch.do 호출. 실패하면 None (호출부가 스냅샷으로 되돌아간다)."""
    if not enabled() or not (query or '').strip():
        return None
    key = f'bizdev:lawapi:search:{query}:{display}'
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        res = httpx.get(f'{base()}/lawSearch.do', timeout=TIMEOUT,
                        headers={'User-Agent': 'res-ai-agent/1.0'},
                        params={'OC': oc(), 'target': 'law', 'type': 'XML',
                                'query': query, 'display': str(display)})
        res.raise_for_status()
        body = res.text
    except Exception as exc:
        logger.warning('법제처 검색 실패 (%s): %s', query, exc)
        return None
    if '<resultMsg>success</resultMsg>' not in body:
        # 키·IP 미등록은 200 으로 오고 본문에만 사유가 적힌다
        logger.warning('법제처 검색 거절 (%s): %s', query, _tag(body, 'msg') or _tag(body, 'result'))
        return None
    rows = [_normalize(b) for b in re.findall(r'<law id="\d+">([\s\S]*?)</law>', body)]
    cache.set(key, rows, SEARCH_TTL)
    return rows


def search_families(query, limit=20):
    """검색어로 찾은 법을 묶음 단위로 돌려준다 (고르기 화면용).

    '농지법' 처럼 시행령·시행규칙이 함께 잡히므로 상위 법 이름으로 접는다.
    """
    rows = _search_raw(query)
    if rows is None:
        return None
    groups = {}
    for row in rows:
        g = groups.setdefault(row['family'], {
            'family': row['family'], 'law_name': row['family'],
            'ministry': row['ministry'], 'count': 0, 'latest': '',
        })
        g['count'] += 1
        if row['date'] > g['latest']:
            g['latest'] = row['date']
        if row['law_type'] in ('법률', '대통령령') and row['family'] == row['law_name']:
            g['law_name'] = row['law_name']
            g['ministry'] = row['ministry']
    ordered = sorted(groups.values(), key=lambda g: (-g['count'], g['family']))
    return ordered[:limit]


def rows_for_family(family):
    """한 묶음의 동향 — 그 법과 시행령·시행규칙. 실패·미설정이면 None."""
    if not enabled():
        return None
    key = f'bizdev:lawapi:family:{family}'
    hit = cache.get(key)
    if hit is not None:
        return hit
    rows = _search_raw(family)
    if rows is None:
        return None
    # 부분일치라 '전기사업법' 에 전기공사업법까지 딸려 온다 — 묶음 이름이
    # 정확히 같은 것만 남긴다.
    mine = [r for r in rows if r['family'] == family]
    cache.set(key, mine, FAMILY_TTL)
    return mine


def forget(family=None):
    """관심 법령을 더하거나 뺐을 때 캐시를 비운다."""
    if family:
        cache.delete(f'bizdev:lawapi:family:{family}')
