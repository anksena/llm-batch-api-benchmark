import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Listing recent OpenAI batch jobs:\n")

try:
    # Batches are listed in chronological order.
    batches_page = client.batches.list(limit=10)

    for batch_job in batches_page.data:
        print(f"Job ID: {batch_job.id}")
        print(f"  - Status: {batch_job.status}")
        print(f"  - Created At: {batch_job.created_at}")
        if batch_job.input_file_id:
            print(f"  - Input File ID: {batch_job.input_file_id}")
        if batch_job.output_file_id:
            print(f"  - Output File ID: {batch_job.output_file_id}")
        print("-" * 20)

except Exception as e:
    print(f"An error occurred: {e}")
