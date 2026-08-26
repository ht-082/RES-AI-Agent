"""문서 유형별 청킹 (v2 — 2026-08-03 전면 재설계).

설계 원칙
---------
1. **단일 출구**: 어떤 경로로 만들어진 청크든 반드시 `normalize_chunks()`를 통과한다.
   v1은 청커를 우회하는 경로(xlsx·표·전문)가 3개 있었고 그 어디에도 크기 규칙이
   걸려 있지 않아 최대 138,570자 청크가 만들어졌다. 규칙은 "각 청커"가 아니라
   "출구"에 걸어야 새 문서 타입을 추가해도 새지 않는다.

2. **경계는 줄머리에서만**: v1의 한글 조항 패턴에는 앵커가 없어 본문 중 인용
   ("제12조 제2항에 불구하고…")을 조 시작으로 오인했다. 그 결과 `제12조~제5조`처럼
   번호가 역행하는 범위 라벨이 생겼다.

3. **잘린 조각은 제 이름을 갖는다**: 하위분할된 후속 조각에 조/섹션 제목을 재부착한다.
   본문에 넣어야 임베딩·리랭킹·표시가 한 번에 해결된다(메타데이터는 임베딩에 안 들어간다).

4. **페이지 단위는 페이지가 실재할 때만**: page_number의 실체가 포맷마다 다르다.
   pdf/pptx만 진짜 페이지이고, hwp는 전부 1, docx는 인위적 순번이다.
   (라우팅은 apps/rag/tasks.py가 담당)

5. **분류는 5종**: law / contract / report / admin / general.
   v1의 spec은 contract와 경계 패턴만 달랐을 뿐이라 흡수했다.
   구조형 문서는 경계 패턴을 자동 선택한다.
"""
import hashlib
import logging
import re

logger = logging.getLogger(__name__)

# ── 공통 파라미터 ─────────────────────────────────────────────────────
MIN_CHUNK_CHARS = 300      # 이 길이를 넘길 때까지 인접 세그먼트를 병합
MAX_SEG_CHARS = 1500       # 청크 크기 상한 (모든 경로에 강제)
SUB_CHUNK_SIZE = 1200
SUB_CHUNK_OVERLAP = 150
GENERAL_CHUNK_SIZE = 800   # 구조가 없는 텍스트의 기계 분할 단위
DISCARD_UNDER = 20         # 최종 청크가 이보다 짧으면 폐기
SMALL_PAGE_CHARS = 100     # report: 이보다 짧은 페이지는 다음 페이지에 병합
ADMIN_SINGLE_CHUNK_MAX = 3000  # admin: 이 길이까지는 문서 전체 = 청크 1개

# 제어문자(탭·개행 제외) — Postgres 저장 실패와 임베딩 잡음의 원인
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# ── 경계 패턴 ─────────────────────────────────────────────────────────
# 조문 "인용"을 조 "시작"으로 오인하지 않기 위한 배제 룩어헤드.
# 실측 오탐: "제12조 제2항에 불구하고", "제14조에 따라", "제7조의 규정"
_CITATION_TAIL = (r'(?!\s*(?:제\s?\d+\s?[항호목]|에\s*따라|에\s*의하여|에\s*의한'
                  r'|에\s*불구|의\s*규정|및|또는|내지|부터|까지))')

# 줄머리 앵커 버전 — 기본. 진짜 조 제목은 거의 항상 줄 시작에 있다.
KO_ARTICLE_ANCHORED = r'(?m)^[ \t]*제\s?\d+\s?조(?:의\s?\d+)?' + _CITATION_TAIL
# 완화 버전 — 개행이 소실된 추출물(일부 hwp/pdf) 대비. 채택 기준을 높게 잡는다.
KO_ARTICLE_LOOSE = r'제\s?\d+\s?조(?:의\s?\d+)?' + _CITATION_TAIL
# 장/절/편 — 뒤에 한글이 붙는 오탐("제3장비")을 배제
KO_CHAPTER_ANCHORED = r'(?m)^[ \t]*제\s?\d+\s?[장절편](?=[^가-힣]|$)'

EN_BOUNDARY_PATTERNS = [
    r'(?m)^[ \t]*ARTICLE\s+[IVXLC\d]+(?:\.\d+)*',
    r'(?m)^[ \t]*Article\s+\d+(?:\.\d+)*',
    r'(?m)^[ \t]*[Ss]ection\s+\d+(?:\.\d+)*',
    r'(?m)^[ \t]*[Cc]lause\s+\d+(?:\.\d+)*',
    r'(?m)^[ \t]*\d{1,2}\.\s+[A-Z][A-Z ,&()\-]{4,}$',
]

