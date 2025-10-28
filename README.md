# LLM Batch API Performance Comparison

This project provides a unified command-line interface to test and compare the batch processing capabilities of the Google and OpenAI APIs. It includes an abstraction layer that allows for easy interaction with both providers through a single script.

## Features

- **Unified CLI:** A single `main.py` script to create, list, and cancel batch jobs for both Gemini and OpenAI.
- **Dual Task Support:** Supports both `text-generation` and `embedding` tasks.
- **Provider Abstraction:** The `batch_processor.py` module abstracts the provider-specific logic, making it easy to add new providers in the future.
- **Asynchronous Job Handling:** Scripts demonstrate the full workflow of creating a batch job, polling for its completion, and retrieving the results.
- **Token Usage Reporting:** Automatically calculates and reports the total token usage for successfully completed batch jobs.
- **Configuration:** Uses a `.env` file to manage API keys.

## Project Structure

- `main.py`: The main command-line interface for interacting with the batch processors.
- `provider_factory.py`: Contains the factory function for creating provider instances.
- `prompts.py`: Contains the prompts for text generation tasks.
- `embedding_prompts.py`: Contains the prompts for embedding tasks.
- `.env`: For storing your `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY`.
- `.gitignore`: Ignores virtual environment files and `.env`.
- `requirements.txt`: Lists the required Python packages.

## Models Used

As of October 26, 2025, the following models are used for the batch jobs:

### Text Generation

| Provider  | Model Name                   |
| --------- | ---------------------------- |
| Google    | `gemini-2.5-flash-lite`      |
| Google-Vertex AI    | `gemini-2.5-flash-lite`      |
| OpenAI    | `gpt-4o-mini`                |
| Anthropic | `claude-3-haiku-20240307`    |

### Embeddings

| Provider  | Model Name                   |
| --------- | ---------------------------- |
| Google    | `gemini-embedding-001`       |
| OpenAI    | `text-embedding-3-small`     |

These models are defined as constants in their respective provider files (e.g., `providers/google.py`).

### Execution Details

- **Max Tokens:** All providers are configured to generate a maximum of `1024` tokens per request. This is defined in the `providers/base.py` file.

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
    If you are using Google Vertex AI provider, please also add your GCP project and location:
    ```
    GOOGLE_CLOUD_PROJECT="YOUR_GCP_PROJECT
    GOOGLE_CLOUD_LOCATION="YOUR_GCP_LOCATION"
    ```


## Usage

The `main.py` script is the primary entry point. All commands follow the format: `python main.py --provider <provider> --action <action> --task <task> [options]`.

### Selecting a Task

The `--task` flag allows you to choose between `text-generation` and `embedding`. If not specified, it defaults to `text-generation`.

### Create Batch Jobs

Creates a specified number of new batch jobs (`--num_jobs`), with each job containing a specified number of requests (`--requests_per_job`). For example, `--num_jobs 5 --requests_per_job 2` will create 5 separate batch jobs, each containing 2 requests.

#### Text Generation

```bash
# For OpenAI (creates 10 jobs by default, with 1 request per job)
python main.py --provider openai --action create_jobs --task text-generation

# For Google (creates 5 jobs with 2 requests per job)
python main.py --provider google --action create_jobs --task text-generation --num_jobs 5 --requests_per_job 2
```

#### Embeddings

```bash
# For OpenAI
python main.py --provider openai --action create_jobs --task embedding

# For Google
python main.py --provider google --action create_jobs --task embedding --num_jobs 5 --requests_per_job 2
```

### Check Recent Batch Jobs

Checks for jobs created in the last few hours.

```bash
# For OpenAI (checks last 36 hours by default)
python main.py --provider openai --action check_recent_jobs

# For Google (checks last 12 hours)
python main.py --provider google --action check_recent_jobs --hours_ago 12
```

### Check a Single Job

Retrieves the status and report for a specific job.

```bash
# For any provider
python main.py --provider <provider> --action check_single_job --job_id <YOUR_JOB_ID>
```

### Check Jobs from a File

Checks the status of jobs listed in a state file.

```bash
# For any provider
python main.py --provider <provider> --action check_jobs_from_file --state_file <PATH_TO_YOUR_STATE_FILE>
```

### Polling for Job Completion

To monitor a set of jobs until they all reach a terminal state (e.g., `SUCCEEDED`, `FAILED`), you can repeatedly use the output of one `check_jobs_from_file` run as the input for the next. This creates a polling loop that updates the status of all non-terminal jobs.

**Example Workflow:**

