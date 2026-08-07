"""적재된 코퍼스 전체의 청크 불변조건을 검사한다.

재적재 직후 반드시 돌린다. v1에서는 이 검사가 없어, 초과 청크 301개(최대 138,570자)와
표 중복 285건이 몇 달간 조용히 남아 있었다.

사용:
  python manage.py audit_chunks
  python manage.py audit_chunks --fail-on-violation   # CI/스크립트용 (위반 시 exit 1)
"""
import re
from collections import Counter

from django.core.management.base import BaseCommand

from apps.documents.models import DocumentChunk
from apps.rag.chunkers import MAX_SEG_CHARS, DISCARD_UNDER, _CONTROL_CHARS


class Command(BaseCommand):
    help = '적재된 청크의 크기·메타·중복 불변조건을 전수 검사한다.'

    def add_arguments(self, parser):
        parser.add_argument('--fail-on-violation', action='store_true',
                            help='위반이 있으면 종료코드 1 (자동화용)')
        parser.add_argument('--limit-samples', type=int, default=5,
                            help='항목별 위반 사례 출력 수')

    def handle(self, *args, **options):
        n = DocumentChunk.objects.count()
        if n == 0:
            self.stdout.write(self.style.WARNING('청크가 없습니다.'))
            return
        self.stdout.write(f'검사 대상 청크 {n:,}개\n')

        k = options['limit_samples']
        results = []

        # ① 크기 상한
        over = DocumentChunk.objects.extra(
            where=[f'LENGTH(content) > {MAX_SEG_CHARS}'])
        results.append(('크기 초과', over.count(),
                        [f'{c.document.title[:34]} — {len(c.content):,}자'
                         for c in over.order_by()[:k]]))

        # ② 최소 길이
        short = DocumentChunk.objects.extra(
            where=[f'LENGTH(TRIM(content)) < {DISCARD_UNDER}'])
        results.append(('길이 부족', short.count(),
                        [f'{c.document.title[:34]} — {len(c.content.strip())}자'
                         for c in short[:k]]))

        # ③ 위치 정보
        noloc = DocumentChunk.objects.filter(page_number__isnull=True, char_start__isnull=True)
        results.append(('위치정보 없음', noloc.count(),
                        [c.document.title[:44] for c in noloc[:k]]))

        # ④ doc_type
        notype = [c for c in DocumentChunk.objects.only('id', 'metadata', 'document')
                  if not (c.metadata or {}).get('doc_type')]
        results.append(('doc_type 없음', len(notype),
                        [c.document.title[:44] for c in notype[:k]]))

        # ⑤ 제어문자
        ctrl = [c for c in DocumentChunk.objects.only('id', 'content', 'document')
                if _CONTROL_CHARS.search(c.content or '')]
        results.append(('제어문자 포함', len(ctrl),
                        [c.document.title[:44] for c in ctrl[:k]]))

        # ⑥ 같은 문서 내 내용 중복
        dup_total, dup_samples = 0, []
        seen_docs = Counter()
        for doc_id, content in DocumentChunk.objects.values_list('document_id', 'content'):
            key = (doc_id, re.sub(r'\s+', ' ', content or '').strip())
            if not key[1]:
                continue
            seen_docs[key] += 1
        for (doc_id, _), cnt in seen_docs.items():
            if cnt > 1:
                dup_total += cnt - 1
                if len(dup_samples) < k:
                    from apps.documents.models import Document
                    t = Document.objects.filter(id=doc_id).values_list('title', flat=True).first()
                    dup_samples.append(f'{(t or "?")[:34]} — {cnt}회 반복')
        results.append(('같은 문서 내 중복', dup_total, dup_samples))

        # ── 출력 ────────────────────────────────────────────────────
        total = 0
        self.stdout.write(f'{"항목":<20}{"위반":>8}')
        self.stdout.write('-' * 46)
        for name, count, samples in results:
            total += count
            style = self.style.SUCCESS if count == 0 else self.style.ERROR
            self.stdout.write(style(f'{name:<20}{count:>8,}'))
            for s in samples:
                self.stdout.write(f'    · {s}')

        self.stdout.write('-' * 46)
        if total == 0:
            self.stdout.write(self.style.SUCCESS('불변조건 위반 없음 ✅'))
        else:
            self.stdout.write(self.style.ERROR(f'총 위반 {total:,}건'))
            if options['fail_on_violation']:
                raise SystemExit(1)
