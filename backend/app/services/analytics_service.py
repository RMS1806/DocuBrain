from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import analytics_repository
from app.schemas.analytics import AnalyticsDashboard, MostStudiedDocument, WeeklyScoreTrend


async def get_dashboard(db: AsyncSession, user: User) -> AnalyticsDashboard:
    # AsyncSession wraps a single connection — concurrent queries on it deadlock.
    # Run sequentially; the DB round-trips are fast and this is a dashboard endpoint.
    doc_count   = await analytics_repository.count_documents(db, user.id)
    quiz_count  = await analytics_repository.count_quizzes(db, user.id)
    msg_count   = await analytics_repository.count_chat_messages(db, user.id)
    trend_rows  = await analytics_repository.weekly_score_trend(db, user.id)
    top_docs    = await analytics_repository.most_studied_documents(db, user.id)

    return AnalyticsDashboard(
        documents_uploaded=doc_count,
        quizzes_generated=quiz_count,
        chat_messages_sent=msg_count,
        weekly_score_trend=[WeeklyScoreTrend(**r) for r in trend_rows],
        most_studied_documents=[MostStudiedDocument(**d) for d in top_docs],
    )
