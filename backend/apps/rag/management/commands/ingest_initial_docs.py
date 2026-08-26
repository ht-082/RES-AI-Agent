import os
import shutil
import hashlib
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from openai import OpenAI
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.accounts.models import User
from apps.workspaces.models import Workspace, Project
from apps.documents.models import Document
from apps.rag.tasks import is_global_folder, process_document

try:
    import fitz
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

def extract_head_text(file_path, file_type, max_chars=5000):
    text = ""
    try:
        if file_type == 'pdf' and fitz:
            with fitz.open(file_path) as pdf:
                for page in pdf:
                    text += page.get_text()
                    if len(text) > max_chars:
                        break
        elif file_type in ('md', 'txt'):
            for enc in ('utf-8', 'utf-8-sig', 'cp949'):
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        text = f.read(max_chars)
                    break
                except UnicodeDecodeError:
                    continue
        elif file_type == 'docx' and docx:
            try:
                doc_file = docx.Document(file_path)
                for para in doc_file.paragraphs:
                    text += para.text + "\n"
                    if len(text) > max_chars:
                        break
            except Exception:
                # 확장자만 .docx인 레거시 .doc (실측 4건: 기술규격서 3 + FS보고서).
                # 빈 텍스트로 두면 규칙 분류가 전부 빗나가고 LLM이 파일명만 보게 된다.
                from services.parser import parse_doc
                items = parse_doc(file_path)
                text = "\n".join(i.get('text', '') for i in items)
        elif file_type == 'doc':
            from services.parser import parse_doc
            items = parse_doc(file_path)
            text = "\n".join(i.get('text', '') for i in items)
        elif file_type == 'hwpx':
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    section_files = [f for f in zf.namelist() if f.startswith('Contents/section') and f.endswith('.xml')]
                    section_files.sort()
                    for sec_file in section_files:
                        with zf.open(sec_file) as xml_file:
                            tree = ET.parse(xml_file)
                            for elem in tree.getroot().iter():
                                if elem.tag.endswith('}t') and elem.text:
                                    text += elem.text + " "
                                    if len(text) > max_chars:
                                        break
                        if len(text) > max_chars:
                            break
            except Exception as inner_e:
                print(f"hwpx 파싱 오류: {inner_e}")
        elif file_type == 'hwp':
            # hwp는 72건으로 2위 포맷 — 빈 텍스트로 두면 전부 general 오분류된다.
            # hwp5txt 기반 파서를 재사용한다 (parser.parse_hwp: hwp5txt → 정규식 폴백).
            from services.parser import parse_hwp
            items = parse_hwp(file_path)
            text = "\n".join(i.get('text', '') for i in items)
        elif file_type == 'pptx':
            from services.parser import parse_pptx
            items = parse_pptx(file_path)
            text = "\n".join(i.get('text', '') for i in items if i.get('kind') != 'table')
    except Exception as e:
        print(f"텍스트 추출 오류 ({os.path.basename(file_path)}): {e}")
    return text[:max_chars]

# 법령 문서에만 나타나는 '발행 표기'. 법제처 PDF의 머리말/꼬리말과 제정 근거에서 온다.
# '시행령'·'부칙'은 계약서도 법을 인용하며 쓰므로 근거로 쓰지 않는다.
# (실측: 용역계약서 2건이 "…시행령에 따라" 문구 때문에 law로 오분류됨.
#  적재 문서 31건 검증 결과 법령 10건은 전부 아래 마커를 보유, 계약서 13건은 0건 보유)
LAW_MARKERS = ("법제처", "국가법령정보센터", "법률 제", "대통령령 제", "부령 제", "고시 제")


# 정리된 파일명은 '종류_대상_날짜' 형태라 **접두가 곧 문서종류**다.
# 접두가 이미 종류를 선언한 파일은, 이름 안쪽에 다른 종류 단어가 섞여 있어도
# 그 선언을 존중한다. (실측 오탐: '보고서_사업타당성검토서'→검토서→admin,
#  '계약서_지역개발채권매입필증'→필증→admin. 둘 다 접두가 정답이다)
_DECLARED_TYPE = re.compile(r'^(보고서|감사보고서|계약서|계약서부록|사업계획서|질의답변)_')

