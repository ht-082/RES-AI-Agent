import json
import logging
import os
import uuid

from django.conf import settings
from django.db.models import F
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from .models import Conversation, Message, MessageSource, MessageAttachment, ConversationShare
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer,
    MessageSerializer, SendMessageSerializer, ConversationShareSerializer,
    MessageAttachmentSerializer,
)

logger = logging.getLogger(__name__)

# 첨부 가능한 형식 (services/parser.py가 다룰 수 있는 것들)
ALLOWED_ATTACHMENT_EXTS = {'pdf', 'docx', 'xlsx', 'xlsm', 'pptx', 'hwp', 'hwpx'}
# 첨부 1건당 LLM에 넣을 텍스트 상한. 문서 전문을 그대로 넣으면 컨텍스트가 폭발한다.
ATTACHMENT_TEXT_LIMIT = 8000


def run_rag(conversation, user_content):
    """검색 → 컨텍스트/출처 구성. (sources, context_text, error, no_hit) 반환.

    send_message(비스트리밍)와 stream_message(SSE)가 공유한다.
    """
    from apps.documents.models import Document, DocumentChunk
    from services.retriever import retrieve_for_views

    sources, context_parts = [], []
    try:
        project_id = conversation.project.id if conversation.project else None
        search_results = retrieve_for_views(
            query=user_content,
            project_id=project_id,
            corpus_version=conversation.corpus_version or None,
        )
    except Exception as e:
        import traceback
        logger.error(f"🚨 [RAG PIPELINE FATAL ERROR]\n{traceback.format_exc()}")
        return [], '', str(e), False

    # search_results는 리랭커 순위대로 정렬되어 있으므로 순서를 유지한다.
    # (score는 Qdrant 점수이므로 이 값으로 재정렬하면 리랭킹이 무효가 된다.)
    from services.retriever import apply_relevance_gate
    passed, gate_reason = apply_relevance_gate(search_results)
    final_chunks = passed[:settings.RAG_MAX_CONTEXT_K]

    if getattr(settings, 'DEBUG_RAG', True):
        logger.info(f"[RAG] 후보 {len(search_results)} (K={settings.RAG_RETRIEVE_K}) "
                    f"게이트[{gate_reason}] 통과={len(passed)} 최종={len(final_chunks)}")

    if not final_chunks:
        return [], '', None, True

    # [M-1] 컨텍스트 길이 가드. 청커 우회 경로 탓에 최대 138,570자짜리 청크가 존재해,
    # 8개만 모아도 30만 자(약 10만 토큰)가 되어 지연·비용 폭증과 타임아웃을 유발했다.
    per_chunk_limit = getattr(settings, 'RAG_CONTEXT_CHUNK_CHAR_LIMIT', 4000)
    total_budget = getattr(settings, 'RAG_CONTEXT_CHAR_BUDGET', 24000)
    used, truncated, skipped = 0, 0, 0

    # [M-3] 출처 번호는 '실제로 컨텍스트에 담긴 순서'로 매긴다.
    # 예전에는 청크 조회 실패 시에도 인덱스가 증가해 [참고자료 N]과 출처 목록이 어긋났다.
    for hit in final_chunks:
        payload = getattr(hit, 'payload', {}) or {}
        try:
            chunk = DocumentChunk.objects.get(qdrant_point_id=payload.get('chunk_id'))
            doc = chunk.document
        except (DocumentChunk.DoesNotExist, Document.DoesNotExist):
            continue

        body = chunk.content or ''
        if len(body) > per_chunk_limit:
            body = body[:per_chunk_limit] + f"\n…(이하 {len(chunk.content) - per_chunk_limit:,}자 생략)"
            truncated += 1
        if used + len(body) > total_budget and context_parts:
            skipped += 1
            continue          # 예산 초과 — 순위가 낮은 청크부터 버린다
        used += len(body)

        loc = format_location(chunk)

        # 컨텍스트 줄에 사업명을 박는다. 파일명만으로는 어느 사업 문서인지 알 수 없어
        # (`보고서_1차투소위사업개요_181221.pdf` → 임자 PJT), LLM 이 질문의 사업과
        # 대조할 근거 자체를 못 받는다. 실측: 코퍼스에 없는 '울산 부유식 해상풍력'을 물었더니
        # 임자 PJT 문서의 200MW 를 그 사업의 계통연계 용량으로 단정했다.
        rank = len(sources) + 1
        proj = project_label_for(payload)
        head = f"[참고자료 {rank}] [사업: {proj}] {doc.title} ({loc})"
        context_parts.append(f"{head}\n{body}")
        sources.append(MessageSource(
            document=doc,
            document_chunk=chunk,
            display_title=doc.original_filename or doc.title,
            short_label=doc.title[:4] + ".." if len(doc.title) > 5 else doc.title,
            page_number=chunk.page_number,
            location_label=loc,
            score=getattr(hit, 'score', 0.0),
            rank=rank,
            snippet=chunk.content[:200],
        ))

    if truncated or skipped:
        logger.info(f"[RAG] 컨텍스트 가드: {used:,}자 사용 / 예산 {total_budget:,}자 "
                    f"(청크 절단 {truncated}건, 예산초과 제외 {skipped}건)")
    return sources, "\n\n".join(context_parts), None, False


