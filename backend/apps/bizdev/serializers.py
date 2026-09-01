from rest_framework import serializers

from .models import (
    BudgetEntry, CommunityIssue, Contract, PermitDocument, PermitStage,
    Site, SiteEvent, SiteFact,
)
from .permissions import can_edit_site


class PermitDocumentSerializer(serializers.ModelSerializer):
    # storage_uri 는 내보내지 않는다 — 다운로드는 전용 엔드포인트(권한 검사)로만.
    class Meta:
        model = PermitDocument
        fields = ['id', 'stage', 'version', 'file_name', 'file_size',
                  'is_current', 'note', 'uploaded_by', 'uploaded_at']
        read_only_fields = fields


class PermitStageSerializer(serializers.ModelSerializer):
    documents = PermitDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = PermitStage
        fields = ['id', 'site', 'stage_no', 'name', 'agency', 'category', 'tier',
                  'status', 'content', 'certainty', 'remark', 'progress_pct',
                  'received_date', 'deadline', 'detail', 'dday_label', 'doc_label',
                  'documents']
        read_only_fields = ['id', 'stage_no']  # stage_no 는 서버가 부여/재정렬


class StageSummarySerializer(serializers.ModelSerializer):
    """대시보드 파이프라인 표에 필요한 최소 필드"""
    class Meta:
        model = PermitStage
        fields = ['id', 'stage_no', 'name', 'status', 'progress_pct', 'tier']


class BudgetEntrySerializer(serializers.ModelSerializer):
    has_receipt = serializers.SerializerMethodField()

    class Meta:
        model = BudgetEntry
        fields = ['id', 'site', 'category', 'amount_krw', 'exec_date', 'memo',
                  'receipt_name', 'has_receipt', 'created_by', 'created_at']
        read_only_fields = ['id', 'receipt_name', 'created_by', 'created_at']

    def get_has_receipt(self, obj):
        return bool(obj.receipt_uri)


class CommunityIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityIssue
        fields = ['id', 'site', 'issue_date', 'title', 'status', 'issue_type',
                  'description', 'created_at']
        read_only_fields = ['id', 'created_at']


def overall_pct(site):
    """진척률 = 완료 항목 수 ÷ 대상 항목 수.

    예전에는 항목별 progress_pct 평균이었는데, 그 값은 상태에서 기계적으로
    파생된 수라 근거가 없었다. 사업개요 양식은 완료/미완료만 다루므로
    "10개 중 1개 완료 = 10%"로 세는 편이 설명 가능하다(미대상은 분모에서 제외).
    """
    stages = [s for s in site.stages.all() if s.status != 'na']
    if not stages:
        return 0
    return round(len([s for s in stages if s.status == 'done']) / len(stages) * 100)


class SiteListSerializer(serializers.ModelSerializer):
    """대시보드 단일 호출용 — stages 요약 + 전체 진척도. address_detail 비노출."""
    stages = StageSummarySerializer(many=True, read_only=True)
    overall_pct = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Site
        fields = ['id', 'slug', 'name', 'capacity_mw', 'location', 'sido',
                  'facility_type', 'status', 'risk_tag', 'risk_level',
                  'pm', 'pm_name', 'target_ntp', 'approved_budget_krw',
                  'lat', 'lng', 'energy_type', 'lifecycle', 'annual_gwh', 'cod',
                  'created_at', 'stages', 'overall_pct', 'can_edit']
        read_only_fields = ['id', 'created_at']

    def get_overall_pct(self, obj):
        return overall_pct(obj)

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request and can_edit_site(request.user, obj))


class SiteWriteSerializer(serializers.ModelSerializer):
    """등록/수정 입력 — slug·pm 은 서버가 채운다."""
    class Meta:
        model = Site
        fields = ['name', 'capacity_mw', 'location', 'sido', 'facility_type',
                  'status', 'risk_tag', 'risk_level', 'target_ntp',
                  'approved_budget_krw', 'lat', 'lng', 'energy_type',
                  'lifecycle', 'annual_gwh', 'cod', 'address_detail']


class SiteFactSerializer(serializers.ModelSerializer):
    """사업개요 항목 — 값·확정도·근거·비고만 수정 가능(라벨/키는 정의가 소유)"""
    class Meta:
        model = SiteFact
        fields = ['id', 'site', 'section', 'key', 'label', 'value',
                  'certainty', 'source', 'note', 'sort_order']
        read_only_fields = ['id', 'site', 'section', 'key', 'label', 'sort_order']


class ContractSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Contract
        fields = ['id', 'site', 'category', 'category_label', 'counterparty',
                  'summary', 'certainty', 'status', 'status_label', 'note',
                  'sort_order', 'created_at']
        read_only_fields = ['id', 'created_at']


class SiteEventSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source='get_event_type_display', read_only=True)
    is_ongoing = serializers.BooleanField(read_only=True)

    class Meta:
        model = SiteEvent
        fields = ['id', 'site', 'event_date', 'is_ongoing', 'event_type',
                  'type_label', 'summary', 'certainty', 'created_at']
        read_only_fields = ['id', 'created_at']
