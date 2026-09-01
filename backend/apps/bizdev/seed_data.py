"""
시드 데이터 — 대표 사업지 1건(홍성태양광)만 유지한다.

원본 Re-project-mng 의 더미 사업지 24개(04_seed.sql·08_more_sites.sql 유래)는
2026-09-01 사용자 요청으로 제거했다. 실제 사업은 화면에서 직접 등록해 관리한다.
지운 더미 정의가 다시 필요하면 커밋 57b23c9 의 이 파일을 참조할 것.

- 이슈의 상대 날짜는 ('days_ago', N) 로 적고 command 가 실행 시점 기준으로 계산한다.
- 단계 정의가 없는 사업지는 command 가 STAGE_DEFS 12단계 idle 골격을 깔아 준다.
"""
from datetime import date

# (slug, name, capacity_mw, location, sido, facility_type, status, risk_tag,
#  risk_level, target_ntp, approved_budget_krw, lat, lng, energy_type,
#  lifecycle, address_detail, annual_gwh, cod)
SITES = [
    ('hongseong-solar', '홍성태양광', 100, '충남 홍성군', '홍성군', '육상태양광',
     'active', '계통대기', 'md', "'27.Q2", 1860000000, 36.68, 126.55, 'solar',
     'dev', '충남 홍성군 갈산면 기산리 780', 135, "'27.Q4"),
]

# slug → [(stage_no, name, agency, tier, status, progress_pct,
#          received_date, detail, dday_label, doc_label)]
STAGES = {
    'hongseong-solar': [
        (1, '발전사업허가', '전기위원회', 'major', 'done', 100, None, '', '', '허가증'),
        (2, '송전용전기설비 이용계약', '한전', 'minor', 'active', 60, None, '', '', '이용계약서'),
        (3, '개발행위허가', '홍성군', 'major', 'active', 60, None, '', '', '허가서'),
        (4, '(소규모)환경영향평가', '금강유역환경청', 'minor', 'active', 45, None, '', '', '협의문'),
        (5, '재해영향평가', '충청남도', 'minor', 'wait', 30, None, '', '', '협의문'),
        (6, '농지 타용도 일시사용허가', '홍성군', 'minor', 'wait', 30, None, '', '', '허가서'),
        (7, '농지생산기반시설 사용허가', '한국농어촌공사', 'minor', 'idle', 0, None, '', '', '승인서'),
        (8, '경관심의', '홍성군', 'minor', 'idle', 0, None, '', '', '심의결과'),
        (9, '교통계획', '홍성군', 'minor', 'idle', 0, None, '', '', '심의결과'),
        (10, '문화재지표조사', '문화재청', 'minor', 'idle', 0, None, '', '', '조사보고서'),
        (11, '도로점용허가', '홍성군', 'major', 'idle', 0, None, '', '', '허가서'),
        (12, '공사계획인가', '전기안전공사', 'major', 'idle', 0, None, '', '', '인가서'),
    ],
}

# slug → [(category, amount_krw, exec_date, memo)]
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

# slug → [(issue_date | ('days_ago', N), title, status, issue_type, description)]
ISSUES = {
    'hongseong-solar': [
        (('days_ago', 3), '갈산면 주민 설명회 요청', 'open', 'complaint',
         '인근 마을 이장단이 사업 설명회 개최를 요청. 일정 협의 중.'),
        (('days_ago', 9), '계통 접속 대기 장기화 우려', 'prog', 'grid',
         '한전 접속 순번 2순위 · 보강 공사 일정 확인 필요.'),
        (('days_ago', 14), '농지 전용 요건 재확인', 'prog', 'etc',
         '농지 타용도 일시사용 요건 보완 자료 준비 중.'),
        (('days_ago', 40), '초기 환경 검토', 'closed', 'etc',
         '사전 환경성 검토 완료.'),
    ],
}

DEFAULT_PM_NAME = '정혁태'