# 앵커가 있는 패턴은 오탐이 드물어 낮은 기준으로 채택한다.
# 1개여도 채택한다 — 조가 하나뿐인 긴 문서(예: 단일 조항 위탁계약)에서
# 폴백시키면 그 조 제목이 통째로 사라져, 하위분할 조각이 소속을 잃는다.
# 완화 패턴은 오탐 위험이 커서 높은 기준을 요구한다.
MIN_ANCHORED_MATCHES = 1
MIN_LOOSE_MATCHES = 10

# 하위호환 별칭 (외부 스크립트가 참조)
KO_ARTICLE_PATTERN = KO_ARTICLE_ANCHORED
SPEC_BOUNDARY_PATTERN = KO_CHAPTER_ANCHORED
EN_MIN_MATCHES = MIN_LOOSE_MATCHES


# ── 저수준 유틸 ───────────────────────────────────────────────────────
def _leading_ws(raw):
    """strip()으로 잘려나갈 앞쪽 공백 길이 (char_start 보정용)"""
    return len(raw) - len(raw.lstrip())


def _snap_cut(text, lo, hi):
    """[lo, hi) 안에서 가장 자연스러운 절단 지점을 찾는다.

    v1은 개행만 봤다. 영문 계약서처럼 개행이 드문 추출물에서는 스냅이 실패해
    단어 중간이 잘렸다(실측: "er due diligence" ← "after due diligence").
    개행 → 문장 끝 → 공백 순으로 후퇴시킨다.
    """
    for marker, offset in (('\n', 1), ('. ', 2), ('。', 1), ('? ', 2), ('! ', 2), (' ', 1)):
        cut = text.rfind(marker, lo, hi)
        if cut > lo:
            return cut + offset
    return hi


def _snap_start(text, pos):
    """겹침 구간의 시작 지점을 단어 경계로 되돌린다.

    v1은 절단 끝(end)만 스냅하고 다음 조각의 시작은 `end - overlap`으로 기계 계산했다.
    그래서 끝은 깔끔해도 **다음 조각이 단어 중간에서 시작**했다
    (실측: "rdance with the terms" ← "accordance with the terms").
    """
    if pos <= 0:
        return 0
    window = max(0, pos - 80)
    for marker, offset in (('\n', 1), ('. ', 2), ('。', 1), (' ', 1)):
        back = text.rfind(marker, window, pos)
        if back != -1:
            return back + offset
    return pos


def split_text_with_offsets(text, chunk_size=SUB_CHUNK_SIZE,
                            chunk_overlap=SUB_CHUNK_OVERLAP, snap=True):
    """(청크 텍스트, 원본 내 시작 오프셋) 목록.

    snap=True면 목표 지점 앞 40% 구간에서 자연스러운 경계로 후퇴시킨다.
    """
    out = []
    start, n = 0, len(text)
    if n == 0:
        return out
    while start < n:
        end = start + chunk_size
        if snap and end < n:
            end = _snap_cut(text, start + int(chunk_size * 0.6), end)
        out.append((text[start:end], start))
        if end >= n:
            break
        nxt = end - chunk_overlap
        if snap:
            nxt = _snap_start(text, nxt)
        start = nxt if nxt > start else end
    return out


def custom_split_text(text, chunk_size=SUB_CHUNK_SIZE, chunk_overlap=SUB_CHUNK_OVERLAP):
    """(호환용) 텍스트만 반환하는 기계 분할"""
    return [c for c, _ in split_text_with_offsets(text, chunk_size, chunk_overlap, snap=False)]


def _segment_by_pattern(text, pattern):
    """경계 패턴으로 분할. [{'start','end','heading'}] (start/end는 원본 오프셋)"""
    matches = list(re.finditer(pattern, text))
    segs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segs.append({
            'start': m.start(),
            'end': end,
            'heading': re.sub(r'\s+', ' ', m.group(0)).strip(),
        })
    return segs


