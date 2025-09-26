import os
import json
import time
from abc import ABC, abstractmethod
from google import genai as google_genai
from openai import OpenAI

class BatchProvider(ABC):
    """Abstract base class for a batch processing provider."""

    def __init__(self, api_key):
        self.client = self._initialize_client(api_key)

    @abstractmethod
    def _initialize_client(self, api_key):
        """Initializes the provider-specific API client."""
        pass

    @abstractmethod
    def create_job(self, requests):
        """Creates and monitors a batch job."""
        pass

    @abstractmethod
    def list_jobs(self):
        """Lists recent batch jobs."""
        pass

    @abstractmethod
    def cancel_job(self, job_id):
        """Cancels a batch job."""
        pass

    @abstractmethod
    def list_models(self):
        """Lists available models."""
        pass

class GoogleProvider(BatchProvider):
    """Batch processing provider for Google."""

    def _initialize_client(self, api_key):
        return google_genai.Client(api_key=api_key)

    def create_job(self, prompts):
        # Implementation adapted from gemini_create_batch_job.py
        file_path = "gemini-batch-requests.jsonl"
        with open(file_path, "w") as f:
            for p in prompts:
                # Gemini expects 'key' and 'request' structure
                gemini_req = {
                    "key": p["custom_id"], 
                    "request": {
                        "contents": [{"parts": [{"text": p["prompt"]}]}]
                    }
                }
                f.write(json.dumps(gemini_req) + "\n")
        
        print(f"Gemini: Batch file created at {file_path}")
        uploaded_file = self.client.files.upload(
            file=file_path,
            config=google_genai.types.UploadFileConfig(mime_type="application/jsonl")
        )
        os.remove(file_path)
        print("Gemini: Uploaded and cleaned up local file.")

        job = self.client.batches.create(
            model="models/gemini-2.5-flash", # Hardcode a known working model
            src=uploaded_file.name,
        )
        print(f"Gemini: Created batch job: {job.name}")

        while job.state.name not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            print(f"Gemini: Job not finished. Current state: {job.state.name}. Waiting 30 seconds...")
            time.sleep(30)
            job = self.client.batches.get(name=job.name)
        
        print(f"Gemini: Job finished with state: {job.state.name}")

        if job.state.name == 'JOB_STATE_SUCCEEDED':
            print("Gemini: Batch job succeeded! Retrieving results...")
            result_file_name = job.dest.file_name
            file_content_bytes = self.client.files.download(file=result_file_name)
            file_content = file_content_bytes.decode('utf-8')
            
            print("\n--- Gemini Batch Log ---")
            for line in file_content.splitlines():
                print("\n--- Raw Response Line ---")
                print(line)
                print("------------------------")
                result_obj = json.loads(line)
                key = result_obj.get('key')
                # Find the original prompt
                original_prompt = next((p['prompt'] for p in prompts if p['custom_id'] == key), "N/A")
                print(f"ID: {key}, Prompt: {original_prompt}")

                response = result_obj.get('response', {})
                candidates = response.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts and 'text' in parts[0]:
                        print(f"Response: {parts[0]['text'].strip()}")
                    else:
                        print(f"Response: [No text content], Finish Reason: {candidates[0].get('finishReason')}")
                else:
                    print("Response: [No candidates found]")
            print("------------------------")

            # Cleanup
            self.client.files.delete(name=uploaded_file.name)
            print("Gemini: Cleaned up input file.")
            # NOTE: Skipping result file deletion due to API bug.
        
        return job

    def list_jobs(self):
        # Implementation adapted from gemini_list_jobs.py
        print("Listing recent Gemini batch jobs:\n")
        for job in self.client.batches.list():
            print(f"  - {job.name} ({job.state.name})")

    def cancel_job(self, job_id):
        # Implementation adapted from gemini_cancel_batch_job.py
        print(f"Gemini: Attempting to delete job: {job_id}")
        self.client.batches.delete(name=job_id)
        print(f"Gemini: Successfully deleted job: {job_id}")

    def list_models(self):
        print("Listing available Gemini models supporting 'batchGenerateContent':\n")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                print(f"- {m.name}")


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
        # Implementation adapted from openai_cancel_batch_job.py
        print(f"OpenAI: Attempting to cancel job: {job_id}")
        cancelled_job = self.client.batches.cancel(job_id)
        print(f"OpenAI: Job {cancelled_job.id} is now {cancelled_job.status}")

    def list_models(self):
        print("Listing available OpenAI models:\n")
        for model in self.client.models.list().data:
            print(f"- {model.id}")

def get_provider(provider_name):
    if provider_name.lower() == "google":
        api_key = os.getenv("GEMINI_API_KEY")
        return GoogleProvider(api_key)
    elif provider_name.lower() == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        return OpenAIProvider(api_key)
    else:
        raise ValueError("Unsupported provider. Choose 'gemini' or 'openai'.")
