#!/usr/bin/env bash
# PostgreSQL baseline 백업 (read-only — 기존 DB를 변경하지 않는다)
# 사용: ./scripts/backup_postgres.sh [버전라벨]   예) v1  (생략 시 v날짜)
. "$(dirname "$0")/_common.sh"

VERSION="${1:-v$(date +%Y%m%d)}"
OUT="baseline/postgres_baseline_${VERSION}.dump"

need_container "$PG_CONTAINER"
pg_ready || { echo "✗ PostgreSQL이 준비되지 않았습니다"; exit 1; }

echo "▶ pg_dump (custom format): db=$PGDB user=$PGUSER → $OUT"
mkdir -p baseline
docker exec "$PG_CONTAINER" pg_dump -U "$PGUSER" -d "$PGDB" -Fc > "$OUT"

# 무결성 확인: 아카이브 목차가 읽히면 정상
COUNT=$(docker exec -i "$PG_CONTAINER" pg_restore --list < "$OUT" | grep -c "TABLE DATA" || true)
SIZE=$(du -h "$OUT" | cut -f1)
echo "✓ 완료: $OUT ($SIZE, TABLE DATA ${COUNT}개)"
echo "  ⚠ 이 파일은 Git에 커밋하지 않습니다(.gitignore 등록됨). 별도 채널로 전달하세요."
