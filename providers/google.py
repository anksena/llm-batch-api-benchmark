"""Batch processing provider for Google."""
import os
import json
from datetime import datetime, timedelta, timezone
from google import genai as google_genai
from .base import BatchProvider
from logger import get_logger
from data_models import ServiceReportedJobDetails, JobReport, UserStatus
from enum import Enum


class GoogleJobStatus(Enum):
    JOB_STATE_PENDING = "JOB_STATE_PENDING"
    JOB_STATE_RUNNING = "JOB_STATE_RUNNING"
    JOB_STATE_SUCCEEDED = "JOB_STATE_SUCCEEDED"
    JOB_STATE_FAILED = "JOB_STATE_FAILED"
    JOB_STATE_CANCELLED = "JOB_STATE_CANCELLED"
    JOB_STATE_EXPIRED = "JOB_STATE_EXPIRED"


logger = get_logger(__name__)


class GoogleProvider(BatchProvider):
    """Batch processing provider for Google."""

    MODEL_NAME = "models/gemini-2.5-flash-lite"

    @property
    def _job_status_enum(self):
        return GoogleJobStatus

    @property
    def _job_status_attribute(self):
        return "state.name"

    def _initialize_client(self, api_key):
        return google_genai.Client(api_key=api_key)

    def _create_single_job(self, job_index, total_jobs, prompt):
        file_path = f"gemini-batch-request-{job_index}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            gemini_req = {
                "key": "request-1",
                "request": {
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generation_config": {
                        "max_output_tokens": self.MAX_TOKENS
                    }
                }
            }
            f.write(json.dumps(gemini_req) + "\n")

        uploaded_file = self.client.files.upload(
            file=file_path,
            config=google_genai.types.UploadFileConfig(
                mime_type="application/jsonl"))
        os.remove(file_path)

        job = self.client.batches.create(
            model=self.MODEL_NAME,
            src=uploaded_file.name,
        )
        logger.info("Created batch job %d/%d: %s", job_index + 1, total_jobs,
                    job.name)
        return job.name

    def _get_job_list(self, hours_ago):
        all_jobs = []
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        for job in self.client.batches.list(config={'page_size': 10}):
            if job.create_time < time_threshold:
                break
            all_jobs.append(job)
        return all_jobs

    def _get_job_create_time(self, job):
        return job.create_time

    def _create_report_from_provider_job(self, job):
        latency = None
        if job.state.name == 'JOB_STATE_SUCCEEDED' and job.end_time:
            latency = round((job.end_time - job.create_time).total_seconds(), 2)

        status = ServiceReportedJobDetails(
            job_id=job.name,
            model=job.model,
            service_job_status=job.state.name,
            created_at=job.create_time.isoformat(),
            ended_at=job.end_time.isoformat() if job.end_time else None,
        )

        if job.state.name == 'JOB_STATE_SUCCEEDED':
            user_status = UserStatus.SUCCEEDED
        elif job.state.name == 'JOB_STATE_CANCELLED':
            if job.end_time and (job.end_time -
                                 job.create_time) > timedelta(days=1):
                user_status = UserStatus.CANCELLED_TIMED_OUT
            else:
                user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.state.name == 'JOB_STATE_FAILED':
            user_status = UserStatus.FAILED
        elif job.state.name == 'JOB_STATE_EXPIRED':
            user_status = UserStatus.CANCELLED_TIMED_OUT
        elif job.state.name in ('JOB_STATE_PENDING', 'BATCH_STATE_RUNNING'):
            if self._should_cancel_for_timeout(job.create_time):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning("Job %s has timed out. Cancelling...", job.name)
                self.cancel_job(job.name)
            else:
                user_status = UserStatus.IN_PROGRESS
        else:
            raise ValueError(f"Unexpected job status: {job.state.name}")

        return JobReport(provider="google",
                         job_id=job.name,
                         user_assigned_status=user_status,
                         latency_seconds=latency,
                         service_reported_details=status)

    def cancel_job(self, job_id):
        logger.info("Attempting to delete job (Google's equivalent of cancel): %s",
                    job_id)
        self.client.batches.delete(name=job_id)
        logger.info("Successfully sent delete request for job: %s", job_id)

    def get_job_details_from_provider(self, job_id):
        return self.client.batches.get(name=job_id)

    def get_provider_name(self):
        return "google"
