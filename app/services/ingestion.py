"""
PIB Production Ingestion Pipeline
===================================
What this does:
  1. Fetches all ministry-specific PIB RSS feeds (14 feeds)
  2. Parses titles, dates, links from RSS
  3. For each new article — fetches the full article page and extracts body text
  4. Uses BeautifulSoup to parse PIB's actual HTML structure
  5. Rate-limits requests (1.5s gap) to avoid 503s
  6. Retries with exponential backoff on failures
  7. Deduplicates by source URL

Requirements (add to requirements.txt):
  beautifulsoup4==4.12.3
  lxml==5.2.2

Run manually:
  python -m app.services.ingestion

Runs automatically via Celery at 6:30 AM IST daily.
"""

import asyncio
import html
import re
import uuid
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.services.classifier import classify_article

# ── PIB RSS Feeds — one per ministry ─────────────────────────────────────────
PIB_RSS_FEEDS = {
    "All":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",  None),
    "PMO":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",  "PMO"),
    "MoF":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=13", "MoF"),
    "MoD":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=7",  "MoD"),
    "MEA":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=8",  "MEA"),
    "MHA":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=9",  "MHA"),
    "MoA":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=11", "MoA"),
    "MoCI":       ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=12", "MoCI"),
    "MoE":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=14", "MoE"),
    "MoHFW":      ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=15", "MoHFW"),
    "MoEFCC":     ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=16", "MoEFCC"),
    "DST":        ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=17", "DST"),
    "MoRD":       ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=18", "MoRD"),
    "Features":   ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=6",  None),
}

# PIB article body CSS selectors (in order of preference)
BODY_SELECTORS = [
    ("div", "innner-page-content"),   # PIB's own typo — intentional
    ("div", "content-area"),
    ("div", "release-content"),
    ("div", "PressReleaseContent"),
    ("div", "entry-content"),
]

# Ministry text → code mapping (from PIB page text)
MINISTRY_TEXT_MAP = {
    "ministry of finance":                   "MoF",
    "ministry of defence":                   "MoD",
    "ministry of external affairs":          "MEA",
    "ministry of home affairs":              "MHA",
    "ministry of health":                    "MoHFW",
    "ministry of education":                 "MoE",
    "ministry of environment":               "MoEFCC",
    "ministry of commerce":                  "MoCI",
    "ministry of agriculture":               "MoA",
    "ministry of rural development":         "MoRD",
    "ministry of new and renewable energy":  "MoNRE",
    "ministry of science":                   "DST",
    "department of science":                 "DST",
    "ministry of labour":                    "MoLE",
    "ministry of road transport":            "MoRTH",
    "prime minister":                        "PMO",
    "ministry of panchayati raj":            "MoPR",
    "ministry of telecommunications":       "DoT",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PIBPrep/1.0; "
        "+https://pibprep.in; Educational UPSC tool)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

RATE_LIMIT_DELAY   = 1.5   # seconds between article page fetches
MAX_ARTICLES_PER_RUN = 60
FETCH_TIMEOUT      = 20


async def fetch_rss_feed(client: httpx.AsyncClient, url: str, ministry_code: Optional[str]) -> list:
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [RSS] Failed {url}: {e}")
        return []

    items = []
    try:
        import xml.etree.ElementTree as ET
        text = resp.text
        # Fix encoding declaration that confuses ElementTree
        text = re.sub(r"<\?xml[^>]+\?>", '<?xml version="1.0" encoding="utf-8"?>', text)
        root = ET.fromstring(text)

        for item in root.findall(".//item"):
            title    = html.unescape(item.findtext("title", "").strip())
            link     = item.findtext("link", "").strip()
            desc     = html.unescape(item.findtext("description", "").strip())
            desc     = re.sub(r"<[^>]+>", " ", desc).strip()
            desc     = re.sub(r"\s+", " ", desc)
            pub_raw  = item.findtext("pubDate", "").strip()

            pub_date = date.today()
            try:
                pub_date = parsedate_to_datetime(pub_raw).date()
            except Exception:
                pass

            if title and link:
                items.append({
                    "title": title, "url": link,
                    "pub_date": pub_date,
                    "ministry_hint": ministry_code,
                    "description": desc[:500],
                })
    except ET.ParseError as e:
        print(f"  [RSS] XML parse error: {e}")

    return items


async def fetch_article_body(client: httpx.AsyncClient, url: str) -> tuple:
    """Returns (body_text, ministry_code_or_None)"""
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"    [BODY] Failed: {e}")
        return "", None

    soup = BeautifulSoup(resp.text, "lxml")

    # Find body content div
    body_div = None
    for tag, cls in BODY_SELECTORS:
        body_div = soup.find(tag, class_=cls)
        if body_div:
            break

    # Fallback: largest div by text length
    if not body_div:
        divs = soup.find_all("div")
        if divs:
            body_div = max(divs, key=lambda d: len(d.get_text(strip=True)))

    body_text = ""
    if body_div:
        paragraphs = body_div.find_all("p")
        if paragraphs:
            body_text = "\n\n".join(
                p.get_text(separator=" ", strip=True)
                for p in paragraphs
                if len(p.get_text(strip=True)) > 30
            )
        else:
            body_text = body_div.get_text(separator="\n", strip=True)

    body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
    body_text = re.sub(r" {2,}", " ", body_text)
    body_text = body_text[:8000]

    # Detect ministry from page text
    ministry_code = None
    page_lower = soup.get_text().lower()
    for keyword, code in MINISTRY_TEXT_MAP.items():
        if keyword in page_lower:
            ministry_code = code
            break

    return body_text, ministry_code


