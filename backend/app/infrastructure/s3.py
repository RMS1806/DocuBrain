"""
app/infrastructure/s3.py

S3-compatible client wrapper (MinIO SDK).
Supports both local MinIO and production AWS S3.
"""

import io
import logging

from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)


def get_s3_client() -> Minio:
    endpoint = settings.S3_ENDPOINT or f"s3.{settings.AWS_REGION}.amazonaws.com"
    is_secure = not any(x in endpoint for x in ("localhost", "minio:9000", "http://"))
    endpoint = endpoint.replace("https://", "").replace("http://", "")

    return Minio(
        endpoint,
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        secure=is_secure,
    )


def upload_bytes_to_s3(
    client: Minio,
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/pdf",
) -> None:
    """Stream bytes directly into S3 without touching disk."""
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_bytes_from_s3(client: Minio, bucket: str, object_name: str) -> bytes:
    """Download an S3 object into memory and return raw bytes."""
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_from_s3(client: Minio, bucket: str, object_name: str) -> None:
    client.remove_object(bucket, object_name)


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create the bucket if it does not already exist. Safe to call on every startup."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket: %s", bucket)
