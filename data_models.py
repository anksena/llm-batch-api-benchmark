from dataclasses import dataclass, asdict
import json
from typing import Optional
from enum import Enum

class UserStatus(Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED_TIMED_OUT = "CANCELLED_TIMED_OUT"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED_ON_DEMAND = "CANCELLED_ON_DEMAND"
    UNKNOWN = "UNKNOWN"

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
class JobReport:
    """A standardized dataclass for the final report of a single job."""
    provider: str
    job_id: str
    user_assigned_status: UserStatus
    details: JobStatus

    def to_json(self):
        # Custom JSON encoder to handle the Enum
        return json.dumps(asdict(self), indent=2, default=lambda o: o.value)
