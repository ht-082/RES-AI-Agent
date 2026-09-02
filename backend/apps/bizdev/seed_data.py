"""
시드 데이터 — 대표 사업지 1건(홍성1 태양광)만 유지한다.

값은 담당자 정리본 "0. 사업개요_홍성1태양광.md"(2026-08-03) 기준이다.
원본 Re-project-mng 의 더미 사업지 24개는 2026-09-01 제거했다(커밋 57b23c9 참조).

- 경과의 날짜가 None 이면 "진행 중"으로 표시된다.
- 항목 골격(FACT_DEFS)·인허가 항목(STAGE_DEFS)은 constants.py 가 단일 소스다.
"""
from datetime import date

NL = chr(10)   # 여러 줄 값 구성용

# (slug, name, capacity_mw, location, sido, facility_type, status, risk_tag,
#  risk_level, target_ntp, approved_budget_krw, lat, lng, energy_type,
#  lifecycle, address_detail, annual_gwh, cod)
SITES = [
    ('hongseong-solar', '홍성1 태양광', 99, '충남 홍성군 갈산면 기산리 780 일원', '홍성군',
     '기타', 'active', '계통 보강 대기', 'md', '', 1860000000,
     36.68, 126.55, 'solar', 'dev', '충남 홍성군 갈산면 기산리 780', None, '2031-12-31'),
]

# 사업개요 항목 — {slug: {(section, key): (value, certainty, source, note)}}
FACTS = {
    'hongseong-solar': {
        ('basic', 'stage'): ('개발', 'confirmed', '', '세부: 인허가 진행 단계'),
        ('basic', 'name'): ('홍성1 태양광', 'confirmed', '발전사업허가증', ''),
        ('basic', 'aliases'): (
            '홍성빛나래솔라 태양광' + NL + '홍성군 염해태양광' + NL + '홍성1 PJT',
            'confirmed', '발전사업허가증', ''),
        ('basic', 'type'): ('기타', 'confirmed', '', '염해간척지 태양광'),
        ('basic', 'capacity'): ('99', 'confirmed', '발전사업허가증', '허가 4건 합계 (AC)'),
        ('basic', 'location'): ('충남 홍성군 갈산면 기산리 780', 'confirmed',
                                '발전사업허가증', '대표 필지'),
        ('basic', 'grid_point'): ('은하', 'confirmed', '발전사업허가증', ''),
        ('basic', 'grid_distance'): ('20 · 지중 · 154kV', 'unconfirmed', '', ''),
        ('basic', 'total_capex'): ('', 'unconfirmed', '', ''),
        ('basic', 'profitability'): ('', 'unconfirmed', '', 'E.IRR은 펀드 기준'),
        ('basic', 'period'): ('2031-12-31', 'confirmed', '', '이후 20년 (부지 임대차와 동일)'),
        ('basic', 'manager'): ('정혁태', 'confirmed', '', ''),

        ('spc', 'corp_name'): ('주식회사 홍성빛나래솔라', 'confirmed', '발전사업허가증', ''),
        ('spc', 'corp_reg_no'): ('161411-0006603', 'confirmed', '사업자등록증', ''),
        ('spc', 'biz_reg_no'): ('324-86-03682', 'confirmed', '사업자등록증', ''),
        ('spc', 'head_office'): ('충청남도 서산시 동서1로 5,2층(석림동)', 'confirmed',
                                 '사업자등록증', ''),
        ('spc', 'directors'): ('대표자 현대석', 'confirmed', '', '이사구성 추후 확인'),
        ('spc', 'capital'): ('미정', 'unconfirmed', '', '추후 확인'),
        ('spc', 'ownership'): (
            '한국투자증권(주) — 트러스톤 ESG 신재생에너지 일반사모투자신탁 제2호 신탁업자 | 100',
            'confirmed', '', ''),

        ('land', 'area'): ('238,638평', 'confirmed', '발전사업허가 신청도서', ''),
        ('land', 'land_type'): ('염해간척지 · 임대', 'confirmed', '임대차계약서', ''),
        ('land', 'zoning'): ('미정', 'unconfirmed', '', ''),
        ('land', 'parcels'): ('58필지', 'confirmed', '', ''),
        ('land', 'category'): ('답', 'confirmed', '', ''),
        ('land', 'lease_period'): ('착공 시점부터 사업 운영 개시 후 20년까지', 'confirmed',
                                   '임대차계약서', ''),
        ('land', 'rent'): ('평당 연 6,000원', 'confirmed', '임대차계약서', ''),

        ('econ', 'total_capex'): ('1,560', 'unconfirmed', '', '예상치'),
        ('econ', 'epc_cost'): ('1,291', 'unconfirmed', '본단지 891억 / 송전선로 400억', '예상치'),
        ('econ', 'equity_debt'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'es_investment'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'gen_hours'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'annual_revenue'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'operating_profit'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'net_profit'): ('미정', 'unconfirmed', '', ''),
        ('econ', 'e_irr'): ('8.94', 'unconfirmed', '', '펀드 기준'),
        ('econ', 'p_irr_pretax'): ('8.25', 'unconfirmed', '', ''),
        ('econ', 'p_irr_aftertax'): ('미정', 'unconfirmed', '', ''),

        ('pf', 'commitment'): ('미정', 'unconfirmed', '', ''),
        ('pf', 'interest_rate'): ('미정', 'unconfirmed', '', ''),
        ('pf', 'maturity'): ('미정', 'unconfirmed', '', ''),
    },
}

