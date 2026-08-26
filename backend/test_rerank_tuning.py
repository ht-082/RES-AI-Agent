"""리랭커 K / max_length 튜닝 측정

**재적재·재청킹 후에 반드시 다시 돌릴 것.**
max_length는 청크 토큰 길이에 직접 종속되므로, 청킹을 바꾸면 최적값이 달라진다.
그대로 두면 청크가 커졌을 때 대부분이 잘려 리랭킹 품질이 조용히 떨어진다.

실행: docker exec re_backend python test_rerank_tuning.py

출력 해석:
  1) 토큰 분포  → max_length 후보 선정 (잘림 비율이 수용 가능한 최소값)
  2) 시간 측정  → 선택한 후보의 실제 비용
  3) 순위 일치도 → 낮은 max_length가 순위를 바꾸지 않으면 그 값을 써도 안전
"""
import os
import time

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

from apps.documents.models import DocumentChunk
from services.retriever import ExistingQdrantRetriever, get_reranker

QUERIES = [
    '홍성 염해태양광 사업의 발전 용량은 얼마인가?',
    '발전사업 허가를 받으려면 어떤 절차를 거쳐야 하는가?',
    '인허가 용역계약서의 대금 지급 조건은?',
    '집적화단지 조성 지원 기준은 무엇인가?',
]
CANDIDATES = [128, 256, 384, 512, 768]

model = get_reranker()
tok = model.client.tokenizer

print('=' * 70)
print(' 1) 청크 토큰 분포 (무작위 표본) — max_length 후보 선정용')
print('=' * 70)
rows = list(DocumentChunk.objects.exclude(content='').order_by('?')
            .values_list('content', 'metadata')[:300])
if not rows:
    raise SystemExit('청크가 없습니다. 먼저 문서를 적재하세요.')

lens = [len(tok.encode(QUERIES[0], c)) for c, _ in rows]
lens.sort()
n = len(lens)
pick = lambda p: lens[min(n - 1, int(n * p / 100))]
print(f'  표본 {n}건 | 중앙 {pick(50)} | 90% {pick(90)} | 95% {pick(95)} | 최대 {lens[-1]}')
for ml in CANDIDATES:
    cut = sum(1 for x in lens if x > ml)
    print(f'    max_length={ml:4d} -> 잘림 {cut:3d}/{n} ({cut / n * 100:4.1f}%)')

print()
print('=' * 70)
print(' 2) max_length별 리랭킹 시간 + 3) 순위 일치도 (기준: 가장 큰 값)')
print('=' * 70)
retriever = ExistingQdrantRetriever(project_id=None, top_k=settings.RAG_RETRIEVE_K)
print(f'  현재 설정: RAG_RETRIEVE_K={settings.RAG_RETRIEVE_K}, '
      f'RERANK_MAX_LENGTH={settings.RERANK_MAX_LENGTH}, '
      f'RAG_MAX_CONTEXT_K={settings.RAG_MAX_CONTEXT_K}')

docsets = [(q, retriever.invoke(q)) for q in QUERIES]
model.score([(QUERIES[0], 'warmup')])  # 워밍업

baseline = {}
for ml in sorted(CANDIDATES, reverse=True):
    model.client.max_seq_length = ml
    total, agree_top1, agree_top8, cnt = 0.0, 0, 0, 0
    for q, docs in docsets:
        pairs = [(q, d.page_content) for d in docs]
        t0 = time.time()
        scores = model.score(pairs)
        total += time.time() - t0
        order = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
        if ml == max(CANDIDATES):
            baseline[q] = order
        else:
            base = baseline[q]
            if base and order and base[0] == order[0]:
                agree_top1 += 1
            k = min(settings.RAG_MAX_CONTEXT_K, len(order))
            agree_top8 += len(set(base[:k]) & set(order[:k])) / max(k, 1)
        cnt += 1
    if ml == max(CANDIDATES):
        print(f'  max_length={ml:4d} | {total / cnt:6.2f}초/질의 | (기준선)')
    else:
        print(f'  max_length={ml:4d} | {total / cnt:6.2f}초/질의 | '
              f'top1 일치 {agree_top1}/{cnt} | 상위{settings.RAG_MAX_CONTEXT_K} 겹침 '
              f'{agree_top8 / cnt * 100:5.1f}%')

model.client.max_seq_length = settings.RERANK_MAX_LENGTH
print()
print('판단 기준: 상위K 겹침이 100%에 가까우면 그 max_length로 낮춰도 품질 손실이 없다.')
print('DONE')
