from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditJob, Business
from .serializers import AuditJobStatusSerializer, BusinessSerializer
from .tasks import scrape_website


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
