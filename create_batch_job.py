import json
from google import genai
from google.genai import types

import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Create a sample JSONL file
with open("my-batch-requests.jsonl", "w") as f:
    requests = [
        {"key": "request-1", "request": {"contents": [{"parts": [{"text": "Describe the process of photosynthesis."}]}]}},
        {"key": "request-2", "request": {"contents": [{"parts": [{"text": "What are the main ingredients in a Margherita pizza?"}]}]}}
    ]
    for req in requests:
        f.write(json.dumps(req) + "\n")

# Upload the file to the File API
uploaded_file = client.files.upload(
    file='my-batch-requests.jsonl',
    config=types.UploadFileConfig(display_name='my-batch-requests', mime_type='jsonl')
)

print(f"Uploaded file: {uploaded_file.name}")

# Assumes `uploaded_file` is the file object from the previous step
file_batch_job = client.batches.create(
    model="models/gemini-2.5-flash",
    src=uploaded_file.name,
    config={
        'display_name': "file-upload-job-1",
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
        key = result_obj['key']
        response_text = result_obj['response']['candidates'][0]['content']['parts'][0]['text']
        print(f"Key: {key}, Response: {response_text.strip().replace('\n', ' ')}")
    print("-----------------------------")

    # Clean up the uploaded files
    client.files.delete(name=uploaded_file.name)
    client.files.delete(name=os.path.basename(batch_job_inline.dest.file_name))
    print("Cleaned up uploaded files.")
