"""
This script implements batch embedding with the OpenAI API.

To run this script:
1. Make sure you have a .env file in the root directory with your OPENAI_API_KEY.
   Example:
   OPENAI_API_KEY="your_api_key_here"

2. Run the script from your terminal:
   python openai_batch_embeddings.py
"""
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
from embedding_prompts import SAMPLE_TEXTS

load_dotenv()

# --- Configuration ---
# Ensure the OPENAI_API_KEY environment variable is set.
API_KEY = os.getenv("OPENAI_API_KEY")

def run():
    """Initializes the client and runs a batch embedding request."""
    if not API_KEY:
        print("Error: Please set the OPENAI_API_KEY environment variable.")
        return

    print("Initializing OpenAI client...")
    client = OpenAI(api_key=API_KEY)

    print("\\n--- OpenAI Batch Embedding Script ---")

    # Sample texts for the batch embedding job
    texts = SAMPLE_TEXTS

    batch_file_path = "openai_batch_input.jsonl"
    batch_file = None
    batch_job = None
    result_file_id = None

    try:
        # Create the batch file
        with open(batch_file_path, "w", encoding="utf-8") as f:
            for i, text in enumerate(texts):
                f.write(json.dumps({
                    "custom_id": f"request-{i}",
                    "method": "POST",
                    "url": "/v1/embeddings",
                    "body": {
                        "input": text,
                        "model": "text-embedding-3-small"
                    }
                }) + "\n")

        # Upload the batch file
        print("Uploading batch file...")
        with open(batch_file_path, "rb") as f:
            batch_file = client.files.create(
                file=f,
                purpose="batch"
            )
        print("File uploaded successfully:")
        print(batch_file)
        os.remove(batch_file_path) # Clean up the local input file

        # Create the batch job
        print("Creating batch job...")
        batch_job = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )
        print(f"Successfully created batch job: {batch_job.id}")

        # Monitor the batch job
        print(f"Monitoring batch job with ID: {batch_job.id}")
        while True:
            batch_job = client.batches.retrieve(batch_job.id)
            if batch_job.status == "completed":
                print("Batch job completed.")
                break
            elif batch_job.status == "failed":
                print("Batch job failed.")
                break
            time.sleep(10)

        # Download and process the results
        if batch_job.status == "completed":
            result_file_id = batch_job.output_file_id
            if result_file_id:
                result_content = client.files.content(result_file_id).text
                print("Embeddings:")
                with open("openai_embeddings.jsonl", "w", encoding="utf-8") as f_out:
                    for line in result_content.splitlines():
                        data = json.loads(line)
                        embedding = data['response']['body']['data'][0]['embedding']
                        print(f"  - Vector: {embedding[:10]}... (truncated)")
                        f_out.write(json.dumps({"embedding": embedding}) + "\n")
            else:
                print("Batch job completed, but no output file was generated.")

    except Exception as e:
        print(f"\nAn unhandled error occurred during the API process: {e}")

    finally:
        # Cleanup (CRITICAL: removes files from OpenAI's servers)
        print("\n--- Cleaning up files... ---")
        if batch_file and batch_file.id:
            try:
                client.files.delete(batch_file.id)
                print(f"Deleted uploaded file: {batch_file.id}")
            except Exception as e:
                print(f"Warning: Could not delete uploaded file {batch_file.id}. Error: {e}")

        if result_file_id:
            try:
                client.files.delete(result_file_id)
                print(f"Deleted result file: {result_file_id}")
            except Exception as e:
                print(f"Warning: Could not delete result file {result_file_id}. Error: {e}")

        print("Cleanup complete.")


if __name__ == "__main__":
    run()
