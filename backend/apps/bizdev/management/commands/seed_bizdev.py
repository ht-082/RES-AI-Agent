"""
사업개발 시드 적재 — 사업개요 양식(법정절차 7 + 개별법 3 · 항목 39종) 기준.

  python manage.py seed_bizdev          # 멱등 적재
  python manage.py seed_bizdev --wipe   # 전부 지우고 재적재

사업개요 항목(SiteFact)·인허가(PermitStage)는 constants 의 정의를 골격으로 깔고,
seed_data 에 값이 있으면 채운다. 구 12단계처럼 정의에서 사라진 인허가 항목은
문서가 붙어 있지 않은 경우에 한해 정리한다(사용자가 추가한 항목은 보존).
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bizdev.constants import FACT_DEFS, STAGE_DEFS
from apps.bizdev.models import (
    BudgetEntry, CommunityIssue, Contract, PermitStage, Site, SiteEvent, SiteFact,
)
from apps.bizdev import seed_data as sd

SITE_FIELDS = ['name', 'capacity_mw', 'location', 'sido', 'facility_type', 'status',
               'risk_tag', 'risk_level', 'target_ntp', 'approved_budget_krw',
               'lat', 'lng', 'energy_type', 'lifecycle', 'address_detail',
               'annual_gwh', 'cod']


def _resolve_date(value):
    if isinstance(value, tuple) and value[0] == 'days_ago':
        return date.today() - timedelta(days=value[1])
    return value


class Command(BaseCommand):
    help = '사업개발 시드 데이터 적재 (사업개요 양식 기준, 멱등)'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true',
                            help='기존 bizdev 데이터를 전부 지우고 재적재')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['wipe']:
            deleted, _ = Site.objects.all().delete()
            self.stdout.write(f'기존 데이터 삭제: {deleted}건(연쇄 포함)')

        for row in SITES_iter():
            slug, values = row[0], dict(zip(SITE_FIELDS, row[1:]))
            values['pm_name'] = sd.DEFAULT_PM_NAME
            site, created = Site.objects.update_or_create(slug=slug, defaults=values)

            self._sync_facts(site, sd.FACTS.get(slug, {}))
            self._sync_permits(site, sd.PERMITS.get(slug, {}))
            self._fill_once(site, slug)
            self.stdout.write(f'  {"신규" if created else "갱신"}: {site.name}')

        self.stdout.write(self.style.SUCCESS(
            f'시드 완료 — 사업지 {Site.objects.count()} · 항목 {SiteFact.objects.count()}'
            f' · 인허가 {PermitStage.objects.count()} · 계약 {Contract.objects.count()}'
            f' · 경과 {SiteEvent.objects.count()} · 예산 {BudgetEntry.objects.count()}'))

    # ── 사업개요 항목: 정의 골격을 깔고 시드 값이 있으면 채운다 ──────────
    def _sync_facts(self, site, values):
        existing = {(f.section, f.key): f for f in site.facts.all()}
        defined = {(d['section'], d['key']) for d in FACT_DEFS}
        # 정의에서 빠진 항목(구 '일정 및 계획' 등)은 정리한다
        for pair, fact in existing.items():
            if pair not in defined:
                fact.delete()
        for order, d in enumerate(FACT_DEFS):
            section, key, label = d['section'], d['key'], d['label']
            fact = existing.get((section, key))
            seeded = values.get((section, key))
            if fact is None:
                value, certainty, source, note = seeded or ('', 'unconfirmed', '', '')
                SiteFact.objects.create(
                    site=site, section=section, key=key, label=label, value=value,
                    certainty=certainty, source=source, note=note, sort_order=order)
            else:
                # 라벨·순서는 정의를 따르고, 값은 비어 있을 때만 시드로 채운다
                fact.label, fact.sort_order = label, order
                if seeded and not fact.value:
                    fact.value, fact.certainty, fact.source, fact.note = seeded
                fact.save()

    # ── 인허가: 정의 10항목 골격 + 시드 값 ────────────────────────────
    def _sync_permits(self, site, values):
        defined_names = {d['name'] for d in STAGE_DEFS}
        # 정의에서 빠진 구(舊) 항목 정리 — 문서가 붙어 있으면 남긴다
        for stage in site.stages.exclude(name__in=defined_names):
            if not stage.documents.exists():
                stage.delete()

        # 남은 항목을 임시 번호대로 밀어 둔다. 그러지 않으면 새 번호를 매기는
        # 도중에 UNIQUE(site, stage_no) 가 충돌한다(구 12항목 ↔ 신 10항목).
        leftovers = list(site.stages.all())
        for i, stage in enumerate(leftovers):
            stage.stage_no = 900 + i
        PermitStage.objects.bulk_update(leftovers, ['stage_no'])

        for d in STAGE_DEFS:
            seeded = values.get(d['name'])
            defaults = {
                'stage_no': d['stage_no'], 'category': d['category'],
                'agency': d['agency'], 'doc_label': d['doc_label'],
                'tier': 'major' if d['category'] == 'statutory' else 'minor',
            }
            stage, created = PermitStage.objects.get_or_create(
                site=site, name=d['name'], defaults=defaults)
            for field, val in defaults.items():
                setattr(stage, field, val)
            if seeded and not stage.content:
                stage.status, stage.content, stage.certainty, stage.remark = seeded
            stage.progress_pct = 100 if stage.status == 'done' else 0
            stage.save()

    # ── 계약·경과·예산: 비어 있을 때만 채운다(사용자 편집 보존) ─────────
    def _fill_once(self, site, slug):
        if not site.contracts.exists():
            Contract.objects.bulk_create([
                Contract(site=site, category=cat, counterparty=party, summary=summary,
                         certainty=certainty, status=status, note=note, sort_order=i)
                for i, (cat, party, summary, certainty, status, note)
                in enumerate(sd.CONTRACTS.get(slug, []))
            ])
        if not site.events.exists():
            SiteEvent.objects.bulk_create([
                SiteEvent(site=site, event_date=_resolve_date(d), event_type=etype,
                          summary=summary, certainty=certainty)
                for (d, etype, summary, certainty) in sd.EVENTS.get(slug, [])
            ])
        if not site.budget_entries.exists():
            BudgetEntry.objects.bulk_create([
                BudgetEntry(site=site, category=cat, amount_krw=amount,
                            exec_date=exec_date, memo=memo)
                for (cat, amount, exec_date, memo) in sd.BUDGETS.get(slug, [])
            ])
        # 구 이슈(CommunityIssue)는 진행경과(SiteEvent)로 대체됐다 — 남아 있으면 이관
        for issue in site.issues.all():
            SiteEvent.objects.get_or_create(
                site=site, summary=issue.title,
                defaults={'event_date': issue.issue_date,
                          'event_type': {'complaint': 'complaint', 'grid': 'permit'}
                          .get(issue.issue_type, 'etc'),
                          'certainty': 'confirmed'})
            issue.delete()


def SITES_iter():
    return sd.SITES
