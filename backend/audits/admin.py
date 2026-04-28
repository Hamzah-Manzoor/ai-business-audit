from django.contrib import admin
from audits.models import (
    Business, AuditJob, AuditReport, AuditIssue,
    Recommendation, KnowledgeDoc, ScrapedPage,
)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'industry_type', 'created_at')
    search_fields = ('name', 'url')


@admin.register(AuditJob)
class AuditJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'status', 'triggered_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('business__name',)


@admin.register(AuditReport)
class AuditReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'audit_job', 'overall_score', 'seo_score', 'conversion_score', 'created_at')


@admin.register(AuditIssue)
class AuditIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'severity', 'score', 'created_at')
    list_filter = ('category', 'severity')
    search_fields = ('title', 'parameter_key')


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority_score', 'effort', 'impact', 'created_at')
    list_filter = ('effort', 'impact')


@admin.register(KnowledgeDoc)
class KnowledgeDocAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'source', 'created_at')
    list_filter = ('category',)
    search_fields = ('title', 'content')


@admin.register(ScrapedPage)
class ScrapedPageAdmin(admin.ModelAdmin):
    list_display = ('url', 'business', 'https', 'status_code', 'load_time_ms', 'scraped_at')
    list_filter = ('https',)
    search_fields = ('url',)
