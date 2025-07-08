from __future__ import annotations

"""Update Companies from Extracted CSVs

This utility reads every `*_extracted.csv` inside `parser/extracted/` and
updates the existing `companies` table with the corresponding columns:
    BIN (match key)
    location,
    tax_payment_2021 … tax_payment_2025,
    degreeofrisk,
    executive,
    phone,
    email

Rows are matched by the `BIN` value. If a company with a given BIN is not found
in the database the row is **skipped** (we cannot insert because
`company_name` is mandatory). A short summary is printed at the end.

Usage (from repo root):
    python backend/parser/update_companies_from_extracted.py
"""

import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv

from sqlalchemy import inspect, text, create_engine

# ---------------------------------------------------------------------------
# Ensure backend/src is importable
# ---------------------------------------------------------------------------

# Add backend directory (so 'src' package is importable)
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

# Optional: also include backend/src directly for legacy absolute-import paths
BACKEND_SRC = BACKEND_DIR / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.append(str(BACKEND_SRC))

# pylint: disable=import-error
from src.core.database import SessionLocal  # type: ignore
from src.companies.models import Company  # type: ignore

# ---------------------------------------------------------------------------
load_dotenv()
EXTRACTED_DIR = Path(__file__).parent / "extracted"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: str) -> Optional[float]:
    """Convert to float, returning None for blanks/invalid."""
    if value is None:
        return None
    value = value.strip().replace(" ", "").replace(",", "")
    if value == "" or value in {"-", "."}:
        return None
    try:
        return float(Decimal(value))
    except (ValueError, InvalidOperation):
        return None


def load_csv(filepath: Path) -> List[Dict[str, Optional[str]]]:
    rows: List[Dict[str, Optional[str]]] = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalised = {k.strip(): (v.strip() if v is not None else None) for k, v in row.items()}
            rows.append(normalised)
    return rows

# ---------------------------------------------------------------------------
# Ensure DB columns exist
# ---------------------------------------------------------------------------

# We need an engine to run raw DDL; reuse the one used by SessionLocal
engine = SessionLocal.kw['bind'] if hasattr(SessionLocal, 'kw') else SessionLocal().get_bind()  # type: ignore


def ensure_extended_columns_exist():
    """Add new columns to `companies` table if they are missing."""
    required_columns = {
        "location": "VARCHAR(255)",
        "tax_payment_2021": "DOUBLE PRECISION",
        "tax_payment_2022": "DOUBLE PRECISION",
        "tax_payment_2023": "DOUBLE PRECISION",
        "tax_payment_2024": "DOUBLE PRECISION",
        "tax_payment_2025": "DOUBLE PRECISION",
        "degreeofrisk": "VARCHAR(100)",
        "executive": "VARCHAR(255)",
        "phone": "VARCHAR(100)",
        "email": "VARCHAR(255)"
    }

    inspector = inspect(engine)
    columns_info = {col["name"]: col for col in inspector.get_columns("companies")}
    existing = set(columns_info.keys())

    with engine.begin() as conn:  # transactional DDL
        for col_name, col_type in required_columns.items():
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                print(f"➕ Added column {col_name} to companies")
            else:
                # Column exists – if it is one of the tax columns and not already DOUBLE PRECISION, widen it.
                if col_name.startswith("tax_payment_"):
                    data_type = columns_info[col_name]["type"].__class__.__name__.lower()
                    if "numeric" in data_type or "float" in data_type or "double" not in data_type:
                        conn.execute(text(
                            f"ALTER TABLE companies ALTER COLUMN {col_name} TYPE DOUBLE PRECISION USING {col_name}::double precision"
                        ))
                        print(f"🔄 Altered column {col_name} to DOUBLE PRECISION")

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def update_from_csv(session, rows: List[Dict[str, Optional[str]]]):
    skipped_no_company = 0
    updated = 0
    for row in rows:
        bin_val = row.get("BIN")
        if not bin_val:
            continue
        company: Optional[Company] = session.query(Company).filter_by(bin_number=bin_val).first()
        if not company:
            skipped_no_company += 1
            continue

        company.location = row.get("location") or company.location
        company.tax_payment_2021 = _safe_float(row.get("tax_payment_2021")) or company.tax_payment_2021
        company.tax_payment_2022 = _safe_float(row.get("tax_payment_2022")) or company.tax_payment_2022
        company.tax_payment_2023 = _safe_float(row.get("tax_payment_2023")) or company.tax_payment_2023
        company.tax_payment_2024 = _safe_float(row.get("tax_payment_2024")) or company.tax_payment_2024
        company.tax_payment_2025 = _safe_float(row.get("tax_payment_2025")) or company.tax_payment_2025
        company.degreeofrisk = row.get("degreeofrisk") or company.degreeofrisk
        company.executive = row.get("executive") or company.executive
        company.phone = row.get("phone") or company.phone
        company.email = row.get("email") or company.email

        updated += 1
    return updated, skipped_no_company


def main():
    # Make sure DB schema is ready
    ensure_extended_columns_exist()

    csv_files = sorted(EXTRACTED_DIR.glob("*_extracted.csv"))
    if not csv_files:
        print("❌ No CSV files found in", EXTRACTED_DIR)
        return

    total_updated = 0
    total_skipped = 0
    with SessionLocal() as session:
        for csv_file in csv_files:
            rows = load_csv(csv_file)
            updated, skipped = update_from_csv(session, rows)
            session.commit()
            total_updated += updated
            total_skipped += skipped
            print(f"📝 {csv_file.name}: updated {updated}, skipped {skipped}")

    print(f"✅ Finished. Total updated: {total_updated}, total skipped: {total_skipped}")


if __name__ == "__main__":
    main() 