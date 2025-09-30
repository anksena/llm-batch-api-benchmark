import os
import json
from anthropic import Anthropic
from .base import BatchProvider
from logger import get_logger

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

    def check_and_process_jobs(self):
        logger.info("Listing status of last 100 Anthropic jobs:")
        for job in self.client.beta.messages.batches.list(limit=100):
            logger.info(f"  - Job ID: {job.id}, Status: {job.processing_status}")

    def list_models(self):
        logger.warning("Anthropic model listing is not directly supported via a simple API call.")
        logger.warning("Please refer to the official Anthropic documentation for available models.")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.beta.messages.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.processing_status}")
