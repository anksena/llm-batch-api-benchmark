"""
Standalone script for running a multimodal batch job with the Gemini API.

This script demonstrates a robust, scalable lifecycle for multimodal batch jobs:
1.  Uploads each image file individually to the File API to get a URI.
2.  Generates a JSONL request file where each request references an image URI
    using the correct `file_data` format.
3.  Uploads the JSONL request file.
4.  Creates the batch job using the uploaded request file.
5.  Polls the job status until it completes.
6.  Downloads and prints the results.
7.  Deletes all uploaded files (images, request file, and result file).
"""

import os
import json
import time
from datetime import datetime, timezone
import mimetypes
from google import genai as google_genai
from google.genai.types import JobState
from google.genai.types import CreateBatchJobConfig

from google.cloud import storage
from dotenv import load_dotenv

# --- Configuration ---
MODEL_NAME = "gemini-2.5-flash-lite"
IMAGE_FILES = ["test_images/image1.jpg", "test_images/image2.jpg"]
LOCAL_REQUEST_FILE = "batch_multimodal_requests.jsonl"
LOCAL_OUTPUT_FILE = "batch_multimodal_results.jsonl"
POLL_INTERVAL_SECONDS = 10

def run_batch_job_v3():
    """Orchestrates the entire API workflow."""
    load_dotenv()
    gcp_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not gcp_project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT not found in .env file")
    gcp_location = os.getenv("GOOGLE_CLOUD_LOCATION")
    if not gcp_location:
        raise ValueError("GOOGLE_CLOUD_LOCATION not found in .env file")

    client = google_genai.Client(vertexai=True, project=gcp_project_id, location=gcp_location)
    gcs_client = storage.Client(project=gcp_project_id)
    
    gcs_input_bucket_name = "llm-batch-api-benchmark-input-bucket"
    gcs_output_bucket_name = "llm-batch-api-benchmark-output-bucket"
    gcs_input_bucket = gcs_client.bucket(gcs_input_bucket_name)
    gcs_output_bucket = gcs_client.bucket(gcs_output_bucket_name)
    gcs_input_prefix = "gemini_batch_src/"

    uploaded_image_file_blobs = []
    uploaded_image_file_uris = []
    request_gcs_blob= None
    request_gcs_uri = None
    batch_job = None
    result_blob_name = None

    try:
        # 1. Upload image files individually to get their URIs
        print("--- Uploading image assets... ---")
        for image_path in IMAGE_FILES:
            if not os.path.exists(image_path):
                print(f"Warning: Image file not found at {image_path}. Skipping.")
                continue
            print(f"Uploading '{image_path}'...")
            gcs_blob = gcs_input_bucket.blob(f"{gcs_input_prefix}{image_path}")
            gcs_blob.upload_from_filename(image_path)
            gcs_uri = f"gs://{gcs_input_bucket_name}/{gcs_blob.name}"
            print(f"  - Success! URI: {gcs_uri}")
            uploaded_image_file_uris.append(gcs_uri)
            uploaded_image_file_blobs.append(gcs_blob.name)

        if not uploaded_image_file_uris:
            raise ValueError("No images were uploaded. Aborting.")

        # 2. Generate the JSONL request file using the correct file_data format
        print(f"\n--- Generating batch request file: {LOCAL_REQUEST_FILE} ---")
        with open(LOCAL_REQUEST_FILE, "w") as f:
            for i, image_file_uri in enumerate(uploaded_image_file_uris):
                mime_type, _ = mimetypes.guess_type(IMAGE_FILES[i])
                if mime_type is None:
                    mime_type = "application/octet-stream"

                request_data = {
                    "key": f"request-{i}",
                    "request": {
                        "model": MODEL_NAME,
                        "contents": {
                            "role": "user",
                            "parts": [
                                {
                                    "file_data": {
                                        "mime_type": mime_type,
                                        "file_uri": image_file_uri
                                    }
                                },
                                {"text": "Caption this image in one sentence."}
                            ]
                        }
                    }
                }
                f.write(json.dumps(request_data) + "\n")
        print("  - Generation complete.")

        # 3. Upload the JSONL request file
        print(f"\n--- Uploading request file... ---")
        gcs_blob = gcs_input_bucket.blob(f"{gcs_input_prefix}{LOCAL_REQUEST_FILE}")
        gcs_blob.upload_from_filename(LOCAL_REQUEST_FILE)
        request_gcs_blob = gcs_blob.name
        request_gcs_uri = f"gs://{gcs_input_bucket_name}/{request_gcs_blob}"
        print(f"  - Success! URI: {request_gcs_uri}")
        os.remove(LOCAL_REQUEST_FILE)

        # 4. Create the batch job
        # Customize a display name and use that name to create unique output path for each job.
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
        display_name = f"vertexai-gemini-batch-job-multimodal-{current_time}"
        output_prefix = display_name
        print("\n--- Creating batch job... ---")
        batch_job = client.batches.create(
            model=MODEL_NAME,
            src=request_gcs_uri,
            config=CreateBatchJobConfig(
                display_name=display_name,
                dest=f"gs://{gcs_output_bucket_name}/{output_prefix}",
            ),
        )
        print(f"  - Created job: {batch_job.name} with state: {batch_job.state.name}")

        # 5. Poll for completion
        print("\n--- Polling for job completion... ---")
        while batch_job.state not in (JobState.JOB_STATE_SUCCEEDED, JobState.JOB_STATE_FAILED, JobState.JOB_STATE_CANCELLED, JobState.JOB_STATE_EXPIRED):
            time.sleep(POLL_INTERVAL_SECONDS)
            batch_job = client.batches.get(name=batch_job.name)
            print(f"  - Job state: {batch_job.state}")

        # 6. Process results
        if batch_job.state == JobState.JOB_STATE_SUCCEEDED:
            print("\n--- Job SUCCEEDED! Downloading and printing results... ---")

            blobs = gcs_output_bucket.list_blobs(prefix=output_prefix)
            
            for blob in blobs:
                if blob.name.endswith("/predictions.jsonl"):
                    result_blob_name = blob.name
                    break
            if not result_blob_name:
              print(
                  "No predictions.jsonl file found for job %s unable to calculate"
                  " total tokens",
                  batch_job.name,
              )
              return None
            blob = gcs_output_bucket.blob(result_blob_name)
            file_content = blob.download_as_bytes()
            result_content = file_content.decode("utf-8").strip()
            
            print(f"Saving results to {LOCAL_OUTPUT_FILE} and printing.")
            with open(LOCAL_OUTPUT_FILE, "w") as f:
                for line in result_content.splitlines():
                    f.write(line + "\n")
                    result_json = json.loads(line)
                    print(f"--- Result for Key: {result_json.get('key')} ---")
                    if 'response' in result_json:
                        print(json.dumps(result_json['response'], indent=2))
                    elif 'error' in result_json:
                        print(f"Error: {result_json['error']}")
        else:
            print(f"\n--- Job FAILED or was CANCELLED. Final state: {batch_job.state} ---")
            if batch_job.error:
                print(f"Error details: {batch_job.error}")

    except Exception as e:
        print(f"\n--- An unhandled error occurred: {e} ---")

    finally:
        # 7. Cleanup
        print("\n--- Cleaning up all server-side files... ---")
        if batch_job and batch_job.state == JobState.JOB_STATE_SUCCEEDED:
             if result_blob_name:
                try:
                    print(f"Deleting result file: {result_blob_name}")
                    gcs_output_bucket.delete_blob(result_blob_name)
                    print("  - Deleted.")
                except Exception as e:
                    print(f"  - Error deleting result file: {e}")
        
        if request_gcs_blob:
            try:
                print(f"Deleting request file: {request_gcs_blob}")
                gcs_blob_request = gcs_input_bucket.blob(request_gcs_blob)
                gcs_input_bucket.delete_blob(gcs_blob_request.name)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting request file: {e}")

        for img_file in uploaded_image_file_blobs:
            try:
                print(f"Deleting image file: {img_file}")
                gcs_blob_img = gcs_input_bucket.blob(img_file)
                gcs_input_bucket.delete_blob(gcs_blob_img.name)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting image file: {e}")
        
        print("Cleanup complete.")

if __name__ == "__main__":
    run_batch_job_v3()
