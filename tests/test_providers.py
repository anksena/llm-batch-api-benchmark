import unittest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.google import GoogleProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from data_models import UserStatus

class TestGoogleProvider(unittest.TestCase):

    def test_process_job_succeeded(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.name = "job-123"
        mock_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_job.create_time = datetime.now(timezone.utc)
        mock_job.end_time = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.name = "job-123"
        mock_job.state.name = "JOB_STATE_FAILED"
        mock_job.create_time = datetime.now(timezone.utc)
        mock_job.end_time = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)

    def test_process_job_timed_out(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.name = "job-123"
        mock_job.state.name = "JOB_STATE_PENDING"
        mock_job.create_time = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_job.end_time = None
        provider.cancel_job = MagicMock()

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.name = "job-123"
        mock_job.state.name = "JOB_STATE_CANCELLED"
        mock_job.create_time = datetime.now(timezone.utc)
        mock_job.end_time = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_ON_DEMAND)

class TestOpenAIProvider(unittest.TestCase):

    def test_process_job_succeeded(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.status = "completed"
        mock_job.created_at = datetime.now(timezone.utc).timestamp()
        mock_job.completed_at = datetime.now(timezone.utc).timestamp()

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.status = "failed"
        mock_job.created_at = datetime.now(timezone.utc).timestamp()
        mock_job.completed_at = None

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)

    def test_process_job_timed_out(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.status = "in_progress"
        mock_job.created_at = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
        mock_job.completed_at = None
        provider.cancel_job = MagicMock()

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.status = "cancelled"
        mock_job.created_at = datetime.now(timezone.utc).timestamp()
        mock_job.completed_at = None

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_ON_DEMAND)

class TestAnthropicProvider(unittest.TestCase):

    def test_process_job_succeeded(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.processing_status = "completed"
        mock_job.created_at = datetime.now(timezone.utc)
        mock_job.ended_at = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_succeeded_when_ended(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.processing_status = "ended"
        mock_job.request_counts.succeeded = 1
        mock_job.created_at = datetime.now(timezone.utc)
        mock_job.ended_at = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.processing_status = "failed"
        mock_job.created_at = datetime.now(timezone.utc)
        mock_job.ended_at = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)

    def test_process_job_timed_out(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.processing_status = "in_progress"
        mock_job.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_job.ended_at = None
        provider.cancel_job = MagicMock()

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.processing_status = "cancelled"
        mock_job.created_at = datetime.now(timezone.utc)
        mock_job.ended_at = datetime.now(timezone.utc)

        report = provider._process_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.CANCELLED_ON_DEMAND)

if __name__ == '__main__':
    unittest.main()
