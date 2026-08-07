"""OpenVINO 리랭커 벤치 (독립 실행 — Django/Qdrant 불필요, 메모리 안전형)

설계 (이전 OOM 교훈 반영):
  - 후보쌍은 .bench_pairs.json에서 읽는다 (사전 덤프)
  - 모델을 한 번에 하나씩만 로드하고, 단계 사이에 완전히 해제한다
  - 기준(PyTorch FP32) 점수는 JSON으로 저장해 이후 단계와 비교한다

단계: [A] torch FP32 기준 → [B] OpenVINO FP32 → [C] OpenVINO INT8(가중치 압축)
품질 게이트: top1 전부 일치 + 상위8 겹침 95%↑ (기존 튜닝과 동일 기준)

실행: docker exec re_backend python bench_openvino.py [단계: all|a|b|c]
"""
import gc
import json
import os
import statistics
import sys
import time

os.environ.setdefault('HF_HUB_DISABLE_SSL_VERIFICATION', '1')

import numpy as np

MODEL_ID = 'BAAI/bge-reranker-v2-m3'
PAIRS_FILE = '.bench_pairs.json'
BASELINE_FILE = '.bench_baseline_scores.json'
OV_INT8_DIR = '.ov_reranker_int8'
MAX_LEN = 384
CTX_K = 8
REPEAT = 3

datasets = json.load(open(PAIRS_FILE, encoding='utf-8'))
print(f'후보: 질의 {len(datasets)}개 × 문서 {len(datasets[0]["docs"])}개')


def bench(score_fn):
    """질의별 (중앙값 시간, 점수배열) 측정"""
    out = []
    for item in datasets:
        pairs = [(item['q'], d) for d in item['docs']]
        score_fn(pairs[:2])  # 워밍업
        times = []
        for _ in range(REPEAT):
            t0 = time.time()
            scores = score_fn(pairs)
            times.append(time.time() - t0)
        out.append((statistics.median(times), np.asarray(scores, dtype=float)))
    return out


def report(label, results, baseline):
    sec = sum(t for t, _ in results) / len(results)
    if baseline is None:
        print(f'  {label:<34} {sec:6.2f}초/질의  (기준)')
        return sec
    top1 = ov_sum = 0
    for (_, s), b in zip(results, baseline):
        bo, so = list(np.argsort(-np.asarray(b))), list(np.argsort(-s))
        top1 += bo[0] == so[0]
        ov_sum += len(set(bo[:CTX_K]) & set(so[:CTX_K])) / CTX_K
    ov = ov_sum / len(results)
    ok = top1 == len(results) and ov >= 0.95
    print(f'  {label:<34} {sec:6.2f}초/질의  top1 {top1}/{len(results)}  '
          f'상위{CTX_K}겹침 {ov*100:5.1f}%  {"✅ 게이트 통과" if ok else "❌"}')
    return sec


stage = (sys.argv[1] if len(sys.argv) > 1 else 'all').lower()

# ── [A] PyTorch FP32 기준 ──────────────────────────────────────────
if stage in ('all', 'a'):
    print('\n[A] PyTorch FP32 (기준 점수 저장)')
    import torch
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(MODEL_ID, max_length=MAX_LEN)
    torch.set_num_threads(9)
    res = bench(lambda pairs: m.predict(pairs, batch_size=len(pairs)))
    report('torch FP32 (현행)', res, None)
    json.dump([s.tolist() for _, s in res], open(BASELINE_FILE, 'w'))
    del m
    gc.collect()

baseline = (json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else None)

def export_ov(save_dir, int8):
    """optimum-intel로 로컬 IR 내보내기.

    sentence-transformers에 모델 ID를 주면 허브 저장소 목록을 온라인 조회하다
    실패/지연할 수 있다(실측). 로컬 디렉토리를 주면 허브 호출이 아예 없다.
    """
    if os.path.exists(os.path.join(save_dir, 'openvino_model.xml')):
        return
    print(f'  IR 내보내는 중 → {save_dir} (int8={int8})...')
    t0 = time.time()
    from optimum.intel import OVModelForSequenceClassification
    from transformers import AutoTokenizer
    kwargs = {'export': True}
    if int8:
        kwargs['load_in_8bit'] = True
    ov = OVModelForSequenceClassification.from_pretrained(MODEL_ID, **kwargs)
    ov.save_pretrained(save_dir)
    AutoTokenizer.from_pretrained(MODEL_ID).save_pretrained(save_dir)
    del ov
    gc.collect()
    print(f'  완료 ({time.time()-t0:.0f}초)')


def run_ov_stage(label, save_dir, int8):
    export_ov(save_dir, int8)
    binf = os.path.join(save_dir, 'openvino_model.bin')
    print(f'  IR 크기: {os.path.getsize(binf)/1e6:.0f}MB')
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(save_dir, max_length=MAX_LEN, backend='openvino')
    res = bench(lambda pairs: m.predict(pairs, batch_size=len(pairs)))
    report(label, res, baseline)
    del m
    gc.collect()


# ── [B] OpenVINO FP32 ──────────────────────────────────────────────
if stage in ('all', 'b'):
    print('\n[B] OpenVINO FP32 (런타임 교체 효과)')
    run_ov_stage('OpenVINO FP32', '.ov_reranker_fp32', int8=False)

# ── [C] OpenVINO INT8 ──────────────────────────────────────────────
if stage in ('all', 'c'):
    print('\n[C] OpenVINO INT8 (가중치 압축)')
    run_ov_stage('OpenVINO INT8(w8)', OV_INT8_DIR, int8=True)

print('\nDONE')
