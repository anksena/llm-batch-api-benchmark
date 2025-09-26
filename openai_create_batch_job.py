import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 1. Prepare the batch file
batch_requests = [
    {
        "custom_id": "request-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 50,
            "temperature": 0.0
        }
    }
]

batch_file_path = "openai-batch-requests.jsonl"
with open(batch_file_path, "w") as f:
    for req in batch_requests:
        f.write(json.dumps(req) + "\n")

print(f"Batch file created at: {batch_file_path}")

# 2. Upload the file
try:
    with open(batch_file_path, "rb") as f:
        batch_file = client.files.create(
            file=f,
            purpose="batch"
        )
    print(f"Uploaded batch file: {batch_file.id}")

    # Clean up local file
    os.remove(batch_file_path)
    print(f"Cleaned up local file: {batch_file_path}")

    # 3. Create the batch job
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    print(f"Created batch job: {batch_job.id}")

    # 4. Check status and wait for completion
    job_id = batch_job.id
    print(f"Polling status for job: {job_id}")
    while True:
        retrieved_job = client.batches.retrieve(job_id)
        if retrieved_job.status in ('completed', 'failed', 'cancelled'):
            break
        print(f"Job not finished. Current status: {retrieved_job.status}. Waiting 30 seconds...")
        time.sleep(30)

    print(f"Job finished with status: {retrieved_job.status}")

    # 5. Retrieve results
    if retrieved_job.status == "completed":
        print("\nBatch job succeeded! Retrieving results...")
        result_file_id = retrieved_job.output_file_id
        result_content = client.files.content(result_file_id).content
        
        # Save and print results
        result_file_path = "openai-batch-results.jsonl"
        with open(result_file_path, "wb") as f:
            f.write(result_content)
        
        print(f"\n--- Batch Results (JSONL) saved to {result_file_path} ---")
        results_str = result_content.decode('utf-8')
        for line in results_str.splitlines():
            result_obj = json.loads(line)
            custom_id = result_obj.get('custom_id')
            response_body = result_obj.get('response', {}).get('body', {})
            content = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"ID: {custom_id}, Response: {content.strip()}")
        print("----------------------------------------------------")

        # Clean up remote files
        client.files.delete(batch_file.id)
        client.files.delete(result_file_id)
        print("Cleaned up remote files.")

except Exception as e:
    print(f"An error occurred: {e}")
    # Clean up local file in case of error
    if os.path.exists(batch_file_path):
        os.remove(batch_file_path)
        print(f"Cleaned up local file: {batch_file_path}")
