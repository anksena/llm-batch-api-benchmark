"""
Standalone script for running a multimodal batch job with the OpenAI API.

This script demonstrates a robust, scalable lifecycle for multimodal batch jobs:
1.  Creates a temporary GCS bucket.
2.  Parses a TSV file to get a list of source image URLs.
3.  Downloads each image to a temporary local file.
4.  Uploads each temporary file to the GCS bucket and makes it public.
5.  Generates a JSONL request file referencing the new public GCS URLs.
6.  Uploads the JSONL request file to OpenAI.
7.  Creates the batch job.
8.  Polls the job status until it completes.
9.  Downloads and prints the results.
10. Deletes all uploaded files (GCS blobs, GCS bucket, and OpenAI files).
"""

import os
import json
import time
import uuid
import csv
import requests
import tempfile
from urllib.parse import urlparse
from openai import OpenAI
from dotenv import load_dotenv
from google.cloud import storage

# --- Configuration ---
MODEL_NAME = "gpt-4o-mini"
IMAGE_URL_LIST_FILE = "multimodal_images_url_list.tsv" # TSV file with source URLs
NUM_IMAGES_TO_PROCESS = 500 # Number of URLs to take from the TSV
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

    gcs_input_bucket_name = "llm-batch-api-benchmark-images"
    gcs_input_bucket = storage_client.bucket(gcs_input_bucket_name)
    bucket = None
    blobs = []
    uploaded_request_file = None
    result_file_id = None

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

        # 4. Generate the JSONL request file with the public GCS URLs
        print(f"\n--- Generating batch request file: {LOCAL_REQUEST_FILE} ---")
        with open(LOCAL_REQUEST_FILE, "w") as f:
            for i, data in enumerate(image_data):
                image_url = data["url"]
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

        # 5. Upload the JSONL request file
        print(f"\n--- Uploading request file... ---")
        with open(LOCAL_REQUEST_FILE, "rb") as f:
            uploaded_request_file = client.files.create(file=f, purpose="batch")
        print(f"  - Success! File ID: {uploaded_request_file.id}")
        os.remove(LOCAL_REQUEST_FILE)

        # 6. Create the batch job
        print("\n--- Creating batch job... ---")
        batch_job = client.batches.create(
            input_file_id=uploaded_request_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        print(f"  - Created job: {batch_job.id} with status: {batch_job.status}")

        # 7. Poll for completion
        print("\n--- Polling for job completion... ---")
        while batch_job.status not in ("completed", "failed", "cancelled", "expired"):
            time.sleep(POLL_INTERVAL_SECONDS)
            batch_job = client.batches.retrieve(batch_job.id)
            print(f"  - Job status: {batch_job.status}")

        # 8. Process results
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
        # 9. Cleanup
        print("\n--- Cleaning up all server-side and GCS files... ---")
        # if result_file_id:
        #     try:
        #         print(f"Deleting result file: {result_file_id}")
        #         client.files.delete(result_file_id)
        #         print("  - Deleted.")
        #     except Exception as e:
        #         print(f"  - Error deleting result file: {e}")
        
                
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