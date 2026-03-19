from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.db.session import get_db
from app.models.models import User
from app.core.security import create_access_token, pwd_context
import uuid

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = ""   # optional — magic-link flow in Phase 2

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = ""

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    free_days_used: int
    is_premium: bool

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        hashed_password=pwd_context.hash(req.password) if req.password else "",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, free_days_used=0, is_premium=False)

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        free_days_used=user.free_days_used,
        is_premium=user.is_premium,
    )
