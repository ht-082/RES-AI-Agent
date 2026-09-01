# Baseline v1 (2026-09-01)

PG 덤프와 Qdrant 스냅샷은 **같은 시점의 쌍**이다. 버전 라벨이 같은 것끼리만 사용한다.
파일명 규약: `postgres_baseline_<버전>.dump` · `qdrant_<컬렉션>_<버전>.snapshot`
⚠ 이 폴더의 덤프·스냅샷은 Git에 커밋하지 않는다(.gitignore 등록). 별도 채널로 전달.

## PostgreSQL — `postgres_baseline_v1.dump`
- DB name: `re_agent` (PostgreSQL 16.14, custom format `-Fc`)
- 내용: **전체 DB** (스키마 + 데이터, django_migrations 포함 → 복원 후 migrate 불필요)
- schema version (최신 적용): `workspaces.0002_align_created_by_columns` ·
  `contracts.0003_align_created_by_columns` · `bizdev.0001_initial` · `documents.0007`
- 주요 데이터: documents 673행(v1 270 + v2 403) · document_chunks(v2) 18,823 ·
  bizdev 시드(사업지 25) · 사용자 계정 포함 ⚠(팀 외부 전달 금지)

## Qdrant — `qdrant_re_documents_v2_v1.snapshot`
- collection name: `re_documents_v2` (활성 코퍼스)
- vector: dense **1024d / Cosine** (BGE-M3) + sparse(`sparse`) 하이브리드
- point count: **18,823**
- v1 컬렉션(`re_documents`, 10,777pt)은 롤백 전용이라 baseline에 포함하지 않음.
  PG 덤프에는 v1 문서 행이 있으나 벡터가 없어 검색되지 않는다(정상).

## RAG 파이프라인 (이 baseline 을 만든 설정)
- embedding model: `BAAI/bge-m3` (로컬 CPU, dense+sparse)
- chunking 방식: 문서 유형별 규칙 기반 — 계약서=조·항 경계 / 법령=조문 /
  markdown=헤딩 / 표=행렬 보존 (backend/apps/rag/chunkers.py)
- chunk size: 상한 1,500자(MAX_SEG) · 하위분할 1,200자(SUB_CHUNK) · 최소 병합 300자
- overlap: 150자 (하위분할 시)
- 임베딩 입력에 컨텍스트 헤더 `[사업: X] [문서: Y]` 주입 (md/txt 제외)
- reranker: `BAAI/bge-reranker-v2-m3` OpenVINO INT8, max_length 384

## 새 baseline 만들기
```bash
./scripts/backup_postgres.sh v2
./scripts/backup_qdrant.sh re_documents_v2 v2   # 반드시 연달아(같은 시점) 실행
```
