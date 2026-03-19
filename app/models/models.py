from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Date, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

def gen_uuid():
    return str(uuid.uuid4())

class Ministry(Base):
    __tablename__ = "ministries"
    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code        = Column(String(20), unique=True, nullable=False)
    name        = Column(String(200), nullable=False)
    short_name  = Column(String(50))
    articles    = relationship("ArticleTag", back_populates="ministry")

class Subject(Base):
    __tablename__ = "subjects"
    id       = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    slug     = Column(String(50), unique=True, nullable=False)
    label    = Column(String(100), nullable=False)
    gs_paper = Column(String(10))  # gs1, gs2, gs3, gs4
    articles = relationship("ArticleTag", back_populates="subject")

class Article(Base):
    __tablename__ = "articles"
    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title           = Column(Text, nullable=False)
    body            = Column(Text)
    source_url      = Column(Text, unique=True)
    published_at    = Column(Date, nullable=False)
    relevance_score = Column(Integer, default=3)   # 1-5 dots
    high_prelims    = Column(Boolean, default=False)
    high_mains      = Column(Boolean, default=False)
    content_type    = Column(String(30))            # scheme, report, policy, judgment...
    relevance_note  = Column(Text)
    snippet_what    = Column(Text)
    snippet_why     = Column(Text)
    snippet_gs      = Column(String(10))
    snippet_prelims = Column(Boolean, default=False)
    snippet_pyq     = Column(Text)
    ingested_at     = Column(DateTime, default=datetime.utcnow)

    tags        = relationship("ArticleTag", back_populates="article", cascade="all, delete")
    mcqs        = relationship("MCQ", back_populates="article", cascade="all, delete")
    mains_qs    = relationship("MainsQuestion", back_populates="article", cascade="all, delete")
    bookmarks   = relationship("Bookmark", back_populates="article", cascade="all, delete")

class ArticleTag(Base):
    __tablename__ = "article_tags"
    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    article_id  = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    ministry_id = Column(UUID(as_uuid=False), ForeignKey("ministries.id"), nullable=True)
    subject_id  = Column(UUID(as_uuid=False), ForeignKey("subjects.id"), nullable=True)

    article  = relationship("Article", back_populates="tags")
    ministry = relationship("Ministry", back_populates="articles")
    subject  = relationship("Subject", back_populates="articles")

class User(Base):
    __tablename__ = "users"
    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email          = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255))
    created_at     = Column(DateTime, default=datetime.utcnow)
    free_days_used = Column(Integer, default=0)
    is_premium     = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)

    bookmarks    = relationship("Bookmark", back_populates="user", cascade="all, delete")
    mcq_attempts = relationship("MCQAttempt", back_populates="user", cascade="all, delete")

class MCQ(Base):
    __tablename__ = "mcqs"
    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    article_id     = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    question       = Column(Text, nullable=False)
    options        = Column(JSON, nullable=False)   # ["A. ...", "B. ...", ...]
    correct_index  = Column(Integer, nullable=False)
    nature         = Column(String(20), default="factual")  # factual, conceptual, analytical
    explanation    = Column(Text)
    pyq_link       = Column(Text)
    admin_approved = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    article  = relationship("Article", back_populates="mcqs")
    attempts = relationship("MCQAttempt", back_populates="mcq", cascade="all, delete")

class MainsQuestion(Base):
    __tablename__ = "mains_questions"
    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    article_id     = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    question       = Column(Text, nullable=False)
    gs_paper       = Column(String(10))
    word_limit     = Column(Integer, default=250)
    admin_approved = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article", back_populates="mains_qs")

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    article_id = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    saved_at   = Column(DateTime, default=datetime.utcnow)

    user    = relationship("User", back_populates="bookmarks")
    article = relationship("Article", back_populates="bookmarks")

class MCQAttempt(Base):
    __tablename__ = "mcq_attempts"
    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id      = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    mcq_id       = Column(UUID(as_uuid=False), ForeignKey("mcqs.id"), nullable=False)
    is_correct   = Column(Boolean, nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="mcq_attempts")
    mcq  = relationship("MCQ", back_populates="attempts")
