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

# Define an Enum for actions
class Action(Enum):
    CREATE = "create"
    LIST = "list"
    CANCEL = "cancel"
    LIST_MODELS = "list-models"

# Define flags
FLAGS = flags.FLAGS
flags.DEFINE_enum("provider", None, [p.value for p in Provider], "The AI provider to use.")
flags.mark_flag_as_required("provider")
flags.DEFINE_enum("action", None, [a.value for a in Action], "The action to perform.")
flags.mark_flag_as_required("action")
flags.DEFINE_string("job_id", None, "The job ID to cancel.")
flags.DEFINE_boolean("debug", False, "Enable debug logging.")

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

        if FLAGS.action == Action.CREATE.value:
            logger.info(f"Starting 'create' action for provider: {FLAGS.provider}")
            sample_prompts = [
                {"custom_id": "request-1", "prompt": "Tell me a short story about a robot who dreams."}
            ]
            provider.create_job(sample_prompts)
        
        elif FLAGS.action == Action.LIST.value:
            logger.info(f"Starting 'list' action for provider: {FLAGS.provider}")
            provider.list_jobs()

        elif FLAGS.action == Action.CANCEL.value:
            if not FLAGS.job_id:
                logger.error("--job_id is required for the 'cancel' action.")
                return
            logger.info(f"Starting 'cancel' action for provider: {FLAGS.provider} on job: {FLAGS.job_id}")
            provider.cancel_job(FLAGS.job_id)

        elif FLAGS.action == Action.LIST_MODELS.value:
            logger.info(f"Starting 'list-models' action for provider: {FLAGS.provider}")
            provider.list_models()

    except (ValueError, Exception) as e:
        logger.error(f"An error occurred: {e}", exc_info=FLAGS.debug)

if __name__ == "__main__":
    app.run(main)
