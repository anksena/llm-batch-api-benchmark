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

import base64
import json
import mimetypes  # Required to get image media types
import os
import time
from anthropic import Anthropic
from dotenv import load_dotenv
import requests  # Required for uploading/downloading to signed URLs

# --- Configuration ---
# Use a modern Claude 3 model that supports vision
MODEL_NAME = "claude-3-haiku-20240307"
IMAGE_FILES = ["test_images/image1.jpg", "test_images/image2.jpg"]
LOCAL_REQUEST_FILE = "anthropic_batch_multimodal_requests.jsonl"
LOCAL_OUTPUT_FILE = "anthropic_batch_multimodal_results.jsonl"
POLL_INTERVAL_SECONDS = 10


def run_anthropic_batch_job():
  """Orchestrates the entire API workflow."""
  load_dotenv()
  api_key = os.getenv("ANTHROPIC_API_KEY")
  if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")

  client = Anthropic(api_key=api_key)
  try:
    # 1. Generate the JSONL request file with inline image data
    anthropic_requests = []
    print(f"\n--- Generating batch request file: {LOCAL_REQUEST_FILE} ---")
    with open(LOCAL_REQUEST_FILE, "w") as f:
      for i, image_path in enumerate(IMAGE_FILES):
        if not os.path.exists(image_path):
          print(f"Warning: Image file not found at {image_path}. Skipping.")
          continue

        # Get media type (e.g., 'image/jpeg', 'image/png')
        media_type, _ = mimetypes.guess_type(image_path)
        if not media_type or not media_type.startswith("image/"):
          print(
              f"Warning: Could not determine image media type for {image_path}."
              " Skipping."
          )
          continue
        print(f"Image media type: {media_type}")

        with open(image_path, "rb") as image_file:
          base64_image = base64.b64encode(image_file.read()).decode("utf-8")

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
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_image,
                            },
                        },
                    ],
                }],
                "max_tokens": 1024,
            },
        }
        anthropic_requests.append(request_data)
        f.write(json.dumps(request_data) + "\n")
    print("  - Generation complete.")

    # 3. Create the batch job
    print("\n--- Creating batch job... ---")
    batch_job = client.beta.messages.batches.create(requests=anthropic_requests)
    print(
        f"  - Created job: {batch_job.id} with status:"
        f" {batch_job.processing_status}"
    )

    # 4. Poll for completion
    print("\n--- Polling for job completion... ---")
    while batch_job.processing_status in ("starting", "in_progress"):
      time.sleep(POLL_INTERVAL_SECONDS)
      batch_job = client.beta.messages.batches.retrieve(batch_job.id)
      print(f"  - Job status: {batch_job.processing_status}")

    # 5. Process results
    if batch_job.processing_status == "ended" and batch_job.results_url:
      print("\n--- Job COMPLETED! Downloading and printing results... ---")
      response = client.get(batch_job.results_url, cast_to=bytes)
      result_content = response.decode("utf-8").strip()

      print(f"Saving results to {LOCAL_OUTPUT_FILE} and printing.")
      with open(LOCAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(result_content)

      # Parse and print results (format is different from OpenAI)
      for line in result_content.splitlines():
        if not line:
          continue
        result_json = json.loads(line)
        print(f"--- Result for Custom ID: {result_json.get('custom_id')} ---")
        if "result" in result_json and result_json["result"]:
          # The 'result' field contains the full chat completion object
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
    print("\n--- Cleanup ---")
    print(
        "  - Anthropic automatically deletes batch input and output files after"
        " 7 days."
    )
    print("  - No manual file deletion is required.")
    print("Local cleanup complete.")


if __name__ == "__main__":
  run_anthropic_batch_job()
