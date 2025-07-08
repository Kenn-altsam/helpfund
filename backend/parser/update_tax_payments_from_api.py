"""
Script: update_tax_payments_from_api.py

Fetch tax payment information for companies that are missing the values
`tax_payment_2021 … tax_payment_2025` and update the database in place.

Usage (from project root):

    poetry run python backend/parser/update_tax_payments_from_api.py

The script:
1. Connects to the existing PostgreSQL DB by re-using the SQLAlchemy
   engine/session from backend.src.core.database.
2. Selects all companies where **any** of the tax_payment_20XX columns
   is NULL.
3. For every such company it calls the public endpoint::

       https://apiba.prgapp.kz/CompanyFullInfo?id=<BIN>&lang=ru

   and attempts to read the keys `tax_payment_2021 … tax_payment_2025`
   from the returned JSON. If at least one value is present and was
   previously NULL, the script writes it back to the DB.
4. If data for a company cannot be downloaded or parsed the script logs
   the error and safely continues with the next BIN.
"""

from __future__ import annotations

import logging
import sys
from typing import Dict, Any

import requests
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

# Make sure the backend directory is on PYTHONPATH when this script is run
# directly (e.g. `python backend/parser/update_tax_payments_from_api.py`).
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[2]

# Add <repo>/backend to PYTHONPATH so that the `src` package becomes importable
sys.path.append(str(ROOT_DIR / "backend"))  # noqa: E402

# Path for type checkers / optional direct access
SRC_PATH = ROOT_DIR / "backend" / "src"

# Deferred imports (after modifying sys.path)
from src.core.database import SessionLocal  # type: ignore  # noqa: E402
from src.companies.models import Company  # type: ignore  # noqa: E402

API_TEMPLATE = "https://apiba.prgapp.kz/CompanyFullInfo?id={bin}&lang=ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

TAX_YEARS = [2021, 2022, 2023, 2024, 2025]


def fetch_tax_data(bin_number: str) -> Dict[str, Any] | None:
    """Fetch tax payment data for a given BIN.

    The external API is expected to return JSON. We optimistically look for
    keys named exactly ``tax_payment_<year>``. If that fails but there is a
    nested ``tax_payments`` object (as observed in similar endpoints) we try
    to read values from there.
    """
    url = API_TEMPLATE.format(bin=bin_number)
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            logging.warning("%s → HTTP %s", url, resp.status_code)
            return None
        data: Dict[str, Any] = resp.json()

        result: Dict[str, Any] = {}
        for year in TAX_YEARS:
            key = f"tax_payment_{year}"
            # 1️⃣ Вариант 1: ключи на верхнем уровне
            if key in data and data[key] is not None:
                result[key] = data[key]
                continue

            # 2️⃣ Вариант 2: вложенный объект {"tax_payments": {"2021": value}}
            if isinstance(data.get("tax_payments"), dict):
                nested_val = data["tax_payments"].get(str(year))
                if nested_val is not None:
                    result[key] = nested_val
                    continue

        # 3️⃣ Вариант 3: массив taxGraph
        if isinstance(data.get("taxGraph"), list):
            for item in data["taxGraph"]:
                y = item.get("year")
                val = item.get("value")
                if y in TAX_YEARS and val is not None:
                    result[f"tax_payment_{y}"] = val
        return result or None
    except Exception as exc:  # broad catch is OK for a maintenance script
        logging.error("Failed to fetch data for BIN %s: %s", bin_number, exc)
        return None


def main() -> None:
    session: Session = SessionLocal()
    try:
        # Build a filter: any of the tax payment columns is NULL
        null_filter = or_(
            Company.tax_payment_2021.is_(None),
            Company.tax_payment_2022.is_(None),
            Company.tax_payment_2023.is_(None),
            Company.tax_payment_2024.is_(None),
            Company.tax_payment_2025.is_(None),
        )

        companies_to_update = session.scalars(select(Company).where(null_filter)).all()
        logging.info("%d companies with missing tax data", len(companies_to_update))

        updated_rows = 0
        for company in companies_to_update:
            bin_number = company.bin_number
            if not bin_number:
                continue

            tax_data = fetch_tax_data(bin_number)
            if not tax_data:
                continue  # nothing fetched → skip

            changed = False
            for key, value in tax_data.items():
                if getattr(company, key) is None and value is not None:
                    setattr(company, key, value)
                    changed = True

            if changed:
                session.add(company)
                updated_rows += 1
                logging.info("Updated %s with new tax data", bin_number)

            # Flush periodically to avoid huge transaction (optional)
            if updated_rows and updated_rows % 100 == 0:
                session.commit()
                logging.info("Committed after %d updates", updated_rows)

        session.commit()
        logging.info("Finished. Total companies updated: %d", updated_rows)

    finally:
        session.close()


if __name__ == "__main__":
    main() 