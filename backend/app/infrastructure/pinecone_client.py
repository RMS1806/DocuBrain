"""
app/infrastructure/pinecone_client.py

Pinecone vector database client.
Initialised once at import time; index is created if it doesn't exist.
"""

import logging

from pinecone import Pinecone, ServerlessSpec

from app.config import settings

logger = logging.getLogger(__name__)

_pc = None

if settings.PINECONE_API_KEY:
    _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    if settings.PINECONE_INDEX_NAME not in _pc.list_indexes().names():
        logger.info("Creating Pinecone index: %s", settings.PINECONE_INDEX_NAME)
        _pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )


def get_pinecone_index():
    if not _pc:
        raise RuntimeError(
            "Pinecone client is not initialised. Ensure PINECONE_API_KEY is set."
        )
    return _pc.Index(settings.PINECONE_INDEX_NAME)
