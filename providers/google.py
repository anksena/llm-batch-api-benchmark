import os
import json
from google import genai as google_genai
from .base import BatchProvider
from logger import get_logger

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

    def check_and_process_jobs(self):
        logger.info("Listing status of last 100 Google jobs:")
        for job in self.client.batches.list(): 
            logger.info(f"  - Job ID: {job.name}, Status: {job.state.name}")

    def list_models(self):
        logger.info("Listing available Gemini models supporting 'batchGenerateContent':")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                logger.info(f"- {m.name}")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to delete job (Google's equivalent of cancel): {job_id}")
        self.client.batches.delete(name=job_id)
        logger.info(f"Successfully sent delete request for job: {job_id}")
