# RES AI Agent

재생에너지(태양광) 사업개발실 사내 RAG 챗봇.
사내 문서를 근거로 답하고, 답변마다 원문 출처를 함께 제시한다.

---

## ⚠️ 이 저장소에는 코드만 있다

**클론만으로는 동작하지 않는다.** 아래 넷은 의도적으로 제외되어 있다.

| 제외 대상 | 크기 | 없으면 |
|---|---|---|
| `backend/media/` — 사내 문서 원본 | ~2.6GB | 출처 열람·재적재 불가 |
| `.env` — API 키·SECRET_KEY | — | **기동 즉시 중단** |
| 리랭커 모델 (`.ov_reranker_*`, `.onnx_reranker`) | ~4.9GB | 로컬에서 재생성 필요 |
| PostgreSQL·Qdrant 데이터 | — | **코퍼스는 DB에 있다. git으로 옮겨지지 않는다** |

마지막 항목이 핵심이다. 코드를 되돌려도(`git checkout`) **이미 적재된 청크는 바뀌지 않는다.**
청킹 로직을 바꿨다면 재적재를 따로 실행해야 반영된다.

---

## 구성

| 계층 | 기술 | 포트 |
|---|---|---|
| 프론트엔드 | React 18 · TypeScript · Vite | 5173 |
| 백엔드 | Django 5 · Django REST Framework | 8000 |
| 벡터 DB | Qdrant (dense 1024 + sparse 하이브리드) | 6333 |
| 메타 DB | PostgreSQL 16 | 5432 |
| 큐 | Redis · Celery | 6379 |
| 임베딩 | BGE-M3 (로컬 CPU) | — |
| 리랭커 | bge-reranker-v2-m3 (OpenVINO INT8) | — |
| 생성 | OpenAI API | — |

본문은 Postgres에, 벡터는 Qdrant에 나눠 저장한다.
Qdrant payload에 본문을 넣지 않아 메모리 사용량을 낮췄다.

---

## 설치

### 1. 환경변수

```bash
cp .env.example .env                    # docker-compose 용
cp backend/.env.example backend/.env    # Django 용
```

`backend/.env`의 `DJANGO_SECRET_KEY`는 **필수**다. 비어 있으면 기동이 중단된다.

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

두 파일 모두에 있는 `LLM_API_BASE` / `LLM_API_KEY`는 **같은 값으로 맞춘다**.
컨테이너 환경변수가 `backend/.env`보다 우선하기 때문이다.

### 2. 원본 문서 배치

```
backend/media/initial_docs/{PJT폴더}/...
```

최상위 폴더명이 프로젝트명이 된다. 하위 경로는 출처 추적용으로만 보존된다.
지원 형식: `pdf` `docx` `xlsx` `pptx` `hwp` `hwpx` `md` `txt`

### 3. 기동

```bash
docker compose up -d
```

### 3-1. 사업개발 대시보드 초기화 (운영관리 → 사업개발 탭)

Re-project-mng 에서 이식한 사업개발 포트폴리오 대시보드(`apps/bizdev`).
테이블은 마이그레이션이, 시드(사업지 25개소)는 커맨드가 만든다:

```bash
docker exec re_backend python manage.py migrate bizdev
docker exec re_backend python manage.py seed_bizdev        # 멱등 · --wipe 로 초기화 재적재
```

- 계통(KEPCO)·법령(법제처) 데이터는 `backend/apps/bizdev/data/*.json` 스냅샷 서빙 (실시간 API 전환은 2차 — `apps/bizdev/snapshots.py` 함수만 교체)
- 인허가 12단계 정의는 `apps/bizdev/constants.py` STAGE_DEFS 단일 소스
- 권한: admin 전체 편집 / 사업지 PM(등록자) 본인 것만 편집 / 그 외 읽기. 사업지 삭제는 admin 전용

### 4. 코퍼스 적재

```bash
# 분류만 먼저 뽑아 사람이 검토 (권장)
docker exec re_backend python manage.py ingest_initial_docs --classify-only

# 검토한 CSV를 반영해 적재
docker exec re_backend python manage.py ingest_initial_docs --type-map classification.csv
```

