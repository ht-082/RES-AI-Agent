"""청킹 파이프라인 감사 (읽기 전용)

실제 적재 문서를 대상으로 파싱→분류→청킹을 메모리에서 다시 돌려 4가지를 점검한다.
DB/Qdrant에 아무것도 쓰지 않는다.

  1) 분류 정확도  : 규칙 판정 vs 저장된 doc_type
  2) 폴백 발생    : law/contract인데 제N조를 못 찾아 general로 떨어진 문서
  3) 파서 노이즈  : 여러 페이지에 반복 등장하는 머리말/꼬리말
  4) page_number  : 청크별 페이지 역산 커버리지

실행: docker exec re_backend python test_chunking_audit.py
"""
import os
import re
from collections import Counter, defaultdict

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.documents.models import Document
from apps.rag.chunkers import chunk_contract, chunk_general, chunk_law, chunk_report
from apps.rag.management.commands.ingest_initial_docs import (extract_head_text,
                                                              rule_based_classify)
from apps.rag.tasks import build_text_and_page_map, page_at_offset, resolve_section_title
from services.parser import parse_file


def resolve_path(doc):
    name = os.path.basename(doc.storage_uri)
    p = os.path.join('media', 'documents', name)
    if os.path.exists(p):
        return p
    for root, _, files in os.walk(os.path.join('media', 'initial_docs')):
        if name in files:
            return os.path.join(root, name)
    return None


def detect_noise(items, min_repeat_ratio=0.6):
    """여러 페이지에 반복 등장하는 짧은 줄 = 머리말/꼬리말 후보"""
    if len(items) < 3:
        return []
    counter = Counter()
    for it in items:
        seen = set()
        for line in (it.get('text') or '').split('\n'):
            s = line.strip()
            # 쪽번호처럼 숫자만 바뀌는 줄은 숫자를 지워 정규화
            norm = re.sub(r'\d+', '#', s)
            if 3 <= len(norm) <= 60 and norm not in seen:
                seen.add(norm)
                counter[norm] += 1
    threshold = max(2, int(len(items) * min_repeat_ratio))
    return [(t, c) for t, c in counter.most_common(4) if c >= threshold]


docs = list(Document.objects.filter(status='indexed').order_by('doc_type', 'original_filename'))
print(f'감사 대상: {len(docs)}건 (status=indexed)')
print('=' * 78)

cls_match = cls_mismatch = cls_norule = 0
fallbacks = []
noise_hits = []
page_stats = []
size_by_type = defaultdict(list)
rows = []

for doc in docs:
    path = resolve_path(doc)
    if not path:
        rows.append((doc.original_filename, doc.doc_type, '파일없음', '-', 0, 0.0))
        continue

    try:
        items = parse_file(path) or []
    except Exception as e:
        rows.append((doc.original_filename, doc.doc_type, f'파싱실패', '-', 0, 0.0))
        continue
    if not items:
        rows.append((doc.original_filename, doc.doc_type, '텍스트없음', '-', 0, 0.0))
        continue

    ext = (doc.file_type or '').lower()

    # --- 1) 분류: 규칙이 뭐라고 하는가 ---
    # 실제 수집 명령과 동일한 입력을 써야 한다. parse_file 결과를 넣으면
    # 스캔본(Vision 파서)에서 결과가 달라져 없는 불일치가 만들어진다.
    guessed, _note = rule_based_classify(extract_head_text(path, ext), ext)
    if guessed is None:
        verdict = '규칙없음(LLM판정)'
        cls_norule += 1
    elif guessed == doc.doc_type:
        verdict = '일치'
        cls_match += 1
    else:
        verdict = f'불일치(규칙:{guessed})'
        cls_mismatch += 1

    # --- 실제 청킹 경로 재현 ---
    page_starts, page_numbers = [], []
    if doc.doc_type == 'report':
        chunks = chunk_report(items, filename=doc.title)
    else:
        full_text, page_starts, page_numbers = build_text_and_page_map(items)
        if doc.doc_type == 'contract':
            chunks = chunk_contract(full_text, filename=doc.title)
        elif doc.doc_type == 'law':
            chunks = chunk_law(full_text, filename=doc.title)
        else:
            chunks = chunk_general(full_text)

    # --- 2) 폴백: law/contract인데 general 청커로 떨어졌는가 ---
    fell_back = (doc.doc_type in ('law', 'contract') and chunks
                 and chunks[0].get('metadata', {}).get('doc_type') == 'general')
    if fell_back:
        fallbacks.append((doc.original_filename, doc.doc_type, len(chunks)))

    # --- 4) page_number 역산 커버리지 ---
    resolved = []
    for c in chunks:
        m = c['metadata']
        pg = m.get('page_no')
        if pg is None:
            pg = page_at_offset(page_starts, page_numbers, m.get('char_start'))
        resolved.append(pg)
        size_by_type[doc.doc_type].append(len(c['text']))
    cov = 100.0 * sum(1 for p in resolved if p is not None) / len(resolved) if resolved else 0.0
    page_stats.append(cov)

    # --- 3) 파서 노이즈 ---
    for txt, cnt in detect_noise(items):
        noise_hits.append((doc.original_filename[:34], txt[:40], cnt, len(items)))

    rows.append((doc.original_filename, doc.doc_type, verdict,
                 'FALLBACK' if fell_back else '-', len(chunks), cov))

