"""Batch processing provider for OpenAI."""
import os
import json
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from .base import BatchProvider
from logger import get_logger
from data_models import ServiceReportedJobDetails, JobReport, UserStatus
from enum import Enum


class OpenAIJobStatus(Enum):
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


logger = get_logger(__name__)


class OpenAIProvider(BatchProvider):
    """Batch processing provider for OpenAI."""

    MODEL_NAME = "gpt-4o-mini"

    @property
    def _job_status_enum(self):
        return OpenAIJobStatus

    @property
    def _job_status_attribute(self):
        return "status"

    def _initialize_client(self, api_key):
        return OpenAI(api_key=api_key)

    def _create_single_batch_job(self, job_index: int, total_jobs: int,
                               prompts: list[str]) -> str:
        file_path = f"openai-batch-request-{job_index}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            for i, prompt in enumerate(prompts):
                openai_req = {
                    "custom_id": f"request-{i}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.MODEL_NAME,
                        "messages": [{
                            "role": "user",
                            "content": prompt
                        }],
                        "max_tokens": self.MAX_TOKENS
                    }
                }
                f.write(json.dumps(openai_req) + "\n")

        with open(file_path, "rb") as f:
            batch_file = self.client.files.create(file=f, purpose="batch")
        os.remove(file_path)

        job = self.client.batches.create(input_file_id=batch_file.id,
                                         endpoint="/v1/chat/completions",
                                         completion_window="24h")
        logger.info("Created batch job %d/%d: %s", job_index + 1, total_jobs,
                    job.id)
        return job.id

    def _get_job_list(self, hours_ago):
        all_jobs = []
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        for page in self.client.batches.list(limit=10).iter_pages():
            for job in page.data:
                job_create_time = datetime.fromtimestamp(job.created_at,
                                                         tz=timezone.utc)
                if job_create_time < time_threshold:
                    return all_jobs
                all_jobs.append(job)
        return all_jobs

    def _get_job_create_time(self, job):
        return datetime.fromtimestamp(job.created_at, tz=timezone.utc)

    def _create_report_from_provider_job(self, job):
        latency = None
        if job.status == 'completed' and job.completed_at:
            latency = round(job.completed_at - job.created_at, 2)

        status = ServiceReportedJobDetails(
            job_id=job.id,
            model=job.model,
            service_job_status=job.status,
            created_at=datetime.fromtimestamp(job.created_at,
                                              tz=timezone.utc).isoformat(),
            ended_at=datetime.fromtimestamp(job.completed_at,
                                            tz=timezone.utc).isoformat()
            if job.completed_at else None,
            total_requests=job.request_counts.total,
            completed_requests=job.request_counts.completed,
            failed_requests=job.request_counts.failed)

        if job.status == 'completed':
            user_status = UserStatus.SUCCEEDED
        elif job.status == 'cancelled':
            if job.completed_at and (datetime.fromtimestamp(
                    job.completed_at, tz=timezone.utc) - datetime.fromtimestamp(
                        job.created_at, tz=timezone.utc)) > timedelta(days=1):
                user_status = UserStatus.CANCELLED_TIMED_OUT
            else:
                user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.status == 'failed':
            user_status = UserStatus.FAILED
        elif job.status == 'expired':
            user_status = UserStatus.CANCELLED_TIMED_OUT
        elif job.status in ('validating', 'in_progress', 'finalizing',
                            'cancelling'):
            if self._should_cancel_for_timeout(
                    datetime.fromtimestamp(job.created_at, tz=timezone.utc)):
                user_status = UserStatus.CANCELLED_TIMED_OUT
                logger.warning("Job %s has timed out. Cancelling...", job.id)
                self.cancel_job(job.id)
            else:
                user_status = UserStatus.IN_PROGRESS
        else:
            raise ValueError(f"Unexpected job status: {job.status}")

        total_tokens = None
        if user_status == UserStatus.SUCCEEDED:
            total_tokens = self._calculate_total_tokens(job)

        return JobReport(provider="openai",
                         job_id=job.id,
                         user_assigned_status=user_status,
                         latency_seconds=latency,
                         total_tokens=total_tokens,
                         service_reported_details=status)

    def cancel_job(self, job_id):
        logger.info("Attempting to cancel job: %s", job_id)
        cancelled_job = self.client.batches.cancel(job_id)
        logger.info("Job %s is now %s", cancelled_job.id, cancelled_job.status)

    def get_job_details_from_provider(self, job_id):
        return self.client.batches.retrieve(batch_id=job_id)

    def get_provider_name(self):
        return "openai"

    def _calculate_total_tokens(self, job):
        """Downloads the result file and calculates the total tokens used."""
        total_tokens = 0
        if job.status == 'completed' and job.output_file_id:
            try:
                logger.info("Calculating total tokens for job %s", job.id)
                result_file_id = job.output_file_id
                file_content = self.client.files.content(result_file_id).read()
                
                content_str = file_content.decode('utf-8').strip()
                
                for line in content_str.splitlines():
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        if 'response' in result and 'body' in result['response'] and 'usage' in result['response']['body']:
                            total_tokens += result['response']['body']['usage'].get('total_tokens', 0)
                    except json.JSONDecodeError:
                        logger.warning("Could not decode JSON line: %s", line)
                
                logger.info("Total tokens calculated for job %s: %d", job.id, total_tokens)
                return total_tokens
            except Exception as e:
                logger.error("Error calculating tokens for job %s: %s", job.id, e)
        return None

    def download_results(self, job, output_file):
        """Downloads the results of a completed batch job.

        Args:
            job: The provider-specific job object.
            output_file: The path to the output file to save the results to.
        """
        if job.status == 'completed':
            if job.output_file_id:
                result_file_id = job.output_file_id
                logger.info("Results are in file: %s", result_file_id)
                logger.info("Downloading result file content...")
                file_content = self.client.files.content(result_file_id)
                with open(output_file, "wb") as f:
                    f.write(file_content.read())
                logger.info("Successfully downloaded results to %s",
                            output_file)
            else:
                logger.info("No results file found for job %s", job.id)
        else:
            logger.warning("Job %s did not succeed. Final state: %s", job.id,
                           job.status)
