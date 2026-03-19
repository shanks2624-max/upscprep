from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import Ministry, Subject

router = APIRouter()

@router.get("/ministries")
async def list_ministries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ministry).order_by(Ministry.name))
    return [{"id": m.id, "code": m.code, "name": m.name, "short_name": m.short_name} for m in result.scalars().all()]

@router.get("/subjects")
async def list_subjects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subject).order_by(Subject.label))
    return [{"id": s.id, "slug": s.slug, "label": s.label, "gs_paper": s.gs_paper} for s in result.scalars().all()]
