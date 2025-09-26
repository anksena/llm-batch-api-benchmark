import argparse
from dotenv import load_dotenv
from batch_processor import get_provider

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Batch processing CLI for AI providers.")
    parser.add_argument("provider", choices=["google", "openai"], help="The AI provider to use.")
    parser.add_argument("action", choices=["create", "list", "cancel", "list-models"], help="The action to perform.")
    parser.add_argument("--job_id", help="The job ID to cancel.")

    args = parser.parse_args()

    try:
        provider = get_provider(args.provider)

        if args.action == "create":
            # Define a sample request structure that can be adapted by each provider
            # Define a simple list of prompts to send.
            # The provider will handle formatting the full request.
            sample_prompts = [
                {"custom_id": "request-1", "prompt": "Tell me a short story about a robot who dreams."}
            ]
            provider.create_job(sample_prompts)
        
        elif args.action == "list":
            provider.list_jobs()

        elif args.action == "cancel":
            if not args.job_id:
                print("Error: --job_id is required for the 'cancel' action.")
                return
            provider.cancel_job(args.job_id)

        elif args.action == "list-models":
            provider.list_models()

    except (ValueError, Exception) as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
