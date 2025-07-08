"""
update_tax_payments_with_chromium.py

Fetches tax payment amounts (2021-2025) for companies whose `tax_payment_20XX` fields
are NULL.  For every company the script calls

    https://apiba.prgapp.kz/CompanyFullInfo?id=<BIN>&lang=ru

parses the JSON (preferring the `taxGraph` array) and writes the numeric values back
into the DB columns `tax_payment_2021` … `tax_payment_2025`.

The download is performed via Playwright (Chromium) so that we honour the user's
request to use a real browser.  Make sure Playwright is installed *and* the browser
binary is fetched:

    pip install playwright
    playwright install chromium

Usage (from repository root):

    poetry run python backend/parser/update_tax_payments_with_chromium.py

"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright, Page

# ---------------------------------------------------------------------------
# Import project modules (add `backend` to PYTHONPATH so that `src` is importable)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

# pylint: disable=import-error
from src.core.database import SessionLocal  # type: ignore
from src.companies.models import Company  # type: ignore

# ---------------------------------------------------------------------------
API_TEMPLATE = "https://apiba.prgapp.kz/CompanyFullInfo?id={bin}&lang=ru"
TAX_YEARS: List[int] = [2021, 2022, 2023, 2024, 2025]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

async def _extract_tax_values(data: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return a mapping tax_payment_<year> → value extracted from the JSON."""

    result: Dict[str, Optional[float]] = {}

    # Preferred: array of objects → {"year": 2021, "value": 123.45}
    if isinstance(data.get("taxGraph"), list):
        for item in data["taxGraph"]:
            year = item.get("year")
            value = item.get("value")
            if year in TAX_YEARS and value is not None:
                result[f"tax_payment_{year}"] = value

    # Fallback 1: flat keys tax_payment_2021 …
    for year in TAX_YEARS:
        key = f"tax_payment_{year}"
        if key in data and data[key] is not None:
            result[key] = data[key]

    # Fallback 2: nested object tax_payments = {"2021": value}
    if isinstance(data.get("tax_payments"), dict):
        for year in TAX_YEARS:
            nested_val = data["tax_payments"].get(str(year))
            if nested_val is not None:
                result[f"tax_payment_{year}"] = nested_val

    return result


async def fetch_tax_data(page: Page, bin_number: str) -> Dict[str, float] | None:
    """Download JSON for *bin_number* and return the extracted tax values."""

    url = API_TEMPLATE.format(bin=bin_number)
    try:
        response = await page.request.get(url, timeout=15_000)
        if response.status != 200:
            logging.warning("%s → HTTP %s", url, response.status)
            return None
        data: Dict[str, Any] = await response.json()
        values = await _extract_tax_values(data)
        return values or None
    except Exception as exc:  # pragma: no cover – maintenance script
        logging.error("Failed to fetch data for BIN %s: %s", bin_number, exc)
        return None


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

async def process_companies(page: Page) -> None:
    """Iterate over companies with missing tax data and update them in DB."""

    session: Session = SessionLocal()
    try:
        missing_filter = or_(
            Company.tax_payment_2021.is_(None),
            Company.tax_payment_2022.is_(None),
            Company.tax_payment_2023.is_(None),
            Company.tax_payment_2024.is_(None),
            Company.tax_payment_2025.is_(None),
        )
        companies = session.scalars(select(Company).where(missing_filter)).all()
        logging.info("%d companies require tax updates", len(companies))

        updated_rows = 0
        for company in companies:
            bin_number = company.bin_number
            if not bin_number:
                continue

            tax_values = await fetch_tax_data(page, bin_number)
            if not tax_values:
                continue

            changed = False
            for col, value in tax_values.items():
                if getattr(company, col) is None and value is not None:
                    setattr(company, col, value)
                    changed = True

            if changed:
                session.add(company)
                updated_rows += 1

            # Commit periodically to avoid giant transaction
            if updated_rows and updated_rows % 100 == 0:
                session.commit()
                logging.info("Committed after %d updates", updated_rows)

        session.commit()
        logging.info("Finished. Total companies updated: %d", updated_rows)
    finally:
        session.close()


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await process_companies(page)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main()) 