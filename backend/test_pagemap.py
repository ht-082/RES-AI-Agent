"""page_number 역산 검증 — 실제 문서를 파싱→청킹까지 돌려 페이지가 채워지는지 확인.

DB/Qdrant에는 쓰지 않는다.
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.chunkers import chunk_contract, chunk_general, chunk_law, chunk_report
from apps.rag.tasks import (build_text_and_page_map, page_at_offset,
                            resolve_section_title)
from services.parser import parse_file

CASES = [
    ('law', 'media/documents/전기사업법(법률)(제21438호)(20260310).pdf'),
    ('contract', 'media/documents/홍성빛나래솔라 인허가 용역계약서.docx'),
    ('report', 'media/documents/1. 홍성군 염해태양광 사업 설명자료_230724.pdf'),
    ('general', 'media/documents/마을설명회자료_260511_vF.pdf'),
]

overall = True
for doc_type, path in CASES:
    name = os.path.basename(path)
    print('=' * 74)
    print(f'[{doc_type}] {name[:56]}')
    if not os.path.exists(path):
        print('  SKIP: 파일 없음')
        continue

    items = parse_file(path)
    src_pages = sorted({i.get('page_number') for i in items if i.get('page_number')})
    print(f'  파서 추출 단위: {len(items)}개, 페이지 범위: '
          f'{min(src_pages) if src_pages else None}~{max(src_pages) if src_pages else None}')

    page_starts, page_numbers = [], []
    if doc_type == 'report':
        chunks = chunk_report(items, filename=name)
    else:
        full_text, page_starts, page_numbers = build_text_and_page_map(items)
        print(f'  합친 텍스트 길이: {len(full_text):,}자')
        if doc_type == 'contract':
            chunks = chunk_contract(full_text, filename=name)
        elif doc_type == 'law':
            chunks = chunk_law(full_text, filename=name)
        else:
            chunks = chunk_general(full_text)

    resolved, samples = [], []
    for c in chunks:
        meta = c['metadata']
        page = meta.get('page_no')
        if page is None:
            page = page_at_offset(page_starts, page_numbers, meta.get('char_start'))
        resolved.append(page)
        if len(samples) < 3 and page is not None:
            samples.append((page, resolve_section_title(meta), c['text'][:38].replace('\n', ' ')))

    filled = sum(1 for p in resolved if p is not None)
    pct = 100.0 * filled / len(resolved) if resolved else 0
    print(f'  청크 수: {len(chunks)}  |  page 채워짐: {filled}/{len(resolved)} ({pct:.1f}%)')

    # 페이지가 단조 증가하는지(오프셋 역산이 뒤죽박죽이 아닌지)
    seq = [p for p in resolved if p is not None]
    mono = all(a <= b for a, b in zip(seq, seq[1:])) if doc_type != 'report' else True
    in_range = all(p in src_pages for p in seq) if src_pages else True
    print(f'  페이지 단조증가: {mono}   |   원본 페이지 범위 내: {in_range}')
    for p, st, t in samples:
        print(f'    p.{p:<4} {st[:22]:<24} | {t}...')

    ok = pct > 90 and mono and in_range
    print(f'  => {"PASS" if ok else "FAIL"}')
    overall = overall and ok

print('=' * 74)
print(f'OVERALL={"PASS" if overall else "FAIL"}')
