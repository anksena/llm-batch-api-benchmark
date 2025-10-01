import os
import json
from datetime import datetime, timezone
from anthropic import Anthropic
from .base import BatchProvider
from logger import get_logger
from data_models import JobStatus

logger = get_logger(__name__)

class AnthropicProvider(BatchProvider):
    """Batch processing provider for Anthropic."""

    def _initialize_client(self, api_key):
        return Anthropic(api_key=api_key)

    def create_jobs(self, num_jobs):
        job_ids = []
        for i in range(num_jobs):
            anthropic_requests = [{
                "custom_id": "request-1",
                "params": {
                    "model": "claude-3-haiku-20240307",
                    "messages": [{"role": "user", "content": self.PROMPT}],
                    "max_tokens": 1024,
                }
            }]

            job = self.client.beta.messages.batches.create(requests=anthropic_requests)
            logger.info(f"Created batch job {i+1}/{num_jobs}: {job.id}")
            job_ids.append(job.id)
        return job_ids

    def check_jobs(self):
        logger.info("Listing status of recent Anthropic jobs:")
        for job in self.client.beta.messages.batches.list(limit=100):
            status = JobStatus(
                job_id=job.id,
                status=job.processing_status,
                created_at=job.created_at.isoformat(),
                ended_at=job.ended_at.isoformat() if job.ended_at else None,
                total_requests=job.request_counts.succeeded + job.request_counts.errored + job.request_counts.expired + job.request_counts.canceled,
                completed_requests=job.request_counts.succeeded,
                failed_requests=job.request_counts.errored
            )
            logger.info(f"Job: {status}")

    def list_models(self):
        logger.warning("Anthropic model listing is not directly supported via a simple API call.")
        logger.warning("Please refer to the official Anthropic documentation for available models.")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.beta.messages.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.processing_status}")
