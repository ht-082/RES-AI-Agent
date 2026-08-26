"""현재 API 키로 쓸 수 있는 모델 목록을 조회한다.

모델명을 추측해서 .env에 넣으면 호출 시점에야 404가 나서 원인을 찾기 어렵다.
바꾸기 전에 이 명령으로 실제 사용 가능 여부를 확인한다.

사용:
  python manage.py list_models
  python manage.py list_models --filter gpt-5
  python manage.py list_models --check gpt-5.6-terra   # 실제 호출까지 검증
"""
import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '현재 API 키로 접근 가능한 모델을 조회한다.'

    def add_arguments(self, parser):
        parser.add_argument('--filter', type=str, default='',
                            help='모델명에 이 문자열이 포함된 것만 표시')
        parser.add_argument('--check', type=str, default='',
                            help='해당 모델로 실제 호출을 1회 시도해 사용 가능한지 확인')

    def handle(self, *args, **options):
        if not settings.LLM_API_KEY:
            self.stdout.write(self.style.ERROR('LLM_API_KEY가 설정되지 않았습니다.'))
            return

        self.stdout.write(f'현재 설정: LLM_MODEL={settings.LLM_MODEL} · '
                          f'LLM_VISION_MODEL={settings.LLM_VISION_MODEL}\n')

        try:
            resp = httpx.get(f'{settings.LLM_API_BASE}/models',
                             headers={'Authorization': f'Bearer {settings.LLM_API_KEY}'},
                             timeout=30)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'조회 실패: {e}'))
            return

        if resp.status_code != 200:
            self.stdout.write(self.style.ERROR(f'HTTP {resp.status_code}: {resp.text[:200]}'))
            return

        ids = sorted(m['id'] for m in resp.json().get('data', []))
        keyword = options['filter']
        shown = [i for i in ids if keyword in i] if keyword else ids

        self.stdout.write(f'접근 가능한 모델 {len(ids)}개'
                          + (f' (필터 "{keyword}" → {len(shown)}개)' if keyword else ''))
        self.stdout.write('-' * 56)
        for name in shown:
            mark = ' ← 현재 사용 중' if name == settings.LLM_MODEL else ''
            self.stdout.write(f'  {name}{self.style.SUCCESS(mark) if mark else ""}')

        target = options['check']
        if not target:
            return

        self.stdout.write('')
        self.stdout.write(f'--- {target} 실제 호출 검증 ---')
        if target not in ids:
            self.stdout.write(self.style.WARNING(
                '  목록에 없습니다. 그래도 호출은 시도합니다(목록이 최신이 아닐 수 있음).'))
        try:
            from services.llm import generate_response
            res = generate_response(
                [{'role': 'user', 'content': '한 단어로만 답하세요: 정상'}],
                model=target, max_tokens=800)
            body = res['content'] if isinstance(res, dict) else str(res)
            self.stdout.write(self.style.SUCCESS(f'  ✅ 호출 성공 — 응답: {body.strip()[:60]!r}'))
            self.stdout.write(f'  응답 모델명: {res.get("model") if isinstance(res, dict) else "?"}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ 호출 실패: {type(e).__name__}: {str(e)[:220]}'))
