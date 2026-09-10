"""재무지표 항목을 사업지마다 만든다(운영 사업 화면 §2-3)."""
from django.db import migrations

from apps.bizdev.constants import FACT_DEFS


def forwards(apps, schema_editor):
    SiteFact = apps.get_model('bizdev', 'SiteFact')
    Site = apps.get_model('bizdev', 'Site')
    order = {(d['section'], d['key']): i for i, d in enumerate(FACT_DEFS)}
    for site in Site.objects.all():
        have = {(f.section, f.key) for f in SiteFact.objects.filter(site=site)}
        SiteFact.objects.bulk_create([
            SiteFact(site=site, section=d['section'], key=d['key'], label=d['label'],
                     sort_order=order[(d['section'], d['key'])])
            for d in FACT_DEFS if (d['section'], d['key']) not in have
        ])
        rows = list(SiteFact.objects.filter(site=site))
        for f in rows:
            if (f.section, f.key) in order:
                f.sort_order = order[(f.section, f.key)]
        SiteFact.objects.bulk_update(rows, ['sort_order'])


class Migration(migrations.Migration):

    dependencies = [('bizdev', '0021_ops_dashboard')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
