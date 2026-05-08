from django.urls import path

from . import views

urlpatterns = [
    path('businesses/', views.BusinessListCreateView.as_view(), name='business-list'),
    path('businesses/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('businesses/<int:pk>/audit/', views.AuditTriggerView.as_view(), name='audit-trigger'),
    path('audits/<int:pk>/status/', views.AuditStatusView.as_view(), name='audit-status'),
    path('audits/<int:pk>/', views.AuditReportDetailView.as_view(), name='audit-report'),
    path('audits/<int:pk>/issues/', views.AuditIssueListView.as_view(), name='audit-issues'),
    path('audits/<int:pk>/recommendations/', views.RecommendationListView.as_view(), name='audit-recommendations'),
    path('knowledge/seed/', views.SeedKnowledgeView.as_view(), name='knowledge-seed'),
]
