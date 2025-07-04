# parser/kazdata_parser.py
"""KazData regional scraper

This script crawls the catalogue page https://kazdata.kz/04/katalog-kazakhstan.html,
collects every regional link in the `<ul class="article-list">`, then visits each
link, extracts the company table (`<table class="sp">`) and writes the rows to a
separate CSV file in **parser/regions/**.

File layout created at runtime:
    parser/
        kazdata_parser.py
        regions/
            2015-kazakhstan-astana-311.csv
            2015-kazakhstan-akmolinskaya-oblast-305-310-311.csv
            2017-oblast-akmolinskaya.csv
            ...

Usage:
    pip install -r requirements.txt
    playwright install chromium
    python parser/kazdata_parser.py
"""

import asyncio
import csv
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

CATALOG_URL = "https://kazdata.kz/04/katalog-kazakhstan.html"
BASE_DIR = Path(__file__).parent
REGION_DIR = BASE_DIR / "regions"
REGION_DIR.mkdir(parents=True, exist_ok=True)

FIELDNAMES = [
    "BIN",
    "Company",
    "OKED",
    "Activity",
    "KATO",
    "Locality",
    "KRP",
    "Size",
]


def slugify(text: str) -> str:
    """Return a filesystem‑safe slug from a string (ASCII, underscore‑separated)."""
    text = re.sub(r"<[^>]+>", "", text)  # strip HTML entities, just in case
    text = re.sub(r"[^\w\-]+", "_", text.lower()).strip("_")
    return text or "region"


async def scrape_region(page, href: str, title: str | None = None):
    """Scrape a single region page and save its table to CSV."""
    url = urljoin(CATALOG_URL, href)
    pretty_name = title or href
    slug = Path(href).stem or slugify(pretty_name)
    csv_path = REGION_DIR / f"{slug}.csv"

    try:
        await page.goto(url, timeout=60_000)
        await page.wait_for_selector("table.sp tbody tr", timeout=15_000)
    except PlaywrightTimeout:
        print(f"⚠️  Timeout while loading {url}. Skipping.")
        return 0

    rows = await page.query_selector_all("table.sp tbody tr")
    if len(rows) <= 1:
        print(f"⚠️  No data rows found on {url}.")
        return 0

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        count = 0
        for row in rows[1:]:  # skip header
            cells = await row.query_selector_all("th, td")
            texts = [" ".join((await c.inner_text()).split()) for c in cells]
            if len(texts) != 8:
                print(
                    f"⚠️  Row with {len(texts)} columns on {url}. Skipping row.")
                continue
            writer.writerow(dict(zip(FIELDNAMES, texts)))
            count += 1

    print(f"✅  Saved {count} rows → {csv_path.relative_to(BASE_DIR)}")
    return count


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 1️⃣  Gather regional links from the catalogue
        await page.goto(CATALOG_URL, timeout=60_000)
        region_links = await page.eval_on_selector_all(
            "ul.article-list a",
            "els => els.map(e => ({ href: e.getAttribute('href'), text: e.textContent.trim() }))",
        )

        if not region_links:
            print("❗ No region links found – page structure may have changed.")
            await browser.close()
            return

        total = 0
        for link in region_links:
            total += await scrape_region(page, link["href"], link["text"])

        await browser.close()
        print(f"\n🎉  Done! Total rows saved across regions: {total}")


if __name__ == "__main__":
    asyncio.run(main())
