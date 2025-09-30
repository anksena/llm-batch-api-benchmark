from abc import ABC, abstractmethod

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
    def check_and_process_jobs(self):
        """Checks the status of recent jobs and processes them."""
        pass

    @abstractmethod
    def list_models(self):
        """Lists available models."""
        pass

    @abstractmethod
    def cancel_job(self, job_id):
        """Cancels a batch job."""
        pass
