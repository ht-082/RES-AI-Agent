from rest_framework import serializers
from .models import ContractTemplate, ContractDraft, ContractReview, ContractReviewFinding


class ContractTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTemplate
        fields = ['id', 'code', 'name_ko', 'name_en', 'category', 'description',
                  'key_term_schema', 'is_active', 'version', 'created_at']
        read_only_fields = ['id', 'created_at']


class ContractTemplateDetailSerializer(ContractTemplateSerializer):
    class Meta(ContractTemplateSerializer.Meta):
        fields = ContractTemplateSerializer.Meta.fields + [
            'template_body', 'standard_clauses', 'review_checklist'
        ]


class ContractDraftSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name_ko', read_only=True, allow_null=True)

    class Meta:
        model = ContractDraft
        fields = ['id', 'project', 'template', 'template_name', 'title',
                  'key_terms', 'generated_content', 'output_file_uri',
                  'status', 'created_at', 'updated_at',
                  'user', 'type_id', 'inputs', 'generated_articles']
        read_only_fields = ['id', 'generated_content', 'output_file_uri', 'status',
                            'created_at', 'updated_at']


class ContractReviewFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractReviewFinding
        fields = ['id', 'clause_ref', 'severity', 'category', 'finding',
                  'suggestion', 'source_clause_ref', 'order_index', 'created_at']
        read_only_fields = ['id', 'created_at']


class ContractReviewSerializer(serializers.ModelSerializer):
    findings = ContractReviewFindingSerializer(many=True, read_only=True)
    template_name = serializers.CharField(source='template.name_ko', read_only=True, allow_null=True)

    class Meta:
        model = ContractReview
        fields = ['id', 'project', 'template', 'template_name', 'title',
                  'source_document_uri', 'review_instruction', 'summary',
                  'output_file_uri', 'status', 'created_by',
                  'created_at', 'updated_at', 'findings']
        read_only_fields = ['id', 'summary', 'output_file_uri', 'status',
                            'created_at', 'updated_at', 'findings']
