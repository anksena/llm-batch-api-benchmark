import unittest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.anthropic import AnthropicProvider
from data_models import JobReport, UserStatus


class MockAnthropicJob:

    def __init__(self, id, status, create_time):
        self.id = id
        self.processing_status = status
        self.created_at = create_time
        self.ended_at = create_time + timedelta(
            seconds=1) if status == "ended" else None
        self.request_counts = MagicMock()
        if id == "failed":
            self.request_counts.succeeded = 0
            self.request_counts.errored = 1
        else:
            self.request_counts.succeeded = 1
            self.request_counts.errored = 0
        self.request_counts.expired = 0
        self.request_counts.canceled = 0


class TestAnthropicStatusMigration(unittest.TestCase):

    def setUp(self):
        if os.path.exists("test_state_file.jsonl"):
            os.remove("test_state_file.jsonl")
        if os.path.exists("test_output.jsonl"):
            os.remove("test_output.jsonl")

        self.provider = AnthropicProvider(api_key="test")
        self.provider.cancel_job = MagicMock()

        now = datetime.now(timezone.utc)
        self.jobs_to_create = {
            "succeeded": {
                "create_time": now - timedelta(hours=1)
            },
            "failed": {
                "create_time": now - timedelta(hours=2)
            },
        }

        with open("test_state_file.jsonl", "w") as f:
            for job_id, details in self.jobs_to_create.items():
                f.write(
                    '{"provider": "anthropic", "job_id": "' + job_id +
                    '", "user_assigned_status": "IN_PROGRESS", "latency_seconds": null, "service_reported_details": {"job_id": "'
                    + job_id +
                    '", "model": "claude-3-haiku-20240307", "service_job_status": "in_progress", "created_at": "'
                    + details["create_time"].isoformat() +
                    '", "ended_at": null, "total_requests": null, "completed_requests": null, "failed_requests": null}}\n'
                )

    def test_status_migration(self):

        def mock_get_job_details(job_id):
            job_details = self.jobs_to_create[job_id]
            terminal_states = {
                "succeeded": "ended",
                "failed": "ended",
            }
            state = terminal_states[job_id]

            return MockAnthropicJob(
                id=job_id,
                status=state,
                create_time=job_details["create_time"],
            )

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

        os.remove("test_state_file.jsonl")
        os.remove("test_output.jsonl")


if __name__ == '__main__':
    unittest.main()
