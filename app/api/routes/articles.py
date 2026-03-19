from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from typing import Optional, List
from datetime import date, timedelta
from app.db.session import get_db
from app.models.models import Article, ArticleTag, Ministry, Subject, User
from app.core.security import get_current_user_optional, get_current_user
from app.core.config import settings
from pydantic import BaseModel
import json

router = APIRouter()

# ── Pydantic response shapes ──────────────────────────────────────────────────

class MinistryOut(BaseModel):
    code: str
    name: str
    short_name: Optional[str] = None

class SubjectOut(BaseModel):
    slug: str
    label: str
    gs_paper: Optional[str] = None

class ArticleCard(BaseModel):
    id: str
    title: str
    source_url: Optional[str]
    published_at: date
    ministry: Optional[MinistryOut]
    subjects: List[SubjectOut]
    relevance_score: int
    high_prelims: bool
    high_mains: bool
    content_type: Optional[str]
    relevance_note: Optional[str]
    blurred: bool = False

class ArticleDetail(ArticleCard):
    body: Optional[str]
    snippet: Optional[dict]
    mcq_count: int = 0
    mains_count: int = 0

class ArticleListResponse(BaseModel):
    data: List[ArticleCard]
    meta: dict

# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_filter(date_param: str):
    today = date.today()
    if date_param == "today" or not date_param:
        return today, today
    elif date_param == "7d":
        return today - timedelta(days=7), today
    elif date_param == "30d":
        return today - timedelta(days=30), today
    else:
        try:
            d = date.fromisoformat(date_param)
            return d, d
        except Exception:
            return today, today

def _article_to_card(article: Article, blurred=False) -> ArticleCard:
    ministry = None
    subjects = []
    for tag in article.tags:
        if tag.ministry:
            ministry = MinistryOut(
                code=tag.ministry.code,
                name=tag.ministry.name,
                short_name=tag.ministry.short_name,
            )
        if tag.subject:
            subjects.append(SubjectOut(
                slug=tag.subject.slug,
                label=tag.subject.label,
                gs_paper=tag.subject.gs_paper,
            ))
    return ArticleCard(
        id=article.id,
        title=article.title if not blurred else "Sign in to read this article",
        source_url=article.source_url,
        published_at=article.published_at,
        ministry=ministry,
        subjects=subjects,
        relevance_score=article.relevance_score,
        high_prelims=article.high_prelims,
        high_mains=article.high_mains,
        content_type=article.content_type,
        relevance_note=article.relevance_note if not blurred else None,
        blurred=blurred,
    )

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=ArticleListResponse)
async def list_articles(
    date_range: str = Query("today"),
    ministry: Optional[str] = None,
    subject: Optional[str] = None,
    gs_paper: Optional[str] = None,
    high_prelims: Optional[bool] = None,
    content_type: Optional[str] = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_optional),
):
    from_date, to_date = _date_filter(date_range)
    page_size = 20

    stmt = (
        select(Article)
        .where(Article.published_at.between(from_date, to_date))
        .order_by(Article.relevance_score.desc(), Article.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    if ministry:
        stmt = stmt.join(ArticleTag).join(Ministry).where(Ministry.code == ministry)
    if subject:
        stmt = stmt.join(ArticleTag).join(Subject).where(Subject.slug == subject)
    if gs_paper:
        stmt = stmt.join(ArticleTag).join(Subject).where(Subject.gs_paper == gs_paper)
    if high_prelims is not None:
        stmt = stmt.where(Article.high_prelims == high_prelims)
    if content_type:
        stmt = stmt.where(Article.content_type == content_type)

    result = await db.execute(stmt)
    articles = result.scalars().all()

    free_limit = settings.FREE_ARTICLES_PER_DAY
    cards = []
    for i, article in enumerate(articles):
        blurred = (user_id is None) and (i >= free_limit)
        cards.append(_article_to_card(article, blurred=blurred))

    count_stmt = select(func.count(Article.id)).where(Article.published_at.between(from_date, to_date))
    total = (await db.execute(count_stmt)).scalar()

    return ArticleListResponse(
        data=cards,
        meta={"total": total, "page": page, "blurred_from": free_limit if not user_id else None},
    )

@router.get("/search", response_model=ArticleListResponse)
async def search_articles(
    q: str = Query(..., min_length=2),
    content_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_optional),
):
    stmt = (
        select(Article)
        .where(Article.title.ilike(f"%{q}%"))
        .order_by(Article.published_at.desc())
        .limit(30)
    )
    if content_type:
        stmt = stmt.where(Article.content_type == content_type)

    result = await db.execute(stmt)
    articles = result.scalars().all()
    cards = [_article_to_card(a, blurred=False) for a in articles]
    return ArticleListResponse(data=cards, meta={"total": len(cards), "blurred_from": None})

@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    card = _article_to_card(article)
    snippet = None
    if article.snippet_what:
        snippet = {
            "what": article.snippet_what,
            "why_upsc": article.snippet_why,
            "gs_paper": article.snippet_gs,
            "prelims": article.snippet_prelims,
            "pyq_link": article.snippet_pyq,
        }

    return ArticleDetail(
        **card.dict(),
        body=article.body,
        snippet=snippet,
        mcq_count=len(article.mcqs),
        mains_count=len(article.mains_qs),
    )
