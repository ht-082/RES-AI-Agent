import os
import time
import base64
import logging
from io import BytesIO
from django.conf import settings   # LLM_VISION_MODEL 참조 (누락 시 OCR 전량 NameError)
from pdf2image import convert_from_path, pdfinfo_from_path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

def encode_image_to_base64(image):
    """PIL Image 객체를 JPEG Base64 문자열로 변환"""
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def _audit_external_send(file_path, pages, model, api_base, ok_pages, note=''):
    """외부 OCR 전송 대장 [보안].

    스캔본은 페이지 **이미지**(도장·서명 포함)가 그대로 외부 API로 나간다.
    무엇이 언제 어디로 나갔는지를 우리 쪽에 남겨야, 나중에 보안·컴플라이언스
    질문("계약서 날인본을 외부로 보냈나?")에 목록으로 답할 수 있다.
    media에 두는 이유: 호스트 바인드 마운트라 컨테이너를 재생성해도 남는다.
    """
    import csv
    from datetime import datetime, timezone as tz
    path = os.path.join(os.getenv('MEDIA_ROOT', '/app/media'), 'ocr_전송대장.csv')
    new = not os.path.exists(path)
    try:
        with open(path, 'a', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(['전송시각(UTC)', '파일', '전송페이지수', '성공페이지수',
                            '수신처', '모델', '목적'])
            w.writerow([datetime.now(tz.utc).strftime('%Y-%m-%d %H:%M:%S'),
                        os.path.basename(file_path), pages, ok_pages,
                        api_base, model,
                        'OCR(스캔본 텍스트 추출)' + (' · ' + note if note else '')])
    except OSError as e:
        logger.warning(f"OCR 전송대장 기록 실패(전송은 정상): {e}")


def parse_with_vision_api(file_path):
    """
    스캔본 PDF 문서를 이미지로 변환한 뒤, Vision API를 통해 텍스트를 추출하는 폴백 함수.
    """
    logger.info(f"Vision API 기반 파싱 시작: {file_path}")
    pages_data = []

    # 1. 페이지 수만 먼저 확인한다.
    #
    #    전 페이지를 한 번에 변환하면(convert_from_path(dpi=200) 단독 호출) 결과
    #    PIL 이미지가 전부 메모리에 남는다. 실측: 92페이지 A3 도면이 약 2.1GB,
    #    365페이지 대출약정서가 약 4.2GB로 컨테이너가 OOM으로 죽었다.
    #    페이지 단위로 변환하면 상주 메모리가 한 장치(약 25MB)로 고정된다.
    try:
        total_pages = pdfinfo_from_path(file_path)['Pages']
    except Exception as e:
        logger.error(f"PDF 페이지 수 확인 실패 ({file_path}): {e}")
        return pages_data

    max_pages = getattr(settings, 'VISION_OCR_MAX_PAGES', 400)
    target_pages = min(total_pages, max_pages)
    truncated = total_pages - target_pages
    if truncated > 0:
        # 잘라낸 사실을 반드시 드러낸다. 조용히 줄이면 "전량 처리됨"으로 오독된다.
        logger.warning(
            f"OCR 페이지 상한 적용: {os.path.basename(file_path)} "
            f"{total_pages}p 중 {target_pages}p만 처리(뒤 {truncated}p 누락). "
            f"VISION_OCR_MAX_PAGES로 조정 가능."
        )

    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE', 'https://api.openai.com/v1')
    
    if not api_key:
        logger.error("LLM_API_KEY가 설정되지 않아 Vision API를 호출할 수 없습니다.")
        return pages_data
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # API 호출 전담 헬퍼 함수 (429 등 오류 발생 시 점진적 대기 후 재시도)
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=2, min=4, max=20),
        stop=stop_after_attempt(4),
        reraise=True
    )
    def call_vision_api(api_url, req_headers, json_payload):
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(api_url, headers=req_headers, json=json_payload)
            resp.raise_for_status()  # 429 Too Many Requests 등 에러 시 예외 발생 -> retry
            return resp

    # 2. 각 페이지별로 변환 → 즉시 호출 → 폐기 (메모리 상주분을 1페이지로 고정)
    for page_idx in range(target_pages):
        page_no = page_idx + 1
        try:
            rendered = convert_from_path(file_path, dpi=200,
                                         first_page=page_no, last_page=page_no)
        except Exception as e:
            logger.error(f"PDF 페이지 변환 실패 ({file_path} p{page_no}): {e}")
            continue
        if not rendered:
            continue
        image = rendered[0]

        time.sleep(2)  # 페이지 당 요청 속도 강제 조절 (RPM 한도 회피)
        base64_image = encode_image_to_base64(image)
        image.close()

        payload = {
            # 답변 생성 모델과 분리한다. OCR은 이미지 입력이 필요하고 적재 시에만
        # 쓰이므로 비용 특성이 다르다. settings.LLM_VISION_MODEL 로 조정한다.
        "model": settings.LLM_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "다음 문서 이미지에 있는 모든 텍스트를 있는 그대로 정확하게 추출해 주세요. 표가 있다면 마크다운 표 형식으로 유지하고, 불필요한 설명은 제외한 순수 내용만 출력하세요."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            # gpt-5.x(terra 등)는 추론 모델이라 'max_tokens'를 거부하고
            # 'max_completion_tokens'만 받는다. 게다가 이 예산에서 추론 토큰이
            # 먼저 소진되므로(실측: 페이지당 300~500), 출력이 잘리지 않게 넉넉히 준다.
            # 2000이면 조밀한 페이지에서 추론이 예산을 다 먹어 본문이 빈 채로 200 응답이 온다.
            "max_completion_tokens": 4000
        }
        
        try:
            response = call_vision_api(f"{api_base}/chat/completions", headers, payload)
            result = response.json()
            extracted_text = result['choices'][0]['message']['content'].strip()
            
            # 마크다운 코드 블록(```markdown ... ```)이 반환될 경우 제거
            if extracted_text.startswith("```"):
                lines = extracted_text.split('\n')
                if len(lines) > 2:
                    extracted_text = "\n".join(lines[1:-1]).strip()
            
            if extracted_text:
                pages_data.append({
                    'text': extracted_text,
                    'page_number': page_no,
                    'section_title': f"페이지 {page_no} (Vision 추출본)",
                    'sheet_name': '',
                    'cell_range': ''
                })
                logger.info(f"Vision API 추출 성공: 페이지 {page_no}")
        except Exception as e:
            logger.error(f"Vision API 요청 실패 (페이지 {page_no}): {e}")

    _audit_external_send(file_path, pages=target_pages,
                         model=settings.LLM_VISION_MODEL,  # 실제 호출값(위 120행)과 일치
                         api_base=api_base, ok_pages=len(pages_data),
                         note=(f'상한 적용: 전체 {total_pages}p 중 뒤 {truncated}p 누락'
                               if truncated > 0 else ''))
    return pages_data
