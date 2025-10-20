import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.openai import OpenAIProvider
from data_models import UserStatus

class MockOpenAIJob:
    def __init__(self, id, status, created_at, completed_at, output_file_id=None):
        self.id = id
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.output_file_id = output_file_id
        self.request_counts = MagicMock()
        self.request_counts.total = 3
        self.request_counts.completed = 3
        self.request_counts.failed = 0

class TestOpenAIProvider(unittest.TestCase):

    @patch('providers.openai.OpenAI')
    def test_calculate_total_tokens_success(self, mock_client):
        """Test that total tokens are calculated correctly for a successful job."""
        # Arrange
        provider = OpenAIProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockOpenAIJob(
            id="batch_123",
            status='completed',
            created_at=datetime.now(timezone.utc).timestamp(),
            completed_at=datetime.now(timezone.utc).timestamp(),
            output_file_id="file-123"
        )

        # Mock the file download content as a proper JSONL format
        mock_file_content = (
            b'{"response": {"body": {"usage": {"total_tokens": 15}}}}\n'
            b'{"response": {"body": {"usage": {"total_tokens": 25}}}}\n'
            b'{"response": {"body": {"usage": {"total_tokens": 35}}}}\n'
        )
        mock_file_response = MagicMock()
        mock_file_response.read.return_value = mock_file_content
        mock_client.files.content.return_value = mock_file_response

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertEqual(total_tokens, 75)
        mock_client.files.content.assert_called_once_with("file-123")

    @patch('providers.openai.OpenAI')
    def test_calculate_total_tokens_no_file(self, mock_client):
        """Test that token calculation returns None when there is no result file."""
        # Arrange
        provider = OpenAIProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockOpenAIJob(
            id="batch_123",
            status='completed',
            created_at=datetime.now(timezone.utc).timestamp(),
            completed_at=datetime.now(timezone.utc).timestamp(),
            output_file_id=None  # No output file
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.files.content.assert_not_called()

    @patch('providers.openai.OpenAI')
    def test_calculate_total_tokens_job_not_succeeded(self, mock_client):
        """Test that token calculation returns None for a non-successful job."""
        # Arrange
        provider = OpenAIProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockOpenAIJob(
            id="batch_123",
            status='failed',  # Job did not succeed
            created_at=datetime.now(timezone.utc).timestamp(),
            completed_at=datetime.now(timezone.utc).timestamp(),
            output_file_id="file-123"
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.files.content.assert_not_called()

if __name__ == '__main__':
    unittest.main()
