import warnings
from absl import app, flags
from dotenv import load_dotenv
from provider_factory import get_provider
from logger import set_logging_level, get_logger
from enum import Enum

# Define an Enum for providers to ensure type safety
class Provider(Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

# Define flags
FLAGS = flags.FLAGS
flags.DEFINE_enum("provider", None, [p.value for p in Provider], "The AI provider to use.")
flags.mark_flag_as_required("provider")
flags.DEFINE_integer("num_jobs", 10, "The number of new batch jobs to create.")
flags.DEFINE_boolean("debug", False, "Enable debug logging.")
flags.DEFINE_boolean("create_only", False, "Only create new jobs.")
flags.DEFINE_boolean("check_only", False, "Only check and process jobs.")
flags.DEFINE_string("cancel_job_id", None, "The job ID to cancel.")


logger = get_logger(__name__)

def main(argv):
    # The first argument is the script name, so we ignore it.
    del argv  

    load_dotenv()
    set_logging_level(FLAGS.debug)

    # Suppress the known UserWarning from the google-genai library
    warnings.filterwarnings("ignore", message=".*BATCH_STATE_RUNNING is not a valid JobState.*")

    try:
        provider = get_provider(FLAGS.provider)

        if FLAGS.cancel_job_id:
            logger.info(f"Cancelling job: {FLAGS.cancel_job_id}")
            provider.cancel_job(FLAGS.cancel_job_id)
        elif FLAGS.check_only:
            logger.info(f"Checking status of recent jobs for provider: {FLAGS.provider}")
            provider.check_and_process_jobs()
        elif FLAGS.create_only:
            logger.info(f"Creating {FLAGS.num_jobs} new batch jobs for provider: {FLAGS.provider}")
            created_job_ids = provider.create_jobs(FLAGS.num_jobs)
            logger.info(f"Successfully created job IDs: {created_job_ids}")
        else: # Default behavior: create and then check
            logger.info(f"Creating {FLAGS.num_jobs} new batch jobs for provider: {FLAGS.provider}")
            created_job_ids = provider.create_jobs(FLAGS.num_jobs)
            logger.info(f"Successfully created job IDs: {created_job_ids}")
            
            logger.info(f"Checking status of recent jobs for provider: {FLAGS.provider}")
            provider.check_and_process_jobs()

    except (ValueError, Exception) as e:
        logger.error(f"An error occurred: {e}", exc_info=FLAGS.debug)

if __name__ == "__main__":
    app.run(main)
