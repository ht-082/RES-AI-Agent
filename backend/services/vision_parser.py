import os
import time
import base64
import logging
from io import BytesIO
from pdf2image import convert_from_path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

def encode_image_to_base64(image):
    """PIL Image 객체를 JPEG Base64 문자열로 변환"""
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def parse_with_vision_api(file_path):
    """
    스캔본 PDF 문서를 이미지로 변환한 뒤, Vision API를 통해 텍스트를 추출하는 폴백 함수.
    """
    logger.info(f"Vision API 기반 파싱 시작: {file_path}")
    pages_data = []
    
    # 1. PDF를 이미지 리스트로 변환 (DPI 200 수준으로 타협하여 토큰/비용 절감)
    try:
        images = convert_from_path(file_path, dpi=200)
    except Exception as e:
        logger.error(f"PDF를 이미지로 변환 실패 ({file_path}): {e}")
        return pages_data
        
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

    # 2. 각 페이지별로 Vision API 호출
    for page_idx, image in enumerate(images):
        time.sleep(2)  # 페이지 당 요청 속도 강제 조절 (RPM 한도 회피)
        base64_image = encode_image_to_base64(image)
        
        payload = {
            "model": "gpt-4o-mini", # 비용 효율과 속도를 위해 4o-mini 우선 적용
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
            "max_tokens": 2000
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
                    'page_number': page_idx + 1,
                    'section_title': f"페이지 {page_idx + 1} (Vision 추출본)",
                    'sheet_name': '',
                    'cell_range': ''
                })
                logger.info(f"Vision API 추출 성공: 페이지 {page_idx + 1}")
        except Exception as e:
            logger.error(f"Vision API 요청 실패 (페이지 {page_idx + 1}): {e}")
            
    return pages_data
