import warnings
import os
import json
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
    CHECK_RECENT_JOBS = "check_recent_jobs"
    CHECK_SINGLE_JOB = "check_single_job"
    CHECK_JOBS_FROM_FILE = "check_jobs_from_file"
    CANCEL_JOB = "cancel_job"

# Define flags
FLAGS = flags.FLAGS
flags.DEFINE_enum("provider", None, [p.value for p in Provider], "The AI provider to use.")
flags.mark_flag_as_required("provider")
flags.DEFINE_multi_enum("action", [], [a.value for a in Action], "The action(s) to perform.")
flags.DEFINE_integer("num_jobs", 10, "The number of new batch jobs to create.")
flags.DEFINE_integer("hours_ago", 36, "The number of hours ago to check for recent jobs.")
flags.DEFINE_string("job_id", None, "The job ID to cancel.")
flags.DEFINE_string("state_file", None, "The path to the state file to process.")
flags.DEFINE_boolean("debug", False, "Enable debug logging.")
flags.DEFINE_string("output_file", "job_reports.jsonl", "The file to append job reports to.")


logger = get_logger(__name__)

def main(argv):
    # The first argument is the script name, so we ignore it.
    del argv  

    # Generate a unique output filename with provider and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{FLAGS.provider}_job_reports_{timestamp}.jsonl"

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

            # Design Rationale:
            # We generate reports in a separate step to adhere to the Single Responsibility
            # Principle. The `create_jobs` method is solely responsible for creating jobs,
            # while `generate_job_report_for_user` is responsible for fetching and
            # formatting reports. This promotes modularity and code reuse.
            logger.info(f"Generating reports for new jobs and saving to {output_filename}")
            with open(output_filename, "a") as f_out:
                for job_id in created_job_ids:
                    report = provider.generate_job_report_for_user(job_id)
                    if report:
                        report_json = report.to_json()
                        print(report_json)
                        f_out.write(report_json + "\n")

        if Action.CHECK_RECENT_JOBS.value in FLAGS.action:
            logger.info(f"Checking jobs from the last {FLAGS.hours_ago} hours for provider: {FLAGS.provider}")
            provider.check_recent_jobs(output_filename, FLAGS.hours_ago)

        if Action.CHECK_SINGLE_JOB.value in FLAGS.action:
            if not FLAGS.job_id:
                raise ValueError("The --job_id flag is required for the 'check_single_job' action.")
            logger.info(f"Checking status of job: {FLAGS.job_id}")
            provider.generate_job_report_for_user(FLAGS.job_id)

        if Action.CHECK_JOBS_FROM_FILE.value in FLAGS.action:
            if not FLAGS.state_file:
                raise ValueError("The --state_file flag is required for the 'check_jobs_from_file' action.")
            logger.info(f"Checking jobs from file: {FLAGS.state_file}")
            provider.check_jobs_from_file(FLAGS.state_file, output_filename)

        if Action.CANCEL_JOB.value in FLAGS.action:
            if not FLAGS.job_id:
                raise ValueError("The --job_id flag is required for the 'cancel_job' action.")
            logger.info(f"Cancelling job: {FLAGS.job_id}")
            provider.cancel_job(FLAGS.job_id)

    except (ValueError, Exception) as e:
        logger.error(f"An error occurred: {e}", exc_info=FLAGS.debug)

if __name__ == "__main__":
    app.run(main)
