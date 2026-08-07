from rest_framework import viewsets
from .models import Workspace, Project
from .serializers import WorkspaceSerializer, ProjectSerializer


class WorkspaceViewSet(viewsets.ModelViewSet):
    """워크스페이스 CRUD API"""
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """프로젝트 CRUD API"""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filterset_fields = ['workspace', 'is_shared']
