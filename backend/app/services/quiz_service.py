"""
app/services/quiz_service.py

AI quiz and flashcard generation service.

Flow:
  1. Validate doc ownership + processing status
  2. Download PDF from S3 (sync → thread executor)
  3. Extract full text via pypdf (sync → thread executor)
  4. Build structured prompt for Gemini
  5. Call Gemini with response_mime_type="application/json" (sync → thread executor)
  6. Parse + validate the JSON response
  7. Persist quiz + items to DB via quiz_repository
"""

import io
import json
import logging

import anyio
import google.generativeai as genai
import pypdf
from fastapi import HTTPException

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError, gemini_breaker, s3_breaker
from app.infrastructure.s3 import download_bytes_from_s3, get_s3_client
from app.models import User
from app.models.quiz import Quiz
from app.repositories import document_repository, quiz_repository

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 500_000  # ~125K tokens — well within Gemini Flash's 1M context window


# ── Sync helpers (run inside thread executors) ────────────────────────────────

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "".join(page.extract_text() or "" for page in reader.pages)


def _call_gemini(prompt: str) -> str:
    """Call Gemini and return the raw JSON string."""
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )
    response = model.generate_content(prompt)
    return response.text


# ── Prompt builders ───────────────────────────────────────────────────────────

def _quiz_prompt(text: str, count: int) -> str:
    return (
        f"You are an expert educational AI. Generate exactly {count} multiple-choice "
        "questions to test a student's comprehension of the document below.\n\n"
        "Return ONLY a JSON object — no markdown, no backticks, no extra text:\n"
        '{"items": [{"question": "...", "options": ["A text", "B text", "C text", "D text"], '
        '"correct_answer": 0, "explanation": "..."}]}\n\n'
        "Rules:\n"
        "- correct_answer is the 0-based index into the options array (0, 1, 2, or 3)\n"
        "- Exactly 4 options per question\n"
        "- Mix factual recall and analytical reasoning questions\n"
        "- Base all questions strictly on the document content\n\n"
        f"Document:\n---\n{text}\n---"
    )


def _flashcard_prompt(text: str, count: int) -> str:
    return (
        f"You are an expert educational AI. Generate exactly {count} flashcards "
        "to help a student study the key concepts from the document below.\n\n"
        "Return ONLY a JSON object — no markdown, no backticks, no extra text:\n"
        '{"items": [{"front": "Concept or term", "back": "Clear concise definition"}]}\n\n'
        "Rules:\n"
        "- Front: a single concept, term, or question (concise)\n"
        "- Back: a complete but concise explanation (1-3 sentences)\n"
        "- Cover the most important concepts from the document\n\n"
        f"Document:\n---\n{text}\n---"
    )


# ── Response parsers ──────────────────────────────────────────────────────────

def _parse_quiz_items(raw_items: list) -> list[dict]:
    parsed = []
    for item in raw_items:
        options = item.get("options", [])
        correct = item.get("correct_answer", 0)
        if not isinstance(options, list) or len(options) != 4:
            continue  # skip malformed items silently
        if not isinstance(correct, int) or not (0 <= correct <= 3):
            correct = 0
        parsed.append({
            "content_front": str(item.get("question", "")),
            "options": [str(o) for o in options],
            "correct_answer": correct,
            "explanation": str(item.get("explanation", "")) or None,
            "content_back": None,
        })
    return parsed


def _parse_flashcard_items(raw_items: list) -> list[dict]:
    return [
        {
            "content_front": str(item.get("front", "")),
            "content_back": str(item.get("back", "")),
            "options": None,
            "correct_answer": None,
            "explanation": None,
        }
        for item in raw_items
        if item.get("front") and item.get("back")
    ]


# ── Public service function ───────────────────────────────────────────────────

