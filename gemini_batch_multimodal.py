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
import mimetypes
from google import genai as google_genai
from google.genai.types import JobState
from dotenv import load_dotenv

# --- Configuration ---
MODEL_NAME = "models/gemini-2.5-flash-lite"
IMAGE_FILES = ["test_images/image1.jpg", "test_images/image2.jpg"]
LOCAL_REQUEST_FILE = "batch_multimodal_requests.jsonl"
LOCAL_OUTPUT_FILE = "batch_multimodal_results.jsonl"
POLL_INTERVAL_SECONDS = 10

def run_batch_job_v3():
    """Orchestrates the entire API workflow."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")

    client = google_genai.Client(api_key=api_key)

    uploaded_image_files = []
    uploaded_request_file = None
    batch_job = None
    result_file_name = None

    try:
        # 1. Upload image files individually to get their URIs
        print("--- Uploading image assets... ---")
        for image_path in IMAGE_FILES:
            if not os.path.exists(image_path):
                print(f"Warning: Image file not found at {image_path}. Skipping.")
                continue
            print(f"Uploading '{image_path}'...")
            uploaded_file = client.files.upload(file=image_path)
            uploaded_image_files.append(uploaded_file)
            print(f"  - Success! URI: {uploaded_file.uri}")

        if not uploaded_image_files:
            raise ValueError("No images were uploaded. Aborting.")

        # 2. Generate the JSONL request file using the correct file_data format
        print(f"\n--- Generating batch request file: {LOCAL_REQUEST_FILE} ---")
        with open(LOCAL_REQUEST_FILE, "w") as f:
            for i, image_file in enumerate(uploaded_image_files):
                mime_type, _ = mimetypes.guess_type(IMAGE_FILES[i])
                if mime_type is None:
                    mime_type = "application/octet-stream"

                request_data = {
                    "key": f"request-{i}",
                    "request": {
                        "model": MODEL_NAME,
                        "contents": {
                            "parts": [
                                {
                                    "file_data": {
                                        "mime_type": mime_type,
                                        "file_uri": image_file.uri
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
        uploaded_request_file = client.files.upload(
            file=LOCAL_REQUEST_FILE,
            config=google_genai.types.UploadFileConfig(mime_type="application/json")
        )
        print(f"  - Success! URI: {uploaded_request_file.uri}")
        os.remove(LOCAL_REQUEST_FILE)

        # 4. Create the batch job
        print("\n--- Creating batch job... ---")
        batch_job = client.batches.create(
            model=MODEL_NAME,
            src=uploaded_request_file.name,
        )
        print(f"  - Created job: {batch_job.name} with state: {batch_job.state.name}")

        # 5. Poll for completion
        print("\n--- Polling for job completion... ---")
        while batch_job.state not in (JobState.JOB_STATE_SUCCEEDED, JobState.JOB_STATE_FAILED, JobState.JOB_STATE_CANCELLED, JobState.JOB_STATE_EXPIRED):
            time.sleep(POLL_INTERVAL_SECONDS)
            batch_job = client.batches.get(name=batch_job.name)
            print(f"  - Job state: {batch_job.state.name}")

        # 6. Process results
        if batch_job.state == JobState.JOB_STATE_SUCCEEDED:
            print("\n--- Job SUCCEEDED! Downloading and printing results... ---")
            result_file_name = batch_job.dest.file_name
            result_file_bytes = client.files.download(file=result_file_name)
            result_content = result_file_bytes.decode("utf-8")
            
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
            print(f"\n--- Job FAILED or was CANCELLED. Final state: {batch_job.state.name} ---")
            if batch_job.error:
                print(f"Error details: {batch_job.error}")

    except Exception as e:
        print(f"\n--- An unhandled error occurred: {e} ---")

    finally:
        # 7. Cleanup
        print("\n--- Cleaning up all server-side files... ---")
        if batch_job and batch_job.state == JobState.JOB_STATE_SUCCEEDED:
             if result_file_name:
                try:
                    if result_file_name.startswith("files/"):
                        result_file_name = result_file_name[6:]
                    print(f"Deleting result file: {result_file_name}")
                    client.files.delete(name=result_file_name)
                    print("  - Deleted.")
                except Exception as e:
                    print(f"  - Error deleting result file: {e}")
        
        if uploaded_request_file:
            try:
                print(f"Deleting request file: {uploaded_request_file.name}")
                client.files.delete(name=uploaded_request_file.name)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting request file: {e}")

        for img_file in uploaded_image_files:
            try:
                print(f"Deleting image file: {img_file.name}")
                client.files.delete(name=img_file.name)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting image file: {e}")

        if os.path.exists(LOCAL_OUTPUT_FILE):
            try:
                print(f"Deleting local result file: {LOCAL_OUTPUT_FILE}...")
                os.remove(LOCAL_OUTPUT_FILE)
                print("  - Deleted.")
            except Exception as e:
                print(f"  - Error deleting local result file: {e}")
        
        print("Cleanup complete.")

if __name__ == "__main__":
    run_batch_job_v3()
