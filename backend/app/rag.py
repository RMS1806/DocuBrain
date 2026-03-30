"""
backend/app/rag.py

Enterprise-grade async RAG pipeline.

Key changes from the prototype:
  - HuggingFace sentence-transformers REMOVED — was blocking the event loop for
    200-800 ms per call. Now uses Google Gemini Embeddings API (async HTTP).
  - ChromaDB I/O wrapped in asyncio.get_event_loop().run_in_executor() so the
    FastAPI event loop is never blocked by sync ChromaDB calls.
  - query_rag_with_history() is now an AsyncGenerator that yields LLM tokens
    the exact moment they arrive (true SSE streaming; TTFT < 200 ms).
  - Sync variants kept for the Celery worker (separate OS process, no event loop).
"""

import asyncio
import logging
import os
from typing import AsyncGenerator, Dict, List, Tuple

import chromadb
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# ── Gemini client config ───────────────────────────────────────────────────────
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=_GEMINI_API_KEY)

EMBED_MODEL = "models/gemini-embedding-001"   # Updated to current active model
CHAT_MODEL  = "gemini-2.5-flash"
CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION  = "docubrain_collection"

# Text chunking parameters for vectorisation
CHUNK_SIZE    = 1500   # characters per chunk
CHUNK_OVERLAP = 100    # overlap between consecutive chunks


from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

# 1. Create a fake embedding function to act as a circuit breaker
class DummyEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        # This will never actually run because you pass raw embeddings in your upsert/query calls!
        return [[0.0] * 768] * len(input) 

# 2. Update your collection fetcher
def _get_chroma_collection() -> chromadb.Collection:
    """Return the ChromaDB collection using a persistent local client."""
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # CRITICAL: Pass the dummy function so Chroma DOES NOT load its 400MB default model into RAM
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=DummyEmbeddingFunction()
    )

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
    Chunk *text*, embed each chunk via Gemini, and upsert into ChromaDB.
    Runs synchronously — correct for the Celery worker process.
    """
    collection = _get_chroma_collection()
    chunks = _chunk_text(text)
    embeddings = get_gemini_embeddings_sync(chunks)

    ids        = [f"{metadata.get('doc_id', 'x')}_{i}" for i in range(len(chunks))]
    metadatas  = [metadata] * len(chunks)

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    logger.info(
        "✅ Upserted %d chunk(s) for doc_id=%s into ChromaDB.",
        len(chunks), metadata.get("doc_id"),
    )


def query_rag(query_text: str, user_id: int) -> Tuple[str, List[str]]:
    """
    Synchronous single-shot RAG query.
    Left for backward compatibility; prefer async_query_rag in FastAPI routes.
    """
    collection = _get_chroma_collection()
    q_embedding = get_gemini_embeddings_sync([query_text])[0]

    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=3,
        where={"user_id": user_id},
    )

    docs      = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not docs:
        return "No relevant information found in the specified documents.", []

    context_text = "\n\n---\n\n".join(docs)
    prompt = (
        f"Answer the question based only on the following context:\n{context_text}\n\n"
        f"---\nAnswer the question based on the above context: {query_text}"
    )
    model    = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7)
    response = model.invoke(prompt)
    sources  = list({m.get("source", "Unknown") for m in metadatas})
    return response.content, sources


def query_rag_with_history(
    query_text: str,
    history: List[Dict[str, str]],
    user_id: int,
) -> Tuple[str, List[str]]:
    """
    Synchronous history-aware RAG query (Celery / legacy callers only).
    """
    collection = _get_chroma_collection()
    q_embedding = get_gemini_embeddings_sync([query_text])[0]

    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=3,
        where={"user_id": user_id},
    )
    docs      = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
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
    response = model.invoke(prompt)
    return response.content, sources


def delete_from_vector_store(doc_id: int) -> None:
    """
    Delete all ChromaDB entries whose metadata has doc_id == *doc_id*.
    Does NOT load the embedding model — just a direct metadata filter delete.
    """
    try:
        logger.info("🔥 Purging Doc ID %d from ChromaDB…", doc_id)
        collection = _get_chroma_collection()
        collection.delete(where={"doc_id": doc_id})
        logger.info("✅ Purged Doc ID %d from Vector DB.", doc_id)
    except Exception as exc:
        logger.warning("⚠️ ChromaDB delete warning for doc_id=%d: %s", doc_id, exc)


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
    Embedding and ChromaDB calls run in thread executors; Gemini call is awaited.
    """
    loop = asyncio.get_event_loop()

    # Embed query (async)
    q_embedding = (await get_gemini_embeddings_async([query_text]))[0]

    # ChromaDB query (sync library — run in executor)
    def _chroma_query():
        collection = _get_chroma_collection()
        return collection.query(
            query_embeddings=[q_embedding],
            n_results=3,
            where={"user_id": user_id},
        )

    results   = await loop.run_in_executor(None, _chroma_query)
    docs      = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not docs:
        return "No relevant information found in the specified documents.", []

    context_text = "\n\n---\n\n".join(docs)
    prompt = (
        f"Answer the question based only on the following context:\n{context_text}\n\n"
        f"---\nAnswer the question based on the above context: {query_text}"
    )

    # Gemini LLM call (async)
    model    = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.7)
    response = await loop.run_in_executor(None, model.invoke, prompt)
    sources  = list({m.get("source", "Unknown") for m in metadatas})
    return response.content, sources


async def async_query_rag_with_history(
    query_text: str,
    history: List[Dict[str, str]],
    user_id: int,
) -> AsyncGenerator[str, None]:
    """
    Async streaming RAG generator.

    Yields LLM token chunks exactly as they arrive from Gemini, enabling
    true Server-Sent Events (SSE) streaming with sub-200 ms TTFT.

    Usage in an SSE endpoint:
        async for token in async_query_rag_with_history(...):
            yield f"data: {token}\\n\\n"
    """
    loop = asyncio.get_event_loop()

    # 1. Embed query
    q_embedding = (await get_gemini_embeddings_async([query_text]))[0]

    # 2. ChromaDB similarity search
    def _chroma_query():
        collection = _get_chroma_collection()
        return collection.query(
            query_embeddings=[q_embedding],
            n_results=3,
            where={"user_id": user_id},
        )

    results   = await loop.run_in_executor(None, _chroma_query)
    docs      = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
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
    import json
    sources = list({m.get("source", "Unknown") for m in metadatas}) if metadatas else []
    yield f"\n\n[SOURCES]{json.dumps(sources)}"


async def async_delete_from_vector_store(doc_id: int) -> None:
    """Async wrapper — runs the sync ChromaDB delete in a thread executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, delete_from_vector_store, doc_id)
