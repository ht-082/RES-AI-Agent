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
    # 텍스트 추출에 성공했는가. **목록에도 실어야 한다** — 예전에는 업로드 응답에만
    # 담겨서, 새로고침하면 추출 실패 파일이 멀쩡한 파일과 똑같이 보였다.
    # 사용자는 그 파일이 답변에 반영되지 않는다는 것을 알 방법이 없었다.
    parsed = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = ['id', 'conversation', 'message', 'filename', 'file_type',
                  'storage_uri', 'file_size', 'created_at', 'parsed']
        read_only_fields = ['id', 'created_at']

    def get_parsed(self, obj):
        return bool(obj.parsed_text_uri)


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
    # ⚠ default 를 두면 **대화에 저장된 설정이 죽는다.** DRF 는 키가 없어도 default 로
    # 채우므로 `validated_data.get(key, conversation.X)` 의 두 번째 인자가 영영 쓰이지 않는다.
    # None 으로 두고 호출측이 '요청에 값이 있으면 그것, 없으면 대화 설정'을 판정한다.
    use_internal_docs = serializers.BooleanField(required=False, allow_null=True, default=None)
    use_web_search = serializers.BooleanField(required=False, allow_null=True, default=None)
    # 값 검증은 views.resolve_llm_model 이 allowlist 로 수행한다
    llm_model = serializers.CharField(required=False, allow_blank=True, default='')
