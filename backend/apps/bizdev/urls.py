from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BudgetEntryViewSet, CommunityIssueViewSet, ContractViewSet, GridCapacityView,
    GridNearbyView, LawListView, OrdinanceListView, PermitDocumentViewSet,
    PermitStageViewSet, SiteEventViewSet, SiteFactViewSet, SiteViewSet,
    SubstationSearchView, SummaryView,
)

router = DefaultRouter()
router.register('bizdev/sites', SiteViewSet, basename='bizdev-site')
router.register('bizdev/stages', PermitStageViewSet, basename='bizdev-stage')
router.register('bizdev/documents', PermitDocumentViewSet, basename='bizdev-document')
router.register('bizdev/budget-entries', BudgetEntryViewSet, basename='bizdev-budget')
router.register('bizdev/issues', CommunityIssueViewSet, basename='bizdev-issue')
router.register('bizdev/facts', SiteFactViewSet, basename='bizdev-fact')
router.register('bizdev/contracts', ContractViewSet, basename='bizdev-contract')
router.register('bizdev/events', SiteEventViewSet, basename='bizdev-event')

urlpatterns = [
    path('bizdev/summary/', SummaryView.as_view(), name='bizdev-summary'),
    path('bizdev/grid/capacity/', GridCapacityView.as_view(), name='bizdev-grid-capacity'),
    path('bizdev/grid/nearby/', GridNearbyView.as_view(), name='bizdev-grid-nearby'),
    path('bizdev/grid/substations/', SubstationSearchView.as_view(), name='bizdev-substations'),
    path('bizdev/laws/', LawListView.as_view(), name='bizdev-laws'),
    path('bizdev/ordinances/', OrdinanceListView.as_view(), name='bizdev-ordinances'),
    path('', include(router.urls)),
]
