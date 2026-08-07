"""
인증 API — 세션 기반 로그인 / 로그아웃 / 현재 사용자 조회
"""
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .serializers import UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    Body: { "email": "...", "password": "..." }
    """
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'error': '이메일과 비밀번호를 입력하세요.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user = authenticate(request, email=email, password=password)
    
    if user is None:
        try:
            # 이메일 형식이 아니라 아이디(username)만 친 경우 수동 인증
            u = User.objects.get(username=email)
            if u.check_password(password):
                user = u
        except User.DoesNotExist:
            pass

    if user is None:
        return Response(
            {'error': '이메일 또는 비밀번호가 올바르지 않습니다.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    login(request, user)

    # last_login 갱신
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    return Response({
        'message': '로그인 성공',
        'user': UserSerializer(user).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/"""
    logout(request)
    return Response({'message': '로그아웃 완료'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """GET /api/auth/me/ — 현재 로그인 사용자 정보"""
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_view(request):
    """GET /api/auth/csrf/ — CSRF 토큰 발급 (프론트엔드 연동용)"""
    token = get_token(request)
    return Response({'csrfToken': token})
