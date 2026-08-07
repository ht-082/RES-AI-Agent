"""
재생E AI Agent — Django Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ── Security ──────────────────────────────────────────────────────────
# 기본값은 모두 "안전한 쪽". 개발 편의는 .env에서 명시적으로 켠다.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise RuntimeError(
        'DJANGO_SECRET_KEY가 설정되지 않았습니다. .env에 실난수 키를 넣으십시오.\n'
        '생성: python -c "from django.core.management.utils import '
        'get_random_secret_key as g; print(g())"'
    )

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,backend').split(',') if h.strip()]
if '*' in ALLOWED_HOSTS and not DEBUG:
    raise RuntimeError('운영 모드에서 ALLOWED_HOSTS=* 는 허용되지 않습니다.')

# ── Applications ──────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    'django_filters',
    # Project apps
    'apps.accounts',
    'apps.workspaces',
    'apps.documents',
    'apps.rag',
    'apps.chat',
    'apps.contracts',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL:
    # Parse DATABASE_URL: postgres://user:pass@host:port/dbname
    import re
    m = re.match(
        r'postgres(?:ql)?://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/(?P<name>.+)',
        DATABASE_URL
    )
    if m:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': m.group('name'),
                'USER': m.group('user'),
                'PASSWORD': m.group('password'),
                'HOST': m.group('host'),
                'PORT': m.group('port'),
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.getenv('POSTGRES_DB', 're_agent'),
                'USER': os.getenv('POSTGRES_USER', 're_user'),
                'PASSWORD': os.getenv('POSTGRES_PASSWORD', 're_pass'),
                'HOST': 'postgres',
                'PORT': '5432',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 're_agent'),
            'USER': os.getenv('POSTGRES_USER', 're_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 're_pass'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

# ── Auth ──────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Session / CSRF (프론트엔드 연동)
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False
# CSRF 신뢰 출처는 CORS 화이트리스트와 같은 목록을 쓴다 (아래 CORS 섹션에서 재사용).
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    'DJANGO_CORS_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]

# ── i18n ──────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# ── Static / Media ────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── REST Framework ────────────────────────────────────────────────────
# [C-1] 기본 권한을 IsAuthenticated로 고정한다.
# DRF 기본값은 AllowAny이므로, 선언을 빠뜨린 뷰가 그대로 공개되는 사고가 났었다.
# 공개가 필요한 뷰(로그인·CSRF 발급)만 @permission_classes([AllowAny])로 명시적 예외.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
}

# ── CORS ──────────────────────────────────────────────────────────────
# [O-4] DEBUG와 연동하지 않는다. 쿠키 인증을 쓰므로 출처 화이트리스트가 유일한 방어선이다.
# (기존 CORS_ALLOW_ALL_ORIGINS=DEBUG 는 임의 사이트에서 세션을 태운 요청을 가능하게 했다.)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    'DJANGO_CORS_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# ── Celery ────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'

# ── Qdrant ────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
QDRANT_COLLECTION = 're_documents'

# ── Embedding ─────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'baai/bge-m3')
EMBEDDING_DEVICE = os.getenv('EMBEDDING_DEVICE', 'cpu')
EMBEDDING_API_BASE = os.getenv('EMBEDDING_API_BASE', 'https://openrouter.ai/api/v1')
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY', '')


# ── LLM ───────────────────────────────────────────────────────────────
LLM_API_BASE = os.getenv('LLM_API_BASE', '')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
# LLM 응답 대기 상한(초). 사내망 SSL 우회를 위해 커스텀 httpx 클라이언트를 넘기면
# OpenAI SDK 기본 타임아웃(600초)이 httpx 기본값 5초로 덮어써지므로 명시한다.
LLM_TIMEOUT = float(os.getenv('LLM_TIMEOUT', '180'))

# ── File Upload ───────────────────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800

# ── RAG Configuration ──────────────────────────────────────────────────
# RAG_RETRIEVE_K: Qdrant 1차 후보 수 = 리랭커가 고를 수 있는 후보 풀.
# 원칙: RAG_MAX_CONTEXT_K의 2~3배. 최종 개수(8)에 가까우면 리랭커가 고를 게 없어 무의미해진다.
# 리랭킹 비용은 이 값에 거의 비례하므로 속도와의 절충점이다.
RAG_RETRIEVE_K = int(os.getenv('RAG_RETRIEVE_K', '16'))
# (구) 청크별 절대 임계값. 실측상 출처 197건 중 1건만 걸러 사실상 무력했다.
# 지금은 아래 관련성 게이트가 이 역할을 대신한다. 호환을 위해 값만 남겨둔다.
RAG_SIMILARITY_THRESHOLD = float(os.getenv('RAG_SIMILARITY_THRESHOLD', '0.5'))

# ── 관련성 게이트 [C-3] ────────────────────────────────────────────────
# 근거(실측, 질의 10건 = 코퍼스에 답 있음 6 / 전혀 없음 4):
#   리랭커 확률 1위  답있음 0.6019~0.7310  vs  답없음 0.5001~0.5179
#   Qdrant 점수 1위  답있음 0.6464~0.8115  vs  답없음 0.3949~0.4715
# 두 지표 모두 빈 구간 한가운데인 0.55를 바닥값으로 잡았다.
# 표본이 작으므로, 정상 질문이 '자료 없음'으로 튕기면 이 값을 먼저 낮춘다.
RAG_GATE_MIN_TOP1_RERANK = float(os.getenv('RAG_GATE_MIN_TOP1_RERANK', '0.55'))
RAG_GATE_MIN_TOP1_QDRANT = float(os.getenv('RAG_GATE_MIN_TOP1_QDRANT', '0.55'))
# 상대 컷: 1위에서 이 폭 이상 떨어진 후보는 노이즈로 보고 버린다.
RAG_GATE_REL_MARGIN_RERANK = float(os.getenv('RAG_GATE_REL_MARGIN_RERANK', '0.12'))
RAG_GATE_REL_MARGIN_QDRANT = float(os.getenv('RAG_GATE_REL_MARGIN_QDRANT', '0.15'))

# ── 프롬프트 길이 가드 [M-1] ───────────────────────────────────────────
# 컨텍스트에 길이 상한이 없어, 상위 8청크만으로 304,520자(약 10만 토큰)가 되는
# 조합이 존재했다. 청크 크기 문제(H-4/H-5)를 재적재로 고치기 전까지의 안전장치이자,
# 고친 뒤에도 유지할 회귀 방지선이다.
RAG_CONTEXT_CHUNK_CHAR_LIMIT = int(os.getenv('RAG_CONTEXT_CHUNK_CHAR_LIMIT', '4000'))
RAG_CONTEXT_CHAR_BUDGET = int(os.getenv('RAG_CONTEXT_CHAR_BUDGET', '24000'))
LLM_HISTORY_CHAR_BUDGET = int(os.getenv('LLM_HISTORY_CHAR_BUDGET', '6000'))

# ── Tavily 웹 검색 ─────────────────────────────────────────────────────
# 사내 문서가 담지 못하는 정보(법령 개정·SMP/REC 시세·정책 동향)를 보완한다.
#
# ⚠ 웹 검색을 켜면 **질문 내용이 Tavily 서버로 전송된다.**
#    "당진행복솔라 PF 대주단" 같은 질의에는 사업명·상대방이 담긴다.
#    그래서 기본은 전부 꺼짐이고, 사용자가 명시적으로 켤 때만 동작한다.
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '')
# 전역 킬스위치. False면 키가 있어도 외부 호출이 일어나지 않는다.
TAVILY_ENABLED = os.getenv('TAVILY_ENABLED', 'False').lower() in ('true', '1', 'yes')

TAVILY_SEARCH_DEPTH = os.getenv('TAVILY_SEARCH_DEPTH', 'basic')   # basic=1크레딧 / advanced=2
TAVILY_MAX_RESULTS = int(os.getenv('TAVILY_MAX_RESULTS', '5'))
TAVILY_TIMEOUT = float(os.getenv('TAVILY_TIMEOUT', '8.0'))        # LLM(180s)보다 훨씬 짧게

# 품질 게이트 — 실측 결과(질의 10건, 2026-08-03)
#   웹에 답 있음 1위: 0.7385 ~ 0.9169
#   웹에 답 없음 1위: 0.1822 ~ 0.7891
#   → **두 그룹이 겹친다.** 사내 게이트(0.5179 vs 0.6019, 빈 구간 존재)와 달리
#     점수만으로 "정답/오답"을 가를 수 없다.
#
# 이유: Tavily score는 '질의-문서 유사도'지 '정답 여부'가 아니다.
#   "우리 회사 구내식당 메뉴" → 남의 회사 구내식당 블로그가 0.7891
#   "당진행복솔라 PF 대주단" → 이름이 비슷한 다른 사업(GS당진솔라팜) 기사가 0.5652
#
# 따라서 점수 컷은 '완전 무관한 꼬리를 자르는' 보조 장치로만 쓴다.
# 오답 방어의 본체는 ① 자동 폴백 금지 ② 출처 도메인 노출 ③ 프롬프트 우선순위 지시다.
TAVILY_MIN_SCORE = float(os.getenv('TAVILY_MIN_SCORE', '0.3'))
TAVILY_REL_MARGIN = float(os.getenv('TAVILY_REL_MARGIN', '0.25'))

# 사내 검색이 실패했을 때 웹으로 자동 보완할 것인가.
# ⚠ 기본 False를 유지할 것. 실측에서 사내 전용 질의("당진행복솔라 PF 대주단")에
#   이름만 비슷한 **다른 사업 기사**가 상위로 올라왔다. 자동 폴백을 켜면
#   실제 대주단(우리은행·교보생명) 대신 그 기사의 은행명을 답할 수 있다.
TAVILY_AUTO_FALLBACK = os.getenv('TAVILY_AUTO_FALLBACK', 'False').lower() in ('true', '1', 'yes')

# 웹 컨텍스트 예산은 사내(24,000자)보다 작게 둔다 — 웹이 사내 근거를 밀어내면 안 된다.
TAVILY_CONTEXT_CHAR_BUDGET = int(os.getenv('TAVILY_CONTEXT_CHAR_BUDGET', '6000'))
RAG_MAX_CONTEXT_K = int(os.getenv('RAG_MAX_CONTEXT_K', '8'))
DEBUG_RAG = os.getenv('DEBUG_RAG', 'True').lower() in ('true', '1', 'yes')

# ── Reranker ───────────────────────────────────────────────────────────
RERANK_ENABLED = os.getenv('RERANK_ENABLED', 'True').lower() in ('true', '1', 'yes')
#
# RERANK_MAX_LENGTH — 리랭커 입력 토큰 상한.
#
# 모델 기본값은 8192다. 그대로 두면 배치가 '가장 긴 청크'에 맞춰 패딩되어 대부분의 연산이
# 빈 칸에 쓰인다(CPU 실측: K=20 기준 46.8초). 이 값을 낮추는 것이 K를 줄이는 것보다
# 효과가 크다. 잘림은 리랭커의 '관련성 판단'에만 영향을 주며, LLM에 들어가는 컨텍스트는
# Postgres에서 청크 전문을 가져오므로 잘리지 않는다(apps/chat/views.py 참조).
#
# 2026-07-18 재적재(병합 청킹, 10,777청크) 후 재산정 — test_rerank_tuning.py 실측:
#   토큰 분포: 중앙 306 / 90% 716 / 95% 931 / 최대 2,776 (병합 청킹으로 재적재 전의 5배)
#   순위 일치도(기준=768): 512 -> 96.9%·top1 4/4·24.8초 | 384 -> 96.9%·top1 4/4·17.7초
#                          | 256 -> 90.6%·top1 2/4·11.6초 (top1이 절반 바뀜 = 품질 손실 실재)
# 384 채택: 512와 순위가 완전히 같으면서 1.4배 빠른 최적점.
#
# ※ 이 값은 청킹 설계에 직접 종속된다. 청크 크기를 바꾸면 test_rerank_tuning.py로
#    반드시 재산정할 것. GPU 도입 시 768 이상으로 상향 검토.
RERANK_MAX_LENGTH = int(os.getenv('RERANK_MAX_LENGTH', '384'))

# 리랭커 실행 백엔드 — 'openvino_int8' | 'openvino' | 'torch'
# 2026-07-28 실측 (질의 6개 × 후보 16, max_length=384, 기준=torch FP32):
#   torch FP32     18~24초   (기준)
#   OpenVINO FP32  15.7초    top1 6/6, 상위8 겹침 100%
#   OpenVINO INT8   7.5초    top1 6/6, 상위8 겹침 97.9%   ← 채택
# INT8은 IR 디렉토리(RERANK_OV_INT8_DIR)가 있어야 하며, 없거나 로드 실패 시 torch로 폴백한다.
# IR 재생성: docker exec re_backend python bench_openvino.py c
RERANK_BACKEND = os.getenv('RERANK_BACKEND', 'openvino_int8')
RERANK_OV_INT8_DIR = os.getenv('RERANK_OV_INT8_DIR', os.path.join(BASE_DIR, '.ov_reranker_int8'))

# 조건부 리랭킹 — Qdrant 점수만으로 컨텍스트 선택이 이미 명확하면 리랭킹을 건너뛴다.
# 컨텍스트 경계(K번째 vs K+1번째)의 점수 차가 전체 점수 폭에서 이 비율 이상이면 생략.
# 0으로 두면 항상 리랭킹(기존 동작). 값이 클수록 리랭킹을 더 자주 수행한다.
RERANK_SKIP_MARGIN = float(os.getenv('RERANK_SKIP_MARGIN', '0.25'))

# 서버 기동 시 임베딩·리랭커 모델을 백그라운드로 미리 로드 (첫 질의 2~3분 지연 제거)
RAG_WARMUP_ON_START = os.getenv('RAG_WARMUP_ON_START', 'True').lower() in ('true', '1', 'yes')

# ── Logging ────────────────────────────────────────────────────────────
# 기본 설정으로는 우리 앱(apps.*, services.*)의 INFO 로그가 콘솔에 나오지 않아
# 예열·조건부 리랭킹·RAG 진단 결과를 확인할 수 없다.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[{levelname}] {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'apps': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'services': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

