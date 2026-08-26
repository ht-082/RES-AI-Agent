"""
LLM 어댑터 — 기 개발 LLM API 연동
OpenAI 호환 API 형식으로 추상화
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_llm_client():
    """LLM API 클라이언트 반환 (OpenAI 호환)"""
    from openai import OpenAI

    import httpx
    # verify=False: 사내망 SSL 검사 우회.
    # timeout을 반드시 함께 지정한다 — httpx.Client()의 기본값은 5초이고, 이 커스텀
    # 클라이언트를 넘기는 순간 OpenAI SDK 기본 타임아웃(600초)이 5초로 덮어써진다.
    # 비스트리밍은 4초대라 아슬아슬하게 통과했지만, 스트리밍은 응답이 끝날 때까지
    # 연결을 유지하므로 5초에 끊겨 'Request timed out'이 발생했다.
    timeout = httpx.Timeout(
        getattr(settings, 'LLM_TIMEOUT', 180.0),   # 전체 응답 대기
        connect=10.0,                              # 연결 수립
    )
    client = OpenAI(
        base_url=settings.LLM_API_BASE,
        api_key=settings.LLM_API_KEY or 'no-key',
        http_client=httpx.Client(verify=False, timeout=timeout),
    )
    return client


def build_completion_kwargs(model, temperature, max_tokens):
    """모델 세대에 맞는 호출 파라미터를 만든다.

    신형 모델(gpt-5 계열 등)은 `max_tokens` 대신 `max_completion_tokens`를 받고,
    `temperature` 커스텀 값을 거부하는 경우가 있다. 모델명으로 미리 갈라내면
    새 모델이 나올 때마다 코드를 고쳐야 하므로, 여기서는 신형 규격을 기본으로 두고
    호출측이 400 응답을 보고 구형 규격으로 1회 재시도한다(_create_with_fallback).
    """
    return {'model': model, 'max_completion_tokens': max_tokens,
            'temperature': temperature}


def _create_with_fallback(client, messages, kwargs, stream=False):
    """신형 규격으로 호출하고, 규격 오류가 나면 구형 규격으로 한 번 재시도한다."""
    from openai import BadRequestError

    call = dict(kwargs)
    if stream:
        call.update(stream=True, stream_options={'include_usage': True})
    try:
        return client.chat.completions.create(messages=messages, **call)
    except BadRequestError as e:
        detail = str(e)
        retry = dict(call)
        changed = []
        # 구형 모델: max_completion_tokens 미지원 → max_tokens
        if 'max_completion_tokens' in detail and 'max_completion_tokens' in retry:
            retry['max_tokens'] = retry.pop('max_completion_tokens')
            changed.append('max_tokens')
        # 일부 신형 모델: temperature 커스텀 값 거부 → 기본값 사용
        if 'temperature' in detail and 'temperature' in retry:
            retry.pop('temperature')
            changed.append('temperature 제거')
        if not changed:
            raise
        logger.info(f"모델 파라미터 규격 조정 후 재시도: {', '.join(changed)} "
                    f"(model={call.get('model')})")
        return client.chat.completions.create(messages=messages, **retry)


def generate_response(messages, model='default', temperature=0.3, max_tokens=4096):
    """
    LLM 답변 생성
    messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
    """
    client = get_llm_client()

    try:
        response = _create_with_fallback(
            client, messages, build_completion_kwargs(model, temperature, max_tokens))
        return {
            'content': response.choices[0].message.content,
            'model': response.model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                'total_tokens': response.usage.total_tokens if response.usage else 0,
            }
        }
    except Exception as e:
        logger.error(f"LLM API 호출 실패: {e}")
        raise


def generate_response_stream(messages, model='default', temperature=0.3, max_tokens=4096):
    """LLM 답변을 토큰 단위로 흘려보낸다 (SSE용).

    총 소요 시간은 비스트리밍과 같지만 첫 글자가 1~2초 안에 나오므로 체감이 크게 다르다.
    호출측은 yield된 조각을 이어붙여 최종 본문을 만든다.
    """
    client = get_llm_client()
    stream = _create_with_fallback(
        client, messages, build_completion_kwargs(model, temperature, max_tokens),
        stream=True)
    usage = None
    for chunk in stream:
        if getattr(chunk, 'usage', None):
            u = chunk.usage
            usage = {
                'prompt_tokens': u.prompt_tokens,
                'completion_tokens': u.completion_tokens,
                'total_tokens': u.total_tokens,
            }
        for choice in (chunk.choices or []):
            piece = getattr(choice.delta, 'content', None)
            if piece:
                yield {'type': 'delta', 'text': piece}
    yield {'type': 'usage', 'usage': usage or {}}


def generate_contract_draft(template_body, key_terms, instructions=''):
    """계약서 초안 생성을 위한 LLM 호출"""
    system_prompt = (
        "당신은 재생에너지 분야의 법무 전문가입니다. "
        "주어진 표준 계약서 양식과 핵심 조건(Key-term)을 바탕으로 "
        "한국어 계약서 초안을 작성합니다. "
        "각 조항은 명확하고 법적으로 유효한 표현을 사용해야 합니다."
    )

    user_prompt = f"""## 표준 양식
{template_body}

