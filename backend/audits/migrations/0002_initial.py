import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import pgvector.django


class Migration(migrations.Migration):
    dependencies = [
        ('audits', '0001_pgvector_extension'),
    ]

    operations = [
        migrations.CreateModel(
            name='Business',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('url', models.URLField(max_length=500)),
                ('industry_type', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'businesses',
            },
        ),
        migrations.CreateModel(
            name='AuditJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')],
                    default='pending',
                    max_length=20,
                )),
                ('triggered_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('business', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_jobs',
                    to='audits.business',
                )),
            ],
        ),
        migrations.CreateModel(
            name='AuditReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('overall_score', models.IntegerField(default=0)),
                ('seo_score', models.IntegerField(default=0)),
                ('conversion_score', models.IntegerField(default=0)),
                ('content_score', models.IntegerField(default=0)),
                ('tech_score', models.IntegerField(default=0)),
                ('trust_score', models.IntegerField(default=0)),
                ('raw_llm_response', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('audit_job', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='report',
                    to='audits.auditjob',
                )),
            ],
        ),
        migrations.CreateModel(
            name='AuditIssue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[('seo', 'SEO'), ('conversion', 'Conversion'), ('content', 'Content'), ('tech', 'Tech'), ('trust', 'Trust')],
                    max_length=20,
                )),
                ('severity', models.CharField(
                    choices=[('critical', 'Critical'), ('warning', 'Warning'), ('info', 'Info')],
                    max_length=20,
                )),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('parameter_key', models.CharField(max_length=100)),
                ('score', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('report', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='issues',
                    to='audits.auditreport',
                )),
            ],
        ),
        migrations.CreateModel(
            name='Recommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority_score', models.FloatField(default=0.0)),
                ('effort', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                    max_length=10,
                )),
                ('impact', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                    max_length=10,
                )),
                ('title', models.CharField(max_length=255)),
                ('rationale', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('report', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recommendations',
                    to='audits.auditreport',
                )),
                ('issue', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recommendations',
                    to='audits.auditissue',
                )),
            ],
            options={
                'ordering': ['-priority_score'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeDoc',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('category', models.CharField(max_length=100)),
                ('content', models.TextField()),
                ('embedding', pgvector.django.VectorField(blank=True, dimensions=1536, null=True)),
                ('source', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ScrapedPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=500)),
                ('html_content', models.TextField(blank=True)),
                ('extracted_text', models.TextField(blank=True)),
                ('meta_title', models.CharField(blank=True, max_length=255)),
                ('meta_description', models.TextField(blank=True)),
                ('h1_tags', models.JSONField(default=list)),
                ('h2_tags', models.JSONField(default=list)),
                ('internal_links', models.JSONField(default=list)),
                ('load_time_ms', models.IntegerField(blank=True, null=True)),
                ('https', models.BooleanField(default=False)),
                ('status_code', models.IntegerField(blank=True, null=True)),
                ('scraped_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scraped_pages',
                    to='audits.business',
                )),
                ('audit_job', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scraped_pages',
                    to='audits.auditjob',
                )),
            ],
        ),
    ]
