#!/usr/bin/env bash
# Qdrant 스냅샷 복원 — 컬렉션이 이미 있으면 중단한다(--force 로만 덮어씀).
# 사용: ./scripts/restore_qdrant.sh baseline/qdrant_re_documents_v2_v1.snapshot [--force]
. "$(dirname "$0")/_common.sh"

SNAP="${1:-}"
FORCE="${2:-}"
[ -n "$SNAP" ] && [ -f "$SNAP" ] || { echo "사용법: $0 <snapshot파일> [--force]"; exit 1; }

# 파일명 규약 qdrant_<컬렉션>_<버전>.snapshot 에서 컬렉션명 추출
BASE=$(basename "$SNAP" .snapshot)
COLLECTION=$(echo "$BASE" | sed -E 's/^qdrant_(.+)_v[^_]+$/\1/')
[ "$COLLECTION" != "$BASE" ] || { echo "✗ 파일명에서 컬렉션명을 못 읽었습니다 (규약: qdrant_<컬렉션>_<버전>.snapshot)"; exit 1; }

need_container "re_qdrant"
qdrant_ready || { echo "✗ Qdrant가 준비되지 않았습니다"; exit 1; }

EXIST=$(curl -s -o /dev/null -w "%{http_code}" "$QDRANT_URL_HOST/collections/$COLLECTION")
if [ "$EXIST" = "200" ]; then
  POINTS=$(curl -s "$QDRANT_URL_HOST/collections/$COLLECTION" | python -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])")
  echo "⚠ 컬렉션 '$COLLECTION' 이 이미 있습니다 (points=$POINTS)."
  if [ "$FORCE" != "--force" ]; then
    echo "  기존 데이터를 보존하기 위해 중단합니다. 덮어쓰려면 --force 를 붙이세요."
    exit 1
  fi
  confirm "기존 컬렉션 '$COLLECTION' (points=$POINTS) 을 스냅샷 내용으로 교체합니다." "$COLLECTION"
fi

echo "▶ 스냅샷 업로드: $SNAP → $COLLECTION ($(du -h "$SNAP" | cut -f1))"
curl -sf -X POST "$QDRANT_URL_HOST/collections/$COLLECTION/snapshots/upload?priority=snapshot" \
  -F "snapshot=@$SNAP" >/dev/null

AFTER=$(curl -s "$QDRANT_URL_HOST/collections/$COLLECTION" | python -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])")
echo "✓ 복원 완료 — $COLLECTION points=$AFTER"
