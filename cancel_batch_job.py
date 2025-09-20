import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def delete_batch_job():
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        # NOTE: You need to replace with the actual job name from the create_batch_job.py output
        job_name = "batches/lhmxamn1yinnrfaiowqpx00uxcs7q7wkag7h"

        print(f"Attempting to delete job: {job_name}")
        client.batches.delete(name=job_name)
        print(f"Successfully deleted job: {job_name}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    delete_batch_job()