# ───────────── 출력 ─────────────
print(f'{"파일":<40} {"유형":<9} {"분류검증":<18} {"폴백":<9} {"청크":>5} {"page%":>6}')
print('-' * 78)
for name, dt, verdict, fb, n, cov in rows:
    print(f'{name[:39]:<40} {dt:<9} {verdict:<18} {fb:<9} {n:>5} {cov:>5.0f}%')

print()
print('=' * 78)
print(' 1) 분류 정확도')
print('=' * 78)
total_cls = cls_match + cls_mismatch
print(f'  규칙-저장 일치   : {cls_match}건')
print(f'  규칙-저장 불일치 : {cls_mismatch}건   <-- 0이 아니면 규칙이 흔들린다는 뜻')
print(f'  규칙 미적용(LLM) : {cls_norule}건   <-- 많으면 규칙 커버리지가 낮다는 뜻')
if total_cls:
    print(f'  규칙 적용분 일치율: {cls_match / total_cls * 100:.1f}%')

print()
print('=' * 78)
print(' 2) 조항 정규식 폴백 (조용한 실패)')
print('=' * 78)
if fallbacks:
    for name, dt, n in fallbacks:
        print(f'  !! {dt:<9} {name[:50]} -> general 800자 분할 ({n}청크)')
    print(f'  합계: {len(fallbacks)}건')
else:
    print('  없음 — law/contract 전부 조항 단위로 정상 분할됨')

print()
print('=' * 78)
print(' 3) 파서 노이즈 (여러 페이지 반복 = 머리말/꼬리말 의심)')
print('=' * 78)
if noise_hits:
    print(f'  {"문서":<36} {"반복 문자열":<42} {"빈도"}')
    for name, txt, cnt, total in noise_hits[:12]:
        print(f'  {name:<36} {txt!r:<42} {cnt}/{total}p')
    print(f'  ...총 {len(noise_hits)}건 (# 은 숫자 자리)')
else:
    print('  탐지된 반복 문자열 없음')

print()
print('=' * 78)
print(' 4) page_number 역산 + 청크 크기')
print('=' * 78)
if page_stats:
    full = sum(1 for c in page_stats if c >= 99.9)
    print(f'  page 100% 문서: {full}/{len(page_stats)}건 | 평균 커버리지 {sum(page_stats) / len(page_stats):.1f}%')
for dt, sizes in sorted(size_by_type.items()):
    sizes.sort()
    n = len(sizes)
    med = sizes[n // 2]
    tiny = sum(1 for s in sizes if s < 100)
    print(f'  {dt:<9} 청크 {n:>5} | 중앙 {med:>5}자 | 최소 {sizes[0]:>4} | 최대 {sizes[-1]:>5} | '
          f'100자미만 {tiny:>4}건({tiny / n * 100:.0f}%)')
print('DONE')
