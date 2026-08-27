"""
재생E AI Agent — URL Configuration
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
def api_root(request):
    """API 루트 엔드포인트 — 사용 가능한 엔드포인트 목록"""
    return Response({
        'message': '재생E AI Agent API',
        'version': 'v1',
        'endpoints': {
            'workspaces': '/api/workspaces/',
            'projects': '/api/projects/',
            'documents': '/api/documents/',
            'conversations': '/api/conversations/',
            'contract_templates': '/api/contract-templates/',
            'contract_drafts': '/api/contracts/drafts/',
            'contract_reviews': '/api/contracts/reviews/',
            'bizdev_sites': '/api/bizdev/sites/',
            'bizdev_summary': '/api/bizdev/summary/',
            'bizdev_grid': '/api/bizdev/grid/capacity/',
            'bizdev_laws': '/api/bizdev/laws/',
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_media(request, path):
    """[C-1] /media/ 원본 파일 서빙 — 로그인 필수.

    기존에는 DEBUG일 때 django.conf.urls.static.static()으로 무인증 공개되어
    계약서 원본이 그대로 다운로드됐다. 경로 탈출 검증은 resolve_media_path가 담당한다.
    """
    from apps.documents.views import resolve_media_path

    abs_path = resolve_media_path(f'{settings.MEDIA_URL}{path}')
    if not abs_path:
        raise Http404('파일을 찾을 수 없습니다.')
    return FileResponse(open(abs_path, 'rb'))


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api_root, name='api-root'),
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.workspaces.urls')),
    path('api/', include('apps.documents.urls')),
    path('api/', include('apps.chat.urls')),
    path('api/', include('apps.contracts.urls')),
    path('api/', include('apps.bizdev.urls')),
    re_path(r'^media/(?P<path>.+)$', protected_media, name='protected-media'),
]
