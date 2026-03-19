from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, date, timedelta
from app.db.session import get_db
from app.models.models import MCQAttempt, Bookmark, User
from app.core.security import get_current_user

router = APIRouter()

@router.get("/me/progress")
async def get_progress(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # Weekly MCQ history (last 7 days)
    weekly = []
    today = date.today()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())

        result = await db.execute(
            select(MCQAttempt).where(
                and_(
                    MCQAttempt.user_id == user_id,
                    MCQAttempt.attempted_at >= day_start,
                    MCQAttempt.attempted_at <= day_end,
                )
            )
        )
        attempts = result.scalars().all()
        correct = sum(1 for a in attempts if a.is_correct)
        total = len(attempts)
        weekly.append({
            "day": day_names[target_date.weekday()],
            "date": target_date.isoformat(),
            "correct": correct if total > 0 else None,
            "total": total if total > 0 else None,
        })

    # Bookmark count
    bm_result = await db.execute(
        select(func.count(Bookmark.id)).where(Bookmark.user_id == user_id)
    )
    bookmark_count = bm_result.scalar() or 0

    # User info
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    return {
        "weekly": weekly,
        "bookmarks_count": bookmark_count,
        "free_days_used": user.free_days_used if user else 0,
        "is_premium": user.is_premium if user else False,
    }
