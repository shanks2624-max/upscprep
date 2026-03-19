from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import Bookmark, Article, Ministry, Subject
from app.core.security import get_current_user
import uuid

router = APIRouter()

# ── Bookmarks ─────────────────────────────────────────────────────────────────

class BookmarkCreate(BaseModel):
    article_id: str

class BookmarkOut(BaseModel):
    id: str
    article_id: str
    title: str
    saved_at: datetime

bookmarks_router = APIRouter()

@bookmarks_router.get("", response_model=List[BookmarkOut])
async def list_bookmarks(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await db.execute(select(Bookmark).where(Bookmark.user_id == user_id).order_by(Bookmark.saved_at.desc()))
    bookmarks = result.scalars().all()
    out = []
    for b in bookmarks:
        art = await db.get(Article, b.article_id)
        out.append(BookmarkOut(id=b.id, article_id=b.article_id, title=art.title if art else "", saved_at=b.saved_at))
    return out

@bookmarks_router.post("", response_model=BookmarkOut, status_code=201)
async def add_bookmark(req: BookmarkCreate, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    existing = await db.execute(select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.article_id == req.article_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already bookmarked")
    bm = Bookmark(id=str(uuid.uuid4()), user_id=user_id, article_id=req.article_id)
    db.add(bm)
    await db.commit()
    await db.refresh(bm)
    art = await db.get(Article, req.article_id)
    return BookmarkOut(id=bm.id, article_id=bm.article_id, title=art.title if art else "", saved_at=bm.saved_at)

@bookmarks_router.delete("/{bookmark_id}", status_code=204)
async def delete_bookmark(bookmark_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.user_id == user_id))
    bm = result.scalar_one_or_none()
    if not bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    await db.delete(bm)
    await db.commit()

# reassign so main.py import works
router = bookmarks_router


# ── Reference data ────────────────────────────────────────────────────────────

ref_router = APIRouter()

@ref_router.get("/ministries")
async def list_ministries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ministry).order_by(Ministry.name))
    ministries = result.scalars().all()
    return [{"id": m.id, "code": m.code, "name": m.name, "short_name": m.short_name} for m in ministries]

@ref_router.get("/subjects")
async def list_subjects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subject).order_by(Subject.label))
    subjects = result.scalars().all()
    return [{"id": s.id, "slug": s.slug, "label": s.label, "gs_paper": s.gs_paper} for s in subjects]

# attach to bookmarks file for import simplicity
reference = ref_router
