"""
지분구조를 SPC 정보 소속으로 옮긴다.
사업 개요에는 SPC 값을 비추는 읽기 전용 항목만 남는다(입력은 한 곳에서만).
"""
from django.db import migrations


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')

    for old in SiteFact.objects.filter(section='basic', key='ownership'):
        SiteFact.objects.update_or_create(
            site=old.site, section='spc', key='ownership',
            defaults={
                'label': '지분구조',
                'value': old.value,
                'certainty': old.certainty,
                'source': old.source,
                'note': old.note,
                'sort_order': 18,
            },
        )
        # 사업 개요 쪽은 파생 표시라 값을 비운다
        old.value = ''
        old.save(update_fields=['value'])


class Migration(migrations.Migration):
    dependencies = [('bizdev', '0005_reformat_ownership')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
