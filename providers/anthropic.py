import os
import time
import json
from anthropic import Anthropic
from .base import BatchProvider
from logger import get_logger

logger = get_logger(__name__)

class AnthropicProvider(BatchProvider):
    """Batch processing provider for Anthropic."""

    def _initialize_client(self, api_key):
        return Anthropic(api_key=api_key)

    def create_job(self, prompts):
        anthropic_requests = []
        for p in prompts:
            anthropic_requests.append({
                "custom_id": p["custom_id"],
                "params": {
                    "model": "claude-3-opus-20240229", # A known model
                    "messages": [{"role": "user", "content": p["prompt"]}],
                    "max_tokens": 1024,
                }
            })

        logger.info("Creating Anthropic message batch...")
        # Note: Anthropic's batch API is in beta and might change.
        # It also does not require a separate file upload step.
        job = self.client.beta.messages.batches.create(requests=anthropic_requests)
        logger.info(f"Created batch job: {job.id}")
        logger.debug(f"Initial job object: {job}")

        start_time = time.time()
        while job.processing_status not in ('completed', 'failed', 'cancelled', 'expired', 'ended'):
            logger.info(f"Job not finished. Current status: {job.processing_status}. Waiting 30 seconds...")
            time.sleep(30)
            job = self.client.beta.messages.batches.retrieve(job.id)

        end_time = time.time()
        latency = end_time - start_time
        logger.info(f"Job finished with status: {job.processing_status} in {latency:.2f} seconds.")

        if job.processing_status == 'completed':
            logger.info("Batch job succeeded! Retrieving results...")
            result_stream = self.client.beta.messages.batches.results(job.id)
            
            logger.info("--- Anthropic Batch Log ---")
            for entry in result_stream:
                original_prompt = next((p['prompt'] for p in prompts if p['custom_id'] == entry.custom_id), "N/A")
                logger.info(f"ID: {entry.custom_id}, Prompt: {original_prompt}")
                if entry.result.type == "succeeded":
                    response_text = " ".join([c.text for c in entry.result.message.content if hasattr(c, 'text')])
                    logger.info(f"Response: {response_text.strip()}")
                else:
                    logger.error(f"Request failed with error: {entry.result.error}")
            logger.info("--------------------------")

        performance_result = {
            "provider": "anthropic",
            "job_id": job.id,
            "start_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)),
            "end_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_time)),
            "latency_seconds": round(latency, 2),
            "final_status": job.processing_status,
            "num_requests": len(prompts)
        }
        logger.info("--- Performance Result ---")
        logger.info(json.dumps(performance_result, indent=2))
        logger.info("--------------------------")

        return job

    def list_jobs(self):
        logger.info("Listing recent Anthropic message batches:")
        for job in self.client.beta.messages.batches.list(limit=10):
            logger.info(f"  - {job.id} ({job.processing_status})")

    def cancel_job(self, job_id):
        logger.info(f"Attempting to cancel job: {job_id}")
        cancelled_job = self.client.beta.messages.batches.cancel(job_id)
        logger.info(f"Job {cancelled_job.id} is now {cancelled_job.processing_status}")

    def list_models(self):
        logger.warning("Anthropic model listing is not directly supported via a simple API call.")
        logger.warning("Please refer to the official Anthropic documentation for available models.")
