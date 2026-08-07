from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ContractTemplateViewSet, ContractDraftViewSet, ContractReviewViewSet,
    ContractTypesAPIView, ContractGenerateAPIView, ContractDraftDownloadAPIView
)

router = DefaultRouter()
router.register('contract-templates', ContractTemplateViewSet, basename='contract-template')
router.register('contracts/drafts', ContractDraftViewSet, basename='contract-draft')
router.register('contracts/reviews', ContractReviewViewSet, basename='contract-review')

urlpatterns = [
    path('contract/types', ContractTypesAPIView.as_view(), name='contract-types'),
    path('contract/generate', ContractGenerateAPIView.as_view(), name='contract-generate'),
    path('contract/drafts/<uuid:draft_id>/download', ContractDraftDownloadAPIView.as_view(), name='contract-draft-download'),
    path('', include(router.urls)),
]