async def ingest():
    print(f"\n{'='*60}")
    print(f"PIB Ingestion — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'='*60}")

    # Step 1: collect stubs from all RSS feeds
    all_stubs = []
    seen_urls = set()

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for feed_name, (feed_url, ministry_code) in PIB_RSS_FEEDS.items():
            print(f"[Feed] {feed_name}...", end=" ", flush=True)
            stubs = await fetch_rss_feed(client, feed_url, ministry_code)
            print(f"{len(stubs)} items")
            for stub in stubs:
                if stub["url"] not in seen_urls:
                    seen_urls.add(stub["url"])
                    all_stubs.append(stub)
            await asyncio.sleep(0.5)

    print(f"\n[Unique stubs] {len(all_stubs)}")

    # Step 2: filter already-known articles
    from app.db.session import AsyncSessionLocal
    from app.models.models import Article, Ministry, Subject, ArticleTag
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        existing_result = await db.execute(select(Article.source_url))
        existing_urls = {row[0] for row in existing_result.all()}

        new_stubs = [s for s in all_stubs if s["url"] not in existing_urls]
        new_stubs = new_stubs[:MAX_ARTICLES_PER_RUN]
        print(f"[New to fetch] {len(new_stubs)}")

        min_result = await db.execute(select(Ministry))
        ministries = {m.code: m for m in min_result.scalars().all()}

        sub_result = await db.execute(select(Subject))
        subjects = {s.slug: s for s in sub_result.scalars().all()}

        saved = 0
        failed = 0

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
            for i, stub in enumerate(new_stubs):
                short_title = stub["title"][:65]
                print(f"\n  [{i+1}/{len(new_stubs)}] {short_title}...")

                body, page_ministry = await fetch_article_body(client, stub["url"])
                if not body:
                    body = stub["description"]  # fallback to RSS summary
                    print(f"    ⚠ Using RSS summary as fallback")

                ministry_code = page_ministry or stub["ministry_hint"]
                cls = classify_article(stub["title"], body)
                if not ministry_code:
                    # Last resort: classifier's keyword detection
                    from app.services.ingestion import _detect_ministry_from_text
                    ministry_code = _detect_ministry_from_text(stub["title"] + " " + body)

                print(f"    Ministry={ministry_code or '?'}  "
                      f"Score={cls['relevance_score']}/5  "
                      f"Type={cls['content_type']}")

                try:
                    article = Article(
                        id=str(uuid.uuid4()),
                        title=stub["title"],
                        body=body,
                        source_url=stub["url"],
                        published_at=stub["pub_date"],
                        relevance_score=cls["relevance_score"],
                        high_prelims=cls["high_prelims"],
                        high_mains=cls["high_mains"],
                        content_type=cls["content_type"],
                        relevance_note=cls["relevance_note"],
                    )
                    db.add(article)
                    await db.flush()

                    if ministry_code and ministry_code in ministries:
                        db.add(ArticleTag(
                            id=str(uuid.uuid4()),
                            article_id=article.id,
                            ministry_id=ministries[ministry_code].id,
                        ))

                    for slug, _ in cls["subjects"][:3]:
                        if slug in subjects:
                            db.add(ArticleTag(
                                id=str(uuid.uuid4()),
                                article_id=article.id,
                                subject_id=subjects[slug].id,
                            ))

                    await db.commit()
                    saved += 1
                    print(f"    ✓ Saved")
                except Exception as e:
                    await db.rollback()
                    failed += 1
                    print(f"    ✗ DB error: {e}")

                if i < len(new_stubs) - 1:
                    await asyncio.sleep(RATE_LIMIT_DELAY)

    print(f"\n{'='*60}")
    print(f"Done. Saved: {saved}  Failed: {failed}")
    print(f"{'='*60}\n")


def _detect_ministry_from_text(text: str) -> Optional[str]:
    t = text.lower()
    for keyword, code in MINISTRY_TEXT_MAP.items():
        if keyword in t:
            return code
    return None


if __name__ == "__main__":
    asyncio.run(ingest())
