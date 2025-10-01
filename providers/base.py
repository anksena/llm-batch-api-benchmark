from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from logger import get_logger

logger = get_logger(__name__)

class BatchProvider(ABC):
    """Abstract base class for a batch processing provider."""

    PROMPT = "In one sentence, what is the main function of a CPU?"
    MAX_TOKENS = 1024

    def __init__(self, api_key):
        self.client = self._initialize_client(api_key)

    @abstractmethod
    def create_jobs(self, num_jobs):
        """Creates a batch job with n requests."""
        pass

    def process_jobs(self, output_file):
        """Processes recent jobs and appends reports to the output file."""
        logger.info(f"Processing recent jobs for provider and appending to {output_file}...")

        with open(output_file, "a") as f:
            for job in self._get_job_list():
                create_time = self._get_job_create_time(job)
                if self._should_skip_job(create_time):
                    continue
                
                report = self._process_job(job)
                if report:
                    f.write(report.to_json() + "\n")

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

    def _should_skip_job(self, job_create_time):
        """Returns True if the job is older than 36 hours."""
        thirty_six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=36)
        return job_create_time < thirty_six_hours_ago

    def _should_cancel_for_timeout(self, job_create_time):
        """Returns True if the job has been running for more than 24 hours."""
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        return job_create_time < one_day_ago
