"""RAG 답변 품질·응답속도 Baseline 측정.

**왜 HTTP 엔드포인트를 그대로 호출하는가**
검색·프롬프트·LLM 호출을 이 커맨드가 직접 재현하면, 나중에 views.py 의 시스템
프롬프트가 바뀌었을 때 측정값이 조용히 실제 서비스와 달라진다. 그래서 실제
`POST /api/conversations/{id}/messages/` 를 호출하고, 시간 분리는 `run_rag` ·
`generate_response` 를 감싸서 얻는다. 측정 대상과 서비스 경로가 항상 같다.

**통합 저장소에서도 그대로 돈다.** 엔드포인트 경로·인증 방식·LLM 함수 이름이
저장소마다 달라서, 있는 것을 찾아 쓰도록 만들었다(_resolve_* 함수들).
질문을 바꾸면 Baseline 과 비교할 수 없으므로 rag_eval_questions.json 은 그대로 둔다.

사용:
    docker exec <backend> python manage.py eval_rag_baseline
    docker exec <backend> python manage.py eval_rag_baseline --repeat 3 --out /app/media/b.json
"""
import json
import os
import statistics
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUESTIONS = os.path.join(HERE, 'rag_eval_questions.json')

# 스트리밍 엔드포인트. **화면이 실제로 쓰는 경로가 이것이다**(ChatView.tsx).
# 비스트리밍 경로는 구 저장소에서 관련성 게이트를 타지 않는 별도 코드라 측정값이
# 사용자 경험과 달라진다 — 그래서 스트리밍을 기본으로 둔다.
STREAM_PATHS = (
    '/api/conversations/{id}/messages/stream/',
    '/api/conversations/{id}/messages/stream',
)
# 비스트리밍(참고용·--endpoint send)
SEND_PATHS = (
    '/api/conversations/{id}/messages/',
    '/api/conversations/{id}/messages/send/',
)


