import os
import json
import time
from google import genai as google_genai
from .base import BatchProvider
from logger import get_logger

logger = get_logger(__name__)

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
        
        logger.info(f"Batch file created at {file_path}")
        uploaded_file = self.client.files.upload(
            file=file_path,
            config=google_genai.types.UploadFileConfig(mime_type="application/jsonl")
        )
        os.remove(file_path)
        logger.info("Uploaded and cleaned up local file.")

        job = self.client.batches.create(
            model="models/gemini-2.5-flash", # Hardcode a known working model
            src=uploaded_file.name,
        )
        logger.info(f"Created batch job: {job.name}")

        start_time = time.time()
        while job.state.name not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            logger.info(f"Job not finished. Current state: {job.state.name}. Waiting 30 seconds...")
            time.sleep(30)
            job = self.client.batches.get(name=job.name)
        
        end_time = time.time()
        latency = end_time - start_time
        logger.info(f"Job finished with state: {job.state.name} in {latency:.2f} seconds.")

        if job.state.name == 'JOB_STATE_SUCCEEDED':
            logger.info("Batch job succeeded! Retrieving results...")
            result_file_name = job.dest.file_name
            file_content_bytes = self.client.files.download(file=result_file_name)
            file_content = file_content_bytes.decode('utf-8')
            
            logger.info("--- Gemini Batch Log ---")
            for line in file_content.splitlines():
                logger.debug(f"Raw Response Line: {line}")
                result_obj = json.loads(line)
                key = result_obj.get('key')
                original_prompt = next((p['prompt'] for p in prompts if p['custom_id'] == key), "N/A")
                logger.info(f"ID: {key}, Prompt: {original_prompt}")

                response = result_obj.get('response', {})
                candidates = response.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts and 'text' in parts[0]:
                        logger.info(f"Response: {parts[0]['text'].strip()}")
                    else:
                        logger.warning(f"Response: [No text content], Finish Reason: {candidates[0].get('finishReason')}")
                else:
                    logger.warning("Response: [No candidates found]")
            logger.info("------------------------")

            # Cleanup
            self.client.files.delete(name=uploaded_file.name)
            logger.info("Cleaned up input file.")
            # NOTE: Skipping result file deletion due to API bug.
        
        performance_result = {
            "provider": "google",
            "job_id": job.name,
            "start_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)),
            "end_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_time)),
            "latency_seconds": round(latency, 2),
            "final_status": job.state.name,
            "num_requests": len(prompts)
        }
        logger.info("--- Performance Result ---")
        logger.info(json.dumps(performance_result, indent=2))
        logger.info("--------------------------")

        return job

    def list_jobs(self):
        logger.info("Listing recent Gemini batch jobs:")
        for job in self.client.batches.list():
            logger.info(f"  - {job.name} ({job.state.name})")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to delete job: {job_id}")
        self.client.batches.delete(name=job_id)
        logger.info(f"Successfully deleted job: {job_id}")

    def list_models(self):
        logger.info("Listing available Gemini models supporting 'batchGenerateContent':")
        for m in self.client.models.list():
            if 'batchGenerateContent' in m.supported_actions:
                logger.info(f"- {m.name}")
