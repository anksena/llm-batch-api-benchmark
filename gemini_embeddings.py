"""
Tests the batch embeddings feature for the Google provider.

To run this script:
1. Make sure you have a .env file in the root directory with your GOOGLE_API_KEY.
   Example:
   GOOGLE_API_KEY="your_api_key_here"

2. Run the script from your terminal:
   python gemini_embeddings.py
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# Ensure the GOOGLE_API_KEY environment variable is set.
API_KEY = os.getenv("GOOGLE_API_KEY")

# Sample texts for the batch embedding job
TEXTS = [
    "What is the meaning of life?",
    "How much wood would a woodchuck chuck?",
    "How does the brain work?",
]

def run_test():
    """Initializes the client and runs a batch embedding request."""
    if not API_KEY:
        print("Error: Please set the GOOGLE_API_KEY environment variable.")
        return

    print("Initializing GenAI client...")
    genai.configure(api_key=API_KEY)

    print("\\n--- Creating Batch Embedding Request ---")
    try:
        result = genai.embed_content(
            model="models/embedding-001",
            content=TEXTS,
            task_type="retrieval_document",
            title="Testing batch embeddings"
        )
        print("Successfully created embeddings.")
        print("Embeddings:")
        for embedding in result['embedding']:
            print(f"  - Vector: {embedding[:10]}... (truncated)")

    except Exception as e:
        print(f"An error occurred: {e}")

    print("\\n--- Test Complete ---")


if __name__ == "__main__":
    run_test()
