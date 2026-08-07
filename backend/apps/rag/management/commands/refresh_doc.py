"""문서 한 건만 교체·갱신한다 (전체 재적재 없이).

사업개요처럼 실무자가 계속 손보는 문서를 위한 경로다.
파일 내용이 바뀌면 checksum이 바뀌어 ingest_initial_docs는 **새 문서를 하나 더**
만들 뿐 옛 버전을 지우지 않는다. 그러면 같은 사업의 옛 수치와 새 수치가 동시에
검색되어 답변이 흔들린다. 이 명령은 옛 문서(및 그 Qdrant 벡터)를 지우고
새 파일을 같은 자리에 적재한다.

사용 예:
  # initial_docs 안의 파일을 고친 뒤 그 한 건만 갱신
  python manage.py refresh_doc --file "media/initial_docs/1. 홍성PJT/[사업개요] 홍성빛나래솔라.md"

  # 파일명 패턴으로 여러 건 (사업개요 전체 갱신)
  python manage.py refresh_doc --pattern "[사업개요]" --dir media/initial_docs

  # 무엇이 지워지고 무엇이 들어갈지만 확인
  python manage.py refresh_doc --pattern "[사업개요]" --dry-run
"""
import hashlib
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.documents.models import CorpusVersion, Document
from apps.rag.tasks import process_document


def file_checksum(path):
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4096), b''):
            md5.update(block)
    return md5.hexdigest()


