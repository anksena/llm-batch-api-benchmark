import json
from google import genai
from google.genai import types

import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Create a sample JSONL file for a single, optimized request
with open("my-batch-requests.jsonl", "w") as f:
    requests = [
        {
            "key": "request-fast",
            "request": {
                "contents": [{"parts": [{"text": "Briefly explain what a CPU is."}]}],
                "generation_config": {
                    "temperature": 0.0,
                    "max_output_tokens": 50
                }
            }
        }
    ]
    for req in requests:
        f.write(json.dumps(req) + "\n")

# Upload the file to the File API
uploaded_file = client.files.upload(
    file='my-batch-requests.jsonl',
    config=types.UploadFileConfig(display_name='my-batch-requests', mime_type='jsonl')
)

print(f"Uploaded file: {uploaded_file.name}")

# Clean up the local requests file now that it's uploaded
if os.path.exists("my-batch-requests.jsonl"):
    os.remove("my-batch-requests.jsonl")
    print("Cleaned up local requests file.")

# Assumes `uploaded_file` is the file object from the previous step
file_batch_job = client.batches.create(
    model="models/gemini-2.5-flash",
    src=uploaded_file.name,
    config={
        'display_name': "optimized-file-upload-job-1",
    },
)

import time

print(f"Created batch job: {file_batch_job.name}")

# wait for the job to finish
job_name = file_batch_job.name
print(f"Polling status for job: {job_name}")

while True:
    batch_job_inline = client.batches.get(name=job_name)
    if batch_job_inline.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED'):
        break
    print(f"Job not finished. Current state: {batch_job_inline.state.name}. Waiting 30 seconds...")
    time.sleep(30)

print(f"Job finished with state: {batch_job_inline.state.name}")

# Download and print the results
if batch_job_inline.state.name == "JOB_STATE_SUCCEEDED":
    print("\nBatch job succeeded! Retrieving results...")
    
    result_file_name = batch_job_inline.dest.file_name
    file_content_bytes = client.files.download(file=result_file_name)
    file_content = file_content_bytes.decode('utf-8')
    
    print("\n--- Batch Results (JSONL) ---")
    for line in file_content.splitlines():
        # Parse each line to show the result and the original key
        result_obj = json.loads(line)
        key = result_obj.get('key')
        response = result_obj.get('response', {})
        candidates = response.get('candidates', [])
        
        if candidates:
            first_candidate = candidates[0]
            content = first_candidate.get('content', {})
            parts = content.get('parts', [])
            finish_reason = first_candidate.get('finishReason')

            if parts and 'text' in parts[0]:
                response_text = parts[0]['text']
                print(f"Key: {key}, Response: {response_text.strip().replace('\n', ' ')}")
            else:
                print(f"Key: {key}, Response: [No text content found], Finish Reason: {finish_reason}")
        else:
            print(f"Key: {key}, Response: [No candidates found in response]")
    print("-----------------------------")

    # Clean up the uploaded files
    client.files.delete(name=uploaded_file.name)
    print("Cleaned up uploaded input file.")
    # NOTE: Deleting the result file is currently failing due to a Gemini API
    # issue where the generated file ID is longer than the allowed 40 characters
    # for the delete endpoint.
    # result_file_id = batch_job_inline.dest.file_name.replace("files/", "")
    # client.files.delete(name=result_file_id)
    # print("Cleaned up result file.")
