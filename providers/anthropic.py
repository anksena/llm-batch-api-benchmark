"""Batch processing provider for Anthropic."""
import json
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from .base import BatchProvider
from logger import get_logger
from data_models import ServiceReportedJobDetails, JobReport, UserStatus
from enum import Enum


class AnthropicJobStatus(Enum):
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


logger = get_logger(__name__)


class AnthropicProvider(BatchProvider):
    """Batch processing provider for Anthropic."""

    MODEL_NAME = "claude-3-haiku-20240307"

    @property
    def _job_status_enum(self):
        return AnthropicJobStatus

    @property
    def _job_status_attribute(self):
        return "processing_status"

    def _initialize_client(self, api_key):
        return Anthropic(api_key=api_key)

    def _create_single_batch_job(self, job_index: int, total_jobs: int,
                               prompts: list[str]) -> str:
        anthropic_requests = []
        for i, prompt in enumerate(prompts):
            anthropic_requests.append({
                "custom_id": f"request-{i}",
                "params": {
                    "model": self.MODEL_NAME,
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "max_tokens": self.MAX_TOKENS,
                }
            })

        job = self.client.beta.messages.batches.create(
            requests=anthropic_requests)
        logger.info("Created batch job %d/%d: %s", job_index + 1, total_jobs,
                    job.id)
        return job.id

    def _get_job_list(self, hours_ago):
        all_jobs = []
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        for page in self.client.beta.messages.batches.list(
                limit=10).iter_pages():
            for job in page.data:
                if job.created_at < time_threshold:
                    return all_jobs
                all_jobs.append(job)
        return all_jobs

    def _get_job_create_time(self, job):
        return job.created_at

    def _create_report_from_provider_job(self, job):
        latency = None
        total_requests = job.request_counts.succeeded + job.request_counts.errored + job.request_counts.expired + job.request_counts.canceled
        if job.processing_status == 'ended' and job.request_counts.succeeded == total_requests and job.ended_at:
            latency = round((job.ended_at - job.created_at).total_seconds(), 2)

        status = ServiceReportedJobDetails(
            job_id=job.id,
            model=self.MODEL_NAME,
            service_job_status=job.processing_status,
            created_at=job.created_at.isoformat(),
            ended_at=job.ended_at.isoformat() if job.ended_at else None,
            total_requests=job.request_counts.succeeded +
            job.request_counts.errored + job.request_counts.expired +
            job.request_counts.canceled,
            completed_requests=job.request_counts.succeeded,
            failed_requests=job.request_counts.errored)

        if job.processing_status == 'ended':
            return self._handle_ended_job(job, status, latency)
        elif job.processing_status == 'in_progress':
            return self._handle_in_progress_job(job, status, latency)
        else:
            raise ValueError(f"Unexpected job status: {job.processing_status}")

    def _handle_ended_job(self, job, status, latency):
        total_requests = job.request_counts.succeeded + job.request_counts.errored + job.request_counts.expired + job.request_counts.canceled
        if job.request_counts.errored > 0:
            user_status = UserStatus.FAILED
        elif job.request_counts.canceled > 0:
            user_status = UserStatus.CANCELLED_ON_DEMAND
        elif job.request_counts.expired > 0:
            user_status = UserStatus.CANCELLED_TIMED_OUT
        elif job.request_counts.succeeded == total_requests:
            user_status = UserStatus.SUCCEEDED
        else:
            raise ValueError(f"Unexpected job status: {job.processing_status}")
        
        total_tokens = None
        if user_status == UserStatus.SUCCEEDED:
            total_tokens = self._calculate_total_tokens(job)

        return JobReport(provider="anthropic",
                         job_id=job.id,
                         user_assigned_status=user_status,
                         latency_seconds=latency,
                         total_tokens=total_tokens,
                         service_reported_details=status)

    def _handle_in_progress_job(self, job, status, latency):
        if self._should_cancel_for_timeout(job.created_at):
            logger.warning("Job %s has timed out. Cancelling...", job.id)
            self.cancel_job(job.id)
            user_status = UserStatus.CANCELLED_TIMED_OUT
        else:
            user_status = UserStatus.IN_PROGRESS
        return JobReport(provider="anthropic",
                         job_id=job.id,
                         user_assigned_status=user_status,
                         latency_seconds=latency,
                         total_tokens=None,
                         service_reported_details=status)

    def cancel_job(self, job_id):
        logger.info("Attempting to cancel job: %s", job_id)
        cancelled_job = self.client.beta.messages.batches.cancel(job_id)
        logger.info("Job %s is now %s", cancelled_job.id,
                    cancelled_job.processing_status)

    def get_job_details_from_provider(self, job_id):
        return self.client.beta.messages.batches.retrieve(job_id)

    def get_provider_name(self):
        return "anthropic"

    def _calculate_total_tokens(self, job):
        """Downloads the result file and calculates the total tokens used."""
        total_tokens = 0
        if job.processing_status == 'ended' and job.results_url:
            try:
                logger.info("Calculating total tokens for job %s", job.id)
                response = self.client.get(job.results_url, cast_to=bytes)
                content_str = response.decode('utf-8').strip()
                
                for line in content_str.splitlines():
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        if 'result' in result and 'message' in result['result'] and 'usage' in result['result']['message']:
                            # Anthropic uses input_tokens and output_tokens
                            total_tokens += result['result']['message']['usage'].get('input_tokens', 0)
                            total_tokens += result['result']['message']['usage'].get('output_tokens', 0)
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
        if job.processing_status == 'ended':
            if job.results_url:
                logger.info("Results are at URL: %s", job.results_url)
                logger.info("Downloading result file content...")
                response = self.client.get(job.results_url, cast_to=bytes)
                with open(output_file, "wb") as f:
                    f.write(response)
                logger.info("Successfully downloaded results to %s",
                            output_file)
            else:
                logger.info("No results file found for job %s", job.id)
        else:
            logger.warning("Job %s did not succeed. Final state: %s", job.id,
                           job.processing_status)
