"""
사업 개요 항목에 입력기(드롭다운·숫자·날짜 등)를 붙이면서 값 형식이 바뀌었다.
기존 자유 텍스트를 새 형식으로 한 번 변환한다.

  용량        "99MW (AC) · DC 미정"      → "99"
  유형        "태양광"                    → 드롭다운 옵션값(없으면 '기타')
  연계점      "은하변전소"                → "은하"       (표시할 때 '변전소'를 붙인다)
  연계거리    "약 20km · 지중 · 154kV"   → "20 · 지중 · 154kV"
  운영개시일  "운영 개시(2031.12.31)..."  → "2031-12-31"
  총사업비·경제성                          → 빈 값(경제성 섹션에서 자동으로 끌어옴)
"""
import re

from django.db import migrations

FACILITY_OPTIONS = ['육상태양광', '수상태양광', '영농형태양광', '지붕형태양광',
                    '육상풍력', '해상풍력', '기타']


def to_number(value):
    m = re.search(r'[\d,]+(?:\.\d+)?', value or '')
    return m.group().replace(',', '') if m else ''


def to_date(value):
    m = re.search(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', value or '')
    if not m:
        return ''
    y, mo, d = m.groups()
    return f'{y}-{int(mo):02d}-{int(d):02d}'


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')

    for fact in SiteFact.objects.filter(section='basic').select_related('site'):
        value = (fact.value or '').strip()
        changed = True

        if fact.key == 'capacity':
            fact.value = to_number(value)
        elif fact.key == 'type':
            if value not in FACILITY_OPTIONS:
                site_type = (fact.site.facility_type or '').strip()
                fact.value = site_type if site_type in FACILITY_OPTIONS else '기타'
        elif fact.key == 'grid_point':
            fact.value = re.sub(r'변전소$', '', value).strip()
        elif fact.key == 'grid_distance':
            km = to_number(value)
            method = next((m for m in ('지중', '가공') if m in value), '')
            volt = next((v for v in ('22.9kV', '154kV', '345kV') if v in value), '')
            fact.value = ' · '.join(x for x in (km, method, volt) if x)
        elif fact.key == 'period':
            fact.value = to_date(value)
        elif fact.key in ('total_capex', 'profitability'):
            fact.value = ''          # 경제성 섹션에서 자동으로 끌어온다
        else:
            changed = False

        if changed:
            fact.save(update_fields=['value'])


def backwards(apps, schema_editor):
    # 형식 변환은 되돌리지 않는다(원문을 복원할 수 없다).
    pass


class Migration(migrations.Migration):
    dependencies = [('bizdev', '0003_alter_siteevent_summary')]
    operations = [migrations.RunPython(forwards, backwards)]
