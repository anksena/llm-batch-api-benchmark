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

    def create_jobs(self, num_jobs):
        job_ids = []
        for i in range(num_jobs):
            file_path = f"gemini-batch-request-{i}.jsonl"
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
            logger.info(f"Created batch job {i+1}/{num_jobs}: {job.name}")
            job_ids.append(job.name)
        return job_ids

    def process_jobs(self, output_file):
        logger.info(f"Processing recent Google jobs and appending to {output_file}...")

        with open(output_file, "a") as f:
            for job in self.client.batches.list():
                if self._should_skip_job(job.create_time):
                    continue
                
                report = self._process_job(job)
                f.write(report.to_json() + "\n")

    def _process_job(self, job):
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
        
        return JobReport(provider="google", job_id=job.name, user_assigned_status=user_status, service_reported_details=status)

    def list_models(self):
        logger.info("Listing available Gemini models supporting 'batchGenerateContent':")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                logger.info(f"- {m.name}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to delete job (Google's equivalent of cancel): {job_id}")
        self.client.batches.delete(name=job_id)
        logger.info(f"Successfully sent delete request for job: {job_id}")
