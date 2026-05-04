from celery import shared_task


@shared_task
def scrape_website(audit_job_id):
    pass
