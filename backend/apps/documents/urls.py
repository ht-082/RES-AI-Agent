from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, CorpusVersionListView

router = DefaultRouter()
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('corpus-versions/', CorpusVersionListView.as_view(), name='corpus-versions'),
    path('', include(router.urls)),
]
