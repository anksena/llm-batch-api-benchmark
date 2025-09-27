import os
import json
import time
from google import genai as google_genai
from .base import BatchProvider

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
