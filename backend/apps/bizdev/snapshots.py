"""
계통(KEPCO)·법령(법제처) 스냅샷 어댑터 — 원본 server/services/{gridApi,lawApi}.js 이관.

1차는 apps/bizdev/data/*.json 스냅샷만 서빙한다. 2차에서 KEPCO 빅데이터·법제처
실시간 API 로 전환할 때는 이 모듈의 함수 본문만 교체하면 된다(응답 스키마 고정 —
프론트 무변경 원칙).
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from .constants import SIDO_FULL, resolve_sido

DATA_DIR = Path(__file__).resolve().parent / 'data'


@lru_cache(maxsize=1)
def _grid_snapshot():
    with open(DATA_DIR / 'grid_snapshot.json', encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _law_snapshot():
    with open(DATA_DIR / 'law_snapshot.json', encoding='utf-8') as f:
        return json.load(f)


# ── 계통 (gridApi.js) ──────────────────────────────────────────────

def grid_capacity_by_sido():
    """시도별 접속가능 여유용량 — gridApi.capacityBySido 이식."""
    snap = _grid_snapshot()
    updated_at = (snap.get('meta') or {}).get('updated_at')
    rows = [
        {
            'sido': r.get('region'),
            'available_mw': round(r.get('hosting') or 0),
            'sat_pct': r.get('sat_pct'),
            'n_subst': r.get('n_subst'),
            'n_dl': r.get('n_dl'),
            'updated_at': updated_at,
        }
        for r in snap.get('regions') or []
    ]
    return sorted(rows, key=lambda r: r['available_mw'], reverse=True)


def grid_nearby(sido=None):
    """인근 변전소 상위 8 (여유 오름차순) — gridApi.nearbySubstations 스냅샷 경로 이식."""
    sd = resolve_sido(sido)
    subs = _grid_snapshot().get('substations') or []
    pool = [s for s in subs if sd and s.get('region') == sd] or subs
    pool = sorted(pool, key=lambda s: s.get('hosting') or 0)[:8]
    out = []
    for s in pool:
        n_dl = s.get('n_dl') or 0
        hosting = s.get('hosting') or 0
        out.append({
            'name': s.get('substation'),
            'sido': sd or s.get('region') or '',
            'capacity_used_pct': round((s.get('n_sat') or 0) / n_dl * 100) if n_dl else 0,
            'available_mw': round(hosting),
            'contract_status': '포화' if hosting <= 0 else ('주의' if hosting <= 3 else '여유'),
        })
    return out


# ── 법령 (lawApi.js) ───────────────────────────────────────────────

def _categorize(law):
    ef = law.get('enforcement_raw') or law.get('enforcement_date_raw') or ''
    if ef and ef > date.today().strftime('%Y%m%d'):
        return '입법예고'
    rv = law.get('revision_type') or ''
    if '개정' in rv:
        return '개정'
    if '제정' in rv:
        return '시행'
    return '기타'


def _normalize(law, law_id):
    short = law.get('short_name') or law.get('name')
    rv = law.get('revision_type') or ''
    return {
        'id': law_id,
        'law_name': law.get('name'),
        'short_name': short,
        'law_type': law.get('law_type'),
        'category': _categorize(law),
        'title': f'{short} · {rv}' if rv else short,
        'date': law.get('enforcement_date') or law.get('promulgation_date') or '',
        'ministry': law.get('ministry') or '',
        'summary': ' · '.join(x for x in [
            law.get('ministry'), '/'.join((law.get('categories') or [])[:3])] if x),
        'source_url': law.get('url') or '',
        'categories': law.get('categories') or [],
        'ai': law.get('ai'),
    }


def _all_laws():
    return [
        _normalize(l, f'L{i}') for i, l in enumerate(_law_snapshot().get('laws') or [])
    ]


def list_laws(limit=None):
    """전국 법령(조례 제외) — 시행/공포일 내림차순."""
    rows = [l for l in _all_laws() if l['law_type'] != '조례']
    rows.sort(key=lambda l: l['date'] or '', reverse=True)
    return rows[:limit] if limit else rows


def get_law(law_id):
    return next((l for l in _all_laws() if l['id'] == law_id), None)


def list_ordinances(sido=None):
    """지자체 조례 — 스냅샷 필터.

    시·군명(홍성군)을 소속 시·도(충남/충청남도)로 정규화해 같은 도의 조례까지
    매칭한다. 매칭이 없으면 빈 배열(무관한 타 지역 조례를 보여주지 않는다).
    """
    rows = [l for l in _all_laws() if l['law_type'] == '조례']
    if not sido:
        return rows
    key = str(sido).strip()
    tokens = {key}
    prov = resolve_sido(key)
    if prov:
        tokens.add(prov)
        tokens.update(full for full, short in SIDO_FULL.items() if short == prov)
    return [
        l for l in rows
        if any(t in (l['ministry'] + l['law_name']) for t in tokens)
    ]
