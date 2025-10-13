# LLM Batch API Performance Comparison

This project provides a unified command-line interface to test and compare the batch processing capabilities of the Google and OpenAI APIs. It includes an abstraction layer that allows for easy interaction with both providers through a single script.

## Features

- **Unified CLI:** A single `main.py` script to create, list, and cancel batch jobs for both Gemini and OpenAI.
- **Provider Abstraction:** The `batch_processor.py` module abstracts the provider-specific logic, making it easy to add new providers in the future.
- **Asynchronous Job Handling:** Scripts demonstrate the full workflow of creating a batch job, polling for its completion, and retrieving the results.
- **Configuration:** Uses a `.env` file to manage API keys.

## Project Structure

- `main.py`: The main command-line interface for interacting with the batch processors.
- `provider_factory.py`: Contains the factory function for creating provider instances.
- `.env`: For storing your `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY`.
- `.gitignore`: Ignores virtual environment files and `.env`.
- `requirements.txt`: Lists the required Python packages.

## Setup

1.  **Clone the repository.**
2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create a `.env` file** and add your API keys:
    ```
    GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
    ```

## Usage

The `main.py` script is the primary entry point.

### Create a Batch Job

```bash
# For OpenAI
python main.py openai create

# For Google
python main.py google create
```

### List Recent Batch Jobs

```bash
# For OpenAI
python main.py openai list

# For Google
python main.py google list
```

### Cancel a Batch Job

You will need the `job_id` from the `create` or `list` command.

```bash
# For OpenAI
python main.py openai cancel --job_id <YOUR_OPENAI_JOB_ID>

# For Google (Note: This deletes the job)
python main.py google cancel --job_id <YOUR_GOOGLE_JOB_ID>
```

## Batch Job States

This section documents the batch job states for each provider as of October 12, 2025.

### User-Assigned Statuses

The `UserStatus` enum in `data_models.py` defines a set of standardized statuses that are used throughout the application. This provides a consistent way to handle job states, regardless of the provider.

| `UserStatus`          | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| `SUCCEEDED`           | The job completed successfully.                                          |
| `FAILED`              | The job failed for a reason other than cancellation or timeout.          |
| `CANCELLED_TIMED_OUT` | The job was cancelled because it exceeded the 24-hour timeout.           |
| `IN_PROGRESS`         | The job is still being processed and hasn't exceeded 24-hour timeout. |
| `CANCELLED_ON_DEMAND` | The job was cancelled by a user request.                                 |
| `UNKNOWN`             | The job is in an unknown or unexpected state.                            |

### Google

- **Source:** [https://ai.google.dev/gemini-api/docs/batch-api#batch-job-status](https://ai.google.dev/gemini-api/docs/batch-api#batch-job-status)
- **Terminal States:**
    - `JOB_STATE_SUCCEEDED`
    - `JOB_STATE_FAILED`
    - `JOB_STATE_CANCELLED`
    - `JOB_STATE_EXPIRED`
- **Non-Terminal States:**
    - `JOB_STATE_PENDING`
    - `BATCH_STATE_RUNNING`

### OpenAI

- **Source:** [https://platform.openai.com/docs/api-reference/batch](https://platform.openai.com/docs/api-reference/batch)
- **FAQ:** [https://help.openai.com/en/articles/9197833-batch-api-faq](https://help.openai.com/en/articles/9197833-batch-api-faq)
- **Terminal States:**
    - `completed`
    - `failed`
    - `cancelled`
    - `expired`
- **Non-Terminal States:**
    - `validating`
    - `in_progress`
    - `finalizing`
    - `cancelling`

### Anthropic

- **Source:** [https://docs.claude.com/en/docs/build-with-claude/batch-processing#tracking-your-batch](https://docs.claude.com/en/docs/build-with-claude/batch-processing#tracking-your-batch)
- **Terminal States:**
    - `ended`
- **Non-Terminal States:**
    - `in_progress`
- **Individual Request Result Types:**
    - `succeeded`
    - `errored`
    - `canceled`
    - `expired`

### Status Mapping

This section documents the mapping from the provider-specific job statuses to the unified `UserStatus` enum.

| Provider  | Service Status          | `UserStatus`            | Notes                                                                 |
| --------- | ----------------------- | ----------------------- | --------------------------------------------------------------------- |
| Google    | `JOB_STATE_SUCCEEDED`   | `SUCCEEDED`             |                                                                       |
|           | `JOB_STATE_FAILED`      | `FAILED`                |                                                                       |
|           | `JOB_STATE_EXPIRED`     | `CANCELLED_TIMED_OUT`   | The job expired after 48 hours.                                       |
|           | `JOB_STATE_CANCELLED`   | `CANCELLED_TIMED_OUT`   | If the job ran for more than 24 hours.                                |
|           | `JOB_STATE_CANCELLED`   | `CANCELLED_ON_DEMAND`   | If the job was cancelled by the user.                                 |
|           | `JOB_STATE_PENDING`     | `IN_PROGRESS`           |                                                                       |
|           | `BATCH_STATE_RUNNING`   | `IN_PROGRESS`           |                                                                       |
| OpenAI    | `completed`             | `SUCCEEDED`             |                                                                       |
|           | `failed`                | `FAILED`                |                                                                       |
|           | `expired`               | `CANCELLED_TIMED_OUT`   | The batch could not be completed within the SLA time window.          |
|           | `cancelled`             | `CANCELLED_ON_DEMAND`   |                                                                       |
|           | `validating`            | `IN_PROGRESS`           |                                                                       |
|           | `in_progress`           | `IN_PROGRESS`           |                                                                       |
|           | `finalizing`            | `IN_PROGRESS`           |                                                                       |
|           | `cancelling`            | `IN_PROGRESS`           |                                                                       |
| Anthropic | `ended` (with `succeeded` requests) | `SUCCEEDED`             |                                                                       |
|           | `ended` (with `errored` requests) | `FAILED`                |                                                                       |
|           | `ended` (with `expired` requests) | `CANCELLED_TIMED_OUT`   |                                                                       |
|           | `ended` (with `canceled` requests) | `CANCELLED_ON_DEMAND`   |                                                                       |
|           | `in_progress`           | `IN_PROGRESS`           |                                                                       |

## Known Issues

- When running a Google batch job, you may see a `UserWarning: BATCH_STATE_RUNNING is not a valid JobState`. This is a known issue in the `google-genai` library and can be safely ignored. The script will continue to poll until the job reaches a final state.
