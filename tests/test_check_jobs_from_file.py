import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

class MockGoogleJob:
    def __init__(self, name, state, create_time, end_time):
        self.name = name
        self.state = MagicMock()
        self.state.name = state
        self.create_time = create_time
        self.end_time = end_time
        self.model = "models/gemini-2.5-flash-lite"

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.google import GoogleProvider
from data_models import JobReport, ServiceReportedJobDetails, UserStatus

class TestCheckJobsFromFile(unittest.TestCase):

    def test_check_jobs_from_file(self):
        provider = GoogleProvider(api_key="test")

        # Create a mock state file
        with open("test_state_file.jsonl", "w") as f:
            f.write('{"provider": "google", "job_id": "job-123", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-123", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-456", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-456", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "2025-10-10T06:00:00+00:00", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')

        # Mock the get_job_details_from_provider method
        def mock_get_job_details(job_id):
            if job_id == "job-123":
                return MockGoogleJob(
                    name="job-123",
                    state="JOB_STATE_SUCCEEDED",
                    create_time=datetime.now(timezone.utc) - timedelta(hours=1),
                    end_time=datetime.now(timezone.utc)
                )
            elif job_id == "job-456":
                return MockGoogleJob(
                    name="job-456",
                    state="JOB_STATE_PENDING",
                    create_time=datetime.now(timezone.utc) - timedelta(hours=25),
                    end_time=None
                )
            return None

        provider.get_job_details_from_provider = MagicMock(side_effect=mock_get_job_details)
        provider.cancel_job = MagicMock()

        # Run the check_jobs_from_file method
        provider.check_jobs_from_file("test_state_file.jsonl", "test_output.jsonl")

        # Verify the results
        with open("test_output.jsonl", "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            report1 = JobReport.from_json(lines[0])
            report2 = JobReport.from_json(lines[1])
            self.assertEqual(report1.user_assigned_status, UserStatus.SUCCEEDED)
            self.assertEqual(report2.user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)

        # Clean up the test files
        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")

from absl.testing import absltest

if __name__ == '__main__':
    absltest.main()