def _continuation_heading(text, meta):
    """하위분할 후속 조각 앞에 다시 붙일 제목을 고른다."""
    if meta.get('kind') == 'table':
        # 마크다운 표는 헤더행 + 구분행(|---|)이 앞 두 줄이다. 그대로 재부착해야
        # 잘린 뒷부분도 어느 열이 무엇인지 알 수 있다.
        lines = text.split('\n')
        head = [l for l in lines[:3] if l.strip()][:2]
        if len(head) == 2 and '---' in head[1]:
            return '\n'.join(head)
        return meta.get('table_title') or ''
    for key in ('article_no', 'section_title', 'sheet_title', 'slide_title', 'table_title'):
        val = meta.get(key)
        if val and not str(val).endswith('~'):
            return str(val)
    return ''


# ── 단일 출구 ─────────────────────────────────────────────────────────
def normalize_chunks(chunks, *, doc_type=None, max_chars=MAX_SEG_CHARS,
                     discard_under=DISCARD_UNDER, dedupe=True, source=''):
    """모든 청킹 경로가 반드시 통과하는 검증·보정 지점.

    여기서 강제하는 불변조건:
      ① 크기 <= max_chars  (초과 시 하위분할 + 제목 재부착)
      ② 길이 >= discard_under
      ③ 제어문자 없음
      ④ doc_type 존재
      ⑤ 같은 문서 안에서 내용 중복 없음

    v1에서 xlsx·표·전문 세 경로가 이 검증을 우회해 초과 청크 301개(최대 138,570자)와
    표 중복 285건이 생겼다. 이 함수를 거치지 않는 경로를 두지 않는 것이 요점이다.
    """
    out, seen = [], set()
    n_split = n_dropped = n_dup = 0

    for chunk in chunks or []:
        raw = chunk.get('text') or ''
        text = _CONTROL_CHARS.sub('', raw).strip()
        if not text:
            n_dropped += 1
            continue

        meta = dict(chunk.get('metadata') or {})
        if doc_type and not meta.get('doc_type'):
            meta['doc_type'] = doc_type
        meta.setdefault('doc_type', 'general')

        base_start = meta.get('char_start')

        # 재부착할 제목을 **먼저** 정하고, 그만큼 분할 폭을 줄인다.
        # v2 초기 사고: 마크다운 표의 헤더행+구분행이 521자였는데, 조각을
        # SUB_CHUNK_SIZE(1200)로 자른 뒤 제목을 붙여 1,610자가 됐다.
        # 그걸 verify_chunk_invariants가 치명 위반으로 잡아 문서 4건이 통째로
        # 실패했다(홍성 용역공정보고 등). 제목 재부착과 크기 상한이 서로
        # 모순이었던 것 — 상한을 지키려면 붙일 몫을 미리 빼둬야 한다.
        head_probe = _continuation_heading(text, meta) if len(text) > max_chars else ''
        head_cost = len(head_probe) + len(' (이어서)\n') if head_probe else 0
        # 제목이 지나치게 길면(폭 넓은 표) 잘라 쓴다. 본문 자리를 남겨야 한다.
        if head_cost > max_chars // 3:
            head_probe = head_probe[:max_chars // 3] + '…'
            head_cost = len(head_probe) + len(' (이어서)\n')
        sub_size = max(200, min(SUB_CHUNK_SIZE, max_chars - head_cost))

        if len(text) <= max_chars:
            pieces = [(text, 0)]
        else:
            pieces = split_text_with_offsets(text, sub_size, SUB_CHUNK_OVERLAP)
            n_split += 1

        heading = head_probe if len(pieces) > 1 else ''

        for idx, (piece, off) in enumerate(pieces):
            piece = piece.strip()
            if len(piece) < discard_under:
                n_dropped += 1
                continue
            if idx > 0 and heading and not piece.startswith(heading):
                piece = f'{heading} (이어서)\n{piece}'

            if dedupe:
                key = hashlib.sha1(re.sub(r'\s+', ' ', piece).encode('utf-8')).hexdigest()
                if key in seen:
                    n_dup += 1
                    continue
                seen.add(key)

            m = dict(meta)
            if len(pieces) > 1:
                m['part'] = idx + 1
            if base_start is not None:
                m['char_start'] = base_start + off
            out.append({'text': piece, 'metadata': m})

    if n_split or n_dropped or n_dup:
        logger.info(f"[정규화{(' ' + source) if source else ''}] "
                    f"분할 {n_split} · 폐기 {n_dropped} · 중복제거 {n_dup} → 최종 {len(out)}")
    return out


# ── 구조 경계 엔진 ────────────────────────────────────────────────────
def chunk_by_boundaries(text, pattern, base_meta, *, preamble_label='전문',
                        group_fn=None, min_chars=MIN_CHUNK_CHARS,
                        max_seg=MAX_SEG_CHARS):
    """구조 경계 기반 누적 병합 청킹 엔진.

    - 세그먼트를 순서대로 누적해 min_chars를 넘기면 청크 확정.
    - **병합 결과가 max_seg를 넘으면 그것도 하위분할한다.**
      (v1은 개별 세그먼트만 검사해, 250자 + 1,400자가 합쳐진 1,650자 청크가 통과했다)
    - group_fn(seg_text) -> (key, extra_meta): key가 바뀌면 병합하지 않는다.
    - 반환: 청크 리스트. 경계가 하나도 없으면 None (호출측이 폴백 결정).
    """
    segs = _segment_by_pattern(text, pattern)
    if not segs:
        return None

    chunks = []

    def emit(raw, meta, heading=''):
        """크기 상한을 강제하며 배출. 초과 시 제목을 재부착해 분할."""
        body = raw.strip()
        if len(body) < DISCARD_UNDER:
            return
        char_start = meta.get('char_start', 0)
        if len(body) <= max_seg:
            chunks.append({'text': body, 'metadata': dict(meta)})
            return
        for i, (sub, off) in enumerate(split_text_with_offsets(
                body, SUB_CHUNK_SIZE, SUB_CHUNK_OVERLAP)):
            sub = sub.strip()
            if len(sub) < DISCARD_UNDER:
                continue
            if i > 0 and heading:
                sub = f'{heading} (이어서)\n{sub}'
            m = dict(meta)
            m['char_start'] = char_start + off
            m['part'] = i + 1
            chunks.append({'text': sub, 'metadata': m})

    # 첫 경계 이전(전문) — v1은 여기에 크기 검사가 없었다
    pre_raw = text[:segs[0]['start']]
    if pre_raw.strip():
        meta = dict(base_meta)
        meta['article_no'] = preamble_label
        meta['char_start'] = _leading_ws(pre_raw)
        emit(pre_raw, meta, heading=preamble_label)

    buf = []

    def flush():
        if not buf:
            return
        raw = text[buf[0]['start']:buf[-1]['end']]
        meta = dict(base_meta)
        meta.update(buf[0].get('extra') or {})
        heads = [b['heading'] for b in buf]
        meta['article_no'] = heads[0] if len(heads) == 1 else f'{heads[0]}~{heads[-1]}'
        if len(heads) > 1:
            meta['articles'] = heads
        meta['char_start'] = buf[0]['start'] + _leading_ws(raw)
        emit(raw, meta, heading=heads[0])
        buf.clear()

    cur_key = None
    for seg in segs:
        seg_text = text[seg['start']:seg['end']]
        key, extra = group_fn(seg_text) if group_fn else (None, {})

        if len(seg_text.strip()) > max_seg:
            flush()                       # 앞의 누적분을 먼저 확정
            meta = dict(base_meta)
            meta.update(extra)
            meta['article_no'] = seg['heading']
            meta['char_start'] = seg['start'] + _leading_ws(seg_text)
            emit(seg_text, meta, heading=seg['heading'])
            cur_key = key
            continue

        if buf and group_fn and key != cur_key:
            flush()
        buf.append({**seg, 'extra': extra})
        cur_key = key
        if len(text[buf[0]['start']:buf[-1]['end']].strip()) >= min_chars:
            flush()
    flush()

    return chunks


def _attach_ko_article_title(chunks):
    """단일 조항 청크에 한해 '제N조(제목)'의 제목을 article_title로 추출"""
    for c in chunks:
        meta = c['metadata']
        if 'articles' in meta or not str(meta.get('article_no', '')).startswith('제'):
            continue
        m = re.search(r'제\s?\d+조(?:의\s?\d+)?[ \t]*[({【\[<](.*?)[)}\]】>]', c['text'])
        if m and m.group(1).strip():
            meta['article_title'] = m.group(1).strip()
    return chunks


def _pick_boundary(text):
    """가장 지배적인 구조 경계를 고른다. (패턴, 매칭수, 전문라벨, 종류) 또는 None.

    한·영 병기 계약(실측: Loan Agreement에 제N조 20회 vs Section 139회)에서
    한글을 무조건 우선하면 영문 구조가 통째로 무시되므로 매칭 수로 결정한다.
    """
    best = None   # (n, pattern, preamble, kind)

    def consider(n, pattern, preamble, kind, threshold):
        nonlocal best
        if n >= threshold and (best is None or n > best[0]):
            best = (n, pattern, preamble, kind)

    consider(len(re.findall(KO_ARTICLE_ANCHORED, text)),
             KO_ARTICLE_ANCHORED, '전문', 'ko_article', MIN_ANCHORED_MATCHES)
    consider(len(re.findall(KO_CHAPTER_ANCHORED, text)),
             KO_CHAPTER_ANCHORED, '서문', 'ko_chapter', MIN_ANCHORED_MATCHES)
    for pat in EN_BOUNDARY_PATTERNS:
        consider(len(re.findall(pat, text)), pat, 'Preamble', 'en', MIN_ANCHORED_MATCHES)

    if best is None:
        # 개행이 소실된 추출물 대비 — 기준을 높여 완화 패턴을 시도한다
        consider(len(re.findall(KO_ARTICLE_LOOSE, text)),
                 KO_ARTICLE_LOOSE, '전문', 'ko_article_loose', MIN_LOOSE_MATCHES)
    return best


def _chapter_group_fn():
    """제N장 경계를 넘어 병합하지 않도록 하는 group_fn (구 chunk_spec의 동작)"""
    state = {'chapter': ''}

    def group(seg_text):
        m = re.match(r'\s*제\s?(\d+)\s?장', seg_text)
        if m:
            state['chapter'] = f"제{m.group(1)}장"
        return state['chapter'], ({'chapter': state['chapter']} if state['chapter'] else {})
    return group


# ── doc_type별 청커 ───────────────────────────────────────────────────
def chunk_structured(text, filename='', doc_type='contract'):
    """구조형 문서(계약서·시방서·기술문서): 경계 패턴을 자동 선택해 병합.

    v1의 chunk_contract와 chunk_spec을 통합했다. 둘은 경계 패턴만 달랐다
    (제N조 vs 제N장·절). 분류 단계에서 계약서와 시방서를 구분하는 것은
    실무적으로 어렵고 이득도 없으므로, 문서를 보고 코드가 정한다.
    """
    picked = _pick_boundary(text)
    if picked is None:
        logger.warning(f"구조 경계 없음, general 폴백: {filename}")
        return chunk_general(text, doc_type=doc_type)

    n, pattern, preamble, kind = picked
    base = {'doc_type': doc_type, 'boundary': kind}
    if kind == 'en':
        base['lang'] = 'en'
    group_fn = _chapter_group_fn() if kind == 'ko_chapter' else None

    result = chunk_by_boundaries(text, pattern, base,
                                 preamble_label=preamble, group_fn=group_fn)
    if result is None:
        return chunk_general(text, doc_type=doc_type)

    logger.info(f"구조 청킹[{kind}] 경계 {n}개 → 청크 {len(result)}개 ({filename})")
    if kind.startswith('ko_article'):
        _attach_ko_article_title(result)
    return result


def chunk_contract(text, filename=""):
    """계약서 — 구조형 청커에 위임 (하위호환 이름)"""
    return chunk_structured(text, filename=filename, doc_type='contract')


def chunk_law(text, filename=""):
    """법령: 조문 병합 + 신구조문(시행일) 분리 — 시행일이 다른 조문은 병합하지 않음"""
    law_title = filename.rsplit('.', 1)[0]
    base = {'law_title': law_title, 'doc_type': 'law', 'version': 'current',
            'boundary': 'ko_article'}

    def group(seg_text):
        m = re.search(r'\[시행일\s*[:\s]*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)\]', seg_text)
        if m:
            return 'future', {'version': 'future', 'effective_date': m.group(1).replace(' ', '')}
        return 'current', {'version': 'current'}

    pattern = KO_ARTICLE_ANCHORED
    if len(re.findall(pattern, text)) < MIN_ANCHORED_MATCHES:
        if len(re.findall(KO_ARTICLE_LOOSE, text)) >= MIN_LOOSE_MATCHES:
            pattern = KO_ARTICLE_LOOSE

    result = chunk_by_boundaries(text, pattern, base,
                                 preamble_label='전문/부칙', group_fn=group)
    if result is None:
        logger.warning(f"법령 분할 실패(조항 패턴 없음), general 폴백: {filename}")
        return chunk_general(text, doc_type='law')
    return _attach_ko_article_title(result)


def chunk_general(text, max_chars=GENERAL_CHUNK_SIZE, overlap=SUB_CHUNK_OVERLAP,
                  doc_type='general'):
    """구조가 없는 텍스트: 문단·문장 경계 스냅 분할"""
    # boundary='none' 은 "구조 경계를 찾지 못해 기계 분할했다"는 표시다.
    # 호출측(tasks.py)이 이 값으로 청킹 폴백 여부를 판정한다.
    return [
        {'text': c.strip(),
         'metadata': {'doc_type': doc_type, 'boundary': 'none',
                      'char_start': off + _leading_ws(c)}}
        for c, off in split_text_with_offsets(text, max_chars, overlap, snap=True)
    ]


def chunk_paged(parsed_items, filename="", doc_type='report'):
    """페이지가 실재하는 포맷(pdf·pptx)의 보고서: 페이지 단위 + 소페이지 병합.

    ⚠ 이 청커는 파서가 **진짜 페이지 번호**를 줄 때만 의미가 있다.
    hwp는 전부 1, docx는 인위적 순번이므로 tasks.py 라우팅이 포맷으로 걸러낸다.
    """
    out = []
    pending_texts, pending_pages = [], []

    def emit():
        if not pending_texts:
            return
        text = "\n".join(pending_texts).strip()
        pages = list(pending_pages)
        pending_texts.clear()
        pending_pages.clear()
        if len(text) < DISCARD_UNDER:
            return
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        first = lines[0] if lines else ''
        slide_title = (first[:100] + '...') if len(first) > 100 else first
        meta = {'page_no': pages[0], 'slide_title': slide_title, 'doc_type': doc_type}
        if len(pages) > 1:
            meta['pages'] = pages
        out.append({'text': text, 'metadata': meta})

    for item in parsed_items:
        text = (item.get('text') or '').strip()
        if not text:
            continue
        pending_texts.append(text)
        pending_pages.append(item.get('page_number', 1))
        if len("\n".join(pending_texts)) >= SMALL_PAGE_CHARS:
            emit()
    emit()
    return out


def chunk_report(parsed_items, filename=""):
    """(하위호환 이름) 페이지 단위 청킹"""
    return chunk_paged(parsed_items, filename=filename, doc_type='report')


def chunk_markdown(parsed_items, filename=""):
    """마크다운(사업개요 등): 헤딩 섹션 = 청크 1개.

    parse_markdown이 헤딩 단위로 잘라 주고 헤딩 줄을 본문에 포함시켜 준다.
    크기 초과 시의 헤딩 재부착은 normalize_chunks가 담당한다.
    """
    out = []
    for item in parsed_items:
        text = (item.get('text') or '').strip()
        if not text:
            continue
        out.append({'text': text, 'metadata': {
            'doc_type': 'markdown',
            'page_no': item.get('page_number', 1),
            'section_title': item.get('section_title', '') or '',
        }})
    return out


def chunk_admin(parsed_items, filename="", paged=True):
    """공문/행정문서: 문서 전체 = 청크 1개 + 문서번호·날짜 메타.

    paged=False (hwp 등 페이지가 없는 포맷)면 길이 초과 시 페이지가 아니라
    구조/문단 기준으로 나눈다. v1은 무조건 페이지 단위로 떨어뜨려서,
    페이지가 전부 1인 hwp 공문이 통짜 청크가 됐다.
    """
    texts = [(item.get('text') or '').strip() for item in parsed_items]
    texts = [t for t in texts if t]
    if not texts:
        return []
    full = "\n".join(texts)

    meta = {'doc_type': 'admin'}
    m = re.search(r'제?\s?(\d{4}\s?-\s?\d+)\s?호?', full)
    if m:
        meta['doc_no'] = m.group(1).replace(' ', '')
        # v1은 doc_no를 뽑아 두고도 section_title에 연결하지 않아,
        # 공문 청크 616개의 출처 라벨이 비어 있었다.
        meta['section_title'] = f"공문 {meta['doc_no']}"
    m = re.search(r'(\d{4})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})', full)
    if m:
        meta['issued_date'] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    first_page = next((i.get('page_number', 1) for i in parsed_items if (i.get('text') or '').strip()), 1)

    if len(full) <= ADMIN_SINGLE_CHUNK_MAX:
        meta['page_no'] = first_page
        return [{'text': full, 'metadata': meta}]

    if not paged:
        # 페이지가 없는 포맷 — 구조 경계를 시도하고, 없으면 문단 분할
        picked = _pick_boundary(full)
        if picked:
            n, pattern, preamble, kind = picked
            result = chunk_by_boundaries(full, pattern, dict(meta), preamble_label=preamble)
            if result:
                for c in result:
                    c['metadata'].setdefault('page_no', first_page)
                return result
        out = chunk_general(full, doc_type='admin')
        for c in out:
            c['metadata'].update({k: v for k, v in meta.items() if k != 'doc_type'})
            c['metadata']['page_no'] = first_page
        return out

    out = []
    for item in parsed_items:
        text = (item.get('text') or '').strip()
        if len(text) < DISCARD_UNDER:
            continue
        m2 = dict(meta)
        m2['page_no'] = item.get('page_number', 1)
        out.append({'text': text, 'metadata': m2})
    return out


def chunk_sheets(parsed_items, doc_type='general'):
    """xlsx: 파서의 시트/행묶음 단위를 보존한다.

    v1은 이 경로가 청커를 완전히 우회해 크기 검사를 받지 않았다(초과 125건).
    크기 초과 시의 분할·헤더행 재부착은 normalize_chunks가 담당한다.
    """
    out = []
    for item in parsed_items:
        text = (item.get('text') or '').strip()
        if not text:
            continue
        out.append({'text': text, 'metadata': {
            'doc_type': doc_type,
            'page_no': item.get('page_number'),
            'sheet_name': item.get('sheet_name', ''),
            'cell_range': item.get('cell_range', ''),
            'sheet_title': item.get('section_title', ''),
            'section_title': item.get('section_title', ''),
        }})
    return out


def verify_chunk_invariants(chunks, *, max_chars=MAX_SEG_CHARS,
                            discard_under=DISCARD_UNDER, require_locator=True):
    """청크 집합이 불변조건을 지키는지 검사한다. 위반 목록을 반환(빈 리스트면 정상).

    normalize_chunks가 이미 강제하지만, **검사를 따로 두는 이유**가 있다.
    v1의 실패는 "규칙이 없어서"가 아니라 "규칙을 우회하는 경로가 생겨서"였다.
    새 경로가 추가돼도 이 검사가 적재 시점에 잡아내야 같은 사고가 반복되지 않는다.

    검사 항목
      ① 크기 <= max_chars
      ② 길이 >= discard_under
      ③ 제어문자 없음
      ④ doc_type 존재
      ⑤ 위치 정보(page_no 또는 char_start) 존재 — 출처 표시·페이지 역산에 필요
      ⑥ 같은 집합 안에 내용 중복 없음
    """
    problems, seen = [], {}
    for i, c in enumerate(chunks or []):
        text = c.get('text') or ''
        meta = c.get('metadata') or {}
        where = f"#{i}({meta.get('article_no') or meta.get('section_title') or ''})"

        if len(text) > max_chars:
            problems.append(f"{where} 크기 초과 {len(text)}자 > {max_chars}")
        if len(text.strip()) < discard_under:
            problems.append(f"{where} 길이 부족 {len(text.strip())}자")
        if _CONTROL_CHARS.search(text):
            problems.append(f"{where} 제어문자 포함")
        if not meta.get('doc_type'):
            problems.append(f"{where} doc_type 없음")
        if require_locator and meta.get('page_no') is None and meta.get('char_start') is None:
            problems.append(f"{where} 위치정보 없음(page_no·char_start 모두 없음)")

        key = re.sub(r'\s+', ' ', text).strip()
        if key and key in seen:
            problems.append(f"{where} 내용 중복 (앞서 #{seen[key]}와 동일)")
        elif key:
            seen[key] = i
    return problems


def chunk_tables(table_items, doc_type='general'):
    """표 청크 — 본문과 별도로 부착한다.

    v1은 이 경로도 청커를 우회했다(초과 151건 + 같은 표가 22회 반복 추출된 중복 285건).
    크기 분할·헤더행 재부착·중복 제거는 normalize_chunks가 담당한다.
    """
    out = []
    for t in table_items:
        text = (t.get('text') or '').strip()
        if not text:
            continue
        title = t.get('section_title', '') or ''
        out.append({'text': text, 'metadata': {
            'doc_type': doc_type,
            'kind': 'table',
            'page_no': t.get('page_number'),
            'table_title': title,
            'section_title': title,
        }})
    return out
