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
            reports = {}
            for line in f:
                report = JobReport.from_json(line)
                reports[report.job_id] = report
            
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports["job-123"].user_assigned_status, UserStatus.SUCCEEDED)
            self.assertEqual(reports["job-456"].user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)

        # Clean up the test files
        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")

    def test_ignore_completed_jobs(self):
        provider = GoogleProvider(api_key="test")

        # Create a mock state file
        with open("test_state_file.jsonl", "w") as f:
            f.write('{"provider": "google", "job_id": "job-123", "user_assigned_status": "SUCCEEDED", "latency_seconds": 123.45, "service_reported_details": {"job_id": "job-123", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_SUCCEEDED", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": "2025-10-12T06:02:03.450000+00:00", "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-456", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-456", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-789", "user_assigned_status": "FAILED", "latency_seconds": null, "service_reported_details": {"job_id": "job-789", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_FAILED", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": "2025-10-12T06:00:00+00:00", "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-abc", "user_assigned_status": "CANCELLED_TIMED_OUT", "latency_seconds": null, "service_reported_details": {"job_id": "job-abc", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_CANCELLED", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": "2025-10-12T06:00:00+00:00", "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-def", "user_assigned_status": "CANCELLED_ON_DEMAND", "latency_seconds": null, "service_reported_details": {"job_id": "job-def", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_CANCELLED", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": "2025-10-12T06:00:00+00:00", "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-ghi", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-ghi", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "2025-10-12T06:00:00+00:00", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')

        # Mock the get_job_details_from_provider method
        def mock_get_job_details(job_id):
            if job_id == "job-456":
                return MockGoogleJob(
                    name=job_id,
                    state="JOB_STATE_SUCCEEDED",
                    create_time=datetime.now(timezone.utc) - timedelta(hours=1),
                    end_time=datetime.now(timezone.utc)
                )
            elif job_id == "job-ghi":
                return MockGoogleJob(
                    name=job_id,
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
        self.assertEqual(provider.get_job_details_from_provider.call_count, 2)
        provider.get_job_details_from_provider.assert_any_call("job-456")
        provider.get_job_details_from_provider.assert_any_call("job-ghi")
        with open("test_output.jsonl", "r") as f:
            reports = {}
            for line in f:
                report = JobReport.from_json(line)
                reports[report.job_id] = report
            
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports["job-456"].user_assigned_status, UserStatus.SUCCEEDED)
            self.assertEqual(reports["job-ghi"].user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)

        # Clean up the test files
        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")

from absl.testing import absltest

if __name__ == '__main__':
    absltest.main()
