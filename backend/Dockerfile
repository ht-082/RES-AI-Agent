FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies
# poppler-utils: pdf2image(스캔본 Vision OCR)
# antiword·catdoc: 레거시 Word(.doc) 텍스트 추출.
#   코퍼스에 확장자만 .docx인 실체 .doc 파일이 4건 있었고 전부 파싱 불가였다.
#   python-docx는 OOXML만 읽으므로 외부 도구가 필요하다. (services/parser.parse_doc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    antiword \
    catdoc \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
