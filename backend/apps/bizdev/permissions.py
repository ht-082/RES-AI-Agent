"""
사업개발 권한 — 원본 Supabase RLS(can_edit_site) 이관.

원본 규칙: admin 은 전체 편집, pm 은 자기 사업지(pm_id)만 편집, 그 외 읽기.
RES 의 User.role ∈ {admin, member} 에 맞춰 "Site.pm 으로 지정된 member"를
원본의 pm 역할로 매핑한다. 사업지 삭제는 연쇄삭제 위험 때문에 admin 전용.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import BudgetEntry, CommunityIssue, PermitDocument, PermitStage, Site


def site_of(obj):
    """어떤 bizdev 객체든 소속 Site 로 환원한다."""
    if isinstance(obj, Site):
        return obj
    if isinstance(obj, (PermitStage, BudgetEntry, CommunityIssue)):
        return obj.site
    if isinstance(obj, PermitDocument):
        return obj.stage.site
    return None


def can_edit_site(user, site):
    return bool(
        user and user.is_authenticated
        and (getattr(user, 'role', '') == 'admin' or site.pm_id == user.id)
    )


def check_site_editable(user, site):
    """ViewSet 밖(perform_create 등)에서 쓰는 명시적 검사 — 실패 시 403."""
    if not can_edit_site(user, site):
        raise PermissionDenied('이 사업지를 편집할 권한이 없습니다. (admin 또는 담당 PM만 가능)')


class IsAdminOrSitePM(BasePermission):
    """읽기는 로그인 사용자 전체, 쓰기는 admin 또는 해당 사업지 PM.

    뷰에 permission_classes 를 지정하면 전역 IsAuthenticated 가 대체되므로
    has_permission 에서 로그인 필수를 직접 보장한다.
    """
    message = '이 사업지를 편집할 권한이 없습니다. (admin 또는 담당 PM만 가능)'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        site = site_of(obj)
        return site is not None and can_edit_site(request.user, site)
