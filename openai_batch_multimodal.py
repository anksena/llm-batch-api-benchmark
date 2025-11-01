"""
Standalone script for running a multimodal batch job with the OpenAI API.

This script demonstrates a robust, scalable lifecycle for multimodal batch jobs:
1.  Uploads each image file individually to the File API to get a file ID.
2.  Generates a JSONL request file where each request references an image file ID.
3.  Uploads the JSONL request file.
4.  Creates the batch job using the uploaded request file.
5.  Polls the job status until it completes.
6.  Downloads and prints the results.
7.  Deletes all uploaded files (images, request file, and result file).
"""

import os
import json
import time
import uuid
from openai import OpenAI
from dotenv import load_dotenv
from google.cloud import storage

# --- Configuration ---
MODEL_NAME = "gpt-4o-mini"
IMAGE_FILES = ["test_images/image1.jpg", "test_images/image2.jpg"]
LOCAL_REQUEST_FILE = "openai_batch_multimodal_gcs_requests.jsonl"
LOCAL_OUTPUT_FILE = "openai_batch_multimodal_gcs_results.jsonl"
POLL_INTERVAL_SECONDS = 10

def run_openai_batch_job_with_gcs():
    """Orchestrates the entire API workflow using GCS-hosted images."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file")

    client = OpenAI(api_key=api_key)
    storage_client = storage.Client()

    bucket_name = f"openai-batch-test-{uuid.uuid4()}"
    bucket = None
    blobs = []
    uploaded_request_file = None
    batch_job = None
    result_file_id = None

    try:
        # 1. Create a GCS bucket
        print(f"--- Creating GCS bucket: {bucket_name} ---")
        bucket = storage_client.create_bucket(bucket_name, location="US")
        print("  - Bucket created.")

        # 2. Upload images and make them public
        image_urls = []
        for image_path in IMAGE_FILES:
            blob_name = os.path.basename(image_path)
            blob = bucket.blob(blob_name)
            print(f"--- Uploading {image_path} to GCS... ---")
            blob.upload_from_filename(image_path)
            print("  - Upload complete.")
            print("--- Making blob public... ---")
            blob.make_public()
            print(f"  - Blob is now public at: {blob.public_url}")
            blobs.append(blob)
            image_urls.append(blob.public_url)

        # 3. Generate the JSONL request file with the public GCS URLs
        print(f"\n--- Generating batch request file: {LOCAL_REQUEST_FILE} ---")
        with open(LOCAL_REQUEST_FILE, "w") as f:
            for i, image_url in enumerate(image_urls):
                request_data = {
                    "custom_id": f"request-gcs-{i}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL_NAME,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Caption this image in one sentence."},
                                    {"type": "image_url", "image_url": {"url": image_url}}
                                ]
                            }
                        ]
                    }
                }
                f.write(json.dumps(request_data) + "\n")
        print("  - Generation complete.")

        # 4. Upload the JSONL request file
        print(f"\n--- Uploading request file... ---")
        with open(LOCAL_REQUEST_FILE, "rb") as f:
            uploaded_request_file = client.files.create(file=f, purpose="batch")
        print(f"  - Success! File ID: {uploaded_request_file.id}")
        os.remove(LOCAL_REQUEST_FILE)

        # 5. Create the batch job
        print("\n--- Creating batch job... ---")
        batch_job = client.batches.create(
            input_file_id=uploaded_request_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        print(f"  - Created job: {batch_job.id} with status: {batch_job.status}")

        # 5. Poll for completion
        print("\n--- Polling for job completion... ---")
        while batch_job.status not in ("completed", "failed", "cancelled", "expired"):
            time.sleep(POLL_INTERVAL_SECONDS)
            batch_job = client.batches.retrieve(batch_job.id)
            print(f"  - Job status: {batch_job.status}")

        # 6. Process results
        if batch_job.status == "completed":
            print("\n--- Job COMPLETED! Downloading and printing results... ---")
            result_file_id = batch_job.output_file_id
            result_content = client.files.content(result_file_id).read()
            
            print(f"Saving results to {LOCAL_OUTPUT_FILE} and printing.")
            with open(LOCAL_OUTPUT_FILE, "wb") as f:
                f.write(result_content)
            
            for line in result_content.decode("utf-8").splitlines():
                result_json = json.loads(line)
                print(f"--- Result for Custom ID: {result_json.get('custom_id')} ---")
                if 'response' in result_json:
                    print(json.dumps(result_json['response'], indent=2))
                elif 'error' in result_json:
                    print(f"Error: {result_json['error']}")
        else:
            print(f"\n--- Job FAILED or was CANCELLED. Final status: {batch_job.status} ---")
            if batch_job.errors:
                print(f"Error details: {batch_job.errors}")

    except Exception as e:
        print(f"\n--- An unhandled error occurred: {e} ---")

    finally:
        # 7. Cleanup
        print("\n--- Cleaning up all server-side and GCS files... ---")
        if result_file_id:
            try:
                print(f"Deleting result file: {result_file_id}")
                client.files.delete(result_file_id)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting result file: {e}")
        
        if uploaded_request_file:
            try:
                print(f"Deleting request file: {uploaded_request_file.id}")
                client.files.delete(uploaded_request_file.id)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting request file: {e}")

        for blob in blobs:
            try:
                print(f"Deleting blob {blob.name} from bucket {bucket_name}...")
                blob.delete()
                print("  - Blob deleted.")
            except Exception as e:
                print(f"  - Error deleting blob: {e}")
        
        if bucket:
            try:
                print(f"Deleting bucket {bucket_name}...")
                bucket.delete()
                print("  - Bucket deleted.")
            except Exception as e:
                print(f"  - Error deleting bucket: {e}")

        if os.path.exists(LOCAL_OUTPUT_FILE):
            try:
                print(f"Deleting local result file: {LOCAL_OUTPUT_FILE}...")
                os.remove(LOCAL_OUTPUT_FILE)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting local result file: {e}")

        print("Cleanup complete.")

if __name__ == "__main__":
    run_openai_batch_job_with_gcs()
