import os
from django.core.management.base import BaseCommand
from apps.documents.models import Document
from services.parser import parse_file
from apps.rag.chunkers import chunk_contract, chunk_law, chunk_report
from django.conf import settings

class Command(BaseCommand):
    help = '대표 문서 3종에 대한 가상 청킹 테스트'

    def handle(self, *args, **options):
        test_files = [
            {'filename': '1. 홍성군 염해태양광 사업 설명자료_230724.pdf', 'type': 'report'}
        ]

        for tf in test_files:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(f"📌 테스트 대상: {tf['filename']} [{tf['type']}]")
            
            # DB를 모두 지웠으므로 파일명으로 직접 처리
            doc_title = tf['filename']
                
            file_path = os.path.join(settings.MEDIA_ROOT, 'documents', tf['filename'])
            if not os.path.exists(file_path):
                self.stdout.write(self.style.ERROR(f"파일이 없습니다: {file_path}"))
                continue
                
            parsed_items = parse_file(file_path)
            if not parsed_items:
                self.stdout.write(self.style.ERROR("파싱 실패 (텍스트 0)"))
                continue
                
            if tf['type'] == 'contract':
                full_text = "\n".join([item.get('text', '') for item in parsed_items])
                chunks = chunk_contract(full_text, filename=doc_title)
            elif tf['type'] == 'law':
                full_text = "\n".join([item.get('text', '') for item in parsed_items])
                chunks = chunk_law(full_text, filename=doc_title)
            elif tf['type'] == 'report':
                chunks = chunk_report(parsed_items, filename=doc_title)
                
            self.stdout.write(self.style.SUCCESS(f"✅ 총 추출된 청크 수: {len(chunks)}개"))
            
            # 메타데이터 출력 (전체 중 앞/중간 일부 샘플)
            sample_count = min(3, len(chunks))
            self.stdout.write("--- [추출 샘플 확인] ---")
            for i, c in enumerate(chunks[:sample_count]):
                self.stdout.write(f" [Chunk {i+1}] 메타데이터: {c.get('metadata')}")
                text_preview = c.get('text', '')[:60].replace('\n', ' ')
                self.stdout.write(f"            텍스트: {text_preview}...")
            
            # 법령의 경우 future(시행일) 버전이 잡혔는지 중간 청크 스캔
            if tf['type'] == 'law':
                future_chunks = [c for c in chunks if c.get('metadata', {}).get('version') == 'future']
                if future_chunks:
                    self.stdout.write(self.style.WARNING(f"\n ⭐ 신구조문(future) 버전 특수 감지 성공! 총 {len(future_chunks)}개 조항 발견"))
                    c = future_chunks[0]
                    self.stdout.write(f" [Future Chunk] 메타데이터: {c.get('metadata')}")
                    text_preview = c.get('text', '')[:60].replace('\n', ' ')
                    self.stdout.write(f"                텍스트: {text_preview}...")
        self.stdout.write("="*80 + "\n")
