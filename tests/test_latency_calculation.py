import unittest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

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
from data_models import JobReport, UserStatus

class TestLatencyCalculation(unittest.TestCase):

    def setUp(self):
        if os.path.exists("test_output.jsonl"):
            os.remove("test_output.jsonl")
        if os.path.exists("test_state_file.jsonl"):
            os.remove("test_state_file.jsonl")

    def test_latency_calculation(self):
        provider = GoogleProvider(api_key="test")

        now = datetime.now(timezone.utc)
        succeeded_create_time_1 = now - timedelta(hours=2)
        succeeded_create_time_2 = now - timedelta(hours=3)
        in_progress_create_time = now - timedelta(hours=1)
        expired_create_time = now - timedelta(hours=25)

        # Create a mock state file
        with open("test_state_file.jsonl", "w") as f:
            f.write('{"provider": "google", "job_id": "job-123", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-123", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "' + succeeded_create_time_1.isoformat() + '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-456", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-456", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "' + succeeded_create_time_2.isoformat() + '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-789", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-789", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "' + expired_create_time.isoformat() + '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')
            f.write('{"provider": "google", "job_id": "job-abc", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "job-abc", "model": "models/gemini-2.5-flash-lite", "service_job_status": "JOB_STATE_PENDING", "created_at": "' + in_progress_create_time.isoformat() + '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n')

        # Mock the get_job_details_from_provider method
        def mock_get_job_details_from_provider(job_id):
            if job_id == "job-123":
                return MockGoogleJob(
                    name=f"batches/{job_id}",
                    state="JOB_STATE_SUCCEEDED",
                    create_time=succeeded_create_time_1,
                    end_time=succeeded_create_time_1 + timedelta(seconds=123.45)
                )
            elif job_id == "job-456":
                return MockGoogleJob(
                    name=f"batches/{job_id}",
                    state="JOB_STATE_SUCCEEDED",
                    create_time=succeeded_create_time_2,
                    end_time=succeeded_create_time_2 + timedelta(seconds=306.79)
                )
            elif job_id == "job-789":
                return MockGoogleJob(
                    name=f"batches/{job_id}",
                    state="JOB_STATE_PENDING",
                    create_time=expired_create_time,
                    end_time=None
                )
            elif job_id == "job-abc":
                return MockGoogleJob(
                    name=f"batches/{job_id}",
                    state="JOB_STATE_PENDING",
                    create_time=in_progress_create_time,
                    end_time=None
                )
            return None

        provider.get_job_details_from_provider = MagicMock(side_effect=mock_get_job_details_from_provider)
        provider.cancel_job = MagicMock()

        # Run the check_jobs_from_file method
        provider.check_jobs_from_file("test_state_file.jsonl", "test_output.jsonl")

        # Verify the results
        with open("test_output.jsonl", "r") as f:
            reports = {}
            for line in f:
                report = JobReport.from_json(line)
                reports[report.job_id] = report
            
            self.assertEqual(len(reports), 4)
            self.assertAlmostEqual(reports["batches/job-123"].latency_seconds, 123.45)
            self.assertAlmostEqual(reports["batches/job-456"].latency_seconds, 306.79)
            self.assertEqual(reports["batches/job-789"].user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
            self.assertEqual(reports["batches/job-abc"].user_assigned_status, UserStatus.IN_PROGRESS)

        # Clean up the test files
        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")

if __name__ == '__main__':
    unittest.main()
