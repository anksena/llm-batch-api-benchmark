import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

print("Listing recent batch jobs:\n")

# Note: The list API currently doesn't return inlined_responses.
# As a workaround,you can make a `get` call for inline jobs to see their results.
batches = client.batches.list(config={'page_size': 10})

for b in batches.page:
    print(f"Job Name: {b.name}")
    print(f"  - Display Name: {b.display_name}")
    print(f"  - State: {b.state.name}")
    print(f"  - Create Time: {b.create_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check if it was an inline job (no destination file)
    if b.dest is not None:
      if not b.dest.file_name:
        full_job = client.batches.get(name=b.name)
        if full_job.inlined_responses:
            print("  - Type: Inline ({} responses)".format(len(full_job.inlined_responses)))
      else:
          print(f"  - Type: File-based (Output: {b.dest.file_name})")

    print("-" * 20)
