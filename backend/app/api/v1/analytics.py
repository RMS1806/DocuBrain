from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_read_db
from app.models.user import User
from app.schemas.analytics import AnalyticsDashboard
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    """
    Per-user analytics dashboard.
    Returns upload count, quiz count, chat message count,
    weekly score trend (last 8 weeks), and top 5 most-studied documents.
    All metrics are computed in a single concurrent batch of SQL aggregate queries.
    """
    return await analytics_service.get_dashboard(db, current_user)
