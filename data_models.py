from dataclasses import dataclass, asdict
import json
from typing import Optional

@dataclass
class JobStatus:
    """A standardized dataclass for reporting the status of a batch job."""
    job_id: str
    status: str
    created_at: str
    ended_at: Optional[str] = None
    total_requests: Optional[int] = None
    completed_requests: Optional[int] = None
    failed_requests: Optional[int] = None

@dataclass
class BatchJobResult:
    """A standardized dataclass for a single request's result."""
    custom_id: str
    prompt: str
    response: str
    error: str = None
    finish_reason: str = None

@dataclass
class PerformanceReport:
    """A standardized dataclass for the overall performance report."""
    provider: str
    job_id: str
    latency_seconds: float
    final_status: str
    num_requests: int
    results: list[BatchJobResult]

    def to_json(self):
        return json.dumps(asdict(self), indent=2)
