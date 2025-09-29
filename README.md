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

### List Supported Models

```bash
# For OpenAI
python main.py openai list-models

# For Google (lists models that support batch processing)
python main.py google list-models

## Known Issues

- When running a Google batch job, you may see a `UserWarning: BATCH_STATE_RUNNING is not a valid JobState`. This is a known issue in the `google-genai` library and can be safely ignored. The script will continue to poll until the job reaches a final state.
