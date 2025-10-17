import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch
from absl import flags

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))

from main import main as main_app


class TestMainApp(unittest.TestCase):

    def setUp(self):
        # Reset flags before each test
        flags.FLAGS.unparse_flags()

    @patch('main.load_dotenv')
    @patch('main.PROMPTS', ["prompt1", "prompt2", "prompt3", "prompt4"])
    @patch('main.get_provider')
    def test_create_jobs_respects_num_jobs_flag(self, mock_get_provider,
                                                mock_load_dotenv):
        # Arrange
        mock_provider = MagicMock()
        mock_provider.create_jobs.return_value = ["job-1", "job-2"]
        mock_provider.generate_job_report_for_user.side_effect = [
            MagicMock(to_json=lambda: '{"job_id": "job-1"}'),
            MagicMock(to_json=lambda: '{"job_id": "job-2"}')
        ]
        mock_get_provider.return_value = mock_provider

        test_args = [
            "main.py", "--provider=google", "--action=create_jobs",
            "--num_jobs=2", "--requests_per_job=2"
        ]

        # Act
        with patch('sys.argv', test_args):
            with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
                flags.FLAGS(test_args)  # Parse the flags
                main_app(test_args)

        # Assert
        mock_provider.create_jobs.assert_called_once_with(
            2, 2, ["prompt1", "prompt2", "prompt3", "prompt4"])
        self.assertEqual(mock_provider.generate_job_report_for_user.call_count,
                         2)

        # Verify that the output file was written to with the correct number of lines
        mock_file().write.assert_called()
        self.assertEqual(mock_file().write.call_count, 2)

    @patch('main.load_dotenv')
    @patch('main.PROMPTS', ["prompt1"])
    @patch('main.get_provider')
    def test_output_filename_is_standardized(self, mock_get_provider,
                                             mock_load_dotenv):
        # Arrange
        mock_provider = MagicMock()
        mock_provider.create_jobs.return_value = ["job-1"]
        mock_provider.generate_job_report_for_user.return_value = MagicMock(
            to_json=lambda: '{"job_id": "job-1"}')
        mock_get_provider.return_value = mock_provider

        test_args = [
            "main.py", "--provider=openai", "--action=create_jobs",
            "--num_jobs=1"
        ]

        # Act
        with patch('sys.argv', test_args):
            with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
                with patch('main.datetime') as mock_datetime:
                    mock_datetime.now.return_value.strftime.return_value = "YYYYMMDD_HHMMSS"
                    flags.FLAGS(test_args)  # Parse the flags
                    main_app(test_args)

        # Assert
        mock_file.assert_called_once_with(
            "openai_job_reports_YYYYMMDD_HHMMSS.jsonl", "a", encoding="utf-8")


if __name__ == '__main__':
    unittest.main()
