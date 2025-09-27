import os
import json
import time
from openai import OpenAI
from .base import BatchProvider

class OpenAIProvider(BatchProvider):
    """Batch processing provider for OpenAI."""

    def _initialize_client(self, api_key):
        return OpenAI(api_key=api_key)

    def create_job(self, prompts):
        # Implementation adapted from openai_create_batch_job.py
        file_path = "openai-batch-requests.jsonl"
        with open(file_path, "w") as f:
            for p in prompts:
                # OpenAI expects 'custom_id', 'method', 'url', and 'body'
                openai_req = {
                    "custom_id": p["custom_id"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "user", "content": p["prompt"]}
                        ]
                    }
                }
                f.write(json.dumps(openai_req) + "\n")

        print(f"OpenAI: Batch file created at {file_path}")
        with open(file_path, "rb") as f:
            batch_file = self.client.files.create(file=f, purpose="batch")
        os.remove(file_path)
        print("OpenAI: Uploaded and cleaned up local file.")

        job = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        print(f"OpenAI: Created batch job: {job.id}")

        while job.status not in ('completed', 'failed', 'cancelled'):
            print(f"OpenAI: Job not finished. Current status: {job.status}. Waiting 30 seconds...")
            time.sleep(30)
            job = self.client.batches.retrieve(job.id)

        print(f"OpenAI: Job finished with status: {job.status}")

        if job.status == 'completed':
            print("OpenAI: Batch job succeeded! Retrieving results...")
            result_file_id = job.output_file_id
            result_content = self.client.files.content(result_file_id).content
            
            print("\n--- OpenAI Batch Log ---")
            results_str = result_content.decode('utf-8')
            for line in results_str.splitlines():
                result_obj = json.loads(line)
                custom_id = result_obj.get('custom_id')
                # Find the original prompt
                original_prompt = next((p['prompt'] for p in prompts if p['custom_id'] == custom_id), "N/A")
                print(f"ID: {custom_id}, Prompt: {original_prompt}")

                response_body = result_obj.get('response', {}).get('body', {})
                content = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"Response: {content.strip()}")
            print("------------------------")

            # Cleanup
            self.client.files.delete(batch_file.id)
            self.client.files.delete(result_file_id)
            print("OpenAI: Cleaned up remote files.")

        elif job.status == 'failed':
            print("OpenAI: Job failed. Retrieving error details...")
            if job.errors and job.errors.data:
                print("--- Error Details ---")
                print(job.errors.data[0])
                print("---------------------")
        
        return job

    def list_jobs(self):
        # Implementation adapted from openai_list_jobs.py
        print("Listing recent OpenAI batch jobs:\n")
        for job in self.client.batches.list(limit=10).data:
            print(f"  - {job.id} ({job.status})")

    def cancel_job(self, job_id):
        # Implementation adapted from openai_cancel_job.py
        print(f"OpenAI: Attempting to cancel job: {job_id}")
        cancelled_job = self.client.batches.cancel(job_id)
        print(f"OpenAI: Job {cancelled_job.id} is now {cancelled_job.status}")

    def list_models(self):
        print("Listing available OpenAI models:\n")
        for model in self.client.models.list().data:
            print(f"- {model.id}")