# 도식·차트를 요청하는 표현. 이 말이 나올 때만 프롬프트에 도식 지시를 붙인다.
# 항상 붙이면 시스템 프롬프트가 길어져 사내 근거 예산을 잠식하고,
# 요청하지도 않은 답변에 도식이 끼어든다.
_DIAGRAM_HINTS = (
    '도식', '도표', '다이어그램', '플로우차트', '순서도', '흐름도',
    '차트', '그래프', '시각화', '타임라인', '간트', '마인드맵',
    '그림으로', '그려', '도식화', 'flowchart', 'diagram', 'chart', 'gantt',
    # 실측(2026-08-19): 사용자가 '가시화'라고 썼는데 '시각화'만 있어 감지에 실패했다.
    # 지침이 안 붙자 모델이 박스 문자로 ASCII 아트를 그렸고, 그게 코드블록으로
    # 렌더돼 가로로 잘렸다. 같은 뜻의 다른 표기를 모두 받는다.
    '가시화', '시각적', '한눈에', '보기 쉽게', '정리해서 보여',
    '로드맵', '타임 라인', '조직도', '관계도', '구조도', '계통도',
    'timeline', 'roadmap', 'graph', 'visual',
)

DIAGRAM_INSTRUCTION = """

[도식 작성 지침]
사용자가 도식·차트를 요청했습니다. 아래 규칙을 지키십시오.

- **연혁·경과·이력**(시점이 나열되는 것)은 ```viz:timeline 블록에 JSON만 담으십시오.
  화면이 전용 컴포넌트로 세로 배치해 그립니다. mermaid timeline은 쓰지 마십시오.
  status는 done(완료) 또는 ongoing(진행 중). phase·detail·tags는 있으면 넣습니다.
  총 기간·건수 같은 요약 수치는 **쓰지 마십시오** — 화면이 직접 계산합니다.
```viz:timeline
{"title":"당진행복솔라 인허가 경과","items":[
{"date":"2021.11.30","phase":"인허가","title":"발전사업허가 취득","tags":["제2021-122호","99MW"],"status":"done"},
{"date":"2024.07","phase":"진행 중","title":"154kV 사전기술검토","status":"ongoing"}]}
```
- 구조·절차·관계는 ```mermaid 코드블록으로 그리십시오.
  · 절차/흐름 → flowchart TD
  · 상태 변화 → stateDiagram-v2
  · 일정(기간이 있는 공정) → gantt (dateFormat YYYY-MM-DD)
- **수치 비교는 mermaid로 그리지 말고 마크다운 표로 제시하십시오.**
  화면에서 표를 막대·선 차트로 바꾸는 기능이 이미 있어, 표가 곧 차트가 됩니다.
  숫자를 도식 안에 다시 쓰면 원본과 어긋날 위험이 있습니다.
  다만 **관계를 설명하는 엣지 라벨의 수치는 유지하십시오** — 지분율·금액·용량처럼
  관계 자체의 의미인 값을 빼면 관계도가 이름 목록으로 전락합니다.
  예: `A -->|지분 49%| B`
- **절대로 문자로 그림을 그리지 마십시오.** `│ └ ├ ─ ▼ ▲ → ┌ ┐` 같은 박스·화살표
  문자를 늘어놓아 표·트리·타임라인 모양을 만드는 방식(ASCII 아트)은 금지입니다.
  화면에서 도식으로 렌더되지 않고 코드 덩어리로 표시되어 가로로 잘립니다.
  반드시 ```mermaid 코드블록이나 마크다운 표 중 하나를 쓰십시오.
- 노드 라벨에 큰따옴표·괄호·콜론을 쓰지 마십시오. 문법 오류의 주된 원인입니다.
- 참고 자료에 없는 항목을 도식에 넣지 마십시오. 모르면 노드를 만들지 않습니다.
- 도식 아래에 핵심을 한두 문장으로 요약하십시오.
"""


def wants_diagram(text):
    """사용자가 도식·차트를 요청했는지 판정한다."""
    lowered = (text or '').lower()
    return any(hint in lowered for hint in _DIAGRAM_HINTS)


def resolve_llm_model(conversation, requested=''):
    """사용할 답변 생성 모델을 정한다. **allowlist 밖의 값은 받지 않는다.**

    클라이언트가 보낸 모델명을 그대로 쓰면 임의의 고가 모델을 호출당할 수 있어,
    settings.LLM_MODEL_CHOICES 안에 있는 것만 통과시킨다.
    우선순위: 이번 요청 지정 > 대화 설정 > 서버 기본값
    """
    allowed = {m['id'] for m in getattr(settings, 'LLM_MODEL_CHOICES', [])}
    for candidate in (requested, getattr(conversation, 'llm_model', '')):
        if candidate and candidate in allowed:
            return candidate
        if candidate:
            logger.warning(f"허용되지 않은 모델 요청을 무시합니다: {candidate!r}")
    return settings.LLM_MODEL


# page_number가 문서의 실제 쪽번호인 포맷. 나머지는 파서가 만든 순번이라
# 화면에 "p.N"으로 쓰면 거짓말이 된다 — apps/rag/chunkers.py 머리말 4번 참조.
# 실측(2026-09-21): 계약서_대출약정서_20240703.docx는 257청크인데 page_number가
# 493까지 올라간다(서로 다른 값 249개). 100쪽 남짓한 약정서에 493쪽은 없다.
# hwp는 전부 1이라 최소한 틀린 티가 나지만, docx는 그럴듯해 보여서 더 위험하다.
_REAL_PAGE_FORMATS = ('pdf', 'pptx')


