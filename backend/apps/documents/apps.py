from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.documents'

    def ready(self):
        # 문서 삭제 → Qdrant 벡터 정리 시그널 등록
        from . import signals  # noqa: F401
