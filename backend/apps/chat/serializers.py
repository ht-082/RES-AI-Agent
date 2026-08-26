from rest_framework import serializers
from .models import Conversation, Message, MessageSource, MessageAttachment, ConversationShare


class MessageSourceSerializer(serializers.ModelSerializer):
    open_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageSource
        fields = ['id', 'document_id', 'short_label', 'display_title',
                  'page_number', 'location_label', 'open_url', 'score',
                  'rank', 'snippet', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_open_url(self, obj):
        # 라우터가 등록한 경로는 끝에 슬래시가 있다. 빼먹으면 301 리다이렉트가 한 번 더 돈다.
        if not obj.document_id:
            return None
        url = f'/api/documents/{obj.document_id}/file/'
        if obj.page_number:
            url += f'?page={obj.page_number}'
        return url


class MessageSerializer(serializers.ModelSerializer):
    sources = MessageSourceSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'role', 'content', 'used_internal_docs',
                  'model', 'token_usage', 'status', 'created_at', 'sources',
                  'web_sources']
        read_only_fields = ['id', 'created_at', 'sources', 'web_sources']


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'conversation', 'message', 'filename', 'file_type',
                  'storage_uri', 'file_size', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'project', 'title', 'use_internal_docs', 'use_web_search', 'llm_model', 'corpus_version',
                  'is_pinned', 'is_shared', 'created_by', 'last_message_at',
                  'created_at', 'updated_at', 'message_count', 'last_message_preview']
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_message_at']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return last_msg.content[:100]
        return None


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']


class ConversationShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationShare
        fields = ['id', 'conversation', 'shared_to_project', 'share_type',
                  'shared_by', 'created_at']
        read_only_fields = ['id', 'created_at']


class SendMessageSerializer(serializers.Serializer):
    """사용자 메시지 전송 시 사용하는 시리얼라이저"""
    content = serializers.CharField()
    use_internal_docs = serializers.BooleanField(required=False, default=True)
    use_web_search = serializers.BooleanField(required=False, default=False)
    # 값 검증은 views.resolve_llm_model 이 allowlist 로 수행한다
    llm_model = serializers.CharField(required=False, allow_blank=True, default='')
