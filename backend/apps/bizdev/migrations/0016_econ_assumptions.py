"""경제성에 금융모델 가정사항 항목을 더한다.

착공·준공일, 운영기간, 자본금 비율, 가격 체계(SMP+REC / PPA)와 단가, 총투자비를
새로 만든다. 자유 텍스트였던 'Equity / Debt 비율'은 자본금 비율(숫자)로 옮기고
지운다 — 앞의 숫자를 자본금 몫으로 읽는다("30/70", "30 : 70", "30%" 모두).
차입금 비율·공사기간·운영종료일은 값을 따로 두지 않고 화면에서 계산한다.
"""
import re

from django.db import migrations

from apps.bizdev.constants import FACT_DEFS

OLD_KEY = 'equity_debt'
NEW_KEY = 'equity_ratio'


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')
    Site = apps.get_model('bizdev', 'Site')
    order = {(d['section'], d['key']): i for i, d in enumerate(FACT_DEFS)}

    for site in Site.objects.all():
        have = {(f.section, f.key): f for f in SiteFact.objects.filter(site=site)}

        # ① 정의에 새로 생긴 항목을 빈칸으로 만든다
        for d in FACT_DEFS:
            if (d['section'], d['key']) in have:
                continue
            have[(d['section'], d['key'])] = SiteFact.objects.create(
                site=site, section=d['section'], key=d['key'], label=d['label'],
                sort_order=order[(d['section'], d['key'])],
            )

        # ② Equity/Debt 텍스트 → 자본금 비율(숫자)
        old = have.get(('econ', OLD_KEY))
        if old:
            new = have.get(('econ', NEW_KEY))
            m = re.search(r'\d+(?:\.\d+)?', old.value or '')
            if new and m and not (new.value or '').strip():
                new.value = m.group()
                new.certainty = old.certainty
                new.note = old.note
                new.save(update_fields=['value', 'certainty', 'note'])
            old.delete()
            have.pop(('econ', OLD_KEY))

        # ③ 정의 순서대로 sort_order 를 다시 매긴다
        rows = [f for k, f in have.items() if k in order]
        for f in rows:
            f.sort_order = order[(f.section, f.key)]
        SiteFact.objects.bulk_update(rows, ['sort_order'])
        # 정의에서 라벨이 바뀐 항목도 맞춰 둔다
        for f in rows:
            label = FACT_DEFS[order[(f.section, f.key)]]['label']
            if f.label != label:
                f.label = label
                f.save(update_fields=['label'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0015_individual_permits')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
