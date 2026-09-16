"""Add expires_at to decisions
Revision ID: 48a99ab75bca
Revises: 0001_initial
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa

revision = '48a99ab75bca'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('decisions', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('decisions', 'expires_at')