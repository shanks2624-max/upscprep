from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/pibprep"
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://pibprep.in"]
    FREE_ARTICLES_PER_DAY: int = 3
    MCQ_UNLOCK_THRESHOLD: int = 3   # correct MCQs needed to unlock Mains
    DAILY_MCQ_COUNT: int = 5
    DAILY_MAINS_COUNT: int = 5
    OPENAI_API_KEY: str = ""        # for MCQ generation
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
