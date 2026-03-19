#!/usr/bin/env python3
"""
PIB Scraper Test — run this FIRST before wiring up the full pipeline.

Install deps:  pip install httpx beautifulsoup4 lxml
Run:           python test_scraper.py

This hits PIB live and shows you exactly what you'll get.
No database needed.
"""

import asyncio
import html
import re
import sys
from datetime import date
from email.utils import parsedate_to_datetime

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing deps. Run: pip install httpx beautifulsoup4 lxml")
    sys.exit(1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PIBPrep/1.0; "
        "+https://pibprep.in; Educational UPSC tool)"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

TEST_FEED = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"

BODY_SELECTORS = [
    ("div", "innner-page-content"),
    ("div", "content-area"),
    ("div", "release-content"),
    ("div", "PressReleaseContent"),
]


async def test_rss():
    print("\n" + "="*60)
    print("TEST 1: Fetching PIB RSS feed")
    print("="*60)
    print(f"URL: {TEST_FEED}\n")

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        try:
            resp = await client.get(TEST_FEED)
            print(f"Status: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
            print(f"Response size: {len(resp.content)} bytes")
        except Exception as e:
            print(f"FAILED: {e}")
            print("\nThis usually means:")
            print("  - No internet access from your machine/server")
            print("  - PIB is temporarily down")
            print("  - Your IP is rate-limited (try again in 5 mins)")
            return []

        if resp.status_code != 200:
            print(f"FAILED with HTTP {resp.status_code}")
            return []

        # Parse RSS
        import xml.etree.ElementTree as ET
        text = re.sub(r"<\?xml[^>]+\?>", '<?xml version="1.0" encoding="utf-8"?>', resp.text)

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
            print("First 500 chars of response:")
            print(resp.text[:500])
            return []

        items = root.findall(".//item")
        print(f"\n✓ Found {len(items)} items in feed\n")

        results = []
        for i, item in enumerate(items[:5]):  # show first 5
            title   = html.unescape(item.findtext("title", "").strip())
            link    = item.findtext("link", "").strip()
            desc    = html.unescape(item.findtext("description", "").strip())
            desc    = re.sub(r"<[^>]+>", " ", desc).strip()
            pub_raw = item.findtext("pubDate", "").strip()

            pub_date = "unknown"
            try:
                pub_date = parsedate_to_datetime(pub_raw).strftime("%d %b %Y")
            except Exception:
                pass

            print(f"  [{i+1}] {title[:80]}")
            print(f"       Date: {pub_date}")
            print(f"       URL:  {link[:80]}")
            print(f"       Desc: {desc[:100]}...")
            print()
            results.append({"title": title, "url": link, "desc": desc})

        return results


async def test_article_body(url: str):
    print("\n" + "="*60)
    print("TEST 2: Fetching full article body")
    print("="*60)
    print(f"URL: {url}\n")

    async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            print(f"Response size: {len(resp.content)} bytes")
        except Exception as e:
            print(f"FAILED: {e}")
            return

        soup = BeautifulSoup(resp.text, "lxml")

        # Try each selector
        body_div = None
        for tag, cls in BODY_SELECTORS:
            found = soup.find(tag, class_=cls)
            if found:
                print(f"✓ Body found using selector: <{tag} class='{cls}'>")
                body_div = found
                break

        if not body_div:
            print("⚠ None of the standard selectors matched")
            print("  Trying fallback: largest div by text length...")
            divs = soup.find_all("div")
            if divs:
                body_div = max(divs, key=lambda d: len(d.get_text(strip=True)))
                print(f"  Fallback div has {len(body_div.get_text())} chars")

        if body_div:
            paragraphs = body_div.find_all("p")
            print(f"  Paragraphs found: {len(paragraphs)}")

            text_parts = [
                p.get_text(separator=" ", strip=True)
                for p in paragraphs
                if len(p.get_text(strip=True)) > 30
            ]
            body_text = "\n\n".join(text_parts)

            if body_text:
                print(f"\n--- Body text preview (first 600 chars) ---")
                print(body_text[:600])
                print("---")
                print(f"\nTotal body length: {len(body_text)} chars")
            else:
                # paragraph fallback
                raw = body_div.get_text(separator="\n", strip=True)
                print(f"\n--- Raw text fallback (first 600 chars) ---")
                print(raw[:600])
                print("---")
        else:
            print("✗ Could not extract body. PIB may have changed their HTML structure.")
            print("\nPage title:", soup.find("title"))
            print("\nTop-level divs:")
            for div in soup.find_all("div", limit=10):
                cls = div.get("class", [])
                if cls:
                    print(f"  <div class='{' '.join(cls)}'>")

        # Check for ministry
        print("\n--- Ministry detection ---")
        page_text = soup.get_text().lower()
        MINISTRY_MAP = {
            "ministry of finance": "MoF",
            "ministry of defence": "MoD",
            "ministry of external affairs": "MEA",
            "ministry of home affairs": "MHA",
            "ministry of health": "MoHFW",
            "ministry of education": "MoE",
            "ministry of environment": "MoEFCC",
        }
        found_ministry = None
        for keyword, code in MINISTRY_MAP.items():
            if keyword in page_text:
                print(f"  ✓ Detected: {code} (from '{keyword}')")
                found_ministry = code
                break
        if not found_ministry:
            print("  ⚠ Ministry not auto-detected — will use RSS feed hint")


async def main():
    print("\nPIB Scraper Diagnostic Test")
    print("============================\n")

    # Test 1: RSS
    items = await test_rss()

    if not items:
        print("\n✗ RSS test failed. Fix connectivity before proceeding.")
        return

    # Test 2: Article body (use first result from RSS)
    first_url = items[0]["url"]
    await asyncio.sleep(1.5)  # polite delay
    await test_article_body(first_url)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("""
If both tests passed:
  → Your scraper will work. Run: python -m app.services.ingestion

If TEST 1 (RSS) failed:
  → Check internet access on your server
  → Try: curl -A "Mozilla/5.0" https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3

If TEST 2 (body) failed with empty body:
  → PIB may have changed their HTML structure
  → Open the article URL in a browser and inspect the element containing
    the article text. Update BODY_SELECTORS in ingestion.py with the
    correct class name.
  → Common fix: add ("div", "new-class-name") to BODY_SELECTORS

If you get 503 errors:
  → Increase RATE_LIMIT_DELAY in ingestion.py from 1.5 to 3.0
  → Run during off-peak hours (early morning IST works best)
""")


if __name__ == "__main__":
    asyncio.run(main())
