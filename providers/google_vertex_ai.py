"""Batch processing provider for Google."""

from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import os
from absl import flags
from data_models import JobReport, ServiceReportedJobDetails, UserStatus
from google import genai as google_genai
from google.cloud import storage
from google.genai.types import CreateBatchJobConfig
from logger import get_logger
from .base import BatchProvider


class GoogleVertexAiJobStatus(Enum):
  JOB_STATE_PENDING = "JOB_STATE_PENDING"
  JOB_STATE_RUNNING = "JOB_STATE_RUNNING"
  JOB_STATE_SUCCEEDED = "JOB_STATE_SUCCEEDED"
  JOB_STATE_FAILED = "JOB_STATE_FAILED"
  JOB_STATE_CANCELLED = "JOB_STATE_CANCELLED"
  JOB_STATE_EXPIRED = "JOB_STATE_EXPIRED"
  JOB_STATE_UNSPECIFIED = "JOB_STATE_UNSPECIFIED"
  JOB_STATE_QUEUED = "JOB_STATE_QUEUED"
  JOB_STATE_CANCELLING = "JOB_STATE_CANCELLING"
  JOB_STATE_PAUSED = "JOB_STATE_PAUSED"
  JOB_STATE_UPDATING = "JOB_STATE_UPDATING"
  JOB_STATE_PARTIALLY_SUCCEEDED = "JOB_STATE_PARTIALLY_SUCCEEDED"


logger = get_logger(__name__)