def format_location(chunk):
    """출처 위치 라벨. 포맷마다 '위치'의 의미가 달라 분기한다.

    xlsx는 페이지가 시트 순번일 뿐이라 "p.3"이 아무 정보도 주지 않는다.
    시트명이 있으면 그것을 쓴다. (LLM 컨텍스트와 출처 칩이 같은 값을 쓰도록
    한 곳에서 만든다 — 예전에는 두 곳이 따로 계산해 서로 달랐다.)

    docx·hwp의 page_number도 같은 이유로 숨긴다. 절 제목만 남으면 라벨이
    짧아지지만, **틀린 쪽번호보다는 없는 쪽이 낫다** — 사용자가 그 숫자를 믿고
    원문에서 찾으면 없다.
    """
    if getattr(chunk, 'sheet_name', ''):
        loc = f"시트: {chunk.sheet_name}"
        return f"{loc} ({chunk.cell_range})" if chunk.cell_range else loc
    parts = []
    # chunk.document는 호출부에서 이미 조회해 FK 캐시에 있다(추가 쿼리 없음).
    file_type = (getattr(getattr(chunk, 'document', None), 'file_type', '') or '').lower()
    if chunk.page_number is not None and file_type in _REAL_PAGE_FORMATS:
        parts.append(f"p.{chunk.page_number}")
    if chunk.section_title:
        parts.append(chunk.section_title)
    return ' · '.join(parts) or '위치 미상'


def run_web_search(query):
    """웹 검색 → (web_sources, web_text, error). run_rag()와 대칭 구조.

    사용자가 토글을 켤 때만 호출된다. 자동 폴백은 하지 않는다 —
    실측에서 사내 전용 질의("당진행복솔라 PF 대주단")에 이름만 비슷한
    다른 사업 기사가 상위로 올라왔다. 자동으로 켜면 그게 답이 된다.
    """
    from services.web_search import (WebSearchError, build_web_context,
                                     filter_results, search)
    try:
        raw = search(query)
    except WebSearchError as e:
        logger.warning(f"웹 검색 실패(무시하고 사내 근거만 사용): {e}")
        return [], '', str(e)

    kept, reason = filter_results(raw)
    logger.info(f"[웹] 후보 {len(raw)} 게이트[{reason}] 통과 {len(kept)}")
    if not kept:
        return [], '', None

    web_text, cited = build_web_context(kept)
    return cited, web_text, None


def build_messages(conversation, user_msg, user_content, use_docs, context_text,
                   web_text=''):
    """LLM 프롬프트 구성 (시스템 지시 + 사내자료 + 첨부 + 최근 히스토리 + 질문)"""
    system_prompt = (
        "당신은 재생에너지(태양광/풍력) 분야의 전문 지식을 갖고 있는 사업개발실의 사내 AI 에이전트입니다.\n"
        "한국어로 친절하고 격식 있게 답변하십시오.\n"
    )
    # 첨부는 근거의 한 종류다. 아래 분기가 '근거가 없다'고 말하기 전에 먼저 확인해야
    # 첨부만 있는 경우에 "일반적인 지식으로 답하라"는 잘못된 지시가 나가지 않는다.
    attachment_text = build_attachment_context(conversation)

    if use_docs and context_text:
        system_prompt += (
            "주어진 [사내 참고 문서 내용]을 기반으로만 사용자의 질문에 대답하십시오.\n"
            "답변은 반드시 참고 자료의 사실에 근거해야 하며, 참고 자료에 없는 내용은 절대 지어내거나 가상의 수치, 예측값 등을 임의로 만들어 대답하지 마십시오.\n"
            "가설적인 추론이나 없는 사실을 꾸며내는 행위는 완전히 금지됩니다.\n"
            "자료가 부족해 정확한 대답을 할 수 없다면 솔직히 모른다고 답변하십시오.\n"
            "각 참고자료 앞의 [사업: X]가 질문의 사업과 일치하는지 먼저 확인하십시오. "
            "일치하는 자료가 하나도 없으면 추정하지 말고 해당 사업 자료를 찾지 못했다고 밝히십시오. "
            "다른 사업의 자료를 근거로 쓸 때는 어느 사업 문서인지 반드시 함께 밝히십시오.\n\n"
            f"[사내 참고 문서 내용]\n{context_text}"
        )
    elif attachment_text:
        # 사내 검색은 비었지만 첨부가 있는 경우. 첨부는 코퍼스에 없는 새 파일이 대부분이라
        # 검색이 비는 것이 정상이며, 이때 근거는 첨부 하나다.
        system_prompt += (
            "사내 문서에서는 관련 자료를 찾지 못했습니다. 아래 [첨부파일 내용]만을 근거로 "
            "답변하고, 첨부파일에 없는 내용은 지어내지 마십시오.\n"
            "첨부파일로도 답할 수 없으면 솔직히 모른다고 답변하십시오."
        )
    elif not web_text:
        system_prompt += "사내 문서 참조 모드가 꺼져있거나 제공된 참고 자료가 없습니다. 일반적인 지식 범주에서 답변하십시오."
    else:
        system_prompt += "사내 참고 자료는 없습니다. 아래 웹 검색 결과만을 근거로 답변하십시오."

    # 웹 검색 근거 — 사내 문서와 **명확히 구분**해서 넣는다.
    # 도메인 화이트리스트를 두지 않으므로 신뢰도 판단은 사용자 몫이고,
    # 판단하려면 도메인·날짜가 답변에 보여야 한다.
    if web_text:
        system_prompt += (
            "\n\n[웹 검색 결과 — 사내 문서가 아니며 출처 신뢰도는 확인되지 않았습니다]\n"
            f"{web_text}\n\n"
            "웹 검색 결과를 쓸 때의 규칙:\n"
            "- 사내 문서와 웹 정보가 충돌하면 **사내 문서를 우선**하고, 충돌 사실을 함께 밝히십시오.\n"
            "- 웹에만 근거가 있는 내용은 \"웹 검색 결과(도메인)에 따르면\" 형태로 출처를 밝혀 쓰십시오.\n"
            "- 웹 출처는 신뢰도가 검증되지 않았음을 답변에 한 번 명시하십시오.\n"
            "- 답변 끝에 근거 구성을 밝히십시오. 예: (사내 근거 3건 · 웹 근거 2건)\n"
        )

    # 사용자가 이 대화에 첨부한 파일 (C-6) — 토글과 무관하게 항상 제공
    if attachment_text:
        system_prompt += (
            "\n\n사용자가 이 대화에 파일을 첨부했습니다. 아래 [첨부파일 내용]도 "
            "함께 근거로 사용하십시오. 첨부파일에 없는 내용을 지어내지 마십시오.\n\n"
            f"[첨부파일 내용]\n{attachment_text}"
        )

    # 도식 지시는 요청이 감지될 때만 붙인다 (약 400자, 평상시 컨텍스트 예산 보존)
    if wants_diagram(user_content):
        system_prompt += DIAGRAM_INSTRUCTION

    payload = [{'role': 'system', 'content': system_prompt}]

    # [M-1] 히스토리 길이 가드. 개수(10개)만 제한하고 길이는 무제한이라, 긴 표 답변이
    # 몇 번 오가면 히스토리만으로 프롬프트가 수만 토큰이 됐다. 최근 것부터 담다가
    # 예산을 넘으면 더 오래된 대화를 버린다.
    hist_budget = getattr(settings, 'LLM_HISTORY_CHAR_BUDGET', 6000)
    history = list(
        conversation.messages.filter(status__in=['done', 'partial'])
        .exclude(id=user_msg.id).order_by('-created_at')[:10]
    )
    picked, used = [], 0
    for h in history:                       # 최신 → 과거 순
        content = h.content or ''
        if used + len(content) > hist_budget and picked:
            break
        used += len(content)
        picked.append(h)

    for h in reversed(picked):              # 다시 시간순으로
        payload.append({'role': 'user' if h.role == 'user' else 'assistant',
                        'content': h.content})
    if len(picked) < len(history):
        logger.info(f"[프롬프트] 히스토리 {len(history)}건 중 {len(picked)}건만 포함 "
                    f"({used:,}자 / 예산 {hist_budget:,}자)")
    payload.append({'role': 'user', 'content': user_content})
    return payload


