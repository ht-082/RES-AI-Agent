"""
사업개발 시드 적재 — 원본 Re-project-mng supabase 시드(25개소) 이식.

  python manage.py seed_bizdev          # 멱등 적재(slug 기준 update_or_create)
  python manage.py seed_bizdev --wipe   # 전부 지우고 재적재
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bizdev.constants import STAGE_DEFS
from apps.bizdev.models import BudgetEntry, CommunityIssue, PermitStage, Site
from apps.bizdev.seed_data import BUDGETS, DEFAULT_PM_NAME, ISSUES, SITES, STAGES

SITE_FIELDS = ['name', 'capacity_mw', 'location', 'sido', 'facility_type', 'status',
               'risk_tag', 'risk_level', 'target_ntp', 'approved_budget_krw',
               'lat', 'lng', 'energy_type', 'lifecycle', 'address_detail',
               'annual_gwh', 'cod']


def _resolve_date(value):
    if isinstance(value, tuple) and value[0] == 'days_ago':
        return date.today() - timedelta(days=value[1])
    return value


class Command(BaseCommand):
    help = '사업개발 시드 데이터 적재 (25개소, 멱등)'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true',
                            help='기존 bizdev 데이터를 전부 지우고 재적재')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['wipe']:
            deleted, _ = Site.objects.all().delete()
            self.stdout.write(f'기존 데이터 삭제: {deleted}건(연쇄 포함)')

        created = updated = 0
        for row in SITES:
            slug, values = row[0], dict(zip(SITE_FIELDS, row[1:]))
            values['pm_name'] = DEFAULT_PM_NAME
            site, was_created = Site.objects.update_or_create(slug=slug, defaults=values)
            created += was_created
            updated += (not was_created)

            # 단계: 이미 있으면 건드리지 않는다(사용자 편집 보존). --wipe 후엔 항상 생성.
            if not site.stages.exists():
                defs = STAGES.get(slug)
                if defs:
                    PermitStage.objects.bulk_create([
                        PermitStage(site=site, stage_no=no, name=name, agency=agency,
                                    tier=tier, status=st, progress_pct=pct,
                                    received_date=received, detail=detail,
                                    dday_label=dday, doc_label=doc)
                        for (no, name, agency, tier, st, pct, received, detail, dday, doc) in defs
                    ])
                else:
                    # 원본 시드에 단계가 없는 사업지 → 12단계 idle 골격
                    PermitStage.objects.bulk_create([
                        PermitStage(site=site, status='idle', progress_pct=0, **d)
                        for d in STAGE_DEFS
                    ])

            if not site.budget_entries.exists():
                BudgetEntry.objects.bulk_create([
                    BudgetEntry(site=site, category=cat, amount_krw=amount,
                                exec_date=exec_date, memo=memo)
                    for (cat, amount, exec_date, memo) in BUDGETS.get(slug, [])
                ])

            if not site.issues.exists():
                CommunityIssue.objects.bulk_create([
                    CommunityIssue(site=site, issue_date=_resolve_date(d), title=title,
                                   status=st, issue_type=itype, description=desc)
                    for (d, title, st, itype, desc) in ISSUES.get(slug, [])
                ])

        self.stdout.write(self.style.SUCCESS(
            f'시드 완료 — 사업지 {Site.objects.count()}개'
            f' (신규 {created} · 갱신 {updated}) · 단계 {PermitStage.objects.count()}'
            f' · 예산 {BudgetEntry.objects.count()} · 이슈 {CommunityIssue.objects.count()}'))
