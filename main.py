import warnings
import os
from datetime import datetime
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

# Define an Enum for actions
class Action(Enum):
    CREATE_JOBS = "create_jobs"
    CHECK_JOBS = "check_jobs"
    CANCEL_JOB = "cancel_job"

# Define flags
FLAGS = flags.FLAGS
flags.DEFINE_enum("provider", None, [p.value for p in Provider], "The AI provider to use.")
flags.mark_flag_as_required("provider")
flags.DEFINE_multi_enum("action", [], [a.value for a in Action], "The action(s) to perform.")
flags.DEFINE_integer("num_jobs", 10, "The number of new batch jobs to create.")
flags.DEFINE_string("job_id", None, "The job ID to cancel.")
flags.DEFINE_boolean("debug", False, "Enable debug logging.")
flags.DEFINE_string("output_file", "job_reports.jsonl", "The file to append job reports to.")


logger = get_logger(__name__)

def main(argv):
    # The first argument is the script name, so we ignore it.
    del argv  

    # Generate a unique output filename with provider and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name, file_extension = os.path.splitext(FLAGS.output_file)
    output_filename = f"{file_name}_{FLAGS.provider}_{timestamp}{file_extension}"

    load_dotenv()
    set_logging_level(FLAGS.debug)

    # Suppress the known UserWarning from the google-genai library
    warnings.filterwarnings("ignore", message=".*BATCH_STATE_RUNNING is not a valid JobState.*")

    try:
        provider = get_provider(FLAGS.provider)

        if not FLAGS.action:
            raise ValueError("You must specify at least one action with the --action flag.")

        if Action.CREATE_JOBS.value in FLAGS.action:
            logger.info(f"Creating {FLAGS.num_jobs} new batch jobs for provider: {FLAGS.provider}")
            created_job_ids = provider.create_jobs(FLAGS.num_jobs)
            logger.info(f"Successfully created job IDs: {created_job_ids}")

        if Action.CHECK_JOBS.value in FLAGS.action:
            logger.info(f"Processing recent jobs for provider: {FLAGS.provider}")
            provider.process_jobs(output_filename)

        if Action.CANCEL_JOB.value in FLAGS.action:
            if not FLAGS.job_id:
                raise ValueError("The --job_id flag is required for the 'cancel_job' action.")
            logger.info(f"Cancelling job: {FLAGS.job_id}")
            provider.cancel_job(FLAGS.job_id)

    except (ValueError, Exception) as e:
        logger.error(f"An error occurred: {e}", exc_info=FLAGS.debug)

if __name__ == "__main__":
    app.run(main)
