"""개별법 협의 항목을 원본 구성(7건)으로 맞춘다.

농지 타용도 일시사용허가 · 농지생산기반시설 사용허가 · 경관심의 · 교통계획 ·
문화재지표조사를 개발행위허가 하위로 추가하고, 자리를 대신하던 '기타 개별법 협의'
는 적어 둔 내용을 개발행위허가 특이사항으로 옮긴 뒤 지운다(문서가 붙어 있으면
남긴다). 항목 번호는 STAGE_DEFS 순서로 다시 매긴다.
"""
from django.db import migrations

from apps.bizdev.constants import STAGE_DEFS

CATCH_ALL = '기타 개별법 협의'
PARENT = '개발행위허가'


def expand(apps, schema_editor):
    PermitStage = apps.get_model('bizdev', 'PermitStage')
    Site = apps.get_model('bizdev', 'Site')
    rank = {d['name']: d['stage_no'] for d in STAGE_DEFS}

    for site in Site.objects.all():
        stages = {s.name: s for s in PermitStage.objects.filter(site=site)}
        if not stages:
            continue

        # ① 기타 개별법 협의에 적어 둔 내용을 개발행위허가 특이사항으로 옮긴다
        catch = stages.get(CATCH_ALL)
        parent = stages.get(PARENT)
        if catch and parent:
            moved = '\n'.join(t for t in (catch.content, catch.remark) if t.strip())
            if moved:
                parent.remark = '\n'.join(t for t in (parent.remark, moved) if t.strip())
                parent.save(update_fields=['remark'])
            if not catch.documents.exists():
                catch.delete()
                stages.pop(CATCH_ALL)

        # ② 정의에 있으나 없는 항목을 만든다
        for d in STAGE_DEFS:
            if d['name'] in stages:
                continue
            stages[d['name']] = PermitStage.objects.create(
                site=site, stage_no=900 + d['stage_no'], name=d['name'],
                category=d['category'], tier=d['tier'], agency=d['agency'],
                doc_label=d['doc_label'], status='idle', certainty='unconfirmed',
            )

        # ③ 정의 순서로 다시 번호를 매긴다(직접 추가한 항목은 뒤로)
        rows = sorted(stages.values(), key=lambda s: (rank.get(s.name, 10_000), s.stage_no))
        for i, stage in enumerate(rows):          # 1차: 충돌 없는 임시 번호
            stage.stage_no = 1000 + i
        PermitStage.objects.bulk_update(rows, ['stage_no'])
        for i, stage in enumerate(rows):          # 2차: 최종 1..n
            stage.stage_no = i + 1
        PermitStage.objects.bulk_update(rows, ['stage_no'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0014_stage_tier_order')]

    operations = [migrations.RunPython(expand, migrations.RunPython.noop)]
