"""인허가 본문을 '라벨: 값' 줄로 맞춘다.

채울 칸이 정해진 항목(허가번호·용량·면적 등)은 화면이 칸마다 값만 넣게 그리는데,
라벨 없이 값만 적혀 있으면 그 칸에 붙지 않고 자유 텍스트로 남는다.
칸이 하나뿐인 항목에 한해 기존 값에 라벨을 붙여 준다(환경영향평가 '소규모' 등).
칸이 여럿인 항목은 어느 칸인지 단정할 수 없어 손대지 않는다.
"""
from django.db import migrations

from apps.bizdev.constants import STAGE_DEFS

SINGLE = {d['name']: d['content_fields'][0]
          for d in STAGE_DEFS if len(d.get('content_fields') or []) == 1}


def forwards(apps, schema_editor):
    PermitStage = apps.get_model('bizdev', 'PermitStage')
    for stage in PermitStage.objects.filter(name__in=SINGLE):
        value = (stage.content or '').strip()
        if not value or ':' in value or '\n' in value:
            continue
        stage.content = f'{SINGLE[stage.name]}: {value}'
        stage.save(update_fields=['content'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0017_capex_breakdown')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
