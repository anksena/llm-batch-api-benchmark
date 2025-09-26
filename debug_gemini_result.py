import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# The job ID from the failed run
job_name = "batches/1xg5a8fjtyi2aw4tu3bk4zbl4tzp5mnd71o6" 

try:
    print(f"Retrieving details for job: {job_name}")
    batch_job_info = client.batches.get(name=job_name)

    if batch_job_info.state.name == "JOB_STATE_SUCCEEDED":
        print("Job succeeded. Downloading result file...")
        result_file_name = batch_job_info.dest.file_name
        print(f"Result file name: {result_file_name}")

        file_content_bytes = client.files.download(file=result_file_name)
        file_content = file_content_bytes.decode('utf-8')

        print("\n--- Raw Result File Content ---")
        print(file_content)
        print("-----------------------------")
    else:
        print(f"Job did not succeed. Final state: {batch_job_info.state.name}")

except Exception as e:
    print(f"An error occurred: {e}")