async def generate_quiz(
    db,
    document_id: int,
    quiz_type: str,
    count: int,
    current_user: User,
) -> Quiz:
    doc = await document_repository.get_by_id(db, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("completed", "ready"):
        raise HTTPException(
            status_code=400,
            detail=f"Document is still being processed (status: {doc.status}). Please wait.",
        )

    # Capture minio_path as a plain string before releasing the DB connection.
    # After commit() the asyncpg connection returns to the pool — the session
    # object stays valid and will reacquire a fresh connection for the later INSERT.
    minio_path: str = doc.minio_path
    await db.commit()

    # S3 download (sync SDK → thread, guarded by circuit breaker)
    try:
        pdf_bytes: bytes = await s3_breaker.call(
            lambda: anyio.to_thread.run_sync(
                lambda: download_bytes_from_s3(get_s3_client(), settings.S3_BUCKET_NAME, minio_path)
            )
        )
    except CircuitOpenError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Text extraction (sync pypdf → thread, no external service — no breaker needed)
    text: str = await anyio.to_thread.run_sync(lambda: _extract_pdf_text(pdf_bytes))
    text = text[:_MAX_TEXT_CHARS]

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from this PDF.")

    # Build prompt and call Gemini (sync SDK → thread, guarded by circuit breaker)
    prompt = _quiz_prompt(text, count) if quiz_type == "quiz" else _flashcard_prompt(text, count)
    try:
        raw_json: str = await gemini_breaker.call(
            lambda: anyio.to_thread.run_sync(lambda: _call_gemini(prompt))
        )
    except CircuitOpenError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Parse response
    try:
        data = json.loads(raw_json)
        raw_items = data.get("items", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Gemini returned invalid JSON for quiz generation: %s", exc)
        raise HTTPException(status_code=502, detail="AI returned an invalid response. Please try again.")

    items_data = (
        _parse_quiz_items(raw_items) if quiz_type == "quiz"
        else _parse_flashcard_items(raw_items)
    )

    if not items_data:
        raise HTTPException(status_code=502, detail="AI could not generate valid items from this document.")

    return await quiz_repository.create_quiz(db, current_user.id, document_id, quiz_type, items_data)


async def get_quiz(db, quiz_id: int, current_user: User) -> Quiz:
    quiz = await quiz_repository.get_quiz(db, quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


async def list_quizzes(db, current_user: User) -> list[Quiz]:
    return await quiz_repository.list_quizzes(db, current_user.id)


# ── Attempt + Progress ────────────────────────────────────────────────────────

async def submit_attempt(db, quiz_id: int, answers: list, current_user: User) -> dict:
    quiz = await quiz_repository.get_quiz(db, quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if quiz.quiz_type == "flashcard":
        attempt = await quiz_repository.create_attempt(
            db, current_user.id, quiz_id, answers=None, score=None, total=None
        )
        return {
            "attempt_id": attempt.id,
            "quiz_type": "flashcard",
            "message": "Flashcard review recorded.",
        }

    items = sorted(quiz.items, key=lambda x: x.order_index)
    if len(answers) != len(items):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(items)} answers, got {len(answers)}.",
        )

    score = sum(
        1 for item, answer in zip(items, answers)
        if answer is not None and answer == item.correct_answer
    )
    total = len(items)

    attempt = await quiz_repository.create_attempt(
        db, current_user.id, quiz_id, answers, score, total
    )

    breakdown = [
        {
            "item_id": item.id,
            "question": item.content_front,
            "your_answer": answers[i],
            "correct_answer": item.correct_answer,
            "is_correct": answers[i] == item.correct_answer,
            "explanation": item.explanation,
        }
        for i, item in enumerate(items)
    ]

    return {
        "attempt_id": attempt.id,
        "quiz_type": "quiz",
        "score": score,
        "total": total,
        "score_pct": round(score / total * 100, 1),
        "breakdown": breakdown,
    }


async def get_progress_stats(db, current_user: User) -> dict:
    attempts = await quiz_repository.list_attempts(db, current_user.id, limit=200)

    # Separate scored quiz attempts from flashcard reviews
    scored = [a for a in attempts if a.total is not None and a.total > 0]

    if not scored:
        return {
            "total_quizzes_attempted": 0,
            "total_questions_answered": 0,
            "average_score_pct": None,
            "best_score_pct": None,
            "documents_studied": 0,
            "recent_attempts": [],
        }

    total_questions = sum(a.total for a in scored)
    total_correct = sum(a.score or 0 for a in scored)
    avg_pct = round(total_correct / total_questions * 100, 1) if total_questions else 0.0
    best_pct = round(
        max((a.score or 0) / a.total * 100 for a in scored), 1
    )
    documents_studied = len({a.quiz.document_id for a in scored})

    recent = [
        {
            "attempt_id": a.id,
            "quiz_id": a.quiz_id,
            "quiz_type": a.quiz.quiz_type,
            "document_id": a.quiz.document_id,
            "score": a.score,
            "total": a.total,
            "score_pct": round((a.score or 0) / a.total * 100, 1) if a.total else None,
            "completed_at": a.completed_at,
        }
        for a in attempts[:10]  # last 10 across all types
    ]

    return {
        "total_quizzes_attempted": len(scored),
        "total_questions_answered": total_questions,
        "average_score_pct": avg_pct,
        "best_score_pct": best_pct,
        "documents_studied": documents_studied,
        "recent_attempts": recent,
    }
