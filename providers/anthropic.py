import os
import json
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from .base import BatchProvider
from logger import get_logger
from data_models import JobStatus, JobReport, UserStatus

logger = get_logger(__name__)

class AnthropicProvider(BatchProvider):
    """Batch processing provider for Anthropic."""

    MODEL_NAME = "claude-3-haiku-20240307"

    def _initialize_client(self, api_key):
        return Anthropic(api_key=api_key)

    def create_jobs(self, num_jobs):
        job_ids = []
        for i in range(num_jobs):
            anthropic_requests = [{
                "custom_id": "request-1",
                "params": {
                    "model": self.MODEL_NAME,
                    "messages": [{"role": "user", "content": self.PROMPT}],
                    "max_tokens": self.MAX_TOKENS,
                }
            }]

            job = self.client.beta.messages.batches.create(requests=anthropic_requests)
            logger.info(f"Created batch job {i+1}/{num_jobs}: {job.id}")
            job_ids.append(job.id)
        return job_ids

    def _get_job_list(self):
        return self.client.beta.messages.batches.list(limit=100)

    def _process_job(self, job):
        if self._should_skip_job(job.created_at):
            return None
        
        latency = None
        if job.ended_at:
            latency = round((job.ended_at - job.created_at).total_seconds(), 2)

        status = JobStatus(
            job_id=job.id,
            model=self.MODEL_NAME,
            status=job.processing_status,
            created_at=job.created_at.isoformat(),
            ended_at=job.ended_at.isoformat() if job.ended_at else None,
            total_requests=job.request_counts.succeeded + job.request_counts.errored + job.request_counts.expired + job.request_counts.canceled,
            completed_requests=job.request_counts.succeeded,
            failed_requests=job.request_counts.errored
        )

        user_status = UserStatus.UNKNOWN
        if job.processing_status == 'completed' or (job.processing_status == 'ended' and job.request_counts.succeeded > 0):
            user_status = UserStatus.SUCCEEDED
        elif job.processing_status == 'cancelled':
            if job.ended_at and (job.ended_at - job.created_at) > timedelta(days=1):
                user_status = UserStatus.CANCELLED_TIMED_OUT
            else:
                user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.processing_status in ('failed', 'expired', 'ended'):
            user_status = UserStatus.FAILED
        elif job.processing_status == 'in_progress':
            if self._should_cancel_for_timeout(job.created_at):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning(f"Job {job.id} has timed out. Cancelling...")
                self.cancel_job(job.id)
            else:
                user_status = UserStatus.IN_PROGRESS
        
        return JobReport(provider="anthropic", job_id=job.id, user_assigned_status=user_status, latency_seconds=latency, service_reported_details=status)

    def list_models(self):
        logger.warning("Anthropic model listing is not directly supported via a simple API call.")
        logger.warning("Please refer to the official Anthropic documentation for available models.")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.beta.messages.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.processing_status}")
