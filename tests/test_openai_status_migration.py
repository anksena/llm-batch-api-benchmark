import unittest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.openai import OpenAIProvider
from data_models import JobReport, UserStatus


class MockOpenAIJob:

    def __init__(self, id, status, created_at):
        self.id = id
        self.status = status
        self.created_at = int(created_at.timestamp())
        self.completed_at = int(
            (created_at + timedelta(seconds=1)
            ).timestamp()) if status == "completed" else None
        self.model = "gpt-4o-mini"
        self.request_counts = MagicMock()
        self.request_counts.total = 1
        self.request_counts.completed = 1
        self.request_counts.failed = 0


class TestOpenAIStatusMigration(unittest.TestCase):

    def setUp(self):
        if os.path.exists("test_state_file.jsonl"):
            os.remove("test_state_file.jsonl")
        if os.path.exists("test_output.jsonl"):
            os.remove("test_output.jsonl")

        self.provider = OpenAIProvider(api_key="test")
        self.provider.cancel_job = MagicMock()

        now = datetime.now(timezone.utc)
        self.jobs_to_create = {
            "succeeded": {
                "create_time": now - timedelta(hours=1)
            },
            "failed": {
                "create_time": now - timedelta(hours=2)
            },
            "cancelled_timed_out_by_service": {
                "create_time": now - timedelta(hours=25)
            },
            "cancelled_timed_out_by_us": {
                "create_time": now - timedelta(hours=25)
            },
            "cancelled_on_demand": {
                "create_time": now - timedelta(hours=1)
            },
        }

        with open("test_state_file.jsonl", "w") as f:
            for job_id, details in self.jobs_to_create.items():
                f.write(
                    '{"provider": "openai", "job_id": "' + job_id +
                    '", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "'
                    + job_id +
                    '", "model": "gpt-4o-mini", "service_job_status": "in_progress", "created_at": "'
                    + details["create_time"].isoformat() +
                    '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n'
                )

    def test_status_migration(self):

        def mock_get_job_details(job_id):
            job_details = self.jobs_to_create[job_id]
            terminal_states = {
                "succeeded": "completed",
                "failed": "failed",
                "cancelled_timed_out_by_service": "expired",
                "cancelled_timed_out_by_us": "in_progress",
                "cancelled_on_demand": "cancelled",
            }
            state = terminal_states[job_id]

            return MockOpenAIJob(id=job_id,
                                 status=state,
                                 created_at=job_details["create_time"])

        self.provider.get_job_details_from_provider = MagicMock(
            side_effect=mock_get_job_details)

        self.provider.check_jobs_from_file("test_state_file.jsonl",
                                           "test_output.jsonl")

        with open("test_output.jsonl", "r") as f:
            reports = {
                JobReport.from_json(line).job_id: JobReport.from_json(line)
                for line in f
            }

        self.assertEqual(len(reports), len(self.jobs_to_create))
        self.assertEqual(reports["succeeded"].user_assigned_status,
                         UserStatus.SUCCEEDED)
        self.assertEqual(reports["failed"].user_assigned_status,
                         UserStatus.FAILED)
        self.assertEqual(
            reports["cancelled_timed_out_by_service"].user_assigned_status,
            UserStatus.CANCELLED_TIMED_OUT)
        self.assertEqual(
            reports["cancelled_timed_out_by_us"].user_assigned_status,
            UserStatus.CANCELLED_TIMED_OUT)
        self.assertEqual(reports["cancelled_on_demand"].user_assigned_status,
                         UserStatus.CANCELLED_ON_DEMAND)

        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")


if __name__ == '__main__':
    unittest.main()
