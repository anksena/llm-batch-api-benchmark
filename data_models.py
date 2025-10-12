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

    @classmethod
    def is_terminal(cls, status):
        return status in [cls.SUCCEEDED, cls.FAILED, cls.CANCELLED_TIMED_OUT, cls.CANCELLED_ON_DEMAND]

@dataclass
class ServiceReportedJobDetails:
    """A standardized dataclass for reporting the status of a batch job."""
    job_id: str
    model: str
    service_job_status: str
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
    latency_seconds: Optional[float]
    service_reported_details: ServiceReportedJobDetails

    def to_json(self):
        # Custom JSON encoder to handle the Enum
        def default_serializer(o):
            if isinstance(o, UserStatus):
                return o.value
            # Handle non-serializable objects by converting them to strings
            try:
                json.dumps(o)
                return o
            except TypeError:
                return str(o)
        return json.dumps(asdict(self), default=default_serializer)

    @classmethod
    def from_json(cls, json_string):
        data = json.loads(json_string)
        
        # Handle UserStatus enum
        user_status_val = data.get('user_assigned_status')
        if user_status_val:
            data['user_assigned_status'] = UserStatus(user_status_val)
            
        # Handle nested ServiceReportedJobDetails dataclass
        status_details_val = data.get('service_reported_details')
        if status_details_val:
            data['service_reported_details'] = ServiceReportedJobDetails(**status_details_val)
            
        return cls(**data)
