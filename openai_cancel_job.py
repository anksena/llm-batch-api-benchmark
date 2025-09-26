import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def cancel_openai_batch_job():
    try:
        # NOTE: You need to replace this with an actual batch job ID
        job_id_to_cancel = "batch_abc123" 

        print(f"Attempting to cancel job: {job_id_to_cancel}")
        cancelled_job = client.batches.cancel(job_id_to_cancel)
        print(f"Successfully sent cancellation request for job: {cancelled_job.id}")
        print(f"Current status: {cancelled_job.status}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    cancel_openai_batch_job()