# 인허가 — {slug: {stage_name: (status, content, certainty, remark)}}
PERMITS = {
    'hongseong-solar': {
        '발전사업허가': (
            'done',
            '허가번호: 제2025-68, 69, 70, 71호' + NL
            + '용량: 53.243 / 19.561 / 12.969 / 13.227MW' + NL
            + '허가일자: 2025.08.26 (신청 2025.07.02)' + NL
            + '허가조건: 2031년 12월 이후 계통 보강 후 접속',
            'confirmed', '조건부 허가 · 허가 4건 분할'),
        '송전용전기설비이용계약': (
            'active', '계약전력: 미정' + NL + '이용개시일: 미정', 'unconfirmed',
            '접속신청 2025.09.17 → 접속제의서 수령 2026.07.20 (한전)'),
        '개발행위허가': (
            'active', '면적: 238,638평' + NL + '필지수: 58', 'unconfirmed',
            '신청 2026.05.21 · 허가일 미정'),
        '공사계획인가': ('idle', '미정', 'unconfirmed', ''),
        '사용전검사': ('idle', '미정', 'unconfirmed', ''),
        '사업개시신고': ('idle', '미정', 'unconfirmed', ''),
        '개발행위준공': ('idle', '미정', 'unconfirmed', ''),
        '환경영향평가': ('active', '소규모', 'unconfirmed', '대상 유형(소규모)은 확정'),
        '재해영향평가': ('idle', '', 'unconfirmed', ''),
        '기타 개별법 협의': (
            'active',
            '토양 염도평가 완료 · 지반조사(압밀침하) 완료' + NL + '농지 타용도일시사용 진행 중',
            'unconfirmed', ''),
    },
}

# 계약 — {slug: [(category, counterparty, summary, certainty, status, note)]}
CONTRACTS = {
    'hongseong-solar': [
        ('land_lease', '토지주', '평당 연 6,000원 · 착공~운영개시 후 20년',
         'confirmed', 'signed', ''),
        ('dev_service', 'SK', 'SK가 개발용역 수행', 'confirmed', 'signed', ''),
        ('asset_transfer', 'SK / 트러스톤', '사업양수도', 'confirmed', 'signed', ''),
        ('expansion_agreement', 'SK / 트러스톤', '', 'confirmed', 'signed', ''),
        ('permit_service', '(주)유신', '', 'confirmed', 'signed', ''),
        ('elec_design', '(주)유신', '', 'confirmed', 'signed', ''),
        ('eia_service', '(주)송현', '', 'confirmed', 'signed', ''),
        ('dia_service', '(주)송현', '', 'confirmed', 'signed', ''),
        ('dev_support', '(주)지오엔', '', 'confirmed', 'signed', ''),
        ('community', '(주)지오엔', '', 'confirmed', 'signed', ''),
        ('grid_contract', '한국전력공사', '', 'unconfirmed', 'planned', ''),
        ('epc', '미정', '', 'unconfirmed', 'none', ''),
        ('pf_loan', '미정', '', 'unconfirmed', 'none', ''),
        ('ppa_rec', '미정', 'PPA 검토 중', 'unconfirmed', 'none', ''),
        ('om', '미정', '', 'unconfirmed', 'none', ''),
        ('supervision', '미정', '', 'unconfirmed', 'none', ''),
    ],
}

# 진행경과 — {slug: [(event_date | None, event_type, summary, certainty)]}
EVENTS = {
    'hongseong-solar': [
        (date(2026, 7, 20), 'permit', '송전용전기설비 접속제의서 수령 (한전)', 'confirmed'),
        (date(2026, 5, 21), 'permit', '개발행위허가 신청', 'confirmed'),
        (date(2025, 9, 17), 'permit', '계통접속 신청', 'confirmed'),
        (date(2025, 8, 26), 'permit',
         '발전사업허가 취득 (제2025-68~71호 · 합계 99MW · 조건부)', 'confirmed'),
        (date(2025, 7, 2), 'permit', '발전사업허가 신청', 'confirmed'),
        (None, 'complaint', '사업부지 해당 마을에서 빠르게 사업 추진할 것 요구 중', 'unconfirmed'),
        (None, 'complaint', '인근 부지 확보 중인 경쟁사 관련 이장님 민원 사항 관리 중', 'unconfirmed'),
        (None, 'land', '송전선로 용지 교섭 협의 중', 'unconfirmed'),
    ],
}

# 예산 집행 — 원본 목업값 유지(실제 집행 내역 확보 전까지)
BUDGETS = {
    'hongseong-solar': [
        ('land', 620000000, date(2026, 2, 11), '부지 매입 계약금(임야·농지)'),
        ('land', 300000000, date(2026, 4, 3), '지장물 보상·추가 매입'),
        ('permit', 220000000, date(2026, 3, 20), '인허가 용역·부담금'),
        ('design', 200000000, date(2026, 1, 15), '계통연계 기본설계'),
        ('legal', 120000000, date(2026, 2, 28), '농지 인허가 법무 자문'),
        ('etc', 80000000, date(2026, 3, 10), '측량·현장 경비'),
    ],
}

DEFAULT_PM_NAME = '정혁태'
