import os
import json
from datetime import datetime, timedelta, timezone
from google import genai as google_genai
from .base import BatchProvider
from logger import get_logger
from data_models import JobStatus, JobReport, UserStatus

logger = get_logger(__name__)

class GoogleProvider(BatchProvider):
    """Batch processing provider for Google."""

    def _initialize_client(self, api_key):
        return google_genai.Client(api_key=api_key)

    def _create_single_job(self, job_index, total_jobs):
        file_path = f"gemini-batch-request-{job_index}.jsonl"
        with open(file_path, "w") as f:
            gemini_req = {
                "key": "request-1", 
                "request": {
                    "contents": [{"parts": [{"text": self.PROMPT}]}],
                    "generation_config": {
                        "max_output_tokens": self.MAX_TOKENS
                    }
                }
            }
            f.write(json.dumps(gemini_req) + "\n")
        
        uploaded_file = self.client.files.upload(
            file=file_path,
            config=google_genai.types.UploadFileConfig(mime_type="application/jsonl")
        )
        os.remove(file_path)

        job = self.client.batches.create(
            model="models/gemini-2.5-flash-lite",
            src=uploaded_file.name,
        )
        logger.info(f"Created batch job {job_index+1}/{total_jobs}: {job.name}")
        return job.name

    def _get_job_list(self):
        all_jobs = []
        thirty_six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=36)
        for job in self.client.batches.list(config={'page_size': 10}):
            if job.create_time < thirty_six_hours_ago:
                break
            all_jobs.append(job)
        return all_jobs

    def _get_job_create_time(self, job):
        return job.create_time

    def _process_job(self, job):
        latency = None
        if job.end_time:
            latency = round((job.end_time - job.create_time).total_seconds(), 2)

        status = JobStatus(
            job_id=job.name,
            model=job.model,
            status=job.state.name,
            created_at=job.create_time.isoformat(),
            ended_at=job.end_time.isoformat() if job.end_time else None,
        )

        user_status = UserStatus.UNKNOWN
        if job.state.name == 'JOB_STATE_SUCCEEDED':
            user_status = UserStatus.SUCCEEDED
        elif job.state.name == 'JOB_STATE_CANCELLED':
            if job.end_time and (job.end_time - job.create_time) > timedelta(days=1):
                user_status = UserStatus.CANCELLED_TIMED_OUT
            else:
                user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.state.name in ('JOB_STATE_FAILED', 'JOB_STATE_EXPIRED'):
            user_status = UserStatus.FAILED
        elif job.state.name in ('JOB_STATE_PENDING', 'BATCH_STATE_RUNNING'):
            if self._should_cancel_for_timeout(job.create_time):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning(f"Job {job.name} has timed out. Cancelling...")
                self.cancel_job(job.name)
            else:
                user_status = UserStatus.IN_PROGRESS
        
        return JobReport(provider="google", job_id=job.name, user_assigned_status=user_status, latency_seconds=latency, service_reported_details=status)

    def list_models(self):
        logger.info("Listing available Gemini models supporting 'batchGenerateContent':")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                logger.info(f"- {m.name}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to delete job (Google's equivalent of cancel): {job_id}")
        self.client.batches.delete(name=job_id)
        logger.info(f"Successfully sent delete request for job: {job_id}")

    def check_single_job(self, job_id):
        job = self.client.batches.get(name=job_id)
        report = self._process_job(job)
        if report:
            print(report.to_json())
