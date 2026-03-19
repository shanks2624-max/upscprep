"""
MCQ Generator — uses OpenAI to generate MCQs from article text.
Generates questions in pending state; admin must approve before publish.
Run: python -m app.services.mcq_generator
"""
import asyncio
import json
import httpx
from app.db.session import AsyncSessionLocal
from app.models.models import Article, MCQ
from app.core.config import settings
import uuid

MCQ_PROMPT = """You are an expert UPSC Prelims question setter. Given the article below, generate 3 high-quality MCQ questions in the style of UPSC Prelims 2020–2025.

Rules:
1. Use UPSC-style formats: "Which of the following is correct?", "Consider the following statements", "Select the correct answer using the codes below"
2. Each question must have exactly 4 options (A, B, C, D)
3. Tag each question: nature = factual | conceptual | analytical
4. Write a clear explanation (2-3 sentences) mentioning why wrong options are wrong
5. Add a PYQ link if similar questions appeared in previous years

Article:
{title}
{body}

Return ONLY a JSON array, no markdown:
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_index": 0,
    "nature": "factual",
    "explanation": "...",
    "pyq_link": "Similar to UPSC 2021 Q42 on..."
  }}
]"""

MAINS_PROMPT = """You are an expert UPSC Mains question setter. Given the article, generate 2 Mains-style questions.

Rules:
1. Map each question to the correct GS paper (GS1/GS2/GS3/GS4)
2. Specify word limit (150 or 250 words)
3. Use standard UPSC Mains phrasing: "Discuss", "Critically analyse", "Examine", "Comment on"

Article:
{title}
{body}

Return ONLY a JSON array:
[
  {{
    "question": "...",
    "gs_paper": "gs3",
    "word_limit": 250
  }}
]"""

async def generate_mcqs_for_article(article: Article) -> list:
    if not settings.OPENAI_API_KEY:
        return []
    prompt = MCQ_PROMPT.format(title=article.title, body=(article.body or "")[:2000])
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(content)

async def generate_mains_for_article(article: Article) -> list:
    if not settings.OPENAI_API_KEY:
        return []
    prompt = MAINS_PROMPT.format(title=article.title, body=(article.body or "")[:2000])
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(content)

async def run_generator():
    from sqlalchemy import select
    from app.models.models import MainsQuestion
    async with AsyncSessionLocal() as db:
        # Get articles without MCQs yet
        result = await db.execute(
            select(Article)
            .where(Article.relevance_score >= 3)
            .order_by(Article.ingested_at.desc())
            .limit(10)
        )
        articles = result.scalars().all()

        for article in articles:
            if article.mcqs:
                continue
            print(f"Generating MCQs for: {article.title[:60]}")
            try:
                mcq_data = await generate_mcqs_for_article(article)
                for m in mcq_data:
                    mcq = MCQ(
                        id=str(uuid.uuid4()),
                        article_id=article.id,
                        question=m["question"],
                        options=m["options"],
                        correct_index=m["correct_index"],
                        nature=m.get("nature", "factual"),
                        explanation=m.get("explanation"),
                        pyq_link=m.get("pyq_link"),
                        admin_approved=False,  # pending review
                    )
                    db.add(mcq)

                mains_data = await generate_mains_for_article(article)
                for mq in mains_data:
                    mains = MainsQuestion(
                        id=str(uuid.uuid4()),
                        article_id=article.id,
                        question=mq["question"],
                        gs_paper=mq.get("gs_paper", "gs3"),
                        word_limit=mq.get("word_limit", 250),
                        admin_approved=False,
                    )
                    db.add(mains)

                await db.commit()
                print(f"  Generated {len(mcq_data)} MCQs, {len(mains_data)} Mains questions")
            except Exception as e:
                print(f"  Error: {e}")
                await db.rollback()

if __name__ == "__main__":
    asyncio.run(run_generator())
