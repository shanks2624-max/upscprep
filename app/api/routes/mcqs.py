from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from app.db.session import get_db, get_redis
from app.models.models import MCQ, MCQAttempt, User
from app.core.security import get_current_user
from app.core.config import settings
import json, random

router = APIRouter()

class MCQOut(BaseModel):
    id: str
    article_id: str
    article_title: str
    question: str
    options: List[str]
    nature: str
    attempted: bool
    is_correct: Optional[bool] = None

class DailyMCQResponse(BaseModel):
    date: str
    questions: List[MCQOut]
    score: dict

class AttemptRequest(BaseModel):
    selected_index: int

class AttemptResponse(BaseModel):
    is_correct: bool
    correct_index: int
    explanation: Optional[str]
    pyq_link: Optional[str]
    daily_score: dict

def _score_key(user_id: str) -> str:
    return f"mcq_score:{user_id}:{date.today().isoformat()}"

async def _get_daily_score(user_id: str, db: AsyncSession) -> dict:
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await db.execute(
        select(MCQAttempt)
        .where(
            and_(
                MCQAttempt.user_id == user_id,
                MCQAttempt.attempted_at >= today_start,
            )
        )
    )
    attempts = result.scalars().all()
    correct = sum(1 for a in attempts if a.is_correct)
    total = len(attempts)
    return {
        "correct": correct,
        "total": total,
        "mains_unlocked": correct >= settings.MCQ_UNLOCK_THRESHOLD,
    }

@router.get("/daily", response_model=DailyMCQResponse)
async def get_daily_mcqs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # Get today's approved MCQs (up to 5)
    result = await db.execute(
        select(MCQ)
        .where(MCQ.admin_approved == True)
        .order_by(func.random())
        .limit(settings.DAILY_MCQ_COUNT)
    )
    mcqs = result.scalars().all()

    # Get today's attempts for this user
    today_start = datetime.combine(date.today(), datetime.min.time())
    attempts_result = await db.execute(
        select(MCQAttempt).where(
            and_(MCQAttempt.user_id == user_id, MCQAttempt.attempted_at >= today_start)
        )
    )
    attempts = {a.mcq_id: a for a in attempts_result.scalars().all()}

    questions = []
    for mcq in mcqs:
        attempt = attempts.get(mcq.id)
        questions.append(MCQOut(
            id=mcq.id,
            article_id=mcq.article_id,
            article_title=mcq.article.title if mcq.article else "",
            question=mcq.question,
            options=mcq.options,
            nature=mcq.nature,
            attempted=attempt is not None,
            is_correct=attempt.is_correct if attempt else None,
        ))

    score = await _get_daily_score(user_id, db)
    return DailyMCQResponse(date=date.today().isoformat(), questions=questions, score=score)

@router.post("/{mcq_id}/attempt", response_model=AttemptResponse)
async def attempt_mcq(
    mcq_id: str,
    req: AttemptRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # Check not already attempted today
    today_start = datetime.combine(date.today(), datetime.min.time())
    existing = await db.execute(
        select(MCQAttempt).where(
            and_(
                MCQAttempt.user_id == user_id,
                MCQAttempt.mcq_id == mcq_id,
                MCQAttempt.attempted_at >= today_start,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already attempted today")

    mcq_result = await db.execute(select(MCQ).where(MCQ.id == mcq_id))
    mcq = mcq_result.scalar_one_or_none()
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")

    is_correct = req.selected_index == mcq.correct_index
    attempt = MCQAttempt(user_id=user_id, mcq_id=mcq_id, is_correct=is_correct)
    db.add(attempt)
    await db.commit()

    score = await _get_daily_score(user_id, db)
    return AttemptResponse(
        is_correct=is_correct,
        correct_index=mcq.correct_index,
        explanation=mcq.explanation,
        pyq_link=mcq.pyq_link,
        daily_score=score,
    )