def _pct(values, p):
    """nearest-rank 백분위. 표본이 10여 개라 보간은 과하다."""
    if not values:
        return None
    s = sorted(values)
    k = max(1, min(len(s), int(-(-len(s) * p // 100))))
    return round(s[k - 1], 2)


class Command(BaseCommand):
    help = 'RAG 답변 품질·응답속도 Baseline 측정 (docs/RAG_QUALITY_BASELINE.md 재검증용)'

    def add_arguments(self, parser):
        parser.add_argument('--questions', default=DEFAULT_QUESTIONS)
        parser.add_argument('--user-email', default='',
                            help='빈 값이면 admin 역할 계정을 자동 선택')
        parser.add_argument('--corpus', default='',
                            help="통합 저장소용 코퍼스 키(final 등). 구 저장소는 비워 둔다")
        parser.add_argument('--model', default='', help='빈 값이면 서버 기본 모델')
        parser.add_argument('--out', default='/app/media/rag_baseline_result.json')
        parser.add_argument('--repeat', type=int, default=1)
        parser.add_argument('--keep-conversations', action='store_true')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--endpoint', default='stream', choices=('stream', 'send'),
                            help='화면이 쓰는 경로는 stream 이다. send 는 참고용')

    # ---------- 계측 ----------

    def _install_probes(self):
        """검색 · 게이트 · LLM 호출을 감싸 구간 시간을 잰다.

        원본을 호출만 하고 반환값은 그대로 흘려보내므로 동작에 영향이 없다.

        검색은 `run_rag` 가 아니라 `retrieve_for_views` 를 잰다. 구 저장소의
        send_message 는 run_rag 를 쓰지 않고 뷰 안에 같은 로직이 인라인돼 있어
        run_rag 를 감싸면 아무것도 잡히지 않는다. retrieve_for_views 는 두 저장소
        모두 같은 이름으로 쓰므로 여기가 유일하게 공통인 지점이다.
        (임베딩 + Qdrant 하이브리드 + 리랭킹 + 중복제거까지 포함. 게이트 이후의
         Postgres 본문 조회·컨텍스트 조립은 '기타'로 빠진다.)
        """
        import services.llm as llm_mod
        import services.retriever as retr_mod

        self._probe = {}
        probe = self._probe

        orig_retr = retr_mod.retrieve_for_views
        orig_gate = retr_mod.apply_relevance_gate

        def timed_retrieve(*a, **kw):
            t0 = time.perf_counter()
            try:
                return orig_retr(*a, **kw)
            finally:
                probe['retrieval_s'] = time.perf_counter() - t0

        def capture_gate(hits):
            kept, reason = orig_gate(hits)
            probe['gate'] = reason
            probe['candidates'] = len(hits)
            probe['passed'] = len(kept)
            return kept, reason

        retr_mod.retrieve_for_views = timed_retrieve
        retr_mod.apply_relevance_gate = capture_gate

        # LLM 함수 이름이 저장소마다 다르다(generate_response / chat_completion).
        for name in ('generate_response', 'chat_completion'):
            fn = getattr(llm_mod, name, None)
            if fn is None:
                continue

            def make(orig):
                def timed(*a, **kw):
                    t0 = time.perf_counter()
                    try:
                        res = orig(*a, **kw)
                        if isinstance(res, dict):
                            probe['usage'] = res.get('usage')
                        return res
                    finally:
                        probe['llm_s'] = time.perf_counter() - t0
                return timed

            setattr(llm_mod, name, make(fn))
            probe.setdefault('llm_func', name)

    # ---------- 준비 ----------

    def _resolve_user(self, email):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if email:
            return User.objects.filter(email=email).first()
        return (User.objects.filter(role='admin').first()
                or User.objects.filter(is_superuser=True).first()
                or User.objects.first())

    def _make_client(self, user):
        """세션 인증이면 force_login, JWT 면 토큰 헤더를 쓴다."""
        classes = str(settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', []))
        if 'JWT' in classes or 'simplejwt' in classes:
            from rest_framework_simplejwt.tokens import RefreshToken
            token = str(RefreshToken.for_user(user).access_token)
            return Client(HTTP_AUTHORIZATION=f'Bearer {token}'), 'jwt'
        c = Client()
        c.force_login(user)
        return c, 'session'

    # ---------- 실행 ----------

    def handle(self, *args, **opts):
        from apps.chat.models import Conversation, Message

        if not os.path.exists(opts['questions']):
            self.stderr.write(f"질문 파일이 없습니다: {opts['questions']}")
            return
        with open(opts['questions'], encoding='utf-8') as f:
            questions = json.load(f)['questions']
        if opts['limit']:
            questions = questions[:opts['limit']]

        user = self._resolve_user(opts['user_email'])
        if user is None:
            self.stderr.write('사용자 계정이 없습니다.')
            return

        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append('testserver')

        client, auth_mode = self._make_client(user)
        self._install_probes()
        self.stdout.write(f'계정 {user.email} · 인증 {auth_mode} · '
                          f"LLM 계측 {self._probe.get('llm_func')}")

        created, send_path = [], None

        streaming = opts['endpoint'] == 'stream'
        candidates_paths = STREAM_PATHS if streaming else SEND_PATHS

        def ask(text):
            """한 질문을 묻고 (상태코드, 답변, 출처, 시간)을 돌려준다.

            매번 새 대화를 만든다 — 직전 답변이 히스토리로 들어가면 같은 질문도
            결과가 달라져 재현이 안 된다.
            """
            nonlocal send_path
            conv = Conversation.objects.create(
                created_by=user, use_internal_docs=True, title='[EVAL] ' + text[:40])
            created.append(conv.id)
            self._probe.update(retrieval_s=None, llm_s=None, gate='', usage=None,
                               candidates=0, passed=0)
            body = {'content': text}
            if opts['corpus']:
                body['corpus'] = opts['corpus']
            if opts['model']:
                body['model'] = opts['model']

            paths = [send_path] if send_path else list(candidates_paths)
            out = {'answer': '', 'sources': [], 'ttft_s': None, 'no_hit': False}
            res = None
            t0 = time.perf_counter()
            for p in paths:
                res = client.post(p.format(id=conv.id), data=json.dumps(body),
                                  content_type='application/json')
                if res.status_code in (200, 201):
                    send_path = p
                    break

            if res is None or res.status_code not in (200, 201):
                out['total_s'] = time.perf_counter() - t0
                out['status'] = res.status_code if res is not None else 0
                return out

            if streaming:
                # SSE 를 끝까지 읽는다. 첫 delta 가 사용자 체감 대기(TTFT)다.
                buf, event = '', ''
                for raw in res.streaming_content:
                    buf += raw.decode('utf-8', 'replace')
                    while '\n\n' in buf:
                        block, buf = buf.split('\n\n', 1)
                        for line in block.splitlines():
                            if line.startswith('event: '):
                                event = line[7:].strip()
                            elif line.startswith('data: '):
                                try:
                                    data = json.loads(line[6:])
                                except json.JSONDecodeError:
                                    continue
                                if event == 'delta':
                                    if out['ttft_s'] is None:
                                        out['ttft_s'] = time.perf_counter() - t0
                                    out['answer'] += data.get('text', '')
                                elif event == 'sources':
                                    out['sources'] = data.get('sources', [])
                                elif event == 'error':
                                    out['answer'] += data.get('message', '')
            else:
                data = res.json()
                out['answer'] = data.get('content', '')
                out['sources'] = data.get('sources') or []
                out['model'] = data.get('model', '')

            out['total_s'] = time.perf_counter() - t0
            out['status'] = res.status_code
            return out

        # 워밍업 — 리랭커·임베딩 모델 로드가 첫 질의에만 얹힌다(실측 30초대). 측정 제외.
        self.stdout.write(f"워밍업 중(측정 제외) · 엔드포인트={opts['endpoint']}...")
        w = ask('워밍업 질의입니다. 홍성 사업 개요를 한 줄로 알려줘')
        self.stdout.write(f"  HTTP {w['status']} · {w['total_s']:.1f}s · 경로 {send_path}")
        if w['status'] not in (200, 201):
            self.stderr.write('워밍업 실패 — 엔드포인트/인증을 확인하십시오.')
            return

        records = []
        for i, q in enumerate(questions, 1):
            for r in range(opts['repeat']):
                self.stdout.write(f"[{i}/{len(questions)}] {q['id']} {q['question'][:38]}…")
                out = ask(q['question'])
                p = dict(self._probe)

                if out['status'] not in (200, 201):
                    records.append({'id': q['id'], 'type': q['type'],
                                    'question': q['question'], 'run': r + 1,
                                    'error': f"HTTP {out['status']}",
                                    'total_s': round(out['total_s'], 2)})
                    self.stdout.write(self.style.ERROR(f"  실패 HTTP {out['status']}"))
                    continue

                total = out['total_s']
                r_s = p.get('retrieval_s')
                ttft = out.get('ttft_s')
                sources = out['sources']
                records.append({
                    'id': q['id'], 'type': q['type'], 'question': q['question'],
                    'run': r + 1,
                    'answer': out['answer'],
                    'answer_chars': len(out['answer']),
                    'sources': [{'rank': j + 1,
                                 'title': s.get('display_title') or s.get('document_title', ''),
                                 'location': s.get('location_label', ''),
                                 'score': round(float(s.get('score') or 0), 4)}
                                for j, s in enumerate(sources)],
                    'source_count': len(sources),
                    'gate': p.get('gate', ''),
                    'candidates': p.get('candidates', 0),
                    'passed': p.get('passed', 0),
                    'retrieval_s': round(r_s, 2) if r_s else None,
                    'ttft_s': round(ttft, 2) if ttft else None,
                    'gen_s': round(total - ttft, 2) if ttft else None,
                    'total_s': round(total, 2),
                    'usage': p.get('usage'),
                })
                last = records[-1]
                self.stdout.write(
                    f"  출처 {last['source_count']}건 · 검색 {last['retrieval_s']}s · "
                    f"첫토큰 {last['ttft_s']}s · 합계 {last['total_s']}s "
                    f"· 게이트[{last['gate'][:38]}]")

        # 측정용 대화는 채팅 목록을 어지럽히므로 기본적으로 지운다(우리가 만든 것만).
        if not opts['keep_conversations'] and created:
            Message.objects.filter(conversation_id__in=created).delete()
            Conversation.objects.filter(id__in=created).delete()
            self.stdout.write(f'측정용 대화 {len(created)}건 정리 완료')

        ok = [r for r in records if 'error' not in r]
        totals = [r['total_s'] for r in ok]
        retr = [r['retrieval_s'] for r in ok if r.get('retrieval_s')]
        llms = [r['ttft_s'] for r in ok if r.get('ttft_s')]

        summary = {
            'measured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'endpoint': opts['endpoint'],
            'question_count': len(questions),
            'run_count': len(records),
            'model': opts['model'] or settings.LLM_MODEL,
            'config': {k: getattr(settings, k, None) for k in (
                'QDRANT_URL', 'QDRANT_COLLECTION', 'RAG_RETRIEVE_K', 'RAG_MAX_CONTEXT_K',
                'RERANK_BACKEND', 'RERANK_MAX_LENGTH', 'RERANK_SKIP_MARGIN',
                'RAG_GATE_MIN_TOP1_RERANK', 'RAG_GATE_REL_MARGIN_RERANK',
                'RAG_GATE_MIN_TOP1_QDRANT', 'RAG_CONTEXT_CHAR_BUDGET',
                'RAG_CONTEXT_CHUNK_CHAR_LIMIT')},
            'latency': {
                'total': {'mean': round(statistics.mean(totals), 2) if totals else None,
                          'p50': _pct(totals, 50), 'p95': _pct(totals, 95),
                          'min': min(totals) if totals else None,
                          'max': max(totals) if totals else None},
                'retrieval': {'mean': round(statistics.mean(retr), 2) if retr else None,
                              'p50': _pct(retr, 50), 'p95': _pct(retr, 95)},
                'ttft': {'mean': round(statistics.mean(llms), 2) if llms else None,
                         'p50': _pct(llms, 50), 'p95': _pct(llms, 95)},
            },
        }

        os.makedirs(os.path.dirname(opts['out']), exist_ok=True)
        with open(opts['out'], 'w', encoding='utf-8') as f:
            json.dump({'summary': summary, 'records': records}, f,
                      ensure_ascii=False, indent=2)

        lat = summary['latency']
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"완료 — {opts['out']}"))
        self.stdout.write(f"  합계 평균 {lat['total']['mean']}s · P50 {lat['total']['p50']}s "
                          f"· P95 {lat['total']['p95']}s")
        self.stdout.write(f"  검색 평균 {lat['retrieval']['mean']}s · "
                          f"첫토큰(TTFT) 평균 {lat['ttft']['mean']}s · "
                          f"P95 {lat['ttft']['p95']}s")
