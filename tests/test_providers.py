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


class MockOpenAIJob:

    def __init__(self, id, status, created_at, completed_at):
        self.id = id
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.request_counts = MagicMock()
        self.model = "gpt-4o-mini"


class MockAnthropicJob:

    def __init__(self, id, processing_status, created_at, ended_at):
        self.id = id
        self.processing_status = processing_status
        self.created_at = created_at
        self.ended_at = ended_at
        self.request_counts = MagicMock()
        self.request_counts.succeeded = 0
        self.request_counts.errored = 0
        self.request_counts.expired = 0
        self.request_counts.canceled = 0


# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.google import GoogleProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from data_models import UserStatus, ServiceReportedJobDetails


class TestGoogleProvider(unittest.TestCase):

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.remove')
    def test_create_single_batch_job_with_multiple_requests(
            self, mock_remove, mock_open):
        # Arrange
        provider = GoogleProvider(api_key="test")
        provider.client = MagicMock()
        prompts = ["prompt1", "prompt2"]

        # Act
        provider._create_single_batch_job(0, 1, prompts)

        # Assert
        mock_open.assert_called_once_with("gemini-batch-request-0.jsonl",
                                          "w",
                                          encoding="utf-8")
        self.assertEqual(mock_open().write.call_count, 2)
        provider.client.files.upload.assert_called_once()
        provider.client.batches.create.assert_called_once()

    def test_process_job_succeeded(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MockGoogleJob(name="job-123",
                                 state="JOB_STATE_SUCCEEDED",
                                 create_time=datetime.now(timezone.utc),
                                 end_time=datetime.now(timezone.utc))

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MockGoogleJob(name="job-123",
                                 state="JOB_STATE_FAILED",
                                 create_time=datetime.now(timezone.utc),
                                 end_time=datetime.now(timezone.utc))

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)
        self.assertIsNone(report.latency_seconds)

    def test_process_job_timed_out(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MockGoogleJob(name="job-123",
                                 state="JOB_STATE_PENDING",
                                 create_time=datetime.now(timezone.utc) -
                                 timedelta(hours=25),
                                 end_time=None)
        provider.cancel_job = MagicMock()

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MockGoogleJob(name="job-123",
                                 state="JOB_STATE_CANCELLED",
                                 create_time=datetime.now(timezone.utc),
                                 end_time=datetime.now(timezone.utc))

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_ON_DEMAND)

    def test_unknown_status_raises_error(self):
        provider = GoogleProvider(api_key="test")
        mock_job = MockGoogleJob(name="job-123",
                                 state="UNKNOWN_STATE",
                                 create_time=datetime.now(timezone.utc),
                                 end_time=datetime.now(timezone.utc))

        with self.assertRaises(ValueError) as context:
            provider._validate_and_create_report(mock_job)

        self.assertTrue("Unknown job status for GOOGLE: UNKNOWN_STATE" in str(
            context.exception))


class TestOpenAIProvider(unittest.TestCase):

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.remove')
    def test_create_single_batch_job_with_multiple_requests(
            self, mock_remove, mock_open):
        # Arrange
        provider = OpenAIProvider(api_key="test")
        provider.client = MagicMock()
        prompts = ["prompt1", "prompt2"]

        # Act
        provider._create_single_batch_job(0, 1, prompts)

        # Assert
        self.assertEqual(mock_open.call_count, 2)
        mock_open.assert_any_call("openai-batch-request-0.jsonl",
                                  "w",
                                  encoding="utf-8")
        mock_open.assert_any_call("openai-batch-request-0.jsonl", "rb")
        self.assertEqual(mock_open().write.call_count, 2)
        provider.client.files.create.assert_called_once()
        provider.client.batches.create.assert_called_once()

    def test_process_job_succeeded(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MockOpenAIJob(
            id="job-123",
            status="completed",
            created_at=datetime.now(timezone.utc).timestamp(),
            completed_at=datetime.now(timezone.utc).timestamp())

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MockOpenAIJob(id="job-123",
                                 status="failed",
                                 created_at=datetime.now(
                                     timezone.utc).timestamp(),
                                 completed_at=None)

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)

    def test_process_job_timed_out(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MockOpenAIJob(id="job-123",
                                 status="in_progress",
                                 created_at=(datetime.now(timezone.utc) -
                                             timedelta(hours=25)).timestamp(),
                                 completed_at=None)
        provider.cancel_job = MagicMock()

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MockOpenAIJob(id="job-123",
                                 status="cancelled",
                                 created_at=datetime.now(
                                     timezone.utc).timestamp(),
                                 completed_at=None)

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_ON_DEMAND)

    def test_unknown_status_raises_error(self):
        provider = OpenAIProvider(api_key="test")
        mock_job = MockOpenAIJob(id="job-123",
                                 status="UNKNOWN_STATE",
                                 created_at=datetime.now(
                                     timezone.utc).timestamp(),
                                 completed_at=None)

        with self.assertRaises(ValueError) as context:
            provider._validate_and_create_report(mock_job)

        self.assertTrue("Unknown job status for OPENAI: UNKNOWN_STATE" in str(
            context.exception))


class TestAnthropicProvider(unittest.TestCase):

    def test_create_single_batch_job_with_multiple_requests(self):
        # Arrange
        provider = AnthropicProvider(api_key="test")
        provider.client = MagicMock()
        prompts = ["prompt1", "prompt2"]

        # Act
        provider._create_single_batch_job(0, 1, prompts)

        # Assert
        self.assertEqual(
            len(provider.client.beta.messages.batches.create.call_args[1]
                ["requests"]), 2)
        provider.client.beta.messages.batches.create.assert_called_once()

    def test_process_job_succeeded(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MockAnthropicJob(id="job-123",
                                    processing_status="ended",
                                    created_at=datetime.now(timezone.utc),
                                    ended_at=datetime.now(timezone.utc))
        mock_job.request_counts.succeeded = 1

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.SUCCEEDED)

    def test_process_job_failed(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MockAnthropicJob(id="job-123",
                                    processing_status="ended",
                                    created_at=datetime.now(timezone.utc),
                                    ended_at=datetime.now(timezone.utc))
        mock_job.request_counts.errored = 1

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status, UserStatus.FAILED)

    def test_process_job_timed_out(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MockAnthropicJob(id="job-123",
                                    processing_status="in_progress",
                                    created_at=datetime.now(timezone.utc) -
                                    timedelta(hours=25),
                                    ended_at=None)
        provider.cancel_job = MagicMock()

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_TIMED_OUT)
        provider.cancel_job.assert_called_once_with("job-123")

    def test_process_job_canceled_on_demand(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MockAnthropicJob(id="job-123",
                                    processing_status="ended",
                                    created_at=datetime.now(timezone.utc),
                                    ended_at=datetime.now(timezone.utc))
        mock_job.request_counts.canceled = 1

        report = provider._create_report_from_provider_job(mock_job)
        self.assertEqual(report.user_assigned_status,
                         UserStatus.CANCELLED_ON_DEMAND)

    def test_unknown_status_raises_error(self):
        provider = AnthropicProvider(api_key="test")
        mock_job = MockAnthropicJob(id="job-123",
                                    processing_status="UNKNOWN_STATE",
                                    created_at=datetime.now(timezone.utc),
                                    ended_at=datetime.now(timezone.utc))

        with self.assertRaises(ValueError) as context:
            provider._validate_and_create_report(mock_job)

        self.assertTrue("Unknown job status for ANTHROPIC: UNKNOWN_STATE" in
                        str(context.exception))


from absl.testing import absltest

if __name__ == '__main__':
    absltest.main()
