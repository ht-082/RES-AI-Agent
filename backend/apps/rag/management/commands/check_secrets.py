"""비밀 설정을 **노출하지 않고** 점검한다.

`cat .env` 를 하면 키가 화면·터미널 기록·스크린샷에 그대로 남는다.
설정이 제대로 들어갔는지 확인하는 데 그럴 필요가 없다. 이 명령은
'설정됨/비어있음'과 지문(앞 4자 + 길이 + 해시 앞 6자)만 보여준다.

지문은 **같은 키인지 비교**하는 용도다. 예를 들어 두 파일의 키가 같은지,
교체 후 실제로 바뀌었는지를 값 노출 없이 확인할 수 있다.

사용:
  python manage.py check_secrets
"""
import hashlib
import os

from django.conf import settings
from django.core.management.base import BaseCommand

# (설정명, 필수 여부, 설명)
SECRETS = [
    ('DJANGO_SECRET_KEY', True, '세션 서명 키'),
    ('LLM_API_KEY', True, '답변 생성 (OpenAI)'),
    ('TAVILY_API_KEY', False, '웹 검색 (꺼져 있으면 불필요)'),
    ('EMBEDDING_API_KEY', False, 'api 모드에서만 필요. cpu 모드면 비어 있는 게 정상'),
    ('POSTGRES_PASSWORD', False, 'DB (컨테이너 내부 전용)'),
]

PLAIN = [
    ('DEBUG', '운영에서는 False'),
    ('ALLOWED_HOSTS', "'*' 금지"),
    ('CORS_ALLOWED_ORIGINS', '쿠키 인증의 유일한 방어선'),
    ('EMBEDDING_DEVICE', 'cpu 여야 sparse 검색이 동작'),
    ('TAVILY_ENABLED', '웹 검색 전역 킬스위치'),
    ('TAVILY_AUTO_FALLBACK', 'False 유지 권장'),
]


def fingerprint(value):
    """값을 드러내지 않는 지문. 같은 키인지 비교할 수 있을 만큼만."""
    if not value:
        return ''
    digest = hashlib.sha256(value.encode()).hexdigest()[:6]
    return f'{value[:4]}… len={len(value)} #{digest}'


class Command(BaseCommand):
    help = '비밀 설정을 값 노출 없이 점검한다.'

    def handle(self, *args, **options):
        self.stdout.write('비밀 설정 (값은 표시하지 않습니다)')
        self.stdout.write('-' * 74)

        missing = []
        for name, required, note in SECRETS:
            value = getattr(settings, name, None) or os.getenv(name, '')
            if value:
                mark = self.style.SUCCESS('설정됨')
                detail = fingerprint(value)
            elif required:
                mark = self.style.ERROR('없음  ')
                detail = '⚠ 필수'
                missing.append(name)
            else:
                mark = self.style.WARNING('비어둠')
                detail = ''
            self.stdout.write(f'  {mark}  {name:<22}{detail}')
            if note:
                self.stdout.write(f'          └ {note}')

        self.stdout.write('')
        self.stdout.write('일반 설정')
        self.stdout.write('-' * 74)
        for name, note in PLAIN:
            self.stdout.write(f'  {name:<24}{getattr(settings, name, "(없음)")}')
            self.stdout.write(f'          └ {note}')

        self.stdout.write('')
        self.stdout.write('키 단일 출처 점검')
        self.stdout.write('-' * 74)
        # 컨테이너 환경변수가 backend/.env(load_dotenv)보다 우선한다.
        # 양쪽에 키가 있으면 어느 값이 쓰이는지 헷갈리므로 중복을 잡아낸다.
        for name in ('LLM_API_KEY', 'TAVILY_API_KEY'):
            from_env = os.environ.get(name)
            effective = getattr(settings, name, '')
            if from_env and effective and from_env != effective:
                self.stdout.write(self.style.ERROR(
                    f'  ⚠ {name}: 컨테이너 환경변수와 .env 값이 다릅니다 — '
                    f'환경변수({fingerprint(from_env)})가 이깁니다'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  OK {name}: 출처 충돌 없음'))

        self.stdout.write('')
        if missing:
            self.stdout.write(self.style.ERROR(f'필수 항목 누락: {", ".join(missing)}'))
        else:
            self.stdout.write(self.style.SUCCESS('필수 항목 모두 설정됨'))
