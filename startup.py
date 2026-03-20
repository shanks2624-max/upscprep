import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return

    print("Connecting to database...")
    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("Database connection OK")

        from app.models.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Tables created OK")

        await engine.dispose()
        print("Startup complete")

    except Exception as e:
        print(f"Startup error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
