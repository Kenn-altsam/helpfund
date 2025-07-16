from fastapi import APIRouter, Depends, HTTPException, Query
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
    limit: int = Query(100, ge=1, le=500, description="Number of companies to process in this batch (default 100)"),
    offset: int = Query(0, ge=0, description="Offset for batch processing (default 0)"),
):
    """
    TEMPORARY ENDPOINT: Fetches and parses data from ba.prg.kz API, updates company fields if NULL and API value is not null.
    Processes companies in batches using limit and offset.
    """
    try:
        bin_rows = db.execute(text('SELECT "BIN" FROM companies ORDER BY "BIN" OFFSET :offset LIMIT :limit'), {"offset": offset, "limit": limit}).fetchall()
        company_bins = [row[0] for row in bin_rows]
        updated = 0
        failed = 0
        for bin in company_bins:
            try:
                api_url = f"https://apiba.prgapp.kz/CompanyFullInfo?id={bin}&lang=ru"
                resp = requests.get(api_url, timeout=10)
                if resp.status_code != 200:
                    logging.warning(f"Failed to fetch {api_url} (status {resp.status_code})")
                    continue
                try:
                    data = resp.json()
                except Exception:
                    logging.error(f"Non-JSON response for BIN={bin}")
                    continue

                # Defensive extraction
                tax_data_2023 = tax_data_2024 = tax_data_2025 = contacts = website = None

                tax_graph = data.get('taxes', {}).get('taxGraph', [])
                if isinstance(tax_graph, list):
                    for item in tax_graph:
                        if item.get('year') == 2023:
                            tax_data_2023 = item.get('value')
                        if item.get('year') == 2024:
                            tax_data_2024 = item.get('value')
                        if item.get('year') == 2025:
                            tax_data_2025 = item.get('value')

                phones = []
                egov_contacts = data.get('egovContacts')
                if egov_contacts and isinstance(egov_contacts.get('phone'), list):
                    phones = [p['value'] for p in egov_contacts['phone'] if 'value' in p]

                emails = []
                goszakup_contacts = data.get('gosZakupContacts')
                if goszakup_contacts and isinstance(goszakup_contacts.get('email'), list):
                    emails = [e['value'] for e in goszakup_contacts['email'] if 'value' in e]

                contacts = ', '.join(phones + emails) if (phones or emails) else None

                websites = []
                if goszakup_contacts and isinstance(goszakup_contacts.get('website'), list):
                    websites = [w['value'] for w in goszakup_contacts['website'] if 'value' in w]
                website = websites[0] if websites else None

                # Build update only for non-null values
                update_fields = {}
                set_clauses = []
                if tax_data_2023 is not None:
                    set_clauses.append('tax_data_2023 = CASE WHEN tax_data_2023 IS NULL THEN :tax2023 ELSE tax_data_2023 END')
                    update_fields['tax2023'] = str(tax_data_2023)
                if tax_data_2024 is not None:
                    set_clauses.append('tax_data_2024 = CASE WHEN tax_data_2024 IS NULL THEN :tax2024 ELSE tax_data_2024 END')
                    update_fields['tax2024'] = str(tax_data_2024)
                if tax_data_2025 is not None:
                    set_clauses.append('tax_data_2025 = CASE WHEN tax_data_2025 IS NULL THEN :tax2025 ELSE tax_data_2025 END')
                    update_fields['tax2025'] = str(tax_data_2025)
                if contacts is not None:
                    set_clauses.append('contacts = CASE WHEN contacts IS NULL THEN :contacts ELSE contacts END')
                    update_fields['contacts'] = contacts
                if website is not None:
                    set_clauses.append('website = CASE WHEN website IS NULL THEN :website ELSE website END')
                    update_fields['website'] = website

                if set_clauses:
                    update_fields['bin'] = bin
                    sql = text(f'''
                        UPDATE companies
                        SET {', '.join(set_clauses)}
                        WHERE "BIN" = :bin
                    ''')
                    db.execute(sql, update_fields)
                    db.commit()
                    updated += 1
                    logging.info(f"Updated company BIN={bin}")
            except Exception as e:
                db.rollback()
                logging.error(f"Error processing BIN={bin}: {e}")
                failed += 1
        return {"message": f"Updated {updated} companies, failed {failed} (using ba.prg.kz API, nulls skipped, batch: offset={offset}, limit={limit})"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Parser error: {e}") 