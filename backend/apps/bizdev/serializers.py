from rest_framework import serializers

from .models import (
    DefectItem, OpsDaily, OpsPlanItem, PortfolioKpi, SiteDocument,
    BudgetApproval, BudgetEntry, CommunityIssue, Contract, PermitDocument,
    PermitStage, Site, SiteEvent, SiteFact, WatchedLaw,
)
from .constants import fact_spec, stage_spec
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
    # 본문에 채울 칸 목록(허가번호·용량 등). 비어 있으면 자유 입력으로 그린다.
    content_fields = serializers.SerializerMethodField()

    class Meta:
        model = PermitStage
        fields = ['id', 'site', 'stage_no', 'name', 'agency', 'category', 'tier',
                  'status', 'content', 'content_fields', 'certainty', 'remark',
                  'received_date', 'deadline', 'detail',
                  'dday_label', 'doc_label', 'documents', 'updated_at', 'is_custom']
        read_only_fields = ['id', 'stage_no', 'is_custom']  # 서버가 부여/재정렬

    def get_content_fields(self, obj):
        return (stage_spec(obj.name) or {}).get('content_fields', [])


class StageSummarySerializer(serializers.ModelSerializer):
    """대시보드 파이프라인 표에 필요한 최소 필드"""
    class Meta:
        model = PermitStage
        fields = ['id', 'stage_no', 'name', 'status', 'tier']


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


class SiteListSerializer(serializers.ModelSerializer):
    """대시보드 단일 호출용 — stages 요약. address_detail 비노출.

    진척률(%)은 두지 않는다. 상태에서 기계적으로 만든 수라 근거가 없고,
    화면에서도 쓰지 않는다 — 완료 개수만 센다.
    """
    stages = StageSummarySerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Site
        fields = ['id', 'slug', 'name', 'capacity_mw', 'location', 'sido',
                  'facility_type', 'status', 'risk_tag', 'risk_level',
                  'pm', 'pm_name', 'target_ntp', 'approved_budget_krw',
                  'lat', 'lng', 'energy_type', 'lifecycle', 'annual_gwh', 'cod',
                  'created_at', 'stages', 'can_edit']
        read_only_fields = ['id', 'created_at']

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
                  'amount', 'summary', 'certainty', 'status', 'status_label',
                  'note', 'sort_order', 'created_at', 'updated_at']
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


class OpsDailySerializer(serializers.ModelSerializer):
    class Meta:
        model = OpsDaily
        fields = ['id', 'site', 'date', 'generation_mwh', 'pr_pct', 'revenue_krw',
                  'note', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class OpsPlanItemSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OpsPlanItem
        fields = ['id', 'site', 'month', 'title', 'cycle', 'owner', 'status',
                  'status_label', 'done_date', 'note', 'updated_at']
        read_only_fields = ['id', 'status_label', 'updated_at']


class DefectItemSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DefectItem
        fields = ['id', 'site', 'found_date', 'part', 'summary', 'status',
                  'status_label', 'fixed_date', 'counterparty', 'note', 'updated_at']
        read_only_fields = ['id', 'status_label', 'updated_at']


class SiteDocumentSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = SiteDocument
        fields = ['id', 'site', 'category', 'category_label', 'title', 'doc_date',
                  'file_name', 'file_size', 'has_file', 'note', 'created_at', 'updated_at']
        read_only_fields = ['id', 'category_label', 'file_name', 'file_size',
                            'has_file', 'created_at', 'updated_at']

    def get_has_file(self, obj):
        return bool(obj.storage_uri)


class PortfolioKpiSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source='get_key_display', read_only=True)

    class Meta:
        model = PortfolioKpi
        fields = ['key', 'label', 'value', 'note', 'updated_at']
        read_only_fields = ['key', 'label', 'updated_at']


class WatchedLawSerializer(serializers.ModelSerializer):
    """관심 대상 — 법령명(kind='law') 또는 본문 키워드(kind='keyword').

    law_name·ministry 는 법령일 때만 붙여 준다(저장하지 않는다 — 법령 메타가
    바뀌면 스냅샷·법제처 한 곳만 갱신되게).
    """
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    law_name = serializers.SerializerMethodField()
    ministry = serializers.SerializerMethodField()

    class Meta:
        model = WatchedLaw
        fields = ['id', 'kind', 'kind_label', 'term', 'law_name', 'ministry',
                  'sort_order', 'created_at']
        read_only_fields = ['id', 'kind_label', 'law_name', 'ministry', 'created_at']

    def _meta_of(self, obj):
        """정식 명칭·소관은 법제처에서(캐시된 동향 조회 결과 재사용), 없으면 스냅샷.

        검색으로 담은 법은 스냅샷에 없으므로 그쪽만 보면 이름이 빈다.
        """
        from . import lawapi, snapshots
        if obj.kind != 'law':
            return {}
        live = lawapi.rows_for_family(obj.term)
        if live:
            head = next((r for r in live if r['law_name'] == obj.term), live[0])
            return {'law_name': head['law_name'], 'ministry': head['ministry']}
        cache = getattr(self, '_catalog_cache', None)
        if cache is None:
            cache = {g['family']: g for g in snapshots.law_catalog()}
            self._catalog_cache = cache
        return cache.get(obj.term) or {}

    def get_law_name(self, obj):
        return self._meta_of(obj).get('law_name') or obj.term

    def get_ministry(self, obj):
        return self._meta_of(obj).get('ministry') or ''

    def validate(self, attrs):
        """담기 전에 실제로 걸리는 게 있는지 확인한다.

        오타는 동향 표에 영영 빈 줄로 남는다 — 담는 순간에 잡는 편이 낫다.
        법령명은 그 이름이 있는지, 키워드는 한 건이라도 물어오는지 본다.
        """
        from . import lawapi, snapshots
        kind = attrs.get('kind') or 'law'
        term = (attrs.get('term') or '').strip()
        if len(term) < 2:
            raise serializers.ValidationError({'term': '두 글자 이상 입력해 주세요.'})
        attrs['term'] = term

        if kind == 'keyword':
            hits = lawapi.rows_for_keyword(term) if lawapi.enabled() else None
            if hits is None:
                hits = snapshots.laws_matching(term)
            if not hits:
                raise serializers.ValidationError(
                    {'term': '이 말이 들어간 법령을 찾지 못했습니다.'})
            return attrs

        if lawapi.enabled():
            found = lawapi.search_families(term)
            if found is None:
                raise serializers.ValidationError(
                    {'term': '법제처 조회에 실패했습니다. 잠시 후 다시 시도해 주세요.'})
            if not any(g['family'] == term for g in found):
                raise serializers.ValidationError({'term': '법제처에서 찾지 못한 이름입니다.'})
            return attrs
        names = {g['family'] for g in snapshots.law_catalog()}
        if term not in names:
            raise serializers.ValidationError({'term': '법령 목록에 없는 이름입니다.'})
        return attrs