## 핵심 조건 (Key-term)
{key_terms}

{f'## 추가 지시사항{chr(10)}{instructions}' if instructions else ''}

위 정보를 바탕으로 완성된 계약서 초안을 작성해주세요."""

    return generate_response([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ], max_tokens=8192)


def review_contract(contract_text, checklist, instruction=''):
    """계약서 검토를 위한 LLM 호출"""
    system_prompt = (
        "당신은 재생에너지 분야의 법무 검토 전문가입니다. "
        "주어진 계약서를 검토하고, 조항별로 위험도(독소/불리/누락/오류)를 평가하여 "
        "JSON 형식의 검토 결과를 반환합니다."
    )

    user_prompt = f"""## 검토 대상 계약서
{contract_text}

## 검토 체크리스트
{checklist}

{f'## 검토 지시사항{chr(10)}{instruction}' if instruction else ''}

다음 JSON 형식으로 검토 결과를 반환해주세요:
[
  {{
    "clause_ref": "조항 위치 (예: 제12조)",
    "severity": "high/mid/low",
    "category": "독소조항/불리조항/누락/오류",
    "finding": "지적 내용",
    "suggestion": "수정 방향"
  }}
]"""

    return generate_response([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ], max_tokens=8192)


def generate_structured_contract(type_id, inputs, article_structure, system_prompt):
    """
    구조화된 계약서 초안을 지정된 JSON 형식으로 완벽하게 생성합니다.
    """
    import json
    # 사용자 입력 Key-term 목록 포맷팅
    key_terms_str = "\n".join([f"- {k}: {v}" for k, v in inputs.items() if v])
    
    # 조항 골격 문자열
    structure_str = ", ".join(article_structure)

    full_system_prompt = (
        f"{system_prompt}\n\n"
        "지침:\n"
        "1. 반드시 아래에 지정된 조항 구조(article_structure)의 순서와 형식을 엄격히 유지하십시오.\n"
        f"   지정된 조항 구조: {structure_str}\n"
        "2. 사용자가 입력한 Key-term들을 본문 조항 내용에 반영하여 서술하십시오.\n"
        "3. 사용자가 직접 값을 입력하지 않은 조항은 대한민국 표준 재생에너지 전력 거래 관행에 따른 일반적이고 상식적인 표준 문안으로 상세하게 작성하십시오.\n"
        "4. custom_terms(기타 관철 조건)에 입력된 자유 문장들이 어느 조항에 반영되었는지를 찾아내어, 'mapping_note' 필드에 구체적인 요약을 포함시켜야 합니다 (예: '위약금 상한 -> 제6조에 반영').\n"
        "5. 이 문서는 법률 대리인의 정식 법률 자문이 아닌 계약서 초안 작성 시스템의 임시 초안 AI 생성물임을 본문에 전제로 명시하거나 상기하십시오.\n"
        "6. 응답은 반드시 아래의 JSON 스키마 포맷만 준수하여 반환해야 합니다. 다른 텍스트 설명이나 markdown 코드 펜스(```)를 붙이지 마십시오."
    )

    user_prompt = f"""## 사용자 입력 핵심 조건 (Key-terms)
{key_terms_str}

## 최종 반환 스키마 (JSON)
{{
  "title": "전력판매계약서 (Power Purchase Agreement)",
  "articles": [
    {{
      "no": "전문",
      "heading": null,
      "content": "전문 내용..."
    }},
    {{
      "no": "제1조",
      "heading": "목적",
      "content": "제1조의 구체적인 내용..."
    }},
    ...
  ],
  "mapping_note": "custom_terms 반영 현황 요약 정보 (예: '지체상금율 한도 설정 -> 제6조에 반영')"
}}"""

    from django.conf import settings
    model = settings.LLM_MODEL
    client = get_llm_client()
    try:
        kwargs = build_completion_kwargs(model, 0.3, 8192)
        kwargs['response_format'] = {"type": "json_object"}
        response = _create_with_fallback(
            client,
            [{'role': 'system', 'content': full_system_prompt},
             {'role': 'user', 'content': user_prompt}],
            kwargs)
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Structured contract generation failed: {e}")
        return {
            "title": "계약서 초안 생성 오류",
            "articles": [{"no": "오류", "heading": "알림", "content": "계약서 생성 중 API 장애가 발생했습니다."}],
            "mapping_note": f"에러 로그: {str(e)}"
        }
