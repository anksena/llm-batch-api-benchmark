import os
import json
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from .base import BatchProvider
from logger import get_logger
from data_models import JobStatus, JobReport, UserStatus

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
                        "messages": [{"role": "user", "content": self.PROMPT}],
                        "max_tokens": self.MAX_TOKENS
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

    def _get_job_list(self):
        return self.client.batches.list(limit=100).data

    def _process_job(self, job):
        if self._should_skip_job(datetime.fromtimestamp(job.created_at, tz=timezone.utc)):
            return None
        
        status = JobStatus(
            job_id=job.id,
            model=job.model,
            status=job.status,
            created_at=datetime.fromtimestamp(job.created_at, tz=timezone.utc).isoformat(),
            ended_at=datetime.fromtimestamp(job.completed_at, tz=timezone.utc).isoformat() if job.completed_at else None,
            total_requests=job.request_counts.total,
            completed_requests=job.request_counts.completed,
            failed_requests=job.request_counts.failed
        )

        user_status = UserStatus.UNKNOWN
        if job.status == 'completed':
            user_status = UserStatus.SUCCEEDED
        elif job.status == 'cancelled':
            if job.completed_at and (datetime.fromtimestamp(job.completed_at, tz=timezone.utc) - datetime.fromtimestamp(job.created_at, tz=timezone.utc)) > timedelta(days=1):
                user_status = UserStatus.CANCELLED_TIMED_OUT
            else:
                user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.status in ('failed', 'expired'):
            user_status = UserStatus.FAILED
        elif job.status in ('validating', 'in_progress'):
            if self._should_cancel_for_timeout(datetime.fromtimestamp(job.created_at, tz=timezone.utc)):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning(f"Job {job.id} has timed out. Cancelling...")
                self.cancel_job(job.id)
            else:
                user_status = UserStatus.IN_PROGRESS
        
        return JobReport(provider="openai", job_id=job.id, user_assigned_status=user_status, service_reported_details=status)

    def list_models(self):
        logger.info("Listing available OpenAI models:")
        for model in self.client.models.list().data:
            logger.info(f"- {model.id}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.status}")
