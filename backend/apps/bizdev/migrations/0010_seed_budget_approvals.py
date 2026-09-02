"""
기존에 한 칸(Site.approved_budget_krw)이던 승인 예산을 용도별 승인 내역으로 옮긴다.

원래 값은 용도 구분이 없던 총액이라 임의로 쪼개지 않고 '기타'에 한 건으로 넣고
메모에 그 사실을 적는다 — 담당자가 화면에서 용도별로 나누면 된다.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Site = apps.get_model('bizdev', 'Site')
    BudgetApproval = apps.get_model('bizdev', 'BudgetApproval')

    for site in Site.objects.exclude(approved_budget_krw=0):
        if BudgetApproval.objects.filter(site=site).exists():
            continue
        BudgetApproval.objects.create(
            site=site,
            category='etc',
            amount_krw=site.approved_budget_krw,
            memo='기존 승인 총액(용도 미구분) — 용도별로 나눠 주세요',
        )


class Migration(migrations.Migration):
    dependencies = [('bizdev', '0009_budgetentry_updated_at_budgetapproval')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