# 접두 → doc_type 직접 매핑 (2026-08-20).
# 이전에는 접두를 오분류 **방지**에만 쓰고 판정은 본문 규칙→LLM에 맡겼다.
# 그 결과 5,000자짜리 '보고서_*.pdf'가 규칙 미달로 LLM 폴백에 넘어갔다
# (실측: 폴백 197건 중 109건이 접두 보유). 이번 달 파일명 정리로 접두가
# 사람이 검수한 신뢰 라벨이 됐으므로 직접 판정에 쓴다 — LLM 추측보다
# 서열이 높고, 재적재 때마다 결과가 흔들리지 않는다.
# ⚠ 전제: 큐레이션된 코퍼스. 접두를 대충 붙인 파일이 들어오면 그대로 박힌다.
_PREFIX_DOC_TYPE = [
    (re.compile(r'^(보고서|감사보고서|사업계획서)_'), 'report'),
    (re.compile(r'^(계약서|계약서부록|협약서|합의서|약정서)_'), 'contract'),
    (re.compile(r'^질의답변_'), 'general'),   # 입찰 Q&A 시트 — 계약도 보고도 아니다
]


def rule_based_classify(text, file_type, filename=''):
    """6종 분류 규칙 (파싱_청킹_전략.md §4, 우선순위 순)"""
    # 0-0. 접두 선언 — 최우선. 본문 규칙보다 앞에 두는 이유: 접두는 사람이 붙인
    # 라벨이고, 본문 규칙은 인용문("…시행령에 따라")에 속을 수 있는 추정이다.
    for pat, dt in _PREFIX_DOC_TYPE:
        if pat.match(filename):
            return dt, '파일명 접두 선언'

    article_matches = len(re.findall(r'제\s?\d+조(의\d+)?', text))
    declared = bool(_DECLARED_TYPE.match(filename))

    # 0. spec(파일명) — 과업지시서는 법령·고시를 인용해 law 규칙에 걸리므로 law보다 먼저 본다
    #    '기술규격서'는 EPC 기술문서의 표준 명칭인데 빠져 있었다(당진1에만 25건).
    #    본문의 제N장/절 구조로 걸릴 수도 있지만, 파일명이 확실한 신호라 여기서 잡는다.
    if not declared and re.search(r'시방서|규격서|과업\s?지시|설계기준|Manual', filename, re.I):
        return "spec", "시방·규격·과업 파일명"

    # 1. law — 제N조 다수 + 법령 발행표기
    if article_matches >= 5 and any(k in text for k in LAW_MARKERS):
        return "law", "제N조 5회 이상 + 법령 발행표기"

    # 2. spec(구조) — 제N장/제N절 다수. 단 보고서류는 시방을 '인용'만 하므로 제외
    #    (실측: 감리월간보고서 12건이 장·절 인용 때문에 spec으로 오분류됨)
    spec_marks = len(re.findall(r'제\s?\d+\s?[장절](?=[^가-힣]|$)', text))
    if spec_marks >= 3 and not re.search(r'보고서|보고자료|현황|월간|주간', filename):
        return "spec", f"장/절 패턴 {spec_marks}회"

    # 3. contract(한글) — 조항 + 당사자/체결 문구.
    #    보고서류는 계약을 '인용'만 하므로 제외 (실측: 최종감리보고서가 contract로 오분류)
    #    '계약'만 요구하면 PF 문서 다수가 샌다 — 대출·출자·자금보충 문서는 본문에서
    #    스스로를 "본 **약정**"이라 부르고 '계약'이라는 낱말이 아예 없을 수 있다.
    #    (코퍼스 실측: 약정서 7 · 협약서 3 · 합의서 5건)
    #    나머지 조건(제N조 + 갑을/당사자/체결 + 보고서 파일명 배제)이 그대로라 범위만 넓어진다.
    if article_matches >= 1 and any(k in text for k in ("계약", "약정", "협약", "합의")) and (
        ("갑" in text and "을" in text) or "당사자" in text or "체결" in text
    ) and not re.search(r'보고서|보고자료', filename):
        return "contract", "제N조 + 계약 당사자/체결 문구"

    # 3-1. contract(영문) — Article/Section/Clause 다수 + 계약 어휘
    en_marks = sum(len(re.findall(p, text)) for p in (
        r'(?m)^[ \t]*ARTICLE\s+[IVXLC\d]+', r'(?m)^[ \t]*Article\s+\d+',
        r'(?m)^[ \t]*[Ss]ection\s+\d+(?:\.\d+)*', r'(?m)^[ \t]*[Cc]lause\s+\d+'))
    if en_marks >= 10 and any(k in text for k in ("Agreement", "Parties", "hereinafter", "shall mean")):
        return "contract", f"영문 조항 구조 {en_marks}회 + 계약 어휘"

    # 4. admin — 문서번호/행정 파일명 + 짧은 문서 (report보다 먼저: '허가 통보' 오분류 흡수)
    has_doc_no = bool(re.search(r'제?\s?\d{4}\s?-\s?\d+\s?호?', text[:1000]))
    # 파일명 정리(2026-08) 후 문서종류가 세분화되면서 기존 목록이 놓치는 것이 많아졌다.
    # 넉넉히 잡아도 되는 이유: 바로 아래 `len(text) < 3000` 게이트가 안전판이라,
    # 긴 문서는 이 이름을 달고 있어도 admin으로 떨어지지 않고 report/general로 흐른다.
    # (admin = 문서 전체 1청크이므로 긴 문서에 적용되면 안 된다)
    admin_name = bool(re.search(
        r'공문|허가증|통보|승낙|신청서|접수증|증명|필증'
        r'|확인증|확인서|등록증|등본|제의서|명부'
        r'|결과서|검토서|내역서|청구서|요청서|통지서|증빙|대장|공정표|신고',
        filename)) and not declared
    if (has_doc_no or admin_name) and len(text) < 3000 and text.strip():
        return "admin", "문서번호/행정 파일명 + 단문"

    # 5. report — 슬라이드형
    if file_type == 'pptx' or (file_type == 'pdf' and len(text) < 1500 and text.strip()):
        if any(k in text for k in ["승인", "보고", "검토", "목차"]):
            return "report", "보고서 키워드 및 슬라이드 특성 감지"

    return None, None

