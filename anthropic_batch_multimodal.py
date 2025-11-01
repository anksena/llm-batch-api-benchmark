"""Standalone script for running a multimodal batch job with the Anthropic API.

This script demonstrates a robust, scalable lifecycle for multimodal batch jobs:
1.  Generates a JSONL request file where each request contains inline
    Base64-encoded image data.
2.  Gets a signed URL from the Anthropic Batch API.
3.  Uploads the JSONL request file to the signed URL using 'requests'.
4.  Creates the batch job using the uploaded request file ID.
5.  Polls the job status until it completes.
6.  Downloads and prints the results.
7.  Notes: Anthropic automatically handles file cleanup after 7 days.
"""

import json
import mimetypes
import os
import time
import uuid
from anthropic import Anthropic
from dotenv import load_dotenv
from google.cloud import storage
import requests

# --- Configuration ---
MODEL_NAME = "claude-3-haiku-20240307"
IMAGE_FILES = ["test_images/image1.jpg", "test_images/image2.jpg"]
LOCAL_REQUEST_FILE = "anthropic_batch_multimodal_file_api_requests.jsonl"
LOCAL_OUTPUT_FILE = "anthropic_batch_multimodal_results.jsonl"
POLL_INTERVAL_SECONDS = 10


def run_anthropic_batch_job_with_gcs():
    """Orchestrates the entire API workflow using GCS-hosted images."""
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in .env file")

    client = Anthropic(api_key=api_key)
    storage_client = storage.Client()

    bucket_name = f"anthropic-batch-test-{uuid.uuid4()}"
    bucket = None
    blobs = []
    batch_job = None

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

        # 3. Build the list of requests with public GCS URLs
        print("\n--- Building batch requests... ---")
        anthropic_requests = []
        for i, image_url in enumerate(image_urls):
            request_data = {
                "custom_id": f"request-gcs-{i}",
                "params": {
                    "model": MODEL_NAME,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Caption this image in one sentence.",
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": image_url,
                                },
                            },
                        ],
                    }],
                    "max_tokens": 1024,
                },
            }
            anthropic_requests.append(request_data)
        print("  - Requests built.")

        # 4. Create the batch job directly from the list of requests
        print("\n--- Creating batch job... ---")
        batch_job = client.beta.messages.batches.create(
            requests=anthropic_requests,
        )
        print(
            f"  - Created job: {batch_job.id} with status:"
            f" {batch_job.processing_status}"
        )

        # 5. Poll for completion
        print("\n--- Polling for job completion... ---")
        while batch_job.processing_status in ("starting", "in_progress"):
            time.sleep(POLL_INTERVAL_SECONDS)
            batch_job = client.beta.messages.batches.retrieve(batch_job.id)
            print(f"  - Job status: {batch_job.processing_status}")

        # 6. Process results
        if batch_job.processing_status == "ended" and batch_job.results_url:
            print("\n--- Job COMPLETED! Downloading and printing results... ---")
            response = client.get(batch_job.results_url, cast_to=bytes)
            result_content = response.decode("utf-8").strip()

            print(f"Saving results to {LOCAL_OUTPUT_FILE} and printing.")
            with open(LOCAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(result_content)

            for line in result_content.splitlines():
                if not line:
                    continue
                result_json = json.loads(line)
                print(f"--- Result for Custom ID: {result_json.get('custom_id')} ---")
                if "result" in result_json and result_json["result"]:
                    print(json.dumps(result_json["result"], indent=2))
                elif "error" in result_json and result_json["error"]:
                    print(f"Error: {json.dumps(result_json['error'], indent=2)}")
        else:
            print(
                "\n--- Job FAILED or was CANCELLED. Final status:"
                f" {batch_job.processing_status} ---"
            )
            if batch_job.errors:
                print(f"Error details: {batch_job.errors}")

    except Exception as e:
        print(f"\n--- An unhandled error occurred: {e} ---")

    finally:
        # 7. Cleanup
        print("\n--- Cleaning up GCS resources... ---")
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
    run_anthropic_batch_job_with_gcs()
