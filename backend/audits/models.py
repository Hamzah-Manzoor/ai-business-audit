from django.db import models
from pgvector.django import VectorField


class Business(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    industry_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'businesses'

    def __str__(self):
        return self.name


class AuditJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='audit_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    triggered_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"AuditJob {self.id} ({self.status}) for {self.business}"


class AuditReport(models.Model):
    audit_job = models.OneToOneField(AuditJob, on_delete=models.CASCADE, related_name='report')
    overall_score = models.IntegerField(default=0)
    seo_score = models.IntegerField(default=0)
    conversion_score = models.IntegerField(default=0)
    content_score = models.IntegerField(default=0)
    tech_score = models.IntegerField(default=0)
    trust_score = models.IntegerField(default=0)
    raw_llm_response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report for Job {self.audit_job_id} (score: {self.overall_score})"


class AuditIssue(models.Model):
    CATEGORY_CHOICES = [
        ('seo', 'SEO'),
        ('conversion', 'Conversion'),
        ('content', 'Content'),
        ('tech', 'Tech'),
        ('trust', 'Trust'),
    ]
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    report = models.ForeignKey(AuditReport, on_delete=models.CASCADE, related_name='issues')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    parameter_key = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.severity.upper()}: {self.title}"


class Recommendation(models.Model):
    EFFORT_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    IMPACT_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]

    report = models.ForeignKey(AuditReport, on_delete=models.CASCADE, related_name='recommendations')
    issue = models.ForeignKey(
        AuditIssue, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recommendations',
    )
    priority_score = models.FloatField(default=0.0)
    effort = models.CharField(max_length=10, choices=EFFORT_CHOICES)
    impact = models.CharField(max_length=10, choices=IMPACT_CHOICES)
    title = models.CharField(max_length=255)
    rationale = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority_score']

    def __str__(self):
        return f"Recommendation: {self.title}"


class KnowledgeDoc(models.Model):
    title = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=100)
    content = models.TextField()
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    source = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ScrapedPage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='scraped_pages')
    audit_job = models.ForeignKey(AuditJob, on_delete=models.CASCADE, related_name='scraped_pages')
    url = models.URLField(max_length=500)
    html_content = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    h1_tags = models.JSONField(default=list)
    h2_tags = models.JSONField(default=list)
    internal_links = models.JSONField(default=list)
    image_alts = models.JSONField(default=list)
    load_time_ms = models.IntegerField(null=True, blank=True)
    https = models.BooleanField(default=False)
    status_code = models.IntegerField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ScrapedPage: {self.url}"
