"""update_tax_data_columns_to_bigint

Revision ID: 405f6de71fd5
Revises: optimize_company_indexes
Create Date: 2025-07-19 15:03:57.385784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '405f6de71fd5'
down_revision: Union[str, None] = 'optimize_company_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change tax_data columns from TEXT to BIGINT
    op.alter_column('companies', 'tax_data_2023',
                    existing_type=sa.TEXT(),
                    type_=sa.BigInteger(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2023::BIGINT")
    
    op.alter_column('companies', 'tax_data_2024',
                    existing_type=sa.TEXT(),
                    type_=sa.BigInteger(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2024::BIGINT")
    
    op.alter_column('companies', 'tax_data_2025',
                    existing_type=sa.TEXT(),
                    type_=sa.BigInteger(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2025::BIGINT")


def downgrade() -> None:
    """Downgrade schema."""
    # Change tax_data columns back from BIGINT to TEXT
    op.alter_column('companies', 'tax_data_2023',
                    existing_type=sa.BigInteger(),
                    type_=sa.TEXT(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2023::TEXT")
    
    op.alter_column('companies', 'tax_data_2024',
                    existing_type=sa.BigInteger(),
                    type_=sa.TEXT(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2024::TEXT")
    
    op.alter_column('companies', 'tax_data_2025',
                    existing_type=sa.BigInteger(),
                    type_=sa.TEXT(),
                    existing_nullable=True,
                    postgresql_using="tax_data_2025::TEXT")
