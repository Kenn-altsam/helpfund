from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import requests
import logging
from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..auth.models import User

router = APIRouter(
    prefix="/dev/parse-ba-prg",
    tags=["Dev/Parser"],
    responses={404: {"description": "Not found"}, 500: {"description": "Internal server error"}},
)

@router.post("/run", summary="Parse and update company data from ba.prg.kz API (TEMPORARY)")
def parse_and_update_ba_prg(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    TEMPORARY ENDPOINT: Fetches and parses data from ba.prg.kz API, updates company fields if NULL.
    This endpoint is for one-time use and should be deleted after use.
    """
    try:
        # 1. Get all BINs from the companies table
        bin_rows = db.execute(text('SELECT "BIN" FROM companies')).fetchall()
        company_bins = [row[0] for row in bin_rows]
        updated = 0
        failed = 0
        for bin in company_bins:
            try:
                api_url = f"https://apiba.prgapp.kz/CompanyFullInfo?id={bin}&lang=ru"
                resp = requests.get(api_url, timeout=10)
                if resp.status_code != 200:
                    logging.warning(f"Failed to fetch {api_url} (status {resp.status_code})")
                    failed += 1
                    continue
                data = resp.json()
                # --- Extract tax data ---
                tax_data_2023 = None
                tax_data_2024 = None
                tax_data_2025 = None
                try:
                    tax_graph = data.get('taxes', {}).get('taxGraph', [])
                    for item in tax_graph:
                        if item.get('year') == 2023:
                            tax_data_2023 = item.get('value')
                        if item.get('year') == 2024:
                            tax_data_2024 = item.get('value')
                        if item.get('year') == 2025:
                            tax_data_2025 = item.get('value')
                except Exception as e:
                    logging.error(f"Error extracting tax data for BIN={bin}: {e}")
                # --- Extract contacts ---
                phones = [p['value'] for p in data.get('egovContacts', {}).get('phone', [])]
                emails = [e['value'] for e in data.get('gosZakupContacts', {}).get('email', [])]
                contacts = ', '.join(phones + emails) if (phones or emails) else None
                # --- Extract website ---
                websites = [w['value'] for w in data.get('gosZakupContacts', {}).get('website', [])]
                website = websites[0] if websites else None
                # Only update if any field is not None and the DB field is NULL
                sql = text('''
                    UPDATE companies
                    SET
                        tax_data_2023 = CASE WHEN tax_data_2023 IS NULL THEN :tax2023 ELSE tax_data_2023 END,
                        tax_data_2024 = CASE WHEN tax_data_2024 IS NULL THEN :tax2024 ELSE tax_data_2024 END,
                        tax_data_2025 = CASE WHEN tax_data_2025 IS NULL THEN :tax2025 ELSE tax_data_2025 END,
                        contacts = CASE WHEN contacts IS NULL THEN :contacts ELSE contacts END,
                        website = CASE WHEN website IS NULL THEN :website ELSE website END
                    WHERE "BIN" = :bin
                ''')
                db.execute(sql, {
                    "tax2023": tax_data_2023,
                    "tax2024": tax_data_2024,
                    "tax2025": tax_data_2025,
                    "contacts": contacts,
                    "website": website,
                    "bin": bin
                })
                updated += 1
                logging.info(f"Updated company BIN={bin}")
            except Exception as e:
                logging.error(f"Error processing BIN={bin}: {e}")
                failed += 1
        db.commit()
        return {"message": f"Updated {updated} companies, failed {failed} (using ba.prg.kz API)"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Parser error: {e}") 