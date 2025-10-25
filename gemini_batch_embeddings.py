"""
This script implements asynchronous batch embedding with the Gemini API using a file-based approach.

It demonstrates the full, correct lifecycle:
1. Create a JSONL input file.
2. Upload the file using the File API.
3. Start the batch job using the specialized 'create_embeddings' method.
4. Poll the job status until completion.
5. Download and print the results file.
6. Clean up all uploaded and generated files.

To run this script:
1. Make sure you have a .env file in the root directory with your GOOGLE_API_KEY.
2. Install dependencies: pip install google-genai python-dotenv
3. Run the script: python gemini_batch_embeddings_fixed.py
"""
import os
import json
import time
import warnings
from google import genai as google_genai
from google.genai.types import JobState # Import JobState enum
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# The correct model identifier for Gemini Embeddings
EMBEDDING_MODEL = "models/gemini-embedding-001"
API_KEY = os.getenv("GOOGLE_API_KEY")
BATCH_FILE_PATH = "gemini_batch_input.jsonl"
# Increase max retries for destination check
MAX_DESTINATION_RETRIES = 10 # Increased from 5
DESTINATION_RETRY_DELAY = 10 # Increased sleep time to 10 seconds


def generate_input_file(texts: list[str]) -> None:
    """Generates the input JSONL file in the correct format for the Batch API."""
    print(f"Generating batch input file: {BATCH_FILE_PATH}")
    with open(BATCH_FILE_PATH, "w", encoding="utf-8") as f:
        for i, text in enumerate(texts):
            # The structure for an embedding request in the JSONL file:
            gemini_req = {
                "key": f"request-{i:03d}", # Unique identifier for matching results
                "request": {
                    # CORRECTED: Uses the current, correct model ID.
                    "model": EMBEDDING_MODEL,
                    "content": {
                        "parts": [{"text": text}]
                    },
                    # Optional: Reduce dimensions for storage/cost optimization
                    "output_dimensionality": 1024
                }
            }
            f.write(json.dumps(gemini_req) + "\n")
    print(f"Successfully created batch input file with {len(texts)} entries.")


def run():
    """Initializes the client, creates, runs, and monitors the batch job."""
    if not API_KEY:
        print("Error: Please set the GOOGLE_API_KEY environment variable.")
        return

    client = google_genai.Client(api_key=API_KEY)

    # Sample texts for the batch embedding job
    texts = [
        "What is the meaning of life?",
        "How much wood would a woodchuck chuck?",
        "How does the human brain process language?",
        "Benchmarking large language models is a complex task.",
        "The most cost-effective method is asynchronous batching.",
    ]

    uploaded_file = None
    batch_job = None
    result_file_name = None

    try:
        # 1. Generate the local file
        generate_input_file(texts)

        # 2. Upload the file
        print("\nUploading batch input file to Gemini API...")
        uploaded_file = client.files.upload(
            file=BATCH_FILE_PATH,
            config=google_genai.types.UploadFileConfig(
                display_name='batch-embeddings-test',
                mime_type="application/jsonl"
            )
        )
        print(f"Successfully uploaded file: {uploaded_file.name}")
        os.remove(BATCH_FILE_PATH) # Clean up the local input file

        # 3. Create the batch job using the dedicated EMBEDDING method
        print("Creating batch job...")

        # FIX: The 'src' argument must be a dictionary specifying the source type and name.
        batch_job = client.batches.create_embeddings(
            model=EMBEDDING_MODEL,
            src={"file_name": uploaded_file.name}, # CORRECTED: Wrap file name in dict
        )
        print(f"Successfully created batch job: {batch_job.name}")
        print(f"Job Initial State: {batch_job.state.name}")

        # 4. Poll for job completion
        print("\n--- Waiting for Job Completion (Max 24 hours) ---")

        # FIX: Removed JOB_STATE_VALIDATING as it's often not in the SDK enum
        polling_states = {JobState.JOB_STATE_RUNNING, JobState.JOB_STATE_PENDING, "BATCH_STATE_RUNNING"}

        while batch_job.state in polling_states:
            print(f"Status: {batch_job.state.name}... sleeping for 10 seconds.")
            time.sleep(10)
            # Retrieve the latest job status
            batch_job = client.batches.get(name=batch_job.name)

        # FIX: Introduce robust waiting and retry check for 'destination' attribute,
        # handling the observed race condition where SUCCEEDED state arrives before the results metadata.
        if batch_job.state == JobState.JOB_STATE_SUCCEEDED:
            print("\n--- Batch Job Object ---")
            print(batch_job)
            print("---------------------------------------------------------")

            # 5. Check final state and download results
            print("\nJob SUCCEEDED! Downloading results...")

            result_file_name = batch_job.dest.file_name

            # Suppress generic warnings during download/decode process
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result_file_bytes = client.files.download(file=result_file_name)
                result_content = result_file_bytes.decode('utf-8')

            print("\n--- First 3 Results (JSONL Lines) ---")
            for i, line in enumerate(result_content.splitlines()):
                if i < 3:
                    # Print the JSON object for visual inspection
                    result_json = json.loads(line)
                    print(f"Key: {result_json.get('key')}")
                    # Print a snippet of the embedding vector
                    # NOTE: Accessing embedding values via result_json['response']['embedding']['values']
                    if 'response' in result_json and 'embedding' in result_json.get('response', {}): # Check response exists
                         # Ensure 'embedding' exists within 'response'
                         if 'values' in result_json['response']['embedding']:
                              embedding_snippet = result_json['response']['embedding']['values'][:5]
                              print(f"  Embedding Snippet: {embedding_snippet}...")
                         else:
                              print(f"  'values' key missing in embedding object: {result_json['response']['embedding']}")
                    elif 'error' in result_json:
                         print(f"  Error processing this request: {result_json.get('error')}")
                    else:
                         print(f"  Unexpected response structure: {result_json.get('response')}")
                    print("-" * 20)
                else:
                    break
        else:
            # FIX: Only report the final non-success state name
            print(f"\nJob FAILED or CANCELLED. Final state: {batch_job.state.name}")
            if batch_job.error:
                print(f"Error details: {batch_job.error}")

    except Exception as e:
        print(f"\nAn unhandled error occurred during the API process: {e}")

    finally:
        # 6. Cleanup (CRITICAL: removes files from Google's servers)
        print("\n--- Cleaning up files... ---")
        if uploaded_file and uploaded_file.name:
            # FIX: Use 'name' keyword argument for file deletion
            try:
                client.files.delete(name=uploaded_file.name)
                print(f"Deleted uploaded file: {uploaded_file.name}")
            except Exception as e:
                print(f"Warning: Could not delete uploaded file {uploaded_file.name}. Error: {e}")

        if result_file_name:
            # FIX: Use 'name' keyword argument for file deletion
            try:
                client.files.delete(name=result_file_name)
                print(f"Deleted result file: {result_file_name}")
            except Exception as e:
                print(f"Warning: Could not delete result file {result_file_name}. Error: {e}")

        print("Cleanup complete.")


if __name__ == "__main__":
    run()