def finalize_conversation(conversation, user_content):
    conversation.last_message_at = timezone.now()
    if not conversation.title:
        conversation.title = user_content[:50]
    conversation.save()


def resolve_toggle(requested, conversation_value):
    """요청에 값이 있으면 그것, 없으면(None) 대화에 저장된 설정을 쓴다.

    시리얼라이저 default 를 None 으로 둔 이유와 한 쌍이다 — default 가 True/False 면
    키가 없어도 채워져서 대화 설정이 영영 반영되지 않는다.
    """
    return conversation_value if requested is None else bool(requested)


def project_label_for(payload):
    """검색 결과 payload → 사업명. 사업에 매이지 않는 문서(법령·지침)는 '공용'.

    리랭커 헤더와 **같은 매핑**을 쓴다. 두 곳이 서로 다른 이름을 쓰면 LLM 이 받는
    사업명과 검색이 쓴 사업명이 어긋난다.
    """
    if payload.get('is_global'):
        return '공용'
    pid = payload.get('project_id')
    if not pid:
        return '공용'
    try:
        from services.retriever import _project_label_map
        return _project_label_map().get(str(pid), '미상')
    except Exception as e:
        logger.debug(f"사업명 조회 실패: {e}")
        return '미상'


def has_attachment_text(conversation):
    """근거로 쓸 수 있는 첨부가 붙어 있는지 **싸게** 확인한다.

    '자료 없음' 단락 판정에 쓰인다. build_attachment_context()는 파일을 전부 읽으므로
    존재 여부만 알면 되는 자리에서는 쓰지 않는다.
    """
    return conversation.attachments.exclude(parsed_text_uri='').exists()


def build_attachment_context(conversation):
    """대화에 붙은 첨부파일들의 추출 텍스트를 컨텍스트 문자열로 만든다."""
    parts = []
    for att in conversation.attachments.all().order_by('created_at'):
        if not att.parsed_text_uri:
            continue
        path = os.path.join(settings.MEDIA_ROOT, att.parsed_text_uri.lstrip('/'))
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read(ATTACHMENT_TEXT_LIMIT)
        except OSError as e:
            logger.warning(f"첨부 텍스트를 읽지 못했습니다 ({att.filename}): {e}")
            continue
        if text.strip():
            parts.append(f"[첨부파일: {att.filename}]\n{text}")
    return "\n\n".join(parts)


