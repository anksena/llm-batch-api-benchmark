"""Utility functions for GCS."""

from google.cloud import storage
import sys

GCS_INPUT_BUCKET_NAME = "llm-batch-api-benchmark-images"
GCS_IMAGE_PREFIX = "images/"


def _get_image_blobs():
  storage_client = storage.Client()
  gcs_input_bucket = storage_client.bucket(GCS_INPUT_BUCKET_NAME)
  image_blobs = []
  print(
      f"Listing images from GCS bucket:"
      f" gs://{GCS_INPUT_BUCKET_NAME}/{GCS_IMAGE_PREFIX}",
      file=sys.stderr,
  )
  try:
    blobs = gcs_input_bucket.list_blobs(prefix=GCS_IMAGE_PREFIX)
    for blob in blobs:
      if blob.name == GCS_IMAGE_PREFIX or blob.name.endswith("/"):
        continue
      mime = blob.content_type if blob.content_type else "image/jpeg"
      if not mime.startswith("image/"):
        print(
            f"Skipping non-image file: {blob.name} (MIME: {mime})",
            file=sys.stderr,
        )
        continue
      image_blobs.append(blob)
  except Exception as e:
    print(f"ERROR listing GCS bucket: {e}", file=sys.stderr)
    raise
  return image_blobs


def get_image_urls_from_gcs():
  """Lists images in GCS and returns a list of public URLs."""
  image_blobs = _get_image_blobs()
  image_urls = [blob.public_url for blob in image_blobs]
  print(f"Found {len(image_urls)} images.", file=sys.stderr)

  if not image_urls:
    print("No image URLs found.", file=sys.stderr)
    return []

  image_urls.sort()
  return image_urls


def get_image_gs_links_from_gcs():
  """Lists images in GCS and returns a list of gs:// URIs."""
  image_blobs = _get_image_blobs()
  image_gs_links = [
      f"gs://{blob.bucket.name}/{blob.name}" for blob in image_blobs
  ]
  print(f"Found {len(image_gs_links)} image gs links.", file=sys.stderr)

  if not image_gs_links:
    print("No image gs links found.", file=sys.stderr)
    return []

  image_gs_links.sort()
  return image_gs_links
