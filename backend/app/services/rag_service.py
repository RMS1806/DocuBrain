"""
app/services/rag_service.py

RAG pipeline: embeddings, vector store operations, and LLM streaming.
Moved from app/rag.py. Pinecone client access delegated to infrastructure layer.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Tuple

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError, gemini_breaker, pinecone_breaker
from app.infrastructure.pinecone_client import get_pinecone_index

logger = logging.getLogger(__name__)

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

EMBED_MODEL = "models/gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 100


def _chunk_text(text: str) -> List[str]:
    chunks: List[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start: start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text]


# ── Sync (Celery worker) ──────────────────────────────────────────────────────

def embed_texts_sync(texts: List[str]) -> List[List[float]]:
    import time
    embeddings = []
    for i, text in enumerate(texts):
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="retrieval_document",
            output_dimensionality=768,
        )
        embeddings.append(result["embedding"])
        # Throttle to ~10 req/s to stay well under the free-tier RPM limit
        if i < len(texts) - 1:
            time.sleep(0.1)
    return embeddings


def add_to_vector_store(text: str, metadata: dict) -> None:
    index = get_pinecone_index()
    chunks = _chunk_text(text)
    embeddings = embed_texts_sync(chunks)
    doc_id = metadata.get("doc_id", "x")

    vectors = [
        (f"{doc_id}_{i}", emb, {"text": chunk, **metadata})
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i: i + 100])

    logger.info("Upserted %d chunk(s) for doc_id=%s into Pinecone.", len(chunks), doc_id)


def delete_from_vector_store(doc_id: int) -> None:
    try:
        get_pinecone_index().delete(filter={"doc_id": doc_id})
        logger.info("Purged doc_id=%d from Pinecone.", doc_id)
    except Exception as exc:
        logger.warning("Pinecone delete warning for doc_id=%d: %s", doc_id, exc)


# ── Async (FastAPI routes) ────────────────────────────────────────────────────

async def embed_texts_async(texts: List[str]) -> List[List[float]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_texts_sync, texts)


async def delete_from_vector_store_async(doc_id: int) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, delete_from_vector_store, doc_id)


def _build_prompt(context: str, history_block: str, question: str) -> str:
    return (
        "You are an AI study assistant helping students understand their course material. "
        "Answer based only on the document context provided.\n\n"
        f"--- DOCUMENT CONTEXT ---\n{context}\n\n"
        f"--- CONVERSATION HISTORY ---\n"
        f"{history_block or '(Start of conversation)'}\n\n"
        f"--- CURRENT QUESTION ---\nUser: {question}\n\n"
        "Answer concisely, citing the document context where relevant."
    )


async def stream_rag_response(
    query_text: str,
    history: List[Dict[str, str]],
    user_id: int,
) -> AsyncGenerator[str, None]:
    """
    Embed query → Pinecone similarity search → build prompt → stream Gemini tokens.
    Yields raw token strings, then a final [SOURCES] JSON event.
    """
    loop = asyncio.get_event_loop()

    try:
        q_embedding = (await gemini_breaker.call(lambda: embed_texts_async([query_text])))[0]
    except CircuitOpenError as exc:
        yield str(exc)
        return

    def _pinecone_query():
        return get_pinecone_index().query(
            vector=q_embedding,
            top_k=5,
            include_metadata=True,
            filter={"user_id": user_id},
        )

    try:
        response = await pinecone_breaker.call(lambda: loop.run_in_executor(None, _pinecone_query))
    except CircuitOpenError as exc:
        yield str(exc)
        return

    docs, metadatas = [], []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        metadatas.append(meta)
        if "text" in meta:
            docs.append(meta["text"])

    context_text = "\n\n---\n\n".join(docs) if docs else "No relevant documents found."
    history_block = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in history[:-1]
    ) if len(history) > 1 else ""

    prompt = _build_prompt(context_text, history_block, query_text)
    model = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7, streaming=True)

    async for chunk in model.astream(prompt):
        if chunk.content:
            yield chunk.content

    sources = list({m.get("source", "Unknown") for m in metadatas})
    yield f"\n\n[SOURCES]{json.dumps(sources)}"
