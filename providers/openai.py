import os
import json
import time
from openai import OpenAI
from .base import BatchProvider
from logger import get_logger

logger = get_logger(__name__)

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

        logger.debug(f"Batch file created at {file_path}")
        with open(file_path, "rb") as f:
            batch_file = self.client.files.create(file=f, purpose="batch")
        os.remove(file_path)
        logger.debug("Uploaded and cleaned up local file.")

        job = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        logger.info(f"Created batch job: {job.id}")

        start_time = time.time()
        while job.status not in ('completed', 'failed', 'cancelled'):
            logger.debug(f"Job not finished. Current status: {job.status}. Waiting 30 seconds...")
            time.sleep(30)
            job = self.client.batches.retrieve(job.id)

        end_time = time.time()
        latency = end_time - start_time
        logger.info(f"Job finished with status: {job.status} in {latency:.2f} seconds.")

        if job.status == 'completed':
            logger.debug("Batch job succeeded! Retrieving results...")
            result_file_id = job.output_file_id
            result_content = self.client.files.content(result_file_id).content
            
            logger.debug("--- OpenAI Batch Log ---")
            results_str = result_content.decode('utf-8')
            for line in results_str.splitlines():
                logger.debug(f"Raw Response Line: {line}")
                result_obj = json.loads(line)
                custom_id = result_obj.get('custom_id')
                original_prompt = next((p['prompt'] for p in prompts if p['custom_id'] == custom_id), "N/A")
                logger.debug(f"ID: {custom_id}, Prompt: {original_prompt}")

                response_body = result_obj.get('response', {}).get('body', {})
                content = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')
                logger.debug(f"Response: {content.strip()}")
            logger.debug("------------------------")

            # Cleanup
            self.client.files.delete(batch_file.id)
            self.client.files.delete(result_file_id)
            logger.debug("Cleaned up remote files.")

        elif job.status == 'failed':
            logger.error("Job failed. Retrieving error details...")
            if job.errors and job.errors.data:
                logger.error("--- Error Details ---")
                logger.error(job.errors.data[0])
                logger.error("---------------------")
        
        performance_result = {
            "provider": "openai",
            "job_id": job.id,
            "start_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)),
            "end_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_time)),
            "latency_seconds": round(latency, 2),
            "final_status": job.status,
            "num_requests": len(prompts)
        }
        logger.info("--- Performance Result ---")
        logger.info(json.dumps(performance_result, indent=2))
        logger.info("--------------------------")

        return job

    def list_jobs(self):
        logger.info("Listing recent OpenAI batch jobs:")
        for job in self.client.batches.list(limit=10).data:
            logger.info(f"  - {job.id} ({job.status})")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.status}")

    def list_models(self):
        logger.info("Listing available OpenAI models:")
        for model in self.client.models.list().data:
            logger.info(f"- {model.id}")
