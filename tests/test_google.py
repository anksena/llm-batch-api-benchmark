import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from providers.google import GoogleProvider
from data_models import UserStatus

class MockGoogleJob:
    def __init__(self, name, state, create_time, end_time, dest_file_name=None):
        self.name = name
        self.state = MagicMock()
        self.state.name = state
        self.create_time = create_time
        self.end_time = end_time
        self.dest = MagicMock()
        self.dest.file_name = dest_file_name

class TestGoogleProvider(unittest.TestCase):

    @patch('providers.google.google_genai.Client')
    def test_calculate_total_tokens_success(self, mock_client):
        """Test that total tokens are calculated correctly for a successful job."""
        # Arrange
        provider = GoogleProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockGoogleJob(
            name="job-123",
            state='JOB_STATE_SUCCEEDED',
            create_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            dest_file_name="results.jsonl"
        )

        # Mock the file download content as a proper JSONL format
        mock_file_content = (
            b'{"response":{"usageMetadata":{"totalTokenCount":10}}}\n'
            b'{"response":{"usageMetadata":{"totalTokenCount":20}}}\n'
            b'{"response":{"usageMetadata":{"totalTokenCount":30}}}\n'
        )
        mock_client.files.download.return_value = mock_file_content

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertEqual(total_tokens, 60)
        mock_client.files.download.assert_called_once_with(file="results.jsonl")

    @patch('providers.google.google_genai.Client')
    def test_calculate_total_tokens_no_file(self, mock_client):
        """Test that token calculation returns None when there is no result file."""
        # Arrange
        provider = GoogleProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockGoogleJob(
            name="job-123",
            state='JOB_STATE_SUCCEEDED',
            create_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            dest_file_name=None  # No destination file
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.files.download.assert_not_called()

    @patch('providers.google.google_genai.Client')
    def test_calculate_total_tokens_job_not_succeeded(self, mock_client):
        """Test that token calculation returns None for a non-successful job."""
        # Arrange
        provider = GoogleProvider(api_key="test_key")
        provider.client = mock_client

        mock_job = MockGoogleJob(
            name="job-123",
            state='JOB_STATE_FAILED',  # Job did not succeed
            create_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            dest_file_name="results.jsonl"
        )

        # Act
        total_tokens = provider._calculate_total_tokens(mock_job)

        # Assert
        self.assertIsNone(total_tokens)
        mock_client.files.download.assert_not_called()

if __name__ == '__main__':
    unittest.main()
