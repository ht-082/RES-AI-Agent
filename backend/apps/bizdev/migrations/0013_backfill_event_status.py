"""
진행경과의 상태를 채운다.

예전에는 일자를 비워 "진행 중"을 나타냈다. 이제 일자는 등록 일자이고 상태는
status 로 따로 두므로, 날짜 없는 행은 진행중 + 등록일(생성 시각)로 옮기고
날짜가 있던 행(이미 일어난 일)은 완료로 본다.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    SiteEvent = apps.get_model('bizdev', 'SiteEvent')

    for event in SiteEvent.objects.all():
        if event.event_date is None:
            event.status = 'ongoing'
            event.event_date = event.created_at.date()
        else:
            event.status = 'done'
        event.save(update_fields=['status', 'event_date'])


class Migration(migrations.Migration):
    dependencies = [('bizdev', '0012_siteevent_status_alter_siteevent_event_date')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
