#!/usr/bin/env bash
# 공통: .env 로드 + 컨테이너 확인. 모든 스크립트가 source 해서 쓴다.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."          # 항상 리포 루트에서 동작

# 루트 .env 가 있으면 POSTGRES_* 를 읽는다 (compose 와 같은 출처)
if [ -f .env ]; then set -a; . ./.env; set +a; fi
PGDB="${POSTGRES_DB:-re_agent}"
PGUSER="${POSTGRES_USER:-re_user}"
PG_CONTAINER="re_postgres"
QDRANT_URL_HOST="${QDRANT_URL_HOST:-http://localhost:6333}"

need_container() {  # $1 = 컨테이너명
  if ! docker ps --format '{{.Names}}' | grep -qx "$1"; then
    echo "✗ 컨테이너 '$1' 이(가) 실행 중이 아닙니다. 먼저: docker compose up -d" >&2
    exit 1
  fi
}

pg_ready() {
  docker exec "$PG_CONTAINER" pg_isready -U "$PGUSER" -d "$PGDB" >/dev/null 2>&1
}

qdrant_ready() {
  curl -sf "$QDRANT_URL_HOST/collections" >/dev/null 2>&1
}

confirm() {  # $1 = 안내문, $2 = 입력해야 하는 문자열
  echo ""
  echo "$1"
  printf "계속하려면 '%s' 를 입력하세요: " "$2"
  read -r ans
  if [ "$ans" != "$2" ]; then echo "중단합니다."; exit 1; fi
}
