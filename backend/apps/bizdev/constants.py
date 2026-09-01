"""
사업개발(bizdev) 공용 상수 — Re-project-mng ver2.0 이관.

STAGE_DEFS: 인허가 항목(법정절차 7 + 개별법 협의 3)의 유일한 정의처.
FACT_DEFS: 사업개요 양식(docs 사업개요_양식_v3.md) 항목의 유일한 정의처.
원본(Re-project-mng)에서는 js/api.js 와 supabase/05_migration_v2.sql 에 이중
하드코딩되어 있던 것을 여기로 단일화했다. 사이트 생성(뷰)·시드(command)가 모두
이 리스트를 사용하므로 단계 구성을 바꿀 때는 이 파일만 고치면 된다.
"""

STAGE_DEFS = [
    # 3-1. 전기사업법·국토계획법 절차
    {'stage_no': 1, 'name': '발전사업허가', 'category': 'statutory', 'agency': '전기위원회',
     'content_hint': '허가번호 / 용량 / 허가일자 / 허가조건', 'doc_label': '허가증'},
    {'stage_no': 2, 'name': '송전용전기설비이용계약', 'category': 'statutory', 'agency': '한국전력공사',
     'content_hint': '계약전력 / 이용개시일', 'doc_label': '이용계약서'},
    {'stage_no': 3, 'name': '개발행위허가', 'category': 'statutory', 'agency': '지자체',
     'content_hint': '면적 / 필지수', 'doc_label': '허가서'},
    {'stage_no': 4, 'name': '공사계획인가', 'category': 'statutory', 'agency': '전기안전공사',
     'content_hint': '', 'doc_label': '인가서'},
    {'stage_no': 5, 'name': '사용전검사', 'category': 'statutory', 'agency': '전기안전공사',
     'content_hint': '', 'doc_label': '검사증'},
    {'stage_no': 6, 'name': '사업개시신고', 'category': 'statutory', 'agency': '지자체',
     'content_hint': '', 'doc_label': '신고증'},
    {'stage_no': 7, 'name': '개발행위준공', 'category': 'statutory', 'agency': '지자체',
     'content_hint': '', 'doc_label': '준공증'},
    # 3-2. 개별법 협의
    {'stage_no': 8, 'name': '환경영향평가', 'category': 'individual', 'agency': '유역환경청',
     'content_hint': '소규모 / 일반', 'doc_label': '협의문'},
    {'stage_no': 9, 'name': '재해영향평가', 'category': 'individual', 'agency': '광역지자체',
     'content_hint': '', 'doc_label': '협의문'},
    {'stage_no': 10, 'name': '기타 개별법 협의', 'category': 'individual', 'agency': '',
     'content_hint': '', 'doc_label': '협의문'},
]

# 인허가 현황 — 문서는 완료/미완료/미대상 3상태지만, 실무상 '미완료'를
# 진행중·미착수로 나눠 관리한다(md 내보낼 때 둘을 '미완료'로 합쳐 출력).
PERMIT_STATE_CHOICES = [
    ('done', '완료'), ('active', '진행중'), ('idle', '미착수'), ('na', '미대상'),
]
PERMIT_CATEGORY_CHOICES = [('statutory', '법정절차'), ('individual', '개별법 협의')]

# 확정도 — 사업개요 양식의 전 항목 공통
CERTAINTY_CHOICES = [('confirmed', '확정'), ('unconfirmed', '미확정'), ('na', '해당없음')]

# 계약 유형(양식 §5 드롭다운)
CONTRACT_CATEGORY_CHOICES = [
    ('land_lease', '부지 임대차'), ('dev_service', '개발용역'), ('asset_transfer', '자산양수도'),
    ('expansion_agreement', '사업확장 등 합의서'), ('permit_service', '개발행위 인허가 용역'),
    ('elec_design', '전기설계 용역'), ('eia_service', '환경영향평가 용역'),
    ('dia_service', '재해영향평가 용역'), ('dev_support', '사업개발지원 용역'),
    ('community', '지역수용성 용역'), ('grid_contract', '송전용전기설비이용계약'),
    ('epc', 'EPC'), ('pf_loan', 'PF 대출약정'), ('ppa_rec', 'PPA / REC 매매'),
    ('om', 'O&M (관리운영위탁)'), ('supervision', '감리 · OE'), ('etc', '기타'),
]
CONTRACT_STATUS_CHOICES = [('signed', '체결'), ('planned', '체결 예정'), ('none', '미체결')]

# 진행경과 유형(양식 §6 드롭다운)
EVENT_TYPE_CHOICES = [
    ('permit', '인허가'), ('complaint', '민원'), ('land', '토지'),
    ('contract', '계약'), ('finance', '금융'), ('etc', '기타'),
]

# 사업개요 항목 정의 — SiteFact 골격의 단일 소스.
# (section, key, label) 순서대로 사업 등록 시 빈 항목이 자동 생성된다.
FACT_SECTIONS = [
    ('basic', '1. 사업 기본 정보'),
    ('spc', '2. SPC 정보'),
    ('land', '4. 부지 정보'),
    ('econ', '7. 경제성 및 총사업비'),
    ('pf', '8. 금융(PF)'),
]
FACT_DEFS = [
    ('basic', 'stage', '사업단계'),
    ('basic', 'name_alias', '사업명 (대표 / 별칭)'),
    ('basic', 'type', '유형'),
    ('basic', 'capacity', '용량'),
    ('basic', 'location', '위치'),
    ('basic', 'grid_point', '연계점'),
    ('basic', 'grid_distance', '연계거리'),
    ('basic', 'total_capex', '총사업비'),
    ('basic', 'ownership', '지분구조'),
    ('basic', 'profitability', '경제성'),
    ('basic', 'period', '사업기간'),
    ('basic', 'schedule', '일정 및 계획'),

    ('spc', 'corp_name', '회사명'),
    ('spc', 'corp_reg_no', '법인등록번호'),
    ('spc', 'biz_reg_no', '사업자등록번호'),
    ('spc', 'head_office', '본점'),
    ('spc', 'directors', '이사진'),
    ('spc', 'capital', '자본금'),

    ('land', 'area', '부지 면적'),
    ('land', 'land_type', '부지 유형'),
    ('land', 'zoning', '용도지역'),
    ('land', 'parcels', '필지 수'),
    ('land', 'category', '지목'),
    ('land', 'lease_period', '계약 기간'),
    ('land', 'rent', '임대료'),

    ('econ', 'total_capex', '총사업비 (억원)'),
    ('econ', 'epc_cost', 'EPC 공사비 (억원)'),
    ('econ', 'equity_debt', 'Equity / Debt 비율'),
    ('econ', 'es_investment', 'E&S 총 투자비 (억원)'),
    ('econ', 'gen_hours', '발전시간 (h)'),
    ('econ', 'annual_revenue', '연간 매출 (억원)'),
    ('econ', 'operating_profit', '영업이익 (억원)'),
    ('econ', 'net_profit', '당기순이익 (억원)'),
    ('econ', 'e_irr', 'E.IRR (%)'),
    ('econ', 'p_irr_pretax', 'P.IRR 세전 (%)'),
    ('econ', 'p_irr_aftertax', 'P.IRR 세후 (%)'),

    ('pf', 'commitment', '대주별 약정금액'),
    ('pf', 'interest_rate', 'PF 금리'),
    ('pf', 'maturity', '만기 · 상환 방식'),
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
