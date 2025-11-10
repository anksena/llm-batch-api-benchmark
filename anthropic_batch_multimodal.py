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
import csv
from anthropic import Anthropic
from dotenv import load_dotenv
from google.cloud import storage
import requests

# --- Configuration ---
MODEL_NAME = "claude-3-haiku-20240307"
IMAGE_URL_LIST_FILE = "multimodal-images-url-list.tsv"
NUM_IMAGES_TO_PROCESS = 500 # Number of URLs to take from the TSV
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
    
    gcs_input_bucket_name = "llm-batch-api-benchmark-images"
    gcs_input_bucket = storage_client.bucket(gcs_input_bucket_name)
    bucket = None
    blobs = []
    batch_job = None

    try:
        # 1. List images in GCS bucket to get gs:// URIs
        print(f"\n--- Listing up to {NUM_IMAGES_TO_PROCESS} images from GCS: gs://{gcs_input_bucket_name}/images/ ---")
        image_data = [] # Will store {"url": ..., "mime": ...}
        gcs_image_prefix = "images/"
        try:
            blobs = gcs_input_bucket.list_blobs(prefix=gcs_image_prefix, max_results=NUM_IMAGES_TO_PROCESS)
            for blob in blobs:
                # Skip the "folder" placeholder object itself
                if blob.name == gcs_image_prefix or blob.name.endswith('/'):
                    continue
                
                # Get MIME type, default to jpeg if unknown
                mime = blob.content_type
                if not mime:
                    mime = "image/jpeg" # Default if not set
                if not mime.startswith("image/"):
                    print(f"  - WARNING: Skipping non-image file: {blob.name} (MIME: {mime})")
                    continue
                image_data.append({
                    "url": blob.public_url,
                    "mime": mime
                })

            print(f"  - Found {len(image_data)} images to process.")
            if not image_data:
                raise ValueError("No images found in GCS bucket/prefix. Exiting.")
        except Exception as e:
            print(f"  - ERROR listing GCS bucket: {e}")
            raise
        # Check if any images were successfully processed
        if not image_data:
            raise ValueError("No images were successfully found. Aborting job.")

        # 3. Build the list of requests with public GCS URLs
        print("\n--- Building batch requests... ---")
        anthropic_requests = []
        for i, data in enumerate(image_data):
            image_url = data["url"]
            print(f"Building request {i} with image URL: {image_url}")
            request_data = {
                "custom_id": f"request-{i}",
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
        print("\n--- Cleaning up... ---")
        print("Cleanup complete.")


if __name__ == "__main__":
    run_anthropic_batch_job_with_gcs()
