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
    texts = [
        "What is the meaning of life?",
        "How much wood would a woodchuck chuck?",
        "How does the brain work?",
    ]

    # Create the batch file
    batch_file_path = "batch_files/openai_batch.jsonl"
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
    batch_file = client.files.create(
        file=open(batch_file_path, "rb"),
        purpose="batch"
    )
    print("File uploaded successfully:")
    print(batch_file)

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
        result_content = client.files.content(result_file_id).text
        print("Embeddings:")
        for line in result_content.splitlines():
            data = json.loads(line)
            embedding = data['response']['body']['data'][0]['embedding']
            print(f"  - Vector: {embedding[:10]}... (truncated)")


if __name__ == "__main__":
    run()
