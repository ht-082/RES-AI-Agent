# 로컬 DB 셋업 가이드 (baseline 복원 방식)

> 신규 개발자가 기준 개발환경(코드 + DB + 벡터)을 그대로 재현하는 절차.
> 원칙: **Docker Image = 실행환경 · PG dump = 관계형 데이터 · Qdrant snapshot = 벡터 데이터**
> — 데이터는 이미지에 넣지 않고 baseline 파일로 별도 관리한다.

## 0. 받아야 하는 것

| 경로 | 내용 |
|---|---|
| GitHub | 코드 (`git clone https://github.com/ht-082/RES-AI-Agent.git`) |
| 별도 채널 | `baseline/postgres_baseline_v1.dump` (≈11MB) + `qdrant_re_documents_v2_v1.snapshot` (≈158MB) |
| 각자 준비 | Docker Desktop · OpenAI API 키(gpt-5.6 계열) |

두 baseline 파일은 **같은 버전 라벨의 쌍**이어야 한다. 받은 파일을 리포의 `baseline/` 폴더에 둔다.
⚠ 덤프에는 사내 데이터·계정이 들어 있다 — 팀 외부 공유 금지, Git 커밋 금지.

## 1. 최초 환경 구축

```bash
git clone https://github.com/ht-082/RES-AI-Agent.git
cd RES-AI-Agent
cp .env.example .env                    # DB 계정 (기본값 그대로도 동작)
cp backend/.env.example backend/.env    # DJANGO_SECRET_KEY·LLM_API_KEY 필수 기입
```

**신규 설치는 `docker-compose.yml`의 `db/schema.sql` 마운트(20행)를 주석 처리**한다
— baseline 복원이 스키마까지 담고 있어 initdb 스크립트와 충돌한다.

```bash
docker compose up -d      # 첫 기동 시 BGE-M3(~2GB) 다운로드
```

## 2. Baseline DB 설치 (한 번에)

```bash
./scripts/setup_baseline.sh
```

순서: 컨테이너 확인 → PG/Qdrant 대기 → baseline 파일 확인 → PG 복원(확인 프롬프트)
→ Qdrant 복원 → Django 연결 확인 → 컬렉션 확인. 완료 후:

```bash
docker exec -it re_backend python manage.py createsuperuser   # 로그인 계정
```

`http://localhost:5173` 접속 — 사용법은 `docs/사용자_이용_가이드.md`.

## 3. 개별 실행

```bash
./scripts/restore_postgres.sh baseline/postgres_baseline_v1.dump     # PG만
./scripts/restore_qdrant.sh baseline/qdrant_re_documents_v2_v1.snapshot [--force]  # Qdrant만
```

restore 는 대상 DB·기존 데이터 유무를 보여주고 **DB명/컬렉션명을 직접 입력해야** 진행된다.
기존 컬렉션이 있으면 `--force` 없이는 중단된다.

## 4. 새 Baseline 생성 (기준 PC에서)

```bash
./scripts/backup_postgres.sh v2
./scripts/backup_qdrant.sh re_documents_v2 v2    # 반드시 연달아 실행 (같은 시점 쌍)
```

둘 다 read-only 라 실행 중인 DB에 영향이 없다. 산출물은 별도 채널로 전달.

## 5. 상태 확인

```bash
docker compose ps                                     # 컨테이너 6개 Up 확인
docker exec re_postgres psql -U re_user -d re_agent -c "select count(*) from document_chunks;"
curl -s http://localhost:6333/collections             # 컬렉션 목록
curl -s http://localhost:6333/collections/re_documents_v2 | grep -o '"points_count":[0-9]*'
```

기대값(v1 baseline): chunks **18,823** · points **18,823** (둘이 같아야 정상).

## 6. 문제 발생 시 초기화 (⚠ 파괴적 — 신규 개발 PC에서만)

복원이 꼬였을 때 로컬 환경을 백지로 되돌리는 방법이다.

```bash
# ⚠⚠ 아래는 로컬 DB·벡터를 전부 삭제한다. 기준 데이터를 보유한 PC에서는 절대 금지.
docker compose down
docker volume rm resaiagentdevelop_pg_data resaiagentdevelop_qdrant_data
docker compose up -d
./scripts/setup_baseline.sh
```

`docker compose down -v` 는 **모든 볼륨(모델 캐시 포함)**을 지우므로 쓰지 않는다.

## 7. 관련 문서

- 협업 규칙(파일 소유·커밋 규율): `docs/협업_작업규칙.md`
- 전체 아키텍처·설계 결정: `docs/프로젝트_현황_요약.md`
- 코퍼스만 선별 이식(구버전 방식): `docs/이관_구동_가이드.md` — baseline 방식이 이를 대체한다
