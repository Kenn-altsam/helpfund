"""Optimize company indexes for performance

Revision ID: optimize_company_indexes
Revises: d91aca5b8c9d
Create Date: 2025-01-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'optimize_company_indexes'
down_revision: Union[str, None] = 'd91aca5b8c9d'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    """Add performance optimization indexes."""
    
    # 1. Composite index for location + tax payment queries (most common pattern)
    op.create_index(
        'ix_companies_locality_tax_2025',
        'companies',
        ['Locality', 'tax_payment_2025'],
        postgresql_ops={'tax_payment_2025': 'DESC'}
    )
    
    # 2. Composite index for activity + tax payment queries
    op.create_index(
        'ix_companies_activity_tax_2025',
        'companies',
        ['Activity', 'tax_payment_2025'],
        postgresql_ops={'tax_payment_2025': 'DESC'}
    )
    
    # 3. Partial index for companies with tax data (faster sorting)
    op.create_index(
        'ix_companies_tax_2025_not_null',
        'companies',
        ['tax_payment_2025'],
        postgresql_ops={'tax_payment_2025': 'DESC'},
        postgresql_where=sa.text("tax_payment_2025 IS NOT NULL")
    )
    
    # 4. Full-text search index for company names
    op.execute("""
        CREATE INDEX ix_companies_name_gin ON companies 
        USING gin(to_tsvector('russian', "Company"))
    """)
    
    # 5. Full-text search index for activities
    op.execute("""
        CREATE INDEX ix_companies_activity_gin ON companies 
        USING gin(to_tsvector('russian', "Activity"))
    """)
    
    # 6. Index for company size filtering
    op.create_index('ix_companies_size', 'companies', ['Size'])
    
    # 7. Composite index for region + size + tax queries
    op.create_index(
        'ix_companies_locality_size_tax_2025',
        'companies',
        ['Locality', 'Size', 'tax_payment_2025'],
        postgresql_ops={'tax_payment_2025': 'DESC'}
    )


def downgrade() -> None:
    """Remove performance optimization indexes."""
    
    op.drop_index('ix_companies_locality_tax_2025')
    op.drop_index('ix_companies_activity_tax_2025')
    op.drop_index('ix_companies_tax_2025_not_null')
    op.drop_index('ix_companies_name_gin')
    op.drop_index('ix_companies_activity_gin')
    op.drop_index('ix_companies_size')
    op.drop_index('ix_companies_locality_size_tax_2025') 