class Command(BaseCommand):
    help = '문서 한 건(또는 패턴 일치분)만 삭제 후 재적재한다. 전체 재적재 불필요.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='갱신할 파일 경로')
        parser.add_argument('--pattern', type=str,
                            help='파일명에 이 문자열이 포함된 파일을 모두 갱신')
        parser.add_argument('--dir', type=str, default='',
                            help='--pattern 탐색 루트 (기본: MEDIA_ROOT/initial_docs)')
        parser.add_argument('--doc-type', type=str, default='',
                            help='문서 유형 강제 지정 (미지정 시 기존 문서 값 유지, 신규는 general)')
        parser.add_argument('--corpus-version', type=str, default='',
                            help='대상 코퍼스 버전 라벨 (미지정 시 is_active 버전)')
        parser.add_argument('--dry-run', action='store_true',
                            help='실제로 바꾸지 않고 대상만 출력')

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        targets = self._collect_targets(options)
        if not targets:
            raise CommandError('갱신할 파일을 찾지 못했습니다. --file 또는 --pattern 을 확인하세요.')

        corpus = self._resolve_corpus(options.get('corpus_version'))
        collection = corpus.collection_name if corpus else settings.QDRANT_COLLECTION
        self.stdout.write(f"대상 코퍼스: v{corpus.version if corpus else '?'} (컬렉션 {collection})")
        self.stdout.write(f"갱신 대상 파일 {len(targets)}건\n")

        dry = options.get('dry_run')
        ok = failed = 0

        for path in targets:
            filename = os.path.basename(path)
            olds = list(Document.objects.filter(original_filename=filename, corpus=corpus))

            # 내용이 그대로면 건드리지 않는다 (불필요한 재임베딩 방지)
            checksum = file_checksum(path)
            if len(olds) == 1 and olds[0].checksum == checksum and olds[0].status == 'indexed':
                self.stdout.write(f"  = 변경 없음, 건너뜀: {filename}")
                continue

            old_chunks = sum(d.chunks.count() for d in olds)
            self.stdout.write(
                f"  ▶ {filename}\n"
                f"     기존 {len(olds)}건 / 청크 {old_chunks}개 삭제 → 재적재"
            )
            if dry:
                continue

            doc_type = options.get('doc_type') or (olds[0].doc_type if olds else '')
            project = olds[0].project if olds else None
            source_path = (olds[0].metadata or {}).get('source_path') if olds else None
            uploader = olds[0].uploaded_by if olds else None

            try:
                # 1) 옛 문서 제거 — post_delete 시그널이 Qdrant 벡터까지 정리한다
                for d in olds:
                    d.delete()

                # 2) 새 파일을 media/documents 로 복사 (checksum 접두어로 이름 충돌 방지)
                media_docs = os.path.join(settings.MEDIA_ROOT, 'documents')
                os.makedirs(media_docs, exist_ok=True)
                stored_name = f"{checksum[:8]}_{filename}"
                shutil.copy2(path, os.path.join(media_docs, stored_name))

                # 3) 문서 레코드 생성 후 동기 적재
                if source_path is None:
                    root = self._scan_root(options)
                    rel = os.path.relpath(os.path.dirname(path), root)
                    source_path = '' if rel == '.' else rel.replace(os.sep, '/')

                doc = Document.objects.create(
                    project=project,
                    corpus=corpus,
                    title=filename,
                    original_filename=filename,
                    file_type=os.path.splitext(filename)[1].lower().strip('.'),
                    storage_uri=f'/media/documents/{stored_name}',
                    file_size=os.path.getsize(path),
                    checksum=checksum,
                    status='uploaded',
                    doc_type=doc_type or 'general',
                    uploaded_by=uploader,
                    metadata={'source_path': source_path},
                )
                result = process_document(str(doc.id))
                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS(
                        f"     ✔ 완료 — 청크 {result.get('chunk_count')}개"))
                    ok += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        f"     ✘ 적재 실패: {result.get('error')}"))
                    failed += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"     ✘ 오류: {e}"))
                failed += 1

        if dry:
            self.stdout.write(self.style.WARNING('\n[dry-run] 실제로 바뀐 것은 없습니다.'))
            return

        self.stdout.write(f"\n갱신 완료: 성공 {ok} / 실패 {failed}")
        self._report_integrity(collection)

    # ------------------------------------------------------------------
    def _scan_root(self, options):
        return options.get('dir') or os.path.join(settings.MEDIA_ROOT, 'initial_docs')

    def _collect_targets(self, options):
        if options.get('file'):
            path = options['file']
            if not os.path.isfile(path):
                raise CommandError(f'파일이 없습니다: {path}')
            return [os.path.abspath(path)]

        pattern = options.get('pattern')
        if not pattern:
            return []

        root = self._scan_root(options)
        if not os.path.isdir(root):
            raise CommandError(f'디렉토리가 없습니다: {root}')

        found = []
        for dirpath, _, files in os.walk(root):
            for name in files:
                ext = os.path.splitext(name)[1].lower().strip('.')
                if ext not in ('pdf', 'docx', 'xlsx', 'hwp', 'hwpx', 'pptx', 'md', 'txt'):
                    continue
                if pattern in name:
                    found.append(os.path.join(dirpath, name))
        return sorted(found)

    def _resolve_corpus(self, version):
        qs = CorpusVersion.objects
        corpus = qs.filter(version=version).first() if version else qs.filter(is_active=True).first()
        if version and not corpus:
            raise CommandError(f'코퍼스 버전을 찾을 수 없습니다: {version}')
        return corpus

    def _report_integrity(self, collection):
        """갱신 후 Postgres ↔ Qdrant 개수 일치를 확인한다."""
        from apps.documents.models import DocumentChunk
        from services.qdrant_client import get_client

        pg = DocumentChunk.objects.count()
        try:
            qd = get_client().get_collection(collection).points_count
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Qdrant 조회 실패: {e}'))
            return

        if pg == qd:
            self.stdout.write(self.style.SUCCESS(f'정합성 OK — Postgres {pg} = Qdrant {qd}'))
        else:
            self.stdout.write(self.style.ERROR(
                f'정합성 불일치 — Postgres {pg} vs Qdrant {qd} (차이 {qd - pg}). '
                f'고아 벡터가 남았을 수 있습니다.'))
