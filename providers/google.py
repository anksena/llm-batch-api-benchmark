import os
import json
import time
from datetime import datetime, timedelta, timezone
from google import genai as google_genai
from .base import BatchProvider
from logger import get_logger
from data_models import JobStatus, BatchJobResult, PerformanceReport

logger = get_logger(__name__)

PROCESSED_JOBS_FILE = ".processed_jobs"

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

    def check_jobs(self):
        logger.info("Checking and processing recent Google jobs...")
        
        for job in self.client.batches.list(): 
            status = JobStatus(
                job_id=job.name,
                status=job.state.name,
                created_at=job.create_time.isoformat(),
                ended_at=job.end_time.isoformat() if job.end_time else None,
                # Google's job object doesn't have request counts, so we leave them as None
            )
            logger.info(f"Job: {status}")

    def list_models(self):
        logger.info("Listing available Gemini models supporting 'batchGenerateContent':")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                logger.info(f"- {m.name}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to delete job (Google's equivalent of cancel): {job_id}")
        self.client.batches.delete(name=job_id)
        logger.info(f"Successfully sent delete request for job: {job_id}")