**4번을 돌려야 실제 시스템이 된다.** 3번까지는 빈 껍데기다.

### 5. 리랭커 INT8 모델 생성 (선택, 속도 개선)

```bash
docker exec re_backend python bench_openvino.py c
```

없으면 torch 백엔드로 자동 폴백한다. 응답이 느려질 뿐 동작에는 문제없다.

---

## 자주 쓰는 명령

### 문서 한 건만 갱신 (전체 재적재 없이)

사업개요처럼 계속 손보는 문서용. 내용이 바뀐 것만 갱신한다.

```bash
# 사업개요 전체 훑어 변경분만
docker exec re_backend python manage.py refresh_doc --pattern "[사업개요]"

# 미리 확인만
docker exec re_backend python manage.py refresh_doc --pattern "[사업개요]" --dry-run

# 한 건만
docker exec re_backend python manage.py refresh_doc --file "/app/media/initial_docs/{PJT폴더}/{파일명}.md"
```

옛 문서와 그 Qdrant 벡터를 지운 뒤 새로 적재한다.
프로젝트·문서유형·원본경로는 그대로 승계한다.

### 청크 불변조건 검사

**재적재 직후 반드시 실행한다.**

```bash
docker exec re_backend python manage.py audit_chunks
docker exec re_backend python manage.py audit_chunks --fail-on-violation   # 자동화용
```

크기 상한 · 최소 길이 · 위치정보 · doc_type · 제어문자 · 문서 내 중복을 전수 검사한다.

---

## 청킹 구조

`doc_type`이 아니라 **포맷이 먼저** 라우팅을 정한다.
`page_number`의 실체가 포맷마다 다르기 때문이다 — pdf/pptx만 진짜 페이지이고,
hwp는 전부 1, docx는 인위적 순번이다.

```
① xlsx              → 시트 단위
② md · txt          → 헤딩 단위 (분류 무시)
③ report + pdf/pptx → 페이지 단위
④ admin             → 문서 전체 1청크 (페이지 없으면 구조 분할)
⑤ law               → 조문
⑥ contract          → 구조 경계 자동 선택 (제N조 / 제N장·절 / Article / Section)
⑦ report + 그 외    → 구조 먼저 시도
⑧ general           → 문단 스냅
   + 표 청크 별도 부착
──────────────────────────────────────────────────
   전부 normalize_chunks() 통과 → verify_chunk_invariants() 검사
```

`normalize_chunks()`가 **단일 출구**다. 어떤 경로로 만들어진 청크든 반드시 통과하며,
크기 상한(1,500자) · 최소 길이 · 제어문자 · 문서 내 중복 · 메타 기본값을 강제한다.
새 문서 타입을 추가할 때도 이 함수를 우회하는 경로를 만들지 말 것.

주요 파라미터는 `backend/apps/rag/chunkers.py` 상단에 모아 두었다.

---

## 검색 파이프라인

```
질문 → BGE-M3 임베딩(dense+sparse)
     → Qdrant 하이브리드 검색 (K=16)
     → 리랭킹 (조건부)
     → 중복 제거
     → 관련성 게이트 (1위 점수 < 0.55 면 '자료 없음')
     → 상위 8개 · 길이 가드
     → LLM 생성 (SSE 스트리밍)
```

관련성 게이트 임계값은 실측으로 정했다 —
답이 있는 질의의 1위 점수는 0.60~0.73, 없는 질의는 0.50~0.52로 겹치지 않는다.
정상 질문이 "자료 없음"으로 튕기면 `settings.py`의 `RAG_GATE_MIN_TOP1_*`를 먼저 낮춘다.

---

## 개발 메모

- 코드 수정은 볼륨 마운트로 즉시 반영된다. 설정 변경 시에만 `docker restart re_backend`
- 프론트엔드는 Windows 바인드 마운트라 `usePolling`으로 파일 변경을 감지한다
- `RAG_WARMUP_ON_START=False` 로 기동 시 모델 예열을 끌 수 있다 (관리 명령 실행 시 유용)
- 로그: `docker logs re_backend --tail 50`
