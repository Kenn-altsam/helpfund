from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import requests
from bs4 import BeautifulSoup
from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..auth.models import User

router = APIRouter(
    prefix="/dev/parse-ba-prg",
    tags=["Dev/Parser"],
    responses={404: {"description": "Not found"}, 500: {"description": "Internal server error"}},
)

@router.post("/run", summary="Parse and update company data from ba.prg.kz (TEMPORARY)")
def parse_and_update_ba_prg(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    TEMPORARY ENDPOINT: Fetches and parses data from ba.prg.kz, updates company fields if NULL.
    This endpoint is for one-time use and should be deleted after use.
    """
    try:
        # Example: Fetch the main page (replace with actual company-specific logic as needed)
        url = "https://ba.prg.kz/"
        resp = requests.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch ba.prg.kz")
        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Example parsing logic ---
        # You must adapt this to the actual structure of company pages on ba.prg.kz
        # For demonstration, we'll just parse the main page for some dummy data
        # In real use, you would loop over companies, fetch their pages, and extract the fields
        # tax_data_2023, tax_data_2024, tax_data_2025, contacts, website
        #
        # Example: Let's say you have a list of company BINs to update
        company_bins = ["201140015461", "250440002972", "971240001315"]  # Replace with real BINs or logic
        updated = 0
        for bin in company_bins:
            # Fetch company page (replace with real URL pattern)
            company_url = f"https://ba.prg.kz/company/{bin}"
            c_resp = requests.get(company_url)
            if c_resp.status_code != 200:
                continue
            c_soup = BeautifulSoup(c_resp.text, "html.parser")
            # Parse fields (replace with real selectors)
            tax_data_2023 = None  # c_soup.select_one('...')
            tax_data_2024 = None  # c_soup.select_one('...')
            tax_data_2025 = None  # c_soup.select_one('...')
            contacts = None       # c_soup.select_one('...')
            website = None        # c_soup.select_one('...')
            # Only update if any field is not None and the DB field is NULL
            sql = text("""
                UPDATE companies
                SET
                    tax_data_2023 = COALESCE(tax_data_2023, :tax2023),
                    tax_data_2024 = COALESCE(tax_data_2024, :tax2024),
                    tax_data_2025 = COALESCE(tax_data_2025, :tax2025),
                    contacts = COALESCE(contacts, :contacts),
                    website = COALESCE(website, :website)
                WHERE \"BIN\" = :bin
            """)
            db.execute(sql, {
                "tax2023": tax_data_2023,
                "tax2024": tax_data_2024,
                "tax2025": tax_data_2025,
                "contacts": contacts,
                "website": website,
                "bin": bin
            })
            updated += 1
        db.commit()
        return {"message": f"Updated {updated} companies (dummy logic, replace with real parser)"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Parser error: {e}") 