import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.anthropic import AnthropicProvider
from data_models import UserStatus

class MockAnthropicJob:
    def __init__(self, id, status, created_at, ended_at, results_url=None):
        self.id = id
        self.processing_status = status
        self.created_at = created_at
        self.ended_at = ended_at
        self.results_url = results_url
        self.request_counts = MagicMock()
        self.request_counts.succeeded = 3
        self.request_counts.errored = 0
        self.request_counts.expired = 0
        self.request_counts.canceled = 0

class TestAnthropicProvider(unittest.TestCase):

    @patch('providers.anthropic.Anthropic')
    def test_calculate_total_tokens_success(self, mock_client):
        """Test that total tokens are calculated correctly for a successful job."""
        # Arrange
        provider = AnthropicProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockAnthropicJob(
            id="msgbatch_123",
            status='ended',
            created_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            results_url="https://example.com/results.jsonl"
        )

        # Mock the file download content as a proper JSONL format
        mock_file_content = (
            b'{"result":{"message":{"usage":{"input_tokens":10, "output_tokens": 5}}}}\n'
            b'{"result":{"message":{"usage":{"input_tokens":20, "output_tokens": 10}}}}\n'
            b'{"result":{"message":{"usage":{"input_tokens":30, "output_tokens": 15}}}}\n'
        )
        mock_client.get.return_value = mock_file_content

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertEqual(total_tokens, 90)
        mock_client.get.assert_called_once_with("https://example.com/results.jsonl", cast_to=bytes)

    @patch('providers.anthropic.Anthropic')
    def test_calculate_total_tokens_no_url(self, mock_client):
        """Test that token calculation returns None when there is no results URL."""
        # Arrange
        provider = AnthropicProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockAnthropicJob(
            id="msgbatch_123",
            status='ended',
            created_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            results_url=None  # No results URL
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.get.assert_not_called()

    @patch('providers.anthropic.Anthropic')
    def test_calculate_total_tokens_job_not_succeeded(self, mock_client):
        """Test that token calculation returns None for a non-successful job."""
        # Arrange
        provider = AnthropicProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockAnthropicJob(
            id="msgbatch_123",
            status='in_progress',  # Job did not succeed
            created_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            results_url="https://example.com/results.jsonl"
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.get.assert_not_called()

if __name__ == '__main__':
    unittest.main()
