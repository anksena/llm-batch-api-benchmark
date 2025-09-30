import os
import json
from openai import OpenAI
from .base import BatchProvider
from logger import get_logger

logger = get_logger(__name__)

class OpenAIProvider(BatchProvider):
    """Batch processing provider for OpenAI."""

    def _initialize_client(self, api_key):
        return OpenAI(api_key=api_key)

    def create_jobs(self, num_jobs):
        job_ids = []
        for i in range(num_jobs):
            file_path = f"openai-batch-request-{i}.jsonl"
            with open(file_path, "w") as f:
                openai_req = {
                    "custom_id": "request-1",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": self.PROMPT}]
                    }
                }
                f.write(json.dumps(openai_req) + "\n")

            with open(file_path, "rb") as f:
                batch_file = self.client.files.create(file=f, purpose="batch")
            os.remove(file_path)

            job = self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )
            logger.info(f"Created batch job {i+1}/{num_jobs}: {job.id}")
            job_ids.append(job.id)
        return job_ids

    def check_and_process_jobs(self):
        logger.info("Listing status of last 100 OpenAI jobs:")
        for job in self.client.batches.list(limit=100).data:
            logger.info(f"  - Job ID: {job.id}, Status: {job.status}")

    def list_models(self):
        logger.info("Listing available OpenAI models:")
        for model in self.client.models.list().data:
            logger.info(f"- {model.id}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.status}")
