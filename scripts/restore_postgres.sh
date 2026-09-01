#!/usr/bin/env bash
# PostgreSQL baseline 복원 — ⚠ 대상 DB의 기존 객체를 덮어쓴다(--clean).
# 신규/빈 로컬 DB 전용. 데이터가 있는 DB에서는 실행하지 말 것.
# 사용: ./scripts/restore_postgres.sh baseline/postgres_baseline_v1.dump
. "$(dirname "$0")/_common.sh"

DUMP="${1:-}"
[ -n "$DUMP" ] && [ -f "$DUMP" ] || { echo "사용법: $0 <dump파일>  (baseline/*.dump)"; exit 1; }

need_container "$PG_CONTAINER"
pg_ready || { echo "✗ PostgreSQL이 준비되지 않았습니다"; exit 1; }

# 복원 대상을 명확히 보여준다 — 실수로 다른 DB를 지우는 것을 막는 핵심 절차
DOCS=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$PGDB" -t -A \
       -c "select count(*) from information_schema.tables where table_schema='public'" 2>/dev/null || echo "?")
echo "┌──────────────────────────────────────────────"
echo "│ 복원 대상   : db=$PGDB · user=$PGUSER · container=$PG_CONTAINER"
echo "│ 현재 테이블 : ${DOCS}개"
echo "│ 덤프 파일   : $DUMP ($(du -h "$DUMP" | cut -f1))"
echo "│ ⚠ --clean --if-exists 로 기존 객체를 삭제 후 재생성합니다."
echo "└──────────────────────────────────────────────"
if [ "${DOCS}" != "0" ] && [ "${DOCS}" != "?" ]; then
  echo "⚠⚠ 이 DB에는 이미 테이블 ${DOCS}개가 있습니다. 기준 개발 PC라면 절대 진행하지 마세요."
fi
confirm "위 DB를 덤프 내용으로 교체합니다." "$PGDB"

# --no-owner: 덤프 생성자와 복원 사용자가 달라도 동작
docker exec -i "$PG_CONTAINER" pg_restore -U "$PGUSER" -d "$PGDB" \
  --clean --if-exists --no-owner < "$DUMP"

AFTER=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$PGDB" -t -A \
        -c "select count(*) from information_schema.tables where table_schema='public'")
echo "✓ 복원 완료 — public 테이블 ${AFTER}개"
docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$PGDB" -t -A \
  -c "select 'documents='||count(*) from documents" 2>/dev/null || true
