from celery import shared_task


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_item(self, item_id: str) -> str:
    """Long-running enrichment executed by the worker, not the web request."""
    return item_id
