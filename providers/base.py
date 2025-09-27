from abc import ABC, abstractmethod

class BatchProvider(ABC):
    """Abstract base class for a batch processing provider."""

    def __init__(self, api_key):
        self.client = self._initialize_client(api_key)

    @abstractmethod
    def _initialize_client(self, api_key):
        """Initializes the provider-specific API client."""
        pass

    @abstractmethod
    def create_job(self, requests):
        """Creates and monitors a batch job."""
        pass

    @abstractmethod
    def list_jobs(self):
        """Lists recent batch jobs."""
        pass

    @abstractmethod
    def cancel_job(self, job_id):
        """Cancels a batch job."""
        pass

    @abstractmethod
    def list_models(self):
        """Lists available models."""
        pass
