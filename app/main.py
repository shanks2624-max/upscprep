from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import articles, auth, mcqs, mains, bookmarks, reference, users
from app.core.config import settings

app = FastAPI(
    title="PIBPrep API",
    description="UPSC Current Affairs Platform — PIB-focused, exam-oriented",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/api/v1/auth",       tags=["Auth"])
app.include_router(articles.router,   prefix="/api/v1/articles",   tags=["Articles"])
app.include_router(mcqs.router,       prefix="/api/v1/mcqs",       tags=["MCQs"])
app.include_router(mains.router,      prefix="/api/v1/mains",      tags=["Mains"])
app.include_router(bookmarks.router,  prefix="/api/v1/bookmarks",  tags=["Bookmarks"])
app.include_router(users.router,       prefix="/api/v1/users",      tags=["Users"])
app.include_router(reference.router,  prefix="/api/v1",            tags=["Reference"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "PIBPrep API"}
