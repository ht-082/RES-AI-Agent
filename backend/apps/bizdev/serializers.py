from rest_framework import serializers

from .models import (
    BudgetApproval, BudgetEntry, CommunityIssue, Contract, PermitDocument,
    PermitStage, Site, SiteEvent, SiteFact,
)
from .constants import fact_spec
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
                  'documents', 'updated_at', 'is_custom']
        read_only_fields = ['id', 'stage_no', 'is_custom']  # 서버가 부여/재정렬


class StageSummarySerializer(serializers.ModelSerializer):
    """대시보드 파이프라인 표에 필요한 최소 필드"""
    class Meta:
        model = PermitStage
        fields = ['id', 'stage_no', 'name', 'status', 'progress_pct', 'tier']


class BudgetApprovalSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = BudgetApproval
        fields = ['id', 'site', 'category', 'category_label', 'amount_krw',
                  'approved_date', 'memo', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BudgetEntrySerializer(serializers.ModelSerializer):
    has_receipt = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = BudgetEntry
        fields = ['id', 'site', 'category', 'category_label', 'amount_krw',
                  'exec_date', 'payee', 'memo', 'receipt_name', 'has_receipt',
                  'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'receipt_name', 'created_by', 'created_at',
                            'updated_at']

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
    """사업개요 항목.

    input_spec 은 화면이 어떤 입력기를 그릴지 알려 준다(드롭다운·숫자·날짜 등).
    derived 항목(총사업비·경제성)은 다른 섹션 값을 그대로 보여 주는 읽기 전용이라
    여기서 값을 계산해 실어 보낸다 — 같은 수치가 두 곳에서 어긋나지 않게.
    """
    input_spec = serializers.SerializerMethodField()

    class Meta:
        model = SiteFact
        fields = ['id', 'site', 'section', 'key', 'label', 'value',
                  'certainty', 'source', 'note', 'sort_order', 'input_spec',
                  'updated_at']
        read_only_fields = ['id', 'site', 'section', 'key', 'label', 'sort_order']

    def get_input_spec(self, obj):
        spec = fact_spec(obj.section, obj.key) or {}
        out = {'input': spec.get('input', 'text')}
        for k in ('options', 'unit', 'display', 'parent'):
            if spec.get(k):
                out[k] = spec[k]
        return out

    def to_representation(self, obj):
        data = super().to_representation(obj)
        spec = fact_spec(obj.section, obj.key) or {}
        if spec.get('input') == 'derived':
            data['value'] = self._derived(obj, spec)
        return data

    def _derived(self, obj, spec):
        """다른 섹션 항목에서 값을 끌어온다(총사업비 = 경제성의 총사업비 등)."""
        by_key = {(f.section, f.key): f for f in obj.site.facts.all()}
        parts = []
        for ref in (spec.get('source'), spec.get('also')):
            if not ref:
                continue
            src = by_key.get(tuple(ref))
            if src and src.value:
                label = (fact_spec(*ref) or {}).get('label', '')
                short = label.split('(')[0].strip()
                unit = spec.get('unit') or ('%' if '%' in label else '')
                parts.append(f'{short} {src.value}{unit}' if spec.get('also')
                             else f'{src.value}{unit}')
        return ' · '.join(parts)


class ContractSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Contract
        fields = ['id', 'site', 'category', 'category_label', 'counterparty',
                  'summary', 'certainty', 'status', 'status_label', 'note',
                  'sort_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SiteEventSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source='get_event_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    is_ongoing = serializers.BooleanField(read_only=True)

    class Meta:
        model = SiteEvent
        fields = ['id', 'site', 'event_date', 'is_ongoing', 'event_type',
                  'type_label', 'status', 'status_label', 'summary', 'certainty',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
