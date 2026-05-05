from rest_framework import serializers
from .models import Business, AuditJob


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
