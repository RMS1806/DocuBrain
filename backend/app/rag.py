"""
backend/app/rag.py

Enterprise-grade async RAG pipeline.

Key changes from the prototype:
  - HuggingFace sentence-transformers REMOVED — was blocking the event loop for
    200-800 ms per call. Now uses Google Gemini Embeddings API (async HTTP).
  - Pinecone Cloud Vector DB replaced ChromaDB to resolve out-of-memory errors
    and support a stateless load-balanced backend architecture.
  - query_rag_with_history() is now an AsyncGenerator that yields LLM tokens
    the exact moment they arrive (true SSE streaming; TTFT < 200 ms).
  - Sync variants kept for the Celery worker (separate OS process, no event loop).
"""

import asyncio
import logging
import os
import json
from typing import AsyncGenerator, Dict, List, Tuple

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

# ── Gemini client config ───────────────────────────────────────────────────────
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if _GEMINI_API_KEY:
    genai.configure(api_key=_GEMINI_API_KEY)

EMBED_MODEL = "models/gemini-embedding-001"   # Updated to current active model
CHAT_MODEL  = "gemini-2.5-flash"

# ── Pinecone client config ────────────────────────────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "docubrain-index")

pc = None
if PINECONE_API_KEY:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Initialize index if it doesn't exist
    if PINECONE_INDEX_NAME not in pc.list_indexes().names():
        logger.info(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )

def _get_pinecone_index():
    if not pc:
        raise ValueError("Pinecone client is not initialized. Please set PINECONE_API_KEY .env variable.")
    return pc.Index(PINECONE_INDEX_NAME)

# Text chunking parameters for vectorisation
CHUNK_SIZE    = 1500   # characters per chunk
CHUNK_OVERLAP = 100    # overlap between consecutive chunks

# ── Text chunking ─────────────────────────────────────────────────────────────
def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split *text* into overlapping fixed-size character chunks."""
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks or [text]

# ── Gemini Embeddings — Sync (Celery worker) ───────────────────────────────────
def get_gemini_embeddings_sync(texts: List[str]) -> List[List[float]]:
    """
    Synchronous Gemini embedding call — safe to use from Celery workers.
    One API call per text (Gemini's batch limit is 1 per request in free tier).
    """
    embeddings = []
    for text in texts:
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="retrieval_document",
            output_dimensionality=768
        )
        embeddings.append(result["embedding"])
    return embeddings

# ── Gemini Embeddings — Async (FastAPI) ───────────────────────────────────────
async def get_gemini_embeddings_async(texts: List[str]) -> List[List[float]]:
    """
    Async wrapper — runs the blocking Gemini SDK call in a thread executor
    so the FastAPI event loop is never stalled.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_gemini_embeddings_sync, texts)


# ─────────────────────────────────────────────────────────────────────────────
# SYNC API  (used by Celery docubrain_tasks.py worker)
# ─────────────────────────────────────────────────────────────────────────────

def add_text_to_vector_store(text: str, metadata: dict) -> None:
    """
    Chunk *text*, embed each chunk via Gemini, and upsert into Pinecone.
    Runs synchronously — correct for the Celery worker process.
    """
    index = _get_pinecone_index()
    chunks = _chunk_text(text)
    embeddings = get_gemini_embeddings_sync(chunks)

    doc_id = metadata.get('doc_id', 'x')
    
    # Prepare vectors for Pinecone format
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{doc_id}_{i}"
        
        # Include the original text chunk in the metadata so we can retrieve it for RAG
        vector_metadata = {"text": chunk}
        vector_metadata.update(metadata)
        
        vectors.append((vector_id, embedding, vector_metadata))

    # Batch upsert to Pinecone
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        
    logger.info(
        "✅ Upserted %d chunk(s) for doc_id=%s into Pinecone.",
        len(chunks), doc_id,
    )


def query_rag(query_text: str, user_id: int) -> Tuple[str, List[str]]:
    """
    Synchronous single-shot RAG query.
    Left for backward compatibility; prefer async_query_rag in FastAPI routes.
    """
    index = _get_pinecone_index()
    q_embedding = get_gemini_embeddings_sync([query_text])[0]

    response = index.query(
        vector=q_embedding,
        top_k=5,
        include_metadata=True,
        filter={"user_id": user_id}
    )

    docs = []
    metadatas = []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        metadatas.append(meta)
        if "text" in meta:
            docs.append(meta["text"])

    if not docs:
        return "No relevant information found in the specified documents.", []

    context_text = "\n\n---\n\n".join(docs)
    prompt = (
        f"Answer the question based only on the following context:\n{context_text}\n\n"
        f"---\nAnswer the question based on the above context: {query_text}"
    )
    model    = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7)
    answer = model.invoke(prompt)
    sources  = list({m.get("source", "Unknown") for m in metadatas})
    return answer.content, sources


