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
    EMBEDDING_MODEL_NAME = "models/gemini-embedding-001"

    @property
    def _job_status_enum(self):
        return GoogleJobStatus

    @property
    def _job_status_attribute(self):
        return "state.name"

    def _initialize_client(self, api_key):
        return google_genai.Client(api_key=api_key)

    def _create_single_batch_job(self, job_index: int, total_jobs: int,
                               prompts: list[str]) -> str:
        file_path = f"gemini-batch-request-{job_index}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            for i, prompt in enumerate(prompts):
                gemini_req = {
                    "key": f"request-{i}",
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
        elif job.state.name in ('JOB_STATE_PENDING', 'JOB_STATE_RUNNING'):
            if self._should_cancel_for_timeout(job.create_time):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning("Job %s has timed out. Cancelling...", job.name)
                self.cancel_job(job.name)
            else:
                user_status = UserStatus.IN_PROGRESS
        else:
            raise ValueError(f"Unexpected job status: {job.state.name}")

        total_tokens = None
        if user_status == UserStatus.SUCCEEDED:
            total_tokens = self._calculate_total_tokens(job)

        return JobReport(provider="google",
                         job_id=job.name,
                         user_assigned_status=user_status,
                         latency_seconds=latency,
                         total_tokens=total_tokens,
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

    def _create_single_embedding_job(self, job_index: int, total_jobs: int,
                                   prompts: list[str]) -> str:
        """Creates a single batch embedding job with multiple requests."""
        file_path = f"google-batch-request-{job_index}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            for i, prompt in enumerate(prompts):
                google_req = {
                    "model": self.EMBEDDING_MODEL_NAME,
                    "content": {
                        "parts": [{"text": prompt}]
                    },
                    "output_dimensionality": 512
                }
                f.write(json.dumps(google_req) + "\n")
        
        with open(file_path, "rb") as f:
            uploaded_file = self.client.files.upload(
                file=f,
                config=google_genai.types.UploadFileConfig(
                    display_name=f'batch-embeddings-test-{job_index}',
                    mime_type="application/jsonl"
                )
            )
        os.remove(file_path)

        batch_job = self.client.batches.create_embeddings(
            model=self.EMBEDDING_MODEL_NAME,
            src={"file_name": uploaded_file.name},
        )
        logger.info("Created batch job %d/%d: %s", job_index + 1, total_jobs,
                    batch_job.name)
        return batch_job.name

    def _calculate_total_tokens(self, job):
        """Downloads the result file and calculates the total tokens used."""
        total_tokens = 0
        if job.state.name == 'JOB_STATE_SUCCEEDED' and job.dest and job.dest.file_name:
            try:
                logger.info("Calculating total tokens for job %s", job.name)
                result_file_name = job.dest.file_name
                file_content = self.client.files.download(file=result_file_name)
                
                content_str = file_content.decode('utf-8').strip()
                
                # The result file contains one JSON object per line
                for line in content_str.splitlines():
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        if 'response' in result:
                            response = result['response']
                            if 'usageMetadata' in response:
                                total_tokens += response['usageMetadata'].get('totalTokenCount', 0)
                            elif 'embedding' in response:
                                # This is an embedding response, which doesn't have a token count.
                                # We can either skip it or estimate it. For now, we'll skip.
                                pass
                    except json.JSONDecodeError:
                        logger.warning("Could not decode JSON line: %s", line)
                
                logger.info("Total tokens calculated for job %s: %d", job.name, total_tokens)
                return total_tokens
            except Exception as e:
                logger.error("Error calculating tokens for job %s: %s", job.name, e)
        return None

    def download_results(self, job, output_file):
        """Downloads the results of a completed batch job.

        Args:
            job: The provider-specific job object.
            output_file: The path to the output file to save the results to.
        """
        if job.state.name == 'JOB_STATE_SUCCEEDED':
            if job.dest and job.dest.file_name:
                result_file_name = job.dest.file_name
                logger.info("Results are in file: %s", result_file_name)
                logger.info("Downloading result file content...")
                file_content = self.client.files.download(file=result_file_name)
                with open(output_file, "wb") as f:
                    f.write(file_content)
                logger.info("Successfully downloaded results to %s", output_file)
            else:
                logger.info("No results file found for job %s", job.name)
        else:
            logger.warning("Job %s did not succeed. Final state: %s", job.name,
                           job.state.name)
