"""사업비를 금융모델 [총투자비] 표와 같은 구성으로 나눈다.

조사설계비 · 토지비 · 공사비 · 기타비용 · 금융비용 · Overfunding · DSRA 를 만들고,
총사업비 · 총투자비는 이 항목들의 합계로 바꾼다(사람이 직접 입력하지 않는다).
기존에 손으로 넣어 둔 총사업비 값은 구성 항목을 하나도 채우지 않은 동안에는
그대로 남는다 — 합계 계산은 구성 항목이 하나라도 있을 때만 값을 덮어쓴다.
'EPC 공사비'는 같은 자리를 뜻하므로 '공사비'로 이름만 바꿔 값을 잇는다.
"""
from django.db import migrations

from apps.bizdev.constants import FACT_DEFS


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')
    Site = apps.get_model('bizdev', 'Site')
    order = {(d['section'], d['key']): i for i, d in enumerate(FACT_DEFS)}
    labels = {(d['section'], d['key']): d['label'] for d in FACT_DEFS}

    for site in Site.objects.all():
        have = {(f.section, f.key): f for f in SiteFact.objects.filter(site=site)}
        for d in FACT_DEFS:
            key = (d['section'], d['key'])
            if key not in have:
                have[key] = SiteFact.objects.create(
                    site=site, section=d['section'], key=d['key'],
                    label=d['label'], sort_order=order[key],
                )

        rows = [f for k, f in have.items() if k in order]
        for f in rows:
            f.sort_order = order[(f.section, f.key)]
            f.label = labels[(f.section, f.key)]
        SiteFact.objects.bulk_update(rows, ['sort_order', 'label'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0016_econ_assumptions')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