class GoogleVertexAiProvider(BatchProvider):
  """Batch processing provider for Google."""

  MODEL_NAME = "gemini-2.5-flash-lite"

  GCS_INPUT_PREFIX = "gemini_batch_src/"

  def __init__(self, api_key):

    self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
    self.location = os.getenv("GOOGLE_CLOUD_LOCATION")
    self.gcs_client = storage.Client(project=self.project)
    FLAGS = flags.FLAGS
    if (
        not FLAGS.vertex_ai_gcs_input_bucket_name
        or not FLAGS.vertex_ai_gcs_output_bucket_name
    ):
      raise ValueError(
          "Both --vertex_ai_gcs_input_bucket_name and"
          " --vertex_ai_gcs_output_bucket_name are required for GoogleVertexAi"
          " provider."
      )

    self.gcs_input_bucket_name = FLAGS.vertex_ai_gcs_input_bucket_name
    self.gcs_output_bucket_name = FLAGS.vertex_ai_gcs_output_bucket_name

    self.gcs_input_bucket = self.gcs_client.bucket(self.gcs_input_bucket_name)
    self.gcs_output_bucket = self.gcs_client.bucket(self.gcs_output_bucket_name)
    super().__init__(api_key)

  @property
  def _job_status_enum(self):
    return GoogleVertexAiJobStatus

  @property
  def _job_status_attribute(self):
    return "state.name"

  def _initialize_client(self, api_key):
    return google_genai.Client(
        vertexai=True, project=self.project, location=self.location
    )

  def _create_single_batch_job(
      self, job_index: int, total_jobs: int, prompts: list[str]
  ) -> str:
    file_path = f"gemini-batch-request-{job_index}.jsonl"
    with open(file_path, "w", encoding="utf-8") as f:
      for i, prompt in enumerate(prompts):
        gemini_req = {
            "key": f"request-{i}",
            "request": {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generation_config": {"max_output_tokens": self.MAX_TOKENS},
            },
        }
        f.write(json.dumps(gemini_req) + "\n")

    gcs_blob = self.gcs_input_bucket.blob(f"{self.GCS_INPUT_PREFIX}{file_path}")
    gcs_blob.upload_from_filename(file_path)
    os.remove(file_path)

    input_data = (
        f"gs://{self.gcs_input_bucket_name}/{self.GCS_INPUT_PREFIX}{file_path}"
    )
    # Customize a display name and use that name to create unique output path for each job.
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    display_name = f"vertexai-gemini-batch-job-{job_index}-{current_time}"
    output_prefix = display_name
    job = self.client.batches.create(
        model=self.MODEL_NAME,
        src=input_data,
        config=CreateBatchJobConfig(
            display_name=display_name,
            dest=f"gs://{self.gcs_output_bucket_name}/{output_prefix}",
        ),
    )
    logger.info(
        "Created batch job %d/%d: %s", job_index + 1, total_jobs, job.name
    )
    return job.name

  def _get_job_list(self, hours_ago):
    all_jobs = []
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    for job in self.client.batches.list(config={"page_size": 10}):
      if job.create_time < time_threshold:
        break
      all_jobs.append(job)
    return all_jobs

  def _get_job_create_time(self, job):
    return job.create_time

  def _create_report_from_provider_job(self, job):
    latency = None
    if job.state.name == "JOB_STATE_SUCCEEDED" and job.end_time:
      latency = round((job.end_time - job.create_time).total_seconds(), 2)

    status = ServiceReportedJobDetails(
        job_id=job.name,
        model=job.model,
        service_job_status=job.state.name,
        created_at=job.create_time.isoformat(),
        ended_at=job.end_time.isoformat() if job.end_time else None,
    )

    if job.state.name == "JOB_STATE_SUCCEEDED":
      user_status = UserStatus.SUCCEEDED
    elif job.state.name == "JOB_STATE_CANCELLED":
      if job.end_time and (job.end_time - job.create_time) > timedelta(days=1):
        user_status = UserStatus.CANCELLED_TIMED_OUT
      else:
        user_status = UserStatus.CANCELLED_ON_DEMAND
    elif (
        job.state.name == "JOB_STATE_FAILED"
        or job.state.name == "JOB_STATE_PARTIALLY_SUCCEEDED"
    ):
      user_status = UserStatus.FAILED
    elif job.state.name == "JOB_STATE_EXPIRED":
      user_status = UserStatus.CANCELLED_TIMED_OUT
    elif job.state.name == "JOB_STATE_CANCELLING":
      if self._should_cancel_for_timeout(job.create_time):
        user_status = UserStatus.CANCELLED_TIMED_OUT
      else:
        user_status = UserStatus.CANCELLED_ON_DEMAND
    elif job.state.name in (
        "JOB_STATE_PENDING",
        "JOB_STATE_RUNNING",
        "JOB_STATE_UNSPECIFIED",
        "JOB_STATE_QUEUED",
        "JOB_STATE_PAUSED",
        "JOB_STATE_UPDATING",
    ):
      if self._should_cancel_for_timeout(job.create_time):
        user_status = UserStatus.CANCELLED_TIMED_OUT
        logger.warning("Job %s has timed out. Cancelling...", job.name)
        self.cancel_job(job.name)
      else:
        user_status = UserStatus.IN_PROGRESS
    else:
      raise ValueError(f"Unexpected job status: {job.state.name}")

    total_tokens = None
    if user_status == UserStatus.SUCCEEDED:
      total_tokens = self._calculate_total_tokens(job)

    return JobReport(
        provider="google_vertex_ai",
        job_id=job.name,
        user_assigned_status=user_status,
        latency_seconds=latency,
        total_tokens=total_tokens,
        service_reported_details=status,
    )

  def cancel_job(self, job_id):
    logger.info(
        "Attempting to delete job (Google's equivalent of cancel): %s", job_id
    )
    self.client.batches.delete(name=job_id)
    logger.info("Successfully sent delete request for job: %s", job_id)

  def get_job_details_from_provider(self, job_id):
    return self.client.batches.get(name=job_id)

  def get_provider_name(self):
    return "google_vertex_ai"

  def _calculate_total_tokens(self, job):
    """Downloads the result file and calculates the total tokens used."""
    total_tokens = 0
    if (
        job.state.name == "JOB_STATE_SUCCEEDED"
        and job.display_name
        and job.dest
    ):
      try:
        logger.info(
            "Downloading result file for job %s, display_name(which is also prefix): %s",
            job.name,
            job.display_name,
        )
        # Vertex AI Batch API creates subdirectories under provided prefix 
        # so we need to list and search the result file
        blobs = self.gcs_output_bucket.list_blobs(prefix=job.display_name)
        blob_name = None
        for blob in blobs:
          if blob.name.endswith("/predictions.jsonl"):
            blob_name = blob.name
            break
        if not blob_name:
          logger.warning(
              "No predictions.jsonl file found for job %s unable to calculate"
              " total tokens",
              job.name,
          )
          return None
        blob = self.gcs_output_bucket.blob(blob_name)
        file_content = blob.download_as_bytes()
        content_str = file_content.decode("utf-8").strip()
        # The result file contains one JSON object per line
        for line in content_str.splitlines():
          if not line:
            continue
          try:
            result = json.loads(line)
            if "response" in result and "usageMetadata" in result["response"]:
              total_tokens += result["response"]["usageMetadata"].get(
                  "totalTokenCount", 0
              )
          except json.JSONDecodeError:
            logger.warning("Could not decode JSON line: %s", line)

        logger.info(
            "Total tokens calculated for job %s: %d", job.name, total_tokens
        )
        return total_tokens
      except Exception as e:
        logger.error("Error calculating tokens for job %s: %s", job.name, e)
    return None

  def download_results(self, job, output_file):
    """Downloads the results of a completed batch job.

    Args:
        job: The provider-specific job object.
        output_file: The path to the output file to save the results to.
    """
    if job.state.name == "JOB_STATE_SUCCEEDED":
      if job.dest and job.dest.file_name:
        result_file_name = job.dest.file_name
        logger.info("Results are in file: %s", result_file_name)
        logger.info("Downloading result file content...")
        file_content = self.client.files.download(file=result_file_name)
        with open(output_file, "wb") as f:
          f.write(file_content)
        logger.info("Successfully downloaded results to %s", output_file)
      else:
        logger.info("No results file found for job %s", job.name)
    else:
      logger.warning(
          "Job %s did not succeed. Final state: %s", job.name, job.state.name
      )
