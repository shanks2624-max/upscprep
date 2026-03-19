from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import MainsQuestion, MCQAttempt
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter()

class MainsQuestionOut(BaseModel):
    id: str
    question: Optional[str]   # null when blurred
    gs_paper: Optional[str]
    word_limit: int
    blurred: bool

class DailyMainsResponse(BaseModel):
    unlocked: bool
    unlock_at_score: int
    current_score: int
    questions: List[MainsQuestionOut]

@router.get("/daily", response_model=DailyMainsResponse)
async def get_daily_mains(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # Check today's MCQ score — enforced server-side
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await db.execute(
        select(MCQAttempt).where(
            and_(MCQAttempt.user_id == user_id, MCQAttempt.attempted_at >= today_start)
        )
    )
    attempts = result.scalars().all()
    correct = sum(1 for a in attempts if a.is_correct)
    unlocked = correct >= settings.MCQ_UNLOCK_THRESHOLD

    mains_result = await db.execute(
        select(MainsQuestion)
        .where(MainsQuestion.admin_approved == True)
        .order_by(func.random())
        .limit(settings.DAILY_MAINS_COUNT)
    )
    questions = mains_result.scalars().all()

    return DailyMainsResponse(
        unlocked=unlocked,
        unlock_at_score=settings.MCQ_UNLOCK_THRESHOLD,
        current_score=correct,
        questions=[
            MainsQuestionOut(
                id=q.id,
                question=q.question if unlocked else None,
                gs_paper=q.gs_paper,
                word_limit=q.word_limit,
                blurred=not unlocked,
            )
            for q in questions
        ],
    )
