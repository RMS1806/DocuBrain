"""
backend/app/s3_client.py

S3-compatible client wrapper bridging MinIO or AWS S3.
Uses `minio-py` to support secure, streaming uploads to object storage.
"""

import os
import io
import logging
from minio import Minio

logger = logging.getLogger(__name__)

def get_s3_client() -> Minio:
    """Initialize and return the MinIO S3 client."""
    s3_endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    # If no S3_ENDPOINT is defined, default to AWS S3 endpoint scheme
    if not s3_endpoint:
        s3_endpoint = f"s3.{region}.amazonaws.com"
        
    is_secure = True
    # Fallback to non-secure if testing against local barebones Minio
    if s3_endpoint and ("localhost" in s3_endpoint or "minio:9000" in s3_endpoint or "http://" in s3_endpoint):
        is_secure = False
        
    # Strip protocol if user included it mistakenly
    s3_endpoint = s3_endpoint.replace("https://", "").replace("http://", "")
        
    client = Minio(
        s3_endpoint,
        access_key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        secure=is_secure
    )
    
    return client
    
def upload_bytes_to_s3(client: Minio, bucket: str, object_name: str, data: bytes, content_type: str = "application/pdf"):
    """Streams pure bytes directly into S3 without hitting disk."""
    data_stream = io.BytesIO(data)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=data_stream,
        length=len(data),
        content_type=content_type
    )

def download_bytes_from_s3(client: Minio, bucket: str, object_name: str) -> bytes:
    """Downloads raw bytes from S3 directly into memory."""
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

def delete_from_s3(client: Minio, bucket: str, object_name: str):
    """Deletes an object from S3."""
    client.remove_object(bucket, object_name)
