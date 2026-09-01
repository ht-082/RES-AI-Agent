"""
지분구조를 "주주명 | 지분%" 줄 목록으로 바꾼다(화면에서 행 단위로 편집·합계 검증).
운영개시일 형식(YYYY-MM-DD)에 맞춰 Site.cod 도 함께 맞춘다.
"""
import re

from django.db import migrations


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')

    for fact in SiteFact.objects.filter(section='basic', key='ownership'):
        value = (fact.value or '').strip()
        if not value or '|' in value:
            continue
        lines = []
        for line in value.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.search(r'\(?\s*지분\s*([\d.]+)\s*%\s*\)?', line)
            pct = m.group(1) if m else ''
            name = re.sub(r'\(?\s*지분\s*[\d.]+\s*%\s*\)?', '', line).strip(' ·,')
            lines.append(f'{name} | {pct}')
        fact.value = '\n'.join(lines)
        fact.save(update_fields=['value'])

    Site = apps.get_model('bizdev', 'Site')
    for site in Site.objects.exclude(cod=''):
        m = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$', (site.cod or '').strip())
        if m:
            y, mo, d = m.groups()
            site.cod = f'{y}-{int(mo):02d}-{int(d):02d}'
            site.save(update_fields=['cod'])


class Migration(migrations.Migration):
    dependencies = [('bizdev', '0004_reformat_basic_facts')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
