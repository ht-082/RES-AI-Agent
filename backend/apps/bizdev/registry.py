"""
법인등기부등본(등기사항전부증명서) 파서.

인터넷등기소에서 내려받는 PDF 는 스캔본이 아니라 텍스트 PDF 라 OCR 없이
그대로 읽힌다(실측: 2쪽 1,600자 추출). 스캔본으로 들어오면 텍스트가 비어
나오므로 그때는 "읽을 수 없다"고 알려 준다 — 잘못 채우는 것보다 낫다.

항목 라벨은 등본 서식이 고정이라 정규식으로 잡는다. 서식이 바뀌어도
못 찾은 항목은 건너뛰고 찾은 것만 채운다.
"""
import re

NL = chr(10)

# 등본 라벨은 글자 사이에 공백이 들어간다(예: "상  호") — \s* 로 흡수한다.
_ROLE = r'(대표이사|사내이사|사외이사|기타비상무이사|감사|이사)'


def _clean(text):
    return re.sub(r'\s+', ' ', (text or '')).strip()


def _after_label(text, label):
    """라벨 다음 줄에서 값 한 줄을 꺼낸다."""
    pattern = re.compile(r'\s*'.join(label) + r'\s*' + NL + r'+([^' + NL + r']+)')
    m = pattern.search(text)
    return _clean(m.group(1)) if m else ''


def parse_registry(text):
    """등본 전문에서 SPC 항목을 뽑는다. {key: value} — 못 찾은 항목은 빠진다."""
    out = {}
    if not text or len(text.strip()) < 50:
        return out

    m = re.search(r'등록번호\s*' + NL + r'+\s*(\d{6}-\d{7})', text)
    if m:
        out['corp_reg_no'] = m.group(1)

    name = _after_label(text, '상호')
    if name:
        out['corp_name'] = name

    office = _after_label(text, '본점')
    if office:
        out['head_office'] = office

    # 자본금 — "1주의 금액 금 500 원"과 구분해야 하므로 가장 큰 금액을 고른다
    amounts = [int(a.replace(',', '')) for a in re.findall(r'금\s*([\d,]{3,})\s*원', text)]
    if amounts:
        out['capital'] = f'{max(amounts):,}원'

    # 임원 — 역할 + 이름 (주민번호 앞자리로 행을 식별). 등장 순서 유지, 중복 제거
    officers, seen = [], set()
    for role, person in re.findall(_ROLE + r'\s+([가-힣]{2,5})\s+\d{6}-', text):
        key = (role, person)
        if key not in seen:
            seen.add(key)
            officers.append(f'{role} {person}')
    if officers:
        out['directors'] = NL.join(officers)

    m = re.search(r'회사성립연월일\s*' + NL + r'+\s*(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
    if m:
        y, mo, d = m.groups()
        out['established'] = f'{y}-{int(mo):02d}-{int(d):02d}'

    return out


def extract_pdf_text(path):
    """PDF 전문 추출. 스캔본이면 빈 문자열에 가깝다."""
    import fitz  # PyMuPDF — 적재 파이프라인이 이미 쓰는 라이브러리
    with fitz.open(path) as doc:
        return NL.join(page.get_text() for page in doc)
