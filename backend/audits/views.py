from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditJob, AuditReport, Business
from .serializers import (
    AuditIssueSerializer,
    AuditJobStatusSerializer,
    AuditReportSerializer,
    BusinessSerializer,
    RecommendationSerializer,
)
from .tasks import scrape_website
from .management.commands.seed_knowledge import seed_knowledge_base


class BusinessListCreateView(generics.ListCreateAPIView):
    queryset = Business.objects.all().order_by('-created_at')
    serializer_class = BusinessSerializer


class BusinessDetailView(generics.RetrieveAPIView):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer


class AuditTriggerView(APIView):
    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        job = AuditJob.objects.create(business=business)
        scrape_website.delay(job.id)
        return Response({'audit_job_id': job.id, 'status': job.status}, status=status.HTTP_201_CREATED)


class AuditStatusView(generics.RetrieveAPIView):
    queryset = AuditJob.objects.all()
    serializer_class = AuditJobStatusSerializer


class AuditReportDetailView(generics.RetrieveAPIView):
    serializer_class = AuditReportSerializer

    def get_object(self):
        return get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])


class AuditIssueListView(generics.ListAPIView):
    serializer_class = AuditIssueSerializer

    def get_queryset(self):
        report = get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])
        qs = report.issues.all()
        category = self.request.query_params.get('category')
        severity = self.request.query_params.get('severity')
        if category:
            qs = qs.filter(category=category)
        if severity:
            qs = qs.filter(severity=severity)
        return qs


class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        report = get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])
        return report.recommendations.all()


class SeedKnowledgeView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            created, skipped = seed_knowledge_base()
            return Response({'created': created, 'skipped': skipped})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
