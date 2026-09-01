#!/usr/bin/env bash
# Qdrant 컬렉션 스냅샷 백업 (컬렉션을 변경하지 않는다)
# 사용: ./scripts/backup_qdrant.sh [컬렉션] [버전라벨]
#   기본 컬렉션: re_documents_v2 (활성 코퍼스)
. "$(dirname "$0")/_common.sh"

COLLECTION="${1:-re_documents_v2}"
VERSION="${2:-v$(date +%Y%m%d)}"
OUT="baseline/qdrant_${COLLECTION}_${VERSION}.snapshot"

need_container "re_qdrant"
qdrant_ready || { echo "✗ Qdrant가 준비되지 않았습니다"; exit 1; }

POINTS=$(curl -s "$QDRANT_URL_HOST/collections/$COLLECTION" | python -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null) \
  || { echo "✗ 컬렉션 '$COLLECTION' 이 없습니다"; exit 1; }
echo "▶ 스냅샷 생성: $COLLECTION (points=$POINTS)"

NAME=$(curl -sf -X POST "$QDRANT_URL_HOST/collections/$COLLECTION/snapshots" \
  | python -c "import json,sys; print(json.load(sys.stdin)['result']['name'])")
echo "  생성됨: $NAME — 다운로드 중"
mkdir -p baseline
curl -sf -o "$OUT" "$QDRANT_URL_HOST/collections/$COLLECTION/snapshots/$NAME"

# 서버 쪽 임시 스냅샷은 정리한다 (방금 만든 것만 지운다 — 컬렉션 데이터와 무관)
curl -sf -X DELETE "$QDRANT_URL_HOST/collections/$COLLECTION/snapshots/$NAME" >/dev/null || true

SIZE=$(du -h "$OUT" | cut -f1)
[ -s "$OUT" ] || { echo "✗ 다운로드 실패(빈 파일)"; exit 1; }
echo "✓ 완료: $OUT ($SIZE, points=$POINTS)"
echo "  ⚠ PG 덤프와 반드시 같은 시점에 떠서 쌍으로 전달하세요."