def query_rag_with_history(
    query_text: str,
    history: List[Dict[str, str]],
    user_id: int,
) -> Tuple[str, List[str]]:
    """
    Synchronous history-aware RAG query (Celery / legacy callers only).
    """
    index = _get_pinecone_index()
    q_embedding = get_gemini_embeddings_sync([query_text])[0]

    response = index.query(
        vector=q_embedding,
        top_k=5,
        include_metadata=True,
        filter={"user_id": user_id}
    )
    
    docs = []
    metadatas = []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        metadatas.append(meta)
        if "text" in meta:
            docs.append(meta["text"])
            
    context_text = "\n\n---\n\n".join(docs) if docs else "No relevant documents found."
    sources      = list({m.get("source", "Unknown") for m in metadatas}) if metadatas else []

    history_block = ""
    if len(history) > 1:
        history_block = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history[:-1]
        )

    prompt = _build_rag_prompt(context_text, history_block, query_text)
    model    = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7)
    answer = model.invoke(prompt)
    return answer.content, sources


def delete_from_vector_store(doc_id: int) -> None:
    """
    Delete all Pinecone entries whose metadata has doc_id == *doc_id*.
    Does NOT load the embedding model — just a direct metadata filter delete.
    """
    try:
        logger.info("🔥 Purging Doc ID %d from Pinecone…", doc_id)
        index = _get_pinecone_index()
        index.delete(filter={"doc_id": doc_id})
        logger.info("✅ Purged Doc ID %d from Vector DB.", doc_id)
    except Exception as exc:
        logger.warning("⚠️ Pinecone delete warning for doc_id=%d: %s", doc_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# ASYNC API  (used by FastAPI routes — never blocks the event loop)
# ─────────────────────────────────────────────────────────────────────────────

def _build_rag_prompt(context: str, history_block: str, question: str) -> str:
    return (
        "You are an AI assistant helping analyze documents. "
        "Answer based on the document context provided.\n\n"
        f"--- DOCUMENT CONTEXT ---\n{context}\n\n"
        f"--- CONVERSATION HISTORY ---\n"
        f"{history_block if history_block else '(This is the start of the conversation)'}\n\n"
        f"--- CURRENT QUESTION ---\nUser: {question}\n\n"
        "Answer concisely, citing the document context where relevant."
    )


async def async_query_rag(query_text: str, user_id: int) -> Tuple[str, List[str]]:
    """
    Async single-shot RAG — used by the legacy /chat/ endpoint in main.py.
    Embedding and Pinecone calls run in thread executors; Gemini call is awaited.
    """
    loop = asyncio.get_event_loop()

    # Embed query (async)
    q_embedding = (await get_gemini_embeddings_async([query_text]))[0]

    # Pinecone query (sync library — run in executor)
    def _pinecone_query():
        index = _get_pinecone_index()
        return index.query(
            vector=q_embedding,
            top_k=5,
            include_metadata=True,
            filter={"user_id": user_id}
        )

    response  = await loop.run_in_executor(None, _pinecone_query)
    
    docs = []
    metadatas = []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        metadatas.append(meta)
        if "text" in meta:
            docs.append(meta["text"])

    if not docs:
        return "No relevant information found in the specified documents.", []

    context_text = "\n\n---\n\n".join(docs)
    prompt = (
        f"Answer the question based only on the following context:\n{context_text}\n\n"
        f"---\nAnswer the question based on the above context: {query_text}"
    )

    # Gemini LLM call (async)
    model    = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7)
    answer = await loop.run_in_executor(None, model.invoke, prompt)
    sources  = list({m.get("source", "Unknown") for m in metadatas})
    return answer.content, sources


async def async_query_rag_with_history(
    query_text: str,
    history: List[Dict[str, str]],
    user_id: int,
) -> AsyncGenerator[str, None]:
    """
    Async streaming RAG generator.

    Yields LLM token chunks exactly as they arrive from Gemini, enabling
    true Server-Sent Events (SSE) streaming with sub-200 ms TTFT.
    """
    loop = asyncio.get_event_loop()

    # 1. Embed query
    q_embedding = (await get_gemini_embeddings_async([query_text]))[0]

    # 2. Pinecone similarity search
    def _pinecone_query():
        index = _get_pinecone_index()
        return index.query(
            vector=q_embedding,
            top_k=5,
            include_metadata=True,
            filter={"user_id": user_id}
        )

    response  = await loop.run_in_executor(None, _pinecone_query)
    
    docs = []
    metadatas = []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        metadatas.append(meta)
        if "text" in meta:
            docs.append(meta["text"])
            
    context_text = "\n\n---\n\n".join(docs) if docs else "No relevant documents found."

    # 3. Build conversation history block
    history_block = ""
    if len(history) > 1:
        history_block = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history[:-1]
        )

    prompt = _build_rag_prompt(context_text, history_block, query_text)

    # 4. Stream tokens from Gemini via astream()
    model = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7, streaming=True)
    full_response = ""
    async for chunk in model.astream(prompt):
        token = chunk.content
        if token:
            full_response += token
            yield token

    # Yield sources as a final SSE JSON event so the client can display citations.
    sources = list({m.get("source", "Unknown") for m in metadatas}) if metadatas else []
    yield f"\n\n[SOURCES]{json.dumps(sources)}"


async def async_delete_from_vector_store(doc_id: int) -> None:
    """Async wrapper — runs the sync Pinecone delete in a thread executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, delete_from_vector_store, doc_id)
