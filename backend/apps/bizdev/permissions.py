"""
사업개발 권한 — 원본 Supabase RLS(can_edit_site) 이관.

원본 규칙: admin 은 전체 편집, pm 은 자기 사업지(pm_id)만 편집, 그 외 읽기.
RES 의 User.role ∈ {admin, member} 에 맞춰 "Site.pm 으로 지정된 member"를
원본의 pm 역할로 매핑한다. 사업지 삭제는 연쇄삭제 위험 때문에 admin 전용.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import (
    BudgetEntry, CommunityIssue, Contract, PermitDocument, PermitStage,
    Site, SiteEvent, SiteFact,
)


def site_of(obj):
    """어떤 bizdev 객체든 소속 Site 로 환원한다."""
    if isinstance(obj, Site):
        return obj
    if isinstance(obj, (PermitStage, BudgetEntry, CommunityIssue,
                        SiteFact, Contract, SiteEvent)):
        return obj.site
    if isinstance(obj, PermitDocument):
        return obj.stage.site
    return None


def can_edit_site(user, site):
    """편집 가능 여부.

    사내 직원만 쓰는 내부 도구라, 로그인한 사용자면 누구나 모든 사업 정보를
    고칠 수 있게 한다(2026-09-01 결정). 원본 Supabase 는 admin/담당PM 으로
    제한했지만, 담당자가 바뀔 때마다 편집이 막히는 쪽이 실무에 더 불편했다.
    사업지 삭제만 admin 으로 남겨 둔다(연쇄 삭제 위험).
    """
    del site  # 사업지별 구분 없음 — 시그니처는 호출부 호환을 위해 유지
    return bool(user and user.is_authenticated)


def check_site_editable(user, site):
    """ViewSet 밖(perform_create 등)에서 쓰는 명시적 검사 — 실패 시 403."""
    if not can_edit_site(user, site):
        raise PermissionDenied('로그인이 필요합니다.')


class IsAdminOrSitePM(BasePermission):
    """읽기·쓰기 모두 로그인 사용자 전체 (사내 도구 — can_edit_site 참고).

    뷰에 permission_classes 를 지정하면 전역 IsAuthenticated 가 대체되므로
    has_permission 에서 로그인 필수를 직접 보장한다.
    """
    message = '로그인이 필요합니다.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        site = site_of(obj)
        return site is not None and can_edit_site(request.user, site)
