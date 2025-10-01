from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

class BatchProvider(ABC):
    """Abstract base class for a batch processing provider."""

    PROMPT = "In one sentence, what is the main function of a CPU?"

    def __init__(self, api_key):
        self.client = self._initialize_client(api_key)

    @abstractmethod
    def _initialize_client(self, api_key):
        """Initializes the provider-specific API client."""
        pass

    @abstractmethod
    def create_jobs(self, num_jobs):
        """Creates a batch job with n requests."""
        pass

    @abstractmethod
    def process_jobs(self, output_file):
        """Processes recent jobs and appends reports to the output file."""
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
