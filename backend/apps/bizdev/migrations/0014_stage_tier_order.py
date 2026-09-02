"""인허가 항목 순서·계층을 STAGE_DEFS 기준으로 맞춘다.

화면이 category(법정/개별) 두 표에서 tier(상위/하위) + 줄 순서 묶음으로 바뀌었다.
개별법 협의가 개발행위허가 바로 뒤에 오도록 다시 번호를 매기고, tier 를 정의대로
채운다. 직접 추가한 항목(is_custom)은 기존 상대 순서를 지켜 뒤에 붙인다.
"""
from django.db import migrations

from apps.bizdev.constants import STAGE_DEFS


def reorder(apps, schema_editor):
    PermitStage = apps.get_model('bizdev', 'PermitStage')
    Site = apps.get_model('bizdev', 'Site')
    rank = {d['name']: d['stage_no'] for d in STAGE_DEFS}
    tiers = {d['name']: d['tier'] for d in STAGE_DEFS}

    for site_id in Site.objects.values_list('id', flat=True):
        stages = list(PermitStage.objects.filter(site_id=site_id).order_by('stage_no'))
        if not stages:
            continue
        # 정의된 항목은 STAGE_DEFS 순서, 직접 추가한 항목은 기존 순서대로 뒤에
        ordered = sorted(
            enumerate(stages),
            key=lambda p: (rank.get(p[1].name, 10_000), p[0]),
        )
        for i, (_, stage) in enumerate(ordered):      # 1차: 충돌 없는 임시 번호
            stage.stage_no = 1000 + i
            if stage.name in tiers:
                stage.tier = tiers[stage.name]
        PermitStage.objects.bulk_update([s for _, s in ordered], ['stage_no', 'tier'])
        for i, (_, stage) in enumerate(ordered):      # 2차: 최종 1..n
            stage.stage_no = i + 1
        PermitStage.objects.bulk_update([s for _, s in ordered], ['stage_no'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0013_backfill_event_status')]

    operations = [migrations.RunPython(reorder, migrations.RunPython.noop)]
