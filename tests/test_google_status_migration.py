import unittest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.google import GoogleProvider
from data_models import JobReport, UserStatus

class MockGoogleJob:
    def __init__(self, name, state, create_time, end_time):
        self.name = name
        self.state = MagicMock()
        self.state.name = state
        self.create_time = create_time
        self.end_time = end_time
        self.model = "models/gemini-2.5-flash-lite"

class TestGoogleStatusMigration(unittest.TestCase):
    
    def setUp(self):
        if os.path.exists("test_state_file.jsonl"):
            os.remove("test_state_file.jsonl")
        if os.path.exists("test_output.jsonl"):
            os.remove("test_output.jsonl")

        self.provider = GoogleProvider(api_key="test")
        self.provider.cancel_job = MagicMock()

        now = datetime.now(timezone.utc)
        self.jobs_to_create = {
            "succeeded": {"create_time": now - timedelta(hours=1)},
            "failed": {"create_time": now - timedelta(hours=2)},
            "cancelled_timed_out_by_service": {"create_time": now - timedelta(hours=25)},
            "cancelled_timed_out_by_us": {"create_time": now - timedelta(hours=25)},
            "cancelled_on_demand": {"create_time": now - timedelta(hours=1)},
        }

        with open("test_state_file.jsonl", "w") as f:
            for job_id, details in self.jobs_to_create.items():
                f.write('{"provider": "google", "job_id": "' + job_id + '", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "' + job_id + '", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "' + details["create_time"].isoformat() + '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')

    def test_status_migration(self):
        def mock_get_job_details(job_id):
            job_details = self.jobs_to_create[job_id]
            terminal_states = {
                "succeeded": "JOB_STATE_SUCCEEDED",
                "failed": "JOB_STATE_FAILED",
                "cancelled_timed_out_by_service": "JOB_STATE_EXPIRED",
                "cancelled_timed_out_by_us": "JOB_STATE_PENDING",
                "cancelled_on_demand": "JOB_STATE_CANCELLED",
            }
            state = terminal_states[job_id]
            
            return MockGoogleJob(
                name=f"batches/{job_id}",
                state=state,
                create_time=job_details["create_time"],
                end_time=job_details["create_time"] + timedelta(seconds=1) if state != "JOB_STATE_PENDING" else None
            )

        self.provider.get_job_details_from_provider = MagicMock(side_effect=mock_get_job_details)
        
        self.provider.check_jobs_from_file("test_state_file.jsonl", "test_output.jsonl")

        with open("test_output.jsonl", "r") as f:
            reports = {JobReport.from_json(line).job_id: JobReport.from_json(line) for line in f}

        self.assertEqual(len(reports), len(self.jobs_to_create))
        self.assertEqual(reports["batches/succeeded"].user_assigned_status, UserStatus.SUCCEEDED)
        self.assertEqual(reports["batches/failed"].user_assigned_status, UserStatus.FAILED)
        self.assertEqual(reports["batches/cancelled_timed_out_by_service"].user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
        self.assertEqual(reports["batches/cancelled_timed_out_by_us"].user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
        self.assertEqual(reports["batches/cancelled_on_demand"].user_assigned_status, UserStatus.CANCELLED_ON_DEMAND)

        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")

if __name__ == '__main__':
    unittest.main()