def llm_classify(text, filename=''):
    # 스캔본(텍스트 없음)도 파일명만으로 분류 가능하다 — "토지매매계약서 날인본.pdf" 등.
    # 텍스트·파일명이 모두 없을 때만 포기한다.
    if not text.strip() and not filename.strip():
        return "general", "텍스트·파일명 없음"
    if not text.strip():
        text = "(스캔 문서 — 본문 텍스트 없음. 파일명으로 판단할 것)"

    api_key = getattr(settings, 'LLM_API_KEY', None) or os.environ.get('LLM_API_KEY')
    if not api_key:
        return "general", "LLM API KEY 없음"

    client = OpenAI(api_key=api_key)
    # 파일명은 강한 분류 신호다("○○용역계약서.docx", "허가증" 등) — 프롬프트에 포함 (전략 §4)
    prompt = f"""다음 문서의 유형을 아래 6가지 중 하나의 단어로만 대답해.
- contract: 계약서·협약서·합의서 (국문/영문 불문)
- law: 법령·시행령·규칙·고시·지침
- spec: 시방서·과업지시서·설계기준·기술 매뉴얼
- admin: 공문·허가증·통보서·신청서·증명서 등 짧은 행정문서
- report: 보고서·설명자료·발표자료
- general: 그 외

파일명: {filename}
텍스트:
{text[:4000]}"""
    try:
        response = client.chat.completions.create(
            # 분류도 답변·OCR과 같은 모델로 통일한다. 예전 리팩터에서 이 한 곳만
            # 'gpt-4o-mini' 하드코딩이 남아, 규칙으로 안 잡힌 문서의 유형 판별이
            # 저사양 모델로 돌고 있었다. settings.LLM_MODEL(.env: gpt-5.6-terra)로 일원화.
            #
            # temperature는 넘기지 않는다. gpt-5.x(추론 모델)는 temperature=0을
            # 거부하고 기본값 1만 허용한다. 분류는 출력 단어를 키워드 매칭하므로
            # 값이 1이어도 결과가 흔들리지 않는다.
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content.strip().lower()
        for t in ['contract', 'report', 'law', 'spec', 'admin', 'general']:
            if t in answer:
                return t, "LLM 판별"
        return "general", "LLM 판별 모호함"
    except Exception:
        return "general", "LLM 오류 발생"

class Command(BaseCommand):
    help = 'backend/media/initial_docs 내의 문서를 탐색하여 일괄 적재 및 RAG 인덱싱을 수행합니다. 자동 분류 및 dry-run 지원.'

    def add_arguments(self, parser):
        parser.add_argument('--sync', action='store_true', help='동기식(순차적) 인덱싱 실행')
        parser.add_argument('--classify-only', action='store_true', help='인덱싱 없이 분류만 수행하고 CSV로 결과 저장')
        parser.add_argument('--type-map', type=str, help='수동 매핑 CSV 파일 경로')
        parser.add_argument('--corpus-version', type=str, default='',
                            help="코퍼스 버전 라벨 (예: 1.1). 마이너 올림=같은 컬렉션 누적, "
                                 "메이저 올림=새 컬렉션 생성. 생략 시 is_active 버전.")

    def handle(self, *args, **options):
        sync = options['sync']
        classify_only = options['classify_only']
        type_map_path = options['type_map']
        
        type_map = {}
        if type_map_path and os.path.exists(type_map_path):
            with open(type_map_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    type_map[row.get('filename')] = row.get('doc_type')
            self.stdout.write(self.style.SUCCESS(f"수동 매핑 파일 로드 완료: {len(type_map)}건"))

        initial_docs_dir = os.path.join(settings.MEDIA_ROOT, 'initial_docs')
        if not os.path.exists(initial_docs_dir):
            self.stdout.write(self.style.ERROR(f"디렉토리가 존재하지 않습니다: {initial_docs_dir}"))
            return

        admin_user = User.objects.filter(role='admin').first() or User.objects.first()
        workspace, _ = Workspace.objects.get_or_create(
            slug='business-dev', defaults={'name': '사업개발실', 'created_by': admin_user}
        )

        # 코퍼스 버전 결정 (파싱_청킹_전략.md / 사용자 버전 체계)
        from apps.documents.models import CorpusVersion
        ver = (options.get('corpus_version') or '').strip()
        if ver:
            try:
                major = int(ver.split('.')[0])
            except ValueError:
                self.stdout.write(self.style.ERROR(f"버전 형식 오류: {ver!r} (예: 1.1)"))
                return
            corpus = CorpusVersion.objects.filter(major=major).first()
            if corpus:
                if corpus.version != ver:
                    self.stdout.write(f"코퍼스 라벨 갱신: v{corpus.version} → v{ver} (컬렉션 {corpus.collection_name} 누적)")
                    corpus.version = ver
                    corpus.save(update_fields=['version', 'updated_at'])
            else:
                corpus = CorpusVersion.objects.create(
                    version=ver, major=major,
                    collection_name=f're_documents_v{major}',
                    description=f'메이저 v{major} — 청킹 방식 변경분',
                )
                self.stdout.write(self.style.SUCCESS(
                    f"신규 메이저 코퍼스 v{ver} 생성 (컬렉션 {corpus.collection_name}). "
                    f"기본 질의 대상으로 쓰려면 is_active 전환 필요."))
        else:
            corpus = CorpusVersion.objects.filter(is_active=True).first()
        self.stdout.write(f"적재 대상 코퍼스: v{corpus.version if corpus else '?'} "
                          f"(컬렉션 {corpus.collection_name if corpus else settings.QDRANT_COLLECTION})")
        media_docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(media_docs_dir, exist_ok=True)

        results = []
        
        for root_dir, dirs, files in os.walk(initial_docs_dir):
            for file in files:
                # 오피스 임시·잠금 파일. `~$문서.xlsm`은 엑셀이 파일을 열어둔 동안
                # 만드는 수백 바이트짜리 소유자 표시용이라 확장자만 같고 내용이 없다.
                # 거르지 않으면 파싱 실패로 남거나 빈 청크가 코퍼스에 섞인다.
                if file.startswith('~$') or file.startswith('.~lock.'):
                    continue

                ext = os.path.splitext(file)[1].lower().strip('.')
                # md/txt: 사업개요처럼 사람이 직접 관리하는 정리본 경로
                if ext not in ('pdf', 'docx', 'doc', 'xlsx', 'xlsm', 'hwp', 'hwpx', 'pptx', 'md', 'txt'):
                    continue

                file_path = os.path.join(root_dir, file)
                
                # 분류 로직
                doc_type = "general"
                method = ""
                note = ""
                
                if file in type_map:
                    doc_type = type_map[file]
                    method = "수동 지정"
                    note = "CSV 맵 오버라이드"
                else:
                    text = extract_head_text(file_path, ext)
                    guessed_type, rule_note = rule_based_classify(text, ext, filename=file)

                    if guessed_type:
                        doc_type = guessed_type
                        method = "규칙 기반"
                        note = rule_note
                    else:
                        doc_type, llm_note = llm_classify(text, filename=file)
                        method = "LLM"
                        note = llm_note

                results.append({
                    'filename': file,
                    'doc_type': doc_type,
                    'method': method,
                    'note': note,
                    'file_path': file_path,
                    'ext': ext,
                    'root': root_dir
                })
        
        # 표 출력
        self.stdout.write("\n" + "="*110)
        self.stdout.write(f"{'파일명':<45} | {'유형':<10} | {'분류 방식':<10} | {'비고'}")
        self.stdout.write("-" * 110)
        for r in results:
            short_name = r['filename']
            if len(short_name) > 42:
                short_name = short_name[:40] + ".."
            self.stdout.write(f"{short_name:<45} | {r['doc_type']:<10} | {r['method']:<10} | {r['note']}")
        self.stdout.write("="*110 + "\n")

        if classify_only:
            csv_path = os.path.join(settings.BASE_DIR, 'classification_result.csv')
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['filename', 'doc_type', 'method', 'note'])
                writer.writeheader()
                for r in results:
                    writer.writerow({
                        'filename': r['filename'], 'doc_type': r['doc_type'], 
                        'method': r['method'], 'note': r['note']
                    })
            self.stdout.write(self.style.SUCCESS(f"dry-run 완료! 분류 결과가 CSV로 저장되었습니다: {csv_path}"))
            return

        # 인덱싱 (배치 안정성 및 리포트 통계 모드 강제)
        from django.utils import timezone
        from services.qdrant_client import get_client
        
        stats = {
            'total_files': len(results),
            'success_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'total_chunks': 0,
            'doc_type_counts': {},
            'fail_reasons': [],
            'fallback_files': [],
            'scan_issue_files': []
        }

        self.stdout.write("\n" + "="*80)
        self.stdout.write(f"🚀 [인덱싱 시작] {stats['total_files']}개 파일 전수 처리 중...")

        for r in results:
            rel_path = os.path.relpath(r['root'], initial_docs_dir)

            # 프로젝트 = 최상위 폴더 (예: '2. 당진PJT'). 하위 폴더 깊이는 무시한다.
            # basename을 쓰면 '당진PJT/Contract'와 '홍성PJT/Contract'가 같은 'Contract'
            # 프로젝트로 합쳐져 PJT 구분이 사라진다.
            # 단, 별칭표에 null로 등록된 폴더('0. 포괄 정보' 등)는 특정 사업 소속이
            # 아닌 공통 문서다. 프로젝트에 묶으면 payload의 is_global이 False가 되어,
            # 사업을 지정해 질문할 때 법령·지침이 통째로 검색에서 빠진다.
            project = None
            if rel_path != '.':
                proj_name = rel_path.split(os.sep)[0]
                if not is_global_folder(proj_name):
                    project, _ = Project.objects.get_or_create(
                        workspace=workspace, name=proj_name,
                        defaults={'description': f'{proj_name} 프로젝트', 'created_by': admin_user}
                    )

            # 원본 내용으로 checksum을 먼저 계산한다(복사 전).
            # 저장 파일명에 checksum을 붙여 이름 충돌을 원천 차단한다.
            # 실측: 'PF 자금인출' 폴더의 '인출요청서.pdf', '03. 통장사본.pdf' 등이
            #      내용이 다른데 이름이 같아, 파일명만 쓰면 서로 덮어쓴다.
            md5 = hashlib.md5()
            with open(r['file_path'], 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5.update(chunk)
            checksum = md5.hexdigest()

            stored_name = f"{checksum[:8]}_{r['filename']}"
            dest_file_path = os.path.join(media_docs_dir, stored_name)
            shutil.copy2(r['file_path'], dest_file_path)

            # 같은 파일이라도 코퍼스 버전(청킹 세대)이 다르면 별도 레코드 — 버전 간 비교 가능
            doc, doc_created = Document.objects.get_or_create(
                checksum=checksum,
                corpus=corpus,
                defaults={
                    'project': project,
                    'title': r['filename'],
                    'original_filename': r['filename'],
                    'file_type': r['ext'],
                    'storage_uri': f'/media/documents/{stored_name}',
                    'file_size': os.path.getsize(dest_file_path),
                    'status': 'uploaded',
                    'doc_type': r['doc_type'],
                    'uploaded_by': admin_user,
                    # 하위 폴더는 분류에 쓰지 않고 출처 추적용으로만 남긴다.
                    'metadata': {'source_path': rel_path.replace(os.sep, '/')},
                }
            )

            # 같은 파일이 여러 PJT 폴더에 복사되어 있으면 checksum이 같아 1건으로 합쳐진다.
            # 어느 PJT에 귀속됐는지 헷갈리지 않도록 알려준다.
            if not doc_created and project and doc.project_id != (project.id if project else None):
                self.stdout.write(self.style.WARNING(
                    f"  ↳ 동일 파일이 다른 프로젝트에도 있음: {r['filename']} "
                    f"(귀속: {doc.project.name if doc.project else '없음'} / 이번 발견: {proj_name})"
                ))

            if not doc_created and doc.doc_type != r['doc_type']:
                doc.doc_type = r['doc_type']
                doc.save(update_fields=['doc_type'])

            if doc_created or doc.status in ('failed', 'uploaded'):
                action = "신규" if doc_created else "재시도"
                self.stdout.write(f"▶ 처리 중: [{action}] {r['filename']} ({r['doc_type']})... ", ending="")
                self.stdout.flush()
                
                try:
                    # 파일 1개 처리 오류가 전체 배치를 중단시키지 않게 격리하고 동기로 호출
                    res = process_document(str(doc.id))
                    
                    if res.get('success'):
                        self.stdout.write(self.style.SUCCESS(f"✅ 완료 ({res.get('chunk_count', 0)} 청크)"))
                        stats['success_count'] += 1
                        stats['total_chunks'] += res.get('chunk_count', 0)
                        dt = res.get('doc_type', 'unknown')
                        stats['doc_type_counts'][dt] = stats['doc_type_counts'].get(dt, 0) + 1
                        
                        if res.get('fallback'):
                            stats['fallback_files'].append(r['filename'])
                    else:
                        err = res.get('error', 'Unknown Error')
                        self.stdout.write(self.style.ERROR(f"❌ 실패 ({err})"))
                        stats['failed_count'] += 1
                        stats['fail_reasons'].append((r['filename'], err))
                        if res.get('scan_issue'):
                            stats['scan_issue_files'].append(r['filename'])
                            
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"💥 치명적 에러 격리됨: {e}"))
                    stats['failed_count'] += 1
                    stats['fail_reasons'].append((r['filename'], f"Unhandled Exception: {str(e)}"))
            else:
                self.stdout.write(self.style.WARNING(f"▶ [스킵] 이미 인덱싱됨: {r['filename']}"))
                stats['skipped_count'] += 1
                # 스킵된 문서도 통계에 반영 (기존 청크 수 합산)
                from apps.documents.models import DocumentChunk
                existing_chunks = DocumentChunk.objects.filter(document=doc).count()
                stats['total_chunks'] += existing_chunks
                stats['doc_type_counts'][doc.doc_type] = stats['doc_type_counts'].get(doc.doc_type, 0) + 1

        # ---------------- 리포트 출력 ----------------
        report_lines = []
        report_lines.append("\n" + "="*80)
        report_lines.append("📊 [인덱싱 배치 종료 요약 리포트]")
        report_lines.append("="*80)
        report_lines.append(f"총 스캔 대상 파일 수: {stats['total_files']}건")
        report_lines.append(f"✅ 신규 성공: {stats['success_count']}건")
        report_lines.append(f"⏩ 기처리 스킵 (성공 유지): {stats['skipped_count']}건")
        report_lines.append(f"❌ 실패: {stats['failed_count']}건")
        report_lines.append(f"🧩 누적 생성 청크 수: {stats['total_chunks']}개")
        report_lines.append("-" * 80)
        report_lines.append("▶ 유형별 분포 (성공+스킵 기준):")
        for dt, count in stats['doc_type_counts'].items():
            report_lines.append(f"  - {dt}: {count}건")
        
        if stats['failed_count'] > 0:
            report_lines.append("-" * 80)
            report_lines.append("▶ 실패 사유 목록:")
            for fname, err in stats['fail_reasons']:
                report_lines.append(f"  - {fname} : {err}")
                
        if stats['scan_issue_files']:
            report_lines.append("-" * 80)
            report_lines.append("▶ 스캔본 의심 (텍스트 추출 0글자):")
            for fname in stats['scan_issue_files']:
                report_lines.append(f"  - {fname}")
                
        if stats['fallback_files']:
            report_lines.append("-" * 80)
            report_lines.append("▶ 조항 분할 폴백 발생 (general 룰로 대체 처리됨):")
            for fname in stats['fallback_files']:
                report_lines.append(f"  - {fname}")

        # 정합성 점검 (Self-Healing Check)
        report_lines.append("="*80)
        report_lines.append("🔍 [데이터베이스/Qdrant 정합성 점검]")
        db_count = Document.objects.filter(status='indexed').count()
        report_lines.append(f"  - PostgreSQL 성공(indexed) 레코드 수: {db_count}건")
        
        qdrant_count = 0
        try:
            client = get_client()
            qdrant_count = client.count(collection_name=settings.QDRANT_COLLECTION).count
            report_lines.append(f"  - Qdrant 저장된 총 벡터(Point) 수: {qdrant_count}개")
        except Exception as e:
            report_lines.append(f"  - Qdrant 접속 불가: {e}")
            
        report_lines.append("="*80)

        report_text = "\n".join(report_lines)
        self.stdout.write(report_text)
        
        date_str = timezone.now().strftime('%Y%m%d')
        report_file = os.path.join(settings.BASE_DIR, f'indexing_report_{date_str}.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
            
        self.stdout.write(self.style.SUCCESS(f"✅ 요약 리포트가 파일로 저장되었습니다: {report_file}\n"))
