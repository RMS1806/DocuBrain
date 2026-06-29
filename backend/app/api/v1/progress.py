from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_read_db
from app.models import User
from app.schemas.quiz import ProgressStats
from app.services import quiz_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/stats", response_model=ProgressStats)
async def get_progress_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    """
    Aggregate study performance stats for the authenticated user.
    Returns total quizzes taken, average score, best score, documents studied,
    and the 10 most recent quiz attempts.
    """
    return await quiz_service.get_progress_stats(db, current_user)