1.  **Create initial jobs and the first report file:**
    ```bash
    python main.py --provider google --action create_jobs --num_jobs 5
    # This creates a file like google_job_reports_YYYYMMDD_HHMMSS.jsonl
    ```

2.  **Use the generated report to check for updates:**
    ```bash
    python main.py --provider google --action check_jobs_from_file --state_file <path_to_first_report>.jsonl
    # This creates a new file, google_job_reports_YYYYMMDD_HHMMSS.jsonl, with updated statuses.
    ```

3.  **Repeat the process** with the newest report file until all jobs have reached a terminal state. The script will automatically ignore completed jobs, so the output file will eventually be empty.

**Automation Script:**

The process of starting a job and repeatedly checking newest report file can be automated by running `run_and_monitor.sh`.

```bash
bash ./run_and_monitor.sh --provider google --task text-generation --num_jobs 20 --requests_per_job 100 --interval 20
# This creates 20 text generation batch jobs for Google provider, checks newest report with `google_job_reports` prefix every 20 seconds until the newest report is empty, which means all jobs reach terminal state.
```


### Cancel a Batch Job

Cancels a specific job.

```bash
# For OpenAI
python main.py --provider openai --action cancel_job --job_id <YOUR_OPENAI_JOB_ID>

# For Google (Note: This deletes the job)
python main.py --provider google --action cancel_job --job_id <YOUR_GOOGLE_JOB_ID>
```

### Download Batch Job Results

Downloads the results of a completed batch job.

```bash
# For any provider
python main.py --provider <provider> --action download_results --job_id <YOUR_JOB_ID> --enable_download_results
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

### Google

- **Source:** [https://ai.google.dev/gemini-api/docs/batch-api#batch-job-status](https://ai.google.dev/gemini-api/docs/batch-api#batch-job-status)
- **Terminal States:**
    - `JOB_STATE_SUCCEEDED`
    - `JOB_STATE_FAILED`
    - `JOB_STATE_CANCELLED`
    - `JOB_STATE_EXPIRED`
- **Non-Terminal States:**
    - `JOB_STATE_PENDING`
    - `JOB_STATE_RUNNING`

### Google-Vertex AI

- **Source:** [https://cloud.google.com/vertex-ai/docs/reference/rest/v1/JobState](https://cloud.google.com/vertex-ai/docs/reference/rest/v1/JobState)
- **Terminal States:**
    - `JOB_STATE_SUCCEEDED`
    - `JOB_STATE_FAILED`
    - `JOB_STATE_CANCELLED`
    - `JOB_STATE_CANCELLING`
    - `JOB_STATE_PARTIALLY_SUCCEEDED`
    - `JOB_STATE_EXPIRED`
- **Non-Terminal States:**
    - `JOB_STATE_PENDING`
    - `JOB_STATE_RUNNING`
    - `JOB_STATE_PAUSED`
    - `JOB_STATE_UNSPECIFIED`
    - `JOB_STATE_QUEUED`
    - `JOB_STATE_UPDATING`

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
|           | `JOB_STATE_RUNNING`     | `IN_PROGRESS`           |                                                                       |
| Google-Vertex AI    | `JOB_STATE_SUCCEEDED`   | `SUCCEEDED`   |                                                                       |
|           | `JOB_STATE_FAILED`      | `FAILED`                |                                                                       |
|           | `JOB_STATE_PARTIALLY_SUCCEEDED`      | `FAILED`   |                                                                       |
|           | `JOB_STATE_EXPIRED`     | `CANCELLED_TIMED_OUT`   | The job expired after 48 hours.                                       |
|           | `JOB_STATE_CANCELLED`, `JOB_STATE_CANCELLING`     | `CANCELLED_TIMED_OUT`   | If the job ran for more than 24 hours.      |
|           | `JOB_STATE_CANCELLED`, `JOB_STATE_CANCELLING`     | `CANCELLED_ON_DEMAND`   | If the job was cancelled by the user.       |
|           | `JOB_STATE_PENDING`     | `IN_PROGRESS`           |                                                                       |
|           | `JOB_STATE_RUNNING`     | `IN_PROGRESS`           |                                                                       |
|           | `JOB_STATE_QUEUED`      | `IN_PROGRESS`           |                                                                       |
|           | `JOB_STATE_UNSPECIFIED` | `IN_PROGRESS`           |                                                                       |
|           | `JOB_STATE_PAUSED`      | `IN_PROGRESS`           |                                                                       |
|           | `JOB_STATE_UPDATING`    | `IN_PROGRESS`           |                                                                       |
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
