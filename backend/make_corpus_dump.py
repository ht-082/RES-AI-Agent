"""코퍼스 이관용 선별 덤프 생성 (읽기 전용 — 원본 DB는 SELECT/COPY TO만 한다).

산출물: /app/media/corpus_package/corpus_data.sql
- 테이블: workspaces → projects → corpus_versions → documents → document_chunks (FK 순서)
- documents.uploaded_by 는 컬럼 자체를 제외 (계정 정보 미이관, nullable 확인됨)
- 파일 앞머리의 TRUNCATE 는 받는 쪽 신규 DB에서의 재실행 안전용 텍스트다.
  이 스크립트는 원본 DB에 어떤 쓰기도 하지 않는다.
"""
import io
import os
import sys

sys.path.insert(0, '/app')
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection  # noqa: E402

OUT_DIR = '/app/media/corpus_package'
OUT = os.path.join(OUT_DIR, 'corpus_data.sql')
os.makedirs(OUT_DIR, exist_ok=True)

# v2.0 코퍼스만 이관한다. v1 청크·문서는 Qdrant 스냅샷(v2 컬렉션)에 벡터가
# 없어 검색 불가한 죽은 데이터가 되므로 제외한다.
V2 = "(SELECT id FROM corpus_versions WHERE major=2)"
TABLES = [
    ('workspaces', None, ''),
    # 고아 프로젝트 144건(과거 적재 시도 잔재, 어느 문서도 미참조) 제외
    ('projects', None,
     f' WHERE id IN (SELECT DISTINCT project_id FROM documents WHERE corpus_id IN {V2} AND project_id IS NOT NULL)'),
    ('corpus_versions', None, ' WHERE major=2'),
    ('documents', 'uploaded_by', f' WHERE corpus_id IN {V2}'),      # 계정 FK 제외
    ('document_chunks', None,
     f' WHERE document_id IN (SELECT id FROM documents WHERE corpus_id IN {V2})'),
]

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('-- RES AI Agent 코퍼스 데이터 (v2.0)\n')
    fh.write('-- 실행: docker exec -i re_postgres psql -U re_user -d re_agent '
             '< corpus_data.sql\n')
    fh.write('-- 주의: 아래 첫 문장이 기존 코퍼스 테이블을 비운다. 신규 설치 전용.\n')
    fh.write('BEGIN;\n')
    fh.write('TRUNCATE document_chunks, documents, corpus_versions, '
             'projects, workspaces CASCADE;\n')
    with connection.cursor() as cur:
        for table, exclude, where in TABLES:
            cond = f" AND column_name <> '{exclude}'" if exclude else ''
            cur.execute(
                "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) "
                "FROM information_schema.columns "
                f"WHERE table_name='{table}'{cond}")
            cols = cur.fetchone()[0]
            fh.write(f'\nCOPY {table} ({cols}) FROM stdin;\n')
            raw = cur.cursor  # psycopg2 원시 커서 (copy_expert 지원)
            raw.copy_expert(f'COPY (SELECT {cols} FROM {table}{where}) TO STDOUT', fh)
            fh.write('\\.\n')
    fh.write('COMMIT;\n')

with connection.cursor() as cur:
    cur.execute('SELECT count(*) FROM document_chunks c JOIN documents d '
                'ON c.document_id=d.id WHERE d.corpus_id IN '
                '(SELECT id FROM corpus_versions WHERE major=2)')
    rows = cur.fetchone()[0]
print(f'생성 완료: {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB) · 원본 청크 {rows}행')
