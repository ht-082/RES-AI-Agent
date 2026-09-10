"""사업개요 md 문서를 읽어 사업지를 등록한다.

`backend/media/initial_docs/*/0. 사업개요_*.md` 는 실무 담당자가 정리한 최신
사실 정리본이고 양식이 같다. 손으로 옮겨 적으면 오타가 나므로 문서를 그대로
읽어 넣는다. 이미 있는 사업지(slug 기준)는 건드리지 않는다 — 화면에서 고친
값을 문서로 되돌리지 않기 위해서다(--force 로만 덮어쓴다).

    python manage.py import_overview_md --list
    python manage.py import_overview_md --only 당진1 --dry-run
    python manage.py import_overview_md
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bizdev.constants import (
    CONTRACT_CATEGORY_CHOICES, EVENT_TYPE_CHOICES, FACILITY_TYPE_OPTIONS,
    FACT_DEFS, STAGE_DEFS, STAGE_TO_LIFECYCLE,
)
from apps.bizdev.models import Contract, PermitStage, Site, SiteEvent, SiteFact
from apps.bizdev.views import bound_fact_values, make_slug, sigun_of

NL = chr(10)
UNSET = {'미정', '미확정', '-', '—', ''}

# 문서 §1·§2·§4 의 '구분' 라벨 → 항목 키
BASIC = {'사업단계': 'stage', '사업명': 'name', '유형': 'type', '용량': 'capacity',
         '위치': 'location', '연계점': 'grid_point', '연계거리': 'grid_distance'}
SPC = {'회사명': 'corp_name', '법인등록번호': 'corp_reg_no', '사업자등록번호': 'biz_reg_no',
       '본점': 'head_office', '이사진': 'directors', '자본금': 'capital', '설립일': 'established'}
LAND = {'부지 면적': 'area', '부지 유형': 'land_type', '용도지역': 'zoning',
        '필지 수': 'parcels', '지목': 'category', '계약 기간': 'lease_period', '임대료': 'rent'}
# §5 계약 정보의 '구분' → 계약 분류
CONTRACT = {'부지 임대차': 'land_lease', '개발용역': 'dev_service', '자산양수도': 'asset_transfer',
            '사업확장 등 합의서': 'expansion_agreement', '개발행위 인허가 용역': 'permit_service',
            '전기설계 용역': 'elec_design', '환경영향평가 용역': 'eia_service',
            '재해영향평가 용역': 'dia_service', '사업개발지원 용역': 'dev_support',
            '지역수용성 용역': 'community', '송전용전기설비이용계약': 'grid_contract',
            'EPC': 'epc', 'PF 대출약정': 'pf_loan', 'PPA / REC 매매': 'ppa_rec',
            'O&M (관리운영위탁)': 'om', '감리 · OE': 'supervision'}
EVENT_TYPE = {'인허가': 'permit', '민원': 'complaint', '토지': 'land',
              '계약': 'contract', '금융': 'finance'}

# 문서의 단계 표기 → 화면 단계(검토/개발/운영). 건설·시공은 아직 개발 단계다.
STAGE_MAP = {'검토': '검토', '개발': '개발', '건설': '개발', '시공': '개발',
             '운영': '운영', '': '개발'}

STAGE_NAMES = {d['name'] for d in STAGE_DEFS}
# 문서에서 쓰는 이름 → 정의된 항목 이름
STAGE_ALIAS = {'송전용전기설비 이용계약': '송전용전기설비이용계약',
               '(소규모)환경영향평가': '환경영향평가',
               '농지 타용도일시사용허가': '농지 타용도 일시사용허가'}


def cell(text):
    """표 한 칸 → 여러 줄 텍스트. <br>·굵게 표시를 정리한다.

    '미정 (REC 계약 물량 기준 50MW)' 처럼 미정으로 시작하는 칸은 값이 없는 것으로
    본다 — 괄호 안 참고 수치를 확정값처럼 옮기면 안 된다.
    """
    t = re.sub(r'<br\s*/?>', NL, text or '')
    t = t.replace('**', '').strip()
    if t in UNSET or re.match(r'^(미정|미확정)', t):
        return ''
    return t


def is_unset(text):
    return cell(text) == ''


def rows_of(md, heading):
    """'## 3-1.' 같은 제목 아래 표의 데이터 행들을 [칸, 칸, ...] 로."""
    m = re.search(r'^#{2,3}\s*' + re.escape(heading) + r'.*?$', md, re.M)
    if not m:
        return []
    body = md[m.end():]
    nxt = re.search(r'^#{2,3}\s', body, re.M)
    if nxt:
        body = body[:nxt.start()]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):   # 구분선
            continue
        if cells and cells[0] in ('구분', '항목', '일자'):          # 머리글
            continue
        out.append(cells)
    return out


def to_date(text):
    m = re.search(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', text or '')
    if not m:
        return ''
    y, mo, d = m.groups()
    return f'{y}-{int(mo):02d}-{int(d):02d}'


def to_number(text):
    m = re.search(r'\d+(?:,\d{3})*(?:\.\d+)?', (text or '').replace(' ', ''))
    return m.group().replace(',', '') if m else ''


def shareholders(text):
    """지분구조 문장 → 조직도 형식('이름 | 지분율' 줄).

    문서는 'SK이노베이션 50.001% (SI) / 트러스톤 자산운용 49.999% (FI)' 처럼 적는다.
    지분율은 각 조각의 첫 퍼센트를 쓴다 — 괄호 안 다른 비율(모회사 지분 등)에
    끌려가지 않게 한다.
    """
    if not text:
        return ''
    parts = re.split(r'\s+/\s+', text)
    if len(parts) == 1:
        parts = re.split(r'\s+[·、]\s+', text)
    rows = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.search(r'(\d+(?:\.\d+)?)\s*%', part)
        pct = m.group(1) if m else ''
        name = (part[:m.start()] + part[m.end():]) if m else part
        name = re.sub(r'\s{2,}', ' ', name).strip(' -—·,')
        rows.append(f'{name} | {pct}')
    return NL.join(rows)


def permit_status(state, content, remark):
    """문서의 '현황' → 화면 상태. 미완료라도 움직임이 있으면 진행중으로 본다."""
    s = (state or '').replace(' ', '')
    if '완료' in s and '미완료' not in s:
        return 'done'
    if '미대상' in s or '해당없음' in s:
        return 'na'
    moving = re.search(r'신청|접수|제출|협의\s*중|진행|조치|수령|심사',
                       f'{content} {remark}')
    return 'active' if moving else 'idle'


class Command(BaseCommand):
    help = '사업개요 md 문서로 사업지를 등록한다'

    def add_arguments(self, parser):
        parser.add_argument('--only', help='문서 이름에 이 말이 든 것만')
        parser.add_argument('--dry-run', action='store_true', help='쓰지 않고 보기만')
        parser.add_argument('--force', action='store_true',
                            help='이미 있는 사업지도 다시 만든다(기존 값을 지운다). '
                                 '--only 와 함께만 쓸 수 있다')
        parser.add_argument('--list', action='store_true', help='문서 목록만')

    def handle(self, *args, **opt):
        root = Path(settings.MEDIA_ROOT) / 'initial_docs'
        files = sorted(root.glob('*/0. 사업개요_*.md'))
        if opt['only']:
            files = [f for f in files if opt['only'] in str(f)]
        if opt['list']:
            for f in files:
                self.stdout.write(f'  {f.parent.name}/{f.name}')
            return
        # --force 는 기존 데이터를 지운다. 어떤 사업을 덮어쓸지 --only 로
        # 분명히 밝히지 않으면 받지 않는다 — 문서에 없는 화면 편집분이 날아간다.
        if opt['force'] and not opt['only']:
            raise CommandError('--force 는 --only 와 함께만 쓸 수 있습니다. '
                               '덮어쓸 사업을 지정하세요.')
        for path in files:
            self.import_one(path, opt)

    # ── 문서 하나 ────────────────────────────────────────────────
    def import_one(self, path, opt):
        md = path.read_text(encoding='utf-8')
        basic = {r[0]: r[1] for r in rows_of(md, '1.') if len(r) > 1}
        name_cell = cell(basic.get('사업명', ''))
        rep = re.search(r'대표:\s*(.+)', name_cell)
        name = (rep.group(1).strip() if rep else name_cell.split(NL)[0]).strip()
        if not name:
            self.stderr.write(f'! 사업명을 못 읽음: {path.name}')
            return

        slug = make_slug(name)
        existing = Site.objects.filter(slug=slug).first() or \
            Site.objects.filter(name=name).first()
        if existing and not opt['force']:
            self.stdout.write(f'· 건너뜀(이미 있음): {name}')
            return

        stage = STAGE_MAP.get(cell(basic.get('사업단계', '')), '개발')
        lifecycle = STAGE_TO_LIFECYCLE.get(stage, 'dev')
        location = cell(basic.get('위치', '')).split(NL)[0]
        capacity = to_number(cell(basic.get('용량', ''))) or '0'
        raw_type = cell(basic.get('유형', ''))
        ftype = next((o for o in FACILITY_TYPE_OPTIONS if raw_type and raw_type in o),
                     '육상태양광' if '태양' in raw_type else '기타')

        counts = {}
        if opt['dry_run']:
            self.stdout.write(self.style.NOTICE(f'[모의] {name} · {stage} · '
                                                f'{capacity}MW · {location}'))
        with transaction.atomic():
            if existing and opt['force']:
                existing.delete()
            site = Site.objects.create(
                slug=slug, name=name, capacity_mw=float(capacity), location=location,
                sido=sigun_of(location) or '', facility_type=ftype,
                energy_type='wind' if '풍력' in ftype else 'solar',
                lifecycle=lifecycle, status='active' if lifecycle == 'dev' else 'done',
                pm_name='', cod=to_date(cell(basic.get('사업기간', ''))),
            )
            counts['facts'] = self.make_facts(site, md, basic)
            counts['stages'] = self.make_stages(site, md)
            counts['contracts'] = self.make_contracts(site, md)
            counts['events'] = self.make_events(site, md)
            if opt['dry_run']:
                transaction.set_rollback(True)

        mark = '[모의] ' if opt['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'{mark}{name} · {stage} · {capacity}MW · {location or "위치 미정"} — '
            f"항목 {counts['facts']} · 인허가 {counts['stages']} · "
            f"계약 {counts['contracts']} · 경과 {counts['events']}"))

    # ── §1·§2·§4 → 사업개요 항목 ─────────────────────────────────
    def make_facts(self, site, md, basic):
        spc = {r[0]: r[1] for r in rows_of(md, '2.') if len(r) > 1}
        land = {r[0]: r[1] for r in rows_of(md, '4.') if len(r) > 1}
        certainty = {}
        values = {}
        leftovers = []

        def take(rows, mapping, section):
            for label, raw in rows.items():
                key = mapping.get(label.strip())
                if not key:
                    continue
                value = cell(raw)
                if not value:
                    continue
                if key == 'established':
                    value = to_date(value)
                elif key == 'capacity':
                    number = to_number(value)
                    if number and number != value:
                        leftovers.append(f'용량 원문: {value}')
                    value = number
                elif key == 'location':
                    first = re.sub(r'^\d+차\s*:\s*', '', value.split(NL)[0])
                    if first != value:
                        leftovers.append(f'위치 원문: {value.replace(NL, " / ")}')
                    value = first
                elif key == 'name':
                    value = site.name
                elif key == 'type':
                    if value != site.facility_type:
                        leftovers.append(f'유형 원문: {value}')
                    value = site.facility_type
                values[(section, key)] = value

        take(basic, BASIC, 'basic')
        take(spc, SPC, 'spc')
        take(land, LAND, 'land')

        # 자리가 없는 §1 행은 버리지 않고 기타에 원문을 남긴다
        for label in ('사업기간', '일정 및 계획'):
            text = cell(basic.get(label, ''))
            if text:
                leftovers.append(f'{label}: {text.replace(NL, " / ")}')
        if leftovers:
            values[('basic', 'etc')] = NL.join(leftovers)

        # 문서에 없는 칸은 등록 폼 값(Site 컬럼)으로 채운다
        for k, v in bound_fact_values(site).items():
            values.setdefault(k, v)

        # 확정도 — 문서 3열
        for rows, mapping, section in ((rows_of(md, '1.'), BASIC, 'basic'),
                                       (rows_of(md, '2.'), SPC, 'spc'),
                                       (rows_of(md, '4.'), LAND, 'land')):
            for r in rows:
                key = mapping.get(r[0].strip()) if r else None
                if key and len(r) > 2:
                    certainty[(section, key)] = ('confirmed' if '미확정' not in r[2]
                                                 and '확정' in r[2] else 'unconfirmed')

        # 별칭 · 지분구조는 자리가 따로 있다
        alias = re.search(r'별칭:\s*(.+)', cell(basic.get('사업명', '')))
        if alias:
            values[('basic', 'aliases')] = alias.group(1).replace(' / ', ', ').strip()
        own = shareholders(cell(basic.get('지분구조', '')))
        if own:
            values[('spc', 'ownership')] = own

        made = 0
        for i, d in enumerate(FACT_DEFS):
            k = (d['section'], d['key'])
            SiteFact.objects.create(
                site=site, section=d['section'], key=d['key'], label=d['label'],
                sort_order=i, value=values.get(k, ''),
                certainty=certainty.get(k, 'unconfirmed'))
            made += 1
        return made

    # ── §3-1·3-2 → 인허가 항목 ───────────────────────────────────
    def make_stages(self, site, md):
        doc = {}
        for heading in ('3-1.', '3-2.'):
            for r in rows_of(md, heading):
                if len(r) < 2:
                    continue
                label = STAGE_ALIAS.get(r[0].strip(), r[0].strip())
                doc[label] = {
                    'status': permit_status(r[1], r[2] if len(r) > 2 else '',
                                            r[4] if len(r) > 4 else ''),
                    'content': cell(r[2]) if len(r) > 2 else '',
                    'certainty': ('confirmed' if len(r) > 3 and '미확정' not in r[3]
                                  and '확정' in r[3] else 'unconfirmed'),
                    'remark': cell(r[4]) if len(r) > 4 else '',
                }

        made = 0
        for d in STAGE_DEFS:                      # 정의된 골격 먼저
            v = doc.pop(d['name'], None)
            PermitStage.objects.create(
                site=site, stage_no=d['stage_no'], name=d['name'],
                agency=d['agency'], category=d['category'], tier=d['tier'],
                doc_label=d['doc_label'],
                status=v['status'] if v else 'idle',
                content=v['content'] if v else '',
                certainty=v['certainty'] if v else 'unconfirmed',
                remark=v['remark'] if v else '')
            made += 1
        for i, (label, v) in enumerate(doc.items()):   # 문서에만 있는 항목
            if label in ('기타 개별법 협의',) and not v['content']:
                continue
            PermitStage.objects.create(
                site=site, stage_no=len(STAGE_DEFS) + 1 + i, name=label,
                agency='', category='individual', tier='minor', doc_label='문서',
                is_custom=True, status=v['status'], content=v['content'],
                certainty=v['certainty'], remark=v['remark'])
            made += 1
        return made

    # ── §5 → 계약 ───────────────────────────────────────────────
    def make_contracts(self, site, md):
        made = 0
        for i, r in enumerate(rows_of(md, '5.')):
            if len(r) < 2:
                continue
            label = r[0].strip()
            counterparty, summary = cell(r[1]), cell(r[2]) if len(r) > 2 else ''
            note = cell(r[4]) if len(r) > 4 else ''
            if not (counterparty or summary or note):
                continue
            # 계약 정보는 체결된 것만 담는다. 문서의 확정도가 '확정'이고 내용이
            # 있으면 체결로 본다 — 비고에 '체결'이라 적지 않은 확정 계약이 많다
            # (임자도는 전 건이 확정인데 비고가 비어 있다). 미체결·검토 중·예정은
            # 넣지 않는다.
            confirmed = len(r) > 3 and '확정' in r[3] and '미확정' not in r[3]
            text = f'{summary} {note}'
            if not confirmed or re.search(r'미체결|검토\s*중|예정', text):
                continue
            Contract.objects.create(
                site=site, category=CONTRACT.get(label, 'etc'),
                counterparty=counterparty, summary=summary,
                certainty='confirmed', status='signed',
                note=re.sub(r'^체결(\s*·\s*)?', '', note).strip(), sort_order=i)
            made += 1
        return made

    # ── §6 → 진행경과 및 이슈 ────────────────────────────────────
    def make_events(self, site, md):
        made = 0
        for r in rows_of(md, '6.'):
            if len(r) < 3:
                continue
            date, kind, summary = to_date(r[0]), r[1].strip(), cell(r[2])
            if not summary:
                continue
            SiteEvent.objects.create(
                site=site, event_date=date or None,
                event_type=EVENT_TYPE.get(kind, 'etc'),
                status='done' if date else 'ongoing',
                summary=summary,
                certainty=('confirmed' if len(r) > 3 and '미확정' not in r[3]
                           and '확정' in r[3] else 'unconfirmed'))
            made += 1
        return made


# 알려진 계약 분류 라벨이 실제 choices 와 어긋나면 바로 드러나게 한다
_valid = {c[0] for c in CONTRACT_CATEGORY_CHOICES}
assert set(CONTRACT.values()) <= _valid, set(CONTRACT.values()) - _valid
_valid_evt = {c[0] for c in EVENT_TYPE_CHOICES}
assert set(EVENT_TYPE.values()) <= _valid_evt, set(EVENT_TYPE.values()) - _valid_evt
