#!/usr/bin/env bash
# 신규 개발자 초기 셋업 — baseline 파일로 PG + Qdrant 를 한 번에 복원.
# 전제: docker compose up -d 완료, baseline/ 에 덤프·스냅샷 쌍이 있음.
# 사용: ./scripts/setup_baseline.sh [버전라벨]   (생략 시 baseline/ 에서 자동 탐지)
. "$(dirname "$0")/_common.sh"

echo "═══ RES AI Agent baseline 셋업 ═══"

# 1. Docker 서비스 확인
for c in re_postgres re_qdrant re_backend; do need_container "$c"; done
echo "✓ 1/8 컨테이너 확인 (postgres·qdrant·backend)"

# 2·3. 준비 대기 (최대 60초)
for i in $(seq 1 12); do pg_ready && break; sleep 5; done
pg_ready || { echo "✗ PostgreSQL 준비 실패"; exit 1; }
echo "✓ 2/8 PostgreSQL 응답"
for i in $(seq 1 12); do qdrant_ready && break; sleep 5; done
qdrant_ready || { echo "✗ Qdrant 준비 실패"; exit 1; }
echo "✓ 3/8 Qdrant 응답"

# 4. baseline 파일 탐지
if [ -n "${1:-}" ]; then
  PG_DUMP="baseline/postgres_baseline_$1.dump"
  QD_SNAP=$(ls baseline/qdrant_*_"$1".snapshot 2>/dev/null | head -1 || true)
else
  PG_DUMP=$(ls -t baseline/postgres_baseline_*.dump 2>/dev/null | head -1 || true)
  QD_SNAP=$(ls -t baseline/qdrant_*.snapshot 2>/dev/null | head -1 || true)
fi
[ -n "$PG_DUMP" ] && [ -f "$PG_DUMP" ] || { echo "✗ baseline/*.dump 이 없습니다. 전달받은 파일을 baseline/ 에 두세요."; exit 1; }
[ -n "$QD_SNAP" ] && [ -f "$QD_SNAP" ] || { echo "✗ baseline/*.snapshot 이 없습니다."; exit 1; }
echo "✓ 4/8 baseline 파일: $(basename "$PG_DUMP") + $(basename "$QD_SNAP")"
echo "  ⚠ 두 파일은 같은 시점의 쌍이어야 합니다 (버전 라벨 확인)."

# 5. PG 복원 (restore_postgres.sh 가 확인 절차를 담당)
bash scripts/restore_postgres.sh "$PG_DUMP"
echo "✓ 5/8 PostgreSQL 복원"

# 6. Qdrant 복원
bash scripts/restore_qdrant.sh "$QD_SNAP" --force
echo "✓ 6/8 Qdrant 복원"

# 7. DB 연결 확인 (Django ORM 경유)
docker exec re_backend python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup()
from apps.documents.models import Document, DocumentChunk
print('  documents=%d chunks=%d' % (Document.objects.count(), DocumentChunk.objects.count()))
" 2>/dev/null | tail -1
echo "✓ 7/8 Django ↔ DB 연결"

# 8. Qdrant 컬렉션 확인
curl -s "$QDRANT_URL_HOST/collections" | python -c "
import json,sys
for c in json.load(sys.stdin)['result']['collections']: print('  -', c['name'])"
echo "✓ 8/8 컬렉션 목록"

echo ""
echo "═══ 완료 — http://localhost:5173 접속. 계정: docker exec -it re_backend python manage.py createsuperuser ═══"
