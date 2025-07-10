from __future__ import annotations

"""Extracted Data Importer

This script loads all CSV files located in the `parser/extracted` directory and
inserts their contents into a dedicated PostgreSQL table.

The expected CSV header is exactly:
    BIN,location,tax_payment_2021,tax_payment_2022,tax_payment_2023,
    tax_payment_2024,tax_payment_2025,degreeofrisk,executive,phone,email

If the destination table (`extracted_company_data`) does not yet exist, it is
created automatically. Each row is identified by the `BIN` value. If a row with
an identical `BIN` already exists it will be **updated** (upsert).

Usage (from repository root):
    python -m parser.extracted_data_importer

Environment variable `DATABASE_URL` must be set (see `backend/.env.example`).
"""

import csv
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Float,
    String,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
import uuid

# ---------------------------------------------------------------------------
# Configuration & Setup
# ---------------------------------------------------------------------------

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
EXTRACTED_DIR = BASE_DIR / "extracted"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/Ayala_database",
)

# Create the SQLAlchemy engine & base
engine = create_engine(DATABASE_URL, echo=False, future=True)
Base = declarative_base()

# ---------------------------------------------------------------------------
# Model definition – mirrors the CSV structure exactly
# ---------------------------------------------------------------------------

class ExtractedCompanyData(Base):
    __tablename__ = "extracted_company_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Keep column names exactly as in CSV for clarity. PostgreSQL folds to lower
    # case automatically unless quoted; therefore we store them lower-case with
    # matching attribute names.
    BIN = Column(String(12), index=True, unique=True, nullable=False)
    location = Column(String(255))

    tax_payment_2021 = Column(Float)
    tax_payment_2022 = Column(Float)
    tax_payment_2023 = Column(Float)
    tax_payment_2024 = Column(Float)
    tax_payment_2025 = Column(Float)

    degreeofrisk = Column(String(50))
    executive = Column(String(255))
    phone = Column(String(100))
    email = Column(String(255))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExtractedCompanyData BIN={self.BIN}>"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _safe_float(value: str) -> Optional[float]:
    """Convert a string to float safely, returning ``None`` for invalid/blank."""
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
    """Read a CSV file and return list of row dictionaries."""
    rows: List[Dict[str, Optional[str]]] = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize header keys to match our model attributes
            normalised = {k.strip(): (v.strip() if v is not None else None) for k, v in row.items()}
            rows.append(normalised)
    return rows


def ensure_table_exists():
    """Create destination table if it is not already present."""
    inspector = inspect(engine)
    # if "extracted_company_data" not in inspector.get_table_names():
        # Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Core importer logic
# ---------------------------------------------------------------------------

def upsert_rows(session: Session, csv_rows: List[Dict[str, Optional[str]]]):
    """Insert or update rows based on BIN primary key."""
    for row in csv_rows:
        if not row.get("BIN"):
            continue  # Skip rows without BIN

        existing: Optional[ExtractedCompanyData] = (
            session.query(ExtractedCompanyData).filter_by(BIN=row["BIN"]).first()
        )

        mapped = {
            "location": row.get("location"),
            "tax_payment_2021": _safe_float(row.get("tax_payment_2021")),
            "tax_payment_2022": _safe_float(row.get("tax_payment_2022")),
            "tax_payment_2023": _safe_float(row.get("tax_payment_2023")),
            "tax_payment_2024": _safe_float(row.get("tax_payment_2024")),
            "tax_payment_2025": _safe_float(row.get("tax_payment_2025")),
            "degreeofrisk": row.get("degreeofrisk"),
            "executive": row.get("executive"),
            "phone": row.get("phone"),
            "email": row.get("email"),
        }

        if existing:
            for key, value in mapped.items():
                setattr(existing, key, value)
        else:
            new_entry = ExtractedCompanyData(BIN=row["BIN"], **mapped)
            session.add(new_entry)


def import_all_csvs():
    """Main entry point: import every CSV inside `parser/extracted`."""
    ensure_table_exists()

    csv_files = sorted(EXTRACTED_DIR.glob("*_extracted.csv"))
    if not csv_files:
        print("❌ No CSV files found in", EXTRACTED_DIR)
        return

    with Session(engine) as session:
        total_inserted = 0
        for csv_file in csv_files:
            print(f"📝 Processing {csv_file.name}…", end=" ")
            rows = load_csv(csv_file)
            pre_count = session.query(ExtractedCompanyData).count()

            upsert_rows(session, rows)
            session.commit()

            post_count = session.query(ExtractedCompanyData).count()
            inserted_this_file = post_count - pre_count
            total_inserted += inserted_this_file
            print(f"done (+{inserted_this_file})")

        print(f"✅ Import completed. Total rows now: {total_inserted} new/updated.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import_all_csvs() 