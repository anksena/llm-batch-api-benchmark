import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from logger import get_logger
from data_models import JobReport

logger = get_logger(__name__)

class BatchProvider(ABC):
    """Abstract base class for a batch processing provider."""

    PROMPT = "In one sentence, what is the main function of a CPU?"
    MAX_TOKENS = 1024

    def __init__(self, api_key):
        self.client = self._initialize_client(api_key)

    def create_jobs(self, num_jobs):
        """Creates a batch job with n requests."""
        job_ids = []
        for i in range(num_jobs):
            job_id = self._create_single_job(i, num_jobs)
            job_ids.append(job_id)
        return job_ids

    def check_jobs_from_file(self, state_file, output_file):
        """Processes a state file of jobs and checks their status."""
        with open(state_file, "r") as f_in, open(output_file, "a") as f_out:
            for line in f_in:
                job_report = JobReport.from_json(line)
                if job_report.job_id:
                    report = self.get_job_report(job_report.job_id)
                    if report:
                        report_json = report.to_json()
                        print(report_json)
                        f_out.write(report_json + "\n")

    def check_recent_jobs(self, output_file, hours_ago):
        """Checks all recent jobs and appends reports to the output file."""
        logger.info(f"Checking recent jobs for provider and appending to {output_file}...")

        with open(output_file, "a") as f:
            for job in self._get_job_list(hours_ago):
                report = self._create_report_from_provider_job(job)
                if report:
                    report_json = report.to_json()
                    print(report_json)
                    f.write(report_json + "\n")

    @abstractmethod
    def _get_job_create_time(self, job):
        """Returns the creation time of a job."""
        pass

    @abstractmethod
    def _get_job_list(self):
        """Returns a list of recent job objects."""
        pass

    @abstractmethod
    def list_models(self):
        """Lists available models."""
        pass

    @abstractmethod
    def cancel_job(self, job_id):
        """Cancels a batch job."""
        pass

    @abstractmethod
    def get_job_report(self, job_id):
        """Gets the report for a single batch job."""
        pass

    def _should_skip_job(self, job_create_time):
        """Returns True if the job is older than 36 hours."""
        thirty_six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=36)
        return job_create_time < thirty_six_hours_ago

    def _should_cancel_for_timeout(self, job_create_time):
        """Returns True if the job has been running for more than 24 hours."""
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        return job_create_time < one_day_ago
