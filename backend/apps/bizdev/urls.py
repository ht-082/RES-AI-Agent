from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BudgetEntryViewSet, CommunityIssueViewSet, GridCapacityView, GridNearbyView,
    LawListView, OrdinanceListView, PermitDocumentViewSet, PermitStageViewSet,
    SiteViewSet, SummaryView,
)

router = DefaultRouter()
router.register('bizdev/sites', SiteViewSet, basename='bizdev-site')
router.register('bizdev/stages', PermitStageViewSet, basename='bizdev-stage')
router.register('bizdev/documents', PermitDocumentViewSet, basename='bizdev-document')
router.register('bizdev/budget-entries', BudgetEntryViewSet, basename='bizdev-budget')
router.register('bizdev/issues', CommunityIssueViewSet, basename='bizdev-issue')

urlpatterns = [
    path('bizdev/summary/', SummaryView.as_view(), name='bizdev-summary'),
    path('bizdev/grid/capacity/', GridCapacityView.as_view(), name='bizdev-grid-capacity'),
    path('bizdev/grid/nearby/', GridNearbyView.as_view(), name='bizdev-grid-nearby'),
    path('bizdev/laws/', LawListView.as_view(), name='bizdev-laws'),
    path('bizdev/ordinances/', OrdinanceListView.as_view(), name='bizdev-ordinances'),
    path('', include(router.urls)),
]
