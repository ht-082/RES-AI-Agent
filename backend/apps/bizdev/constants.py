"""
사업개발(bizdev) 공용 상수 — Re-project-mng ver2.0 이관.

STAGE_DEFS: 인허가 12단계의 유일한 정의처.
원본(Re-project-mng)에서는 js/api.js 와 supabase/05_migration_v2.sql 에 이중
하드코딩되어 있던 것을 여기로 단일화했다. 사이트 생성(뷰)·시드(command)가 모두
이 리스트를 사용하므로 단계 구성을 바꿀 때는 이 파일만 고치면 된다.
"""

STAGE_DEFS = [
    {'stage_no': 1,  'name': '발전사업허가',              'agency': '전기위원회',     'tier': 'major', 'doc_label': '허가증'},
    {'stage_no': 2,  'name': '송전용전기설비 이용계약',   'agency': '한전',           'tier': 'minor', 'doc_label': '이용계약서'},
    {'stage_no': 3,  'name': '개발행위허가',              'agency': '지자체',         'tier': 'major', 'doc_label': '허가서'},
    {'stage_no': 4,  'name': '(소규모)환경영향평가',      'agency': '유역환경청',     'tier': 'minor', 'doc_label': '협의문'},
    {'stage_no': 5,  'name': '재해영향평가',              'agency': '광역지자체',     'tier': 'minor', 'doc_label': '협의문'},
    {'stage_no': 6,  'name': '농지 타용도 일시사용허가',  'agency': '지자체',         'tier': 'minor', 'doc_label': '허가서'},
    {'stage_no': 7,  'name': '농지생산기반시설 사용허가', 'agency': '한국농어촌공사', 'tier': 'minor', 'doc_label': '승인서'},
    {'stage_no': 8,  'name': '경관심의',                  'agency': '지자체',         'tier': 'minor', 'doc_label': '심의결과'},
    {'stage_no': 9,  'name': '교통계획',                  'agency': '지자체',         'tier': 'minor', 'doc_label': '심의결과'},
    {'stage_no': 10, 'name': '문화재지표조사',            'agency': '문화재청',       'tier': 'minor', 'doc_label': '조사보고서'},
    {'stage_no': 11, 'name': '도로점용허가',              'agency': '지자체',         'tier': 'major', 'doc_label': '허가서'},
    {'stage_no': 12, 'name': '공사계획인가',              'agency': '전기안전공사',   'tier': 'major', 'doc_label': '인가서'},
]

STATUS_CHOICES = [
    ('done', '완료'), ('active', '진행중'), ('wait', '대기'),
    ('risk', '리스크'), ('idle', '미착수'),
]
ENERGY_CHOICES = [('solar', '태양광'), ('wind', '풍력')]
LIFECYCLE_CHOICES = [('dev', '개발중'), ('ops', '운영중')]
TIER_CHOICES = [('major', '상위'), ('minor', '하위')]
BUDGET_CATEGORY_CHOICES = [
    ('land', '부지'), ('permit', '인허가'), ('design', '설계'),
    ('legal', '법무'), ('etc', '기타'),
]
ISSUE_STATUS_CHOICES = [('open', '진행중'), ('prog', '대응중'), ('closed', '완료')]
ISSUE_TYPE_CHOICES = [('complaint', '민원성'), ('grid', '계통'), ('etc', '기타')]
RISK_LEVEL_CHOICES = [('hi', '높음'), ('md', '중간')]

# ── 시·도 정규화 (원본 index.page.js:163-181 + gridApi.js:14 통합) ─────────
# KEPCO 스냅샷의 region 명(2자)에 맞춘다. 시·군명이 sido 컬럼에 저장되는
# 원본 데이터 특성 때문에 조회 때마다 이 정규화가 필요하다.
SIDO_FULL = {
    '충청남도': '충남', '충청북도': '충북', '전라남도': '전남', '전라북도': '전북',
    '전북특별자치도': '전북', '경상남도': '경남', '경상북도': '경북',
    '강원도': '강원', '강원특별자치도': '강원', '경기도': '경기',
    '제주특별자치도': '제주', '제주도': '제주', '세종특별자치시': '세종',
}
SIDO_2 = [
    '충남', '충북', '전남', '전북', '경남', '경북', '강원', '경기', '제주',
    '세종', '서울', '부산', '대구', '인천', '광주', '대전', '울산',
]
SIGUN_SIDO = {
    '서산시': '충남', '당진시': '충남', '홍성군': '충남', '청양군': '충남',
    '서천군': '충남', '태안군': '충남', '예산군': '충남', '보령시': '충남',
    '영암군': '전남', '신안군': '전남', '해남군': '전남', '영광군': '전남',
    '완도군': '전남', '보성군': '전남', '함평군': '전남', '나주시': '전남',
    '고흥군': '전남', '여수시': '전남',
    '고령군': '경북', '영덕군': '경북', '김천시': '경북', '상주시': '경북', '포항시': '경북',
    '밀양시': '경남', '창녕군': '경남', '진주시': '경남',
    '태백시': '강원', '정선군': '강원', '영월군': '강원',
    '군산시': '전북', '김제시': '전북',
    '제주시': '제주', '서귀포시': '제주',
}

import re as _re


def resolve_sido(value):
    """주소 첫 토큰/시·군명/시·도명을 KEPCO 2자 시·도명으로 정규화. 실패 시 None."""
    if not value:
        return None
    tok = _re.split(r'[\s·]+', str(value).strip())[0]
    if not tok:
        return None
    if tok in SIDO_FULL:
        return SIDO_FULL[tok]
    two = tok[:2]
    if two in SIDO_2 and not _re.search(r'[시군구]$', tok):
        return two
    return SIGUN_SIDO.get(tok)
