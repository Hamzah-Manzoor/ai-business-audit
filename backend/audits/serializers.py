from rest_framework import serializers

from .models import AuditIssue, AuditJob, AuditReport, Business


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'url', 'industry_type', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AuditJobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditJob
        fields = ['id', 'status', 'triggered_at', 'completed_at', 'error_message']
        read_only_fields = ['id', 'status', 'triggered_at', 'completed_at', 'error_message']


class AuditIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditIssue
        fields = ['id', 'category', 'severity', 'title', 'description', 'parameter_key', 'score', 'created_at']
        read_only_fields = fields


class AuditReportSerializer(serializers.ModelSerializer):
    issues = AuditIssueSerializer(many=True, read_only=True)

    class Meta:
        model = AuditReport
        fields = [
            'id', 'audit_job_id', 'overall_score',
            'seo_score', 'conversion_score', 'content_score', 'tech_score', 'trust_score',
            'created_at', 'issues',
        ]
        read_only_fields = fields