class ConversationViewSet(viewsets.ModelViewSet):
    """대화 CRUD + 메시지 전송 API"""
    serializer_class = ConversationSerializer
    filterset_fields = ['project', 'is_shared']

    def get_queryset(self):
        # 고정된 대화가 맨 위, 그 다음 최근 대화 순.
        # Postgres는 DESC에서 NULL을 먼저 놓으므로, 아직 메시지가 없는 대화
        # (last_message_at IS NULL)가 목록 상단을 차지하지 않게 nulls_last를 준다.
        return Conversation.objects.order_by(
            '-is_pinned', F('last_message_at').desc(nulls_last=True), '-created_at'
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer

    @action(detail=True, methods=['post'], url_path='messages')
    def send_message(self, request, pk=None):
        """
        POST /api/conversations/{id}/messages
        사용자 질의 → Qdrant 하이브리드 검색 → LLM 답변 → 출처 저장 후 결과 반환
        """
        conversation = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_content = serializer.validated_data['content']
        use_docs = resolve_toggle(serializer.validated_data.get('use_internal_docs'),
                                  conversation.use_internal_docs)

        # 1. 사용자 메시지 저장
        user_msg = Message.objects.create(
            conversation=conversation,
            role='user',
            content=user_content,
            status='done',
        )

        sources_to_create = []
        context_text = ""
        rag_error = None

        # 2. RAG 파이프라인 작동 (use_docs가 참일 때)
        if use_docs:
            from services.retriever import retrieve_for_views
            from apps.documents.models import Document, DocumentChunk

            try:
                # A, B. LangChain 리랭킹 + Qdrant 하이브리드 통합 파이프라인 단일 호출
                project_id = conversation.project.id if conversation.project else None
                search_results = retrieve_for_views(
                    query=user_content,
                    project_id=project_id,
                    corpus_version=conversation.corpus_version or None,
                )

                # C. 검색된 청크 분석, 임계값 필터링 및 상한선 상위 K개 추출
                # search_results는 리랭커 순위대로 정렬되어 있으므로 순서를 유지한다.
                # (score는 Qdrant 점수이므로 이 값으로 재정렬하면 리랭킹이 무효가 된다.)
                passed_chunks = []
                for hit in search_results:
                    score = getattr(hit, 'score', 0.0)
                    if score >= settings.RAG_SIMILARITY_THRESHOLD:
                        passed_chunks.append(hit)

                # 상한선 적용
                final_chunks = passed_chunks[:settings.RAG_MAX_CONTEXT_K]

                # 디버그 로깅
                if getattr(settings, 'DEBUG_RAG', True):
                    import logging
                    rag_logger = logging.getLogger(__name__)
                    scores = [getattr(hit, 'score', 0.0) for hit in search_results]
                    rag_logger.info("=== [RAG DIAGNOSTIC START] ===")
                    rag_logger.info(f"1차 검색(Qdrant) 후보 수: {len(search_results)} (설정된 RETRIEVE_K: {settings.RAG_RETRIEVE_K})")
                    rag_logger.info(f"전체 후보 score 목록 (상위 5개): {scores[:5]}")
                    rag_logger.info(f"설정된 임계값 (THRESHOLD): {settings.RAG_SIMILARITY_THRESHOLD}")
                    rag_logger.info(f"임계값 필터 통과 개수: {len(passed_chunks)}")
                    rag_logger.info(f"상한(MAX_CONTEXT_K): {settings.RAG_MAX_CONTEXT_K}")
                    rag_logger.info(f"최종 컨텍스트 개수: {len(final_chunks)}")
                    rag_logger.info("=== [RAG DIAGNOSTIC END] ===")

                # 임계값을 넘는 조각이 하나도 없는 경우: 고정 응답 반환 및 차단
                #
                # 단, 첨부파일이 붙어 있으면 단락하지 않는다. 첨부는 코퍼스에 없는 새 파일이
                # 대부분이라 검색이 비는 것이 정상인데, 여기서 끊으면 **답이 되는 파일을
                # 읽어보지도 않고 거절**하게 된다("이 계약서 위약금 조항 정리해줘").
                # 첨부는 build_messages()에서 프롬프트에 붙는데 그 지점은 이 return 뒤에 있다.
                if len(final_chunks) == 0 and not has_attachment_text(conversation):
                    ai_msg = Message.objects.create(
                        conversation=conversation,
                        role='assistant',
                        content="관련 자료를 찾지 못했습니다.",
                        used_internal_docs=True,
                        model="none",
                        status='done',
                    )
                    conversation.last_message_at = timezone.now()
                    if not conversation.title:
                        conversation.title = user_content[:50]
                    conversation.save()
                    
                    msg_serializer = MessageSerializer(ai_msg)
                    return Response(msg_serializer.data, status=status.HTTP_201_CREATED)

                context_parts = []
                for idx, hit in enumerate(final_chunks):
                    # hit 데이터에서 payload 추출
                    payload = getattr(hit, 'payload', {}) or {}
                    chunk_id = payload.get('chunk_id')
                    score = getattr(hit, 'score', 0.0)

                    # DB 매핑 조회
                    try:
                        chunk = DocumentChunk.objects.get(qdrant_point_id=chunk_id)
                        doc = chunk.document
                        
                        # 위치 라벨은 format_location() 한 곳에서만 만든다.
                        # 여기 인라인 구현이 따로 남아 있어 스트리밍 경로와 값이 달랐다
                        # ("페이지 3 · 제5조" vs "p.3 · 제5조"). 같은 청크인데 어느
                        # 엔드포인트로 물었느냐에 따라 출처 표기가 갈렸다.
                        loc_lbl = format_location(chunk)

                        # 사업명을 박는다 — 파일명만으로는 어느 사업 문서인지 알 수 없어
                        # LLM 이 질문의 사업과 대조할 근거를 못 받는다(스트리밍 경로와 동일).
                        context_parts.append(
                            f"[참고자료 {idx+1}] [사업: {project_label_for(payload)}] "
                            f"{doc.title} ({loc_lbl})\n{chunk.content}"
                        )

                        # MessageSource 데이터 리스트업
                        short_lbl = doc.title[:4] + ".." if len(doc.title) > 5 else doc.title
                        sources_to_create.append(MessageSource(
                            document=doc,
                            document_chunk=chunk,
                            display_title=doc.original_filename or doc.title,
                            short_label=short_lbl,
                            page_number=chunk.page_number,
                            # loc_lbl과 같은 값을 쓴다. 여기도 인라인 구현이 따로 있어
                            # LLM에 준 위치와 화면 출처 칩의 위치가 서로 달랐다.
                            location_label=loc_lbl,
                            score=score,
                            rank=idx + 1,
                            snippet=chunk.content[:200]
                        ))
                    except (DocumentChunk.DoesNotExist, Document.DoesNotExist):
                        continue
                
                if context_parts:
                    context_text = "\n\n".join(context_parts)
            except Exception as e:
                import traceback
                import logging
                tb = traceback.format_exc()
                logging.getLogger(__name__).error(f"🚨 [RAG PIPELINE FATAL ERROR]\n{tb}")
                rag_error = str(e)

        # RAG 과정에서 치명적 예외가 발생한 경우: LLM 호출을 건너뛰고 에러 설명 본문과 함께 HTTP 500 반환
        if use_docs and rag_error:
            ai_msg = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=(
                    f"🚨 **사내 문서 검색(RAG) 엔진 오류**\n\n"
                    f"사내 문서를 검색하고 분석하는 과정에서 내부 시스템 예외가 발생했습니다.\n"
                    f"- **에러 유형**: `{rag_error}`\n\n"
                    f"자세한 기술 스택 트레이스백은 서버 에러 로그(`🚨 [RAG PIPELINE FATAL ERROR]`)를 참고하시기 바랍니다."
                ),
                used_internal_docs=True,
                status='failed',
                model="none",
            )
            conversation.last_message_at = timezone.now()
            conversation.save()
            msg_serializer = MessageSerializer(ai_msg)
            return Response(msg_serializer.data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. LLM API 프롬프트 구성 및 실행
        from services.llm import generate_response

        system_prompt = (
            "당신은 재생에너지(태양광/풍력) 분야의 전문 지식을 갖고 있는 사업개발실의 사내 AI 에이전트입니다.\n"
            "한국어로 친절하고 격식 있게 답변하십시오.\n"
        )
        # 첨부는 근거의 한 종류다. 아래 분기가 '근거가 없다'고 말하기 전에 먼저 확인해야
        # 첨부만 있는 경우에 "일반적인 지식으로 답하라"는 잘못된 지시가 나가지 않는다.
        attachment_text = build_attachment_context(conversation)

        if use_docs and context_text:
            system_prompt += (
                "주어진 [사내 참고 문서 내용]을 기반으로만 사용자의 질문에 대답하십시오.\n"
                "답변은 반드시 참고 자료의 사실에 근거해야 하며, 참고 자료에 없는 내용은 절대 지어내거나 가상의 수치, 예측값 등을 임의로 만들어 대답하지 마십시오.\n"
                "가설적인 추론이나 없는 사실을 꾸며내는 행위는 완전히 금지됩니다.\n"
                "자료가 부족해 정확한 대답을 할 수 없다면 솔직히 모른다고 답변하십시오.\n"
                "각 참고자료 앞의 [사업: X]가 질문의 사업과 일치하는지 먼저 확인하십시오. "
                "일치하는 자료가 하나도 없으면 추정하지 말고 해당 사업 자료를 찾지 못했다고 밝히십시오. "
                "다른 사업의 자료를 근거로 쓸 때는 어느 사업 문서인지 반드시 함께 밝히십시오.\n\n"
                f"[사내 참고 문서 내용]\n{context_text}"
            )
        elif attachment_text:
            # 사내 검색은 비었지만 첨부가 있는 경우. 근거는 첨부 하나다.
            system_prompt += (
                "사내 문서에서는 관련 자료를 찾지 못했습니다. 아래 [첨부파일 내용]만을 근거로 "
                "답변하고, 첨부파일에 없는 내용은 지어내지 마십시오.\n"
                "첨부파일로도 답할 수 없으면 솔직히 모른다고 답변하십시오."
            )
        else:
            system_prompt += "사내 문서 참조 모드가 꺼져있거나 제공된 참고 자료가 없습니다. 일반적인 지식 범주에서 답변하십시오."

        # 사용자가 이 대화에 첨부한 파일의 내용 (C-6)
        # 사내 문서 참조 토글과 무관하게, 사용자가 직접 올린 자료이므로 항상 제공한다.
        if attachment_text:
            system_prompt += (
                "\n\n사용자가 이 대화에 파일을 첨부했습니다. 아래 [첨부파일 내용]도 "
                "함께 근거로 사용하십시오. 첨부파일에 없는 내용을 지어내지 마십시오.\n\n"
                f"[첨부파일 내용]\n{attachment_text}"
            )

        # 이전 대화 히스토리 구성 (최근 10개)
        # 방금 저장한 user_msg는 아래에서 따로 추가하므로 여기서 제외한다.
        messages_payload = [{'role': 'system', 'content': system_prompt}]
        history_msgs = list(
            conversation.messages
            .filter(status='done')
            .exclude(id=user_msg.id)
            .order_by('-created_at')[:10]
        )
        for h_msg in reversed(history_msgs):
            messages_payload.append({
                'role': 'user' if h_msg.role == 'user' else 'assistant',
                'content': h_msg.content
            })

        # 최신 질문 추가
        messages_payload.append({'role': 'user', 'content': user_content})

        # LLM 응답 생성
        llm_model = resolve_llm_model(
            conversation, serializer.validated_data.get('llm_model', ''))
        llm_res = generate_response(messages=messages_payload, model=llm_model)

        # 4. AI 응답 메시지 생성
        # 참조 청크의 유사도·출처·위치·스니펫은 응답의 sources 배열로 전달된다.
        ai_content = llm_res['content']

        ai_msg = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_content,
            used_internal_docs=use_docs and len(sources_to_create) > 0,
            model=llm_res.get('model', llm_model),
            token_usage=llm_res.get('usage'),
            status='done',
        )

        # 5. 출처(Sources) DB 영속화
        for src in sources_to_create:
            src.message = ai_msg
            src.save()

        # 6. 대화 마지막 시간 및 제목 업데이트
        conversation.last_message_at = timezone.now()
        if not conversation.title:
            conversation.title = user_content[:50]
        conversation.save()

        # 7. 직렬화 반환
        msg_serializer = MessageSerializer(ai_msg)
        return Response(msg_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='messages/stream')
    def stream_message(self, request, pk=None):
        """POST /api/conversations/{id}/messages/stream — SSE 스트리밍 응답

        이벤트: status(진행 단계) → sources(출처) → delta(본문 조각)* → done / error
        총 소요는 비스트리밍과 같지만 첫 글자가 1~2초 안에 나오고, 검색 단계가
        실시간으로 표시되어 체감 대기가 크게 줄어든다.
        """
        conversation = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_content = serializer.validated_data['content']
        use_docs = resolve_toggle(serializer.validated_data.get('use_internal_docs'),
                                  conversation.use_internal_docs)
        use_web = resolve_toggle(serializer.validated_data.get('use_web_search'),
                                 conversation.use_web_search)

        user_msg = Message.objects.create(
            conversation=conversation, role='user', content=user_content, status='done')

        def sse(event, data):
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        def stream():
            from concurrent.futures import ThreadPoolExecutor

            from services.llm import generate_response_stream
            from services.web_search import is_available

            # 웹 검색은 사내 검색과 **병렬**로 던진다. 순차로 하면 2~3초가 그대로 더해진다.
            # (웹 검색은 ORM을 쓰지 않으므로 스레드에서 안전하다)
            web_sources, web_text = [], ''
            pool = fut_web = None
            web_ok, web_reason = is_available()
            if use_web and web_ok:
                pool = ThreadPoolExecutor(max_workers=1)
                fut_web = pool.submit(run_web_search, user_content)
            elif use_web:
                logger.info(f"웹 검색 요청됐으나 사용 불가: {web_reason}")

            sources, context_text, rag_error, no_hit = [], '', None, False
            if use_docs:
                yield sse('status', {'stage': 'searching', 'message': '사내 자료를 검색하고 있습니다'})
                sources, context_text, rag_error, no_hit = run_rag(conversation, user_content)

                if rag_error:
                    if pool:
                        pool.shutdown(wait=False)
                    content = (f"🚨 **사내 문서 검색(RAG) 엔진 오류**\n\n"
                               f"- **에러 유형**: `{rag_error}`\n\n서버 로그를 확인해 주세요.")
                    Message.objects.create(conversation=conversation, role='assistant',
                                           content=content, used_internal_docs=True,
                                           status='failed', model='none')
                    finalize_conversation(conversation, user_content)
                    yield sse('error', {'message': content})
                    return

            # 병렬로 돌던 웹 검색 결과 수거
            if fut_web is not None:
                yield sse('status', {'stage': 'web', 'message': '웹을 검색하고 있습니다'})
                try:
                    web_sources, web_text, _ = fut_web.result(timeout=20)
                except Exception as e:
                    logger.warning(f"웹 검색 결과 수거 실패(사내 근거만 사용): {e}")
                finally:
                    pool.shutdown(wait=False)

            # 사내에도 없고 웹 근거도 첨부도 없으면 여기서 끝낸다.
            # 웹 근거가 있으면 사내가 비어도 답변을 시도한다(사용자가 웹을 켠 경우).
            # 첨부도 마찬가지다 — 첨부는 코퍼스에 없는 새 파일이 대부분이라 검색이 비는 것이
            # 정상인데, 여기서 끊으면 **답이 되는 파일을 읽어보지도 않고 거절**하게 된다.
            # (첨부는 build_messages()에서 붙는데 그 호출은 이 return 뒤에 있다.)
            if use_docs and no_hit and not web_text and not has_attachment_text(conversation):
                content = "관련 자료를 찾지 못했습니다."
                msg = Message.objects.create(conversation=conversation, role='assistant',
                                             content=content, used_internal_docs=True,
                                             model='none', status='done')
                finalize_conversation(conversation, user_content)
                yield sse('delta', {'text': content})
                yield sse('done', {'message_id': str(msg.id), 'sources': []})
                return

            # 출처는 LLM 생성 전에 확정되므로 먼저 보낸다 (UI가 근거를 즉시 표시).
            # kind로 사내/웹을 구분해 프론트가 배지를 다르게 칠할 수 있게 한다.
            if sources or web_sources:
                yield sse('sources', {'sources': [
                    {'kind': 'internal',
                     'short_label': s.short_label, 'display_title': s.display_title,
                     'page_number': s.page_number, 'location_label': s.location_label,
                     'score': s.score, 'rank': s.rank, 'snippet': s.snippet,
                     'document_id': str(s.document_id),
                     # 쪽번호는 붙이지 않는다 — 이유는 MessageSourceSerializer.get_open_url 주석 참조.
                     # (두 경로가 같은 URL을 만들어야 한다. 예전에는 여기만 고치고 직렬화기를
                     #  빠뜨려 스트리밍과 비스트리밍의 출처 링크가 달랐다.)
                     'open_url': f'/api/documents/{s.document_id}/file/'}
                    for s in sources
                ] + [
                    {'kind': 'web',
                     'short_label': w['domain'][:14], 'display_title': w['title'] or w['domain'],
                     'location_label': ' · '.join(x for x in (w['domain'], w['published']) if x),
                     'score': w['score'], 'rank': w['rank'], 'snippet': w['snippet'][:200],
                     'open_url': w['url']}
                    for w in web_sources
                ]})

            yield sse('status', {'stage': 'generating', 'message': '답변을 작성하고 있습니다'})
            messages_payload = build_messages(conversation, user_msg, user_content,
                                              use_docs, context_text, web_text=web_text)
            llm_model = resolve_llm_model(
            conversation, serializer.validated_data.get('llm_model', ''))

            parts, usage = [], {}
            try:
                for ev in generate_response_stream(messages=messages_payload, model=llm_model):
                    if ev['type'] == 'delta':
                        parts.append(ev['text'])
                        yield sse('delta', {'text': ev['text']})
                    elif ev['type'] == 'usage':
                        usage = ev.get('usage') or {}
            except Exception as e:
                logger.error(f"LLM 스트리밍 실패: {e}")
                # [M-2] 여기까지 생성된 내용을 버리지 않는다.
                # 타임아웃·연결 끊김이 실제로 발생하고 있고, 예전에는 부분 답변이
                # 통째로 사라져 사용자가 처음부터 다시 질문해야 했다.
                partial = ''.join(parts)
                msg_id = None
                if partial.strip():
                    partial_msg = Message.objects.create(
                        conversation=conversation, role='assistant',
                        content=partial + '\n\n⚠️ *생성이 중단되었습니다 (연결 오류). 위 내용은 중단 시점까지의 답변입니다.*',
                        used_internal_docs=bool(use_docs and sources),
                        model=llm_model, status='partial',
                        web_sources=web_sources or None)
                    for s in sources:
                        s.message = partial_msg
                        s.save()
                    msg_id = str(partial_msg.id)
                finalize_conversation(conversation, user_content)
                # 이미 200으로 스트림이 시작돼 HTTP 오류를 보낼 수 없으므로 error 이벤트로 알린다
                yield sse('error', {'message': f'답변 생성 중 오류가 발생했습니다: {e}',
                                    'partial_saved': bool(msg_id), 'message_id': msg_id})
                return

            content = ''.join(parts)
            ai_msg = Message.objects.create(
                conversation=conversation, role='assistant', content=content,
                used_internal_docs=bool(use_docs and sources),
                model=llm_model, token_usage=usage, status='done',
                web_sources=web_sources or None)
            for s in sources:
                s.message = ai_msg
                s.save()
            finalize_conversation(conversation, user_content)
            yield sse('done', {'message_id': str(ai_msg.id),
                               'used_internal_docs': bool(use_docs and sources),
                               'used_web_search': bool(web_sources)})

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'   # 프록시 버퍼링 방지 (조각이 즉시 전달되도록)
        return response

    @action(detail=True, methods=['get', 'post'], url_path='attachments',
            parser_classes=[MultiPartParser, FormParser])
    def attachments(self, request, pk=None):
        """GET/POST /api/conversations/{id}/attachments — 대화 첨부파일 (C-6)

        업로드한 파일은 파싱해 텍스트만 뽑아 두고, 이 대화의 질의에서만 컨텍스트로 쓴다.
        Qdrant에는 넣지 않는다(일회성 자료로 사내 코퍼스를 오염시키지 않기 위해).
        """
        conversation = self.get_object()

        if request.method == 'GET':
            qs = conversation.attachments.all().order_by('created_at')
            return Response(MessageAttachmentSerializer(qs, many=True).data)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'file 필드가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(uploaded.name)[1].lower().lstrip('.')
        if ext not in ALLOWED_ATTACHMENT_EXTS:
            return Response(
                {'error': f'지원하지 않는 형식입니다: .{ext} '
                          f'(가능: {", ".join(sorted(ALLOWED_ATTACHMENT_EXTS))})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 저장 파일명은 UUID로 만든다. 사용자 파일명을 경로에 쓰면 경로 탈출 위험이 있다.
        att_id = uuid.uuid4()
        rel_dir = 'attachments'
        abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        stored_name = f'{att_id}.{ext}'
        abs_path = os.path.join(abs_dir, stored_name)
        with open(abs_path, 'wb+') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        # 파싱 → 텍스트 추출 (실패해도 첨부 자체는 남긴다)
        parsed_rel = ''
        try:
            from services.parser import parse_file
            items = parse_file(abs_path) or []
            text = "\n".join((it.get('text') or '') for it in items).strip()
            if text:
                parsed_rel = f'{rel_dir}/{att_id}.txt'
                with open(os.path.join(settings.MEDIA_ROOT, parsed_rel), 'w',
                          encoding='utf-8') as f:
                    f.write(text)
            else:
                logger.warning(f"첨부에서 추출된 텍스트가 없습니다: {uploaded.name}")
        except Exception as e:
            logger.error(f"첨부 파싱 실패 ({uploaded.name}): {e}", exc_info=True)

        att = MessageAttachment.objects.create(
            id=att_id,
            conversation=conversation,
            filename=uploaded.name,
            file_type=ext,
            storage_uri=f'{settings.MEDIA_URL}{rel_dir}/{stored_name}',
            file_size=uploaded.size,
            parsed_text_uri=parsed_rel,
        )
        data = MessageAttachmentSerializer(att).data
        data['parsed'] = bool(parsed_rel)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        """POST /api/conversations/{id}/share — 공용 프로젝트로 반출"""
        conversation = self.get_object()
        payload = {
            'conversation': str(conversation.id),
            'shared_to_project': request.data.get('shared_to_project_id'),
            'share_type': request.data.get('share_type', 'copy'),
        }
        # 누가 반출했는지 기록한다. 인증된 사용자가 있으면 그 사용자를 남긴다.
        if request.user and request.user.is_authenticated:
            payload['shared_by'] = str(request.user.id)

        serializer = ConversationShareSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        conversation.is_shared = True
        conversation.save(update_fields=['is_shared'])

        return Response(serializer.data, status=status.HTTP_201_CREATED)
